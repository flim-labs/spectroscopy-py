import os
import shutil

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from components.box_message import BoxMessage
from components.gui_styles import GUIStyles
from components.messages_utilities import MessagesUtilities

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path, ".."))


class ScriptFileUtils:
    @classmethod
    def export_script_file(
        cls, bin_file_path, file_extension, content_modifier
    ):
        file_name, _ = QFileDialog.getSaveFileName(
            None, "Save File", "", f"All Files (*.{file_extension})"
        )
        if not file_name:
            return
        try:
            bin_file_name = os.path.join(
                os.path.dirname(file_name),
                f"{os.path.splitext(os.path.basename(file_name))[0]}.bin",
            ).replace("\\", "/")

            shutil.copy(bin_file_path, bin_file_name) if bin_file_path else None

            # write script file
            content = content_modifier["source_file"]
            new_content = cls.manipulate_file_content(content, bin_file_name)
            cls.write_file(file_name, new_content)

            # write requirements file only for python export
            if len(content_modifier["requirements"]) > 0:
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
        requirements_content = []

        for requirement in requirements:
            requirements_content.append(f"{requirement}\n")
        return [requirements_path, requirements_content]

    @classmethod
    def read_file_content(cls, file_path):
        with open(file_path, "r") as file:
            return file.readlines()

    @classmethod
    def manipulate_file_content(cls, content, file_name):
        return content.replace("<FILE-PATH>", file_name.replace("\\", "/"))

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
        content_modifier = {
            "source_file": """import struct
from matplotlib.gridspec import GridSpec            
import matplotlib.pyplot as plt

file_path = "<FILE-PATH>"
                     
                              
            """,
            "skip_pattern": "def get_recent_fcs_file():",
            "end_pattern": "def calc_g2_correlations_mean(g2):",
            "replace_pattern": "def calc_g2_correlations_mean(g2):",
            "requirements": ["matplotlib"],
        }
        ScriptFileUtils.export_script_file(
            bin_file_path, "py", content_modifier
        )
        
    @staticmethod
    def download_phasors(window, bin_file_path):
        content_modifier = {
            "source_file": """import struct
from matplotlib.gridspec import GridSpec            
import matplotlib.pyplot as plt

file_path = "<FILE-PATH>"
                     
                              
            """,
            "skip_pattern": "def get_recent_fcs_file():",
            "end_pattern": "def calc_g2_correlations_mean(g2):",
            "replace_pattern": "def calc_g2_correlations_mean(g2):",
            "requirements": ["matplotlib"],
        }
        ScriptFileUtils.export_script_file(
            bin_file_path, "py", content_modifier
        )