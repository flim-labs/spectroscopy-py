"""
controls_state.py
=================
Handles enable/disable state management and general UI helpers:
- controls_set_enabled / top_bar_set_enabled
- sync_buttons_set_enabled / channel_selector_set_enabled
- toggle_intensities_widgets_visibility
- time_shifts_set_enabled / reset_time_shifts_values
- SBR_set_visible / on_show_SBR_changed
- show_harmonic_selector / hide_harmonic_selector
- open_plots_config_popup / open_reader_popup / open_reader_metadata_popup
- export_data
"""

import flim_labs

from components.box_message import BoxMessage
from utils.gui_styles import GUIStyles
from components.plots_config import PlotsConfigPopup
from components.read_data import ReadDataControls, ReaderMetadataPopup, ReaderPopup
import settings.settings as s

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget


def controls_set_enabled(app, enabled: bool):
    """
    Enables or disables all main control inputs.

    Args:
        app: The main application instance.
        enabled (bool): True to enable controls, False to disable.
    """
    from core.controls.controls_acquisition import get_free_running_state

    for key in app.control_inputs:
        if key != "start_button":
            widget = app.control_inputs[key]
            if isinstance(widget, QWidget):
                widget.setEnabled(enabled)
    if "time_shift_sliders" in app.control_inputs:
        for _, widget in app.control_inputs["time_shift_sliders"].items():
            widget.setEnabled(enabled)
    if "time_shift_inputs" in app.control_inputs:
        for _, widget in app.control_inputs["time_shift_inputs"].items():
            widget.setEnabled(enabled)
    if enabled:
        app.control_inputs[s.SETTINGS_ACQUISITION_TIME].setEnabled(
            not get_free_running_state(app)
        )


def sync_buttons_set_enabled(app, enabled: bool):
    """
    Enables or disables all synchronization mode buttons.

    Args:
        app: The main application instance.
        enabled (bool): True to enable buttons, False to disable.
    """
    for button, _ in app.sync_buttons:
        button.setEnabled(enabled)


def channel_selector_set_enabled(app, enabled: bool):
    """
    Enables or disables all channel selection checkboxes.

    Args:
        app: The main application instance.
        enabled (bool): True to enable checkboxes, False to disable.
    """
    for checkbox in app.channel_checkboxes:
        checkbox.setEnabled(enabled)


def top_bar_set_enabled(app, enabled: bool):
    """
    Enables or disables the entire top bar area, including all controls.

    Args:
        app: The main application instance.
        enabled (bool): True to enable the top bar, False to disable.
    """
    sync_buttons_set_enabled(app, enabled)
    channel_selector_set_enabled(app, enabled)
    controls_set_enabled(app, enabled)


def toggle_intensities_widgets_visibility(app):
    """
    Shows or hides the intensity plot widgets based on the current mode.

    Args:
        app: The main application instance.
    """
    if app.intensities_widgets:
        for _, widget in app.intensities_widgets.items():
            if widget and isinstance(widget, QWidget):
                widget.setVisible(app.acquire_read_mode == "acquire")


def time_shifts_set_enabled(app, enabled: bool):
    """
    Enables or disables all time shift controls (sliders and inputs).

    Args:
        app: The main application instance.
        enabled (bool): True to enable controls, False to disable.
    """
    if "time_shift_sliders" in app.control_inputs:
        for _, widget in app.control_inputs["time_shift_sliders"].items():
            widget.setEnabled(enabled)
    if "time_shift_inputs" in app.control_inputs:
        for _, widget in app.control_inputs["time_shift_inputs"].items():
            widget.setEnabled(enabled)


def reset_time_shifts_values(app):
    """
    Resets all time shift controls to their default value (0).

    Args:
        app: The main application instance.
    """
    if "time_shift_sliders" in app.control_inputs:
        for _, widget in app.control_inputs["time_shift_sliders"].items():
            widget.setValue(0)
    if "time_shift_inputs" in app.control_inputs:
        for _, widget in app.control_inputs["time_shift_inputs"].items():
            widget.setValue(0)


def SBR_set_visible(app, visible: bool):
    """
    Sets the visibility of all SBR (Signal-to-Background Ratio) labels.

    Args:
        app: The main application instance.
        visible (bool): True to show SBR labels, False to hide.
    """
    for _, widget in app.SBR_items.items():
        if widget is not None:
            widget.setVisible(visible)


def on_show_SBR_changed(app, state: bool):
    """
    Callback for the 'Show SBR' switch.

    Args:
        app: The main application instance.
        state (bool): The new state of the switch.
    """
    app.settings.setValue(s.SETTINGS_SHOW_SBR, state)
    app.show_SBR = state
    SBR_set_visible(app, state)


def show_harmonic_selector(app, harmonics: int):
    """
    Shows and populates the harmonic selector dropdown.

    Args:
        app: The main application instance.
        harmonics (int): The number of harmonics to display.
    """
    if harmonics > 1:
        app.control_inputs[s.HARMONIC_SELECTOR].show()
        app.control_inputs[s.HARMONIC_SELECTOR_LABEL].show()
        selector_harmonics = [
            int(app.control_inputs[s.HARMONIC_SELECTOR].itemText(index))
            for index in range(app.control_inputs[s.HARMONIC_SELECTOR].count())
        ]
        if (
            len(selector_harmonics)
            != app.control_inputs[s.SETTINGS_HARMONIC].value()
            or app.acquire_read_mode == "read"
        ):
            app.control_inputs[s.HARMONIC_SELECTOR].clear()
            for i in range(harmonics):
                app.control_inputs[s.HARMONIC_SELECTOR].addItem(str(i + 1))
        app.control_inputs[s.HARMONIC_SELECTOR].setCurrentIndex(
            app.phasors_harmonic_selected - 1
        )


def hide_harmonic_selector(app):
    """
    Hides the harmonic selector dropdown and its label.

    Args:
        app: The main application instance.
    """
    app.control_inputs[s.HARMONIC_SELECTOR].hide()
    app.control_inputs[s.HARMONIC_SELECTOR_LABEL].hide()


def open_plots_config_popup(app):
    """
    Opens the plots configuration popup window.

    Args:
        app: The main application instance.
    """
    app.popup = PlotsConfigPopup(app, start_acquisition=False)
    app.popup.show()


def open_reader_popup(app):
    """
    Opens the file reader popup window.

    Args:
        app: The main application instance.
    """
    app.popup = ReaderPopup(app, tab_selected=app.tab_selected)
    app.popup.show()


def open_reader_metadata_popup(app):
    """
    Opens the file reader metadata popup window.

    Args:
        app: The main application instance.
    """
    app.popup = ReaderMetadataPopup(app, tab_selected=app.tab_selected)
    app.popup.show()


def export_data(app):
    """
    Opens a file dialog to export the currently buffered data to a .bin file.

    Args:
        app: The main application instance.
    """
    if not app.write_data:
        return
    dialog = QFileDialog()
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setNameFilter("Binary files (*.bin)")
    dialog.setDefaultSuffix("bin")
    file_name, _ = dialog.getSaveFileName(
        app,
        "Save binary file",
        "",
        "Binary files (*.bin)",
        options=QFileDialog.Option.DontUseNativeDialog,
    )
    if file_name:
        if not file_name.endswith(".bin"):
            file_name += ".bin"
        try:
            flim_labs.export_data(file_name)
        except Exception as e:
            BoxMessage.setup(
                "Error",
                "Error exporting data: " + str(e),
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )