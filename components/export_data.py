import datetime
import os
import shutil
from PyQt6.QtWidgets import QFileDialog
from components.file_utils import get_recent_phasors_file, get_recent_spectroscopy_file
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
            ExportData.save_fitting_data()

    @staticmethod
    def save_spectroscopy_data(app):
        try:
            spectroscopy_file = get_recent_spectroscopy_file()
            new_spectroscopy_file_path, save_dir, save_name = ExportData.rename_and_move_file(
                spectroscopy_file, "Save Spectroscopy files", app
            )
            if not new_spectroscopy_file_path:
                return
            ExportData.save_spectroscopy_reference(save_name, save_dir)
            file_paths = {"spectroscopy": new_spectroscopy_file_path}
            ExportData.download_scripts(file_paths, save_name, save_dir, "spectroscopy")
        except Exception as e:
            ScriptFileUtils.show_error_message(e)


    @staticmethod 
    def save_spectroscopy_reference(file_name, directory):
        # read all lines from .pid file            
        with open(".pid", "r") as f:
            lines = f.readlines()
            reference_file = lines[0].split("=")[1].strip()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        full_path = os.path.join(directory, f"{file_name}_spectroscopy_{timestamp}.reference.json")
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(reference_file, "r") as f:            
            with open(full_path, "w") as f2:
                f2.write(f.read())    
    
    @staticmethod        
    def save_phasors_data(app):
        try:
            spectroscopy_file_ref = get_recent_spectroscopy_file()
            phasors_file = get_recent_phasors_file()
            new_phasors_file_path, save_dir, save_name = ExportData.rename_and_move_file(phasors_file, "Save Phasors Files", app)
            if not new_phasors_file_path:
                return
            original_spectroscopy_ref_name = os.path.basename(spectroscopy_file_ref)
            new_spectroscopy_ref_name = f"{save_name}_{original_spectroscopy_ref_name}"
            new_spectroscopy_ref_path = os.path.join(save_dir, new_spectroscopy_ref_name)
            shutil.copyfile(spectroscopy_file_ref, new_spectroscopy_ref_path)
            file_paths = {"spectroscopy_phasors_ref": new_spectroscopy_ref_path, "phasors": new_phasors_file_path}
            ExportData.download_scripts(file_paths, save_name, save_dir, "phasors")
            
        except Exception as e:
            ScriptFileUtils.show_error_message(e)

    @staticmethod        
    def save_fitting_data():
        pass
    
    @staticmethod
    def download_scripts(bin_file_paths, file_name, directory, script_type):
        ScriptFileUtils.export_scripts(bin_file_paths, file_name, directory, script_type)
        
    @staticmethod
    def rename_and_move_file(original_file_path, file_dialog_prompt, app):
        dialog = QFileDialog()
        save_path, _ = dialog.getSaveFileName(
            app,
            file_dialog_prompt,
            "",
            "All Files (*);;Binary Files (*.bin)",
            options=QFileDialog.Option.DontUseNativeDialog,
            
        )
        if save_path:
            save_dir = os.path.dirname(save_path)
            save_name = os.path.basename(save_path)
            original_filename = os.path.basename(original_file_path)
            new_filename = f"{save_name}_{original_filename}"
            new_file_path = os.path.join(save_dir, new_filename)
            shutil.copyfile(original_file_path, new_file_path)
            return new_file_path, save_dir, save_name
        else: 
            return None, None, None
