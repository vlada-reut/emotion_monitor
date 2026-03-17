from __future__ import annotations

from datetime import datetime

import requests

from core.models import WeatherSnapshot
from services.config_service import WeatherConfig


WEATHER_CODE_MAP = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "слабая морось",
    53: "морось",
    55: "сильная морось",
    61: "слабый дождь",
    63: "дождь",
    65: "сильный дождь",
    71: "слабый снег",
    73: "снег",
    75: "сильный снег",
    80: "ливень",
    81: "ливень",
    82: "сильный ливень",
    95: "гроза",
}


class WeatherService:
    _session = requests.Session()

    def __init__(self, config: WeatherConfig) -> None:
        self.config = config
        self._last_snapshot: WeatherSnapshot | None = None
        self._last_update_ts: float = 0.0

    def should_refresh(self, now_ts: float) -> bool:
        if not self.config.enabled:
            return False
        return (now_ts - self._last_update_ts) >= self.config.refresh_seconds

    def get_last_snapshot(self) -> WeatherSnapshot | None:
        return self._last_snapshot

    def fetch_weather(self) -> WeatherSnapshot | None:
        if not self.config.enabled:
            return None

        params = {
            "latitude": self.config.latitude,
            "longitude": self.config.longitude,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
            "timezone": "auto",
        }

        response = self._session.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        payload = response.json()

        current = payload.get("current", {})
        weather_code = current.get("weather_code")
        weather_text = WEATHER_CODE_MAP.get(weather_code, "нет данных")

        snapshot = WeatherSnapshot(
            location_name=self.config.location_name,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            temperature_c=current.get("temperature_2m"),
            apparent_temperature_c=current.get("apparent_temperature"),
            humidity=current.get("relative_humidity_2m"),
            wind_speed_kmh=current.get("wind_speed_10m"),
            weather_code=weather_code,
            weather_text=weather_text,
        )

        self._last_snapshot = snapshot
        self._last_update_ts = datetime.now().timestamp()
        return snapshot
