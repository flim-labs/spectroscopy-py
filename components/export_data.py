import datetime
import json
import os
import shutil
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from components.file_utils import FileUtils
from components.box_message import BoxMessage
from components.gui_styles import GUIStyles
from components.helpers import calc_timestamp
from export_data_scripts.script_files_utils import ScriptFileUtils
from settings import *

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class ExportData:
    @staticmethod
    def save_acquisition_data(app, active_tab):
        if active_tab == TAB_SPECTROSCOPY:
            ExportData.save_spectroscopy_data(app)

        elif active_tab == TAB_PHASORS:
            ExportData.save_phasors_data(app)
        else:
            return

    @staticmethod
    def save_fitting_data(fitting_data, window, app):
        try:
            timestamp  = calc_timestamp()
            time_tagger = app.time_tagger
            # Spectroscopy file (.bin)
            spectroscopy_file = FileUtils.get_recent_spectroscopy_file()
            new_spectroscopy_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(
                    spectroscopy_file, "fitting_spectroscopy", "Save Fitting files", timestamp, window, app))
            if not new_spectroscopy_file_path:
                return
            # Laserblood metadata file (.json)
            laserblood_metadata_file_path = ExportData.save_laserblood_metadata(
                app, save_name, save_dir, timestamp, [new_spectroscopy_file_path]
            )
            # Fitting file (.json)
            ExportData.save_fitting_config_json(fitting_data, save_dir, save_name, app, timestamp)
            
            # Time Tagger file (.bin)
            if time_tagger:
                time_tagger_file = FileUtils.get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
                    time_tagger_file, save_name, save_dir, "time_tagger_spectroscopy", timestamp, app
                )
            new_time_tagger_path = (
                ""
                if not time_tagger or not new_time_tagger_path
                else new_time_tagger_path
            )

            file_paths = {"spectroscopy": new_spectroscopy_file_path, "laserblood_metadata": laserblood_metadata_file_path,}
            ExportData.download_scripts(
                file_paths,
                save_name,
                save_dir,
                "fitting",
                app,
                timestamp,
                time_tagger=time_tagger,
                time_tagger_file_path=new_time_tagger_path,
            )
        except Exception as e:
            ScriptFileUtils.show_error_message(e)

    @staticmethod
    def save_fitting_config_json(fitting_data, save_dir, save_name, app, timestamp):
        try:
            laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
            file_name = FileUtils.clean_filename(f"{timestamp}_{laser_key}_{filter_key}_{save_name}_fitting_result")
            file_name = f"{file_name}.json"
            save_path = os.path.join(
                save_dir, file_name
            )
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
        try:
            timestamp = calc_timestamp()
            # Spectroscopy file (.bin)
            spectroscopy_file = FileUtils.get_recent_spectroscopy_file()
            time_tagger = app.time_tagger
            new_spectroscopy_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(
                    spectroscopy_file, "spectroscopy", "Save Spectroscopy files", timestamp, app, app
                )
            )
            if not new_spectroscopy_file_path:
                return

            # Time tagger file (.bin)
            if time_tagger:
                time_tagger_file = FileUtils.get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
                    time_tagger_file, save_name, save_dir, "time_tagger_spectroscopy", timestamp, app
                )
            new_time_tagger_path = (
                ""
                if not time_tagger or not new_time_tagger_path
                else new_time_tagger_path
            )
            # Laserblood metadata file (.json)
            laserblood_metadata_file_path = ExportData.save_laserblood_metadata(
                app, save_name, save_dir, timestamp, [new_spectroscopy_file_path]
            )      
            # Spectroscopy reference file (.json)      
            if app.control_inputs["calibration"].currentIndex() == 1:
                ExportData.save_spectroscopy_reference(save_name, save_dir, app, timestamp)
            
            file_paths = {
                "spectroscopy": new_spectroscopy_file_path,
                "laserblood_metadata": laserblood_metadata_file_path,
            }            
            ExportData.download_scripts(
                file_paths,
                save_name,
                save_dir,
                "spectroscopy",
                app,
                timestamp,
                time_tagger=time_tagger,
                time_tagger_file_path=new_time_tagger_path,
            )
        except Exception as e:
            ScriptFileUtils.show_error_message(e)

    @staticmethod
    def save_laserblood_metadata(app, file_name, directory, timestamp, reference_file):
        return FileUtils.save_laserblood_metadata_json(file_name, directory, app, timestamp, reference_file)

    @staticmethod
    def save_spectroscopy_reference(file_name, directory, app, timestamp):
        # read all lines from .pid file
        with open(".pid", "r") as f:
            lines = f.readlines()
            reference_file = lines[0].split("=")[1].strip()
        laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
        file_name = FileUtils.clean_filename(f"{timestamp}_{laser_key}_{filter_key}_{file_name}_spectroscopy_reference")
        full_path = os.path.join(
            directory,
            f"{file_name}.json",
        )
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(reference_file, "r") as f:
            with open(full_path, "w") as f2:
                f2.write(f.read())


    @staticmethod
    def get_laser_filter_type_info(app):
        filter_wavelength_input = next(
                (
                    input
                    for input in app.laserblood_settings
                    if input["LABEL"] == "Emission filter wavelength"
                ),
                None,
            )
        laser_key, filter_key = FileUtils.get_laser_info_slug(
            app, filter_wavelength_input
        )
        return laser_key, filter_key

    @staticmethod
    def save_phasors_data(app):
        try:
            timestamp = calc_timestamp()
            spectroscopy_file_ref = FileUtils.get_recent_spectroscopy_file()
            phasors_file = FileUtils.get_recent_phasors_file()
            time_tagger = app.time_tagger
        
            # Phasors file (.bin)
            new_phasors_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(phasors_file, "phasors", "Save Phasors Files", timestamp, app, app)
            )
            if not new_phasors_file_path:
                return
            
            # Spectroscopy file (.bin)
            laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
            clean_name = FileUtils.clean_filename(f"{timestamp}_{laser_key}_{filter_key}_{save_name}_phasors_spectroscopy")
            new_spectroscopy_ref_name = (
                f"{clean_name}.bin"
            )
            new_spectroscopy_ref_path = os.path.join(
                save_dir, new_spectroscopy_ref_name
            )
            shutil.copyfile(spectroscopy_file_ref, new_spectroscopy_ref_path)
      
            # Laserblood metadata file (.json)
            laserblood_metadata_file_path = ExportData.save_laserblood_metadata(
                app, save_name, save_dir, timestamp, [new_phasors_file_path, new_spectroscopy_ref_path]
            )

            # Time Tagger file (.bin)
            if time_tagger:
                time_tagger_file = FileUtils.get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
                    time_tagger_file, save_name, save_dir, "time_tagger_spectroscopy", timestamp, app
                )
            new_time_tagger_path = (
                ""
                if not time_tagger or not new_time_tagger_path
                else new_time_tagger_path
            )

            file_paths = {
                "spectroscopy_phasors_ref": new_spectroscopy_ref_path,
                "phasors": new_phasors_file_path,
                "laserblood_metadata": laserblood_metadata_file_path,
            }
            ExportData.download_scripts(
                file_paths,
                save_name,
                save_dir,
                "phasors",
                app,
                timestamp,
                time_tagger=time_tagger,
                time_tagger_file_path=new_time_tagger_path,
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
    ):
        file_name = FileUtils.clean_filename(file_name)
        laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
        file_name = f"{timestamp}_{laser_key}_{filter_key}_{file_name}"
        ScriptFileUtils.export_scripts(
            bin_file_paths,
            file_name,
            directory,
            script_type,
            time_tagger,
            time_tagger_file_path,
        )

    @staticmethod
    def copy_file(origin_file_path, save_name, save_dir, file_type, timestamp, app, file_extension="bin"):
        laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
        new_filename = f"{timestamp}_{laser_key}_{filter_key}_{save_name}_{file_type}"
        new_filename = f"{FileUtils.clean_filename(new_filename)}.{file_extension}"
        new_file_path = os.path.join(save_dir, new_filename)
        shutil.copyfile(origin_file_path, new_file_path)
        return new_file_path

    @staticmethod
    def rename_and_move_file(original_file_path, file_type, file_dialog_prompt, timestamp, window, app, file_extension="bin"):
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
            laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
            new_filename = f"{timestamp}_{laser_key}_{filter_key}_{save_name}_{file_type}"
            new_filename = f"{FileUtils.clean_filename(new_filename)}.{file_extension}"
            new_file_path = os.path.join(save_dir, new_filename)
            shutil.copyfile(original_file_path, new_file_path)
            return new_file_path, save_dir, save_name
        else:
            return None, None, None