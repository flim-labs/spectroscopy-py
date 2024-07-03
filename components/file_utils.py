import os
import shutil
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from components.box_message import BoxMessage
from components.gui_styles import GUIStyles


def get_recent_spectroscopy_tracing_file():
    data_folder = os.path.join(os.environ["USERPROFILE"], ".flim-labs", "data")
    files = [
        f
        for f in os.listdir(data_folder)
        if f.startswith("spectroscopy") and not ("calibration" in f)
    ]
    files.sort(
        key=lambda x: os.path.getmtime(os.path.join(data_folder, x)), reverse=True
    )
    if files:
        return os.path.join(data_folder, files[0])
    else:
        return None


def save_spectroscopy_bin_file(window):
    source_file = get_recent_spectroscopy_tracing_file()
    if not source_file:
        return
    dialog = QFileDialog()
    dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setNameFilter("All files (*.*)")
    dialog.setDefaultSuffix("bin")
    file_name, _ = dialog.getSaveFileName(
        window, "Save Spectroscopy File As", "", "Binary files (*.bin);;All files (*.*)"
    )
    if file_name:
        try:
            _, file_extension = os.path.splitext(source_file)
            base_name = os.path.basename(source_file).replace(file_extension, "")
            new_file_name = os.path.basename(file_name).replace(file_extension, "")
            dest_file_name = f"{new_file_name}_{base_name}{file_extension}"
            dest_file_path = os.path.join(os.path.dirname(file_name), dest_file_name)
            shutil.copyfile(source_file, dest_file_path)
            BoxMessage.setup(
                "File saved",
                f"File saved successfully to: {dest_file_path} path",
                QMessageBox.Icon.Information,
                GUIStyles.set_msg_box_style(),
            )
        except Exception as e:
            BoxMessage.setup(
                "Error",
                f"Failed to save file: {str(e)}",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
