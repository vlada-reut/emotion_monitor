from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from analytics.stats import emotion_to_russian


class ChartWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.figure = Figure(figsize=(4, 4))
        self.canvas = FigureCanvasQTAgg(self.figure)

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def update_chart(self, data: dict[str, float], title: str) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if data:
            labels = [emotion_to_russian(key) for key in data.keys()]
            values = list(data.values())
            ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        else:
            ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")

        ax.set_title(title)
        self.canvas.draw()
