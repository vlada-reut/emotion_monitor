from __future__ import annotations

import cv2


BACKEND_MAP = {
    "dshow": cv2.CAP_DSHOW,
    "msmf": cv2.CAP_MSMF,
    "ffmpeg": cv2.CAP_FFMPEG,
    "any": cv2.CAP_ANY,
}


class VideoCapture:
    def __init__(self, source: int | str = 0, backend: str = "dshow") -> None:
        self.source = source
        self.backend = BACKEND_MAP.get(backend.lower(), cv2.CAP_ANY)
        self.cap: cv2.VideoCapture | None = None

    def open(self, width: int | None = None, height: int | None = None) -> None:
        if isinstance(self.source, str) and self.source.isdigit():
            source = int(self.source)
        else:
            source = self.source

        if isinstance(source, int):
            self.cap = cv2.VideoCapture(source, self.backend)
        else:
            self.cap = cv2.VideoCapture(source)

        if width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if not self.cap.isOpened():
            raise RuntimeError("Не удалось открыть источник видеопотока")

    def read(self):
        if self.cap is None:
            raise RuntimeError("Источник видеопотока не инициализирован")
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
