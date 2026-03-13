from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO

from services.config_service import BASE_DIR


class FaceDetector:
    def __init__(self, model_path: str, confidence: float = 0.4, imgsz: int = 320) -> None:
        resolved_path = self._resolve_model_path(model_path)
        self.model = YOLO(str(resolved_path))
        self.confidence = confidence
        self.imgsz = imgsz

    @staticmethod
    def _resolve_model_path(model_path: str) -> Path:
        candidates = [
            Path(model_path),
            BASE_DIR / model_path,
            BASE_DIR / "weights" / model_path,
            BASE_DIR / Path(model_path).name,
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        raise FileNotFoundError(
            f"Не найден файл модели детекции лиц: {model_path}. "
            f"Ожидался путь вроде '{BASE_DIR / 'weights' / 'face_yolov8n.pt'}'."
        )

    def detect(self, frame) -> list[tuple[int, int, int, int]]:
        results = self.model(frame, conf=self.confidence, imgsz=self.imgsz, verbose=False)
        boxes: list[tuple[int, int, int, int]] = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes.xyxy:
                x1, y1, x2, y2 = map(int, box.tolist())
                boxes.append((x1, y1, x2, y2))

        return boxes
