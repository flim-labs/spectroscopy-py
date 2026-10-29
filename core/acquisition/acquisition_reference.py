"""
acquisition_reference.py
=============================================================================
Handles reference file validation before starting an acquisition:
- _validate_reference_file  (dispatcher)
- _validate_irf_reference
- _validate_phasors_reference
- _show_error_popup         (helper)
- _validate_reference_data  (helper)
"""

import json

from components.box_message import BoxMessage
from utils.gui_styles import GUIStyles
from utils.helpers import ns_to_mhz
from components.plots_config import PlotsConfigPopup
import settings.settings as s

from PyQt6.QtWidgets import QMessageBox


def _validate_reference_data(ref_file, required_keys):
    """
    Loads and validates the structure of a JSON reference file.

    Args:
        ref_file (str): Path to the reference file.
        required_keys (list[str]): Keys that must be present in the JSON.

    Returns:
        dict | False: Parsed data if valid, False on read/parse error or
                      missing keys.
    """
    try:
        with open(ref_file, "r") as f:
            ref_data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        _show_error_popup("Error", f"Error reading reference file: {e}")
        return False

    for key in required_keys:
        if key not in ref_data:
            _show_error_popup("Error", f"Invalid reference file (missing {key})")
            return False

    return ref_data


def _validate_irf_reference(app, frequency_mhz):
    """
    Validates an IRF reference file for use on the Fitting tab.

    Args:
        app: The main application instance.
        frequency_mhz (float): The current laser frequency in MHz.

    Returns:
        bool | str: True if valid, False on error, "popup" if a channel
                    selection popup was triggered.
    """
    if not app.irf_reference_file:
        return _show_error_popup("Error", "No IRF reference file selected")

    ref_data = _validate_reference_data(
        app.irf_reference_file, ["channels", "irfs", "laser_period_ns"]
    )
    if not ref_data:
        return False

    if len(ref_data["channels"]) != len(app.selected_channels):
        return _show_error_popup(
            "Error", "Invalid IRF reference file (channels mismatch)"
        )

    if ns_to_mhz(ref_data["laser_period_ns"]) != frequency_mhz:
        return _show_error_popup(
            "Error",
            "Invalid calibration reference file (laser period mismatch)",
        )

    if (
        not all(plot in ref_data["channels"] for plot in app.plots_to_show)
        or len(app.plots_to_show) == 0
    ):
        popup = PlotsConfigPopup(
            app,
            start_acquisition=True,
            is_reference_loaded=True,
            reference_channels=ref_data["channels"],
        )
        popup.show()
        return "popup"

    return True


def _validate_phasors_reference(app, frequency_mhz):
    """
    Validates a phasors calibration reference file for use on the Phasors tab.

    Args:
        app: The main application instance.
        frequency_mhz (float): The current laser frequency in MHz.

    Returns:
        bool | str: True if valid, False on error, "popup" if a channel
                    selection popup was triggered.
    """
    if not app.phasors_reference_file:
        return _show_error_popup("Error", "No calibration reference file selected")

    ref_data = _validate_reference_data(
        app.phasors_reference_file,
        ["channels", "laser_period_ns", "harmonics", "curves", "tau_ns"],
    )
    if not ref_data:
        return False

    if len(ref_data["channels"]) != len(app.selected_channels):
        return _show_error_popup(
            "Error", "Invalid calibration reference file (channels mismatch)"
        )

    if ns_to_mhz(ref_data["laser_period_ns"]) != frequency_mhz:
        return _show_error_popup(
            "Error",
            "Invalid calibration reference file (laser period mismatch)",
        )

    if (
        not all(plot in ref_data["channels"] for plot in app.plots_to_show)
        or len(app.plots_to_show) == 0
    ):
        popup = PlotsConfigPopup(
            app,
            start_acquisition=True,
            is_reference_loaded=True,
            reference_channels=ref_data["channels"],
        )
        popup.show()
        return "popup"

    return True


def _validate_reference_file(app, frequency_mhz):
    """
    Dispatcher that routes reference validation based on the active tab.

    - Spectroscopy tab: always valid (no reference needed).
    - Fitting tab: skips validation unless deconvolution is enabled;
      then validates the IRF reference.
    - Phasors tab: validates the phasors calibration reference.

    Args:
        app: The main application instance.
        frequency_mhz (float): The current laser frequency in MHz.

    Returns:
        bool | str: True if valid, False on error, "popup" if a
                    channel-selection popup was triggered.
    """
    if app.tab_selected == s.TAB_SPECTROSCOPY:
        return True
    if app.tab_selected == s.TAB_FITTING:
        if not app.use_deconvolution:
            return True
        return _validate_irf_reference(app, frequency_mhz)
    if app.tab_selected == s.TAB_PHASORS:
        return _validate_phasors_reference(app, frequency_mhz)
    return True


def _show_error_popup(title, message):
    """
    Helper that shows a warning message box and returns False.

    Returns:
        bool: Always False, so callers can use `return _show_error_popup(...)`.
    """
    BoxMessage.setup(
        title,
        message,
        QMessageBox.Icon.Warning,
        GUIStyles.set_msg_box_style(),
    )
    return False
