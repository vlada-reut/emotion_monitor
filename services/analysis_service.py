from __future__ import annotations

import logging
from typing import Any

from core.models import AnalysisResult

try:
    from deepface import DeepFace
except Exception:  # pragma: no cover - зависит от среды выполнения
    DeepFace = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


class FaceAnalysisService:
    def __init__(self) -> None:
        self.available = DeepFace is not None
        if not self.available:
            logger.warning(
                "Библиотека DeepFace недоступна. Анализ эмоций, пола и возраста будет возвращать 'unknown'."
            )

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

    def analyze(self, face) -> AnalysisResult:
        if face is None or getattr(face, "size", 0) == 0:
            return AnalysisResult()

        if not self.available:
            return AnalysisResult()

        try:
            raw: Any = DeepFace.analyze(
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
            confidence = None

            emotion_scores = raw.get("emotion", {})
            if isinstance(emotion_scores, dict) and emotion_scores:
                numeric_scores = [
                    float(value) for value in emotion_scores.values() if isinstance(value, (int, float))
                ]
                if numeric_scores:
                    confidence = round(max(numeric_scores), 2)

            return AnalysisResult(
                emotion=emotion,
                gender=gender,
                age=age,
                age_group=self._to_age_group(age),
                confidence=confidence,
            )
        except Exception as error:  # pragma: no cover - зависит от модели и среды
            logger.exception("Ошибка анализа лица: %s", error)
            return AnalysisResult()
