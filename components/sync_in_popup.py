import flim_labs
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog
from PyQt6.QtGui import  QIcon, QPixmap, QTransform
from components.gui_styles import GUIStyles
from components.resource_path import resource_path
from settings import *

class FrequencyWorker(QThread):
    finished = pyqtSignal(float)
    error = pyqtSignal(str)

    def run(self):
        try:
            res = flim_labs.detect_laser_frequency()
            if res is None or res == 0.0:
                self.finished.emit(0.0)
            else:
                self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))

class SyncInDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sync In Measure Frequency")
        self.setWindowIcon(QIcon(resource_path("assets/wave-icon.png")))
        self.setMinimumSize(300, 250)  
        self.setMaximumSize(400, 350)  
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
 
        # Loader
        self.loader_label = QLabel(self)
        self.loader_pixmap = QPixmap(resource_path("assets/wave-icon.png"))
        self.loader_pixmap = self.loader_pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio) 
        self.loader_label.setPixmap(self.loader_pixmap)
        self.loader_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.loader_label.setVisible(False)  
        
        # Success/Error Icon
        self.success_icon_layout = QHBoxLayout()
        self.success_icon_layout.setContentsMargins(0,0,0,0)
        self.success_icon_layout.setSpacing(0)
        self.success_icon = QLabel()
        self.success_icon_pixmap = QPixmap(resource_path("assets/success-lens.png"))
        self.success_icon_pixmap = self.success_icon_pixmap.scaled(45, 45, Qt.AspectRatioMode.KeepAspectRatio) 
        self.success_icon.setPixmap(self.success_icon_pixmap)
        self.success_icon.setVisible(False)
        self.success_icon_layout.addWidget(self.success_icon, alignment=Qt.AlignmentFlag.AlignHCenter)        
        
        self.error_icon_layout = QHBoxLayout()
        self.error_icon_layout.setContentsMargins(0,0,0,0)
        self.error_icon_layout.setSpacing(0)
        self.error_icon = QLabel()
        self.error_icon_pixmap = QPixmap(resource_path("assets/error-lens.png"))
        self.error_icon_pixmap = self.error_icon_pixmap.scaled(45, 45, Qt.AspectRatioMode.KeepAspectRatio) 
        self.error_icon.setPixmap(self.error_icon_pixmap)
        self.error_icon.setVisible(False)
        self.error_icon_layout.addWidget(self.error_icon, alignment=Qt.AlignmentFlag.AlignHCenter) 

        # Label
        label_container = QHBoxLayout()
        self.label = QLabel("Do you want to start to measure frequency?")
        self.label.setStyleSheet("font-family: Montserrat; font-size: 14px;")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        label_container.addWidget(self.label)


        self.layout.addWidget(self.loader_label)
        self.layout.addLayout(self.success_icon_layout)
        self.layout.addLayout(self.error_icon_layout)
        self.layout.addLayout(label_container)
        self.layout.addSpacing(20)

        # Buttons
        self.button_layout = QHBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.no_button = QPushButton("NO")
        self.no_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.no_button.setObjectName("btn")
        GUIStyles.set_stop_btn_style(self.no_button)
        self.no_button.clicked.connect(self.on_no_button_click)
        self.button_layout.addWidget(self.no_button)

        self.yes_button = QPushButton("DO IT")
        self.yes_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.yes_button.setObjectName("btn")
        GUIStyles.set_start_btn_style(self.yes_button)
        self.yes_button.clicked.connect(self.on_yes_button_click)
        self.button_layout.addWidget(self.yes_button)

        self.frequency_mhz = 0.0
        GUIStyles.customize_theme(self)
        GUIStyles.set_fonts()

        self.worker = None
        self.flip_timer = QTimer(self)
        self.flip_timer.timeout.connect(self.flip_loader)

        self.flipped = False  

    def flip_loader(self):
        transform = QTransform()
        if self.flipped:
            transform.scale(1, 1) 
        else:
            transform.scale(-1, 1)  

        self.loader_label.setPixmap(self.loader_pixmap.transformed(transform, mode=Qt.TransformationMode.SmoothTransformation))
        self.flipped = not self.flipped  

    def on_yes_button_click(self):
        self.error_icon.setVisible(False)
        self.success_icon.setVisible(False)        
        self.label.setText("Measuring frequency... The process can take a few seconds. Please wait and don't close the window. After 60 seconds, the process "
                           "will be interrupted automatically.")
        self.loader_label.setVisible(True) 
        self.flip_timer.start(400)  

        self.yes_button.setEnabled(False)
        self.no_button.setEnabled(False)

        self.worker = FrequencyWorker()
        self.worker.finished.connect(self.on_measurement_complete)
        self.worker.error.connect(self.on_measurement_error)
        self.worker.start()

    def on_measurement_complete(self, frequency_mhz):
        self.frequency_mhz = round(frequency_mhz, 3)
        self.flip_timer.stop() 
        self.loader_label.setVisible(False) 

        if self.frequency_mhz == 0.0:
            self.error_icon.setVisible(True)
            self.success_icon.setVisible(False)
            self.label.setText("Frequency not detected. Please check the connection and try again.")
            self.yes_button.setEnabled(True)
            self.yes_button.setText("RETRY")
        else:
            self.error_icon.setVisible(False)
            self.success_icon.setVisible(True)            
            self.label.setText(f"Frequency detected: {self.frequency_mhz} MHz")
            self.yes_button.setEnabled(False)
            self.yes_button.setVisible(False)

        self.no_button.setEnabled(True)
        GUIStyles.set_start_btn_style(self.no_button)
        self.no_button.setText("DONE")

    def on_measurement_error(self, error_msg):
        self.flip_timer.stop()  
        self.loader_label.setVisible(False)  
        self.error_icon.setVisible(True)
        self.success_icon.setVisible(False)        
        self.label.setText(f"Error: {error_msg}")
        self.yes_button.setEnabled(True)
        self.yes_button.setText("RETRY")
        self.no_button.setEnabled(True)
        self.no_button.setText("CANCEL")

    def on_no_button_click(self):
        self.error_icon.setVisible(False)
        self.success_icon.setVisible(False)
        self.loader_label.setVisible(False)
        self.close()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
        super().closeEvent(event)
