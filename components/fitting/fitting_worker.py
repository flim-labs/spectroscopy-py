"""
fitting_worker.py
=================
Background QThread worker that runs the decay-curve fitting.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from utils.fitting_utilities import fit_decay_curve


class FittingWorker(QThread):
    """
    A worker thread to perform the decay curve fitting in the background.

    This prevents the GUI from freezing during the potentially long fitting process.

    Signals:
        fitting_done (pyqtSignal): Emitted when fitting is complete, carrying a list of results.
        error_occurred (pyqtSignal): Emitted if an error occurs during fitting.
    """

    fitting_done = pyqtSignal(
        list
    )  # Emit a list of tuples (chart title (channel),  fitting result)
    error_occurred = pyqtSignal(str)  # Emit an error message

    def __init__(
        self,
        data,
        roi_checkboxes,
        cut_data_x,
        cut_data_y,
        y_data_shift,
        roi_regions,
        parent=None,
    ):
        """
        Initializes the FittingWorker.

        Args:
            data (list): The list of channel data to be fitted.
            roi_checkboxes (dict): A dictionary of ROI checkboxes to check if ROI is active.
            cut_data_x (dict): A dictionary of x-data, cut by ROI (for single file mode).
            cut_data_y (dict): A dictionary of y-data, cut by ROI (for single file mode).
            y_data_shift (int): A global time shift to apply to the data.
            roi_regions (dict): A dictionary of ROI regions (min, max) for each channel.
            parent (QObject, optional): The parent object. Defaults to None.
        """
        super().__init__(parent)
        self.data = data
        self.roi_checkboxes = roi_checkboxes
        self.cut_data_x = cut_data_x
        self.cut_data_y = cut_data_y
        self.y_data_shift = y_data_shift
        self.roi_regions = roi_regions

    def get_data_point(self, data_point, channel):
        """
        Gets the appropriate data (full or ROI-cut) for a given channel.

        Args:
            data_point (dict): The full data dictionary for the channel.
            channel (int): The channel index.

        Returns:
            tuple: A tuple of (x_data, y_data) arrays for fitting.
        """
        if channel in self.roi_checkboxes and self.roi_checkboxes[channel].isChecked():
            # Check if we're in multi-file mode
            has_file_index = "file_index" in data_point

            if has_file_index and channel in self.roi_regions:
                # Multi-file mode: apply ROI to this specific file's data
                x = data_point["x"]
                y = data_point["y"]

                # Ensure X and Y have the same length
                min_len = min(len(x), len(y))
                if len(x) != len(y):
                    x = x[:min_len]
                    y = y[:min_len]

                min_x, max_x = self.roi_regions[channel]
                mask = (x >= min_x) & (x <= max_x)
                return x[mask], y[mask]
            elif channel in self.cut_data_x:
                # Single file mode: use the pre-cut data
                return self.cut_data_x[channel], self.cut_data_y[channel]
            else:
                # Fallback: no ROI data available
                return data_point["x"], data_point["y"]
        else:
            return data_point["x"], data_point["y"]

    def run(self):
        """
        The main execution method of the thread.

        Iterates through the data for each channel, performs the fitting,
        and emits the results or an error.
        """
        results = []
        for idx, data_point in enumerate(self.data):
            try:
                x, y = self.get_data_point(data_point, data_point["channel_index"])
                result = fit_decay_curve(
                    x,
                    y,
                    data_point["channel_index"],
                    y_shift=data_point["time_shift"],
                )
                # Preserve file_index and file_name from input data
                if "file_index" in data_point:
                    result["file_index"] = data_point["file_index"]
                if "file_name" in data_point:
                    result["file_name"] = data_point["file_name"]
                results.append((result))
            except TimeoutError as te:
                self.error_occurred.emit(f"An error occurred: {str(te)}")
                return
            except Exception as e:
                import traceback

                traceback.print_exc()
                self.error_occurred.emit(f"An error occurred: {str(e)}")
                return
        self.fitting_done.emit(results)
