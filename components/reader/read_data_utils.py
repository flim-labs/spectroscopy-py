"""
read_data_utils.py
==================
Utility and data-transformation methods of the ReadData class:
- get_data_type
- show_warning_message
- has_laser_period_mismatch
- get_fitting_active_channels
- are_spectroscopy_and_fitting_from_same_acquisition
- preloaded_fitting_data
- _average_channels_for_file
- get_phasors_laser_period_ns
- get_phasors_frequency_mhz
- get_spectroscopy_frequency_mhz
- get_frequency_mhz
- get_spectroscopy_file_x_values
"""

import os

import numpy as np
from components.box_message import BoxMessage
from utils.gui_styles import GUIStyles
from utils.helpers import ns_to_mhz
from utils.fitting_utilities import (
    convert_json_serializable_item_into_np_fitting_result,
)
import settings.settings as s

from PyQt6.QtWidgets import QMessageBox


def get_data_type(active_tab):
    """Converts a tab identifier constant to a string representation.

    Args:
        active_tab (str): The tab identifier from settings.

    Returns:
        str: The string representation ('spectroscopy', 'phasors', or 'fitting').
    """
    return {s.TAB_SPECTROSCOPY: "spectroscopy", s.TAB_PHASORS: "phasors"}.get(
        active_tab, "fitting"
    )


def show_warning_message(title, message):
    """Displays a standardized warning message box.

    Args:
        title (str): The title of the message box.
        message (str): The content of the message.
    """
    BoxMessage.setup(
        title, message, QMessageBox.Icon.Warning, GUIStyles.set_msg_box_style()
    )


def has_laser_period_mismatch(reader_data_phasors):
    """
    Check if all loaded files (spectroscopy and phasors) have the same laser_period_ns.

    Args:
        reader_data_phasors (dict): The phasors section of reader_data containing metadata lists.

    Returns:
        bool: True if there's a mismatch (error), False if all match.
    """
    spectroscopy_metadata = reader_data_phasors["spectroscopy_metadata"]
    phasors_metadata = reader_data_phasors["phasors_metadata"]

    spectroscopy_files = reader_data_phasors["files"]["spectroscopy"]
    phasors_files = reader_data_phasors["files"]["phasors"]

    if isinstance(spectroscopy_files, str):
        spectroscopy_files = (
            [spectroscopy_files] if spectroscopy_files.strip() else []
        )
    if isinstance(phasors_files, str):
        phasors_files = [phasors_files] if phasors_files.strip() else []

    valid_metadata_count = 0
    laser_periods = set()

    for i, meta in enumerate(spectroscopy_metadata):
        file_name = (
            spectroscopy_files[i]
            if i < len(spectroscopy_files)
            else f"spectroscopy_file_{i}"
        )
        file_display_name = (
            os.path.basename(file_name) if isinstance(file_name, str) else file_name
        )
        if isinstance(meta, dict) and "laser_period_ns" in meta:
            laser_period = meta["laser_period_ns"]
            laser_periods.add(laser_period)
            valid_metadata_count += 1

    for i, meta in enumerate(phasors_metadata):
        file_name = (
            phasors_files[i] if i < len(phasors_files) else f"phasors_file_{i}"
        )
        file_display_name = (
            os.path.basename(file_name) if isinstance(file_name, str) else file_name
        )
        if isinstance(meta, dict) and "laser_period_ns" in meta:
            laser_period = meta["laser_period_ns"]
            laser_periods.add(laser_period)
            valid_metadata_count += 1

    if len(laser_periods) > 1:
        show_warning_message(
            "Frequency mismatch", "Loaded files must have the same frequency MHz"
        )
        return True

    return False


def get_fitting_active_channels(app):
    """Extracts the list of active channels from loaded fitting data.

    Args:
        app: The main application instance.

    Returns:
        list: A list of active channel indices.
    """
    data = app.reader_data["fitting"]["data"]["fitting_data"]
    if data:
        if isinstance(data, list) and len(data) > 0:
            all_channels = []
            for file_data in data:
                all_channels.extend([item["channel"] for item in file_data])
            return list(set(all_channels))
        elif isinstance(data, dict):
            return [item["channel"] for item in data]
    return []


def are_spectroscopy_and_fitting_from_same_acquisition(app):
    """Checks if the loaded spectroscopy and fitting files are from the same acquisition.

    It compares the active channels in both datasets.

    Args:
        app: The main application instance.

    Returns:
        bool: True if channels match, False otherwise.
    """
    def show_error():
        show_warning_message(
            "Channels mismatch",
            "Active channels mismatching in Spectroscopy file and Fitting file. Files are not from the same acquisition",
        )

    fitting_channels = get_fitting_active_channels(app)
    spectroscopy_metadata = app.reader_data["fitting"]["spectroscopy_metadata"]
    spectroscopy_channels = spectroscopy_metadata["channels"]
    if not (set(fitting_channels) == set(spectroscopy_channels)):
        show_error()
        return False
    return True


def _average_channels_for_file(file_results, file_index, file_name=""):
    """Calculates the average of all channels for a single fitting file.

    Args:
        file_results (list): List of fitting results for all channels in a file.
        file_index (int): Index of the file (for color assignment).
        file_name (str): Name of the file.

    Returns:
        dict: Averaged fitting result with file_index and file_name.
    """
    if not file_results or len(file_results) == 0:
        return None

    valid_results = [r for r in file_results if "error" not in r]
    if not valid_results:
        return None

    min_len_y = min(len(r["y_data"]) for r in valid_results)
    min_len_fitted = min(len(r["fitted_values"]) for r in valid_results)
    min_len_residuals = min(len(r["residuals"]) for r in valid_results)
    min_len_x = min(len(r["x_values"]) for r in valid_results)
    min_len_t = min(len(r["t_data"]) for r in valid_results)

    avg_chi2 = np.mean([r["chi2"] for r in valid_results])
    avg_r2 = (
        np.mean([r.get("r2", 0) for r in valid_results])
        if all("r2" in r for r in valid_results)
        else 0
    )
    output_data = valid_results[0]["output_data"]
    model = valid_results[0]["model"]

    fitted_params_text = ""
    component_num = 1
    while f"component_A{component_num}" in output_data:
        comp = output_data[f"component_A{component_num}"]
        fitted_params_text += f'τ{component_num} = {comp["tau_ns"]:.4f} ns, {comp["percentage"]:.2%} of total\n'
        component_num += 1

    if "component_B" in output_data:
        fitted_params_text += f"B component included\n"

    fitted_params_text += f"X² = {avg_chi2:.4f}\n"
    fitted_params_text += f"Model = {model}\n"
    fitted_params_text += f"R² = {avg_r2:.4f}\n"

    return {
        "x_values": valid_results[0]["x_values"][:min_len_x],
        "t_data": valid_results[0]["t_data"][:min_len_t],
        "y_data": np.mean([r["y_data"][:min_len_y] for r in valid_results], axis=0),
        "fitted_values": np.mean(
            [r["fitted_values"][:min_len_fitted] for r in valid_results], axis=0
        ),
        "residuals": np.mean(
            [r["residuals"][:min_len_residuals] for r in valid_results], axis=0
        ),
        "fitted_params_text": fitted_params_text,
        "output_data": output_data,
        "scale_factor": np.mean([r["scale_factor"] for r in valid_results]),
        "decay_start": valid_results[0]["decay_start"],
        "channel": 0,
        "chi2": avg_chi2,
        "r2": avg_r2,
        "model": model,
        "file_index": file_index,
        "file_name": file_name,
    }


def preloaded_fitting_data(app):
    """Retrieves and parses preloaded fitting data if available.

    For multiple files, calculates the average of all channels per file.

    Args:
        app: The main application instance.

    Returns:
        list or None: A list of averaged fitting results per file, or None if not available.
    """
    fitting_files = app.reader_data["fitting"]["files"]["fitting"]
    has_files = (isinstance(fitting_files, list) and len(fitting_files) > 0) or (
        isinstance(fitting_files, str) and len(fitting_files.strip()) > 0
    )
    if has_files and app.acquire_read_mode == "read":
        fitting_data = app.reader_data["fitting"]["data"]["fitting_data"]
        if isinstance(fitting_data, list) and len(fitting_data) > 0:
            averaged_results = []
            for file_index, file_data in enumerate(fitting_data):
                file_results = convert_json_serializable_item_into_np_fitting_result(
                    file_data
                )
                if len(file_results) > 0:
                    file_name = (
                        os.path.basename(fitting_files[file_index])
                        if isinstance(fitting_files, list)
                        else f"File {file_index + 1}"
                    )
                    averaged_result = _average_channels_for_file(
                        file_results, file_index, file_name
                    )
                    if averaged_result:
                        averaged_results.append(averaged_result)
            return averaged_results
        else:
            results = convert_json_serializable_item_into_np_fitting_result(
                fitting_data
            )
            if results:
                file_name = (
                    os.path.basename(fitting_files)
                    if isinstance(fitting_files, str)
                    else "File 1"
                )
                for result in results:
                    if "error" not in result:
                        result["file_name"] = file_name
                        result["file_index"] = 0
            return results
    return None


def get_phasors_laser_period_ns(app):
    """Retrieves the laser period from the phasors metadata.

    Args:
        app: The main application instance.

    Returns:
        float: The laser period in nanoseconds, or 0.0 if not found.
    """
    metadata = app.reader_data["phasors"]["phasors_metadata"]
    if "laser_period_ns" in metadata:
        return metadata["laser_period_ns"]
    return 0.0


def get_phasors_frequency_mhz(app):
    """Calculates the laser frequency from the phasors metadata.

    Args:
        app: The main application instance.

    Returns:
        float: The frequency in MHz, or 0.0 if not found.
    """
    metadata = app.reader_data["phasors"]["phasors_metadata"]
    if isinstance(metadata, list) and len(metadata) > 0:
        metadata = metadata[0]
    if isinstance(metadata, dict) and "laser_period_ns" in metadata:
        return ns_to_mhz(metadata["laser_period_ns"])
    return 0.0


def get_spectroscopy_frequency_mhz(app):
    """Calculates the laser frequency from the spectroscopy metadata.

    Args:
        app: The main application instance.

    Returns:
        float: The frequency in MHz, or 0.0 if not found.
    """
    metadata = app.reader_data["spectroscopy"]["metadata"]
    if isinstance(metadata, list) and len(metadata) > 0:
        metadata = metadata[0]
    if isinstance(metadata, dict) and "laser_period_ns" in metadata:
        laser_period_ns = metadata["laser_period_ns"]
        if laser_period_ns > 1000:
            laser_period_ns = laser_period_ns / 1000.0
        return ns_to_mhz(laser_period_ns)
    return 0.0


def get_frequency_mhz(app):
    """Gets the laser frequency based on the currently selected tab.

    Args:
        app: The main application instance.

    Returns:
        float: The frequency in MHz.
    """
    if app.tab_selected == s.TAB_SPECTROSCOPY:
        return get_spectroscopy_frequency_mhz(app)
    elif app.tab_selected == s.TAB_PHASORS:
        return get_phasors_frequency_mhz(app)
    elif app.tab_selected == s.TAB_FITTING:
        spectroscopy_metadata = app.reader_data["fitting"].get(
            "spectroscopy_metadata", []
        )
        if isinstance(spectroscopy_metadata, list) and len(spectroscopy_metadata) > 0:
            first_meta = spectroscopy_metadata[0]
            if "laser_period_ns" in first_meta and first_meta["laser_period_ns"] > 0:
                return ns_to_mhz(first_meta["laser_period_ns"])
        return 0.0
    return 0.0


def get_spectroscopy_file_x_values(app):
    """Generates the x-axis values (time in microseconds) for spectroscopy plots from file data.

    Args:
        app: The main application instance.

    Returns:
        np.ndarray or None: An array of x-values, or None if data is not available.
    """
    if app.acquire_read_mode == "read":
        metadata = app.reader_data[get_data_type(app.tab_selected)]["metadata"]
        if metadata and "laser_period_ns" in metadata:
            return np.linspace(0, metadata["laser_period_ns"], 256) / 1_000
    return None