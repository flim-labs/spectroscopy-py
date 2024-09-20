import flim_labs
from PyQt6.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, QObject
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog
from components.gui_styles import GUIStyles
from settings import *


class WorkerSignals(QObject):
    finished = pyqtSignal(float) 
    error = pyqtSignal(str)      


class FrequencyWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()

    def run(self):
        try:
            res = flim_labs.detect_laser_frequency()
            if res is None or res == 0.0:
                self.signals.finished.emit(0.0)
            else:
                self.signals.finished.emit(res)
        except Exception as e:
            self.signals.error.emit(str(e))


class SyncInDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sync In Measure Frequency")
        self.setFixedSize(300, 200)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.label = QLabel("Do you want to start to measure frequency?")
        self.layout.addWidget(self.label)
        self.label.setWordWrap(True)

        self.button_layout = QHBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.no_button = QPushButton("No")
        self.no_button.clicked.connect(self.on_no_button_click)
        self.button_layout.addWidget(self.no_button)

        self.yes_button = QPushButton("Do it")
        self.yes_button.clicked.connect(self.on_yes_button_click)
        self.button_layout.addWidget(self.yes_button)

        self.frequency_mhz = 0.0
        GUIStyles.customize_theme(self)
        GUIStyles.set_fonts()
 
        self.threadpool = QThreadPool()

    def on_yes_button_click(self):
        self.label.setText("Measuring frequency... The process can take a few seconds. Please wait. After 60 seconds, the process "
            "will be interrupted automatically.")
        self.yes_button.setEnabled(False)
        self.no_button.setEnabled(False)

        worker = FrequencyWorker()
        worker.signals.finished.connect(self.on_measurement_complete)
        worker.signals.error.connect(self.on_measurement_error)
        self.threadpool.start(worker)

    def on_measurement_complete(self, frequency_mhz):
        self.frequency_mhz = round(frequency_mhz, 3)
        if self.frequency_mhz == 0.0:
            self.label.setText("Frequency not detected. Please check the connection and try again.")
            self.yes_button.setEnabled(True)
            self.yes_button.setText("Retry")
        else:
            self.label.setText(f"Frequency detected: {self.frequency_mhz} MHz")
            self.yes_button.setEnabled(False)
        self.no_button.setEnabled(True)
        self.no_button.setText("Done")

    def on_measurement_error(self, error_msg):
        self.label.setText(f"Error: {error_msg}")
        self.yes_button.setEnabled(True)
        self.yes_button.setText("Retry again")
        self.no_button.setEnabled(True)
        self.no_button.setText("Cancel")

    def on_no_button_click(self):
        self.close()


    def closeEvent(self, event):
        flim_labs.request_stop()
        super().closeEvent(event)