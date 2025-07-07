"""
Script File Utilities Module

This module provides utilities for exporting and generating analysis scripts for different
types of spectroscopy data analysis including spectroscopy, phasors, and fitting analysis.
It handles the creation of both Python and MATLAB scripts with appropriate file paths
and requirements.
"""

import os

from PyQt6.QtWidgets import QMessageBox

from components.box_message import BoxMessage
from utils.gui_styles import GUIStyles
from utils.messages_utilities import MessagesUtilities
from utils.resource_path import resource_path

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))

spectroscopy_py_script_path = resource_path("export_data_scripts/spectroscopy_script.py")  
spectroscopy_m_script_path = resource_path("export_data_scripts/spectroscopy_script.m") 
phasors_py_script_path = resource_path("export_data_scripts/phasors_script.py")  
phasors_m_script_path = resource_path("export_data_scripts/phasors_script.m")  
fitting_py_script_path = resource_path("export_data_scripts/fitting_script.py")  
fitting_m_script_path = resource_path("export_data_scripts/fitting_script.m")  
time_tagger_py_script_path = resource_path("export_data_scripts/time_tagger_script.py") 
spectroscopy_macro_py_script_path = resource_path("export_data_scripts/macro_spectroscopy_script.py")   
phasors_macro_py_script_path = resource_path("export_data_scripts/macro_phasors_script.py")  


class ScriptFileUtils:
    """
    Utility class for handling script file operations.
    
    This class provides methods to export analysis scripts for different types of
    spectroscopy data analysis. It supports generating Python and MATLAB scripts
    for spectroscopy, phasors, and fitting analysis, along with macro scripts
    and requirements files.
    """
    
    @classmethod
    def export_scripts(cls, bin_file_paths, file_name, directory, script_type, time_tagger=False, time_tagger_file_path=""):
        """
        Export analysis scripts based on the specified script type.
        
        Args:
            bin_file_paths (dict): Dictionary containing file paths for different data types
            file_name (str): Base name for the output script files
            directory (str): Target directory for saving the scripts
            script_type (str): Type of script to generate ('spectroscopy', 'phasors', 'fitting')
            time_tagger (bool, optional): Whether to include time tagger functionality. Defaults to False.
            time_tagger_file_path (str, optional): Path to time tagger file. Defaults to "".
            
        Raises:
            Exception: If an error occurs during script generation or file writing
        """
        try:
            if time_tagger:
                python_modifier = cls.get_time_tagger_content_modifiers()
                cls.write_new_scripts_content(python_modifier, {"time_tagger": time_tagger_file_path}, file_name, directory, "py", "time_tagger_spectroscopy")
            if script_type == 'spectroscopy':
                python_modifier, matlab_modifier = cls.get_spectroscopy_content_modifiers(time_tagger)
                cls.write_new_scripts_content(python_modifier, bin_file_paths, file_name, directory, "py", script_type)
                cls.write_new_scripts_content(matlab_modifier, bin_file_paths, file_name, directory, "m", script_type)
                # Spectroscopy macro
                python_modifier = cls.get_spectroscopy_macro_content_modifiers()
                cls.write_new_scripts_content(python_modifier, None, "macro", directory, "py", "spectroscopy")
            elif script_type == 'phasors':
                python_modifier, matlab_modifier = cls.get_phasors_content_modifiers(time_tagger)   
                cls.write_new_scripts_content(python_modifier, bin_file_paths, file_name, directory, "py", script_type)
                cls.write_new_scripts_content(matlab_modifier, bin_file_paths, file_name, directory, "m", script_type)
                # Phasors macro
                python_modifier = cls.get_phasors_macro_content_modifiers()
                cls.write_new_scripts_content(python_modifier, None, "macro", directory, "py", "phasors")                
            elif script_type == 'fitting':
                python_modifier, matlab_modifier = cls.get_fitting_content_modifiers(time_tagger)    
                cls.write_new_scripts_content(python_modifier, bin_file_paths, file_name, directory, "py", script_type)
                cls.write_new_scripts_content(matlab_modifier, bin_file_paths, file_name, directory, "m", script_type)    
            cls.show_success_message(file_name)                
        except Exception as e:
            cls.show_error_message(str(e))

    @classmethod
    def write_new_scripts_content(cls, content_modifier, bin_file_paths, file_name, directory, file_extension, script_type):
        """
        Write new script content to files based on content modifiers.
        
        Args:
            content_modifier (dict): Configuration for content modification including source file and patterns
            bin_file_paths (dict or None): Dictionary of file paths to be embedded in the script
            file_name (str): Base name for the output file
            directory (str): Target directory for saving the file
            file_extension (str): File extension ('py' or 'm')
            script_type (str): Type of script being generated
        """
        is_phasors = script_type == "phasors"
        content = cls.read_file_content(content_modifier["source_file"])
        if bin_file_paths is not None:
            new_content = cls.manipulate_file_content(content, bin_file_paths, is_phasors)
        else:
            new_content = content    
        script_file_name = f"{file_name}_{script_type}_script.{file_extension}"
        script_file_path = os.path.join(directory, script_file_name)
        cls.write_file(script_file_path, new_content)
        if content_modifier["requirements"]:
            requirements_file_name = "requirements.txt"
            requirements_file_path = os.path.join(directory, requirements_file_name)
            requirements_content = cls.create_requirements_content(
                content_modifier["requirements"]
            )
            cls.write_file(requirements_file_path, requirements_content)
        
    @classmethod
    def get_spectroscopy_content_modifiers(cls, time_tagger=False):
        """
        Get content modifiers for spectroscopy scripts.
        
        Args:
            time_tagger (bool, optional): Whether to include time tagger functionality. Defaults to False.
            
        Returns:
            tuple: A tuple containing (python_modifier, matlab_modifier) dictionaries
        """
        python_modifier = {
            "source_file": spectroscopy_py_script_path,
            "skip_pattern": "def get_recent_spectroscopy_file():",
            "end_pattern": "# Read laserblood experiment metadata",
            "replace_pattern": "# Read laserblood experiment metadata",
            "requirements": ["matplotlib", "numpy", "pandas", "tqdm", "pyarrow",  "colorama", "openpyxl"],
        }
        matlab_modifier = {
            "source_file": spectroscopy_m_script_path,      
            "skip_pattern": "% Get the recent spectroscopy file",
            "end_pattern": "% READ LASERBLOOD EXPERIMENT METADATA",
            "replace_pattern": "% READ LASERBLOOD EXPERIMENT METADATA",
            "requirements": [],
        }
        return python_modifier, matlab_modifier
    
    @classmethod    
    def get_phasors_content_modifiers(cls, time_tagger=False):
        """
        Get content modifiers for phasors analysis scripts.
        
        Args:
            time_tagger (bool, optional): Whether to include time tagger functionality. Defaults to False.
            
        Returns:
            tuple: A tuple containing (python_modifier, matlab_modifier) dictionaries
        """
        python_modifier = {
            "source_file": phasors_py_script_path,
            "skip_pattern": "get_recent_spectroscopy_file():",
            "end_pattern": "def ns_to_mhz(laser_period_ns):",
            "replace_pattern": "def ns_to_mhz(laser_period_ns):",
            "requirements":  ["matplotlib", "numpy", "pandas", "tqdm", "pyarrow",  "colorama", "openpyxl"],
        }
        matlab_modifier = {
            "source_file": phasors_m_script_path,
            "skip_pattern": "% Get recent spectroscopy file",
            "end_pattern": "% READ LASERBLOOD EXPERIMENT METADATA",
            "replace_pattern": "% READ LASERBLOOD EXPERIMENT METADATA",
            "requirements": [],
        }
        return python_modifier, matlab_modifier
    
    @classmethod    
    def get_fitting_content_modifiers(cls, time_tagger=False):
        """
        Get content modifiers for fitting analysis scripts.
        
        Args:
            time_tagger (bool, optional): Whether to include time tagger functionality. Defaults to False.
            
        Returns:
            tuple: A tuple containing (python_modifier, matlab_modifier) dictionaries
        """
        python_modifier = {
            "source_file": fitting_py_script_path,
            "skip_pattern": "def get_recent_spectroscopy_file():",
            "end_pattern": "# Read laserblood experiment metadata:",
            "replace_pattern": "# Read laserblood experiment metadata",
            "requirements": ["matplotlib", "numpy", "scipy", "pandas", "tqdm", "pyarrow",  "colorama", "openpyxl"],
        }
        matlab_modifier = {
            "source_file": fitting_m_script_path,      
            "skip_pattern": "% Get the recent spectroscopy file",
            "end_pattern": "% READ LASERBLOOD EXPERIMENT METADATA",
            "replace_pattern": "% READ LASERBLOOD EXPERIMENT METADATA",
            "requirements": [],
        }
        return python_modifier, matlab_modifier            

    @classmethod    
    def get_time_tagger_content_modifiers(cls):
        """
        Get content modifiers for time tagger scripts.
        
        Returns:
            dict: Dictionary containing configuration for time tagger script generation
        """
        python_modifier = {
            "source_file": time_tagger_py_script_path,
            "skip_pattern": "def get_recent_time_tagger_file():",
            "end_pattern": "init(autoreset=True)",
            "replace_pattern": "init(autoreset=True)",
            "requirements": [],
        }
        return python_modifier 
    
    @classmethod    
    def get_spectroscopy_macro_content_modifiers(cls):
        """
        Get content modifiers for spectroscopy macro scripts.
        
        Returns:
            dict: Dictionary containing configuration for spectroscopy macro script generation
        """
        python_modifier = {
            "source_file": spectroscopy_macro_py_script_path,
            "skip_pattern": "",
            "end_pattern": "# Create a directory for output files ('summary analysis') if it does not exist",
            "replace_pattern": "# Create a directory for output files ('summary analysis') if it does not exist",
            "requirements": [],
        }
        return python_modifier   
    
    @classmethod    
    def get_phasors_macro_content_modifiers(cls):
        """
        Get content modifiers for phasors macro scripts.
        
        Returns:
            dict: Dictionary containing configuration for phasors macro script generation
        """
        python_modifier = {
            "source_file": phasors_macro_py_script_path,
            "skip_pattern": "",
            "end_pattern": "# Create a directory for output files ('summary analysis') if it does not exist",
            "replace_pattern": "# Create a directory for output files ('summary analysis') if it does not exist",
            "requirements": [],
        }
        return python_modifier                 

    @classmethod
    def write_file(cls, file_name, content):
        """
        Write content to a file.
        
        Args:
            file_name (str): Path and name of the file to write
            content (list): List of strings representing file content lines
        """
        with open(file_name, "w") as file:
            file.writelines(content)

    @classmethod
    def create_requirements_content(cls, requirements):
        """
        Create content for requirements.txt file.
        
        Args:
            requirements (list): List of package names to include in requirements
            
        Returns:
            list: List of formatted requirement strings with newlines
        """
        requirements_content = [f"{requirement}\n" for requirement in requirements]
        return requirements_content

    @classmethod
    def read_file_content(cls, file_path):
        """
        Read content from a file.
        
        Args:
            file_path (str): Path to the file to read
            
        Returns:
            list: List of strings representing file content lines
        """
        with open(file_path, "r") as file:
            return file.readlines()

    @classmethod
    def manipulate_file_content(cls, content, file_paths, is_phasors):
        """
        Manipulate file content by replacing placeholders with actual file paths.
        
        Args:
            content (list): List of strings representing original file content
            file_paths (dict): Dictionary containing file paths for replacement
            is_phasors (bool): Whether the script is for phasors analysis
            
        Returns:
            list: List of strings with placeholders replaced by actual file paths
        """
        manipulated_lines = []
        for line in content:
            if "time_tagger" not in file_paths:
                line = line.replace("<LASERBLOOD-METADATA-FILE-PATH>", file_paths['laserblood_metadata'].replace("\\", "/"))
            if is_phasors:
                line = line.replace("<SPECTROSCOPY-FILE-PATH>", file_paths['spectroscopy_phasors_ref'].replace("\\", "/"))
                line = line.replace("<PHASORS-FILE-PATH>", file_paths['phasors'].replace("\\", "/"))
            elif "time_tagger" in file_paths:
               line = line.replace("<FILE-PATH>", file_paths['time_tagger'].replace("\\", "/"))    
            else:
                line = line.replace("<FILE-PATH>", file_paths['spectroscopy'].replace("\\", "/"))
            manipulated_lines.append(line)
        return manipulated_lines

    @classmethod
    def show_success_message(cls, file_name):
        """
        Display a success message dialog.
        
        Args:
            file_name (str): Name of the successfully processed file
        """
        info_title, info_msg = MessagesUtilities.info_handler(
            "SavedDataFiles", file_name
        )
        BoxMessage.setup(
            info_title,
            info_msg,
            QMessageBox.Icon.Information,
            GUIStyles.set_msg_box_style(),
        )

    @classmethod
    def show_error_message(cls, error_message):
        """
        Display an error message dialog.
        
        Args:
            error_message (str): Error message to display
        """
        error_title, error_msg = MessagesUtilities.error_handler(
            "ErrorSavingDataFiles", error_message
        )
        BoxMessage.setup(
            error_title,
            error_msg,
            QMessageBox.Icon.Critical,
            GUIStyles.set_msg_box_style(),
        )