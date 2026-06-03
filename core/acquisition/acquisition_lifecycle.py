"""
acquisition_lifecycle.py 
============================================================
Handles the full acquisition lifecycle:
- _validate_parameters
- _prepare_spectroscopy_parameters
- _start_acquisition_process
- _update_ui_post_start
- begin_spectroscopy_experiment
- _stop_hardware_and_update_state
- _finalize_ui_after_stop
- _handle_reference_file_after_stop
- _process_phasor_results
- _handle_post_acquisition_tasks
- stop_spectroscopy_experiment
- check_card_connection
"""

import json
import flim_labs

from components.box_message import BoxMessage
from components.check_card import CheckCard
from utils.export_data import ExportData
from utils.gui_styles import GUIStyles
from utils.helpers import mhz_to_ns
from components.lin_log_control import LinLogControl
from components.plots_config import PlotsConfigPopup
from core.phasors_controller import PhasorsController
import settings.settings as s

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer


def _validate_parameters(app) -> bool:
    """
    Validates essential acquisition parameters before starting.

    Checks for selected channels and a valid bin width.

    Args:
        app: The main application instance.

    Returns:
        bool: True if validation passes, False otherwise.
    """
    if len(app.selected_channels) == 0:
        BoxMessage.setup(
            "Error",
            "No channels selected",
            QMessageBox.Icon.Warning,
            GUIStyles.set_msg_box_style(),
        )
        return False

    bin_width_micros = int(
        app.settings.value(s.SETTINGS_BIN_WIDTH, s.DEFAULT_BIN_WIDTH)
    )
    if bin_width_micros < 1000:
        BoxMessage.setup(
            "Error",
            "Bin width value cannot be less than 1000μs",
            QMessageBox.Icon.Warning,
            GUIStyles.set_msg_box_style(),
        )
        return False

    return True


def _prepare_spectroscopy_parameters(app, frequency_mhz) -> dict:
    """
    Gathers and prepares all parameters for the flim_labs.start_spectroscopy call.

    Args:
        app: The main application instance.
        frequency_mhz (float): The current laser frequency in MHz.

    Returns:
        dict: A dictionary of parameters for the FLIM-Labs library.
    """
    from core.controls_controller import ControlsController

    acquisition_time = ControlsController.get_acquisition_time(app)
    # Standard edition passes pico_mode explicitly as a kwarg override
    firmware_selected, _ = ControlsController.get_firmware_selected(
        app, frequency_mhz, app.pico_mode
    )

    tau_ns = (
        float(app.settings.value(s.SETTINGS_TAU_NS, "0"))
        if ControlsController.is_reference_phasors(app)
        or ControlsController.is_reference_birfi(app)
        else None
    )

    phasors_reference_file = None
    if app.tab_selected == s.TAB_PHASORS:
        phasors_reference_file = app.phasors_reference_file
        with open(app.phasors_reference_file, "r") as f:
            reference_data = json.load(f)
            app.harmonic_selector_value = int(reference_data["harmonics"])
    else:
        app.harmonic_selector_value = app.control_inputs[s.SETTINGS_HARMONIC].value()

    # Build channels_name dictionary with 0-based integer keys
    channels_name_dict = {}
    if hasattr(app, "channel_names") and app.channel_names:
        for channel in sorted(app.selected_channels):
            name = app.channel_names.get(str(channel), str(channel + 1))
            channels_name_dict[channel] = name

    # Calibration type
    calibration_type = "None"
    if ControlsController.is_reference_phasors(app):
        calibration_type = "Phasors"
    elif app.tab_selected == s.TAB_SPECTROSCOPY and ControlsController.is_reference_irf(app):
        calibration_type = "IRF"
    elif app.tab_selected == s.TAB_SPECTROSCOPY and ControlsController.is_reference_birfi(app):
        calibration_type = "BIRFI"

    return {
        "enabled_channels": app.selected_channels,
        "bin_width_micros": int(
            app.settings.value(s.SETTINGS_BIN_WIDTH, s.DEFAULT_BIN_WIDTH)
        ),
        "frequency_mhz": frequency_mhz,
        "firmware_file": firmware_selected,
        "acquisition_time_millis": (
            acquisition_time * 1000 if acquisition_time else None
        ),
        "tau_ns": tau_ns,
        "reference_file": phasors_reference_file,
        "harmonics": int(app.harmonic_selector_value),
        "write_bin": False,
        "time_tagger": (
            app.time_tagger
            and app.write_data_gui
            and app.tab_selected != s.TAB_PHASORS
        ),
        "pico_mode": app.pico_mode,
        "channels_name": channels_name_dict,
        "calibration_type": calibration_type,
    }


def _start_acquisition_process(app, params) -> bool:
    """
    Initiates the hardware acquisition process by calling the core library.

    Args:
        app: The main application instance.
        params (dict): The dictionary of parameters for the acquisition.

    Returns:
        bool: True if acquisition started successfully, False otherwise.
    """
    try:
        print(f"Starting acquisition with params: {params}")
        app.all_phasors_points = PhasorsController.get_empty_phasors_points()
        flim_labs.start_spectroscopy(**params)
        return True
    except Exception as e:
        check_card_connection(app)
        BoxMessage.setup(
            "Error",
            f"Error starting spectroscopy: {e}",
            QMessageBox.Icon.Warning,
            GUIStyles.set_msg_box_style(),
        )
        return False


def _update_ui_post_start(app):
    """
    Updates UI elements and timers after acquisition starts successfully.

    Disables controls, updates the start button style, and starts the
    data polling timer.

    Args:
        app: The main application instance.
    """
    from core.ui_controller import UIController
    from core.controls_controller import ControlsController

    app.mode = s.MODE_RUNNING
    UIController.style_start_button(app)
    QApplication.processEvents()
    app.update_plots_enabled = True
    ControlsController.top_bar_set_enabled(app, False)
    LinLogControl.set_lin_log_switches_enable_mode(app.lin_log_switches, False)
    app.pull_from_queue_timer.start(25)


def begin_spectroscopy_experiment(app):
    """
    Coordinates the process of starting a spectroscopy experiment.

    Runs through all pre-flight checks, prepares parameters, starts the
    hardware, and updates the UI.

    Args:
        app: The main application instance.
    """
    from core.plots_controller import PlotsController
    from core.controls_controller import ControlsController
    from core.acquisition.acquisition_reference import _validate_reference_file

    try:
        check_card_connection(app, start_experiment=True)
    except Exception as e:
        BoxMessage.setup(
            "Error",
            f"Error starting spectroscopy: {e}",
            QMessageBox.Icon.Warning,
            GUIStyles.set_msg_box_style(),
        )
        return

    frequency_mhz = ControlsController.get_frequency_mhz(app)
    if frequency_mhz == 0.0:
        BoxMessage.setup(
            "Error",
            "Frequency not detected",
            QMessageBox.Icon.Warning,
            GUIStyles.set_msg_box_style(),
        )
        return

    if not _validate_parameters(app):
        return

    if (
        (app.tab_selected == s.TAB_SPECTROSCOPY or app.tab_selected == s.TAB_FITTING)
        and len(app.selected_channels) > 4
        and not app.plots_to_show_already_appear
    ):
        popup = PlotsConfigPopup(app, start_acquisition=True)
        popup.show()
        app.plots_to_show_already_appear = True
        return

    ref_valid = _validate_reference_file(app, frequency_mhz)
    if not ref_valid:
        return
    if ref_valid == "popup":
        return

    PlotsController.clear_plots(app)
    PlotsController.generate_plots(app, frequency_mhz)

    params = _prepare_spectroscopy_parameters(app, frequency_mhz)

    if not _start_acquisition_process(app, params):
        return

    _update_ui_post_start(app)


def _stop_hardware_and_update_state(app):
    """
    Stops the FLIM-LABS hardware and updates the application's internal state.

    Args:
        app: The main application instance.
    """
    from core.ui_controller import UIController

    print("Stopping spectroscopy")
    try:
        flim_labs.request_stop()
    except Exception as e:
        print(f"Could not stop flim_labs gracefully: {e}")
    app.mode = s.MODE_STOPPED
    UIController.style_start_button(app)
    QApplication.processEvents()


def _finalize_ui_after_stop(app):
    """
    Re-enables UI controls and cleans up temporary widgets after stopping acquisition.

    Args:
        app: The main application instance.
    """
    from core.controls_controller import ControlsController

    LinLogControl.set_lin_log_switches_enable_mode(app.lin_log_switches, True)
    ControlsController.top_bar_set_enabled(app, True)

    def clear_cps_and_countdown_widgets():
        for _, animation in app.cps_widgets_animation.items():
            if animation:
                animation.stop()
        for _, widget in app.acquisition_time_countdown_widgets.items():
            if widget:
                widget.setVisible(False)

    QTimer.singleShot(400, clear_cps_and_countdown_widgets)
    if app.tab_selected == s.TAB_FITTING:
        ControlsController.fit_button_show(app)

    harmonic_selected = int(
        app.settings.value(s.SETTINGS_HARMONIC, s.SETTINGS_HARMONIC_DEFAULT)
    )
    if harmonic_selected > 1:
        app.harmonic_selector_shown = True


def _handle_reference_file_after_stop(app):
    """
    If a calibration reference was recorded, reads the generated file path from .pid file.

    Args:
        app: The main application instance.
    """
    from core.controls_controller import ControlsController
    from core.fitting_controller import FittingController
    from core.ui_controller import UIController

    if app.tab_selected != s.TAB_FITTING and (
        ControlsController.is_reference_phasors(app)
        or ControlsController.is_reference_birfi(app)
        or ControlsController.is_reference_irf(app)
    ):
        try:
            with open(".pid", "r") as f:
                lines = f.readlines()
                reference_file = lines[0].split("=")[1].strip()
            if reference_file.endswith("calibration.json"):
                app.saved_phasors_reference_file = reference_file
                app.phasors_reference_file = reference_file
            else:
                app.irf_reference_file = reference_file
            print(f"Last reference file: {reference_file}")
            if (
                app.control_inputs["calibration"].currentIndex() == 3
                and reference_file.endswith("birfi.json")
            ):
                FittingController.update_ref_file_with_birfi_results(
                    app, reference_file
                )
            if (
                app.control_inputs["calibration"].currentIndex() == 2
                and reference_file.endswith("irf.json")
            ):
                FittingController.extract_irf_data_from_ref_file(app, reference_file)
            UIController.update_reference_info_banner_label(app)
        except (IOError, IndexError) as e:
            print(f"Could not read reference file from .pid: {e}")


def _process_phasor_results(app):
    """
    Finalizes phasor plots after acquisition stops.

    Adds cluster centers, legends, and quantizes the data if enabled.

    Args:
        app: The main application instance.
    """
    from core.controls_controller import ControlsController

    if not ControlsController.is_phasors(app):
        return

    frequency_mhz = ControlsController.get_current_frequency_mhz(app)
    laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0

    for _, channel_index in enumerate(app.plots_to_show):
        PhasorsController.generate_coords(app, channel_index)
        PhasorsController.draw_lifetime_points_in_phasors(
            app, channel_index, 1, laser_period_ns, frequency_mhz
        )

    if app.quantized_phasors:
        PhasorsController.quantize_phasors(
            app, 1, bins=int(s.PHASORS_RESOLUTIONS[app.phasors_resolution])
        )

    PhasorsController.generate_phasors_cluster_center(app, 1)
    PhasorsController.generate_phasors_legend(app, 1)


def _handle_post_acquisition_tasks(app):
    """
    Handles final tasks like data saving after acquisition.

    Args:
        app: The main application instance.
    """
    if app.write_data_gui:
        QTimer.singleShot(
            300,
            lambda: ExportData.save_acquisition_data(app, active_tab=app.tab_selected),
        )


def stop_spectroscopy_experiment(app):
    """
    Coordinates the process of stopping a spectroscopy experiment.

    Stops the hardware, finalizes the UI, processes results, and handles
    any post-acquisition tasks.

    Args:
        app: The main application instance.
    """
    _stop_hardware_and_update_state(app)
    _finalize_ui_after_stop(app)
    _handle_reference_file_after_stop(app)
    _process_phasor_results(app)
    _handle_post_acquisition_tasks(app)


def check_card_connection(app, start_experiment=False):
    """
    Checks for a connection to the FLIM-LABS hardware card.

    Updates the UI with the card's status or an error message.

    Args:
        app: The main application instance.
        start_experiment (bool): If True, re-raises exceptions to halt
            the start of an experiment. Defaults to False.

    Raises:
        Exception: Re-raises the exception if start_experiment is True
                   and a card is not found.
    """
    try:
        card_serial_number = flim_labs.check_card()
        CheckCard.update_check_message(app, str(card_serial_number), error=False)
    except Exception as e:
        if str(e) == "CardNotFound":
            CheckCard.update_check_message(app, "Card Not Found", error=True)
        else:
            CheckCard.update_check_message(app, str(e), error=True)
        if start_experiment:
            raise