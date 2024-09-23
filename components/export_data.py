import datetime
import json
import os
import shutil
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from components.box_message import BoxMessage
from components.file_utils import (
    clean_filename,
    get_recent_phasors_file,
    get_recent_spectroscopy_file,
    get_recent_time_tagger_file,
)
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
            timestamp = calc_timestamp()
            time_tagger = app.time_tagger
            # Spectroscopy reference file (.bin)
            spectroscopy_file = get_recent_spectroscopy_file()
            new_spectroscopy_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(
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
            ExportData.save_fitting_config_json(
                fitting_data, save_dir, save_name, timestamp
            )

            # Time Tagger file (.bin)
            if time_tagger:
                time_tagger_file = get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
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

            # Scripts
            file_paths = {"spectroscopy": new_spectroscopy_file_path}
            ExportData.download_scripts(
                file_paths,
                save_name,
                save_dir,
                "fitting",
                timestamp,
                time_tagger=time_tagger,
                time_tagger_file_path=new_time_tagger_path,
            )
        except Exception as e:
            ScriptFileUtils.show_error_message(e)

    @staticmethod
    def save_fitting_config_json(fitting_data, save_dir, save_name, timestamp):
        try:
            file_name = clean_filename(f"{save_name}_{timestamp}_fitting_result")
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
        try:
            timestamp = calc_timestamp()
            time_tagger = app.time_tagger
            # Spectroscopy file (.bin)
            spectroscopy_file = get_recent_spectroscopy_file()
            new_spectroscopy_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(
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
                time_tagger_file = get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
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
                ExportData.save_spectroscopy_reference(save_name, save_dir, timestamp)
            file_paths = {"spectroscopy": new_spectroscopy_file_path}
            ExportData.download_scripts(
                file_paths,
                save_name,
                save_dir,
                "spectroscopy",
                timestamp,
                time_tagger=time_tagger,
                time_tagger_file_path=new_time_tagger_path,
            )
        except Exception as e:
            ScriptFileUtils.show_error_message(e)

    @staticmethod
    def save_spectroscopy_reference(file_name, directory, timestamp):
        # read all lines from .pid file
        with open(".pid", "r") as f:
            lines = f.readlines()
            reference_file = lines[0].split("=")[1].strip()
        file_name = clean_filename(f"{file_name}_{timestamp}_spectroscopy_reference")
        full_path = os.path.join(directory, f"{file_name}.json")
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(reference_file, "r") as f:
            with open(full_path, "w") as f2:
                f2.write(f.read())

    @staticmethod
    def save_phasors_data(app):
        try:
            timestamp = calc_timestamp()
            time_tagger = app.time_tagger

            spectroscopy_file_ref = get_recent_spectroscopy_file()
            phasors_file = get_recent_phasors_file()
            # Phasors file (.bin)
            new_phasors_file_path, save_dir, save_name = (
                ExportData.rename_and_move_file(phasors_file, "phasors", "Save Phasors Files", timestamp, app)
            )
            if not new_phasors_file_path:
                return
            
            # Spectroscopy reference file (.bin)
            new_spectroscopy_ref_path = ExportData.copy_file(
                spectroscopy_file_ref, save_name, save_dir, "phasors_spectroscopy", timestamp
            )

            # Time Tagger file (.bin)
            if time_tagger:
                time_tagger_file = get_recent_time_tagger_file()
                new_time_tagger_path = ExportData.copy_file(
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
            ExportData.download_scripts(
                file_paths,
                save_name,
                save_dir,
                "phasors",
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
        timestamp,
        time_tagger=False,
        time_tagger_file_path="",
    ):
        file_name = clean_filename(file_name)
        file_name = f"{file_name}_{timestamp}"
        ScriptFileUtils.export_scripts(
            bin_file_paths,
            file_name,
            directory,
            script_type,
            time_tagger,
            time_tagger_file_path,
        )

    @staticmethod
    def copy_file(
        origin_file_path,
        save_name,
        save_dir,
        file_type,
        timestamp,
        file_extension="bin",
    ):
        new_filename = f"{save_name}_{timestamp}_{file_type}"
        new_filename = f"{clean_filename(new_filename)}.{file_extension}"
        new_file_path = os.path.join(save_dir, new_filename)
        shutil.copyfile(origin_file_path, new_file_path)
        return new_file_path

    @staticmethod
    def rename_and_move_file(
        original_file_path,
        file_type,
        file_dialog_prompt,
        timestamp,
        window,
        file_extension="bin",
    ):
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
            new_filename = f"{clean_filename(new_filename)}.{file_extension}"
            new_file_path = os.path.join(save_dir, new_filename)
            shutil.copyfile(original_file_path, new_file_path)
            return new_file_path, save_dir, save_name
        else:
            return None, None, None
