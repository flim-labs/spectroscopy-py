"""
controls_tab_handlers.py
========================
Handles tab switching logic and per-tab UI state updates:
- _handle_spectroscopy_tab_selection
- _handle_fitting_tab_selection
- _handle_phasors_tab_selection
- on_tab_selected
"""

import json

from utils.layout_utilities import hide_layout, show_layout
from components.read_data import ReadDataControls
from core.phasors_controller import PhasorsController
from core.plots_controller import PlotsController
import settings.settings as s


def _handle_spectroscopy_tab_selection(app):
    """
    Handles UI updates when the Spectroscopy tab is selected.

    Args:
        app: The main application instance.
    """
    app.widgets[s.TIME_TAGGER_WIDGET].setVisible(app.write_data_gui)
    from core.controls.controls_fitting import fit_button_hide
    from core.controls.controls_state import hide_harmonic_selector

    fit_button_hide(app)
    hide_harmonic_selector(app)
    hide_layout(app.control_inputs["phasors_resolution_container"])
    hide_layout(app.control_inputs["quantize_phasors_container"])
    hide_layout(app.control_inputs["use_deconv_container"])
    hide_layout(app.widgets[s.REFERENCE_INFO_BANNER])
    app.control_inputs["tau_label"].hide()
    app.control_inputs["tau"].hide()
    app.control_inputs[s.SETTINGS_HARMONIC].hide()
    app.control_inputs[s.SETTINGS_HARMONIC_LABEL].hide()
    app.control_inputs["calibration"].show()
    app.control_inputs["calibration_label"].show()
    current_tau = app.settings.value(s.SETTINGS_TAU_NS, "0")
    app.control_inputs["tau"].setValue(float(current_tau))
    from core.controls.controls_acquisition import on_tau_change, on_calibration_change
    on_tau_change(app, float(current_tau))
    current_calibration = app.settings.value(
        s.SETTINGS_CALIBRATION_TYPE, s.DEFAULT_SETTINGS_CALIBRATION_TYPE
    )
    on_calibration_change(app, int(current_calibration))
    app.control_inputs[s.LOAD_REF_BTN].hide()
    channels_grid = app.widgets[s.CHANNELS_GRID]
    plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
    if plot_config_btn is not None:
        plot_config_btn.setVisible(True)


def _handle_fitting_tab_selection(app):
    """
    Handles UI updates when the Fitting tab is selected.

    Args:
        app: The main application instance.
    """
    from core.ui_controller import UIController
    from core.controls.controls_fitting import fit_button_show, fit_button_hide
    from core.controls.controls_state import hide_harmonic_selector

    app.widgets[s.TIME_TAGGER_WIDGET].setVisible(app.write_data_gui)
    if ReadDataControls.fit_button_enabled(app):
        fit_button_show(app)
    else:
        fit_button_hide(app)

    if UIController.show_ref_info_banner(app) == False:
        hide_layout(app.widgets[s.REFERENCE_INFO_BANNER])
    else:
        show_layout(app.widgets[s.REFERENCE_INFO_BANNER])
        UIController.update_reference_info_banner_label(app)

    if app.acquire_read_mode == "read":
        hide_layout(app.control_inputs["use_deconv_container"])
        app.control_inputs[s.LOAD_REF_BTN].hide()
    else:
        show_layout(app.control_inputs["use_deconv_container"])
        if app.use_deconvolution:
            app.control_inputs[s.LOAD_REF_BTN].setText("LOAD IRF")
            app.control_inputs[s.LOAD_REF_BTN].show()
        else:
            app.control_inputs[s.LOAD_REF_BTN].hide()
    hide_harmonic_selector(app)
    hide_layout(app.control_inputs["phasors_resolution_container"])
    hide_layout(app.control_inputs["quantize_phasors_container"])
    app.control_inputs["tau_label"].hide()
    app.control_inputs["tau"].hide()
    app.control_inputs["calibration"].hide()
    app.control_inputs["calibration_label"].hide()
    app.control_inputs[s.SETTINGS_HARMONIC].hide()
    app.control_inputs[s.SETTINGS_HARMONIC_LABEL].hide()
    channels_grid = app.widgets[s.CHANNELS_GRID]
    plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
    if plot_config_btn is not None:
        plot_config_btn.setVisible(True)


def _handle_phasors_tab_selection(app):
    """
    Handles UI updates when the Phasors tab is selected.

    Args:
        app: The main application instance.
    """
    from core.ui_controller import UIController
    from core.controls.controls_fitting import fit_button_hide
    from core.controls.controls_state import show_harmonic_selector
    from core.controls.controls_phasors import on_quantize_phasors_changed, _update_phasor_plots_for_harmonic

    app.widgets[s.TIME_TAGGER_WIDGET].setVisible(False)
    fit_button_hide(app)
    hide_layout(app.control_inputs["use_deconv_container"])

    if app.acquire_read_mode == "read":
        app.control_inputs[s.LOAD_REF_BTN].hide()
        hide_layout(app.control_inputs["phasors_resolution_container"])
        hide_layout(app.control_inputs["quantize_phasors_container"])
        hide_layout(app.widgets[s.REFERENCE_INFO_BANNER])
        on_quantize_phasors_changed(app, False)
        app.settings.setValue(s.SETTINGS_QUANTIZE_PHASORS, False)
    else:
        app.control_inputs[s.LOAD_REF_BTN].setText("LOAD REFERENCE")
        app.control_inputs[s.LOAD_REF_BTN].show()
        UIController.update_reference_info_banner_label(app)
        show_layout(app.control_inputs["quantize_phasors_container"])
        show_layout(app.widgets[s.REFERENCE_INFO_BANNER])
        if app.quantized_phasors:
            show_layout(app.control_inputs["phasors_resolution_container"])

    app.control_inputs["tau_label"].hide()
    app.control_inputs["tau"].hide()
    app.control_inputs["calibration"].hide()
    app.control_inputs["calibration_label"].hide()
    app.control_inputs[s.SETTINGS_HARMONIC].hide()
    app.control_inputs[s.SETTINGS_HARMONIC_LABEL].hide()

    PhasorsController.initialize_phasor_feature(app)
    _update_phasor_plots_for_harmonic(app)

    if app.harmonic_selector_shown or (
        app.acquire_read_mode == "read" and hasattr(app, "loaded_phasors_harmonics")
    ):
        harmonics_count = getattr(
            app,
            "loaded_phasors_harmonics",
            app.control_inputs[s.SETTINGS_HARMONIC].value(),
        )
        show_harmonic_selector(app, harmonics_count)

    channels_grid = app.widgets[s.CHANNELS_GRID]
    plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
    if plot_config_btn is not None:
        plot_config_btn.setVisible(False)


def on_tab_selected(app, tab_name):
    """
    Handles the logic for switching between the main application tabs.

    Updates app state, clears and regenerates plots, and calls the
    appropriate helper to adjust the UI for the selected tab.

    Args:
        app: The main application instance.
        tab_name (str): The name of the newly selected tab.
    """
    from core.controls.controls_state import toggle_intensities_widgets_visibility

    app.control_inputs[app.tab_selected].setChecked(False)
    app.tab_selected = tab_name
    app.control_inputs[app.tab_selected].setChecked(True)

    # Close fitting popup when changing tabs
    if hasattr(app, "fitting_config_popup") and app.fitting_config_popup is not None:
        try:
            app.fitting_config_popup.close()
            app.fitting_config_popup.deleteLater()
            app.fitting_config_popup = None
        except Exception:
            pass

    bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(app)
    app.control_inputs["bin_metadata_button"].setVisible(bin_metadata_btn_visible)
    app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
        bin_metadata_btn_visible and app.tab_selected != s.TAB_FITTING
    )
    if tab_name != s.TAB_PHASORS or (
        tab_name == s.TAB_PHASORS and app.acquire_read_mode == "acquire"
    ):
        channels = app.selected_channels or []
        app.plots_to_show = channels[:4]
        app.settings.setValue(s.SETTINGS_PLOTS_TO_SHOW, json.dumps(app.plots_to_show))
    else:
        app.plots_to_show = [0]
        app.settings.setValue(s.SETTINGS_PLOTS_TO_SHOW, json.dumps(app.plots_to_show))

    if app.acquire_read_mode == "acquire":
        PlotsController.clear_plots(app, deep_clear=False)
        PlotsController.generate_plots(app)
        toggle_intensities_widgets_visibility(app)
    else:
        ReadDataControls.plot_data_on_tab_change(app)

    if tab_name == s.TAB_SPECTROSCOPY:
        _handle_spectroscopy_tab_selection(app)
    elif tab_name == s.TAB_FITTING:
        _handle_fitting_tab_selection(app)
    elif tab_name == s.TAB_PHASORS:
        _handle_phasors_tab_selection(app)