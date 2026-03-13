import cv2

from PySide6.QtWidgets import (
    QMainWindow,
    QLabel,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QComboBox
)

from PySide6.QtGui import QImage, QPixmap

from core.video_worker import VideoWorker
from analytics.stats import calculate_distribution
from ui.chart_widget import ChartWidget


class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Emotion Monitor")

        self.video_label = QLabel()

        self.chart = ChartWidget()

        self.mode = QComboBox()
        self.mode.addItems(["Current","Session"])

        self.start_button = QPushButton("Start")

        layout = QVBoxLayout()

        layout.addWidget(self.video_label)
        layout.addWidget(self.chart)
        layout.addWidget(self.mode)
        layout.addWidget(self.start_button)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

        self.worker = VideoWorker()

        self.start_button.clicked.connect(self.start)

        self.worker.frame_ready.connect(self.update_ui)

    def start(self):

        self.worker.start()

    def update_ui(self, frame, active_faces, session_faces):

        rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

        h,w,ch = rgb.shape
        bytes_per_line = ch*w

        img = QImage(rgb.data,w,h,bytes_per_line,QImage.Format_RGB888)

        self.video_label.setPixmap(QPixmap.fromImage(img))

        if self.mode.currentText() == "Current":

            stats = calculate_distribution(active_faces.values())

        else:

            stats = calculate_distribution(session_faces.values())

        self.chart.update_chart(stats)