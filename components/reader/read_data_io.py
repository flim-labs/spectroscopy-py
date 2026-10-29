"""
read_data_io.py
===============
File I/O methods of the ReadData class:
- read_bin_data
- read_multiple_bin_data
- read_multiple_json_data
- read_laserblood_metadata
- read_fitting_data
- read_json
- read_bin
- read_spectroscopy_data
- read_phasors_data
- get_bin_filter_file_string
"""

import glob
import json
import os
import struct

import numpy as np
from components.box_message import BoxMessage
from utils.gui_styles import GUIStyles
import settings.settings as s

from PyQt6.QtWidgets import QFileDialog, QMessageBox


# ---------------------------------------------------------------------------
# Internal helpers (forward declarations resolved at call time via module ref)
# ---------------------------------------------------------------------------

def _show_warning(title, message):
    BoxMessage.setup(
        title, message, QMessageBox.Icon.Warning, GUIStyles.set_msg_box_style()
    )


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def get_bin_filter_file_string(file_type):
    """Gets the file filter string for binary file dialogs.

    Args:
        file_type (str): The type of binary file ('spectroscopy' or 'phasors').

    Returns:
        str: The corresponding filter string, or None for unknown types.
    """
    if file_type == "spectroscopy":
        return "_spectroscopy_"
    elif file_type == "phasors":
        return "phasors-spectroscopy"
    return None


def show_warning_message(title, message):
    """Displays a standardized warning message box.

    Args:
        title (str): The title of the message box.
        message (str): The content of the message.
    """
    _show_warning(title, message)


def read_bin_data(window, app, tab_selected, file_type):
    """Reads binary data for spectroscopy or phasors from a .bin file.

    Args:
        window: The parent window for the file dialog.
        app: The main application instance.
        tab_selected (str): The currently active tab identifier.
        file_type (str): The type of data to read ('spectroscopy' or 'phasors').
    """
    from components.reader.read_data_utils import get_data_type

    active_tab = get_data_type(tab_selected)
    file_info = {
        "spectroscopy": (b"SP01", "Spectroscopy", read_spectroscopy_data),
        "phasors": (b"SPF1", "Phasors", read_phasors_data),
    }
    if file_type not in file_info:
        return
    result = read_bin(window, app, *file_info[file_type], active_tab)
    if not result:
        return
    file_name, file_type, *data, metadata = result
    app.reader_data[active_tab]["plots"] = []
    app.reader_data[active_tab]["metadata"] = metadata
    app.reader_data[active_tab]["files"][file_type] = file_name

    # Auto-load laserblood_metadata if a matching JSON exists alongside the .bin
    try:
        bin_dir = os.path.dirname(file_name)
        timestamp = os.path.basename(file_name).split("_")[0]
        pattern = os.path.join(bin_dir, f"{timestamp}_*_laserblood_metadata.json")
        matches = glob.glob(pattern)
        if matches:
            with open(matches[0], "r", encoding="utf-8") as f:
                laserblood_data = json.load(f)
                app.reader_data[active_tab]["laserblood_metadata"] = laserblood_data
                app.reader_data[active_tab]["files"]["laserblood_metadata"] = matches[0]
    except Exception:
        pass

    # Clear decay widgets when loading new data
    for channel in list(app.decay_widgets.keys()):
        if channel in app.decay_widgets:
            app.decay_widgets[channel].clear()

    # Clear cached values for the active tab
    if tab_selected in app.cached_decay_values:
        app.cached_decay_values[tab_selected] = {}

    if file_type == "spectroscopy":
        times, channels_curves = data
        if active_tab == "spectroscopy":
            app.reader_data[active_tab]["data"] = {
                "times": times,
                "channels_curves": channels_curves,
            }
        if active_tab in ("phasors", "fitting"):
            app.reader_data[active_tab]["spectroscopy_metadata"] = metadata
            app.reader_data[active_tab]["data"]["spectroscopy_data"] = {
                "times": times,
                "channels_curves": channels_curves,
            }
    elif file_type == "phasors":
        phasors_data = data[0]
        app.reader_data[active_tab]["data"]["phasors_data"] = phasors_data
        app.reader_data[active_tab]["phasors_metadata"] = metadata


def read_multiple_bin_data(window, app, tab_selected, file_type):
    """
    Opens a multi-select dialog for binary files, validates magic bytes, and
    returns the paths of all valid files (max 4).

    Args:
        window: Parent window for file dialogs.
        app: Main application instance.
        tab_selected: Currently selected tab identifier.
        file_type (str): Type of file ('spectroscopy' or 'phasors').

    Returns:
        list: List of valid file paths (empty if none are valid or selection cancelled).
    """
    dialog = QFileDialog()
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
    filter_pattern = "Bin files (*.bin)"
    dialog.setNameFilter(filter_pattern)
    file_names, _ = dialog.getOpenFileNames(
        window, f"Load multiple {file_type} files (max 4)", "", filter_pattern
    )

    if not file_names:
        return []
    if len(file_names) > 4:
        show_warning_message(
            "Too many files",
            "You can select a maximum of 4 files. Only the first 4 will be loaded.",
        )
        file_names = file_names[:4]

    magic_bytes_map = {"spectroscopy": b"SP01", "phasors": b"SPF1"}
    magic_bytes = magic_bytes_map.get(file_type)
    if not magic_bytes:
        show_warning_message(
            "Invalid file type", f"Unsupported file type: {file_type}"
        )
        return []

    valid_files = []
    invalid_count = 0
    for file_name in file_names:
        try:
            with open(file_name, "rb") as f:
                if f.read(4) == magic_bytes:
                    valid_files.append(file_name)
                else:
                    invalid_count += 1
        except Exception:
            invalid_count += 1

    if invalid_count > 0:
        show_warning_message(
            "Invalid files",
            f"{invalid_count} out of {len(file_names)} selected files are not valid "
            f"{file_type} files. No files were loaded.",
        )
        return []

    return valid_files


def read_multiple_json_data(
    window, app, tab_selected, file_type="laserblood_metadata"
):
    """Reads multiple JSON metadata files (max 4) in phasors/read mode.

    Args:
        window: The parent window for the file dialog.
        app: The main application instance.
        tab_selected (str): The currently active tab identifier.
        file_type (str): The type of JSON file (e.g., 'laserblood_metadata').

    Returns:
        list: List of tuples (file_name, data) for each valid JSON file.
    """
    dialog = QFileDialog()
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
    filter_pattern = "JSON files (*.json)"
    dialog.setNameFilter(filter_pattern)
    file_names, _ = dialog.getOpenFileNames(
        window, f"Load multiple {file_type} files (max 4)", "", filter_pattern
    )

    if not file_names:
        return []

    if len(file_names) > 4:
        show_warning_message(
            "Too many files",
            "You can select a maximum of 4 files. Only the first 4 will be loaded.",
        )
        file_names = file_names[:4]

    valid_results = []
    invalid_count = 0
    for file_name in file_names:
        if not file_name.endswith(".json"):
            invalid_count += 1
            continue
        try:
            with open(file_name, "r") as f:
                data = json.load(f)
                valid_results.append((file_name, data))
        except (json.JSONDecodeError, Exception):
            invalid_count += 1

    if invalid_count > 0:
        show_warning_message(
            "Invalid files",
            f"{invalid_count} out of {len(file_names)} selected files could not be loaded.",
        )

    return valid_results


def read_laserblood_metadata(window, app, tab_selected):
    """Reads LaserBlood-specific metadata from a JSON file.

    Args:
        window: The parent window for the file dialog.
        app: The main application instance.
        tab_selected (str): The currently active tab identifier.
    """
    from components.reader.read_data_utils import get_data_type

    active_tab = get_data_type(tab_selected)
    result = read_json(window, "Laserblood metadata", "laserblood_metadata")
    if None in result:
        return
    file_name, data = result
    app.reader_data[active_tab]["files"]["laserblood_metadata"] = file_name
    app.reader_data[active_tab]["laserblood_metadata"] = data


def read_fitting_data(window, app):
    """Reads fitting results from JSON files (max 4 files).

    Args:
        window: The parent window for the file dialog.
        app: The main application instance.
    """
    dialog = QFileDialog()
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
    filter_pattern = "JSON files (*fitting_result*.json)"
    dialog.setNameFilter(filter_pattern)
    file_names, _ = dialog.getOpenFileNames(
        window, "Load fitting files (max 4)", "", filter_pattern
    )

    if not file_names:
        return

    if len(file_names) > 4:
        show_warning_message(
            "Too many files",
            "You can select a maximum of 4 files. Only the first 4 will be loaded.",
        )
        file_names = file_names[:4]

    # Clear previous fitting data and spectroscopy data
    app.reader_data["fitting"]["files"]["fitting"] = []
    app.reader_data["fitting"]["files"]["spectroscopy"] = ""
    app.reader_data["fitting"]["data"]["fitting_data"] = []
    app.reader_data["fitting"]["data"]["spectroscopy_data"] = {}
    app.reader_data["fitting"]["fitting_metadata"] = []
    app.reader_data["fitting"]["spectroscopy_metadata"] = []

    for channel in list(app.decay_widgets.keys()):
        if channel in app.decay_widgets:
            app.decay_widgets[channel].clear()
    if s.TAB_FITTING in app.cached_decay_values:
        app.cached_decay_values[s.TAB_FITTING] = {}

    valid_data = []
    all_channels = []
    for file_name in file_names:
        if not file_name.endswith(".json"):
            continue
        try:
            with open(file_name, "r") as f:
                data = json.load(f)
                if data:
                    valid_data.append(
                        {
                            "file": file_name,
                            "data": data,
                            "channels": [item["channel"] for item in data],
                        }
                    )
                    all_channels.extend([item["channel"] for item in data])
        except Exception:
            pass

    if valid_data:
        app.reader_data["fitting"]["files"]["fitting"] = [
            item["file"] for item in valid_data
        ]
        app.reader_data["fitting"]["data"]["fitting_data"] = [
            item["data"] for item in valid_data
        ]
        app.reader_data["fitting"]["fitting_metadata"] = [
            item["channels"] for item in valid_data
        ]
        app.reader_data["fitting"]["metadata"]["channels"] = list(set(all_channels))
        app.settings.setValue(
            "fitting_read_last_fitting_files", [item["file"] for item in valid_data]
        )


def read_json(window, file_type, filter_string=None):
    """Opens a file dialog to read a generic JSON file.

    Args:
        window: The parent window for the dialog.
        file_type (str): A description of the file type for the dialog title.
        filter_string (str, optional): A string to filter files by name. Defaults to None.

    Returns:
        tuple: A tuple containing (file_name, data). Returns (None, None) on failure.
    """
    dialog = QFileDialog()
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    if filter_string:
        filter_pattern = f"JSON files (*{filter_string}*.json)"
    else:
        filter_pattern = "JSON files (*.json)"
    dialog.setNameFilter(filter_pattern)
    file_name, _ = dialog.getOpenFileName(
        window,
        f"Load {file_type} file",
        "",
        filter_pattern,
        options=QFileDialog.Option.DontUseNativeDialog,
    )
    if not file_name:
        return None, None
    if not file_name.endswith(".json"):
        show_warning_message(
            "Invalid extension", "Invalid extension. File should be a .json"
        )
        return None, None

    try:
        with open(file_name, "r") as f:
            data = json.load(f)
            return file_name, data
    except json.JSONDecodeError:
        show_warning_message(
            "Invalid JSON", "The file could not be parsed as valid JSON."
        )
        return None, None
    except Exception as e:
        show_warning_message(
            "Error reading file", f"Error reading {file_type} file: {str(e)}"
        )
        return None, None


def read_bin(
    window,
    app,
    magic_bytes,
    file_type,
    read_data_cb,
    tab_selected,
    filter_string=None,
):
    """Generic method to read a binary file after verifying its magic bytes.

    Args:
        window: The parent window for the file dialog.
        app: The main application instance.
        magic_bytes (bytes): The expected magic bytes at the start of the file.
        file_type (str): A description of the file type.
        read_data_cb (function): The callback function to parse the file content.
        tab_selected (str): The currently active tab identifier.
        filter_string (str, optional): A string to filter files by name. Defaults to None.

    Returns:
        The result of the read_data_cb function, or None on failure.
    """
    dialog = QFileDialog()
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    if filter_string:
        filter_pattern = f"Bin files (*{filter_string}*.bin)"
    else:
        filter_pattern = "Bin files (*.bin)"
    dialog.setNameFilter(filter_pattern)
    file_name, _ = dialog.getOpenFileName(
        window,
        f"Load {file_type} file",
        "",
        filter_pattern,
        options=QFileDialog.Option.DontUseNativeDialog,
    )
    if not file_name:
        return None
    if not file_name.endswith(".bin"):
        show_warning_message(
            "Invalid extension", "Invalid extension. File should be a .bin"
        )
        return None

    try:
        with open(file_name, "rb") as f:
            if f.read(4) != magic_bytes:
                show_warning_message(
                    "Invalid file",
                    f"Invalid file. The file is not a valid {file_type} file.",
                )
                return None
            return read_data_cb(f, file_name, file_type, tab_selected, app)
    except Exception:
        show_warning_message(
            "Error reading file", f"Error reading {file_type} file"
        )
        return None


def read_spectroscopy_data(file, file_name, file_type, tab_selected, app):
    """Parses spectroscopy data from an open binary file.

    Args:
        file (file object): The open binary file stream.
        file_name (str): The name of the file.
        file_type (str): The type of file ('spectroscopy').
        tab_selected (str): The currently active tab.
        app: The main application instance.

    Returns:
        tuple or None: (file_name, file_type, times, channel_curves, metadata) or None on error.
    """
    try:
        json_length = struct.unpack("I", file.read(4))[0]
        metadata = json.loads(file.read(json_length).decode("utf-8"))
        channel_curves = {i: [] for i in range(len(metadata["channels"]))}
        times = []
        number_of_channels = len(metadata["channels"])
        while True:
            data = file.read(8)
            if not data:
                break
            time = struct.unpack("d", data)[0]
            times.append(time / 1_000_000_000)
            for i in range(number_of_channels):
                data = file.read(4 * 256)
                if len(data) < 4 * 256:
                    return times, channel_curves
                channel_curves[i].append(np.array(struct.unpack("I" * 256, data)))
        return file_name, "spectroscopy", times, channel_curves, metadata
    except Exception:
        show_warning_message("Error reading file", "Error reading Spectroscopy file")
        return None


def read_phasors_data(file, file_name, file_type, tab_selected, app):
    """Parses phasors data from an open binary file.

    Args:
        file (file object): The open binary file stream.
        file_name (str): The name of the file.
        file_type (str): The type of file ('phasors').
        tab_selected (str): The currently active tab.
        app: The main application instance.

    Returns:
        tuple or None: (file_name, file_type, phasors_data, metadata) or None on error.
    """
    phasors_data = {}
    try:
        json_length = struct.unpack("I", file.read(4))[0]
        metadata = json.loads(file.read(json_length).decode("utf-8"))
        while True:
            bytes_read = file.read(32)
            if not bytes_read:
                break
            try:
                time_ns, channel_name, harmonic_name, g, s = struct.unpack(
                    "QIIdd", bytes_read
                )
            except struct.error:
                show_warning_message(
                    "Error unpacking file", "Error unpacking Phasors file data"
                )
                break
            phasors_data.setdefault(channel_name, {}).setdefault(
                harmonic_name, []
            ).append((g, s))
            app.reader_data["phasors"]["data"]["phasors_data"].setdefault(
                channel_name, {}
            ).setdefault(harmonic_name, []).append((g, s, file_name))
        return file_name, "phasors", phasors_data, metadata
    except Exception:
        show_warning_message("Error reading file", "Error reading Phasors file")
        return None