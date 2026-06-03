"""
controls_controller.py
============================================================
Facade / controller that delegates all user-interaction callbacks and UI
state management to the dedicated sub-modules in `core/controls/`.

Sub-module responsibilities
---------------------------
core.controls.controls_tab_handlers  — tab selection logic and per-tab UI state
                                       (manages N° Replicate visibility, Laserblood-specific)
core.controls.controls_fitting           — FIT button lifecycle and fitting popup
core.controls.controls_acquisition   — start/stop, timing, channels, sync, firmware
                                       (Laserblood: LaserbloodMetadataPopup side effects,
                                        handle_pico_mode_toggle_visibility, on_replicate_change,
                                        get_selected_channels_from_settings returns list)
core.controls.controls_phasors       — quantize, resolution, harmonic, phasor plots
core.controls.controls_reference     — calibration, TAU, reference loading, deconvolution
core.controls.controls_state         — enable/disable, SBR, time shifts, harmonic selector,
                                       popups, export
"""

from core.controls.controls_tab_handlers import (
    on_tab_selected,
    _handle_spectroscopy_tab_selection,
    _handle_fitting_tab_selection,
    _handle_phasors_tab_selection,
)
from core.controls.controls_fitting import (
    fit_button_show,
    fit_button_hide,
    on_fit_btn_click,
)
from core.controls.controls_acquisition import (
    on_start_button_click,
    on_bin_width_change,
    on_time_span_change,
    on_free_running_changed,
    on_acquisition_time_change,
    on_export_data_changed,
    on_cps_threshold_change,
    on_connection_type_value_change,
    get_free_running_state,
    get_acquisition_time,
    get_current_frequency_mhz,
    get_frequency_mhz,
    on_pico_mode_changed,
    get_firmware_selected,
    is_pico_mode_active,
    handle_pico_mode_toggle_visibility,
    on_channel_selected,
    channel_selector_set_enabled,
    get_selected_channels_from_settings,
    set_selected_channels_to_settings,
    on_sync_selected,
    start_sync_in_dialog,
    update_sync_in_button,
    on_tau_change,
    on_harmonic_change,
    on_calibration_change,
    on_use_deconvolution_changed,
)
from core.controls.controls_phasors import (
    is_phasors,
    on_quantize_phasors_changed,
    on_phasors_resolution_changed,
    on_harmonic_selector_change,
    _update_phasor_plots_for_harmonic,
)
from core.controls.controls_reference import (
    on_load_reference,
    on_load_phasors_reference,
    on_load_irf_reference,
    is_reference_phasors,
    is_reference_irf,
    is_reference_birfi,
    is_phasor_ref_data,
    is_irf_ref_data,
    is_birfi_ref_data,
    is_fitting_ref_data,
)
from core.controls.controls_state import (
    controls_set_enabled,
    sync_buttons_set_enabled,
    channel_selector_set_enabled,
    top_bar_set_enabled,
    toggle_intensities_widgets_visibility,
    time_shifts_set_enabled,
    reset_time_shifts_values,
    SBR_set_visible,
    on_show_SBR_changed,
    show_harmonic_selector,
    hide_harmonic_selector,
    open_plots_config_popup,
    open_reader_popup,
    open_reader_metadata_popup,
    export_data,
)


class ControlsController:
    """
    Facade controller for all user-interaction callbacks and UI state management.
    
    Every method is a thin static wrapper that delegates to the appropriate
    `core/controls/` sub-module.
    """

    # ------------------------------------------------------------------
    # Tab selection
    # ------------------------------------------------------------------

    @staticmethod
    def on_tab_selected(app, tab_name):
        on_tab_selected(app, tab_name)

    @staticmethod
    def _handle_spectroscopy_tab_selection(app):
        _handle_spectroscopy_tab_selection(app)

    @staticmethod
    def _handle_fitting_tab_selection(app):
        _handle_fitting_tab_selection(app)

    @staticmethod
    def _handle_phasors_tab_selection(app):
        _handle_phasors_tab_selection(app)

    # ------------------------------------------------------------------
    # FIT button
    # ------------------------------------------------------------------

    @staticmethod
    def fit_button_show(app):
        fit_button_show(app)

    @staticmethod
    def fit_button_hide(app):
        fit_button_hide(app)

    @staticmethod
    def on_fit_btn_click(app):
        on_fit_btn_click(app)

    # ------------------------------------------------------------------
    # Acquisition flow & settings
    # ------------------------------------------------------------------

    @staticmethod
    def on_start_button_click(app):
        on_start_button_click(app)

    @staticmethod
    def on_bin_width_change(app, value):
        on_bin_width_change(app, value)

    @staticmethod
    def on_time_span_change(app, value):
        on_time_span_change(app, value)

    @staticmethod
    def on_free_running_changed(app, state):
        on_free_running_changed(app, state)

    @staticmethod
    def on_acquisition_time_change(app, value):
        on_acquisition_time_change(app, value)

    @staticmethod
    def on_export_data_changed(app, state):
        on_export_data_changed(app, state)

    @staticmethod
    def on_cps_threshold_change(app, value):
        on_cps_threshold_change(app, value)

    @staticmethod
    def on_connection_type_value_change(app, value):
        on_connection_type_value_change(app, value)

    @staticmethod
    def get_free_running_state(app):
        return get_free_running_state(app)

    @staticmethod
    def get_acquisition_time(app):
        return get_acquisition_time(app)

    @staticmethod
    def get_current_frequency_mhz(app):
        return get_current_frequency_mhz(app)

    @staticmethod
    def get_frequency_mhz(app):
        return get_frequency_mhz(app)

    @staticmethod
    def on_pico_mode_changed(app, enabled: bool):
        on_pico_mode_changed(app, enabled)

    @staticmethod
    def get_firmware_selected(app, frequency_mhz):
        return get_firmware_selected(app, frequency_mhz)

    # ------------------------------------------------------------------
    # Pico mode helpers (Laserblood-specific)
    # ------------------------------------------------------------------

    @staticmethod
    def is_pico_mode_active(app, selected_channels, frequency_mhz):
        """Determines whether pico mode should be active (Laserblood-specific)."""
        return is_pico_mode_active(app, selected_channels, frequency_mhz)

    @staticmethod
    def handle_pico_mode_toggle_visibility(app, selected_channels, frequency_mhz):
        """Updates pico mode switch visibility (Laserblood-specific)."""
        handle_pico_mode_toggle_visibility(app, selected_channels, frequency_mhz)

    # ------------------------------------------------------------------
    # Replicate (Laserblood-specific)
    # ------------------------------------------------------------------

    @staticmethod
    def on_replicate_change(app, value):
        """
        Callback for when the number of replicates changes.

        Args:
            app: The main application instance.
            value (int): The new number of replicates.
        """
        app.replicates = int(value)

    # ------------------------------------------------------------------
    # Channel selection
    # ------------------------------------------------------------------

    @staticmethod
    def on_channel_selected(app, checked: bool, channel: int):
        on_channel_selected(app, checked, channel)

    @staticmethod
    def channel_selector_set_enabled(app, enabled: bool):
        channel_selector_set_enabled(app, enabled)

    @staticmethod
    def get_selected_channels_from_settings(app):
        """Returns selected_channels list (Laserblood edition returns the value)."""
        return get_selected_channels_from_settings(app)

    @staticmethod
    def set_selected_channels_to_settings(app):
        set_selected_channels_to_settings(app)

    # ------------------------------------------------------------------
    # Sync mode
    # ------------------------------------------------------------------

    @staticmethod
    def on_sync_selected(app, sync: str):
        on_sync_selected(app, sync)

    @staticmethod
    def start_sync_in_dialog(app):
        start_sync_in_dialog(app)

    @staticmethod
    def update_sync_in_button(app):
        update_sync_in_button(app)

    # ------------------------------------------------------------------
    # Phasors
    # ------------------------------------------------------------------

    @staticmethod
    def on_quantize_phasors_changed(app, value):
        on_quantize_phasors_changed(app, value)

    @staticmethod
    def on_phasors_resolution_changed(app, value):
        on_phasors_resolution_changed(app, value)

    @staticmethod
    def on_harmonic_selector_change(app, value):
        on_harmonic_selector_change(app, value)

    @staticmethod
    def _update_phasor_plots_for_harmonic(app):
        _update_phasor_plots_for_harmonic(app)

    # ------------------------------------------------------------------
    # Reference & calibration
    # ------------------------------------------------------------------

    @staticmethod
    def on_tau_change(app, value):
        on_tau_change(app, value)

    @staticmethod
    def on_harmonic_change(app, value):
        on_harmonic_change(app, value)

    @staticmethod
    def on_calibration_change(app, value):
        on_calibration_change(app, value)

    @staticmethod
    def on_load_reference(app):
        on_load_reference(app)

    @staticmethod
    def on_load_phasors_reference(app):
        on_load_phasors_reference(app)

    @staticmethod
    def on_load_irf_reference(app):
        on_load_irf_reference(app)

    @staticmethod
    def on_use_deconvolution_changed(app, state):
        on_use_deconvolution_changed(app, state)

    @staticmethod
    def is_reference_phasors(app):
        return is_reference_phasors(app)

    @staticmethod
    def is_reference_irf(app):
        return is_reference_irf(app)

    @staticmethod
    def is_reference_birfi(app):
        return is_reference_birfi(app)

    @staticmethod
    def is_phasor_ref_data(reference_data):
        return is_phasor_ref_data(reference_data)

    @staticmethod
    def is_irf_ref_data(reference_data):
        return is_irf_ref_data(reference_data)

    @staticmethod
    def is_birfi_ref_data(reference_data):
        return is_birfi_ref_data(reference_data)

    @staticmethod
    def is_fitting_ref_data(reference_data):
        return is_fitting_ref_data(reference_data)

    # ------------------------------------------------------------------
    # UI state management
    # ------------------------------------------------------------------

    @staticmethod
    def controls_set_enabled(app, enabled: bool):
        controls_set_enabled(app, enabled)

    @staticmethod
    def sync_buttons_set_enabled(app, enabled: bool):
        sync_buttons_set_enabled(app, enabled)

    @staticmethod
    def top_bar_set_enabled(app, enabled: bool):
        top_bar_set_enabled(app, enabled)

    @staticmethod
    def toggle_intensities_widgets_visibility(app):
        toggle_intensities_widgets_visibility(app)

    @staticmethod
    def time_shifts_set_enabled(app, enabled: bool):
        time_shifts_set_enabled(app, enabled)

    @staticmethod
    def reset_time_shifts_values(app):
        reset_time_shifts_values(app)

    @staticmethod
    def SBR_set_visible(app, visible: bool):
        SBR_set_visible(app, visible)

    @staticmethod
    def on_show_SBR_changed(app, state):
        on_show_SBR_changed(app, state)

    @staticmethod
    def show_harmonic_selector(app, harmonics: int):
        show_harmonic_selector(app, harmonics)

    @staticmethod
    def hide_harmonic_selector(app):
        hide_harmonic_selector(app)

    @staticmethod
    def is_phasors(app):
        return is_phasors(app)

    # ------------------------------------------------------------------
    # Popups & export
    # ------------------------------------------------------------------

    @staticmethod
    def open_plots_config_popup(app):
        open_plots_config_popup(app)

    @staticmethod
    def open_laserblood_metadata_popup(app):
        """
        Opens the Laserblood metadata popup window (Laserblood-specific).

        Args:
            app: The main application instance.
        """
        from components.laserblood_metadata_popup import LaserbloodMetadataPopup
        from PyQt6.QtCore import Qt

        LaserbloodMetadataPopup.set_FPGA_firmware(app)
        app.popup = LaserbloodMetadataPopup(app, start_acquisition=False)
        app.popup.setWindowState(Qt.WindowState.WindowMaximized)
        app.popup.show()

    @staticmethod
    def open_reader_popup(app):
        open_reader_popup(app)

    @staticmethod
    def open_reader_metadata_popup(app):
        open_reader_metadata_popup(app)

    @staticmethod
    def export_data(app):
        export_data(app)