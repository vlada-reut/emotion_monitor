from __future__ import annotations

import logging
import time
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from analytics.session_analyzer import (
    build_current_metrics,
    build_full_summary,
    build_session_metrics,
)
from analytics.stats import (
    age_group_to_russian,
    emotion_to_russian,
    gender_to_russian,
)
from analytics.summarizer import build_text_summary
from core.draw_utils import annotate_frame
from core.face_detector import FaceDetector
from core.models import AnalysisResult, FaceObservation, SessionState
from core.session_registry import SessionRegistry
from core.tracker import CentroidTracker
from core.video_capture import VideoCapture
from services.analysis_service import FaceAnalysisService
from services.config_service import Settings
from services.database_service import UserDatabaseService
from services.session_logger import SessionLogger
from services.weather_service import WeatherService


logger = logging.getLogger(__name__)


class VideoWorker(QThread):
    frame_ready = Signal(object, object)
    error_occurred = Signal(str)
    status_changed = Signal(str)
    session_finished = Signal(str)

    def __init__(self, settings: Settings, user_database: UserDatabaseService | None = None) -> None:
        super().__init__()
        self.settings = settings
        self.user_database = user_database
        self.running = False
        self._capture_error_reported = False
        self._resolved_users: dict[int, tuple[int, str]] = {}

        self.session = SessionState.create()
        self.registry = SessionRegistry(self.session)

        self.capture = VideoCapture(
            source=settings.app.camera_source,
            backend=settings.app.camera_backend,
        )
        self.detector: FaceDetector | None = None
        self.tracker: CentroidTracker | None = None
        self.analysis_service: FaceAnalysisService | None = None
        self.weather_service = WeatherService(settings.weather)
        self.session_logger = SessionLogger(
            logs_dir=settings.logging.logs_dir,
            session_id=self.session.session_id,
        )

    def _initialize_runtime(self) -> None:
        self.status_changed.emit("Подготовка моделей анализа...")
        self.detector = FaceDetector(
            model_path=self.settings.models.face_detector_path,
            confidence=self.settings.app.detector_confidence,
            imgsz=self.settings.app.detector_imgsz,
        )
        self.tracker = CentroidTracker(
            max_distance=self.settings.app.tracker_max_distance,
            max_missing=self.settings.app.tracker_max_missing,
        )
        self.analysis_service = FaceAnalysisService()

    @staticmethod
    def _clamp_bbox(frame, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = bbox

        x1 = max(0, min(int(x1), width - 1))
        y1 = max(0, min(int(y1), height - 1))
        x2 = max(0, min(int(x2), width))
        y2 = max(0, min(int(y2), height))

        return x1, y1, x2, y2

    @staticmethod
    def _is_valid_crop(bbox: tuple[int, int, int, int]) -> bool:
        x1, y1, x2, y2 = bbox
        return (x2 - x1) > 4 and (y2 - y1) > 4

    @staticmethod
    def _build_label(observation: FaceObservation) -> str:
        gender_ru = gender_to_russian(observation.gender)
        age_ru = str(observation.age) if observation.age is not None else age_group_to_russian(observation.age_group)
        emotion_ru = emotion_to_russian(observation.emotion)
        label_id = observation.user_id if observation.user_id is not None else observation.person_id
        return f"ID {label_id} | {gender_ru} | {age_ru} | {emotion_ru}"

    def _resolve_database_user(
        self,
        session_person_id: int,
        timestamp: str,
        result: AnalysisResult,
        embedding: list[float] | None,
    ) -> tuple[int, str] | None:
        cached = self._resolved_users.get(session_person_id)
        if cached is not None:
            return cached
        if self.user_database is None:
            return None

        try:
            user = self.user_database.resolve_user(
                embedding=embedding,
                observed_at=timestamp,
                gender=result.gender,
                age_group=result.age_group,
            )
        except Exception as error:
            logger.exception("Не удалось сопоставить пользователя с базой: %s", error)
            self.session_logger.log_event(
                f"Не удалось сопоставить пользователя с базой: {error}",
                level=logging.WARNING,
            )
            return None

        resolved = (user.user_id, user.display_name)
        self._resolved_users[session_person_id] = resolved
        return resolved

    def _should_reanalyze(self, track_id: int) -> bool:
        last_frame = self.session.last_analysis_frame.get(track_id)
        if last_frame is None:
            return True
        return (self.session.frames_processed - last_frame) >= self.settings.app.analysis_interval_frames

    def _get_weather_if_needed(self) -> None:
        now_ts = time.time()
        if not self.weather_service.should_refresh(now_ts):
            return

        try:
            self.status_changed.emit("Обновление погодных данных...")
            snapshot = self.weather_service.fetch_weather()
            self.session.last_weather = snapshot

            if snapshot is None:
                return

            if snapshot.weather_text == "погода в данный момент недоступна":
                self.session_logger.log_event(
                    "Погодные данные временно недоступны. Приложение продолжает работу без них.",
                    level=logging.WARNING,
                )
                self.status_changed.emit("Погода в данный момент недоступна")
                return

            self.session_logger.log_event(
                f"Получены погодные данные: "
                f"{snapshot.location_name}, {snapshot.temperature_c}°C, {snapshot.weather_text}"
            )
        except Exception as error:
            self.session_logger.log_event(
                f"Не удалось получить погодные данные: {error}",
                level=logging.WARNING,
            )

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        summary_path = ""

        try:
            self.status_changed.emit("Инициализация видеопотока...")
            self.capture.open(
                width=self.settings.app.frame_width,
                height=self.settings.app.frame_height,
            )
            self._initialize_runtime()

            self.running = True
            self.session_logger.log_event(f"Сессия {self.session.session_id} запущена")
            self.status_changed.emit("Мониторинг запущен")

            while self.running:
                loop_started = time.perf_counter()
                frame = self.capture.read()

                if frame is None:
                    if not self._capture_error_reported:
                        self._capture_error_reported = True
                        self.error_occurred.emit("Не удалось прочитать кадр из видеопотока")
                    self.msleep(50)
                    continue

                self._capture_error_reported = False
                self.session.frames_processed += 1
                self._get_weather_if_needed()

                if self.detector is None or self.tracker is None or self.analysis_service is None:
                    raise RuntimeError("Компоненты анализа видео не инициализированы")

                boxes = self.detector.detect(frame)
                tracked = self.tracker.update(boxes)
                active_track_ids = {track.track_id for track in tracked}
                self.registry.begin_frame(active_track_ids)

                current_active_faces: dict[int, FaceObservation] = {}
                annotations: list[dict] = []

                for track in tracked:
                    bbox = self._clamp_bbox(frame, track.bbox)
                    if not self._is_valid_crop(bbox):
                        continue

                    x1, y1, x2, y2 = bbox
                    face_crop = frame[y1:y2, x1:x2]

                    if face_crop.size == 0:
                        continue

                    if self._should_reanalyze(track.track_id):
                        previous_result = self.session.last_results.get(track.track_id)
                        if previous_result is None or (
                            previous_result.age is None and previous_result.gender == "unknown"
                        ):
                            result = self.analysis_service.analyze_full(face_crop)
                        else:
                            result = self.analysis_service.analyze_emotion(face_crop, previous_result)
                        self.session.last_results[track.track_id] = result
                        self.session.last_analysis_frame[track.track_id] = self.session.frames_processed
                    else:
                        result = self.session.last_results.get(track.track_id, AnalysisResult())

                    embedding = None
                    if track.track_id not in self.session.active_track_to_person:
                        embedding = self.analysis_service.extract_embedding(face_crop)

                    person_id = self.registry.resolve_person_id(
                        track.track_id,
                        embedding=embedding,
                    )

                    timestamp = datetime.now().isoformat(timespec="seconds")
                    resolved_user = self._resolve_database_user(
                        session_person_id=person_id,
                        timestamp=timestamp,
                        result=result,
                        embedding=embedding,
                    )

                    observation = FaceObservation(
                        person_id=person_id,
                        user_id=resolved_user[0] if resolved_user is not None else None,
                        timestamp=timestamp,
                        bbox=bbox,
                        emotion=result.emotion,
                        gender=result.gender,
                        age_group=result.age_group,
                        age=result.age,
                        confidence=result.confidence,
                    )

                    self.registry.register_observation(
                        track_id=track.track_id,
                        observation=observation,
                        embedding=embedding,
                    )
                    person = self.session.people.get(person_id)
                    if person is not None and resolved_user is not None:
                        person.user_id = resolved_user[0]
                        person.display_name = resolved_user[1]
                    current_active_faces[person_id] = observation

                    self.session_logger.log_observation(
                        observation,
                        weather=self.session.last_weather,
                        extra={
                            "frame_index": self.session.frames_processed,
                            "track_id": track.track_id,
                        },
                    )

                    annotations.append(
                        {
                            "bbox": bbox,
                            "label": self._build_label(observation),
                            "color": (0, 0, 255),
                        }
                    )

                self.registry.set_active_faces(current_active_faces)

                if annotations:
                    frame = annotate_frame(frame, annotations)

                current_metrics = build_current_metrics(self.session)
                session_metrics = build_session_metrics(self.session)

                elapsed = max(time.perf_counter() - loop_started, 1e-6)
                instant_fps = 1.0 / elapsed
                if self.session.fps == 0.0:
                    self.session.fps = instant_fps
                else:
                    self.session.fps = self.session.fps * 0.9 + instant_fps * 0.1

                weather_dict = self.session.last_weather.to_dict() if self.session.last_weather else None

                payload = {
                    "fps": round(self.session.fps, 2),
                    "current_metrics": current_metrics,
                    "session_metrics": session_metrics,
                    "current_summary": build_text_summary(
                        current_metrics,
                        weather=weather_dict,
                        mode="current",
                    ),
                    "session_summary": build_text_summary(
                        session_metrics,
                        weather=weather_dict,
                        mode="session",
                    ),
                    "weather": weather_dict,
                    "logs_dir": str(self.session_logger.logs_dir),
                }

                self.frame_ready.emit(frame, payload)
                self.msleep(1)

        except Exception as error:
            logger.exception("Ошибка в рабочем потоке обработки видео: %s", error)
            self.session_logger.log_event(
                f"Критическая ошибка потока обработки: {error}",
                level=logging.ERROR,
            )
            self.error_occurred.emit(str(error))

        finally:
            try:
                summary = build_full_summary(self.session)
                summary_path = str(self.session_logger.write_summary(summary))
                if self.user_database is not None:
                    try:
                        self.user_database.save_session(self.session, summary_path)
                    except Exception as error:
                        logger.exception("Не удалось сохранить данные сессии в базу: %s", error)
                        self.session_logger.log_event(
                            f"Не удалось сохранить данные сессии в базу: {error}",
                            level=logging.WARNING,
                        )
                self.session_logger.log_event(
                    f"Сессия {self.session.session_id} завершена. "
                    f"Итоговый отчет сохранен: {summary_path}"
                )
            finally:
                self.capture.release()
                self.session_logger.close()

                if summary_path:
                    self.session_finished.emit(summary_path)

                self.status_changed.emit("Мониторинг остановлен")
