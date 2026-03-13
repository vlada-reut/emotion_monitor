from PySide6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class ChartWidget(QWidget):

    def __init__(self):

        super().__init__()

        self.figure = Figure()

        self.canvas = FigureCanvasQTAgg(self.figure)

        layout = QVBoxLayout()

        layout.addWidget(self.canvas)

        self.setLayout(layout)

    def update_chart(self, data):

        self.figure.clear()

        ax = self.figure.add_subplot(111)

        if data:

            labels = list(data.keys())
            values = list(data.values())

            ax.pie(values, labels=labels, autopct="%1.1f%%")

        ax.set_title("Emotion Distribution")

        self.canvas.draw()