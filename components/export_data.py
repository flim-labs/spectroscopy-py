import datetime
import json
import os
import shutil
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from components.file_utils import FileUtils
from components.box_message import BoxMessage
from components.gui_styles import GUIStyles
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
            time_tagger = app.time_tagger
            spectroscopy_file = FileUtils.get_recent_spectroscopy_file()
            new_spectroscopy_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(
                    spectroscopy_file, "Save Fitting files", window, app))
            if not new_spectroscopy_file_path:
                return
            laserblood_metadata_file_path = ExportData.save_laserblood_metadata(
                app, save_name, save_dir
            )
            ExportData.save_fitting_config_json(fitting_data, save_dir, save_name, app)
            
            if time_tagger:
                time_tagger_file = FileUtils.get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
                    time_tagger_file, save_name, save_dir, app
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
                time_tagger=time_tagger,
                time_tagger_file_path=new_time_tagger_path,
            )
        except Exception as e:
            ScriptFileUtils.show_error_message(e)

    @staticmethod
    def save_fitting_config_json(fitting_data, save_dir, save_name, app):
        try:
            laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
            file_name = f"{save_name}_{laser_key}_{filter_key}_fitting_result.json"
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
            spectroscopy_file = FileUtils.get_recent_spectroscopy_file()
            time_tagger = app.time_tagger
            new_spectroscopy_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(
                    spectroscopy_file, "Save Spectroscopy files", app, app
                )
            )
            if not new_spectroscopy_file_path:
                return

            if time_tagger:
                time_tagger_file = FileUtils.get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
                    time_tagger_file, save_name, save_dir, app
                )
            new_time_tagger_path = (
                ""
                if not time_tagger or not new_time_tagger_path
                else new_time_tagger_path
            )
            laserblood_metadata_file_path = ExportData.save_laserblood_metadata(
                app, save_name, save_dir
            )            
            if app.control_inputs["calibration"].currentIndex() == 1:
                ExportData.save_spectroscopy_reference(save_name, save_dir, app)
            
            file_paths = {
                "spectroscopy": new_spectroscopy_file_path,
                "laserblood_metadata": laserblood_metadata_file_path,
            }            
            ExportData.download_scripts(
                file_paths,
                save_name,
                save_dir,
                "spectroscopy",
                time_tagger=time_tagger,
                time_tagger_file_path=new_time_tagger_path,
            )
        except Exception as e:
            ScriptFileUtils.show_error_message(e)

    @staticmethod
    def save_laserblood_metadata(app, file_name, directory):
        return FileUtils.save_laserblood_metadata_json(file_name, directory, app)

    @staticmethod
    def save_spectroscopy_reference(file_name, directory, app):
        # read all lines from .pid file
        with open(".pid", "r") as f:
            lines = f.readlines()
            reference_file = lines[0].split("=")[1].strip()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
        full_path = os.path.join(
            directory,
            f"{file_name}_{laser_key}_{filter_key}__spectroscopy_{timestamp}.reference.json",
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
            spectroscopy_file_ref = FileUtils.get_recent_spectroscopy_file()
            phasors_file = FileUtils.get_recent_phasors_file()
            time_tagger = app.time_tagger
        
            new_phasors_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(phasors_file, "Save Phasors Files", app, app)
            )
            if not new_phasors_file_path:
                return
            
            original_spectroscopy_ref_name = os.path.basename(spectroscopy_file_ref)
            laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
            new_spectroscopy_ref_name = (
                f"{save_name}_{laser_key}_{filter_key}_{original_spectroscopy_ref_name}"
            )
            new_spectroscopy_ref_path = os.path.join(
                save_dir, new_spectroscopy_ref_name
            )
            shutil.copyfile(spectroscopy_file_ref, new_spectroscopy_ref_path)
      
            laserblood_metadata_file_path = ExportData.save_laserblood_metadata(
                app, save_name, save_dir
            )

            if time_tagger:
                time_tagger_file = FileUtils.get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
                    time_tagger_file, save_name, save_dir, app
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
        time_tagger=False,
        time_tagger_file_path="",
    ):
        ScriptFileUtils.export_scripts(
            bin_file_paths,
            file_name,
            directory,
            script_type,
            time_tagger,
            time_tagger_file_path,
        )

    @staticmethod
    def copy_file(origin_file_path, save_name, save_dir, app):
        laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
        origin_file_name = os.path.basename(origin_file_path)
        new_file_name = f"{save_name}_{laser_key}_{filter_key}_{origin_file_name}"
        new_file_path = os.path.join(save_dir, new_file_name)
        shutil.copyfile(origin_file_path, new_file_path)
        return new_file_path

    @staticmethod
    def rename_and_move_file(original_file_path, file_dialog_prompt, window, app):
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
            original_filename = os.path.basename(original_file_path)
            replaced_filename = original_filename.replace("spectroscopy-phasors", "phasors-spectroscopy")
            laser_key, filter_key = ExportData.get_laser_filter_type_info(app)
            new_filename = f"{save_name}_{laser_key}_{filter_key}_{replaced_filename}"
            new_file_path = os.path.join(save_dir, new_filename)
            shutil.copyfile(original_file_path, new_file_path)
            return new_file_path, save_dir, save_name
        else:
            return None, None, None