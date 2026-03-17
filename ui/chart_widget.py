from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from analytics.stats import emotion_to_russian


EMOTION_COLORS = {
    "happy": "#24c78f",
    "neutral": "#5f88e8",
    "sad": "#f4b942",
    "surprise": "#ff9b5d",
    "angry": "#ff7a66",
    "fear": "#ea5b6f",
    "disgust": "#8a6cf2",
    "unknown": "#9aa6b2",
}


class ChartWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        self.figure = Figure(figsize=(4, 4), facecolor="#ffffff")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setStyleSheet("background: transparent; border: none;")
        self._last_signature: tuple | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setMinimumHeight(250)

    def update_chart(self, data: dict[str, float], title: str = "") -> None:
        signature = (tuple(data.items()), title)
        if signature == self._last_signature:
            return
        self._last_signature = signature

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#ffffff")

        if data:
            labels = [emotion_to_russian(key).capitalize() for key in data.keys()]
            values = list(data.values())
            colors = [EMOTION_COLORS.get(key, "#9aa6b2") for key in data.keys()]
            wedges, _, autotexts = ax.pie(
                values,
                colors=colors,
                startangle=90,
                counterclock=False,
                wedgeprops={"width": 0.92, "edgecolor": "#ffffff", "linewidth": 1.2},
                autopct=lambda pct: f"{pct:.0f}%" if pct >= 6 else "",
                textprops={"color": "#425466", "fontsize": 10},
            )

            for autotext in autotexts:
                autotext.set_color("#ffffff")
                autotext.set_fontsize(10)
                autotext.set_weight("bold")

            ax.legend(
                wedges,
                labels,
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=False,
                fontsize=10,
                labelcolor="#425466",
            )
        else:
            ax.text(
                0.5,
                0.5,
                "Нет данных",
                ha="center",
                va="center",
                fontsize=12,
                color="#7a8797",
                transform=ax.transAxes,
            )

        ax.set_aspect("equal")
        self.figure.subplots_adjust(left=0.04, right=0.84, top=0.86, bottom=0.10)
        self.canvas.draw_idle()
