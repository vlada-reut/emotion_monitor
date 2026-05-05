from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout, QWidget


def _build_card(object_name: str) -> QFrame:
    card = QFrame()
    card.setObjectName(object_name)
    card.setFrameShape(QFrame.Shape.NoFrame)
    return card


class SummaryPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.mood_title = QLabel("Общее настроение аудитории")
        self.mood_value = QLabel("Ожидание запуска")
        self.mood_meta = QLabel("Анализируемых людей: 0")

        self.weather_title = QLabel("Погода")
        self.weather_location = QLabel("Нет данных")
        self.weather_location.setObjectName("weatherLocation")
        self.weather_description_inline = QLabel("")
        self.weather_description_inline.setObjectName("weatherDescriptionInline")
        self.weather_temperature = QLabel("—")

        self.summary_title = QLabel("Анализ взаимосвязи")
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.summary_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.summary_text.setObjectName("summaryText")
        self.summary_text.setPlainText("")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self._create_info_card("moodCard", self.mood_title, self.mood_value, self.mood_meta))
        layout.addWidget(self._create_weather_card())
        layout.addWidget(self._create_summary_card())

    def _create_info_card(self, name: str, title: QLabel, value: QLabel, meta: QLabel) -> QFrame:
        card = _build_card(name)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(4)

        title.setObjectName("cardCaption")
        value.setObjectName("cardValue")
        value.setWordWrap(True)
        value.setMinimumHeight(32)
        meta.setObjectName("cardMeta")
        meta.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(value)
        card_layout.addWidget(meta)
        return card

    def _create_weather_card(self) -> QFrame:
        card = _build_card("weatherCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(6)

        self.weather_title.setObjectName("cardCaption")
        self.weather_temperature.setObjectName("weatherTemp")

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        left_row = QHBoxLayout()
        left_row.setContentsMargins(0, 0, 0, 0)
        left_row.setSpacing(8)
        left_row.addWidget(self.weather_location)
        left_row.addWidget(self.weather_description_inline)
        left_row.addStretch()

        top_row.addLayout(left_row)
        top_row.addStretch()
        top_row.addWidget(self.weather_temperature, alignment=Qt.AlignmentFlag.AlignVCenter)

        card_layout.addWidget(self.weather_title)
        card_layout.addLayout(top_row)
        return card

    def _create_summary_card(self) -> QFrame:
        card = _build_card("summaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)

        self.summary_title.setObjectName("cardCaption")
        self.summary_text.setMinimumHeight(72)
        self.summary_text.setMaximumHeight(72)

        card_layout.addWidget(self.summary_title)
        card_layout.addWidget(self.summary_text)
        return card

    def update_status(self, text: str) -> None:
        del text
        return

    def update_fps(self, fps: float) -> None:
        del fps
        return

    def update_logs_path(self, path: str) -> None:
        del path
        return

    def update_weather_text(self, weather: dict | None) -> None:
        if not weather:
            self.weather_location.setText("Погода")
            self.weather_description_inline.setText("в данный момент недоступна")
            self.weather_temperature.setText("—")
            return

        location = weather.get("location_name", "Локация не задана")
        description = str(weather.get("weather_text", "")).capitalize()
        temp = weather.get("temperature_c")

        self.weather_location.setText(location)
        self.weather_description_inline.setText(description)
        self.weather_temperature.setText(f"{temp:.1f}°C" if isinstance(temp, (int, float)) else "—")

    def update_overall_mood(
        self,
        group_mood: str | None,
        dominant_emotion: str | None,
        people_count: int,
        is_session_mode: bool,
    ) -> None:
        del dominant_emotion
        mood = (group_mood or "неопределенное").capitalize()
        self.mood_value.setText(mood)
        if is_session_mode:
            self.mood_meta.setText(f"Учтено в статистике: {people_count}")
            return
        self.mood_meta.setText(f"Анализируемых людей: {people_count}")

    def update_summary(self, text: str) -> None:
        self.summary_text.setPlainText(text)

    def reset(self) -> None:
        self.mood_value.setText("Ожидание запуска")
        self.mood_meta.setText("Анализируемых людей: 0")
        self.weather_location.setText("Погода")
        self.weather_description_inline.setText("в данный момент недоступна")
        self.weather_temperature.setText("—")
        self.summary_text.setPlainText("")
