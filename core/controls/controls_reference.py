"""
controls_reference.py
=====================
Handles calibration, reference controls:
- on_load_reference / on_load_phasors_reference / on_load_irf_reference
- is_reference_phasors / is_reference_irf / is_reference_birfi
- is_phasor_ref_data / is_irf_ref_data / is_birfi_ref_data / is_fitting_ref_data
"""

import settings.settings as s

from PyQt6.QtWidgets import QFileDialog



def on_load_reference(app):
    """
    Opens a file dialog to allow the user to select a phasor or IRF reference file.

    Args:
        app: The main application instance.
    """
    from core.ui_controller import UIController

    if app.tab_selected == s.TAB_PHASORS:
        on_load_phasors_reference(app)
    if app.tab_selected == s.TAB_FITTING:
        on_load_irf_reference(app)
    UIController.update_reference_info_banner_label(app)


def on_load_phasors_reference(app):
    """
    Opens a file dialog for selecting a phasor calibration reference file.

    Args:
        app: The main application instance.
    """
    dialog = QFileDialog()
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    dialog.setNameFilter("Calibration Reference files (*phasors_reference.json)")
    dialog.setDefaultSuffix("phasors_reference.json")
    file_name, _ = dialog.getOpenFileName(
        app,
        "Load calibration reference file",
        "",
        "Calibration Reference files (*phasors_reference.json)",
        options=QFileDialog.Option.DontUseNativeDialog,
    )
    if file_name:
        app.phasors_reference_file = file_name


def on_load_irf_reference(app):
    """
    Opens a file dialog for selecting an IRF or BIRFI reference file.

    Args:
        app: The main application instance.
    """
    from core.fitting_controller import FittingController

    dialog = QFileDialog()
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    dialog.setNameFilter(
        "IRF Reference files (*irf_reference.json *birfi_reference.json)"
    )
    dialog.setDefaultSuffix("irf_reference.json")
    file_name, _ = dialog.getOpenFileName(
        app,
        "Load IRF reference file",
        "",
        "IRF Reference files (*irf_reference.json *birfi_reference.json)",
        options=QFileDialog.Option.DontUseNativeDialog,
    )
    if file_name:
        app.irf_reference_file = file_name
        FittingController.extract_irf_data_from_ref_file(app, file_name)



# ------------------------------------------------------------------
# Reference type predicates
# ------------------------------------------------------------------

def is_reference_phasors(app) -> bool:
    """
    Checks if the current mode is for recording a phasor reference.

    Returns:
        bool: True if in spectroscopy tab with 'Phasors Ref.' calibration.
    """
    selected_calibration = app.settings.value(
        s.SETTINGS_CALIBRATION_TYPE, s.DEFAULT_SETTINGS_CALIBRATION_TYPE
    )
    return app.tab_selected == s.TAB_SPECTROSCOPY and selected_calibration == 1


def is_reference_irf(app) -> bool:
    """
    Checks if the current mode is for recording an IRF reference.

    Returns:
        bool: True if selected calibration is 'IRF Ref.'
    """
    selected_calibration = app.settings.value(
        s.SETTINGS_CALIBRATION_TYPE, s.DEFAULT_SETTINGS_CALIBRATION_TYPE
    )
    return selected_calibration == 2


def is_reference_birfi(app) -> bool:
    """
    Checks if the current mode is for recording a BIRFI reference.

    Returns:
        bool: True if selected calibration is 'BIRFI Ref.'
    """
    selected_calibration = app.settings.value(
        s.SETTINGS_CALIBRATION_TYPE, s.DEFAULT_SETTINGS_CALIBRATION_TYPE
    )
    return selected_calibration == 3


def is_phasor_ref_data(reference_data) -> bool:
    return "ref_type" in reference_data and reference_data["ref_type"] == "phasors"


def is_irf_ref_data(reference_data) -> bool:
    return "ref_type" in reference_data and reference_data["ref_type"] == "irf"


def is_birfi_ref_data(reference_data) -> bool:
    return "ref_type" in reference_data and reference_data["ref_type"] == "birfi"


def is_fitting_ref_data(reference_data) -> bool:
    return (
        "ref_type" in reference_data
        and reference_data["ref_type"] == "irf"
        or reference_data["ref_type"] == "birfi"
    )