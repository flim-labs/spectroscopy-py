import json
import flim_labs
import numpy as np
from components.box_message import BoxMessage
from components.check_card import CheckCard
from utils.export_data import ExportData
from utils.gui_styles import GUIStyles
from utils.helpers import calc_SBR, humanize_number, mhz_to_ns, ns_to_mhz
from components.laserblood_metadata_popup import LaserbloodMetadataPopup
from components.lin_log_control import LinLogControl
from components.plots_config import PlotsConfigPopup
from core.phasors_controller import PhasorsController
import settings.settings as s
from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox,
)
from PyQt6.QtCore import QTimer


class AcquisitionController:
    """
    Manages the data acquisition lifecycle for spectroscopy experiments.

    This class provides static methods to handle the entire workflow, including
    parameter validation, hardware initialization, starting and stopping the
    acquisition, processing incoming data, and updating the user interface.
    """

    @staticmethod
    def _validate_parameters(app):
        """
        Validates essential acquisition parameters before starting.

        Checks for selected channels, a valid bin width, and the presence of
        required metadata if data writing is enabled.

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

        if (
            app.write_data_gui
            and not LaserbloodMetadataPopup.laserblood_metadata_valid(app)
        ):
            BoxMessage.setup(
                "Error",
                "All required Laserblood metadata must be filled before starting the acquisition.",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return False

        return True

    @staticmethod
    def _validate_reference_file(app, frequency_mhz):
        """
        Validates the selected reference file for phasor analysis.

        This check is skipped if the application is not in phasor mode. It verifies
        file existence, format, and consistency with current settings.

        Args:
            app: The main application instance.
            frequency_mhz (float): The current laser frequency in MHz.

        Returns:
            bool | str: True if valid, False if invalid. Returns the string "popup"
                        if a configuration dialog was opened, indicating that the
                        process should wait for user input.
        """
        if app.tab_selected != s.TAB_PHASORS:
            return True

        if not app.reference_file:
            BoxMessage.setup(
                "Error",
                "No reference file selected",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return False

        try:
            with open(app.reference_file, "r") as f:
                ref_data = json.load(f)

            required_keys = [
                "channels",
                "laser_period_ns",
                "harmonics",
                "curves",
                "tau_ns",
            ]
            for key in required_keys:
                if key not in ref_data:
                    BoxMessage.setup(
                        "Error",
                        f"Invalid reference file (missing {key})",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )
                    return False

            if len(ref_data["channels"]) != len(app.selected_channels):
                BoxMessage.setup(
                    "Error",
                    "Invalid reference file (channels mismatch)",
                    QMessageBox.Icon.Warning,
                    GUIStyles.set_msg_box_style(),
                )
                return False

            if ns_to_mhz(ref_data["laser_period_ns"]) != frequency_mhz:
                BoxMessage.setup(
                    "Error",
                    "Invalid reference file (laser period mismatch)",
                    QMessageBox.Icon.Warning,
                    GUIStyles.set_msg_box_style(),
                )
                return False

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
                return "popup"  # Special return to indicate popup was shown

        except (IOError, json.JSONDecodeError) as e:
            BoxMessage.setup(
                "Error",
                f"Error reading reference file: {e}",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return False

        return True

    @staticmethod
    def _prepare_spectroscopy_parameters(app, frequency_mhz):
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
        firmware_selected, _ = ControlsController.get_firmware_selected(
            app, frequency_mhz
        )

        tau_ns = (
            float(app.settings.value(s.SETTINGS_TAU_NS, "0"))
            if ControlsController.is_reference_phasors(app)
            else None
        )

        reference_file = None
        if app.tab_selected == s.TAB_PHASORS:
            reference_file = app.reference_file
            with open(app.reference_file, "r") as f:
                reference_data = json.load(f)
                app.harmonic_selector_value = int(reference_data["harmonics"])
        else:
            app.harmonic_selector_value = app.control_inputs[
                s.SETTINGS_HARMONIC
            ].value()

        params = {
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
            "reference_file": reference_file,
            "harmonics": int(app.harmonic_selector_value),
            "write_bin": False,
            "time_tagger": app.time_tagger
            and app.write_data_gui
            and app.tab_selected != s.TAB_PHASORS,
            "pico_mode": app.pico_mode,
        }
        return params

    @staticmethod
    def _start_acquisition_process(app, params):
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
            AcquisitionController.check_card_connection(app)
            BoxMessage.setup(
                "Error",
                f"Error starting spectroscopy: {e}",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return False

    @staticmethod
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

    @staticmethod
    def begin_spectroscopy_experiment(app):
        from core.plots_controller import PlotsController

        """
        Coordinates the process of starting a spectroscopy experiment.

        This method runs through all pre-flight checks, prepares parameters,
        starts the hardware, and updates the UI.

        Args:
            app: The main application instance.
        """
        from core.controls_controller import ControlsController

        try:
            AcquisitionController.check_card_connection(app, start_experiment=True)
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

        if not AcquisitionController._validate_parameters(app):
            return

        if (
            (
                app.tab_selected == s.TAB_SPECTROSCOPY
                or app.tab_selected == s.TAB_FITTING
            )
            and len(app.selected_channels) > 4
            and not app.plots_to_show_already_appear
        ):
            popup = PlotsConfigPopup(app, start_acquisition=True)
            popup.show()
            app.plots_to_show_already_appear = True
            return

        ref_valid = AcquisitionController._validate_reference_file(app, frequency_mhz)
        if not ref_valid:
            return
        if ref_valid == "popup":  # A popup was shown, so we wait for user action
            return

        PlotsController.clear_plots(app)
        PlotsController.generate_plots(app, frequency_mhz)

        params = AcquisitionController._prepare_spectroscopy_parameters(
            app, frequency_mhz
        )

        if not AcquisitionController._start_acquisition_process(app, params):
            return

        AcquisitionController._update_ui_post_start(app)

    @staticmethod
    def _stop_hardware_and_update_state(app):
        """
        Stops the FLIM-LABS hardware and updates the application's internal state.

        Args:
            app: The main application instance.
        """
        print("Stopping spectroscopy")
        from core.ui_controller import UIController

        try:
            flim_labs.request_stop()
        except Exception as e:
            print(f"Could not stop flim_labs gracefully: {e}")
        app.mode = s.MODE_STOPPED
        UIController.style_start_button(app)
        QApplication.processEvents()

    @staticmethod
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

    @staticmethod
    def _handle_reference_file_after_stop(app):
        """
        If a calibration reference was recorded, reads the generated file path from .pid file.

        Args:
            app: The main application instance.
        """
        from core.controls_controller import ControlsController

        if ControlsController.is_reference_phasors(app):
            try:
                with open(".pid", "r") as f:
                    lines = f.readlines()
                    reference_file = lines[0].split("=")[1].strip()
                app.reference_file = reference_file
                app.saved_spectroscopy_reference = reference_file
                print(f"Last reference file: {reference_file}")
            except (IOError, IndexError) as e:
                print(f"Could not read reference file from .pid: {e}")

    @staticmethod
    def _process_phasor_results(app):
        """
        Finalizes phasor plots after acquisition stops.

        This includes adding analysis elements like cluster centers, legends,
        and quantizing the data if enabled.

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

    @staticmethod
    def _handle_post_acquisition_tasks(app):
        """
        Handles final tasks like data saving and metadata updates after acquisition.

        Args:
            app: The main application instance.
        """
        if app.write_data_gui:
            QTimer.singleShot(
                300,
                lambda: ExportData.save_acquisition_data(
                    app, active_tab=app.tab_selected
                ),
            )

        LaserbloodMetadataPopup.set_FPGA_firmware(app)
        LaserbloodMetadataPopup.set_average_CPS(app.all_cps_counts, app)
        LaserbloodMetadataPopup.set_average_SBR(app.all_SBR_counts, app)

    @staticmethod
    def stop_spectroscopy_experiment(app):
        """
        Coordinates the process of stopping a spectroscopy experiment.

        This method stops the hardware, finalizes the UI, processes results,
        and handles any post-acquisition tasks.

        Args:
            app: The main application instance.
        """
        AcquisitionController._stop_hardware_and_update_state(app)
        AcquisitionController._finalize_ui_after_stop(app)
        AcquisitionController._handle_reference_file_after_stop(app)
        AcquisitionController._process_phasor_results(app)
        AcquisitionController._handle_post_acquisition_tasks(app)

    @staticmethod
    def pull_from_queue(app):
        """
        Pulls data from the FLIM-LABS output queue and processes it.

        This method is connected to a timer and runs continuously during
        acquisition. It dispatches different data types (e.g., decay curves,
        phasors) to the appropriate update functions.

        Args:
            app: The main application instance.
        """
        from core.plots_controller import PlotsController
        from core.ui_controller import UIController

        val = flim_labs.pull_from_queue()
        if len(val) > 0:
            for v in val:
                if v == ("end",):  # End of acquisition
                    print("Got end of acquisition, stopping")
                    UIController.style_start_button(app)
                    app.acquisition_stopped = True
                    AcquisitionController.stop_spectroscopy_experiment(app)
                    break
                if app.mode == s.MODE_STOPPED:
                    break
                if "sp_phasors" in v[0]:
                    channel = v[1][0]
                    harmonic = v[2][0]
                    phasors = v[3]
                    channel_index = next(
                        (item for item in app.plots_to_show if item == channel), None
                    )
                    if harmonic == 1:
                        if channel_index is not None:
                            PhasorsController.draw_points_in_phasors(
                                app, channel, harmonic, phasors
                            )
                    if channel_index is not None:
                        app.all_phasors_points[channel_index][harmonic].extend(phasors)
                    continue
                try:
                    ((channel,), (time_ns,), intensities) = v
                except:
                    print(v)
                ((channel,), (time_ns,), intensities) = v
                channel_index = next(
                    (item for item in app.plots_to_show if item == channel), None
                )
                if channel_index is not None:
                    PlotsController.update_plots(
                        app, channel_index, time_ns, intensities
                    )
                    AcquisitionController.update_acquisition_countdowns(app, time_ns)
                    AcquisitionController.update_cps(
                        app, channel_index, time_ns, intensities
                    )
                QApplication.processEvents()

    @staticmethod
    def update_acquisition_countdowns(app, time_ns):
        """
        Updates the acquisition countdown timer widgets.

        This function is called during acquisition. It calculates the remaining
        time based on the total acquisition duration and the elapsed time,
        and updates the corresponding UI labels. It does nothing if the
        acquisition is in 'Free running' mode.

        Args:
            app: The main application instance.
            time_ns (int): The elapsed time of the acquisition in nanoseconds.
        """
        free_running = app.settings.value(
            s.SETTINGS_FREE_RUNNING, s.DEFAULT_FREE_RUNNING
        )
        acquisition_time = app.control_inputs[s.SETTINGS_ACQUISITION_TIME].value()
        if free_running is True or free_running == "true":
            return
        elapsed_time_sec = time_ns / 1_000_000_000
        remaining_time_sec = max(0, acquisition_time - elapsed_time_sec)
        seconds = int(remaining_time_sec)
        milliseconds = int((remaining_time_sec - seconds) * 1000)
        milliseconds = milliseconds // 10
        for _, countdown_widget in app.acquisition_time_countdown_widgets.items():
            if countdown_widget:
                if not countdown_widget.isVisible():
                    countdown_widget.setVisible(True)
                countdown_widget.setText(
                    f"Remaining time: {seconds:02}:{milliseconds:02} (s)"
                )

    @staticmethod
    def update_SBR(app, channel_index, curve):
        """
        Calculates and updates the Signal-to-Background Ratio (SBR) for a channel.

        Args:
            app: The main application instance.
            channel_index (int): The index of the channel to update.
            curve (np.ndarray): The decay curve data used for calculation.
        """
        if channel_index in app.SBR_items:
            SBR_value = calc_SBR(np.array(curve))
            app.SBR_items[channel_index].setText(f"SBR: {SBR_value:.2f} ㏈")

    @staticmethod
    def update_cps(app, channel_index, time_ns, curve):
        """
        Updates the Counts Per Second (CPS) display for a given channel.

        This method calculates the CPS based on the incoming data rate. It also
        triggers a pile-up warning animation if the CPS exceeds a user-defined
        threshold and updates the SBR value if enabled.

        Args:
            app: The main application instance.
            channel_index (int): The index of the channel to update.
            time_ns (int): The timestamp of the current data chunk in nanoseconds.
            curve (np.ndarray): The intensity data for the current chunk.
        """
        # check if there is channel_index'th element in cps_counts
        if not (channel_index in app.cps_counts):
            return
        cps = app.cps_counts[channel_index]
        curve_sum = np.sum(curve)
        # SBR
        SBR_count = calc_SBR(np.array(curve))
        app.all_SBR_counts.append(SBR_count)
        if cps["last_time_ns"] == 0:
            cps["last_time_ns"] = time_ns
            cps["last_count"] = curve_sum
            cps["current_count"] = curve_sum
            return
        cps["current_count"] = cps["current_count"] + np.sum(curve)
        time_elapsed = time_ns - cps["last_time_ns"]
        if time_elapsed > 330_000_000:
            cps_value = (cps["current_count"] - cps["last_count"]) / (
                time_elapsed / 1_000_000_000
            )
            app.all_cps_counts.append(cps_value)
            humanized_number = humanize_number(cps_value)
            app.cps_widgets[channel_index].setText(f"{humanized_number} CPS")
            cps_threshold = app.control_inputs[s.SETTINGS_CPS_THRESHOLD].value()
            if cps_threshold > 0:
                if cps_value > cps_threshold:
                    app.cps_widgets_animation[channel_index].start()
                else:
                    app.cps_widgets_animation[channel_index].stop()
            # SBR
            if app.show_SBR:
                AcquisitionController.update_SBR(app, channel_index, curve)
            cps["last_time_ns"] = time_ns
            cps["last_count"] = cps["current_count"]

    @staticmethod
    def acquired_spectroscopy_data_to_fit(app, read):
        """
        Prepares and formats the acquired spectroscopy data for the fitting process.

        It extracts decay curve data (x and y values) and time shifts for the
        currently displayed channels. The data is structured into a list of
        dictionaries, which is the format expected by the fitting module.

        Args:
            app: The main application instance.
            read (bool): A flag indicating if the data comes from a loaded file
                         (True) or a live acquisition (False). This affects
                         the scaling of the x-axis data.

        Returns:
            tuple[list[dict], float]: A tuple containing the list of prepared
                                      data dictionaries and the time shift of
                                      the last channel.
        """
        data = []
        time_shift = 0  # Initialize time_shift before loop
        channels_shown = [
            channel for channel in app.plots_to_show if channel in app.selected_channels
        ]
        for channel, channel_index in enumerate(channels_shown):
            time_shift = (
                0
                if channel_index not in app.time_shifts
                else app.time_shifts[channel_index]
            )
            
            # Check if channel exists in decay_curves and cached_decay_values
            if (app.tab_selected not in app.decay_curves or 
                channel_index not in app.decay_curves[app.tab_selected] or
                app.decay_curves[app.tab_selected][channel_index] is None):
                continue
            
            if (app.tab_selected not in app.cached_decay_values or
                channel_index not in app.cached_decay_values[app.tab_selected]):
                continue
                
            x, _ = app.decay_curves[app.tab_selected][channel_index].getData()
            y = app.cached_decay_values[app.tab_selected][channel_index]
            
            # For FITTING READ mode with bin indices, don't multiply by 1000
            # Check if x is already in bin indices (0-255 range)
            is_bin_indices = len(x) > 0 and np.max(x) <= 256
            if read and not is_bin_indices:
                x_data = x * 1000
            else:
                x_data = x
            
            data.append(
                {
                    "x": x_data,
                    "y": y,
                    "title": "Channel " + str(channel_index + 1),
                    "channel_index": channel_index,
                    "time_shift": time_shift,
                }
            )
        return data, time_shift

    @staticmethod
    def check_card_connection(app, start_experiment=False):
        """
        Checks for a connection to the FLIM-LABS hardware card.

        Updates the UI with the card's status or an error message.

        Args:
            app: The main application instance.
            start_experiment (bool, optional): If True, re-raises exceptions
                to halt the start of an experiment. Defaults to False.

        Raises:
            Exception: Re-raises the exception from `flim_labs.check_card()`
                       if `start_experiment` is True and a card is not found.
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
