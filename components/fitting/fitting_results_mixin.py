"""
fitting_results_mixin.py
========================
Mixin that provides fitting result processing, signal handlers,
channel averaging and error display.
"""

import os
import numpy as np
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import QLabel
from components.lin_log_control import LinLogControl
from components.fitting.fitting_constants import DARK_THEME_BG_COLOR
import settings.settings as s


class FittingResultsMixin:
    """Mixin that handles processing and displaying fitting results."""

    # ------------------------------------------------------------------
    # Main results processor
    # ------------------------------------------------------------------

    def process_fitting_results(self, results):
        """
        Processes and displays the fitting results received from the worker.
        Groups results by file_index if multiple files are loaded.

        Args:
            results (list): A list of result dictionaries from the fitting process.
        """
        self.fitting_results = results

        # Add file_name and file_index to results if not present
        for result in results:
            if "error" in result:
                title = (
                    "Channel " + str(result["channel"] + 1)
                    if "channel" in result
                    else ""
                )
                self.display_error(result["error"], title)
            if "error" not in result:
                if "file_index" not in result:
                    result["file_index"] = 0
                if "file_name" not in result or result.get("file_name") == "File 1":
                    # Try to get file name from reader_data
                    fitting_files = (
                        self.app.reader_data.get("fitting", {})
                        .get("files", {})
                        .get("spectroscopy", "")
                    )
                    if fitting_files:
                        if isinstance(fitting_files, str):
                            result["file_name"] = os.path.basename(fitting_files)
                        elif isinstance(fitting_files, list) and len(fitting_files) > 0:
                            file_idx = result.get("file_index", 0)
                            if file_idx < len(fitting_files):
                                result["file_name"] = os.path.basename(
                                    fitting_files[file_idx]
                                )
                            else:
                                result["file_name"] = os.path.basename(fitting_files[0])

        # Check if results have multiple different file_index values (true multi-file)
        valid_results = [r for r in results if "error" not in r]
        unique_file_indices = set(r.get("file_index", 0) for r in valid_results)
        has_multiple_files = len(unique_file_indices) > 1

        # In READ mode with multiple channels from same file, we could average them
        # But in ACQUIRE mode, we ALWAYS want separate plots per channel
        has_multiple_channels_same_file = (
            self.read_mode and len(valid_results) > 1 and len(unique_file_indices) == 1
        )

        if has_multiple_files or has_multiple_channels_same_file:
            # For multiple files OR multiple channels from same file (READ mode only), show aggregated result
            if has_multiple_channels_same_file:
                # Average the channels (READ mode only)
                averaged_result = self._average_channels(valid_results)
                if averaged_result and 0 in self.plot_widgets:
                    self.update_plot(averaged_result, 0)
                    # Store the averaged result for export instead of original results
                    if self.save_plot_img:
                        self.export_img_btn.set_data_to_save([averaged_result])
                        self.export_img_btn.setVisible(True)
            else:
                # Multiple files case (READ mode)
                if valid_results:
                    # Check if channel 0 plot exists (should have been created in __init__ for multi-file mode)
                    if 0 in self.plot_widgets:
                        self.update_plot(valid_results, 0)
                        # Set data for export
                        if self.save_plot_img:
                            self.export_img_btn.set_data_to_save(valid_results)
                            self.export_img_btn.setVisible(True)
                    else:
                        # Fallback: display per-channel if channel 0 plot doesn't exist
                        for result in valid_results:
                            channel = next(
                                (
                                    item["channel_index"]
                                    for item in self.data
                                    if item["channel_index"] == result.get("channel", 0)
                                ),
                                None,
                            )
                            if channel is not None:
                                self.update_plot(result, channel)
        else:
            # Original behavior for single file
            for result in results:
                if "error" in result:
                    title = (
                        "Channel " + str(result["channel"] + 1)
                        if "channel" in result
                        else ""
                    )
                    self.display_error(result["error"], title)
                else:
                    channel = next(
                        (
                            item["channel_index"]
                            for item in self.data
                            if item["channel_index"] == result["channel"]
                        ),
                        None,
                    )
                    # If channel not found in data (e.g., fitting only without spectroscopy),
                    # use the channel from result directly if plot exists
                    if channel is None:
                        channel = result.get("channel", 0)

                    if channel is not None and channel in self.plot_widgets:
                        self.update_plot(result, channel)

            # Set export data for single file mode
            if self.save_plot_img:
                self.export_img_btn.set_data_to_save(results)
                self.export_img_btn.setVisible(True)

        # Hide roi checkboxes
        self.set_roi_checkboxes_visibility(False)
        LinLogControl.set_lin_log_switches_enable_mode(self.lin_log_switches, True)
        # Note: export button visibility is now set inside the if/else branches above
        # to ensure correct data is passed for export

        # Show export image button after fitting is complete (if save_plot_img is True)
        if self.save_plot_img:
            self.export_img_btn.setVisible(True)

    # ------------------------------------------------------------------
    # Qt slots
    # ------------------------------------------------------------------

    @pyqtSlot(list)
    def handle_fitting_done(self, results):
        """
        Slot to handle the successful completion of the fitting process.

        Args:
            results (list): The list of fitting results from the worker.
        """
        self.loading_text.setVisible(False)
        self.gif_label.setVisible(False)
        # Process results
        self.process_fitting_results(results)
        # Enable and style the export button
        self.export_fitting_btn.setEnabled(True)
        self.export_fitting_btn.setStyleSheet(
            "border: 1px solid #11468F; font-family: Montserrat; color:#11468F; background-color: white; font-weight: bold; padding: 8px; border-radius: 4px;"
        )

    @pyqtSlot(str)
    def handle_error(self, error_message):
        """
        Slot to handle errors that occurred during the fitting process.

        Args:
            error_message (str): The error message from the worker.
        """
        self.loading_text.setVisible(False)
        self.gif_label.setVisible(False)
        self.display_error(error_message, "")

    # ------------------------------------------------------------------
    # Channel averaging (READ mode)
    # ------------------------------------------------------------------

    def _average_channels(self, results):
        """Calculates the average of multiple channels from the same file.

        Args:
            results (list): List of fitting results for different channels.

        Returns:
            dict: Averaged fitting result with channel=0.
        """
        if not results or len(results) == 0:
            return None

        # Find minimum length to handle arrays of different sizes
        min_len_y = min(len(r["y_data"]) for r in results)
        min_len_fitted = min(len(r["fitted_values"]) for r in results)
        min_len_residuals = min(len(r["residuals"]) for r in results)
        min_len_x = min(len(r["x_values"]) for r in results)
        min_len_t = min(len(r["t_data"]) for r in results)

        # Calculate averages with truncated arrays
        avg_chi2 = np.mean([r["chi2"] for r in results])
        avg_r2 = (
            np.mean([r.get("r2", 0) for r in results])
            if all("r2" in r for r in results)
            else 0
        )

        # Use first result as template
        first = results[0]

        # Calculate averaged y_data
        avg_y_data = np.mean([r["y_data"][:min_len_y] for r in results], axis=0)
        avg_fitted = np.mean(
            [r["fitted_values"][:min_len_fitted] for r in results], axis=0
        )

        # Build fitted_params_text from averaged values
        fitted_params_text = f"Average of {len(results)} channels\n"
        fitted_params_text += (
            first.get("fitted_params_text", "").split("\n")[0] + "\n"
        )  # Keep first line (tau values)
        fitted_params_text += f"X² = {avg_chi2:.4f}\n"
        fitted_params_text += f"R² = {avg_r2:.4f}\n"

        avg_result = {
            "x_values": first["x_values"][:min_len_x],
            "t_data": first["t_data"][:min_len_t],
            "y_data": avg_y_data,
            "fitted_values": avg_fitted,
            "residuals": np.mean(
                [r["residuals"][:min_len_residuals] for r in results], axis=0
            ),
            "fitted_params_text": fitted_params_text,
            "scale_factor": np.mean([r["scale_factor"] for r in results]),
            "decay_start": first["decay_start"],
            "channel": 0,
            "chi2": avg_chi2,
            "r2": avg_r2,
            "file_index": first.get("file_index", 0),
            "file_name": first.get("file_name", "Averaged"),
        }

        return avg_result

    # ------------------------------------------------------------------
    # Error display
    # ------------------------------------------------------------------

    def display_error(self, error_message, title):
        """
        Displays an error message in the UI.

        Args:
            error_message (str): The error message to display.
            title (str): A title for the error (e.g., the channel name).
        """
        self.error_label = QLabel(f"Error {title}: {error_message}")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.error_label.setStyleSheet(
            f"font-size: 20px; color: red; background-color: {DARK_THEME_BG_COLOR}; margin-left: 10px;"
        )
        self.errors_layout.addWidget(self.error_label)
