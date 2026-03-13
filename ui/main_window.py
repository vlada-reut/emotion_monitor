from __future__ import annotations

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.video_worker import VideoWorker
from services.config_service import Settings
from ui.chart_widget import ChartWidget
from ui.summary_panel import SummaryPanel


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.worker: VideoWorker | None = None
        self.last_summary_path: str = ""

        self.setWindowTitle(settings.app.title)
        self.resize(1400, 900)

        self.video_label = QLabel("Видеопоток не запущен")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(800, 450)
        self.video_label.setStyleSheet("background-color: #111; color: #DDD; border: 1px solid #333;")

        self.chart = ChartWidget()
        self.summary_panel = SummaryPanel()

        self.mode = QComboBox()
        self.mode.addItems(["Current", "Session"])

        self.start_button = QPushButton("Начать мониторинг")
        self.stop_button = QPushButton("Остановить")
        self.stop_button.setEnabled(False)

        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.mode.currentTextChanged.connect(self.refresh_mode_dependent_widgets)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Режим аналитики:"))
        controls_layout.addWidget(self.mode)
        controls_layout.addStretch()
        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.stop_button)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.chart, stretch=2)
        right_layout.addWidget(self.summary_panel, stretch=3)

        content_layout = QHBoxLayout()
        content_layout.addWidget(self.video_label, stretch=3)
        content_layout.addLayout(right_layout, stretch=2)

        root_layout = QVBoxLayout()
        root_layout.addLayout(controls_layout)
        root_layout.addLayout(content_layout)

        container = QWidget()
        container.setLayout(root_layout)
        self.setCentralWidget(container)
        self.statusBar().showMessage("Готово к запуску")

    def _connect_worker(self, worker: VideoWorker) -> None:
        worker.frame_ready.connect(self.update_ui)
        worker.error_occurred.connect(self.show_error)
        worker.status_changed.connect(self.on_status_changed)
        worker.session_finished.connect(self.on_session_finished)

    def start_monitoring(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return

        self.worker = VideoWorker(self.settings)
        self._connect_worker(self.worker)
        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.summary_panel.update_status("запуск")
        self.statusBar().showMessage("Мониторинг запускается...")

    def stop_monitoring(self) -> None:
        if self.worker is None:
            return

        self.stop_button.setEnabled(False)
        self.summary_panel.update_status("остановка")
        self.statusBar().showMessage("Остановка мониторинга...")
        self.worker.stop()
        self.worker.wait(5000)
        self.start_button.setEnabled(True)

    def on_status_changed(self, status: str) -> None:
        self.summary_panel.update_status(status)
        self.statusBar().showMessage(status)

    def on_session_finished(self, summary_path: str) -> None:
        self.last_summary_path = summary_path
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.statusBar().showMessage(f"Сессия завершена. Отчет: {summary_path}")

    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Ошибка", message)

    def refresh_mode_dependent_widgets(self) -> None:
        self.summary_panel.update_summary(self.summary_panel.summary_text.toPlainText())

    def update_ui(self, frame, payload: dict) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        bytes_per_line = channels * width

        image = QImage(rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(pixmap)

        mode = self.mode.currentText()
        if mode == "Current":
            metrics = payload.get("current_metrics", {})
            summary = payload.get("current_summary", "")
            chart_title = "Распределение эмоций в текущем кадре"
        else:
            metrics = payload.get("session_metrics", {})
            summary = payload.get("session_summary", "")
            chart_title = "Распределение эмоций за сессию"

        self.chart.update_chart(metrics.get("distribution", {}), chart_title)
        self.summary_panel.update_summary(summary)
        self.summary_panel.update_fps(float(payload.get("fps", 0.0)))
        self.summary_panel.update_logs_path(payload.get("logs_dir", "-"))
        self.summary_panel.update_weather_text(payload.get("weather"))

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            if self.worker is not None and self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(5000)
        finally:
            super().closeEvent(event)
