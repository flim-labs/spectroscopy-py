import os
from PyQt6.QtWidgets import QFileDialog


def directory_selector(window):
    folder_path = QFileDialog.getExistingDirectory(window, "Select Directory")
    return folder_path


def get_recent_spectroscopy_file():
    data_folder = os.path.join(os.environ["USERPROFILE"], ".flim-labs", "data")
    files = [
        f
        for f in os.listdir(data_folder)
        if f.startswith("spectroscopy")
        and not ("calibration" in f)
        and not ("phasors" in f)
    ]
    files.sort(
        key=lambda x: os.path.getmtime(os.path.join(data_folder, x)), reverse=True
    )
    return os.path.join(data_folder, files[0])


def get_recent_phasors_file():
    data_folder = os.path.join(os.environ["USERPROFILE"], ".flim-labs", "data")
    files = [
        f
        for f in os.listdir(data_folder)
        if f.startswith("spectroscopy-phasors") and not ("calibration" in f)
    ]
    files.sort(
        key=lambda x: os.path.getmtime(os.path.join(data_folder, x)), reverse=True
    )
    if not files:
        raise FileNotFoundError("No suitable phasors file found.")
    return os.path.join(data_folder, files[0])


def rename_bin_file(source_file, new_filename):
    _, file_extension = os.path.splitext(source_file)
    base_name = os.path.basename(source_file).replace(file_extension, "")
    dest_file_name = f"{new_filename}_{base_name}{file_extension}"
    return dest_file_name



