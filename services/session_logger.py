from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import FaceObservation, WeatherSnapshot
from services.config_service import BASE_DIR


class SessionLogger:
    _FLUSH_EVERY = 20

    def __init__(self, logs_dir: str, session_id: str) -> None:
        self.logs_dir = (BASE_DIR / logs_dir).resolve()
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = session_id
        self.events_log_path = self.logs_dir / "app.log"
        self.observations_path = self.logs_dir / f"session_{session_id}.jsonl"
        self.summary_path = self.logs_dir / f"session_summary_{session_id}.json"
        self._observations_file = self.observations_path.open("a", encoding="utf-8")
        self._pending_flush_count = 0

        self._setup_app_logger()
        self.app_logger = logging.getLogger("emotion_monitor")

    def _setup_app_logger(self) -> None:
        logger = logging.getLogger("emotion_monitor")
        logger.setLevel(logging.INFO)

        if not any(
            isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == self.events_log_path
            for handler in logger.handlers
        ):
            handler = logging.FileHandler(self.events_log_path, encoding="utf-8")
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            logger.addHandler(handler)

    def log_event(self, message: str, level: int = logging.INFO) -> None:
        self.app_logger.log(level, message)

    def log_observation(
        self,
        observation: FaceObservation,
        weather: WeatherSnapshot | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload = observation.to_dict()
        if weather is not None:
            payload["weather"] = weather.to_dict()
        if extra:
            payload.update(extra)

        self._observations_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._pending_flush_count += 1
        if self._pending_flush_count >= self._FLUSH_EVERY:
            self._observations_file.flush()
            self._pending_flush_count = 0

    def write_summary(self, summary: dict[str, Any]) -> Path:
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            **summary,
        }
        with self.summary_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return self.summary_path

    def close(self) -> None:
        if not self._observations_file.closed:
            self._observations_file.flush()
            self._observations_file.close()
