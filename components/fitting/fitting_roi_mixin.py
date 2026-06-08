"""
fitting_roi_mixin.py
====================
Mixin that provides all Region-of-Interest (ROI) selection and management
methods for the fitting popup.
"""

import json
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox
from utils.gui_styles import GUIStyles
import settings.settings as s


class FittingROIMixin:
    """Mixin that handles ROI creation, interaction and persistence."""

    # ------------------------------------------------------------------
    # Saved ROI retrieval
    # ------------------------------------------------------------------

    def get_saved_roi(self, channel):
        """
        Retrieves the saved Region of Interest (ROI) for a channel from settings.

        Args:
            channel (int): The channel index.

        Returns:
            tuple or None: The (min, max) tuple for the ROI, or None if not found.
        """
        if channel in self.app.roi:
            return self.app.roi[channel]
        else:
            return None

    # ------------------------------------------------------------------
    # ROI change callbacks
    # ------------------------------------------------------------------

    def on_roi_selection_changed(self, roi, x, y, channel):
        """
        Callback for when the ROI selection is changed by the user.

        Args:
            roi (pg.LinearRegionItem): The ROI item that was changed.
            x (np.ndarray): The x-data array for the plot.
            y (np.ndarray): The y-data array for the plot.
            channel (int): The channel index.
        """
        self.set_roi_mask(roi, x, y, channel)
        self.app.settings.setValue(s.SETTINGS_ROI, json.dumps(self.app.roi))

    def on_roi_selection_changed_multi_file(self, roi, channel):
        """
        Callback for when the ROI selection is changed in multi-file mode.

        Args:
            roi (pg.LinearRegionItem): The ROI item that was changed.
            channel (int): The channel index.
        """
        min_x, max_x = roi.getRegion()
        # Store ROI region for multi-file mode
        self.roi_regions[channel] = (min_x, max_x)
        self.app.roi[channel] = (min_x, max_x)
        self.app.settings.setValue(s.SETTINGS_ROI, json.dumps(self.app.roi))

    # ------------------------------------------------------------------
    # ROI boundary enforcement
    # ------------------------------------------------------------------

    def limit_roi_bounds(self, roi):
        """
        Ensures the ROI selection does not go beyond the plot's x-axis limits.

        Args:
            roi (pg.LinearRegionItem): The ROI item to check.
        """
        min_val, max_val = roi.getRegion()
        min_limit = 0
        # Use data range instead of laser_period_ns for bin indices
        if self.data and len(self.data) > 0:
            x_data = self.data[0].get("x", [])
            if len(x_data) > 0:
                max_limit = np.max(x_data)
            else:
                max_limit = self.laser_period_ns
        else:
            max_limit = self.laser_period_ns

        if min_val < min_limit:
            min_val = min_limit
        if max_val > max_limit:
            max_val = max_limit
        roi.setRegion([min_val, max_val])

    # ------------------------------------------------------------------
    # ROI mask application
    # ------------------------------------------------------------------

    def set_roi_mask(self, roi, x, y, channel):
        """
        Applies the ROI to the data, storing the "cut" data for fitting.

        Args:
            roi (pg.LinearRegionItem): The ROI item defining the region.
            x (np.ndarray): The full x-data array.
            y (np.ndarray): The full y-data array.
            channel (int): The channel index.
        """
        if not roi.isVisible():
            return
        min_x, max_x = roi.getRegion()

        # Check if we're in multi-file mode
        has_multi_file = (
            self.data
            and len(self.data) > 1
            and any("file_index" in d for d in self.data)
        )

        if has_multi_file:
            # For multi-file mode, just store the ROI region - we'll apply it per file in get_data_point
            self.app.roi[channel] = (min_x, max_x)
        else:
            # For single file mode, apply the mask and store the cut data
            mask = (x >= min_x) & (x <= max_x)
            selected_x = x[mask]
            selected_y = y[mask]
            self.cut_data_x[channel] = selected_x
            self.cut_data_y[channel] = selected_y
            self.app.roi[channel] = (min_x, max_x)

            # Also cut IRF and raw signal using THE SAME MASK for consistency
            if self.use_deconvolution and self.irfs and self.raw_signals:
                # Find the index of this channel in self.data
                data_index = None
                for idx, d in enumerate(self.data):
                    if d["channel_index"] == channel:
                        data_index = idx
                        break

                if data_index is not None:
                    # Cut IRF with the same mask
                    if data_index < len(self.irfs):
                        irf = np.array(self.irfs[data_index])
                        # Verify IRF has same length as x before applying mask
                        if len(irf) == len(x):
                            self.cut_irfs[channel] = irf[mask]
                        else:
                            print(
                                f"Warning: IRF length ({len(irf)}) != x length ({len(x)}) for channel {channel}"
                            )

                    # Cut raw signal with the same mask
                    if data_index < len(self.raw_signals):
                        raw_signal_data = self.raw_signals[data_index]
                        raw_signal = np.array(
                            raw_signal_data["y"]
                            if isinstance(raw_signal_data, dict)
                            else raw_signal_data
                        )
                        # Verify raw signal has same length as x before applying mask
                        if len(raw_signal) == len(x):
                            self.cut_raw_signals[channel] = raw_signal[mask]
                        else:
                            print(
                                f"Warning: Raw signal length ({len(raw_signal)}) != x length ({len(x)}) for channel {channel}"
                            )

    # ------------------------------------------------------------------
    # ROI checkbox
    # ------------------------------------------------------------------

    def create_roi_checkbox(self, channel):
        """
        Creates the 'ROI' checkbox for a specific channel.

        Args:
            channel (int): The channel index.

        Returns:
            QCheckBox: The created checkbox widget.
        """
        checkbox = QCheckBox("ROI")
        checkbox.setStyleSheet(GUIStyles.set_checkbox_style())
        checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        checkbox.toggled.connect(
            lambda checked, channel=channel: self.on_roi_checkbox_state_changed(
                checked, channel
            )
        )
        self.roi_checkboxes[channel] = checkbox
        return checkbox

    def on_roi_checkbox_state_changed(self, checked: bool, channel: int):
        """
        Callback for when the ROI checkbox state changes. Shows/hides the ROI tool.

        Args:
            checked (bool): The new state of the checkbox.
            channel (int): The channel index.
        """
        if checked:
            self.roi_warnings[channel].setText(
                "Please select a significant portion of the curve that includes points from both the rising edge, the peak, and the falling edge for an accurate fit. Insufficient data may lead to unreliable fitting results."
            )
            self.roi_warnings[channel].setVisible(True)
        else:
            self.roi_warnings[channel].setVisible(False)
            self.roi_warnings[channel].setText("")
        if channel in self.roi_items:
            roi = self.roi_items[channel]
            roi.setVisible(checked)

    def set_roi_checkboxes_visibility(self, visible):
        """
        Shows or hides all ROI-related checkboxes and warning labels.

        Args:
            visible (bool): True to show, False to hide.
        """
        for ch, widget in self.roi_checkboxes.items():
            if widget is not None:
                widget.setVisible(visible)
        for ch, widget in self.roi_warnings.items():
            if widget is not None:
                widget.setVisible(visible)
