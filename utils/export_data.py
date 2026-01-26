import json
import os
import shutil
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from utils.file_utils import FileUtils
from components.box_message import BoxMessage
from utils.gui_styles import GUIStyles
from utils.helpers import calc_timestamp, format_size
from export_data_scripts.script_files_utils import ScriptFileUtils
import settings.settings as s

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class ExportData:
    """A utility class for exporting acquisition and analysis data."""

    @staticmethod
    def save_acquisition_data(app, active_tab):
        """
        Routes the data saving process based on the active tab.

        Args:
            app: The main application instance.
            active_tab (str): The identifier of the currently active tab.
        """
        if active_tab == s.TAB_SPECTROSCOPY:
            ExportData.save_spectroscopy_data(app)

        elif active_tab == s.TAB_PHASORS:
            ExportData.save_phasors_data(app)
        else:
            return

    @staticmethod
    def save_fitting_data(fitting_data, window, app):
        """
        Saves all data related to a fitting analysis.

        This includes the raw spectroscopy data, time tagger data (if applicable),
        the fitting results JSON, and associated analysis scripts.

        Args:
            fitting_data (dict): The dictionary containing the fitting results.
            window: The main window instance, used for the save dialog.
            app: The main application instance.
        """
        try:
            timestamp  = calc_timestamp()
            time_tagger = app.time_tagger
            # Spectroscopy reference file (.bin)
            spectroscopy_file = FileUtils.get_recent_spectroscopy_file()
            new_spectroscopy_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(
                    app,
                    spectroscopy_file,
                    "fitting_spectroscopy",
                    "Save Fitting files",
                    timestamp,
                    window,
                )
            )
            if not new_spectroscopy_file_path:
                return
            
            # Fitting file (.json)
            ExportData.save_fitting_config_json(fitting_data, save_dir, save_name, app, timestamp)
            
            # Time Tagger file (.bin)
            if time_tagger:
                time_tagger_file = FileUtils.get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
                    app,
                    time_tagger_file,
                    save_name,
                    save_dir,
                    "time_tagger_spectroscopy",
                    timestamp,
                )
            new_time_tagger_path = (
                ""
                if not time_tagger or not new_time_tagger_path
                else new_time_tagger_path
            )

            file_paths = {"spectroscopy": new_spectroscopy_file_path}
            channel_names = getattr(app, 'channel_names', {})
            ExportData.download_scripts(
                file_paths,
                save_name,
                save_dir,
                "fitting",
                app,
                timestamp,
                time_tagger=time_tagger,
                time_tagger_file_path=new_time_tagger_path,
                channel_names=channel_names,
            )
        except Exception as e:
            ScriptFileUtils.show_error_message(e)
            

    @staticmethod
    def save_fitting_config_json(fitting_data, save_dir, save_name, app, timestamp):
        """
        Saves the fitting results to a JSON file.

        Args:
            fitting_data (dict): The dictionary of fitting results.
            save_dir (str): The directory to save the file in.
            save_name (str): The base name for the file.
            app: The main application instance.
            timestamp (str): The timestamp for the filename.
        """
        try:
            file_name = FileUtils.clean_filename(f"{save_name}_{timestamp}_fitting_result")
            file_name = f"{file_name}.json"
            save_path = os.path.join(save_dir, file_name)
            with open(save_path, "w") as file:
                json.dump(fitting_data, file, indent=4)
        except Exception as e:
            BoxMessage.setup(
                "Error",
                "Error saving fitting JSON",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )

    @staticmethod
    def save_spectroscopy_data(app):
        """
        Saves all data related to a spectroscopy acquisition.

        This includes the raw spectroscopy data, time tagger data (if applicable),
        the spectroscopy reference (if used), and associated analysis scripts.

        Args:
            app: The main application instance.
        """
        try:
            timestamp = calc_timestamp()
            time_tagger = app.time_tagger
            # Spectroscopy file (.bin)
            spectroscopy_file = FileUtils.get_recent_spectroscopy_file()
            new_spectroscopy_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(
                    app,
                    spectroscopy_file,
                    "spectroscopy",
                    "Save Spectroscopy files",
                    timestamp,
                    app,
                )
            )
            if not new_spectroscopy_file_path:
                return

          # Time tagger file (.bin)
            if time_tagger:
                time_tagger_file = FileUtils.get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
                    app,
                    time_tagger_file,
                    save_name,
                    save_dir,
                    "time_tagger_spectroscopy",
                    timestamp,
                )
            new_time_tagger_path = (
                ""
                if not time_tagger or not new_time_tagger_path
                else new_time_tagger_path
            )
            
            # Spectroscopy Calibration reference file (.json)
            if app.control_inputs["calibration"].currentIndex() == 1:
                ExportData.save_spectroscopy_reference(app, save_name, save_dir, timestamp)
            file_paths = {"spectroscopy": new_spectroscopy_file_path}
            channel_names = getattr(app, 'channel_names', {})       
            ExportData.download_scripts(
                file_paths,
                save_name,
                save_dir,
                "spectroscopy",
                app,
                timestamp,
                time_tagger=time_tagger,
                time_tagger_file_path=new_time_tagger_path,
                channel_names=channel_names,
            )
        except Exception as e:
            ScriptFileUtils.show_error_message(e)
    

    @staticmethod
    def save_spectroscopy_reference(app, file_name, directory, timestamp):
        """
        Saves the spectroscopy reference file used for calibration.
        Args:
            file_name (str): The base name for the file.
            directory (str): The directory to save the file in.
            app: The main application instance.
            timestamp (str): The timestamp for the filename.
        """
        # read all lines from .pid file
        with open(".pid", "r") as f:
            lines = f.readlines()
            reference_file = lines[0].split("=")[1].strip()
        file_name = FileUtils.clean_filename(f"{file_name}_{timestamp}_spectroscopy_reference")
        full_path = os.path.join(directory, f"{file_name}.json")
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(reference_file, "r") as f:
            with open(full_path, "w") as f2:
                f2.write(f.read())

  

    @staticmethod
    def save_phasors_data(app):
        """
        Saves all data related to a phasors acquisition.

        This includes the raw phasors data, the associated spectroscopy data,
        time tagger data (if applicable) and analysis scripts.

        Args:
            app: The main application instance.
        """
        try:
            timestamp = calc_timestamp()
            time_tagger = app.time_tagger
            
            spectroscopy_file_ref = FileUtils.get_recent_spectroscopy_file()
            phasors_file = FileUtils.get_recent_phasors_file()
            
            # Phasors file (.bin)
            new_phasors_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(app, phasors_file, "phasors", "Save Phasors Files", timestamp, app)
            )
            if not new_phasors_file_path:
                return
            
            # Spectroscopy reference file (.bin)
            new_spectroscopy_ref_path = ExportData.copy_file(
                app,
                spectroscopy_file_ref, save_name, save_dir, "phasors_spectroscopy", timestamp
            )
            
            # Time Tagger file (.bin)
            if time_tagger:
                time_tagger_file = FileUtils.get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
                    app,
                    time_tagger_file, save_name, save_dir, "time_tagger_spectroscopy", timestamp
                )
                
            new_time_tagger_path = (
                ""
                if not time_tagger or not new_time_tagger_path
                else new_time_tagger_path
            )
            
            file_paths = {
                "spectroscopy_phasors_ref": new_spectroscopy_ref_path,
                "phasors": new_phasors_file_path,
            }
            channel_names = getattr(app, 'channel_names', {})
            ExportData.download_scripts(
                file_paths,
                save_name,
                save_dir,
                "phasors",
                app,
                timestamp,
                time_tagger=time_tagger,
                time_tagger_file_path=new_time_tagger_path,
                channel_names=channel_names,
            )

        except Exception as e:
            ScriptFileUtils.show_error_message(e)

    @staticmethod
    def download_scripts(
        bin_file_paths,
        file_name,
        directory,
        script_type,
        app,
        timestamp,
        time_tagger=False,
        time_tagger_file_path="",
        channel_names=None,
    ):
        """
        Exports Python analysis scripts along with the saved data.

        Args:
            bin_file_paths (dict): A dictionary of paths to the saved binary files.
            file_name (str): The base name for the script files.
            directory (str): The directory to save the scripts in.
            script_type (str): The type of analysis script to generate ('spectroscopy', 'phasors', 'fitting').
            app: The main application instance.
            timestamp (str): The timestamp for the filename.
            time_tagger (bool, optional): Whether time tagger data is included. Defaults to False.
            time_tagger_file_path (str, optional): The path to the time tagger file. Defaults to "".
            channel_names (dict, optional): Dictionary of custom channel names. Defaults to None.
        """
        if channel_names is None:
            channel_names = {}
        file_name = FileUtils.clean_filename(file_name)
        file_name = f"{file_name}_{timestamp}"
        ScriptFileUtils.export_scripts(
            bin_file_paths,
            file_name,
            directory,
            script_type,
            time_tagger,
            time_tagger_file_path,
            channel_names,
        )

    @staticmethod
    def copy_file(app, origin_file_path, save_name, save_dir, file_type, timestamp, file_extension="bin"):
        """
        Copies a file to a new location with a standardized filename.

        Args:
            origin_file_path (str): The path to the source file.
            save_name (str): The base name for the new file.
            save_dir (str): The directory to save the new file in.
            file_type (str): A descriptor for the file type (e.g., 'time_tagger_spectroscopy').
            timestamp (str): The timestamp for the filename.
            app: The main application instance.
            file_extension (str, optional): The file extension. Defaults to "bin".

        Returns:
            str: The path to the newly created file.
        """
        new_filename = f"{save_name}_{timestamp}_{file_type}"
        new_filename = f"{FileUtils.clean_filename(new_filename)}.{file_extension}"
        new_file_path = os.path.join(save_dir, new_filename)
        shutil.copyfile(origin_file_path, new_file_path)
        return new_file_path
    

    @staticmethod
    def rename_and_move_file(app, original_file_path, file_type, file_dialog_prompt, timestamp, window, file_extension="bin"):
        """
        Opens a save dialog, then copies and renames a file to the chosen location.

        Args:
            original_file_path (str): The path to the source file.
            file_type (str): A descriptor for the file type (e.g., 'spectroscopy').
            file_dialog_prompt (str): The title for the save file dialog.
            timestamp (str): The timestamp for the filename.
            window: The parent window for the dialog.
            app: The main application instance.
            file_extension (str, optional): The file extension. Defaults to "bin".

        Returns:
            tuple: A tuple containing the new file path (str), save directory (str),
                   and base save name (str), or (None, None, None) if canceled.
        """
        dialog = QFileDialog()
        save_path, _ = dialog.getSaveFileName(
            window,
            file_dialog_prompt,
            "",
            "All Files (*);;Binary Files (*.bin)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if save_path:
            save_dir = os.path.dirname(save_path)
            save_name = os.path.basename(save_path)
            new_filename = f"{save_name}_{timestamp}_{file_type}"
            new_filename = f"{FileUtils.clean_filename(new_filename)}.{file_extension}"
            new_file_path = os.path.join(save_dir, new_filename)
            shutil.copyfile(original_file_path, new_file_path)
            return new_file_path, save_dir, save_name
        else:
            return None, None, None

        
        
    
    @staticmethod
    def calc_exported_file_size(app):
        """
        Calculates and displays the estimated size of the output .bin file.

        The calculation depends on whether the acquisition is free-running or
        has a fixed duration. The result is displayed in a label in the UI.

        Args:
            app: The main application instance.
        """
        free_running = app.settings.value(s.SETTINGS_FREE_RUNNING, s.DEFAULT_FREE_RUNNING)
        acquisition_time = app.settings.value(
            s.SETTINGS_ACQUISITION_TIME, s.DEFAULT_ACQUISITION_TIME
        )
        bin_width = app.settings.value(s.SETTINGS_BIN_WIDTH, s.DEFAULT_BIN_WIDTH)
        if free_running is True or acquisition_time is None:
            file_size_MB = len(app.selected_channels) * (1000 / int(bin_width))
            app.bin_file_size = format_size(file_size_MB * 1024 * 1024)
            app.bin_file_size_label.setText(
                "File size: " + str(app.bin_file_size) + "/s"
            )
        else:
            file_size_MB = (
                int(acquisition_time)
                * len(app.selected_channels)
                * (1000 / int(bin_width))
            )
            app.bin_file_size = format_size(file_size_MB * 1024 * 1024)
            app.bin_file_size_label.setText("File size: " + str(app.bin_file_size))