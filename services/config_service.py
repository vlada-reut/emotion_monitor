from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "configs" / "settings.json"


@dataclass(slots=True)
class AppConfig:
    title: str = "Emotion Monitor"
    camera_source: int | str = 0
    camera_backend: str = "dshow"
    frame_width: int = 960
    frame_height: int = 540
    analysis_interval_frames: int = 12
    detector_confidence: float = 0.4
    detector_imgsz: int = 256
    tracker_max_distance: int = 70
    tracker_max_missing: int = 12


@dataclass(slots=True)
class ModelsConfig:
    face_detector_path: str = "weights/face_yolov8n.pt"


@dataclass(slots=True)
class WeatherConfig:
    enabled: bool = True
    latitude: float = 48.7080
    longitude: float = 44.5133
    location_name: str = "Volgograd"
    refresh_seconds: int = 120
    request_timeout: int = 10


@dataclass(slots=True)
class LoggingConfig:
    logs_dir: str = "logs"


@dataclass(slots=True)
class Settings:
    app: AppConfig
    models: ModelsConfig
    weather: WeatherConfig
    logging: LoggingConfig


def _merge_dict(defaults: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = defaults.copy()
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _default_settings_dict() -> dict[str, Any]:
    return {
        "app": asdict(AppConfig()),
        "models": asdict(ModelsConfig()),
        "weather": asdict(WeatherConfig()),
        "logging": asdict(LoggingConfig()),
    }


def load_settings(config_path: str | Path | None = None) -> Settings:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    raw = _default_settings_dict()
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            raw = _merge_dict(raw, json.load(file))

    return Settings(
        app=AppConfig(**raw["app"]),
        models=ModelsConfig(**raw["models"]),
        weather=WeatherConfig(**raw["weather"]),
        logging=LoggingConfig(**raw["logging"]),
    )


__all__ = [
    "Settings",
    "AppConfig",
    "ModelsConfig",
    "WeatherConfig",
    "LoggingConfig",
    "BASE_DIR",
    "DEFAULT_CONFIG_PATH",
    "load_settings",
]
