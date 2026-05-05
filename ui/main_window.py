from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from analytics.stats import emotion_to_russian
from services.config_service import Settings
from services.database_service import UserDatabaseService
from ui.summary_panel import SummaryPanel
from ui.user_search_panel import UserSearchPanel

if TYPE_CHECKING:
    from core.video_worker import VideoWorker


SOFT_BLUE = "#5f88e8"
SOFT_BLUE_HOVER = "#4f79dc"
ALERT_RED = "#ff4d5f"
UNAVAILABLE_WEATHER_TEXT = (
    "Погодные данные пока недоступны. Связь между погодой и настроением аудитории "
    "будет рассчитана после обновления прогноза."
)


def _card(name: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName(name)
    frame.setFrameShape(QFrame.Shape.NoFrame)
    return frame


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.user_database = UserDatabaseService(settings.database)
        self.worker: VideoWorker | None = None
        self.last_summary_path: str = ""
        self.current_mode = "current"
        self.monitoring_active = False

        self.setWindowTitle(settings.app.title)
        self.resize(1460, 860)
        self.setMinimumSize(1280, 820)
        self._apply_styles()

        self.title_label = QLabel("Эмоциональное отслеживание аудитории")
        self.title_label.setObjectName("pageTitle")

        self.top_status = QLabel("Готово к запуску")
        self.top_status.setObjectName("topStatus")
        self.top_meta = QLabel("FPS: 0.00 · Логи: -")
        self.top_meta.setObjectName("topMeta")

        self.video_label = QLabel("Видеопоток не запущен")
        self.video_label.setObjectName("videoSurface")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(860, 520)

        self.live_badge = QLabel("LIVE")
        self.live_badge.setObjectName("liveBadge")
        self.live_badge.hide()

        self.detected_caption = QLabel("Обнаруженное настроение")
        self.detected_caption.setObjectName("metaCaption")
        self.detected_emotion = QLabel("Ожидание сигнала")
        self.detected_emotion.setObjectName("emotionValue")
        self.detected_meta = QLabel(
            "Запустите мониторинг, чтобы получить первое определение эмоции."
        )
        self.detected_meta.setObjectName("metaText")
        self.detected_meta.setWordWrap(True)

        self.chart_title_label = QLabel("Аналитика эмоций в кадре")
        self.chart_title_label.setObjectName("sectionTitle")

        self.chart: QWidget | None = None
        self.chart_placeholder = QLabel(
            "Запустите мониторинг, чтобы увидеть аналитику эмоций."
        )
        self.chart_placeholder.setObjectName("emptyStateLabel")
        self.chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_placeholder.setWordWrap(True)
        self.summary_panel = SummaryPanel()
        self.user_search_panel = UserSearchPanel(self.user_database)

        self.current_mode_button = QPushButton("Текущий кадр")
        self.current_mode_button.setObjectName("modeButton")
        self.current_mode_button.setCheckable(True)
        self.current_mode_button.setChecked(True)
        self.current_mode_button.clicked.connect(lambda: self.set_mode("current"))

        self.session_mode_button = QPushButton("Сессия")
        self.session_mode_button.setObjectName("modeButton")
        self.session_mode_button.setCheckable(True)
        self.session_mode_button.clicked.connect(lambda: self.set_mode("session"))

        self.start_button = QPushButton("Начать мониторинг")
        self.start_button.setObjectName("primaryButton")
        self.stop_button = QPushButton("Остановить")
        self.stop_button.setObjectName("secondaryButton")
        self.stop_button.setEnabled(False)

        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)

        self._build_layout()
        self.statusBar().hide()
        self.showMaximized()

    def _reset_detected_emotion_state(self) -> None:
        self.detected_emotion.setText("Ожидание сигнала")
        self.detected_meta.setText(
            "Запустите мониторинг, чтобы получить определение эмоции."
        )

    def _update_chart_title(self) -> None:
        if self.current_mode == "current":
            title = (
                "Аналитика эмоций в текущем кадре"
                if self.monitoring_active
                else "Аналитика эмоций в кадре"
            )
        else:
            title = "Аналитика эмоций за сессию"
        self.chart_title_label.setText(title)

    def _ensure_chart(self) -> None:
        if self.chart is not None:
            return

        from ui.chart_widget import ChartWidget

        self.chart = ChartWidget()
        self.chart.hide()
        self.chart_body_layout.addWidget(self.chart)

    def _set_chart_placeholder_visible(self, visible: bool) -> None:
        self.chart_placeholder.setVisible(visible)
        if self.chart is not None:
            self.chart.setVisible(not visible)

    def _set_monitoring_active(self, active: bool) -> None:
        self.monitoring_active = active
        self._update_chart_title()
        if active:
            self._ensure_chart()
            self._set_chart_placeholder_visible(False)
            return

        self._reset_detected_emotion_state()
        self.top_meta.setText("FPS: 0.00 · Логи: -")
        if self.chart is None:
            self._set_chart_placeholder_visible(True)
        else:
            self._set_chart_placeholder_visible(False)

    def _build_layout(self) -> None:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(20, 16, 20, 16)
        page_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        status_layout = QVBoxLayout()
        status_layout.setSpacing(1)
        status_layout.addWidget(self.top_status, alignment=Qt.AlignmentFlag.AlignRight)
        status_layout.addWidget(self.top_meta, alignment=Qt.AlignmentFlag.AlignRight)
        header_layout.addLayout(status_layout)

        controls_card = _card("controlsCard")
        controls_layout = QHBoxLayout(controls_card)
        controls_layout.setContentsMargins(16, 12, 16, 12)
        controls_layout.setSpacing(12)

        mode_caption = QLabel("Режим аналитики")
        mode_caption.setObjectName("controlLabel")

        mode_switch = QWidget()
        mode_switch.setObjectName("modeSwitch")
        mode_switch_layout = QHBoxLayout(mode_switch)
        mode_switch_layout.setContentsMargins(4, 4, 4, 4)
        mode_switch_layout.setSpacing(4)
        mode_switch_layout.addWidget(self.current_mode_button)
        mode_switch_layout.addWidget(self.session_mode_button)

        controls_layout.addWidget(mode_caption)
        controls_layout.addWidget(mode_switch)
        controls_layout.addStretch()
        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.stop_button)

        video_card = _card("panelCard")
        video_layout = QVBoxLayout(video_card)
        video_layout.setContentsMargins(16, 16, 16, 16)
        video_layout.setSpacing(12)

        video_header = QHBoxLayout()
        video_title = QLabel("Видеопоток")
        video_title.setObjectName("sectionTitle")
        video_header.addWidget(video_title)
        video_header.addStretch()
        video_header.addWidget(self.live_badge)
        video_layout.addLayout(video_header)
        video_layout.addWidget(self.video_label, stretch=1)

        emotion_card = _card("emotionCard")
        emotion_layout = QVBoxLayout(emotion_card)
        emotion_layout.setContentsMargins(16, 14, 16, 14)
        emotion_layout.setSpacing(4)
        emotion_layout.addWidget(self.detected_caption)
        emotion_layout.addWidget(self.detected_emotion)
        emotion_layout.addWidget(self.detected_meta)
        video_layout.addWidget(emotion_card)

        chart_card = _card("panelCard")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(16, 16, 16, 16)
        chart_layout.setSpacing(10)
        chart_layout.addWidget(self.chart_title_label)
        self.chart_body = QWidget()
        self.chart_body_layout = QVBoxLayout(self.chart_body)
        self.chart_body_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_body_layout.addWidget(self.chart_placeholder)
        chart_layout.addWidget(self.chart_body)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(12)
        right_layout.addWidget(chart_card, stretch=3)
        right_layout.addWidget(self.summary_panel, stretch=3)
        right_layout.addWidget(self.user_search_panel, stretch=4)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)
        content_layout.addWidget(video_card, stretch=12)
        content_layout.addLayout(right_layout, stretch=8)

        page_layout.addLayout(header_layout)
        page_layout.addWidget(controls_card)
        page_layout.addLayout(content_layout, stretch=1)

        self.setCentralWidget(page)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background: #f4f7fb;
            }}
            QWidget {{
                color: #1d2d44;
                font-family: "Segoe UI";
                font-size: 14px;
            }}
            #pageTitle {{
                font-size: 26px;
                font-weight: 700;
                color: #19314d;
            }}
            #topStatus {{
                font-size: 15px;
                font-weight: 700;
                color: #1f3552;
            }}
            #topMeta {{
                font-size: 12px;
                color: #7a8b9e;
            }}
            #controlsCard, #panelCard, #emotionCard, #moodCard, #weatherCard, #summaryCard, #userDatabaseCard {{
                background: #ffffff;
                border: 1px solid #e4ebf3;
                border-radius: 22px;
            }}
            #sectionTitle {{
                font-size: 18px;
                font-weight: 650;
                color: #1f3552;
            }}
            #controlLabel, #metaCaption, #cardCaption {{
                font-size: 13px;
                color: #718399;
                font-weight: 600;
            }}
            #cardValue {{
                font-size: 18px;
                font-weight: 700;
                color: #1a2e49;
            }}
            #weatherLocation {{
                font-size: 18px;
                font-weight: 700;
                color: #1a2e49;
            }}
            #weatherDescriptionInline {{
                font-size: 16px;
                font-weight: 500;
                color: #7f8ea1;
            }}
            #weatherTemp {{
                font-size: 24px;
                font-weight: 700;
                color: #1a2e49;
            }}
            #cardMeta, #metaText {{
                font-size: 13px;
                color: #6f8094;
                line-height: 1.4;
            }}
            #emotionValue {{
                font-size: 18px;
                font-weight: 700;
                color: #1a2e49;
            }}
            #emptyStateLabel {{
                min-height: 250px;
                border-radius: 18px;
                background: #f7fafd;
                border: 1px dashed #d8e2ee;
                color: #73859a;
                font-size: 14px;
                font-weight: 500;
                padding: 18px;
            }}
            #videoSurface {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #eef3f9, stop:1 #dfe8f3);
                border: 1px solid #dde6f0;
                border-radius: 20px;
                color: #728398;
                font-size: 16px;
                font-weight: 500;
            }}
            #liveBadge {{
                background: {ALERT_RED};
                color: white;
                border-radius: 10px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 700;
            }}
            #modeSwitch {{
                background: #eef3f8;
                border: 1px solid #d8e2ee;
                border-radius: 14px;
            }}
            #modeButton {{
                min-height: 36px;
                min-width: 132px;
                padding: 0 14px;
                border: none;
                border-radius: 10px;
                background: transparent;
                color: #5e7188;
                font-size: 13px;
                font-weight: 600;
            }}
            #modeButton:checked {{
                background: #ffffff;
                color: #27425e;
            }}
            QPushButton {{
                min-height: 42px;
                padding: 0 16px;
                border-radius: 14px;
                font-size: 13px;
                font-weight: 600;
            }}
            #primaryButton {{
                background: {SOFT_BLUE};
                color: white;
                border: none;
            }}
            #primaryButton:hover {{
                background: {SOFT_BLUE_HOVER};
            }}
            #primaryButton:disabled {{
                background: #bfd0f7;
            }}
            #secondaryButton {{
                background: #eef3f8;
                color: #29425f;
                border: 1px solid #dbe5ef;
            }}
            #secondaryButton:hover {{
                background: #e5edf6;
            }}
            #secondaryButton:disabled {{
                color: #9dacbb;
                background: #f4f7fb;
            }}
            QTextEdit#summaryText {{
                background: transparent;
                border: none;
                border-radius: 0px;
                padding: 0px;
                color: #38506b;
            }}
            #searchInput, #filterCombo {{
                min-height: 38px;
                border-radius: 12px;
                border: 1px solid #d8e2ee;
                background: #f8fbff;
                padding: 0 12px;
                color: #1d2d44;
            }}
            #usersList, #detailsText {{
                background: #f8fbff;
                border: 1px solid #d8e2ee;
                border-radius: 16px;
                padding: 8px;
                color: #38506b;
            }}
            #usersList::item {{
                padding: 8px;
                border-radius: 12px;
                margin: 2px 0;
            }}
            #usersList::item:selected {{
                background: #e8f0ff;
                color: #16345a;
            }}
            """
        )

    def _clear_video_surface(self) -> None:
        self.video_label.clear()
        self.video_label.setText("Видеопоток не запущен")

    def _set_video_pixmap(self, source: QPixmap) -> None:
        target_size = self.video_label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            self.video_label.setPixmap(source)
            return

        scaled = source.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.FastTransformation,
        )

        x = max(0, (scaled.width() - target_size.width()) // 2)
        y = max(0, (scaled.height() - target_size.height()) // 2)
        cropped = scaled.copy(x, y, target_size.width(), target_size.height())
        self.video_label.setPixmap(cropped)

    def _connect_worker(self, worker: VideoWorker) -> None:
        worker.frame_ready.connect(self.update_ui)
        worker.error_occurred.connect(self.show_error)
        worker.status_changed.connect(self.on_status_changed)
        worker.session_finished.connect(self.on_session_finished)

    def set_mode(self, mode: str) -> None:
        self.current_mode = mode
        self.current_mode_button.setChecked(mode == "current")
        self.session_mode_button.setChecked(mode == "session")
        self._update_chart_title()
        self.summary_panel.update_summary("")

    def start_monitoring(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return

        from core.video_worker import VideoWorker

        self.worker = VideoWorker(self.settings, self.user_database)
        self._connect_worker(self.worker)
        self._set_monitoring_active(True)
        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.live_badge.show()
        self.top_status.setText("Запуск мониторинга")

    def stop_monitoring(self) -> None:
        if self.worker is None:
            return

        self.stop_button.setEnabled(False)
        self.top_status.setText("Остановка мониторинга")
        self.worker.stop()
        self.worker.wait(5000)
        self.start_button.setEnabled(True)
        self.live_badge.hide()
        self._clear_video_surface()
        self.worker = None
        self._set_monitoring_active(False)

    def on_status_changed(self, status: str) -> None:
        self.top_status.setText(status)

    def on_session_finished(self, summary_path: str) -> None:
        self.last_summary_path = summary_path
        self.user_search_panel.refresh_results()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.live_badge.hide()
        self.top_status.setText("Сессия завершена")
        self._clear_video_surface()
        self.worker = None
        self._set_monitoring_active(False)

    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Ошибка", message)

    def _update_detected_emotion(self, metrics: dict, mode_label: str, people_count: int) -> None:
        if not self.monitoring_active:
            self._reset_detected_emotion_state()
            return

        emotion = metrics.get("dominant_emotion", "unknown")
        distribution = metrics.get("distribution", {})
        unique_emotions = metrics.get("unique_emotions", [])

        if people_count <= 0 or not distribution:
            self.detected_emotion.setText("Нет данных")
            self.detected_meta.setText(f"{mode_label} · лица еще не определены")
            return

        translated = emotion_to_russian(emotion).capitalize()
        if people_count > 1:
            unique_labels = ", ".join(
                emotion_to_russian(item).capitalize() for item in unique_emotions
            ) or translated
            self.detected_emotion.setText(unique_labels)
            distribution_text = ", ".join(
                f"{emotion_to_russian(key).capitalize()}: {value:.1f}%"
                for key, value in distribution.items()
            )
            self.detected_meta.setText(
                f"{mode_label} · людей в кадре: {people_count} · доли эмоций в кадре: {distribution_text}"
            )
            return

        share = distribution.get(emotion, 0.0)
        self.detected_emotion.setText(translated)
        self.detected_meta.setText(
            f"{mode_label} · людей в кадре: {people_count} · доля эмоции в кадре: {share:.1f}%"
        )

    @staticmethod
    def _build_weather_mood_summary(group_mood: str | None, weather: dict | None) -> str:
        if not weather:
            return UNAVAILABLE_WEATHER_TEXT

        weather_text = str(weather.get("weather_text", "текущая погода")).lower().strip()
        if weather_text == "погода в данный момент недоступна":
            return UNAVAILABLE_WEATHER_TEXT

        mood = (group_mood or "неопределенное").lower()
        positive_moods = {"позитивное", "спокойное", "воодушевленное", "возбужденное"}
        negative_moods = {"подавленное", "напряженное", "тревожное", "негативное"}
        positive_weather_markers = {"ясно", "солнечно", "малооблачно", "переменная облачность"}
        negative_weather_markers = {"пасмурно", "дождь", "ливень", "снег", "гроза", "туман", "метель"}

        weather_positive = any(marker in weather_text for marker in positive_weather_markers)
        weather_negative = any(marker in weather_text for marker in negative_weather_markers)

        if mood in positive_moods and weather_positive:
            return (
                f"В группе наблюдается {mood} настроение, хорошая погода сочетается "
                f"с комфортным эмоциональным фоном аудитории."
            )
        if mood in positive_moods and weather_negative:
            return (
                f"В группе сохраняется {mood} настроение, погодный фон сейчас не "
                f"ухудшает общее состояние аудитории."
            )
        if mood in negative_moods and weather_positive:
            return (
                f"В группе заметно {mood} настроение, вероятно, на эмоциональный фон "
                f"сильнее влияют внутренние факторы, а не погодные условия."
            )
        if mood in negative_moods and weather_negative:
            return (
                f"В группе преобладает {mood} настроение, неблагоприятная погода может "
                f"дополнительно усиливать общий напряженный или утомленный фон аудитории."
            )
        return "Связь между настроением и погодными условиями требует накопления дополнительных наблюдений."

    def update_ui(self, frame, payload: dict) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        bytes_per_line = channels * width

        image = QImage(rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        self._set_video_pixmap(pixmap)

        frame_metrics = payload.get("current_metrics", {})
        frame_people_count = int(frame_metrics.get("people_count", 0))

        if self.current_mode == "current":
            metrics = frame_metrics
            mode_label = "Текущий кадр"
            people_count = frame_people_count
        else:
            metrics = payload.get("session_metrics", {})
            mode_label = "Сессия"
            people_count = int(metrics.get("unique_people_count", metrics.get("people_count", 0)))
        self._update_chart_title()

        self._ensure_chart()
        self._set_chart_placeholder_visible(False)
        if self.chart is not None:
            self.chart.update_chart(metrics.get("distribution", {}), "")
        self.summary_panel.update_overall_mood(
            group_mood=metrics.get("group_mood"),
            dominant_emotion=metrics.get("dominant_emotion"),
            people_count=people_count,
            mode_label=mode_label,
        )
        self._update_detected_emotion(frame_metrics, mode_label, frame_people_count)
        self.summary_panel.update_summary(
            self._build_weather_mood_summary(metrics.get("group_mood"), payload.get("weather"))
        )
        self.top_meta.setText(
            f"FPS: {float(payload.get('fps', 0.0)):.2f} · Логи: {payload.get('logs_dir', '-')}"
        )
        self.summary_panel.update_weather_text(payload.get("weather"))

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            if self.worker is not None and self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(5000)
        finally:
            super().closeEvent(event)
