import os
import shutil

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from components.box_message import BoxMessage
from components.gui_styles import GUIStyles
from components.messages_utilities import MessagesUtilities

current_path = os.path.dirname(os.path.abspath(__file__))
spectroscopy_py_script_path = os.path.join(current_path, "spectroscopy_py_script_for_export.py")
spectroscopy_m_script_path = os.path.join(current_path, "spectroscopy_m_script_for_export.m")
phasors_py_script_path = os.path.join(current_path, "phasors_py_script_for_export.py")
phasors_m_script_path = os.path.join(current_path, "phasors_m_script_for_export.m")

class ScriptFileUtils:
    @classmethod
    def export_script_file(cls, bin_file_paths, file_extension, content_modifier):
        file_name, _ = QFileDialog.getSaveFileName(
            None, "Save File", "", f"All Files (*.{file_extension})"
        )
        if not file_name:
            return
        try:
            copied_files = {}
            for key, bin_file_path in bin_file_paths.items():
                bin_file_name = os.path.join(
                    os.path.dirname(file_name),
                    f"{os.path.splitext(os.path.basename(file_name))[0]}_{key}.bin"
                ).replace("\\", "/")

                if bin_file_path:
                    shutil.copy(bin_file_path, bin_file_name)
                    copied_files[key] = bin_file_name

            # write script file
            is_phasors = 'phasors' in bin_file_path
            content = cls.read_file_content(content_modifier["source_file"])
            new_content = cls.manipulate_file_content(content, copied_files, is_phasors)
            cls.write_file(file_name, new_content)

            # write requirements file only for python export
            if content_modifier["requirements"]:
                requirement_path, requirements_content = cls.create_requirements_file(
                    file_name, content_modifier["requirements"]
                )
                cls.write_file(requirement_path, requirements_content)

            cls.show_success_message(file_name)
        except Exception as e:
            cls.show_error_message(str(e))

    @classmethod
    def write_file(cls, file_name, content):
        with open(file_name, "w") as file:
            file.writelines(content)

    @classmethod
    def create_requirements_file(cls, script_file_name, requirements):
        directory = os.path.dirname(script_file_name)
        requirements_path = os.path.join(directory, "requirements.txt")
        requirements_content = [f"{requirement}\n" for requirement in requirements]
        return requirements_path, requirements_content

    @classmethod
    def read_file_content(cls, file_path):
        with open(file_path, "r") as file:
            return file.readlines()

    @classmethod
    def manipulate_file_content(cls, content, file_paths, is_phasors):
        manipulated_lines = []
        for line in content:
            if is_phasors:
                line = line.replace("<SPECTROSCOPY-FILE-PATH>", file_paths['spectroscopy_phasors_ref'].replace("\\", "/"))
                line = line.replace("<PHASORS-FILE-PATH>", file_paths['phasors'].replace("\\", "/"))
            else:
                line = line.replace("<FILE-PATH>", file_paths['spectroscopy'].replace("\\", "/"))
            manipulated_lines.append(line)
        return manipulated_lines

    @classmethod
    def show_success_message(cls, file_name):
        info_title, info_msg = MessagesUtilities.info_handler(
            "SavedScriptFile", file_name
        )
        BoxMessage.setup(
            info_title,
            info_msg,
            QMessageBox.Icon.Information,
            GUIStyles.set_msg_box_style(),
        )

    @classmethod
    def show_error_message(cls, error_message):
        error_title, error_msg = MessagesUtilities.error_handler(
            "ErrorSavingScriptFile", error_message
        )
        BoxMessage.setup(
            error_title,
            error_msg,
            QMessageBox.Icon.Critical,
            GUIStyles.set_msg_box_style(),
        )


class PythonScriptUtils(ScriptFileUtils):

    @staticmethod
    def download_spectroscopy(window, bin_file_path):
        file_paths = {"spectroscopy": bin_file_path}
        content_modifier = {
            "source_file": spectroscopy_py_script_path,
            "skip_pattern": "def get_recent_spectroscopy_file():",
            "end_pattern": "with open(file_path, 'rb') as f:",
            "replace_pattern": "with open(file_path, 'rb') as f:",
            "requirements": ["matplotlib", "numpy"],
        }
        ScriptFileUtils.export_script_file(file_paths, "py", content_modifier)

    @staticmethod
    def download_phasors(window, spectroscopy_ref_file_path, phasors_file_path):
        file_paths = {"spectroscopy_phasors_ref": spectroscopy_ref_file_path, "phasors": phasors_file_path}
        content_modifier = {
            "source_file": phasors_py_script_path,
            "skip_pattern": "get_recent_spectroscopy_file():",
            "end_pattern": "def ns_to_mhz(laser_period_ns):",
            "replace_pattern": "def ns_to_mhz(laser_period_ns):",
            "requirements": ["matplotlib", "numpy"],
        }
        ScriptFileUtils.export_script_file(file_paths, "py", content_modifier)


class MatlabScriptUtils(ScriptFileUtils):
    @staticmethod
    def download_spectroscopy(window, bin_file_path):
        file_paths = {"spectroscopy": bin_file_path}
        content_modifier = {
            "source_file": spectroscopy_m_script_path,      
            "skip_pattern": "% Get the recent spectroscopy file",
            "end_pattern": "% Open the file",
            "replace_pattern": "% Open the file",
            "requirements": [],
        }
        ScriptFileUtils.export_script_file(file_paths, "m", content_modifier)

    @staticmethod
    def download_phasors(window, spectroscopy_ref_file_path, phasors_file_path):
        file_paths = {"spectroscopy_phasors_ref": spectroscopy_ref_file_path, "phasors": phasors_file_path}
        content_modifier = {
            "source_file": phasors_m_script_path,
            "skip_pattern": "% Get recent spectroscopy file",
            "end_pattern": "% READ SPECTROSCOPY DATA",
            "replace_pattern": "% READ SPECTROSCOPY DATA",
            "requirements": [],
        }
        ScriptFileUtils.export_script_file(file_paths, "m", content_modifier)
