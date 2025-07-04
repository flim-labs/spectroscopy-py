from functools import partial
from PyQt6.QtCore import (
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
from utils.export_data import ExportData
from utils.gui_styles import GUIStyles
from settings.settings import DEFAULT_BIN_WIDTH, SETTINGS_BIN_WIDTH, TIME_TAGGER_PROGRESS_BAR


class TimeTaggerWorkerSignals(QObject):
    """Defines the signals available from a running TimeTaggerProcessingTask."""
    success = pyqtSignal()
    error = pyqtSignal(str)


class TimeTaggerProcessingTask(QRunnable):
    """A QRunnable task for processing time tagger data in a background thread."""
    def __init__(self, bin_width_micros, enabled_channels, frequency_mhz, signals):
        """Initializes the TimeTaggerProcessingTask.

        Args:
            bin_width_micros (int): The bin width in microseconds.
            enabled_channels (list): A list of enabled channel indices.
            frequency_mhz (float): The laser frequency in MHz.
            signals (TimeTaggerWorkerSignals): The signals object to communicate results.
        """
        super().__init__()
        self.bin_width_micros = bin_width_micros
        self.enabled_channels = enabled_channels
        self.frequency_mhz = frequency_mhz
        self.signals = signals

    @pyqtSlot()
    def run(self):
        """Executes the time tagger processing and emits signals on completion or error."""
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
    """A static controller class for managing time tagger processing."""
    @staticmethod
    def init_time_tagger_processing(app):
        """Initializes and starts the time tagger data processing in a background thread.

        Args:
            app: The main application instance.
        """
        from core.controls_controller import ControlsController
        bin_width_micros = int(
            app.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH)
        )
        enabled_channels = app.selected_channels
        frequency_mhz = ControlsController.get_frequency_mhz(app)
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
        """Displays an error message box.

        Args:
            app: The main application instance.
            error (str): The error message to display.
        """
        app.widgets[TIME_TAGGER_PROGRESS_BAR].set_visible(False)
        BoxMessage.setup(
            "Error", error, QMessageBox.Icon.Warning, GUIStyles.set_msg_box_style()
        )

    @staticmethod
    def handle_success_processing(app):
        """Handles the successful completion of time tagger processing.

        Hides the progress bar and triggers the data export process.

        Args:
            app: The main application instance.
        """
        app.widgets[TIME_TAGGER_PROGRESS_BAR].set_visible(False)
        QTimer.singleShot(
            300,
            partial(ExportData.save_acquisition_data, app, active_tab=app.tab_selected),
        )
