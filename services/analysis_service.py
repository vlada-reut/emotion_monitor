from __future__ import annotations

import logging
from typing import Any

from core.models import AnalysisResult


logger = logging.getLogger(__name__)


class FaceAnalysisService:
    _shared_deepface = None
    _shared_import_error: Exception | None = None
    _shared_import_attempted = False

    def __init__(self) -> None:
        self._deepface = self.__class__._shared_deepface
        self._import_error = self.__class__._shared_import_error
        self._import_attempted = self.__class__._shared_import_attempted

    @property
    def available(self) -> bool:
        return self._load_deepface() is not None

    def _load_deepface(self):
        if self.__class__._shared_import_attempted:
            self._deepface = self.__class__._shared_deepface
            self._import_error = self.__class__._shared_import_error
            self._import_attempted = True
            return self._deepface

        self.__class__._shared_import_attempted = True
        self._import_attempted = True
        try:
            from deepface import DeepFace  # type: ignore
        except Exception as error:  # pragma: no cover
            self._import_error = error
            self.__class__._shared_import_error = error
            logger.warning(
                "DeepFace не удалось импортировать: %s. Анализ эмоций, пола, возраста и re-id будут недоступны.",
                error,
            )
            self._deepface = None
        else:
            self._deepface = DeepFace
            self.__class__._shared_deepface = DeepFace

        return self._deepface

    @staticmethod
    def _to_age_group(age: int | None) -> str:
        if age is None:
            return "unknown"
        if age < 13:
            return "child"
        if age < 18:
            return "teen"
        if age < 30:
            return "young_adult"
        if age < 60:
            return "adult"
        return "senior"

    @staticmethod
    def _extract_confidence(raw: Any) -> float | None:
        emotion_scores = raw.get("emotion", {})
        if isinstance(emotion_scores, dict) and emotion_scores:
            numeric_scores = [float(value) for value in emotion_scores.values() if isinstance(value, (int, float))]
            if numeric_scores:
                return round(max(numeric_scores), 2)
        return None

    def analyze_full(self, face) -> AnalysisResult:
        if face is None or getattr(face, "size", 0) == 0:
            return AnalysisResult()

        deepface = self._load_deepface()
        if deepface is None:
            return AnalysisResult()

        try:
            raw: Any = deepface.analyze(
                img_path=face,
                actions=["emotion", "gender", "age"],
                enforce_detection=False,
                detector_backend="skip",
                silent=True,
            )
            if isinstance(raw, list):
                raw = raw[0]

            emotion = str(raw.get("dominant_emotion", "unknown")).lower()
            gender = str(raw.get("dominant_gender", "unknown"))
            age_value = raw.get("age")
            age = int(age_value) if age_value is not None else None

            return AnalysisResult(
                emotion=emotion,
                gender=gender,
                age=age,
                age_group=self._to_age_group(age),
                confidence=self._extract_confidence(raw),
            )
        except Exception as error:  # pragma: no cover
            logger.exception("Ошибка полного анализа лица: %s", error)
            return AnalysisResult()

    def analyze_emotion(self, face, base_result: AnalysisResult | None = None) -> AnalysisResult:
        if face is None or getattr(face, "size", 0) == 0:
            return base_result or AnalysisResult()

        deepface = self._load_deepface()
        if deepface is None:
            return base_result or AnalysisResult()

        base = base_result or AnalysisResult()

        try:
            raw: Any = deepface.analyze(
                img_path=face,
                actions=["emotion"],
                enforce_detection=False,
                detector_backend="skip",
                silent=True,
            )
            if isinstance(raw, list):
                raw = raw[0]

            return AnalysisResult(
                emotion=str(raw.get("dominant_emotion", base.emotion)).lower(),
                gender=base.gender,
                age=base.age,
                age_group=base.age_group,
                confidence=self._extract_confidence(raw),
            )
        except Exception as error:  # pragma: no cover
            logger.exception("Ошибка анализа эмоции: %s", error)
            return base

    def extract_embedding(self, face) -> list[float] | None:
        if face is None or getattr(face, "size", 0) == 0:
            return None

        deepface = self._load_deepface()
        if deepface is None:
            return None

        try:
            raw: Any = deepface.represent(
                img_path=face,
                model_name="Facenet512",
                detector_backend="skip",
                enforce_detection=False,
                normalization="base",
            )
            if isinstance(raw, list):
                raw = raw[0]
            embedding = raw.get("embedding")
            if not embedding:
                return None
            return [float(value) for value in embedding]
        except Exception as error:  # pragma: no cover
            logger.exception("Ошибка извлечения face embedding: %s", error)
            return None
