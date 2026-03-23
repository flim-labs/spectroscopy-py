import os
import json
import re
from PyQt6.QtWidgets import QFileDialog
from settings.settings import DEFAULT_BIN_WIDTH, SETTINGS_BIN_WIDTH, SETTINGS_TAU_NS


class FileUtils:
    """A collection of utility methods for file and directory operations."""
    @staticmethod
    def directory_selector(window):
        """Opens a dialog for the user to select a directory.

        Args:
            window (QWidget): The parent window for the dialog.

        Returns:
            str: The path of the selected directory, or an empty string if canceled.
        """
        folder_path = QFileDialog.getExistingDirectory(window, "Select Directory")
        return folder_path

    @staticmethod
    def get_recent_spectroscopy_file():
        """Finds the most recent spectroscopy data file in the default data directory.

        Returns:
            str: The full path to the most recent spectroscopy file.
        """
        data_folder = os.path.join(os.environ["USERPROFILE"], ".flim-labs", "data")
        files = [
            f
            for f in os.listdir(data_folder)
            if f.startswith("spectroscopy")
            and f.endswith(".bin")
            and not ("calibration" in f)
            and not ("phasors" in f)
        ]
        files.sort(
            key=lambda x: os.path.getmtime(os.path.join(data_folder, x)), reverse=True
        )
        return os.path.join(data_folder, files[0])

    @staticmethod
    def get_recent_time_tagger_file():
        """Finds the most recent time tagger data file in the default data directory.

        Returns:
            str: The full path to the most recent time tagger file.
        """
        data_folder = os.path.join(os.environ["USERPROFILE"], ".flim-labs", "data")
        files = [
            f
            for f in os.listdir(data_folder)
            if f.startswith("time_tagger_spectroscopy") and f.endswith(".bin")
        ]
        files.sort(
            key=lambda x: os.path.getmtime(os.path.join(data_folder, x)), reverse=True
        )
        return os.path.join(data_folder, files[0])

    @staticmethod
    def get_recent_phasors_file():
        """Finds the most recent phasors data file in the default data directory.

        Raises:
            FileNotFoundError: If no suitable phasors file is found.

        Returns:
            str: The full path to the most recent phasors file.
        """
        data_folder = os.path.join(os.environ["USERPROFILE"], ".flim-labs", "data")
        files = [
            f
            for f in os.listdir(data_folder)
            if f.startswith("spectroscopy-phasors") and f.endswith(".bin") and not ("calibration" in f)
        ]
        files.sort(
            key=lambda x: os.path.getmtime(os.path.join(data_folder, x)), reverse=True
        )
        if not files:
            raise FileNotFoundError("No suitable phasors file found.")
        return os.path.join(data_folder, files[0])

    @staticmethod
    def rename_bin_file(source_file, new_filename):
        """Constructs a new, descriptive filename for a binary data file.

        Args:
            source_file (str): The original path of the binary file.
            new_filename (str): The base name for the new file.
            window: The main application window instance.

        Returns:
            str: The newly constructed filename.
        """
        _, file_extension = os.path.splitext(source_file)
        base_name = os.path.basename(source_file).replace(file_extension, "")
        dest_file_name = f"{new_filename}_{base_name}{file_extension}"
        return dest_file_name

 

    @staticmethod
    def compare_file_timestamps(file_path1, file_path2):
        """Calculates the absolute difference in creation time between two files.

        Args:
            file_path1 (str): Path to the first file.
            file_path2 (str): Path to the second file.

        Returns:
            float: The absolute difference in seconds between the files' creation times.
        """
        ctime1 = os.path.getctime(file_path1)
        ctime2 = os.path.getctime(file_path2)
        time_diff = abs(ctime1 - ctime2)
        return time_diff

    @staticmethod
    def clean_filename(filename):
        """Removes characters from a string that are not letters, numbers, or underscores.

        Args:
            filename (str): The input string.

        Returns:
            str: The cleaned string, suitable for use as a filename.
        """
        # Keep only letters, numbers and underscores
        filename = filename.replace(" ", "_")
        return re.sub(r"[^a-zA-Z0-9_]", "", filename)
