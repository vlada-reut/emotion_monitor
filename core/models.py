from __future__ import annotations

from collections import Counter
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
    user_id: int | None
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
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "bbox": list(self.bbox),
            "emotion": self.emotion,
            "gender": self.gender,
            "age_group": self.age_group,
            "age": self.age,
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class SessionPerson:
    person_id: int
    user_id: int | None
    display_name: str | None
    first_seen: str
    last_seen: str
    track_ids: set[int] = field(default_factory=set)
    observations_count: int = 0
    emotion_counter: Counter[str] = field(default_factory=Counter)
    gender_counter: Counter[str] = field(default_factory=Counter)
    age_group_counter: Counter[str] = field(default_factory=Counter)
    last_observation: FaceObservation | None = None
    embedding: list[float] | None = None
    embeddings: list[list[float]] = field(default_factory=list)

    def register_observation(
        self,
        observation: FaceObservation,
        track_id: int,
        embedding: list[float] | None = None,
    ) -> None:
        self.last_seen = observation.timestamp
        self.last_observation = observation
        self.track_ids.add(track_id)
        self.observations_count += 1

        if observation.emotion:
            self.emotion_counter[observation.emotion] += 1
        if observation.gender:
            self.gender_counter[observation.gender] += 1
        if observation.age_group:
            self.age_group_counter[observation.age_group] += 1
        if embedding is not None:
            normalized_embedding = [float(value) for value in embedding]
            self.embedding = normalized_embedding
            self.embeddings.append(normalized_embedding)
            if len(self.embeddings) > 6:
                self.embeddings.pop(0)

    def dominant_emotion(self) -> str:
        if not self.emotion_counter:
            return "unknown"
        return self.emotion_counter.most_common(1)[0][0]

    def dominant_gender(self) -> str:
        if not self.gender_counter:
            return "unknown"
        return self.gender_counter.most_common(1)[0][0]

    def dominant_age_group(self) -> str:
        if not self.age_group_counter:
            return "unknown"
        return self.age_group_counter.most_common(1)[0][0]


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
    people: dict[int, SessionPerson] = field(default_factory=dict)
    active_track_to_person: dict[int, int] = field(default_factory=dict)
    last_results: dict[int, AnalysisResult] = field(default_factory=dict)
    last_analysis_frame: dict[int, int] = field(default_factory=dict)
    frames_processed: int = 0
    fps: float = 0.0
    last_weather: WeatherSnapshot | None = None

    @classmethod
    def create(cls) -> "SessionState":
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        return cls(session_id=now, started_at=datetime.now().isoformat(timespec="seconds"))
