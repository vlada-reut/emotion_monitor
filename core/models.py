from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AnalysisResult:
    emotion: str = "unknown"
    gender: str = "unknown"
    age: int | None = None
    age_group: str = "unknown"
    confidence: float | None = None


@dataclass(slots=True)
class TrackDetection:
    track_id: int
    bbox: tuple[int, int, int, int]
    center: tuple[int, int]
    missed_frames: int = 0


@dataclass(slots=True)
class FaceObservation:
    person_id: int
    timestamp: str
    bbox: tuple[int, int, int, int]
    emotion: str
    gender: str
    age_group: str
    age: int | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "person_id": self.person_id,
            "timestamp": self.timestamp,
            "bbox": list(self.bbox),
            "emotion": self.emotion,
            "gender": self.gender,
            "age_group": self.age_group,
            "age": self.age,
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class WeatherSnapshot:
    location_name: str
    timestamp: str
    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    humidity: int | None = None
    wind_speed_kmh: float | None = None
    weather_code: int | None = None
    weather_text: str = "нет данных"

    def to_dict(self) -> dict[str, Any]:
        return {
            "location_name": self.location_name,
            "timestamp": self.timestamp,
            "temperature_c": self.temperature_c,
            "apparent_temperature_c": self.apparent_temperature_c,
            "humidity": self.humidity,
            "wind_speed_kmh": self.wind_speed_kmh,
            "weather_code": self.weather_code,
            "weather_text": self.weather_text,
        }


@dataclass(slots=True)
class SessionState:
    session_id: str
    started_at: str
    history: list[FaceObservation] = field(default_factory=list)
    active_faces: dict[int, FaceObservation] = field(default_factory=dict)
    unique_face_ids: set[int] = field(default_factory=set)
    last_results: dict[int, AnalysisResult] = field(default_factory=dict)
    last_analysis_frame: dict[int, int] = field(default_factory=dict)
    frames_processed: int = 0
    fps: float = 0.0
    last_weather: WeatherSnapshot | None = None

    @classmethod
    def create(cls) -> "SessionState":
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        return cls(session_id=now, started_at=datetime.now().isoformat(timespec="seconds"))
