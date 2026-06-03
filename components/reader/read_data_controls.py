"""
read_data_controls.py
=====================
ReadDataControls — static methods for managing UI controls in read mode:
- handle_widgets_visibility
- handle_plots_config
- plot_data_on_tab_change
- read_bin_metadata_enabled
- fit_button_enabled
"""

import settings.settings as s
from utils.layout_utilities import hide_layout, show_layout


class ReadDataControls:
    """A collection of static methods for managing UI controls in read mode."""

    @staticmethod
    def handle_widgets_visibility(app, read_mode):
        """Shows or hides UI controls based on whether the app is in read mode.

        Args:
            app: The main application instance.
            read_mode (bool): True if the application is in read mode.
        """
        from core.controls_controller import ControlsController
        from core.ui_controller import UIController

        if not read_mode:
            ControlsController.fit_button_hide(app)
        else:
            if ReadDataControls.fit_button_enabled(app):
                ControlsController.fit_button_show(app)

        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(app)
        app.control_inputs["bin_metadata_button"].setVisible(bin_metadata_btn_visible)
        app.control_inputs["start_button"].setVisible(not read_mode)
        app.control_inputs["read_bin_button"].setVisible(read_mode)

        # Export button: shown in read mode when files are loaded; hidden for fitting tab in non-read mode
        if read_mode:
            app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
                bin_metadata_btn_visible
            )
        else:
            app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
                bin_metadata_btn_visible and app.tab_selected != s.TAB_FITTING
            )

        # Fitting tab specifics
        if app.tab_selected == s.TAB_FITTING:
            app.control_inputs[s.SETTINGS_REPLICATES].setVisible(not read_mode)
            app.control_inputs["replicates_label"].setVisible(not read_mode)
            app.control_inputs[s.LOAD_REF_BTN].setText("LOAD IRF")
            app.control_inputs[s.LOAD_REF_BTN].setVisible(
                not read_mode and app.use_deconvolution
            )
            if read_mode:
                app.control_inputs[s.LOAD_REF_BTN].hide()
                hide_layout(app.control_inputs["use_deconv_container"])
                if UIController.show_ref_info_banner(app) == False:
                    hide_layout(app.widgets[s.REFERENCE_INFO_BANNER])
            else:
                show_layout(app.control_inputs["use_deconv_container"])
                if UIController.show_ref_info_banner(app):
                    UIController.update_reference_info_banner_label(app)
                    show_layout(app.widgets[s.REFERENCE_INFO_BANNER])

        app.widgets[s.TOP_COLLAPSIBLE_WIDGET].setVisible(not read_mode)
        app.widgets["collapse_button"].setVisible(not read_mode)
        app.control_inputs[s.SETTINGS_BIN_WIDTH].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_ACQUISITION_TIME].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_FREE_RUNNING].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_CALIBRATION_TYPE].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_CPS_THRESHOLD].setEnabled(not read_mode)
        app.control_inputs["tau"].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_TIME_SPAN].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_HARMONIC].setEnabled(not read_mode)

        # Phasors tab specifics
        if app.tab_selected == s.TAB_PHASORS:
            app.control_inputs[s.LOAD_REF_BTN].setText("LOAD REFERENCE")
            app.control_inputs[s.LOAD_REF_BTN].setVisible(not read_mode)
            if read_mode:
                app.control_inputs[s.LOAD_REF_BTN].hide()
                hide_layout(app.control_inputs["phasors_resolution_container"])
                hide_layout(app.control_inputs["quantize_phasors_container"])
                ControlsController.on_quantize_phasors_changed(app, False)
                app.settings.setValue(s.SETTINGS_QUANTIZE_PHASORS, False)
                if UIController.show_ref_info_banner(app) == False:
                    hide_layout(app.widgets[s.REFERENCE_INFO_BANNER])
            else:
                show_layout(app.control_inputs["quantize_phasors_container"])
                if app.quantized_phasors:
                    show_layout(app.control_inputs["phasors_resolution_container"])
                if UIController.show_ref_info_banner(app):
                    UIController.update_reference_info_banner_label(app)
                    show_layout(app.widgets[s.REFERENCE_INFO_BANNER])

    @staticmethod
    def handle_plots_config(app, file_type):
        """Configures channel selection checkboxes based on loaded file metadata.

        Args:
            app: The main application instance.
            file_type (str): The data type ('spectroscopy', 'phasors', etc.).
        """
        if file_type != "phasors":
            file_metadata = app.reader_data[file_type].get("metadata", {})
            if file_metadata.get("channels"):
                app.selected_channels = sorted(file_metadata["channels"])
                app.plots_to_show = app.reader_data[file_type].get("plots", [])
                for i, checkbox in enumerate(app.channel_checkboxes):
                    checkbox.set_checked(i in app.selected_channels)

    @staticmethod
    def plot_data_on_tab_change(app):
        """Handles UI updates and data plotting when the main tab changes in read mode.

        Args:
            app: The main application instance.
        """
        from core.plots_controller import PlotsController
        from core.controls_controller import ControlsController
        from components.reader.read_data_utils import get_data_type, get_frequency_mhz
        from components.reader.read_data_plot import plot_data

        file_type = get_data_type(app.tab_selected)
        if app.acquire_read_mode == "read":
            ReadDataControls.handle_plots_config(app, file_type)
            PlotsController.clear_plots(app)
            freq = get_frequency_mhz(app)
            PlotsController.generate_plots(app, freq)
            ControlsController.toggle_intensities_widgets_visibility(app)
            plot_data(app)
            new_freq = get_frequency_mhz(app)
            if freq == 0 and new_freq > 0:
                PlotsController.clear_plots(app)
                PlotsController.generate_plots(app, new_freq)
                ControlsController.toggle_intensities_widgets_visibility(app)
                plot_data(app)

    @staticmethod
    def read_bin_metadata_enabled(app):
        """Determines if the 'view metadata' button should be enabled.

        Args:
            app: The main application instance.

        Returns:
            bool: True if the button should be enabled, False otherwise.
        """
        from components.reader.read_data_utils import get_data_type

        data_type = get_data_type(app.tab_selected)
        metadata = app.reader_data[data_type]["metadata"]
        if data_type != "phasors":
            return not (metadata == {}) and app.acquire_read_mode == "read"
        else:
            phasors_files = app.reader_data[data_type]["files"]["phasors"]
            spectroscopy_files = app.reader_data[data_type]["files"]["spectroscopy"]
            has_phasors = (
                isinstance(phasors_files, list) and len(phasors_files) > 0
            ) or (isinstance(phasors_files, str) and len(phasors_files.strip()) > 0)
            has_spectroscopy = (
                isinstance(spectroscopy_files, list) and len(spectroscopy_files) > 0
            ) or (
                isinstance(spectroscopy_files, str)
                and len(spectroscopy_files.strip()) > 0
            )
            return (has_phasors or has_spectroscopy) and app.acquire_read_mode == "read"

    @staticmethod
    def fit_button_enabled(app):
        """Determines if the 'Fit Data' button should be enabled.

        Args:
            app: The main application instance.

        Returns:
            bool: True if the button should be enabled, False otherwise.
        """
        tab_selected_fitting = app.tab_selected == s.TAB_FITTING
        read_mode = app.acquire_read_mode == "read"
        fitting_files = app.reader_data["fitting"]["files"]["fitting"]
        spectroscopy_file = app.reader_data["fitting"]["files"]["spectroscopy"]
        fitting_file_exists = (
            isinstance(fitting_files, list) and len(fitting_files) > 0
        ) or (isinstance(fitting_files, str) and len(fitting_files.strip()) > 0)
        spectroscopy_file_exists = (
            isinstance(spectroscopy_file, list) and len(spectroscopy_file) > 0
        ) or (isinstance(spectroscopy_file, str) and len(spectroscopy_file.strip()) > 0)
        return (
            tab_selected_fitting
            and read_mode
            and (fitting_file_exists or spectroscopy_file_exists)
        )
