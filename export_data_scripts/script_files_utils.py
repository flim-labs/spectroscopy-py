"""
Script Files Utilities Module.

This module provides utilities for exporting data processing scripts in Python and MATLAB
formats. It handles template processing, file path manipulation, and requirements generation
for spectroscopy, phasors, fitting, and time tagger data analysis scripts.

The module supports automatic generation of analysis scripts with embedded file paths
and appropriate dependency requirements based on the data type and processing needs.

Classes:
    ScriptFileUtils: Main utility class for script export operations
"""

import os

from PyQt6.QtWidgets import QMessageBox

from components.box_message import BoxMessage
from utils.gui_styles import GUIStyles
from utils.messages_utilities import MessagesUtilities
from utils.resource_path import resource_path

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))

# Script template file paths
spectroscopy_py_script_path = resource_path("export_data_scripts/spectroscopy_script.py")  
spectroscopy_m_script_path = resource_path("export_data_scripts/spectroscopy_script.m") 
phasors_py_script_path = resource_path("export_data_scripts/phasors_script.py")  
phasors_m_script_path = resource_path("export_data_scripts/phasors_script.m")  
fitting_py_script_path = resource_path("export_data_scripts/fitting_script.py")  
fitting_m_script_path = resource_path("export_data_scripts/fitting_script.m")  
time_tagger_py_script_path = resource_path("export_data_scripts/time_tagger_script.py")


class ScriptFileUtils:
    """
    Utility class for generating and exporting data analysis scripts.
    
    This class provides methods to create customized Python and MATLAB scripts
    for different types of data analysis (spectroscopy, phasors, fitting).
    It handles template processing, file path injection, and dependency management.
    """
    
    @classmethod
    def export_scripts(cls, bin_file_paths, file_name, directory, script_type, time_tagger=False, time_tagger_file_path="", channel_names=None):
        """
        Export analysis scripts for the specified data type and configuration.
        
        Args:
            bin_file_paths (dict): Dictionary containing file paths for different data types
            file_name (str): Base name for the exported script files
            directory (str): Target directory for script export
            script_type (str): Type of script to export ('spectroscopy', 'phasors', 'fitting')
            time_tagger (bool, optional): Whether to include time tagger functionality. Defaults to False.
            time_tagger_file_path (str, optional): Path to time tagger data file. Defaults to "".
            channel_names (dict, optional): Dictionary of custom channel names. Defaults to None.
            
        Returns:
            None: Creates script files in the specified directory
            
        Raises:
            Exception: If script generation or file writing fails
        """
        if channel_names is None:
            channel_names = {}
        try:
            if time_tagger:
                python_modifier = cls.get_time_tagger_content_modifiers()
                cls.write_new_scripts_content(python_modifier, {"time_tagger": time_tagger_file_path}, file_name, directory, "py", "time_tagger_spectroscopy", channel_names)
            if script_type == 'spectroscopy':
                python_modifier, matlab_modifier = cls.get_spectroscopy_content_modifiers(time_tagger)
                cls.write_new_scripts_content(python_modifier, bin_file_paths, file_name, directory, "py", script_type, channel_names)
                cls.write_new_scripts_content(matlab_modifier, bin_file_paths, file_name, directory, "m", script_type, channel_names)
            elif script_type == 'phasors':
                python_modifier, matlab_modifier = cls.get_phasors_content_modifiers(time_tagger)   
                cls.write_new_scripts_content(python_modifier, bin_file_paths, file_name, directory, "py", script_type, channel_names)
                cls.write_new_scripts_content(matlab_modifier, bin_file_paths, file_name, directory, "m", script_type, channel_names)
            elif script_type == 'fitting':
                python_modifier, matlab_modifier = cls.get_fitting_content_modifiers(time_tagger)    
                cls.write_new_scripts_content(python_modifier, bin_file_paths, file_name, directory, "py", script_type, channel_names)
                cls.write_new_scripts_content(matlab_modifier, bin_file_paths, file_name, directory, "m", script_type, channel_names)    
            cls.show_success_message(file_name)                
        except Exception as e:
            cls.show_error_message(str(e))

    @classmethod
    def write_new_scripts_content(cls, content_modifier, bin_file_paths, file_name, directory, file_extension, script_type, channel_names=None):
        """
        Generate and write customized script content to files.
        
        Args:
            content_modifier (dict): Configuration for content modification including source file and patterns
            bin_file_paths (dict): Dictionary of data file paths to inject into scripts
            file_name (str): Base name for the output script file
            directory (str): Target directory for file creation
            file_extension (str): File extension ('py' or 'm')
            script_type (str): Type of script being generated
            channel_names (dict, optional): Dictionary of custom channel names. Defaults to None.
            
        Returns:
            None: Creates script and requirements files
        """
        if channel_names is None:
            channel_names = {}
        is_phasors = script_type == "phasors"
        is_fitting = script_type == "fitting"
        content = cls.read_file_content(content_modifier["source_file"])
        new_content = cls.manipulate_file_content(content, bin_file_paths, is_phasors, is_fitting, channel_names)
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
        Get content modification configuration for spectroscopy scripts.
        
        Args:
            time_tagger (bool, optional): Whether to include time tagger dependencies. Defaults to False.
            
        Returns:
            tuple: (python_modifier, matlab_modifier) dictionaries containing modification settings
        """
        python_modifier = {
            "source_file": spectroscopy_py_script_path,
            "skip_pattern": "def get_recent_spectroscopy_file():",
            "end_pattern": "with open(file_path, 'rb') as f:",
            "replace_pattern": "with open(file_path, 'rb') as f:",
            "requirements": ["matplotlib", "numpy"] if not time_tagger else ["matplotlib", "numpy", "pandas", "tqdm", "pyarrow",  "colorama"],
        }
        matlab_modifier = {
            "source_file": spectroscopy_m_script_path,      
            "skip_pattern": "% Get the recent spectroscopy file",
            "end_pattern": "% Open the file",
            "replace_pattern": "% Open the file",
            "requirements": [],
        }
        return python_modifier, matlab_modifier
    
    @classmethod    
    def get_phasors_content_modifiers(cls, time_tagger=False):
        """
        Get content modification configuration for phasors scripts.
        
        Args:
            time_tagger (bool, optional): Whether to include time tagger dependencies. Defaults to False.
            
        Returns:
            tuple: (python_modifier, matlab_modifier) dictionaries containing modification settings
        """
        python_modifier = {
            "source_file": phasors_py_script_path,
            "skip_pattern": "get_recent_spectroscopy_file():",
            "end_pattern": "def ns_to_mhz(laser_period_ns):",
            "replace_pattern": "def ns_to_mhz(laser_period_ns):",
            "requirements": ["matplotlib", "numpy"] if not time_tagger else ["matplotlib", "numpy", "pandas", "tqdm", "pyarrow",  "colorama"],
        }
        matlab_modifier = {
            "source_file": phasors_m_script_path,
            "skip_pattern": "% Get recent spectroscopy file",
            "end_pattern": "% READ SPECTROSCOPY DATA",
            "replace_pattern": "% READ SPECTROSCOPY DATA",
            "requirements": [],
        }
        return python_modifier, matlab_modifier
    
    @classmethod    
    def get_fitting_content_modifiers(cls, time_tagger=False):
        """
        Get content modification configuration for fitting scripts.
        
        Args:
            time_tagger (bool, optional): Whether to include time tagger dependencies. Defaults to False.
            
        Returns:
            tuple: (python_modifier, matlab_modifier) dictionaries containing modification settings
        """
        python_modifier = {
            "source_file": fitting_py_script_path,
            "skip_pattern": "def get_recent_spectroscopy_file():",
            "end_pattern": "with open(file_path, 'rb') as f:",
            "replace_pattern": "with open(file_path, 'rb') as f:",
            "requirements": ["matplotlib", "numpy", "scipy"] if not time_tagger else ["matplotlib", "numpy", "scipy", "pandas", "tqdm", "pyarrow",  "colorama"],
        }
        matlab_modifier = {
            "source_file": fitting_m_script_path,      
            "skip_pattern": "% Get the recent spectroscopy file",
            "end_pattern": "% Open the file",
            "replace_pattern": "% Open the file",
            "requirements": [],
        }
        return python_modifier, matlab_modifier            

    @classmethod    
    def get_time_tagger_content_modifiers(cls):
        """
        Get content modification configuration for time tagger scripts.
        
        Returns:
            dict: Configuration dictionary for time tagger script modification
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
    def write_file(cls, file_name, content):
        """
        Write content to a file.
        
        Args:
            file_name (str): Path to the output file
            content (list): List of strings to write to the file
            
        Returns:
            None: Creates or overwrites the specified file
        """
        with open(file_name, "w") as file:
            file.writelines(content)

    @classmethod
    def create_requirements_content(cls, requirements):
        """
        Create requirements.txt content from a list of package names.
        
        Args:
            requirements (list): List of Python package names
            
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
            list: List of lines from the file
            
        Raises:
            FileNotFoundError: If the specified file doesn't exist
            IOError: If file reading fails
        """
        with open(file_path, "r") as file:
            return file.readlines()

    @classmethod
    def manipulate_file_content(cls, content, file_paths, is_phasors, is_fitting, channel_names=None):
        """
        Replace placeholder patterns in file content with actual file paths and channel names.
        
        Args:
            content (list): List of file content lines
            file_paths (dict): Dictionary mapping data types to file paths
            is_phasors (bool): Whether this is phasors data processing
            is_fitting (bool): Whether this is fitting data processing
            channel_names (dict, optional): Dictionary of custom channel names. Defaults to None.
            
        Returns:
            list: Modified content with file paths and channel names injected
        """
        import json
        if channel_names is None:
            channel_names = {}
        channel_names_json = json.dumps(channel_names)
        manipulated_lines = []
        for line in content:
            if is_phasors:
                # Replace placeholders for phasors analysis (requires both spectroscopy and phasors files)
                line = line.replace("<SPECTROSCOPY-FILE-PATH>", file_paths['spectroscopy_phasors_ref'].replace("\\", "/"))
                line = line.replace("<PHASORS-FILE-PATH>", file_paths['phasors'].replace("\\", "/"))
            elif is_fitting:
                # Replace placeholder for fitting data
                line = line.replace("<SPECTROSCOPY-FILE-PATH>", file_paths['spectroscopy'].replace("\\", "/"))
                line = line.replace("<FITTING-FILE-PATH>", file_paths['fitting'].replace("\\", "/"))
            elif "time_tagger" in file_paths:
                # Replace placeholder for time tagger data
                line = line.replace("<FILE-PATH>", file_paths['time_tagger'].replace("\\", "/"))    
            else:
                # Replace placeholder for spectroscopy or fitting data
                line = line.replace("<FILE-PATH>", file_paths['spectroscopy'].replace("\\", "/"))
            # Replace channel names placeholder
            line = line.replace("<CHANNEL-NAMES>", channel_names_json)
            manipulated_lines.append(line)
        return manipulated_lines

    @classmethod
    def show_success_message(cls, file_name):
        """
        Display success message after script export completion.
        
        Args:
            file_name (str): Name of the exported files
            
        Returns:
            None: Shows success dialog
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
        Display error message if script export fails.
        
        Args:
            error_message (str): Description of the error that occurred
            
        Returns:
            None: Shows error dialog
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