"""
controls_acquisition.py
=======================
Handles acquisition flow, channel selection, sync mode, and frequency logic:
- on_start_button_click
- on_bin_width_change / on_time_span_change / on_free_running_changed / on_acquisition_time_change
- on_export_data_changed
- on_connection_type_value_change
- on_channel_selected / channel_selector_set_enabled
- get_selected_channels_from_settings / set_selected_channels_to_settings
- get_frequency_mhz / get_current_frequency_mhz
- on_sync_selected / start_sync_in_dialog / update_sync_in_button
- on_pico_mode_changed / update_pico_mode_toggle / _is_pico_mode_available
- get_firmware_selected / get_acquisition_time
"""

import json
import flim_labs

from utils.helpers import is_frequency_near_supported_pico_modes, mhz_to_ns
from components.read_data import ReadData
from components.sync_in_popup import SyncInDialog
from core.acquisition_controller import AcquisitionController
from core.phasors_controller import PhasorsController
from core.plots_controller import PlotsController
import settings.settings as s
from utils.layout_utilities import hide_layout, show_layout

from PyQt6.QtWidgets import QWidget


def on_start_button_click(app):
    """
    Handles the click event of the main START/STOP button.

    Args:
        app: The main application instance.
    """
    from core.controls.controls_phasors import is_phasors

    if app.mode == s.MODE_STOPPED:
        app.acquisition_stopped = False
        if not is_phasors(app):
            app.harmonic_selector_shown = False
        AcquisitionController.begin_spectroscopy_experiment(app)
    elif app.mode == s.MODE_RUNNING:
        app.acquisition_stopped = True
        AcquisitionController.stop_spectroscopy_experiment(app)


def on_bin_width_change(app, value):
    """
    Callback for when the bin width changes.

    Args:
        app: The main application instance.
        value (int): The new bin width in microseconds.
    """
    from utils.export_data import ExportData

    app.settings.setValue(s.SETTINGS_BIN_WIDTH, value)
    ExportData.calc_exported_file_size(app)


def on_time_span_change(app, value):
    """
    Callback for when the intensity plot time span changes.

    Args:
        app: The main application instance.
        value (int): The new time span in seconds.
    """
    app.settings.setValue(s.SETTINGS_TIME_SPAN, value)


def on_free_running_changed(app, state):
    """
    Callback for the 'Free running' mode switch.

    Args:
        app: The main application instance.
        state (bool): The new state of the switch.
    """
    from utils.export_data import ExportData

    app.control_inputs[s.SETTINGS_ACQUISITION_TIME].setEnabled(not state)
    app.settings.setValue(s.SETTINGS_FREE_RUNNING, state)
    ExportData.calc_exported_file_size(app)


def on_acquisition_time_change(app, value):
    """
    Callback for when the acquisition time changes.

    Args:
        app: The main application instance.
        value (int): The new acquisition time in seconds.
    """
    from utils.export_data import ExportData

    app.settings.setValue(s.SETTINGS_ACQUISITION_TIME, value)
    ExportData.calc_exported_file_size(app)


def on_export_data_changed(app, state):
    """
    Callback for the 'Export data' switch.

    Args:
        app: The main application instance.
        state (bool): The new state of the switch.
    """
    from utils.export_data import ExportData

    app.settings.setValue(s.SETTINGS_WRITE_DATA, state)
    app.write_data_gui = state
    if s.TIME_TAGGER_WIDGET in app.widgets:
        app.widgets[s.TIME_TAGGER_WIDGET].setVisible(state)
    app.bin_file_size_label.show() if state else app.bin_file_size_label.hide()
    ExportData.calc_exported_file_size(app) if state else None


def on_cps_threshold_change(app, value):
    """
    Callback for when the pile-up CPS threshold changes.

    Args:
        app: The main application instance.
        value (int): The new CPS threshold.
    """
    app.settings.setValue(s.SETTINGS_CPS_THRESHOLD, value)


def on_connection_type_value_change(app, value):
    """
    Callback for when the connection type (USB/SMA) changes.

    Args:
        app: The main application instance.
        value (int): The index of the selected connection type.
    """
    app.settings.setValue(s.SETTINGS_CONNECTION_TYPE, value)


def get_free_running_state(app):
    """
    Gets the current state of the 'Free running' mode switch.

    Args:
        app: The main application instance.

    Returns:
        bool: True if free running mode is enabled, False otherwise.
    """
    return app.control_inputs[s.SETTINGS_FREE_RUNNING].isChecked()


def get_acquisition_time(app):
    """
    Gets the acquisition time in seconds based on the current settings.

    Returns None if in 'Free running' mode.

    Args:
        app: The main application instance.

    Returns:
        int | None: The acquisition time in seconds, or None.
    """
    return (
        None
        if get_free_running_state(app)
        else int(
            app.settings.value(
                s.SETTINGS_ACQUISITION_TIME, s.DEFAULT_ACQUISITION_TIME
            )
        )
    )


def get_current_frequency_mhz(app):
    """
    Gets the current operational laser frequency in MHz.

    Determined based on the current mode (read vs. acquire) and the
    selected synchronization source.

    Args:
        app: The main application instance.

    Returns:
        float: The current frequency in MHz.
    """
    if app.acquire_read_mode == "read":
        return ReadData.get_frequency_mhz(app)
    if app.selected_sync == "sync_in":
        return app.sync_in_frequency_mhz
    return int(app.selected_sync.split("_")[-1])


def get_frequency_mhz(app):
    """
    Gets the laser frequency in MHz based on the current settings.

    Convenience alias for get_current_frequency_mhz.

    Args:
        app: The main application instance.

    Returns:
        float: The current frequency in MHz.
    """
    return get_current_frequency_mhz(app)


def _is_pico_mode_available(app, frequency_mhz=None):
    """
    Checks whether pico mode can be enabled based on channels and frequency.

    Args:
        app: The main application instance.
        frequency_mhz (float | None): Frequency to evaluate. Defaults to current.

    Returns:
        bool: True if pico mode can be used, False otherwise.
    """
    freq = frequency_mhz if frequency_mhz is not None else get_current_frequency_mhz(app)
    channels_ok = 0 < len(app.selected_channels) <= 2
    freq_ok = is_frequency_near_supported_pico_modes(freq)
    return channels_ok and freq_ok


def update_pico_mode_toggle(app, frequency_mhz=None):
    """
    Updates visibility and checked state of the pico mode toggle.

    Args:
        app: The main application instance.
        frequency_mhz (float | None): Frequency to evaluate. Defaults to current.
    """
    if s.SETTINGS_PICO_MODE not in app.control_inputs:
        return

    pico_toggle = app.control_inputs[s.SETTINGS_PICO_MODE]
    pico_container = app.widgets.get("pico_mode_container", None)
    available = _is_pico_mode_available(app, frequency_mhz)

    if available:
        if pico_container:
            pico_container.setVisible(True)
        pico_toggle.setVisible(True)
        pico_toggle.setEnabled(True)
        pico_toggle.setChecked(app.pico_mode)
    else:
        pico_toggle.setChecked(False)
        pico_toggle.setVisible(False)
        if pico_container:
            pico_container.setVisible(False)
        app.pico_mode = False
        app.settings.setValue(s.SETTINGS_PICO_MODE, s.DEFAULT_PICO_MODE)


def on_pico_mode_changed(app, enabled: bool):
    """
    Handles pico mode toggle changes.

    Args:
        app: The main application instance.
        enabled (bool): New pico mode state.
    """
    app.pico_mode = enabled
    app.settings.setValue(s.SETTINGS_PICO_MODE, enabled)


def get_firmware_selected(app, frequency_mhz, pico_mode=None):
    """
    Determines the appropriate firmware file based on current settings.

    Args:
        app: The main application instance.
        frequency_mhz (float): The current laser frequency.
        pico_mode (bool | None): Pico mode to pass to backend. Defaults to current.

    Returns:
        tuple[str, str]: Firmware file path and connection type string.
    """
    connection_type = app.control_inputs["channel_type"].currentText()
    connection_type = "USB" if str(connection_type) == "USB" else "SMA"
    firmware_selected = flim_labs.get_spectroscopy_firmware(
        sync="in" if app.selected_sync == "sync_in" else "out",
        frequency_mhz=frequency_mhz,
        channel=connection_type.lower(),
        channels=app.selected_channels,
        sync_connection="sma",
        pico_mode=False  # Pico mode support removed; always False,
    )
    firmware_selected = firmware_selected.replace("_100ps", "")
    print(firmware_selected)
    return firmware_selected, connection_type


def on_channel_selected(app, checked: bool, channel: int):
    """
    Callback for when a channel selection checkbox is toggled.

    Updates selected channels and plots_to_show, then regenerates plots.

    Args:
        app: The main application instance.
        checked (bool): The new state of the checkbox.
        channel (int): The channel index that was changed.
    """
    from utils.export_data import ExportData

    app.settings.setValue(s.SETTINGS_PLOTS_TO_SHOW, json.dumps(app.plots_to_show))
    if checked:
        if channel not in app.selected_channels:
            app.selected_channels.append(channel)
        if channel not in app.plots_to_show and len(app.plots_to_show) < 4:
            app.plots_to_show.append(channel)
    else:
        if channel in app.selected_channels:
            app.selected_channels.remove(channel)
        if channel in app.plots_to_show:
            app.plots_to_show.remove(channel)
    app.selected_channels.sort()
    app.plots_to_show.sort()
    app.settings.setValue(s.SETTINGS_PLOTS_TO_SHOW, json.dumps(app.plots_to_show))
    set_selected_channels_to_settings(app)
    PlotsController.clear_plots(app)
    PlotsController.generate_plots(app)
    ExportData.calc_exported_file_size(app)
    update_pico_mode_toggle(app)


def channel_selector_set_enabled(app, enabled: bool):
    """
    Enables or disables all channel selection checkboxes.

    Args:
        app: The main application instance.
        enabled (bool): True to enable checkboxes, False to disable.
    """
    for checkbox in app.channel_checkboxes:
        checkbox.setEnabled(enabled)


def get_selected_channels_from_settings(app):
    """
    Loads the selected channels from the application settings.

    Args:
        app: The main application instance.
    """
    app.selected_channels = []
    for i in range(s.MAX_CHANNELS):
        is_selected = app.settings.value(f"channel_{i}", "false") == "true"
        if is_selected:
            app.selected_channels.append(i)
        if i < len(app.channel_checkboxes):
            app.channel_checkboxes[i].set_checked(is_selected)


def set_selected_channels_to_settings(app):
    """
    Saves the currently selected channels to the application settings.

    Args:
        app: The main application instance.
    """
    for i in range(s.MAX_CHANNELS):
        app.settings.setValue(f"channel_{i}", "false")
        if i in app.selected_channels:
            app.settings.setValue(f"channel_{i}", "true")


def on_sync_selected(app, sync: str):
    """
    Callback for when a synchronization mode is selected.

    Args:
        app: The main application instance.
        sync (str): The name of the selected sync mode.
    """

    def update_phasors_lifetimes():
        frequency_mhz = get_current_frequency_mhz(app)
        if frequency_mhz != 0.0:
            from core.controls.controls_state import time_shifts_set_enabled, reset_time_shifts_values
            time_shifts_set_enabled(app, True)
            laser_period_ns = mhz_to_ns(frequency_mhz)
            harmonic = app.control_inputs[s.HARMONIC_SELECTOR].currentIndex() + 1
            for _, channel in enumerate(app.plots_to_show):
                PhasorsController.draw_lifetime_points_in_phasors(
                    app, channel, harmonic, laser_period_ns, frequency_mhz
                )
        else:
            from core.controls.controls_state import time_shifts_set_enabled
            time_shifts_set_enabled(app, False)
        from core.controls.controls_state import reset_time_shifts_values
        reset_time_shifts_values(app)

    if app.selected_sync == sync and sync == "sync_in":
        start_sync_in_dialog(app)
        update_phasors_lifetimes()
        return
    app.selected_sync = sync
    app.settings.setValue(s.SETTINGS_SYNC, sync)
    update_phasors_lifetimes()
    update_pico_mode_toggle(app, get_current_frequency_mhz(app))


def start_sync_in_dialog(app):
    """
    Opens the dialog for configuring the 'Sync In' frequency.

    Args:
        app: The main application instance.
    """
    dialog = SyncInDialog()
    dialog.exec()
    if dialog.frequency_mhz != 0.0:
        app.sync_in_frequency_mhz = dialog.frequency_mhz
        app.settings.setValue(
            s.SETTINGS_SYNC_IN_FREQUENCY_MHZ, app.sync_in_frequency_mhz
        )
        update_sync_in_button(app)


def update_sync_in_button(app):
    """
    Updates the text of the 'Sync In' button to show the detected frequency.

    Args:
        app: The main application instance.
    """
    from core.controls.controls_state import time_shifts_set_enabled

    if app.sync_in_frequency_mhz == 0.0:
        time_shifts_set_enabled(app, False)
        app.sync_buttons[0][0].setText("Sync In (not detected)")
    else:
        time_shifts_set_enabled(app, True)
        app.sync_buttons[0][0].setText(f"Sync In ({app.sync_in_frequency_mhz} MHz)")
    update_pico_mode_toggle(app, app.sync_in_frequency_mhz)



def on_use_deconvolution_changed(app, state):
    """
    Callback for the 'Use deconvolution' switch.

    Args:
        app: The main application instance.
        state (bool): The new state of the switch.
    """
    from core.ui_controller import UIController

    app.settings.setValue(s.SETTINGS_USE_DECONVOLUTION, state)
    app.use_deconvolution = state
    if state:
        UIController.update_reference_info_banner_label(app)
        show_layout(app.widgets[s.REFERENCE_INFO_BANNER])
        app.control_inputs[s.LOAD_REF_BTN].setText("LOAD IRF")
        app.control_inputs[s.LOAD_REF_BTN].show()
    else:
        hide_layout(app.widgets[s.REFERENCE_INFO_BANNER])
        app.control_inputs[s.LOAD_REF_BTN].hide()    
        
        

def on_tau_change(app, value):
    """
    Callback for when the TAU value changes. Saves the new value to settings.

    Args:
        app: The main application instance.
        value (float): The new TAU value in nanoseconds.
    """
    app.settings.setValue(s.SETTINGS_TAU_NS, value)


def on_harmonic_change(app, value):
    """
    Callback for when the harmonic number changes. Saves the value.

    Args:
        app: The main application instance.
        value (int): The new harmonic number.
    """
    app.settings.setValue(s.SETTINGS_HARMONIC, value)


def on_calibration_change(app, value):
    """
    Callback for when the calibration type changes.

    Args:
        app: The main application instance.
        value (int): The index of the selected calibration type.
    """
    app.settings.setValue(s.SETTINGS_CALIBRATION_TYPE, value)
    if value == 1:  # Phasors Ref. selected
        app.control_inputs[s.SETTINGS_HARMONIC].show()
        app.control_inputs[s.SETTINGS_HARMONIC_LABEL].show()
    if value == 1 or value == 3:  # Phasors Ref. or BIRFI Ref. selected
        app.control_inputs["tau_label"].show()
        app.control_inputs["tau"].show()
    else:
        app.control_inputs["tau_label"].hide()
        app.control_inputs["tau"].hide()
        app.control_inputs[s.SETTINGS_HARMONIC].hide()
        app.control_inputs[s.SETTINGS_HARMONIC_LABEL].hide()        