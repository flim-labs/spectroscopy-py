from functools import partial
from PyQt6.QtCore import (
    Qt,
    QRunnable,
    QThreadPool,
    pyqtSignal,
    QObject,
    pyqtSlot,
    QTimer,
)
from PyQt6.QtWidgets import QMessageBox
import flim_labs
from components.box_message import BoxMessage
from components.export_data import ExportData
from components.gui_styles import GUIStyles
from settings import DEFAULT_BIN_WIDTH, SETTINGS_BIN_WIDTH, TIME_TAGGER_PROGRESS_BAR


class TimeTaggerWorkerSignals(QObject):
    success = pyqtSignal()
    error = pyqtSignal(str)


class TimeTaggerProcessingTask(QRunnable):
    def __init__(self, bin_width_micros, enabled_channels, frequency_mhz, signals):
        super().__init__()
        self.bin_width_micros = bin_width_micros
        self.enabled_channels = enabled_channels
        self.frequency_mhz = frequency_mhz
        self.signals = signals

    @pyqtSlot()
    def run(self):
        try:
            flim_labs.spectroscopy_time_tagger(
                bin_width_micros=self.bin_width_micros,
                enabled_channels=self.enabled_channels,
                frequency_mhz=self.frequency_mhz,
            )
            self.signals.success.emit()
        except Exception as e:
            self.signals.error.emit(f"Error processing time tagger: {str(e)}")


class TimeTaggerController:
    @staticmethod
    def init_time_tagger_processing(app):
        bin_width_micros = int(
            app.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH)
        )
        enabled_channels = app.selected_channels
        frequency_mhz = app.get_frequency_mhz()
        signals = TimeTaggerWorkerSignals()
        signals.success.connect(
            lambda: TimeTaggerController.handle_success_processing(app)
        )
        signals.error.connect(
            lambda error: TimeTaggerController.show_error_message(app, error)
        )
        task = TimeTaggerProcessingTask(
            bin_width_micros, enabled_channels, frequency_mhz, signals
        )
        QThreadPool.globalInstance().start(task)

    @staticmethod
    def show_error_message(app, error):
        app.widgets[TIME_TAGGER_PROGRESS_BAR].set_visible(False)
        BoxMessage.setup(
            "Error", error, QMessageBox.Icon.Warning, GUIStyles.set_msg_box_style()
        )

    @staticmethod
    def handle_success_processing(app):
        app.widgets[TIME_TAGGER_PROGRESS_BAR].set_visible(False)
        QTimer.singleShot(
            300,
            partial(ExportData.save_acquisition_data, app, active_tab=app.tab_selected),
        )
