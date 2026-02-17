from functools import partial
import json
import flim_labs
from components.box_message import BoxMessage
from components.fitting_config_popup import FittingDecayConfigPopup
from utils.gui_styles import GUIStyles
from utils.helpers import is_frequency_near_supported_pico_modes, mhz_to_ns
from utils.layout_utilities import hide_layout, show_layout
from components.plots_config import PlotsConfigPopup
from components.read_data import (
    ReadData,
    ReadDataControls,
    ReaderMetadataPopup,
    ReaderPopup,
)
from components.sync_in_popup import SyncInDialog
from core.acquisition_controller import AcquisitionController
from core.phasors_controller import PhasorsController
from core.plots_controller import PlotsController
import settings.settings as s


from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QMessageBox,
    QFileDialog,
)


class ControlsController:
    """
    A controller class for handling user interactions with UI controls.

    This class provides static methods that act as callbacks for various UI
    events, such as button clicks and value changes. It encapsulates the logic
    for updating the application state and triggering actions based on user input,
    serving as the bridge between the UI and the core application logic.
    """

    @staticmethod
    def on_start_button_click(app):
        """
        Handles the click event of the main START/STOP button.

        Starts the acquisition if the system is stopped, or stops it if it's
        currently running.

        Args:
            app: The main application instance.
        """
        if app.mode == s.MODE_STOPPED:
            app.acquisition_stopped = False
            if not (ControlsController.is_phasors(app)):
                app.harmonic_selector_shown = False
            AcquisitionController.begin_spectroscopy_experiment(app)
        elif app.mode == s.MODE_RUNNING:
            app.acquisition_stopped = True
            AcquisitionController.stop_spectroscopy_experiment(app)

    @staticmethod
    def _handle_spectroscopy_tab_selection(app):
        """
        Handles UI updates when the Spectroscopy tab is selected.

        This private helper method configures the visibility and state of
        various controls specific to the spectroscopy view.

        Args:
            app: The main application instance.
        """
        app.widgets[s.TIME_TAGGER_WIDGET].setVisible(app.write_data_gui)
        ControlsController.fit_button_hide(app)
        ControlsController.hide_harmonic_selector(app)
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
        ControlsController.on_tau_change(app, float(current_tau))
        current_calibration = app.settings.value(
            s.SETTINGS_CALIBRATION_TYPE, s.DEFAULT_SETTINGS_CALIBRATION_TYPE
        )
        ControlsController.on_calibration_change(app, int(current_calibration))
        app.control_inputs[s.LOAD_REF_BTN].hide()
        channels_grid = app.widgets[s.CHANNELS_GRID]
        plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
        if plot_config_btn is not None:
            plot_config_btn.setVisible(True)

    @staticmethod
    def _handle_fitting_tab_selection(app):
        """
        Handles UI updates when the Fitting tab is selected.

        This private helper method configures the visibility and state of
        controls relevant to the fitting view.

        Args:
            app: The main application instance.
        """
        from core.ui_controller import UIController

        app.widgets[s.TIME_TAGGER_WIDGET].setVisible(app.write_data_gui)
        if ReadDataControls.fit_button_enabled(app):
            ControlsController.fit_button_show(app)
        else:
            ControlsController.fit_button_hide(app)

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
        ControlsController.hide_harmonic_selector(app)
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

        This private helper method configures the visibility and state of
        controls specific to the phasor analysis view.

        Args:
            app: The main application instance.
        """
        from core.ui_controller import UIController

        app.widgets[s.TIME_TAGGER_WIDGET].setVisible(False)
        ControlsController.fit_button_hide(app)
        hide_layout(app.control_inputs["use_deconv_container"])

        if app.acquire_read_mode == "read":
            app.control_inputs[s.LOAD_REF_BTN].hide()
            hide_layout(app.control_inputs["phasors_resolution_container"])
            hide_layout(app.control_inputs["quantize_phasors_container"])
            hide_layout(app.widgets[s.REFERENCE_INFO_BANNER])
            ControlsController.on_quantize_phasors_changed(app, False)
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
        ControlsController._update_phasor_plots_for_harmonic(app)

        # Show harmonic selector if needed (for both acquire and read modes)
        # In read mode with loaded files, always show if we have loaded_phasors_harmonics
        if app.harmonic_selector_shown or (
            app.acquire_read_mode == "read" and hasattr(app, "loaded_phasors_harmonics")
        ):
            # Use loaded_phasors_harmonics if available (from loaded file), otherwise use settings value
            harmonics_count = getattr(
                app,
                "loaded_phasors_harmonics",
                app.control_inputs[s.SETTINGS_HARMONIC].value(),
            )
            ControlsController.show_harmonic_selector(app, harmonics_count)

        channels_grid = app.widgets[s.CHANNELS_GRID]
        plot_config_btn = channels_grid.itemAt(channels_grid.count() - 1).widget()
        if plot_config_btn is not None:
            plot_config_btn.setVisible(False)

    @staticmethod
    def on_tab_selected(app, tab_name):
        """
        Handles the logic for switching between the main application tabs.

        It updates the application state, clears and regenerates plots, and
        calls the appropriate helper method to adjust the UI for the selected tab.

        Args:
            app: The main application instance.
            tab_name (str): The name of the newly selected tab.
        """
        app.control_inputs[app.tab_selected].setChecked(False)
        app.tab_selected = tab_name
        app.control_inputs[app.tab_selected].setChecked(True)

        # Close fitting popup when changing tabs
        if (
            hasattr(app, "fitting_config_popup")
            and app.fitting_config_popup is not None
        ):
            try:
                app.fitting_config_popup.close()
                app.fitting_config_popup.deleteLater()
                app.fitting_config_popup = None
            except:
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
            app.settings.setValue(
                s.SETTINGS_PLOTS_TO_SHOW, json.dumps(app.plots_to_show)
            )
        else:
            app.plots_to_show = [0]
            app.settings.setValue(
                s.SETTINGS_PLOTS_TO_SHOW, json.dumps(app.plots_to_show)
            )

        if app.acquire_read_mode == "acquire":
            PlotsController.clear_plots(app, deep_clear=False)
            PlotsController.generate_plots(app)
            ControlsController.toggle_intensities_widgets_visibility(app)
        else:
            ReadDataControls.plot_data_on_tab_change(app)

        if tab_name == s.TAB_SPECTROSCOPY:
            ControlsController._handle_spectroscopy_tab_selection(app)
        elif tab_name == s.TAB_FITTING:
            ControlsController._handle_fitting_tab_selection(app)
        elif tab_name == s.TAB_PHASORS:
            ControlsController._handle_phasors_tab_selection(app)

    @staticmethod
    def fit_button_show(app):
        """
        Dynamically creates and displays the 'FIT' button in its placeholder.

        Args:
            app: The main application instance.
        """
        if s.FIT_BTN not in app.control_inputs:
            app.control_inputs[s.FIT_BTN] = QPushButton("FIT")
            app.control_inputs[s.FIT_BTN].setFlat(True)
            app.control_inputs[s.FIT_BTN].setFixedHeight(55)
            app.control_inputs[s.FIT_BTN].setCursor(Qt.CursorShape.PointingHandCursor)
            app.control_inputs[s.FIT_BTN].clicked.connect(
                partial(ControlsController.on_fit_btn_click, app)
            )
            app.control_inputs[s.FIT_BTN].setStyleSheet(
                """
            QPushButton {
                background-color: #1E90FF;
                color: white;
                width: 60px;
                border-radius: 5px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 16px;
            }
            """
            )
            app.control_inputs[s.FIT_BTN_PLACEHOLDER].layout().addWidget(
                app.control_inputs[s.FIT_BTN]
            )

    @staticmethod
    def fit_button_hide(app):
        """
        Dynamically removes and hides the 'FIT' button from its placeholder.

        Args:
            app: The main application instance.
        """
        if s.FIT_BTN in app.control_inputs:
            app.control_inputs[s.FIT_BTN_PLACEHOLDER].layout().removeWidget(
                app.control_inputs[s.FIT_BTN]
            )
            app.control_inputs[s.FIT_BTN].deleteLater()
            del app.control_inputs[s.FIT_BTN]
            app.control_inputs[s.FIT_BTN_PLACEHOLDER].layout().setContentsMargins(
                0, 0, 0, 0
            )

    @staticmethod
    def on_fit_btn_click(app):
        """
        Handles the 'FIT' button click event.

        It gathers the necessary data from the current state (either from a live
        acquisition or a loaded file) and opens the fitting configuration popup.

        Args:
            app: The main application instance.
        """
        from core.acquisition_controller import AcquisitionController
        from core.fitting_controller import FittingController

        data = []
        time_shift = 0
        frequency_mhz = ControlsController.get_frequency_mhz(app)
        laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0

        preloaded_fitting_results = ReadData.preloaded_fitting_data(app)
        has_multi_file_fitting = preloaded_fitting_results and any(
            "file_index" in r for r in preloaded_fitting_results if "error" not in r
        )

        if app.acquire_read_mode == "read":
            display_channel = app.plots_to_show[0] if app.plots_to_show else 0
            time_shift = 0 if display_channel not in app.time_shifts else app.time_shifts[display_channel]

            if app.reader_data["fitting"]["data"]["spectroscopy_data"]:

                if has_multi_file_fitting:
                    # Multi-file comparison: create single plot entry regardless of selected channels
                    active_channels = ReadData.get_fitting_active_channels(app)
                    data.append(
                        {
                            "x": [0],
                            "y": [0],
                            "time_shift": time_shift,
                            "title": "Multi-File Comparison",
                            "channel_index": 0,
                        }
                    )
                else:
                    # Check if we have multi-file spectroscopy data
                    spectroscopy_data = app.reader_data["fitting"]["data"][
                        "spectroscopy_data"
                    ]
                    has_files_data = (
                        "files_data" in spectroscopy_data
                        and len(spectroscopy_data.get("files_data", [])) > 0
                    )

                    if has_files_data:
                        # Use get_spectroscopy_data_to_fit whenever files_data exists
                        data = ReadData.get_spectroscopy_data_to_fit(app)
                        # Keep the time_shift calculated above (don't reset to 0)
                    else:
                        # No files_data: use acquired_spectroscopy_data_to_fit
                        data, time_shift = (
                            AcquisitionController.acquired_spectroscopy_data_to_fit(
                                app, read=True
                            )
                        )

                    if len(data) > 0 and "file_index" not in data[0]:
                        import os

                        file_name = "Single File"
                        if hasattr(app, "reader_data") and app.reader_data:
                            if "fitting" in app.reader_data:
                                if "files" in app.reader_data["fitting"]:
                                    fitting_files = app.reader_data["fitting"]["files"]

                                    # files is a dict with 'spectroscopy' key containing list of paths
                                    if (
                                        isinstance(fitting_files, dict)
                                        and "spectroscopy" in fitting_files
                                    ):
                                        spectroscopy_files = fitting_files[
                                            "spectroscopy"
                                        ]
                                        if (
                                            isinstance(spectroscopy_files, list)
                                            and len(spectroscopy_files) > 0
                                        ):
                                            file_name = os.path.basename(
                                                spectroscopy_files[0]
                                            )
                        for entry in data:
                            entry["file_index"] = 0
                            entry["file_name"] = file_name
            else:
                # In FITTING READ mode without spectroscopy data, create single plot
                from utils.channel_name_utils import get_channel_name

                active_channels = ReadData.get_fitting_active_channels(app)

                # Create only one plot entry (will show fitting results for all channels averaged)
                if len(active_channels) > 1:
                    title = f"Average of {len(active_channels)} channel(s)"
                elif len(active_channels) > 0:
                    title = get_channel_name(active_channels[0], app.channel_names)
                else:
                    title = "No data"

                data.append(
                    {
                        "x": [0],
                        "y": [0],
                        "time_shift": time_shift,
                        "title": title,
                        "channel_index": 0,
                    }
                )
        else:
            data, time_shift = AcquisitionController.acquired_spectroscopy_data_to_fit(
                app, read=False
            )
        for i, d in enumerate(data):
            has_file_info = "file_index" in d
        # Determine read_mode based on app.acquire_read_mode, not just preloaded_fitting
        read_mode = app.acquire_read_mode == "read"

        # Close existing popup if it exists
        if (
            hasattr(app, "fitting_config_popup")
            and app.fitting_config_popup is not None
        ):
            try:
                app.fitting_config_popup.close()
                app.fitting_config_popup.deleteLater()
                app.fitting_config_popup = None
            except Exception as e:
                pass

        # Extract IRFs from reference file
        irfs = []
        irfs_tau_ns = None
        if app.irf_reference_file is not None:
            if (
                "ref_type" in app.birfi_reference_data
                and app.birfi_reference_data["ref_type"] == "birfi"
            ):
                if "irfs" in app.birfi_reference_data:
                    irfs = app.birfi_reference_data["irfs"]
                if "tau_ns" in app.birfi_reference_data:
                    irfs_tau_ns = app.birfi_reference_data["tau_ns"]
            if (
                "ref_type" in app.irf_reference_data
                and app.irf_reference_data["ref_type"] == "irf"
            ):
                if "irfs" in app.irf_reference_data:
                    irfs = app.irf_reference_data["irfs"]
      
        deconvolved_signals = FittingController.deconvolve_signals(
            app, [d for d in data], irfs, laser_period_ns
        )

        app.fitting_config_popup = FittingDecayConfigPopup(
            app,
            data=deconvolved_signals if len(deconvolved_signals) > 0 else data,
            read_mode=read_mode,
            preloaded_fitting=preloaded_fitting_results,
            save_plot_img=app.acquire_read_mode == "read",
            y_data_shift=time_shift,
            laser_period_ns=laser_period_ns,
            use_deconvolution=app.use_deconvolution
            and app.acquire_read_mode != "read"
            and len(irfs) > 0,
            irfs=irfs,
            raw_signals=data,
            irfs_tau_ns=irfs_tau_ns,
        )
        app.fitting_config_popup.show()

    @staticmethod
    def on_tau_change(app, value):
        """
        Callback for when the TAU value changes. Saves the new value to settings.

        Args:
            app: The main application instance.
            value (float): The new TAU value in nanoseconds.
        """
        app.settings.setValue(s.SETTINGS_TAU_NS, value)

    @staticmethod
    def on_harmonic_change(app, value):
        """
        Callback for when the harmonic number changes. Saves the value.

        Args:
            app: The main application instance.
            value (int): The new harmonic number.
        """
        app.settings.setValue(s.SETTINGS_HARMONIC, value)

    @staticmethod
    def on_load_reference(app):
        from core.ui_controller import UIController

        """
        Opens a file dialog to allow the user to select a phasor or IRF reference file.

        Args:
            app: The main application instance.
        """
        if app.tab_selected == s.TAB_PHASORS:
            ControlsController.on_load_phasors_reference(app)
        if app.tab_selected == s.TAB_FITTING:
            ControlsController.on_load_irf_reference(app)
        UIController.update_reference_info_banner_label(app)

    @staticmethod
    def on_load_phasors_reference(app):
        dialog = QFileDialog()
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        # extension supported: .phasors_reference.json
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

    @staticmethod
    def on_load_irf_reference(app):
        from core.fitting_controller import FittingController

        dialog = QFileDialog()
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        # extension supported: .irf_reference.json  / .birfi_reference.json
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

    @staticmethod
    def get_free_running_state(app):
        """
        Gets the current state of the 'Free running' mode switch.

        Args:
            app: The main application instance.

        Returns:
            bool: True if free running mode is enabled, False otherwise.
        """
        return app.control_inputs[s.SETTINGS_FREE_RUNNING].isChecked()

    @staticmethod
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

    @staticmethod
    def on_cps_threshold_change(app, value):
        """
        Callback for when the pile-up CPS threshold changes.

        Args:
            app: The main application instance.
            value (int): The new CPS threshold.
        """
        app.settings.setValue(s.SETTINGS_CPS_THRESHOLD, value)

    @staticmethod
    def on_time_span_change(app, value):
        """
        Callback for when the intensity plot time span changes.

        Args:
            app: The main application instance.
            value (int): The new time span in seconds.
        """
        app.settings.setValue(s.SETTINGS_TIME_SPAN, value)

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def on_connection_type_value_change(app, value):
        """
        Callback for when the connection type (USB/SMA) changes.

        Args:
            app: The main application instance.
            value (int): The index of the selected connection type.
        """
        app.settings.setValue(s.SETTINGS_CONNECTION_TYPE, value)

    @staticmethod
    def on_quantize_phasors_changed(app, value):
        """
        Callback for the 'Quantize Phasors' switch.

        Args:
            app: The main application instance.
            value (bool): The new state of the switch.
        """
        PhasorsController.clear_phasors_points(app)
        harmonic_value = int(app.control_inputs[s.HARMONIC_SELECTOR].currentText())
        app.quantized_phasors = value
        app.settings.setValue(s.SETTINGS_QUANTIZE_PHASORS, value)
        container = app.control_inputs["phasors_resolution_container"]
        if value:
            show_layout(container)
            bins = int(s.PHASORS_RESOLUTIONS[app.phasors_resolution])
            PhasorsController.quantize_phasors(app, harmonic_value, bins)
        else:
            hide_layout(container)
            for channel_index in app.plots_to_show:
                if channel_index in app.quantization_images:
                    widget = app.phasors_widgets[channel_index]
                    widget.removeItem(app.quantization_images[channel_index])
                    del app.quantization_images[channel_index]
                if channel_index in app.phasors_colorbars:
                    widget.removeItem(app.phasors_colorbars[channel_index])
                    del app.phasors_colorbars[channel_index]

            # In phasors read mode, points are ONLY drawn by plot_phasors_data
            import settings.settings as settings

            is_phasors_read_mode = (
                app.tab_selected == settings.TAB_PHASORS
                and app.acquire_read_mode == "read"
            )

            # Only redraw in acquisition mode - never in phasors read mode
            if not is_phasors_read_mode and len(app.plots_to_show) <= len(
                app.all_phasors_points
            ):
                for channel_index in app.plots_to_show:
                    points = app.all_phasors_points[channel_index][harmonic_value]
                    PhasorsController.draw_points_in_phasors(
                        app, channel_index, harmonic_value, points
                    )

    @staticmethod
    def on_phasors_resolution_changed(app, value):
        """
        Callback for when the phasor quantization resolution changes.

        Args:
            app: The main application instance.
            value (int): The index of the selected resolution.
        """
        app.phasors_resolution = int(value)
        harmonic_value = int(app.control_inputs[s.HARMONIC_SELECTOR].currentText())
        app.settings.setValue(s.SETTINGS_PHASORS_RESOLUTION, value)
        PhasorsController.quantize_phasors(
            app,
            harmonic_value,
            bins=int(s.PHASORS_RESOLUTIONS[app.phasors_resolution]),
        )

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def on_use_deconvolution_changed(app, state):
        """
        Callback for the 'Use deconvolution' switch.

        Args:
            app: The main application instance.
            state (bool): The new state of the switch.
        """
        app.settings.setValue(s.SETTINGS_USE_DECONVOLUTION, state)
        app.use_deconvolution = state
        if state:
            show_layout(app.widgets[s.REFERENCE_INFO_BANNER])
            app.control_inputs[s.LOAD_REF_BTN].setText("LOAD IRF")
            app.control_inputs[s.LOAD_REF_BTN].show()
        else:
            hide_layout(app.widgets[s.REFERENCE_INFO_BANNER])
            app.control_inputs[s.LOAD_REF_BTN].hide()

    @staticmethod
    def on_show_SBR_changed(app, state):
        """
        Callback for the 'Show SBR' switch.

        Args:
            app: The main application instance.
            state (bool): The new state of the switch.
        """
        app.settings.setValue(s.SETTINGS_SHOW_SBR, state)
        app.show_SBR = state
        ControlsController.SBR_set_visible(app, state)

    @staticmethod
    def _update_phasor_plots_for_harmonic(app):
        """
        Redraws all elements on the phasor plots based on the current harmonic.

        This private helper is called when the harmonic selection changes,
        updating points, clusters, legends, and lifetime curves.

        Args:
            app: The main application instance.
        """
        # In phasors read mode, file-specific scatters/legends are managed by plot_phasors_data
        # Do not clear them here, as they won't be redrawn by this function
        import settings.settings as settings

        is_phasors_read_mode = (
            app.tab_selected == settings.TAB_PHASORS and app.acquire_read_mode == "read"
        )

        if app.acquire_read_mode == "read" and not is_phasors_read_mode:
            # Only clear for non-phasors read modes (e.g., fitting/spectroscopy read)
            PhasorsController.clear_phasors_file_scatters(app)
            PhasorsController.clear_phasors_files_legend(app)

        # Get frequency - use metadata frequency in read mode, current frequency in acquire mode
        if app.acquire_read_mode == "read":
            frequency_mhz = ReadData.get_frequency_mhz(app)
        else:
            frequency_mhz = ControlsController.get_current_frequency_mhz(app)
        laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0

        if app.harmonic_selector_value >= 1 and app.quantized_phasors:
            PhasorsController.quantize_phasors(
                app,
                app.harmonic_selector_value,
                bins=int(s.PHASORS_RESOLUTIONS[app.phasors_resolution]),
            )

        if not app.quantized_phasors:
            # In phasors read mode, clear old scatters and redraw for new harmonic
            if is_phasors_read_mode:
                PhasorsController.clear_phasors_file_scatters(app)
                PhasorsController.clear_phasors_files_legend(app)

                # Redraw points for the selected harmonic (only in read mode)
                for i, channel_index in enumerate(app.plots_to_show):
                    if (
                        channel_index < len(app.all_phasors_points)
                        and app.harmonic_selector_value
                        in app.all_phasors_points[channel_index]
                    ):
                        PhasorsController.draw_points_in_phasors(
                            app,
                            channel_index,
                            app.harmonic_selector_value,
                            app.all_phasors_points[channel_index][
                                app.harmonic_selector_value
                            ],
                        )

        PhasorsController.generate_phasors_cluster_center(
            app, app.harmonic_selector_value
        )
        PhasorsController.hide_phasors_legends(app)
        PhasorsController.generate_phasors_legend(app, app.harmonic_selector_value)

        for i, channel_index in enumerate(app.plots_to_show):
            PhasorsController.draw_lifetime_points_in_phasors(
                app,
                channel_index,
                app.harmonic_selector_value,
                laser_period_ns,
                frequency_mhz,
            )

    @staticmethod
    def on_harmonic_selector_change(app, value):
        """
        Callback for when the displayed harmonic is changed via the selector.

        Args:
            app: The main application instance.
            value (int): The index of the selected harmonic.
        """
        PhasorsController.clear_phasors_points(app)
        if not app.phasors_widgets or value < 0:
            return
        app.harmonic_selector_value = int(value) + 1
        app.phasors_harmonic_selected = int(value) + 1
        ControlsController._update_phasor_plots_for_harmonic(app)

    @staticmethod
    def controls_set_enabled(app, enabled: bool):
        """
        Enables or disables all main control inputs.

        Args:
            app: The main application instance.
            enabled (bool): True to enable controls, False to disable.
        """
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
                not ControlsController.get_free_running_state(app)
            )

    @staticmethod
    def SBR_set_visible(app, visible):
        """
        Sets the visibility of all SBR (Signal-to-Background Ratio) labels.

        Args:
            app: The main application instance.
            visible (bool): True to show SBR labels, False to hide.
        """
        for _, widget in app.SBR_items.items():
            if widget is not None:
                widget.setVisible(visible)

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def top_bar_set_enabled(app, enabled: bool):
        """
        Enables or disables the entire top bar area, including all controls.

        Args:
            app: The main application instance.
            enabled (bool): True to enable the top bar, False to disable.
        """
        ControlsController.sync_buttons_set_enabled(app, enabled)
        ControlsController.channel_selector_set_enabled(app, enabled)
        ControlsController.controls_set_enabled(app, enabled)

    @staticmethod
    def sync_buttons_set_enabled(app, enabled: bool):
        """
        Enables or disables all synchronization mode buttons.

        Args:
            app: The main application instance.
            enabled (bool): True to enable buttons, False to disable.
        """
        for i in range(len(app.sync_buttons)):
            app.sync_buttons[i][0].setEnabled(enabled)

    @staticmethod
    def get_current_frequency_mhz(app):
        """
        Gets the current operational laser frequency in MHz.

        The frequency is determined based on the current mode (read vs. acquire)
        and the selected synchronization source.

        Args:
            app: The main application instance.

        Returns:
            float: The current frequency in MHz.
        """
        if app.acquire_read_mode == "read":
            return ReadData.get_frequency_mhz(app)
        else:
            if app.selected_sync == "sync_in":
                frequency_mhz = app.sync_in_frequency_mhz
            else:
                frequency_mhz = int(app.selected_sync.split("_")[-1])
            return frequency_mhz

    @staticmethod
    def get_frequency_mhz(app):
        """
        Gets the laser frequency in MHz based on the current settings.

        This is a convenience method, similar to get_current_frequency_mhz.

        Args:
            app: The main application instance.

        Returns:
            float: The current frequency in MHz.
        """
        if app.acquire_read_mode == "read":
            return ReadData.get_frequency_mhz(app)
        else:
            if app.selected_sync == "sync_in":
                frequency_mhz = app.sync_in_frequency_mhz
            else:
                frequency_mhz = int(app.selected_sync.split("_")[-1])
            return frequency_mhz

    @staticmethod
    def _is_pico_mode_available(app, frequency_mhz=None):
        """
        Checks whether pico mode can be enabled based on channels and frequency.

        Args:
            app: The main application instance.
            frequency_mhz (float | None, optional): Frequency to evaluate. Defaults to current.

        Returns:
            bool: True if pico mode can be used, False otherwise.
        """
        freq = (
            frequency_mhz
            if frequency_mhz is not None
            else ControlsController.get_current_frequency_mhz(app)
        )
        channels_ok = len(app.selected_channels) <= 2 and len(app.selected_channels) > 0
        freq_ok = is_frequency_near_supported_pico_modes(freq)
        return channels_ok and freq_ok

    @staticmethod
    def update_pico_mode_toggle(app, frequency_mhz=None):
        """
        Updates visibility and checked state of the pico mode toggle based on current conditions.

        Args:
            app: The main application instance.
            frequency_mhz (float | None, optional): Frequency to evaluate. Defaults to current.
        """
        if s.SETTINGS_PICO_MODE not in app.control_inputs:
            return

        pico_toggle = app.control_inputs[s.SETTINGS_PICO_MODE]
        pico_container = app.widgets.get("pico_mode_container", None)
        available = ControlsController._is_pico_mode_available(app, frequency_mhz)

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

    @staticmethod
    def on_pico_mode_changed(app, enabled: bool):
        """
        Handles pico mode toggle changes.

        Args:
            app: The main application instance.
            enabled (bool): New pico mode state.
        """
        app.pico_mode = enabled
        app.settings.setValue(s.SETTINGS_PICO_MODE, enabled)

    @staticmethod
    def get_firmware_selected(app, frequency_mhz, pico_mode=None):
        """
        Determines the appropriate firmware file based on current settings.

        Args:
            app: The main application instance.
            frequency_mhz (float): The current laser frequency.
            pico_mode (bool | None, optional): Pico mode selection to pass to backend. Defaults to current state.

        Returns:
            tuple[str, str]: A tuple containing the path to the selected
                             firmware file and the connection type string.
        """
        connection_type = app.control_inputs["channel_type"].currentText()
        if str(connection_type) == "USB":
            connection_type = "USB"
        else:
            connection_type = "SMA"
        firmware_selected = flim_labs.get_spectroscopy_firmware(
            sync="in" if app.selected_sync == "sync_in" else "out",
            frequency_mhz=frequency_mhz,
            channel=connection_type.lower(),
            channels=app.selected_channels,
            sync_connection="sma",
            pico_mode=app.pico_mode if pico_mode is None else pico_mode,
        )
        return firmware_selected, connection_type

    @staticmethod
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
            if ControlsController.get_free_running_state(app)
            else int(
                app.settings.value(
                    s.SETTINGS_ACQUISITION_TIME, s.DEFAULT_ACQUISITION_TIME
                )
            )
        )

    @staticmethod
    def channel_selector_set_enabled(app, enabled: bool):
        """
        Enables or disables all channel selection checkboxes.

        Args:
            app: The main application instance.
            enabled (bool): True to enable checkboxes, False to disable.
        """
        for i in range(len(app.channel_checkboxes)):
            app.channel_checkboxes[i].setEnabled(enabled)

    @staticmethod
    def on_channel_selected(app, checked: bool, channel: int):
        """
        Callback for when a channel selection checkbox is toggled.

        Updates the list of selected channels and the list of channels to plot,
        then regenerates the plots.

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
        ControlsController.set_selected_channels_to_settings(app)
        PlotsController.clear_plots(app)
        PlotsController.generate_plots(app)
        ExportData.calc_exported_file_size(app)
        ControlsController.update_pico_mode_toggle(app)

    @staticmethod
    def on_sync_selected(app, sync: str):
        """
        Callback for when a synchronization mode is selected.

        Args:
            app: The main application instance.
            sync (str): The name of the selected sync mode.
        """

        def update_phasors_lifetimes():
            frequency_mhz = ControlsController.get_current_frequency_mhz(app)
            if frequency_mhz != 0.0:
                ControlsController.time_shifts_set_enabled(app, True)
                laser_period_ns = mhz_to_ns(frequency_mhz)
                harmonic = app.control_inputs[s.HARMONIC_SELECTOR].currentIndex() + 1
                for _, channel in enumerate(app.plots_to_show):
                    PhasorsController.draw_lifetime_points_in_phasors(
                        app, channel, harmonic, laser_period_ns, frequency_mhz
                    )
            else:
                ControlsController.time_shifts_set_enabled(app, False)
            ControlsController.reset_time_shifts_values(app)

        if app.selected_sync == sync and sync == "sync_in":
            ControlsController.start_sync_in_dialog(app)
            update_phasors_lifetimes()
            return
        app.selected_sync = sync
        app.settings.setValue(s.SETTINGS_SYNC, sync)
        update_phasors_lifetimes()
        ControlsController.update_pico_mode_toggle(
            app, ControlsController.get_current_frequency_mhz(app)
        )

    @staticmethod
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
            ControlsController.update_sync_in_button(app)

    @staticmethod
    def update_sync_in_button(app):
        """
        Updates the text of the 'Sync In' button to show the detected frequency.

        Args:
            app: The main application instance.
        """
        if app.sync_in_frequency_mhz == 0.0:
            ControlsController.time_shifts_set_enabled(app, False)
            app.sync_buttons[0][0].setText("Sync In (not detected)")
        else:
            ControlsController.time_shifts_set_enabled(app, True)
            app.sync_buttons[0][0].setText(f"Sync In ({app.sync_in_frequency_mhz} MHz)")
        ControlsController.update_pico_mode_toggle(app, app.sync_in_frequency_mhz)

    @staticmethod
    def show_harmonic_selector(app, harmonics):
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
                # clear the items
                app.control_inputs[s.HARMONIC_SELECTOR].clear()
                for i in range(harmonics):
                    app.control_inputs[s.HARMONIC_SELECTOR].addItem(str(i + 1))
            app.control_inputs[s.HARMONIC_SELECTOR].setCurrentIndex(
                app.phasors_harmonic_selected - 1
            )

    @staticmethod
    def hide_harmonic_selector(app):
        """
        Hides the harmonic selector dropdown and its label.

        Args:
            app: The main application instance.
        """
        app.control_inputs[s.HARMONIC_SELECTOR].hide()
        app.control_inputs[s.HARMONIC_SELECTOR_LABEL].hide()

    @staticmethod
    def open_plots_config_popup(app):
        """
        Opens the plots configuration popup window.

        Args:
            app: The main application instance.
        """
        app.popup = PlotsConfigPopup(app, start_acquisition=False)
        app.popup.show()

    @staticmethod
    def open_reader_popup(app):
        """
        Opens the file reader popup window.

        Args:
            app: The main application instance.
        """
        app.popup = ReaderPopup(app, tab_selected=app.tab_selected)
        app.popup.show()

    @staticmethod
    def open_reader_metadata_popup(app):
        """
        Opens the file reader metadata popup window.

        Args:
            app: The main application instance.
        """
        app.popup = ReaderMetadataPopup(app, tab_selected=app.tab_selected)
        app.popup.show()

    @staticmethod
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

    @staticmethod
    def is_reference_phasors(app):
        """
        Checks if the current mode is for recording a phasor reference.

        Args:
            app: The main application instance.

        Returns:
            bool: True if in spectroscopy tab with 'Phasors Ref.' calibration.
        """
        selected_calibration = app.settings.value(
            s.SETTINGS_CALIBRATION_TYPE, s.DEFAULT_SETTINGS_CALIBRATION_TYPE
        )
        return app.tab_selected == s.TAB_SPECTROSCOPY and selected_calibration == 1

    @staticmethod
    def is_reference_irf(app):
        """
        Checks if the current mode is for recording an IRF reference.

        Args:
            app: The main application instance.

        Returns:
            bool: True if selected calibration is 'IRF Ref.'
        """
        selected_calibration = app.settings.value(
            s.SETTINGS_CALIBRATION_TYPE, s.DEFAULT_SETTINGS_CALIBRATION_TYPE
        )
        return selected_calibration == 2

    @staticmethod
    def is_phasor_ref_data(reference_data):
        return "ref_type" in reference_data and reference_data["ref_type"] == "phasors"

    @staticmethod
    def is_irf_ref_data(reference_data):
        return "ref_type" in reference_data and reference_data["ref_type"] == "irf"

    @staticmethod
    def is_birfi_ref_data(reference_data):
        return "ref_type" in reference_data and reference_data["ref_type"] == "birfi"

    @staticmethod
    def is_fitting_ref_data(reference_data):
        return (
            "ref_type" in reference_data
            and reference_data["ref_type"] == "irf"
            or reference_data["ref_type"] == "birfi"
        )

    @staticmethod
    def is_reference_birfi(app):
        """
        Checks if the current mode is for recording a BIRFI reference.

        Args:
            app: The main application instance.

        Returns:
            bool: True if selected calibration is 'BIRFI Ref.'
        """
        selected_calibration = app.settings.value(
            s.SETTINGS_CALIBRATION_TYPE, s.DEFAULT_SETTINGS_CALIBRATION_TYPE
        )
        return selected_calibration == 3

    @staticmethod
    def is_phasors(app):
        """
        Checks if the currently selected tab is the Phasors tab.

        Args:
            app: The main application instance.

        Returns:
            bool: True if the Phasors tab is active, False otherwise.
        """
        return app.tab_selected == s.TAB_PHASORS

    @staticmethod
    def get_selected_channels_from_settings(app):
        """
        Loads the selected channels from the application settings.

        This method iterates through the possible channels and repopulates the
        `app.selected_channels` list based on the values stored in the
        persistent settings. It also updates the visual state of the checkboxes.

        Args:
            app: The main application instance.
        """
        app.selected_channels = []
        for i in range(s.MAX_CHANNELS):
            is_selected = app.settings.value(f"channel_{i}", "false") == "true"
            if is_selected:
                app.selected_channels.append(i)
            # Update the checkbox UI if it already exists
            if i < len(app.channel_checkboxes):
                app.channel_checkboxes[i].set_checked(is_selected)

    @staticmethod
    def set_selected_channels_to_settings(app):
        """
        Saves the currently selected channels to the application settings.

        This method ensures that the user's channel selection is persisted
        across application sessions by storing the state of each channel
        in the settings file.

        Args:
            app: The main application instance.
        """
        for i in range(s.MAX_CHANNELS):
            app.settings.setValue(f"channel_{i}", "false")
            if i in app.selected_channels:
                app.settings.setValue(f"channel_{i}", "true")
