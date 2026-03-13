from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget


class SummaryPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.status_label = QLabel("Статус: ожидание запуска")
        self.fps_label = QLabel("FPS: 0.0")
        self.logs_label = QLabel("Логи: -")
        self.weather_label = QLabel("Погода: -")

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.fps_label)
        layout.addWidget(self.logs_label)
        layout.addWidget(self.weather_label)
        layout.addWidget(self.summary_text)
        self.setLayout(layout)

    def update_status(self, text: str) -> None:
        self.status_label.setText(f"Статус: {text}")

    def update_fps(self, fps: float) -> None:
        self.fps_label.setText(f"FPS: {fps:.2f}")

    def update_logs_path(self, path: str) -> None:
        self.logs_label.setText(f"Логи: {path}")

    def update_weather_text(self, weather: dict | None) -> None:
        if not weather:
            self.weather_label.setText("Погода: нет данных")
            return

        location = weather.get("location_name", "-")
        temp = weather.get("temperature_c")
        description = weather.get("weather_text", "нет данных")
        temp_text = f", {temp}°C" if temp is not None else ""
        self.weather_label.setText(f"Погода: {location}{temp_text}, {description}")

    def update_summary(self, text: str) -> None:
        self.summary_text.setPlainText(text)
