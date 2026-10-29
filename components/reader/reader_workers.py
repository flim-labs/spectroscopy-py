"""
reader_workers.py
=================
Background thread utilities for read_data operations:
- WorkerSignals  — Qt signals for inter-thread communication
- SavePlotTask   — QRunnable that saves a matplotlib figure to PNG and EPS
"""

from matplotlib import pyplot as plt

from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject, pyqtSlot


class WorkerSignals(QObject):
    """Defines signals available from a running worker thread."""

    success = pyqtSignal(str)
    error = pyqtSignal(str)


class SavePlotTask(QRunnable):
    """A QRunnable task for saving a plot in a separate thread."""

    def __init__(self, plot, base_path, signals):
        """Initializes the SavePlotTask.

        Args:
            plot (matplotlib.figure.Figure): The plot to save.
            base_path (str): The base file path for the saved images.
            signals (WorkerSignals): The signals object to communicate results.
        """
        super().__init__()
        self.plot = plot
        self.base_path = base_path
        self.signals = signals

    @pyqtSlot()
    def run(self):
        """Executes the task: saves the plot to PNG and EPS formats."""
        try:
            png_path = (
                f"{self.base_path}.png"
                if not self.base_path.endswith(".png")
                else self.base_path
            )
            self.plot.savefig(png_path, format="png", bbox_inches="tight")
            eps_path = (
                f"{self.base_path}.eps"
                if not self.base_path.endswith(".eps")
                else self.base_path
            )
            self.plot.savefig(eps_path, format="eps", bbox_inches="tight")
            plt.close(self.plot)
            self.signals.success.emit(
                f"Plot images saved successfully as {png_path} and {eps_path}"
            )
        except Exception as e:
            plt.close(self.plot)
            self.signals.error.emit(str(e))