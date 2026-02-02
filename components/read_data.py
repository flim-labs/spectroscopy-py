from functools import partial
import json
import os
import struct
from matplotlib import pyplot as plt
import numpy as np
from components.box_message import BoxMessage
from utils.gui_styles import GUIStyles
from utils.helpers import extract_channel_from_label, ns_to_mhz
from components.input_text_control import InputTextControl
from utils.layout_utilities import clear_layout, hide_layout, show_layout
from utils.messages_utilities import MessagesUtilities
from utils.resource_path import resource_path
from utils.fitting_utilities import (
    convert_json_serializable_item_into_np_fitting_result,
)
import settings.settings as s
from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QApplication,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QGridLayout,
    QCheckBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, QObject, pyqtSlot
from PyQt6.QtGui import QColor, QIcon, QPalette
import pdb
import pprint
from utils.logo_utilities import TitlebarIcon

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class ReadData:
    """A collection of static methods for reading and processing data from files."""

    @staticmethod
    def read_bin_data(window, app, tab_selected, file_type):
        """Reads binary data for spectroscopy or phasors from a .bin file.

        Args:
            window: The parent window for the file dialog.
            app: The main application instance.
            tab_selected (str): The currently active tab identifier.
            file_type (str): The type of data to read ('spectroscopy' or 'phasors').
        """
        active_tab = ReadData.get_data_type(tab_selected)
        file_info = {
            "spectroscopy": (b"SP01", "Spectroscopy", ReadData.read_spectroscopy_data),
            "phasors": (b"SPF1", "Phasors", ReadData.read_phasors_data),
        }
        if file_type not in file_info:
            return
        result = ReadData.read_bin(window, app, *file_info[file_type], active_tab)
        if not result:
            return
        file_name, file_type, *data, metadata = result
        app.reader_data[active_tab]["plots"] = []
        app.reader_data[active_tab]["metadata"] = metadata
        app.reader_data[active_tab]["files"][file_type] = file_name
        
        # Auto-load laserblood_metadata if exists
        try:
            import os, glob, json
            bin_dir = os.path.dirname(file_name)
            timestamp = os.path.basename(file_name).split('_')[0]
            pattern = os.path.join(bin_dir, f"{timestamp}_*_laserblood_metadata.json")
            matches = glob.glob(pattern)
            
            if matches:
                with open(matches[0], 'r', encoding='utf-8') as f:
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
            if active_tab == "phasors" or active_tab == "fitting":
                app.reader_data[active_tab]["spectroscopy_metadata"] = metadata
                app.reader_data[active_tab]["data"]["spectroscopy_data"] = {
                    "times": times,
                    "channels_curves": channels_curves,
                }
        elif file_type == "phasors":
            phasors_data = data[0]
            app.reader_data[active_tab]["data"]["phasors_data"] = phasors_data
            app.reader_data[active_tab]["phasors_metadata"] = metadata

    @staticmethod
    def has_laser_period_mismatch(reader_data_phasors):
        """
        Check if all loaded files (spectroscopy and phasors) have the same laser_period_ns.

        Args:
            reader_data_phasors (dict): The phasors section of reader_data containing metadata lists

        Returns:
            bool: True if there's a mismatch (error), False if all match
        """
        # Combina tutti i metadati da spectroscopy e phasors
        spectroscopy_metadata = reader_data_phasors["spectroscopy_metadata"]
        phasors_metadata = reader_data_phasors["phasors_metadata"]

        # Combina i file corrispondenti (gestisci sia liste che stringhe)
        spectroscopy_files = reader_data_phasors["files"]["spectroscopy"]
        phasors_files = reader_data_phasors["files"]["phasors"]

        # Assicurati che siano liste
        if isinstance(spectroscopy_files, str):
            spectroscopy_files = (
                [spectroscopy_files] if spectroscopy_files.strip() else []
            )
        if isinstance(phasors_files, str):
            phasors_files = [phasors_files] if phasors_files.strip() else []

        # Contatore dei metadati con laser_period_ns valido
        valid_metadata_count = 0
        laser_periods = set()

        # Analizza file spectroscopy
        for i, meta in enumerate(spectroscopy_metadata):
            file_name = (
                spectroscopy_files[i]
                if i < len(spectroscopy_files)
                else f"spectroscopy_file_{i}"
            )
            # Estrai solo il nome del file dal path completo
            file_display_name = (
                os.path.basename(file_name) if isinstance(file_name, str) else file_name
            )
            if isinstance(meta, dict) and "laser_period_ns" in meta:
                laser_period = meta["laser_period_ns"]
                laser_periods.add(laser_period)
                valid_metadata_count += 1

        # Analizza file phasors
        for i, meta in enumerate(phasors_metadata):
            file_name = (
                phasors_files[i] if i < len(phasors_files) else f"phasors_file_{i}"
            )
            # Estrai solo il nome del file dal path completo
            file_display_name = (
                os.path.basename(file_name) if isinstance(file_name, str) else file_name
            )
            if isinstance(meta, dict) and "laser_period_ns" in meta:
                laser_period = meta["laser_period_ns"]
                laser_periods.add(laser_period)
                valid_metadata_count += 1

        # Controllo mismatch
        if len(laser_periods) > 1:
            ReadData.show_warning_message(
                "Frequency mismatch", "Loaded files must have the same frequency MHz"
            )
            return True

        return False

    @staticmethod
    def read_multiple_bin_data(window, app, tab_selected, file_type):
        """
        Select multiple binary files, validate them by checking magic bytes,
        and return the paths of all valid files.

        Args:
            window: Parent window for file dialogs
            app: Main application instance
            tab_selected: Currently selected tab identifier (should be PHASORS)
            file_type (str): Type of file ('spectroscopy' or 'phasors')

        Returns:
            list: List of valid file paths (empty if none are valid or selection canceled)
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
            ReadData.show_warning_message(
                "Too many files",
                "You can select a maximum of 4 files. Only the first 4 will be loaded.",
            )
            file_names = file_names[:4]
        # Validate each file by checking magic bytes
        valid_files = []
        invalid_count = 0
        file_info = {
            "spectroscopy": b"SP01",
            "phasors": b"SPF1",
        }
        magic_bytes = file_info.get(file_type)
        if not magic_bytes:
            ReadData.show_warning_message(
                "Invalid file type", f"Unsupported file type: {file_type}"
            )
            return []

        for file_name in file_names:
            try:
                with open(file_name, "rb") as f:
                    if f.read(4) == magic_bytes:
                        valid_files.append(file_name)
                    else:
                        invalid_count += 1
            except Exception as e:
                invalid_count += 1

        if invalid_count > 0:
            ReadData.show_warning_message(
                "Invalid files",
                f"{invalid_count} out of {len(file_names)} selected files are not valid {file_type} files. No files were loaded.",
            )
            return []

        return valid_files

    @staticmethod
    def get_bin_filter_file_string(file_type):
        """Gets the file filter string for binary file dialogs.

        Args:
            file_type (str): The type of binary file ('spectroscopy' or 'phasors').

        Returns:
            str: The corresponding filter string.
        """
        if file_type == "spectroscopy":
            return "_spectroscopy_"
        elif file_type == "phasors":
            return "phasors-spectroscopy"
        else:
            return None

    @staticmethod
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
        active_tab = ReadData.get_data_type(tab_selected)

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
            ReadData.show_warning_message(
                "Too many files",
                "You can select a maximum of 4 files. Only the first 4 will be loaded.",
            )
            file_names = file_names[:4]

        # Validate and load each file
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
            except json.JSONDecodeError:
                invalid_count += 1
            except Exception as e:
                invalid_count += 1

        if invalid_count > 0:
            ReadData.show_warning_message(
                "Invalid files",
                f"{invalid_count} out of {len(file_names)} selected files could not be loaded.",
            )

        return valid_results

    @staticmethod
    def read_laserblood_metadata(window, app, tab_selected):
        """Reads LaserBlood-specific metadata from a JSON file.

        Args:
            window: The parent window for the file dialog.
            app: The main application instance.
            tab_selected (str): The currently active tab identifier.
        """
        active_tab = ReadData.get_data_type(tab_selected)
        result = ReadData.read_json(
            window, "Laserblood metadata", "laserblood_metadata"
        )
        if None in result:
            return
        file_name, data = result
        app.reader_data[active_tab]["files"]["laserblood_metadata"] = file_name
        app.reader_data[active_tab]["laserblood_metadata"] = data

    @staticmethod
    def get_bin_filter_file_string(file_type):
        """Gets the file filter string for binary file dialogs.

        Args:
            file_type (str): The type of binary file ('spectroscopy' or 'phasors').

        Returns:
            str: The corresponding filter string.
        """
        if file_type == "spectroscopy":
            return "_spectroscopy_"
        elif file_type == "phasors":
            return "phasors-spectroscopy"
        else:
            return None

    @staticmethod
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
            ReadData.show_warning_message(
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

        # Clear decay widgets and cached values
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
            except:
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

            # Salva i file fitting caricati nelle settings
            app.settings.setValue(
                "fitting_read_last_fitting_files", [item["file"] for item in valid_data]
            )

    @staticmethod
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

    @staticmethod
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
                # Multiple files: calculate average of channels for each file
                averaged_results = []
                for file_index, file_data in enumerate(fitting_data):
                    file_results = (
                        convert_json_serializable_item_into_np_fitting_result(file_data)
                    )
                    if len(file_results) > 0:
                        # Get file name from path
                        file_name = (
                            os.path.basename(fitting_files[file_index])
                            if isinstance(fitting_files, list)
                            else f"File {file_index + 1}"
                        )
                        averaged_result = ReadData._average_channels_for_file(
                            file_results, file_index, file_name
                        )
                        if averaged_result:
                            averaged_results.append(averaged_result)
                return averaged_results
            else:
                # Single file
                results = convert_json_serializable_item_into_np_fitting_result(
                    fitting_data
                )
                # Add file_name and file_index to each result
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

    @staticmethod
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

        # Filter out results with errors
        valid_results = [r for r in file_results if "error" not in r]
        if not valid_results:
            return None

        # Find minimum length to handle arrays of different sizes
        min_len_y = min(len(r["y_data"]) for r in valid_results)
        min_len_fitted = min(len(r["fitted_values"]) for r in valid_results)
        min_len_residuals = min(len(r["residuals"]) for r in valid_results)
        min_len_x = min(len(r["x_values"]) for r in valid_results)
        min_len_t = min(len(r["t_data"]) for r in valid_results)

        # Calculate averages with truncated arrays
        avg_chi2 = np.mean([r["chi2"] for r in valid_results])
        # Check if r2 exists in results (may not be present in older saved files)
        avg_r2 = (
            np.mean([r.get("r2", 0) for r in valid_results])
            if all("r2" in r for r in valid_results)
            else 0
        )
        output_data = valid_results[0]["output_data"]
        model = valid_results[0]["model"]

        # Build fitted_params_text like in fitting_utilities.py (without file name)
        fitted_params_text = ""

        # Extract tau components from output_data
        component_num = 1
        while f"component_A{component_num}" in output_data:
            comp = output_data[f"component_A{component_num}"]
            fitted_params_text += f'τ{component_num} = {comp["tau_ns"]:.4f} ns, {comp["percentage"]:.2%} of total\n'
            component_num += 1

        # Add B component
        if "component_B" in output_data:
            # Calculate B percentage (this is approximation from first result)
            fitted_params_text += f"B component included\n"

        fitted_params_text += f"X² = {avg_chi2:.4f}\n"
        fitted_params_text += f"Model = {model}\n"
        fitted_params_text += f"R² = {avg_r2:.4f}\n"

        avg_result = {
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
        return avg_result

    @staticmethod
    def are_spectroscopy_and_fitting_from_same_acquisition(app):
        """Checks if the loaded spectroscopy and fitting files are from the same acquisition.

        It compares the active channels in both datasets.

        Args:
            app: The main application instance.

        Returns:
            bool: True if channels match, False otherwise.
        """

        def show_error():
            ReadData.show_warning_message(
                "Channels mismatch",
                "Active channels mismatching in Spectroscopy file and Fitting file. Files are not from the same acquisition",
            )

        fitting_channels = ReadData.get_fitting_active_channels(app)
        spectroscopy_metadata = app.reader_data["fitting"]["spectroscopy_metadata"]
        spectroscopy_channels = spectroscopy_metadata["channels"]
        if not (set(fitting_channels) == set(spectroscopy_channels)):
            show_error()
            return False
        return True

    @staticmethod
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
        if file_name is not None and not file_name.endswith(".json"):
            ReadData.show_warning_message(
                "Invalid extension", "Invalid extension. File should be a .json"
            )
            return None, None

        try:
            with open(file_name, "r") as f:
                data = json.load(f)
                return file_name, data
        except json.JSONDecodeError:
            ReadData.show_warning_message(
                "Invalid JSON", "The file could not be parsed as valid JSON."
            )
            return None, None
        except Exception as e:
            ReadData.show_warning_message(
                "Error reading file", f"Error reading {file_type} file: {str(e)}"
            )
            return None, None

    @staticmethod
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

    @staticmethod
    def plot_data(app):
        """Plots the loaded data based on the currently selected tab."""
        data_type = ReadData.get_data_type(app.tab_selected)
        if data_type != "phasors":

            spectroscopy_data = (
                app.reader_data[data_type]["data"]
                if data_type == "spectroscopy"
                else app.reader_data[data_type]["data"]["spectroscopy_data"]
            )

            if isinstance(spectroscopy_data, dict):

                if "files_data" in spectroscopy_data:
                    print(
                        f"[DEBUG] files_data length: {len(spectroscopy_data['files_data'])}"
                    )
            metadata = app.reader_data[data_type]["metadata"]
            laser_period_ns = (
                metadata["laser_period_ns"]
                if "laser_period_ns" in metadata
                and metadata["laser_period_ns"] is not None
                else 25
            )
            channels = metadata["channels"] if "channels" in metadata else []

            # Check if we have multi-file data or traditional single-file data
            has_files_data = (
                "files_data" in spectroscopy_data
                and len(spectroscopy_data["files_data"]) > 0
            )
            has_traditional_data = (
                "times" in spectroscopy_data and "channels_curves" in spectroscopy_data
            )

            if (has_files_data or has_traditional_data) and not (metadata == {}):
                ReadData.plot_spectroscopy_data(
                    app,
                    spectroscopy_data.get("times"),
                    spectroscopy_data.get("channels_curves"),
                    laser_period_ns,
                    channels,
                )
                
                # SPECTROSCOPY READ: Set plot titles from binary metadata instead of JSON
                if app.tab_selected == s.TAB_SPECTROSCOPY and app.acquire_read_mode == "read":
                    from utils.channel_name_utils import get_channel_name
                    # Get channel_names from binary metadata
                    binary_metadata = app.reader_data.get("spectroscopy", {}).get("metadata", {})
                    names_for_read = binary_metadata.get("channels_name", {}) if isinstance(binary_metadata, dict) else {}
                    for ch in app.decay_widgets:
                        title = get_channel_name(ch, names_for_read)
                        app.decay_widgets[ch].setTitle(title)

        phasors_metadata = app.reader_data["phasors"]["phasors_metadata"]
        if data_type == "phasors" and len(phasors_metadata) > 0:
            laser_period_ns = phasors_metadata[0]["laser_period_ns"]

            spectroscopy_metadata = app.reader_data["phasors"]["spectroscopy_metadata"]
            all_metadata = spectroscopy_metadata + phasors_metadata
            harmonics_values = []
            for meta in all_metadata:
                h = meta.get("harmonics")
                if isinstance(h, int):
                    harmonics_values.append(h)
                elif isinstance(h, list) and h:
                    harmonics_values.append(max(h))
            max_harmonic = max(harmonics_values)

            # Plot spectroscopy decay curves if multi-file data available
            spectroscopy_data = app.reader_data["phasors"]["data"]["spectroscopy_data"]
            if (
                "files_data" in spectroscopy_data
                and len(spectroscopy_data["files_data"]) > 0
            ):
                # Get channels from first file's metadata
                channels = (
                    spectroscopy_metadata[0]["channels"]
                    if len(spectroscopy_metadata) > 0
                    else []
                )
                ReadData.plot_spectroscopy_data(
                    app,
                    None,  # times not used in multi-file mode
                    None,  # channels_curves not used in multi-file mode
                    laser_period_ns,
                    channels,
                )

            phasors_data = app.reader_data["phasors"]["data"]["phasors_data"]
            grouped_data = ReadData.group_phasors_data_without_channels(phasors_data)
            ReadData.plot_phasors_data(app, grouped_data, max_harmonic, laser_period_ns)

    @staticmethod
    def plot_spectroscopy_data(
        app, times, channels_curves, laser_period_ns, metadata_channels
    ):
        """Plots spectroscopy decay curves on the appropriate widgets.

        Args:
            app: The main application instance.
            times (list): A list of timestamps for the measurements (unused in multi-file mode).
            channels_curves (dict): A dictionary of decay curve data per channel (unused in multi-file mode).
            laser_period_ns (float): The laser period in nanoseconds.
            metadata_channels (list): A list of active channel indices from metadata.
        """
        import pyqtgraph as pg
        from core.plots_controller import PlotsController
        from core.phasors_controller import PhasorsController

        # Check if we're in read mode with multi-file data (works for both PHASORS and FITTING)
        data_type = "phasors" if app.tab_selected == s.TAB_PHASORS else "fitting"
        spectroscopy_data = (
            app.reader_data[data_type]["data"]["spectroscopy_data"]
            if data_type == "fitting"
            else app.reader_data["phasors"]["data"]["spectroscopy_data"]
        )
        is_multi_file = (
            "files_data" in spectroscopy_data
            and len(spectroscopy_data.get("files_data", [])) > 0
        )

        # In FITTING READ mode with multi-file data, collect all unique channels from all files
        if (
            app.tab_selected == s.TAB_FITTING
            and app.acquire_read_mode == "read"
            and is_multi_file
        ):
            metadata_list = app.reader_data[data_type]["spectroscopy_metadata"]
            # Use the first channel from the first file to maintain consistency
            if metadata_list and "channels" in metadata_list[0]:
                app.plots_to_show = [metadata_list[0]["channels"][0]]
        elif app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
            if len(metadata_channels) > 0:
                app.plots_to_show = [metadata_channels[0]]

        if is_multi_file and app.tab_selected in [s.TAB_PHASORS, s.TAB_FITTING]:
            # Multi-file mode: plot each file's curve with a different color
            files_data = spectroscopy_data["files_data"]
            num_bins = 256
            frequency_mhz = ns_to_mhz(laser_period_ns)
            period_ns = (
                1_000 / frequency_mhz if frequency_mhz != 0.0 else laser_period_ns
            )
            # Use bin indices for FITTING READ, time values for PHASORS
            if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                x_values = np.arange(num_bins)
            else:
                x_values = (
                    np.linspace(0, period_ns, num_bins)
                    if app.tab_selected == s.TAB_PHASORS
                    else np.linspace(0, period_ns, num_bins) / 1_000
                )

            # Get metadata for file names
            metadata_list = (
                app.reader_data[data_type]["spectroscopy_metadata"]
                if data_type == "fitting"
                else app.reader_data["phasors"]["spectroscopy_metadata"]
            )

            # Initialize structure to store multi-file plot items for time shift (FITTING READ only)
            if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                if not hasattr(app, "multi_file_plots"):
                    app.multi_file_plots = {}
                if app.tab_selected not in app.multi_file_plots:
                    app.multi_file_plots[app.tab_selected] = {}

            # Clear decay widgets first and add legend
            for ch in app.plots_to_show:
                if ch in app.decay_widgets:
                    widget = app.decay_widgets[ch]
                    widget.clear()
                    # Clear multi-file plots for this channel (FITTING READ only)
                    if (
                        app.tab_selected == s.TAB_FITTING
                        and app.acquire_read_mode == "read"
                    ):
                        if (
                            hasattr(app, "multi_file_plots")
                            and app.tab_selected in app.multi_file_plots
                        ):
                            app.multi_file_plots[app.tab_selected][ch] = []
                    # Add legend if not already present
                    if widget.plotItem.legend is None:
                        legend = widget.addLegend(offset=(10, 10))
                        legend.setLabelTextColor("w")

            # Collect all y_values for caching (sum of all files for lin/log control)
            all_y_values_by_channel = {}
            ticks_by_channel = {}  # Store ticks for each channel

            # Check current lin/log mode for FITTING tab
            from components.lin_log_control import LinLogControl

            current_lin_log_modes = {}
            if app.tab_selected == s.TAB_FITTING:
                for ch in app.plots_to_show:
                    # Get mode from app.lin_log_mode dictionary
                    current_lin_log_modes[ch] = app.lin_log_mode.get(ch, "LIN")

            # Plot each file's data with its own color
            for file_idx, file_data in enumerate(files_data):
                file_channels_curves = file_data["channels_curves"]
                color = PhasorsController.get_color_for_file_index(file_idx)

                # Get file name from metadata or file_data
                file_name = "Unknown"
                if file_idx < len(metadata_list):
                    file_name = metadata_list[file_idx].get(
                        "file_name",
                        os.path.basename(
                            file_data.get("file_path", f"File {file_idx + 1}")
                        ),
                    )
                elif "file_path" in file_data:
                    file_name = os.path.basename(file_data["file_path"])
                else:
                    file_name = f"File {file_idx + 1}"

                for channel, curves in file_channels_curves.items():
                    # In multi-file FITTING READ, map all first channels to the display channel
                    if (
                        app.tab_selected == s.TAB_FITTING
                        and app.acquire_read_mode == "read"
                    ):
                        # Use the first channel from each file's metadata
                        file_metadata = (
                            metadata_list[file_idx]
                            if file_idx < len(metadata_list)
                            else None
                        )
                        if file_metadata and "channels" in file_metadata:
                            # If this is the first channel of the file, map it to plots_to_show[0]
                            if channel == 0:
                                logical_channel = app.plots_to_show[0]
                            else:
                                continue  # Skip other channels in multi-file READ mode
                        else:
                            if channel == 0:
                                logical_channel = app.plots_to_show[0]
                            else:
                                continue
                    else:
                        # Normal mapping for PHASORS: use actual channel index from file
                        logical_channel = channel

                    if logical_channel in app.plots_to_show:
                        y_values = np.sum(curves, axis=0)

                        # Accumulate y_values for caching
                        ch_idx = logical_channel
                        if ch_idx not in all_y_values_by_channel:
                            all_y_values_by_channel[ch_idx] = []
                        all_y_values_by_channel[ch_idx].append(y_values)

                        # Apply time_shift first (from app.time_shifts)
                        time_shift = (
                            0
                            if ch_idx not in app.time_shifts
                            else app.time_shifts[ch_idx]
                        )
                        y_shifted = np.roll(y_values, time_shift)

                        # Apply lin/log transformation based on current mode
                        y_to_plot = y_shifted
                        if ch_idx in current_lin_log_modes:
                            if current_lin_log_modes[ch_idx] == "LOG":
                                ticks, y_to_plot, _ = LinLogControl.calculate_log_mode(
                                    y_shifted
                                )
                                ticks_by_channel[ch_idx] = ticks
                                if ch_idx in app.decay_widgets:
                                    app.decay_widgets[ch_idx].showGrid(
                                        x=False, y=True, alpha=0.3
                                    )
                            else:
                                ticks, y_to_plot = LinLogControl.calculate_lin_mode(
                                    y_shifted
                                )
                                ticks_by_channel[ch_idx] = ticks
                                if ch_idx in app.decay_widgets:
                                    app.decay_widgets[ch_idx].showGrid(x=False, y=False)

                        # Plot with specific color for this file and add to legend
                        if ch_idx in app.decay_widgets:
                            pen = pg.mkPen(color=color, width=2)
                            plot_item = app.decay_widgets[ch_idx].plot(
                                x_values, y_to_plot, pen=pen, name=file_name
                            )
                            # Save plot item with original y_values for time shift (FITTING READ only)
                            if (
                                app.tab_selected == s.TAB_FITTING
                                and app.acquire_read_mode == "read"
                            ):
                                if (
                                    hasattr(app, "multi_file_plots")
                                    and app.tab_selected in app.multi_file_plots
                                ):
                                    app.multi_file_plots[app.tab_selected][
                                        ch_idx
                                    ].append(
                                        {
                                            "plot_item": plot_item,
                                            "y_values": y_values,  # Original values
                                            "file_idx": file_idx,
                                            "file_name": file_name,
                                        }
                                    )

            # Update ticks for each channel after plotting
            for ch_idx, ticks in ticks_by_channel.items():
                if ch_idx in app.decay_widgets:
                    app.decay_widgets[ch_idx].getAxis("left").setTicks([ticks])
                    PlotsController.set_plot_y_range(app.decay_widgets[ch_idx])

            # Cache summed values for lin/log control (sum all files)
            if app.tab_selected != s.TAB_PHASORS:
                for ch_idx, y_values_list in all_y_values_by_channel.items():
                    if len(y_values_list) > 0:
                        summed_y = np.sum(y_values_list, axis=0)
                        app.cached_decay_values[app.tab_selected][ch_idx] = summed_y
        else:
            # Single-file mode (original behavior)
            num_bins = 256
            frequency_mhz = ns_to_mhz(laser_period_ns)
            period_ns = (
                1_000 / frequency_mhz if frequency_mhz != 0.0 else laser_period_ns
            )
            x_values = (
                np.linspace(0, period_ns, num_bins)
                if app.tab_selected == s.TAB_PHASORS
                else np.linspace(0, period_ns, num_bins) / 1_000
            )

            # In FITTING tab READ mode, calculate average of all channels and show single plot
            if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                all_y_values = []
                first_channel = None

                for channel, curves in channels_curves.items():
                    if (
                        channel < len(metadata_channels)
                        and metadata_channels[channel] in app.plots_to_show
                    ):
                        y_values = np.sum(curves, axis=0)
                        all_y_values.append(y_values)
                        if first_channel is None:
                            first_channel = metadata_channels[channel]
                        # Cache individual channel values for fitting
                        app.cached_decay_values[app.tab_selected][
                            metadata_channels[channel]
                        ] = y_values

                # Calculate average and plot only on the first channel widget
                if len(all_y_values) > 0 and first_channel is not None:
                    y_avg = np.mean(all_y_values, axis=0)
                    PlotsController.update_plots(
                        app, first_channel, x_values, y_avg, reader_mode=True
                    )

                    # Hide other channel plots by hiding their parent widgets
                    for channel, curves in channels_curves.items():
                        if channel < len(metadata_channels):
                            ch = metadata_channels[channel]
                            if ch != first_channel and ch in app.plots_to_show:
                                # Hide the entire decay container widget for this channel
                                if ch in app.decay_widgets:
                                    parent_widget = app.decay_widgets[ch].parent()
                                    if parent_widget is not None:
                                        parent_widget.hide()
                                    else:
                                        app.decay_widgets[ch].hide()
            else:
                # Original behavior: plot each channel separately
                for channel, curves in channels_curves.items():
                    if (
                        channel < len(metadata_channels)
                        and metadata_channels[channel] in app.plots_to_show
                    ):
                        y_values = np.sum(curves, axis=0)
                        if app.tab_selected != s.TAB_PHASORS:
                            app.cached_decay_values[app.tab_selected][
                                metadata_channels[channel]
                            ] = y_values
                        PlotsController.update_plots(
                            app,
                            metadata_channels[channel],
                            x_values,
                            y_values,
                            reader_mode=True,
                        )

    @staticmethod
    def group_phasors_data_without_channels(data):
        """Return {harmonic: [(g, s, file_name), ...]} without channel separation."""
        grouped_data = {}
        for channel_data in data.values():
            if not isinstance(channel_data, dict):
                continue
            for harmonic, points in channel_data.items():
                harmonic_bucket = grouped_data.setdefault(harmonic, [])
                for point in points:
                    g, s = point[0], point[1]
                    file_name = point[2] if len(point) >= 3 else ""
                    if file_name is None:
                        file_name = ""
                    harmonic_bucket.append((g, s, str(file_name)))
        return grouped_data

    @staticmethod
    def get_spectroscopy_data_to_fit(app):
        """Prepares spectroscopy data for the fitting process.

        Args:
            app: The main application instance.

        Returns:
            list: A list of dictionaries, each containing the data for one channel to be fitted.
                  In multi-file mode, returns one entry per file per channel.
        """
        spectroscopy_data = app.reader_data["fitting"]["data"]["spectroscopy_data"]
        metadata = app.reader_data["fitting"]["metadata"]

        laser_period_ns = (
            metadata["laser_period_ns"]
            if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None
            else 25
        )
        data = []
        num_bins = 256

        # Check if we have multi-file data
        if (
            "files_data" in spectroscopy_data
            and len(spectroscopy_data["files_data"]) > 0
        ):
            # Multi-file mode: use the actual file times converted to proper units
            files_data = spectroscopy_data["files_data"]
            spectroscopy_metadata = app.reader_data["fitting"]["spectroscopy_metadata"]

            # Use times from first file as reference (converted to ns)
            first_file_times = files_data[0]["times"]
            x_values = np.array(first_file_times) * 1000  # Convert to ns if needed

            for file_idx, file_data in enumerate(files_data):
                file_channels_curves = file_data["channels_curves"]
                file_metadata = (
                    spectroscopy_metadata[file_idx]
                    if file_idx < len(spectroscopy_metadata)
                    else metadata
                )
                file_name = file_metadata.get("file_name", f"File {file_idx + 1}")
                channels = file_metadata["channels"]

                # In multi-file mode, map all first channels to the display channel
                for channel, curves in file_channels_curves.items():
                    # Only process the first channel of each file
                    if channel == 0:
                        y_values = np.sum(curves, axis=0)
                        # Use the display channel from plots_to_show
                        display_channel = (
                            app.plots_to_show[0] if app.plots_to_show else 0
                        )
                        data.append(
                            {
                                "x": x_values,
                                "y": y_values,
                                "title": f"Channel {channels[channel] + 1}",
                                "channel_index": display_channel,
                                "time_shift": 0,
                                "file_index": file_idx,
                                "file_name": file_name,
                            }
                        )
        else:
            # Single-file mode: check if we have actual times data
            if "times" in spectroscopy_data and spectroscopy_data["times"]:
                # Use actual times from data (convert to ns if needed)
                x_values = np.array(spectroscopy_data["times"]) * 1000
            else:
                # Fallback to linspace
                x_values = np.linspace(0, laser_period_ns, num_bins)

            channels_curves = spectroscopy_data.get("channels_curves", {})
            channels = metadata["channels"]

            for channel, curves in channels_curves.items():
                if channels[channel] in app.plots_to_show:
                    y_values = np.sum(curves, axis=0)
                    if app.tab_selected != s.TAB_PHASORS:
                        app.cached_decay_values[app.tab_selected][
                            channels[channel]
                        ] = y_values
                    data.append(
                        {
                            "x": x_values,
                            "y": y_values,
                            "title": "Channel " + str(channels[channel] + 1),
                            "channel_index": channels[channel],
                            "time_shift": 0,
                        }
                    )
        return data

    @staticmethod
    def plot_phasors_data(app, data, harmonics, laser_period_ns):
        """
        Plot phasors data with harmonic analysis.

        Args:
            app: The main application instance.
            data (dict): The phasor data grouped by harmonic {harmonic: [(g, s, file_name), ...]}.
            harmonics (int): Maximum harmonic value.
            laser_period_ns (float): Laser period in nanoseconds.

        This method now handles multi-file data where each point is tagged with its source file.
        """
        from core.controls_controller import ControlsController
        from core.phasors_controller import PhasorsController

        frequency_mhz = ns_to_mhz(laser_period_ns)

        # Clear previous phasors data before loading new files
        PhasorsController.clear_phasors_file_scatters(app)
        PhasorsController.clear_phasors_files_legend(app)
        PhasorsController.hide_phasors_legends(app)

        # Reset all_phasors_points
        app.all_phasors_points = PhasorsController.get_empty_phasors_points()

        # Populate all_phasors_points BEFORE resetting harmonic selector
        # to ensure _update_phasor_plots_for_harmonic has data to work with
        for harmonic, values in data.items():
            app.all_phasors_points[0][harmonic].extend(values)

        if harmonics > 1:
            app.harmonic_selector_shown = True
            ControlsController.show_harmonic_selector(app, harmonics)

        # Now reset harmonic selector (this will trigger _update_phasor_plots_for_harmonic)
        # which will handle drawing points and generating legends
        app.control_inputs[s.HARMONIC_SELECTOR].setCurrentIndex(0)
        # Store the number of harmonics for later use when switching modes
        app.loaded_phasors_harmonics = harmonics

        PhasorsController.generate_phasors_cluster_center(
            app, app.phasors_harmonic_selected
        )
        # Note: draw_points_in_phasors and generate_phasors_legend are called by
        # _update_phasor_plots_for_harmonic which is triggered when harmonic selector is reset
        for i, channel_index in enumerate(app.plots_to_show):
            PhasorsController.draw_lifetime_points_in_phasors(
                app,
                channel_index,
                app.phasors_harmonic_selected,
                laser_period_ns,
                frequency_mhz,
            )

    @staticmethod
    def show_warning_message(title, message):
        """Displays a standardized warning message box.

        Args:
            title (str): The title of the message box.
            message (str): The content of the message.
        """
        BoxMessage.setup(
            title, message, QMessageBox.Icon.Warning, GUIStyles.set_msg_box_style()
        )

    @staticmethod
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
        if file_name is not None and not file_name.endswith(".bin"):
            ReadData.show_warning_message(
                "Invalid extension", "Invalid extension. File should be a .bin"
            )
            return None

        try:
            with open(file_name, "rb") as f:
                if f.read(4) != magic_bytes:
                    ReadData.show_warning_message(
                        "Invalid file",
                        f"Invalid file. The file is not a valid {file_type} file.",
                    )
                    return None
                return read_data_cb(f, file_name, file_type, tab_selected, app)
        except Exception:
            ReadData.show_warning_message(
                "Error reading file", f"Error reading {file_type} file"
            )
            return None

    @staticmethod
    def read_spectroscopy_data(file, file_name, file_type, tab_selected, app):
        """Parses spectroscopy data from an open binary file.

        Args:
            file (file object): The open binary file stream.
            file_name (str): The name of the file.
            file_type (str): The type of file ('spectroscopy').
            tab_selected (str): The currently active tab.
            app: The main application instance.

        Returns:
            tuple or None: A tuple containing file_name, file_type, times, channel_curves, and metadata, or None on error.
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
        except Exception as e:
            ReadData.show_warning_message(
                "Error reading file", "Error reading Spectroscopy file"
            )
            return None

    @staticmethod
    def read_phasors_data(file, file_name, file_type, tab_selected, app):
        """Parses phasors data from an open binary file.

        Args:
            file (file object): The open binary file stream.
            file_name (str): The name of the file.
            file_type (str): The type of file ('phasors').
            tab_selected (str): The currently active tab.
            app: The main application instance.

        Returns:
            tuple or None: A tuple containing file_name, file_type, phasors_data, and metadata, or None on error.
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
                    ReadData.show_warning_message(
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
            ReadData.show_warning_message(
                "Error reading file", "Error reading Phasors file"
            )
            return None

    @staticmethod
    def save_plot_image(plot):
        """Saves a matplotlib plot to an image file (PNG and EPS).

        Args:
            plot (matplotlib.figure.Figure): The plot figure to save.
        """
        dialog = QFileDialog()
        base_path, _ = dialog.getSaveFileName(
            None,
            "Save plot image",
            "",
            "PNG Files (*.png);;EPS Files (*.eps)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )

        def show_success_message():
            info_title, info_msg = MessagesUtilities.info_handler("SavedPlotImage")
            BoxMessage.setup(
                info_title,
                info_msg,
                QMessageBox.Icon.Information,
                GUIStyles.set_msg_box_style(),
            )

        def show_error_message(error):
            ReadData.show_warning_message(
                "Error saving images", f"Error saving plot images: {error}"
            )

        if base_path:
            signals = WorkerSignals()
            signals.success.connect(show_success_message)
            signals.error.connect(show_error_message)
            task = SavePlotTask(plot, base_path, signals)
            QThreadPool.globalInstance().start(task)

    @staticmethod
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
        else:
            return 0.0

    @staticmethod
    def get_phasors_frequency_mhz(app):
        """Calculates the laser frequency from the phasors metadata.

        Args:
            app: The main application instance.

        Returns:
            float: The frequency in MHz, or 0.0 if not found.
        """
        metadata = app.reader_data["phasors"]["phasors_metadata"]
        # Handle both single file (dict) and multiple files (list of dicts)
        if isinstance(metadata, list) and len(metadata) > 0:
            metadata = metadata[0]  # Get first file's metadata
        if isinstance(metadata, dict) and "laser_period_ns" in metadata:
            return ns_to_mhz(metadata["laser_period_ns"])
        return 0.0

    @staticmethod
    def get_spectroscopy_frequency_mhz(app):
        """Calculates the laser frequency from the spectroscopy metadata.

        Args:
            app: The main application instance.

        Returns:
            float: The frequency in MHz, or 0.0 if not found.
        """
        metadata = app.reader_data["spectroscopy"]["metadata"]
        # Handle both single file (dict) and multiple files (list of dicts)
        if isinstance(metadata, list) and len(metadata) > 0:
            metadata = metadata[0]  # Get first file's metadata
        if isinstance(metadata, dict) and "laser_period_ns" in metadata:
            laser_period_ns = metadata["laser_period_ns"]
            # If the value is > 1000, it's likely in picoseconds, convert to ns
            if laser_period_ns > 1000:
                laser_period_ns = laser_period_ns / 1000.0
            freq = ns_to_mhz(laser_period_ns)
            return freq
        return 0.0

    @staticmethod
    def get_frequency_mhz(app):
        """Gets the laser frequency based on the currently selected tab.

        Args:
            app: The main application instance.

        Returns:
            float: The frequency in MHz.
        """
        if app.tab_selected == s.TAB_SPECTROSCOPY:
            freq = ReadData.get_spectroscopy_frequency_mhz(app)
            return freq
        elif app.tab_selected == s.TAB_PHASORS:
            freq = ReadData.get_phasors_frequency_mhz(app)
            return freq
        elif app.tab_selected == s.TAB_FITTING:
            # For fitting tab, get frequency from spectroscopy_metadata (multi-file case)
            spectroscopy_metadata = app.reader_data["fitting"].get(
                "spectroscopy_metadata", []
            )
            if (
                isinstance(spectroscopy_metadata, list)
                and len(spectroscopy_metadata) > 0
            ):
                first_meta = spectroscopy_metadata[0]
                if (
                    "laser_period_ns" in first_meta
                    and first_meta["laser_period_ns"] > 0
                ):
                    from utils.helpers import ns_to_mhz

                    freq = ns_to_mhz(first_meta["laser_period_ns"])
                    return freq
            return 0.0
        else:
            return 0.0

    @staticmethod
    def get_spectroscopy_file_x_values(app):
        """Generates the x-axis values (time in microseconds) for spectroscopy plots from file data.

        Args:
            app: The main application instance.

        Returns:
            np.ndarray or None: An array of x-values, or None if data is not available.
        """
        if app.acquire_read_mode == "read":
            metadata = app.reader_data[ReadData.get_data_type(app.tab_selected)][
                "metadata"
            ]
            if metadata and "laser_period_ns" in metadata:
                x_values = np.linspace(0, metadata["laser_period_ns"], 256) / 1_000
                return x_values
        return None

    def prepare_spectroscopy_data_for_export_img(app):
        """Prepares spectroscopy data for exporting as an image.

        Args:
            app: The main application instance.

        Returns:
            tuple: A tuple containing channels_curves, times, metadata, and channel_names.
        """
        metadata = app.reader_data["spectroscopy"]["metadata"]
        channels_curves = app.reader_data["spectroscopy"]["data"]["channels_curves"]
        times = app.reader_data["spectroscopy"]["data"]["times"]
        
        # Extract channel_names from binary metadata instead of laserblood JSON
        channel_names = metadata.get("channels_name", {}) if isinstance(metadata, dict) else {}
        
        return channels_curves, times, metadata, channel_names

    @staticmethod
    def prepare_phasors_data_for_export_img(app):
        """Prepares phasors and related spectroscopy data for exporting as an image.

        Args:
            app: The main application instance.

        Returns:
            tuple: A tuple containing all necessary data for plotting.
        """
        phasors_data = app.reader_data["phasors"]["data"]["phasors_data"]

        # phasors metadata can be stored as a list (multi-file) or a dict (single file)
        phasors_meta = app.reader_data["phasors"].get(
            "phasors_metadata"
        ) or app.reader_data["phasors"].get("metadata")
        if isinstance(phasors_meta, list):
            meta = phasors_meta[0] if len(phasors_meta) > 0 else {}
        elif isinstance(phasors_meta, dict):
            meta = phasors_meta
        else:
            meta = {}

        laser_period = meta.get("laser_period_ns", 0)
        active_channels = meta.get("channels", [])

        # spectroscopy data can be stored per-file under 'files_data' or as aggregated times/channels_curves
        spectroscopy_section = app.reader_data["phasors"]["data"].get(
            "spectroscopy_data", {}
        )
        if (
            isinstance(spectroscopy_section, dict)
            and "files_data" in spectroscopy_section
        ):
            # multi-file mode: individual file infos will be passed separately when exporting
            spectroscopy_curves = None
            spectroscopy_times = None
        else:
            spectroscopy_curves = (
                spectroscopy_section.get("channels_curves")
                if isinstance(spectroscopy_section, dict)
                else None
            )
            spectroscopy_times = (
                spectroscopy_section.get("times")
                if isinstance(spectroscopy_section, dict)
                else None
            )

        return (
            phasors_data,
            laser_period,
            active_channels,
            spectroscopy_times,
            spectroscopy_curves,
        )


class ReadDataControls:
    """A collection of static methods for managing UI controls in read mode."""

    @staticmethod
    def handle_widgets_visibility(app, read_mode):
        """Shows or hides UI controls based on whether the app is in read mode.

        Args:
            app: The main application instance.
            read_mode (bool): True if the application is in read mode.
        """
        from core.controls_controller import ControlsController

        if not read_mode:
            ControlsController.fit_button_hide(app)
        else:
            if ReadDataControls.fit_button_enabled(app):
                ControlsController.fit_button_show(app)
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(app)
        app.control_inputs["bin_metadata_button"].setVisible(bin_metadata_btn_visible)
        app.control_inputs["start_button"].setVisible(not read_mode)
        app.control_inputs["read_bin_button"].setVisible(read_mode)

        # Export button remains hidden like in main branch - NO EXPORT BUTTON VISIBILITY
        # app.control_inputs["export_button"].setVisible(not read_mode)  # Commented out to match main branch behavior

        # In read mode, always show plot image download button when files are loaded
        # Hide export button in read mode
        if read_mode:
            app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
                bin_metadata_btn_visible
            )
        else:
            # In non-read mode, keep original logic (hidden for fitting tab)
            app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
                bin_metadata_btn_visible and app.tab_selected != s.TAB_FITTING
            )

        # Handle N° Replicate visibility for fitting tab
        if app.tab_selected == s.TAB_FITTING:
            app.control_inputs[s.SETTINGS_REPLICATES].setVisible(not read_mode)
            app.control_inputs["replicates_label"].setVisible(not read_mode)

        app.widgets[s.TOP_COLLAPSIBLE_WIDGET].setVisible(not read_mode)
        app.widgets["collapse_button"].setVisible(not read_mode)
        app.control_inputs[s.SETTINGS_BIN_WIDTH].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_ACQUISITION_TIME].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_FREE_RUNNING].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_CALIBRATION_TYPE].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_CPS_THRESHOLD].setEnabled(not read_mode)
        app.control_inputs["tau"].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_TIME_SPAN].setEnabled(not read_mode)
        app.control_inputs[s.SETTINGS_HARMONIC].setEnabled(not read_mode)
        if app.tab_selected == s.TAB_PHASORS:
            app.control_inputs[s.LOAD_REF_BTN].setVisible(not read_mode)
            if read_mode:
                app.control_inputs[s.LOAD_REF_BTN].hide()
                hide_layout(app.control_inputs["phasors_resolution_container"])
                hide_layout(app.control_inputs["quantize_phasors_container"])
                ControlsController.on_quantize_phasors_changed(app, False)
                app.settings.setValue(s.SETTINGS_QUANTIZE_PHASORS, False)
            else:
                show_layout(app.control_inputs["quantize_phasors_container"])
                if app.quantized_phasors:
                    show_layout(app.control_inputs["phasors_resolution_container"])

    @staticmethod
    def handle_plots_config(app, file_type):
        """Configures channel selection checkboxes based on loaded file metadata.

        Args:
            app: The main application instance.
            file_type (str): The data type ('spectroscopy', 'phasors', etc.).
        """
        if file_type != "phasors":
            file_metadata = app.reader_data[file_type].get("metadata", {})
            if file_metadata.get("channels"):
                app.selected_channels = sorted(file_metadata["channels"])
                app.plots_to_show = app.reader_data[file_type].get("plots", [])
                for i, checkbox in enumerate(app.channel_checkboxes):
                    checkbox.set_checked(i in app.selected_channels)

    @staticmethod
    def plot_data_on_tab_change(app):
        """Handles UI updates and data plotting when the main tab changes in read mode.

        Args:
            app: The main application instance.
        """
        from core.plots_controller import PlotsController
        from core.controls_controller import ControlsController

        file_type = ReadData.get_data_type(app.tab_selected)
        if app.acquire_read_mode == "read":
            ReadDataControls.handle_plots_config(app, file_type)
            PlotsController.clear_plots(app)
            # First try to get frequency from already loaded data
            freq = ReadData.get_frequency_mhz(app)
            # Generate plots - if freq is 0, will use default
            PlotsController.generate_plots(app, freq)
            ControlsController.toggle_intensities_widgets_visibility(app)
            ReadData.plot_data(app)
            # If frequency was 0 before but now we have data, regenerate with correct frequency
            new_freq = ReadData.get_frequency_mhz(app)
            if freq == 0 and new_freq > 0:
                PlotsController.clear_plots(app)
                PlotsController.generate_plots(app, new_freq)
                ControlsController.toggle_intensities_widgets_visibility(app)
                ReadData.plot_data(app)

    @staticmethod
    def read_bin_metadata_enabled(app):
        """Determines if the 'view metadata' button should be enabled.

        Args:
            app: The main application instance.

        Returns:
            bool: True if the button should be enabled, False otherwise.
        """
        data_type = ReadData.get_data_type(app.tab_selected)
        metadata = app.reader_data[data_type]["metadata"]
        if data_type != "phasors":
            return not (metadata == {}) and app.acquire_read_mode == "read"
        else:
            # For phasors, check if either phasors or spectroscopy files are loaded
            phasors_files = app.reader_data[data_type]["files"]["phasors"]
            spectroscopy_files = app.reader_data[data_type]["files"]["spectroscopy"]
            phasors_metadata = app.reader_data[data_type].get("phasors_metadata", [])
            spectroscopy_metadata = app.reader_data[data_type].get(
                "spectroscopy_metadata", []
            )

            # Check if at least one type of file is loaded
            has_phasors = (
                isinstance(phasors_files, list) and len(phasors_files) > 0
            ) or (isinstance(phasors_files, str) and len(phasors_files.strip()) > 0)
            has_spectroscopy = (
                isinstance(spectroscopy_files, list) and len(spectroscopy_files) > 0
            ) or (
                isinstance(spectroscopy_files, str)
                and len(spectroscopy_files.strip()) > 0
            )

            return (has_phasors or has_spectroscopy) and app.acquire_read_mode == "read"

    @staticmethod
    def fit_button_enabled(app):
        """Determines if the 'Fit Data' button should be enabled.

        Args:
            app: The main application instance.

        Returns:
            bool: True if the button should be enabled, False otherwise.
        """
        tab_selected_fitting = app.tab_selected == s.TAB_FITTING
        read_mode = app.acquire_read_mode == "read"
        fitting_files = app.reader_data["fitting"]["files"]["fitting"]
        spectroscopy_file = app.reader_data["fitting"]["files"]["spectroscopy"]
        fitting_file_exists = (
            isinstance(fitting_files, list) and len(fitting_files) > 0
        ) or (isinstance(fitting_files, str) and len(fitting_files.strip()) > 0)
        spectroscopy_file_exists = (
            isinstance(spectroscopy_file, list) and len(spectroscopy_file) > 0
        ) or (isinstance(spectroscopy_file, str) and len(spectroscopy_file.strip()) > 0)
        return (
            tab_selected_fitting
            and read_mode
            and (fitting_file_exists or spectroscopy_file_exists)
        )


class ReaderPopup(QWidget):
    """A popup window for loading data files and selecting plots to display."""

    def __init__(self, window, tab_selected):
        """Initializes the ReaderPopup.

        Args:
            window: The main application window instance.
            tab_selected (str): The identifier of the tab that opened the popup.
        """
        super().__init__()
        self.app = window
        self.tab_selected = tab_selected
        self.widgets = {}
        self.layouts = {}
        self.channels_checkboxes = []
        self.channels_checkbox_first_toggle = True
        self.data_type = ReadData.get_data_type(self.tab_selected)
        self.file_type_checkboxes = {}  # Store radio buttons for file type selection
        self.file_input_containers = {}  # Store containers for each file input
        self.setWindowTitle("Read data")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg=QColor(20, 20, 20))
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # PLOT BUTTON ROW
        plot_btn_row = self.create_plot_btn_layout()
        # LOAD FILE ROW
        load_file_row = self.init_file_load_ui()
        self.layout.addSpacing(10)
        self.layout.insertLayout(1, load_file_row)
        # LOAD CHANNELS GRID
        self.layout.addSpacing(20)
        channels_layout = self.init_channels_layout()
        if channels_layout is not None:
            self.layout.insertLayout(2, channels_layout)

        self.layout.addSpacing(20)
        self.layout.insertLayout(3, plot_btn_row)
        self.setLayout(self.layout)
        self.setStyleSheet(GUIStyles.plots_config_popup_style())
        self.app.widgets[s.READER_POPUP] = self
        self.center_window()

    def create_file_type_selector(self):
        """Creates radio button selector for choosing which file types to load (fitting tab only).
        Exclusive choice between spectroscopy or fitting files.

        Returns:
            QVBoxLayout: The layout containing the radio button controls.
        """
        from PyQt6.QtWidgets import QRadioButton, QButtonGroup

        v_box = QVBoxLayout()
        v_box.setSpacing(10)

        title = QLabel("SELECT FILE TYPE TO LOAD:")
        title.setStyleSheet(
            "font-size: 16px; font-family: 'Montserrat'; font-weight: bold;"
        )
        v_box.addWidget(title)

        radio_layout = QHBoxLayout()
        radio_layout.setSpacing(20)

        # Create button group for exclusive selection
        button_group = QButtonGroup(self)

        # Spectroscopy radio button
        spectroscopy_rb = QRadioButton("Spectroscopy files")
        spectroscopy_rb.setStyleSheet(
            """
            QRadioButton {
                font-size: 14px; 
                font-family: 'Montserrat'; 
                color: white;
            }
            QRadioButton::indicator {
                width: 13px;
                height: 13px;
            }
            QRadioButton::indicator::unchecked {
                border: 2px solid gray;
                background-color: transparent;
                border-radius: 6px;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #DA1212;
                background-color: #DA1212;
                border-radius: 6px;
            }
        """
        )
        # Remove palette approach
        # palette = spectroscopy_rb.palette()
        # palette.setColor(QPalette.ColorRole.Base, QColor("#DA1212"))
        # palette.setColor(QPalette.ColorRole.Button, QColor("#DA1212"))
        # spectroscopy_rb.setPalette(palette)

        # Check which files are loaded to restore the correct selection
        fitting_files = self.app.reader_data["fitting"]["files"]["fitting"]
        spectroscopy_files = self.app.reader_data["fitting"]["files"]["spectroscopy"]
        # Ripristina l'ultima selezione salvata (default: spectroscopy)
        last_selection = self.app.settings.value(
            "fitting_read_last_file_type", "spectroscopy"
        )

        spectroscopy_rb.setChecked(last_selection == "spectroscopy")
        spectroscopy_rb.toggled.connect(
            lambda checked: self.on_file_type_changed("spectroscopy", checked)
        )
        button_group.addButton(spectroscopy_rb)
        self.file_type_checkboxes["spectroscopy"] = spectroscopy_rb
        radio_layout.addWidget(spectroscopy_rb)

        # Fitting radio button
        fitting_rb = QRadioButton("Fitting files")
        fitting_rb.setStyleSheet(
            """
            QRadioButton {
                font-size: 14px; 
                font-family: 'Montserrat'; 
                color: white;
            }
            QRadioButton::indicator {
                width: 13px;
                height: 13px;
            }
            QRadioButton::indicator::unchecked {
                border: 2px solid gray;
                background-color: transparent;
                border-radius: 6px;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #DA1212;
                background-color: #DA1212;
                border-radius: 6px;
            }
        """
        )
        # Remove palette approach
        # palette = fitting_rb.palette()
        # palette.setColor(QPalette.ColorRole.Base, QColor("#DA1212"))
        # palette.setColor(QPalette.ColorRole.Button, QColor("#DA1212"))
        # fitting_rb.setPalette(palette)

        fitting_rb.setChecked(last_selection == "fitting")
        fitting_rb.toggled.connect(
            lambda checked: self.on_file_type_changed("fitting", checked)
        )
        button_group.addButton(fitting_rb)
        self.file_type_checkboxes["fitting"] = fitting_rb
        radio_layout.addWidget(fitting_rb)

        radio_layout.addStretch()
        v_box.addLayout(radio_layout)

        return v_box

    def on_file_type_changed(self, file_type, checked):
        """Handles radio button changes to show/hide file input rows.

        Args:
            file_type (str): The file type ('spectroscopy' or 'fitting').
            checked (bool): Whether this radio button is now checked.
        """
        if not checked:
            return

        # Salva la selezione nelle settings
        self.app.settings.setValue("fitting_read_last_file_type", file_type)

        # For fitting tab with stacked widget, just change the index
        if (
            hasattr(self, "file_type_stack")
            and file_type in self.file_type_stack_indices
        ):
            self.file_type_stack.setCurrentIndex(
                self.file_type_stack_indices[file_type]
            )

        # Control metadata button visibility based on file type selection
        if (
            hasattr(self.app, "control_inputs")
            and "bin_metadata_button" in self.app.control_inputs
        ):
            metadata_button = self.app.control_inputs["bin_metadata_button"]
            if file_type == "fitting":
                # Hide metadata button when "Fitting files" is selected
                metadata_button.setVisible(False)
            elif file_type == "spectroscopy":
                # Show metadata button when "Spectroscopy files" is selected
                metadata_button.setVisible(True)

        # Store the current selection to check later if files were actually loaded
        self.current_file_type_selection = file_type

    def check_and_restore_file_type_selection(self):
        """Check if fitting files are actually loaded, if not restore to spectroscopy selection."""
        if (
            hasattr(self, "current_file_type_selection")
            and self.current_file_type_selection == "fitting"
        ):
            # Check if fitting files are actually loaded
            fitting_files = self.app.reader_data["fitting"]["files"]["fitting"]
            has_fitting_files = (
                isinstance(fitting_files, list) and len(fitting_files) > 0
            ) or (isinstance(fitting_files, str) and len(fitting_files.strip()) > 0)

            if not has_fitting_files:
                # No fitting files loaded, restore to spectroscopy selection
                if "spectroscopy" in self.file_type_checkboxes:
                    self.file_type_checkboxes["spectroscopy"].setChecked(True)
                    # This will trigger on_file_type_changed with spectroscopy=True
            else:
                # Fitting files are loaded, ensure metadata button stays hidden
                if (
                    hasattr(self.app, "control_inputs")
                    and "bin_metadata_button" in self.app.control_inputs
                ):
                    metadata_button = self.app.control_inputs["bin_metadata_button"]
                    metadata_button.setVisible(False)

    def init_file_load_ui(self):
        """Initializes the UI for loading different types of data files.

        Returns:
            QVBoxLayout: The layout containing the file input controls.
        """
        from PyQt6.QtWidgets import QStackedWidget

        v_box = QVBoxLayout()

        # Add radio button selector for fitting tab
        if self.data_type == "fitting":
            selector_layout = self.create_file_type_selector()
            v_box.addLayout(selector_layout)
            v_box.addSpacing(20)

            # Create a stacked widget to hold the two file type containers
            self.file_type_stack = QStackedWidget()
            self.file_type_stack_indices = {}  # Map file_type to stack index

        files = self.app.reader_data[self.data_type]["files"]
        for file_type, file_path in files.items():
            # Exclude laserblood_metadata from all modes (auto-loaded only)
            if file_type == "laserblood_metadata":
                continue

            # Create container for this input row
            container = QWidget()
            container_layout = QVBoxLayout()
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(10)

            if (file_type == "phasors" and self.data_type == "phasors") or (
                file_type == "fitting" and self.data_type == "fitting"
            ):
                input_desc = QLabel(f"LOAD RELATED {file_type.upper()} FILE:")
            elif file_type == "spectroscopy":
                input_desc = QLabel(f"LOAD A {file_type.upper()} FILE:")
            else:
                file_name = file_type.upper().replace("_", " ")
                input_desc = QLabel(f"LOAD A {file_name} FILE:")
            if self.data_type == "phasors" or self.data_type == "fitting":
                input_desc.setText(input_desc.text().replace("FILE", "FILES (MAX 4)"))
            input_desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
            control_row = QHBoxLayout()

            file_extension = (
                ".json"
                if file_type == "fitting" or file_type == "laserblood_metadata"
                else ".bin"
            )

            def on_change(file_type=file_type):
                def callback(text):
                    self.on_loaded_file_change(text, file_type)

                return callback

            display_text = ""
            if isinstance(file_path, list):
                display_text = (
                    file_path[0]
                    if len(file_path) == 1
                    else (
                        f"{len(file_path)} file(s) loaded" if len(file_path) > 1 else ""
                    )
                )
            else:
                display_text = file_path

            _, input = InputTextControl.setup(
                label="",
                placeholder=f"Load {file_extension} file",
                event_callback=on_change(),
                text=display_text,  # Ora sempre stringa
            )
            input.setStyleSheet(GUIStyles.set_input_text_style())
            widget_key = f"load_{file_type}_input"
            self.widgets[widget_key] = input
            load_file_btn = QPushButton()
            load_file_btn.setIcon(QIcon(resource_path("assets/folder-white.png")))
            load_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            GUIStyles.set_start_btn_style(load_file_btn)
            load_file_btn.setFixedHeight(36)
            # Route to appropriate handler based on data type and file type
            if self.data_type == "phasors":
                if file_type in ["spectroscopy", "phasors"]:
                    load_file_btn.clicked.connect(
                        partial(self.on_load_file_btn_clicked_phasors, file_type)
                    )
                elif file_type == "laserblood_metadata":
                    load_file_btn.clicked.connect(
                        partial(
                            self.on_load_file_btn_clicked_phasors_metadata, file_type
                        )
                    )
                else:
                    load_file_btn.clicked.connect(
                        partial(self.on_load_file_btn_clicked, file_type)
                    )
            elif self.data_type == "fitting":
                if file_type == "spectroscopy":
                    # Use main branch logic extended for multi-file support
                    load_file_btn.clicked.connect(
                        partial(
                            self.on_load_file_btn_clicked_main_branch_logic, file_type
                        )
                    )
                elif file_type == "fitting":
                    load_file_btn.clicked.connect(
                        partial(self.on_load_file_btn_clicked, file_type)
                    )
            else:
                load_file_btn.clicked.connect(
                    partial(self.on_load_file_btn_clicked, file_type)
                )

            control_row.addWidget(input)
            control_row.addWidget(load_file_btn)
            container_layout.addWidget(input_desc)
            container_layout.addSpacing(10)
            container_layout.addLayout(control_row)
            container.setLayout(container_layout)

            # Store container for show/hide control
            self.file_input_containers[file_type] = container

            # For fitting tab, add container to stacked widget instead of directly to layout
            if self.data_type == "fitting" and hasattr(self, "file_type_stack"):
                index = self.file_type_stack.addWidget(container)
                self.file_type_stack_indices[file_type] = index
            else:
                # For other tabs, add directly to layout
                v_box.addWidget(container)
                v_box.addSpacing(10)

        # Add the stacked widget to layout for fitting tab
        if self.data_type == "fitting" and hasattr(self, "file_type_stack"):
            v_box.addWidget(self.file_type_stack)
            # Set initial visible widget based on last selection saved in settings
            last_selection = self.app.settings.value(
                "fitting_read_last_file_type", "spectroscopy"
            )

            # Show the correct section based on the saved selection
            if (
                last_selection == "fitting"
                and "fitting" in self.file_type_stack_indices
            ):
                self.file_type_stack.setCurrentIndex(
                    self.file_type_stack_indices["fitting"]
                )
            elif "spectroscopy" in self.file_type_stack_indices:
                self.file_type_stack.setCurrentIndex(
                    self.file_type_stack_indices["spectroscopy"]
                )

        return v_box

    def init_channels_layout(self):
        """Initializes the grid of checkboxes for selecting which channels to plot.

        Returns:
            QVBoxLayout or None: The layout for channel selection, or None if no channels are available.
        """
        from core.controls_controller import ControlsController

        if self.tab_selected == s.TAB_PHASORS:
            return None
        self.channels_checkboxes.clear()
        file_metadata = self.app.reader_data[self.data_type]["metadata"]
        plots_to_show = self.app.reader_data[self.data_type]["plots"]
        if "channels" in file_metadata and file_metadata["channels"] is not None:
            selected_channels = file_metadata["channels"]
            selected_channels.sort()
            self.app.selected_channels = selected_channels
            for i, ch in enumerate(self.app.channel_checkboxes):
                ch.set_checked(i in self.app.selected_channels)
            ControlsController.set_selected_channels_to_settings(self.app)
            if len(plots_to_show) == 0:
                plots_to_show = selected_channels[:2]

            # In FITTING READ mode, show only first channel (will display average)
            if self.data_type == "fitting" and self.app.acquire_read_mode == "read":
                plots_to_show = (
                    [selected_channels[0]] if len(selected_channels) > 0 else []
                )
                # Update plots_to_show before returning
                self.app.plots_to_show = plots_to_show
                self.app.settings.setValue(
                    s.SETTINGS_PLOTS_TO_SHOW, json.dumps(plots_to_show)
                )
                self.app.reader_data[self.data_type]["plots"] = plots_to_show
                # Don't show the channels selection section in fitting read mode
                return None

            self.app.plots_to_show = plots_to_show
            self.app.settings.setValue(
                s.SETTINGS_PLOTS_TO_SHOW, json.dumps(plots_to_show)
            )
            
            # Extract channel_names from binary metadata instead of laserblood JSON
            from utils.channel_name_utils import get_channel_name
            binary_metadata = self.app.reader_data[self.data_type].get("metadata", {})
            channel_names = binary_metadata.get("channels_name", {}) if isinstance(binary_metadata, dict) else {}
            
            channels_layout = QVBoxLayout()
            desc = QLabel("CHOOSE MAX 4 PLOTS TO DISPLAY:")
            desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
            grid = QGridLayout()
            for ch in selected_channels:
                label = get_channel_name(ch, channel_names)
                checkbox, checkbox_wrapper = self.set_checkboxes(label)
                isChecked = ch in plots_to_show
                checkbox.setChecked(isChecked)
                if len(plots_to_show) >= 4 and ch not in plots_to_show:
                    checkbox.setEnabled(False)
                grid.addWidget(checkbox_wrapper)
            channels_layout.addWidget(desc)
            channels_layout.addSpacing(10)
            channels_layout.addLayout(grid)
            self.layouts["ch_layout"] = channels_layout
            return channels_layout
        else:
            return None

    def create_plot_btn_layout(self):
        """Creates the layout containing the 'Plot Data' or 'Fit Data' button.

        Returns:
            QHBoxLayout: The layout with the main action button.
        """
        fitting_data = self.app.reader_data["fitting"]["data"]["fitting_data"]
        spectroscopy_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"]
        has_fitting = (isinstance(fitting_data, list) and len(fitting_data) > 0) or (
            isinstance(fitting_data, dict) and bool(fitting_data)
        )
        has_spectroscopy = bool(spectroscopy_data)
        row_btn = QHBoxLayout()
        # PLOT BTN
        plot_btn = QPushButton("")
        if has_fitting and not has_spectroscopy:
            plot_btn.setText("FIT DATA")
        else:
            plot_btn.setText("PLOT DATA")
        plot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plot_btn.setObjectName("btn")
        GUIStyles.set_stop_btn_style(plot_btn)
        plot_btn.setFixedHeight(40)
        plot_btn.setFixedWidth(200)
        plots_to_show = self.app.reader_data[self.data_type]["plots"]

        # Enable button based on data type
        if self.data_type == "phasors":
            # For phasors mode, check if required files are loaded
            phasors_file = self.app.reader_data["phasors"]["files"]["phasors"]
            spectroscopy_file = self.app.reader_data["phasors"]["files"]["spectroscopy"]
            # Check if files are loaded (handle both string and list formats)
            phasors_loaded = False
            spectroscopy_loaded = False

            if isinstance(phasors_file, list):
                phasors_loaded = len(phasors_file) > 0 and any(
                    f.strip() for f in phasors_file if isinstance(f, str)
                )
            elif isinstance(phasors_file, str):
                phasors_loaded = len(phasors_file.strip()) > 0

            if isinstance(spectroscopy_file, list):
                spectroscopy_loaded = len(spectroscopy_file) > 0 and any(
                    f.strip() for f in spectroscopy_file if isinstance(f, str)
                )
            elif isinstance(spectroscopy_file, str):
                spectroscopy_loaded = len(spectroscopy_file.strip()) > 0

            should_enable = phasors_loaded and spectroscopy_loaded
        else:
            # For other modes, check if there are plots to show
            should_enable = len(plots_to_show) > 0

        plot_btn.setEnabled(should_enable)
        plot_btn.clicked.connect(self.on_plot_data_btn_clicked)
        self.widgets["plot_btn"] = plot_btn
        row_btn.addStretch(1)
        row_btn.addWidget(plot_btn)
        return row_btn

    def remove_channels_grid(self):
        """Removes the channel selection grid from the layout."""
        if "ch_layout" in self.layouts:
            clear_layout(self.layouts["ch_layout"])
            del self.layouts["ch_layout"]

    def set_checkboxes(self, text):
        """Creates a styled checkbox widget for channel selection.

        Args:
            text (str): The label for the checkbox.

        Returns:
            tuple: A tuple containing the QCheckBox and its wrapper QWidget.
        """
        checkbox_wrapper = QWidget()
        checkbox_wrapper.setObjectName(f"simple_checkbox_wrapper")
        row = QHBoxLayout()
        checkbox = QCheckBox(text)
        checkbox.setStyleSheet(
            GUIStyles.set_simple_checkbox_style(color=s.PALETTE_BLUE_1)
        )
        checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        checkbox.toggled.connect(
            lambda state, checkbox=checkbox: self.on_channel_toggled(state, checkbox)
        )
        row.addWidget(checkbox)
        checkbox_wrapper.setLayout(row)
        checkbox_wrapper.setStyleSheet(GUIStyles.checkbox_wrapper_style())
        return checkbox, checkbox_wrapper

    def on_channel_toggled(self, state, checkbox):
        """Handles the toggling of a channel selection checkbox.

        Args:
            state (bool): The new checked state.
            checkbox (QCheckBox): The checkbox that was toggled.
        """
        from core.plots_controller import PlotsController
        from core.controls_controller import ControlsController

        label_text = checkbox.text()
        ch_index = extract_channel_from_label(label_text)
        if state:
            if ch_index not in self.app.plots_to_show:
                self.app.plots_to_show.append(ch_index)
        else:
            if ch_index in self.app.plots_to_show:
                self.app.plots_to_show.remove(ch_index)
        self.app.plots_to_show.sort()
        self.app.settings.setValue(
            s.SETTINGS_PLOTS_TO_SHOW, json.dumps(self.app.plots_to_show)
        )
        self.app.reader_data[self.data_type]["plots"] = self.app.plots_to_show
        if len(self.app.plots_to_show) >= 4:
            for checkbox in self.channels_checkboxes:
                if checkbox.text() != label_text and not checkbox.isChecked():
                    checkbox.setEnabled(False)
        else:
            for checkbox in self.channels_checkboxes:
                checkbox.setEnabled(True)
        if "plot_btn" in self.widgets:
            plot_btn_enabled = len(self.app.plots_to_show) > 0
            self.widgets["plot_btn"].setEnabled(plot_btn_enabled)
        PlotsController.clear_plots(self.app)
        PlotsController.generate_plots(self.app)
        ControlsController.toggle_intensities_widgets_visibility(self.app)
        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)

    def on_loaded_file_change(self, text, file_type):
        """Handles changes to the file path input field.

        Args:
            text (str): The new file path.
            file_type (str): The type of file associated with the input.
        """
        from core.plots_controller import PlotsController
        from core.controls_controller import ControlsController

        if "file(s) loaded" in text:
            return

        if (
            text != self.app.reader_data[self.data_type]["files"][file_type]
            and file_type != "laserblood_metadata"
        ):
            PlotsController.clear_plots(self.app)
            PlotsController.generate_plots(self.app)
            ControlsController.toggle_intensities_widgets_visibility(self.app)
        self.app.reader_data[self.data_type]["files"][file_type] = text

        # Update FIT button visibility when files change
        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)

    def on_load_file_btn_clicked(self, file_type):
        """Handles the click event for the 'load file' button.

        Args:
            file_type (str): The type of file to load.
        """
        from core.controls_controller import ControlsController

        # Clear the other file type when loading (fitting tab only)
        if self.data_type == "fitting":
            if file_type == "spectroscopy":
                self.app.reader_data["fitting"]["files"]["fitting"] = ""
                self.app.reader_data["fitting"]["data"]["fitting_data"] = []
            elif file_type == "fitting":
                self.app.reader_data["fitting"]["files"]["spectroscopy"] = ""
                self.app.reader_data["fitting"]["data"]["spectroscopy_data"] = {}

        if file_type == "laserblood_metadata":
            ReadData.read_laserblood_metadata(self, self.app, self.tab_selected)
        if file_type == "fitting":
            ReadData.read_fitting_data(self, self.app)
            # After loading fitting data, ensure metadata button remains hidden
            if (
                hasattr(self.app, "control_inputs")
                and "bin_metadata_button" in self.app.control_inputs
            ):
                metadata_button = self.app.control_inputs["bin_metadata_button"]
                metadata_button.setVisible(False)
        else:
            ReadData.read_bin_data(self, self.app, self.tab_selected, file_type)
        file_path = self.app.reader_data[self.data_type]["files"][file_type]
        file_name = (
            file_path[0]
            if isinstance(file_path, list) and len(file_path) > 0
            else file_path if isinstance(file_path, str) else ""
        )
        has_files = (isinstance(file_path, list) and len(file_path) > 0) or (
            isinstance(file_path, str) and len(file_path) > 0
        )
        if has_files:
            bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(
                self.app
            )
            # For fitting files, always keep metadata button hidden
            if file_type == "fitting":
                self.app.control_inputs["bin_metadata_button"].setVisible(False)
            else:
                self.app.control_inputs["bin_metadata_button"].setVisible(
                    bin_metadata_btn_visible
                )
            self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
                bin_metadata_btn_visible and self.tab_selected != s.TAB_FITTING
            )
            widget_key = f"load_{file_type}_input"
            display_name = (
                f"{len(file_path)} file(s) loaded"
                if isinstance(file_path, list) and len(file_path) > 1
                else file_name
            )
            self.widgets[widget_key].setText(display_name)
            if file_type != "laserblood_metadata":
                self.remove_channels_grid()
                channels_layout = self.init_channels_layout()
                if channels_layout is not None:
                    self.layout.insertLayout(2, channels_layout)
                # Update plot button enabled state after channels are initialized
                if "plot_btn" in self.widgets:
                    plots_to_show = self.app.reader_data[self.data_type]["plots"]
                    if self.data_type == "phasors":
                        phasors_file = self.app.reader_data["phasors"]["files"][
                            "phasors"
                        ]
                        spectroscopy_file = self.app.reader_data["phasors"]["files"][
                            "spectroscopy"
                        ]
                        phasors_loaded = (
                            isinstance(phasors_file, list) and len(phasors_file) > 0
                        ) or (
                            isinstance(phasors_file, str)
                            and len(phasors_file.strip()) > 0
                        )
                        spectroscopy_loaded = (
                            isinstance(spectroscopy_file, list)
                            and len(spectroscopy_file) > 0
                        ) or (
                            isinstance(spectroscopy_file, str)
                            and len(spectroscopy_file.strip()) > 0
                        )
                        should_enable = phasors_loaded and spectroscopy_loaded
                    else:
                        should_enable = len(plots_to_show) > 0
                    self.widgets["plot_btn"].setEnabled(should_enable)
        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)
        if "plot_btn" in self.widgets:
            fitting_data = self.app.reader_data["fitting"]["data"]["fitting_data"]
            spectroscopy_data = self.app.reader_data["fitting"]["data"][
                "spectroscopy_data"
            ]
            has_fitting = (
                isinstance(fitting_data, list) and len(fitting_data) > 0
            ) or (isinstance(fitting_data, dict) and bool(fitting_data))
            has_spectroscopy = bool(spectroscopy_data)
            if has_fitting and not has_spectroscopy:
                self.widgets["plot_btn"].setText("FIT DATA")
            else:
                self.widgets["plot_btn"].setText("PLOT DATA")

    def on_load_file_btn_clicked_main_branch_logic(self, file_type):
        """
        Handle file load button click with automatic multi-file logic.
        Always uses multi-file approach to support automatic fitting calculations.
        """
        from core.controls_controller import ControlsController

        # Always use multi-file mode with automatic fitting calculations
        # Clear fitting data when loading new spectroscopy files
        self.app.reader_data["fitting"]["files"]["fitting"] = ""
        self.app.reader_data["fitting"]["data"]["fitting_data"] = []

        # Use multi-file logic that includes automatic fitting
        self.on_load_file_btn_clicked_fitting_spectroscopy(file_type)

        # Update UI controls after loading
        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)

        if "plot_btn" in self.widgets:
            spectroscopy_files = self.app.reader_data["fitting"]["files"][
                "spectroscopy"
            ]
            # Handle both string and list formats
            if isinstance(spectroscopy_files, list):
                has_spectroscopy = len(spectroscopy_files) > 0
            else:
                has_spectroscopy = (
                    spectroscopy_files and len(spectroscopy_files.strip()) > 0
                )
            self.widgets["plot_btn"].setEnabled(has_spectroscopy)
            if has_spectroscopy:
                self.widgets["plot_btn"].setText("PLOT DATA")
                ControlsController.fit_button_show(self.app)

    def on_load_file_btn_clicked_fitting_spectroscopy(self, file_type):
        """
        Handle file load button click event for spectroscopy files in FITTING tab.
        Allows multiple file selection (up to 4 files), validation, and data accumulation.

        Args:
            file_type (str): Type of file to load (should be 'spectroscopy')

        Returns:
            None: Reads multiple selected files, accumulates data, and updates the UI
        """
        from core.controls_controller import ControlsController

        # Read multiple bin files (up to 4)
        valid_files = ReadData.read_multiple_bin_data(
            self, self.app, self.tab_selected, file_type
        )
        if not valid_files:
            return

        # Clear fitting data when loading new spectroscopy files
        self.app.reader_data["fitting"]["files"]["fitting"] = ""
        self.app.reader_data["fitting"]["data"]["fitting_data"] = []

        # Clear previous spectroscopy data
        self.app.reader_data["fitting"]["files"]["spectroscopy"] = []
        self.app.reader_data["fitting"]["spectroscopy_metadata"] = []
        self.app.reader_data["fitting"]["laserblood_metadata"] = []  # Reset auto-loaded metadata
        self.app.reader_data["fitting"]["data"]["spectroscopy_data"] = {
            "files_data": []
        }

        # Clear decay widgets and cached values
        for channel in list(self.app.decay_widgets.keys()):
            if channel in self.app.decay_widgets:
                self.app.decay_widgets[channel].clear()

        if s.TAB_FITTING in self.app.cached_decay_values:
            self.app.cached_decay_values[s.TAB_FITTING] = {}

        # Set the files list
        self.app.reader_data["fitting"]["files"]["spectroscopy"] = valid_files

        # Read and accumulate data from each valid file
        magic_bytes = b"SP01"

        for file_path in valid_files:
            try:
                with open(file_path, "rb") as f:
                    if f.read(4) == magic_bytes:
                        result = ReadData.read_spectroscopy_data(
                            f, file_path, file_type, self.tab_selected, self.app
                        )
                        if result:
                            (
                                file_name,
                                file_type_result,
                                times,
                                channels_curves,
                                metadata,
                            ) = result

                            # Add file_name to metadata for multi-file tracking
                            metadata["file_name"] = os.path.basename(file_path)

                            # Accumulate metadata
                            self.app.reader_data["fitting"][
                                "spectroscopy_metadata"
                            ].append(metadata)
                            
                            # Auto-load laserblood_metadata if exists (for spectroscopy files)
                            import glob
                            file_dir = os.path.dirname(file_path)
                            file_base = os.path.basename(file_path).replace('.bin', '')
                            # Extract timestamp (format: YYYYMMDD_HHMMSS)
                            timestamp = '_'.join(file_base.split('_')[:2])
                            
                            # Search for matching metadata file
                            metadata_pattern = os.path.join(file_dir, f"{timestamp}_*_laserblood_metadata.json")
                            metadata_files = glob.glob(metadata_pattern)
                            
                            if metadata_files:
                                metadata_file = metadata_files[0]
                                try:
                                    import json
                                    with open(metadata_file, 'r') as mf:
                                        auto_loaded_metadata = json.load(mf)
                                        
                                        # Initialize laserblood_metadata list if not exists or convert dict to list
                                        if "laserblood_metadata" not in self.app.reader_data["fitting"]:
                                            self.app.reader_data["fitting"]["laserblood_metadata"] = []
                                        elif not isinstance(self.app.reader_data["fitting"]["laserblood_metadata"], list):
                                            self.app.reader_data["fitting"]["laserblood_metadata"] = []
                                        
                                        # Append metadata to list (only for internal use, not shown in UI)
                                        self.app.reader_data["fitting"]["laserblood_metadata"].append(auto_loaded_metadata)
                                        
                                        # Extract and update channel_names in app.channel_names
                                        from utils.channel_name_utils import extract_channel_names_from_metadata
                                        channel_names = extract_channel_names_from_metadata(auto_loaded_metadata)
                                        if channel_names:
                                            # Update app.channel_names with custom names from metadata
                                            self.app.channel_names.update(channel_names)
                                except Exception as e:
                                    pass

                            # Store per-file data
                            if (
                                "files_data"
                                not in self.app.reader_data["fitting"]["data"][
                                    "spectroscopy_data"
                                ]
                            ):
                                self.app.reader_data["fitting"]["data"][
                                    "spectroscopy_data"
                                ]["files_data"] = []
                            self.app.reader_data["fitting"]["data"][
                                "spectroscopy_data"
                            ]["files_data"].append(
                                {
                                    "file_path": file_path,
                                    "times": times,
                                    "channels_curves": channels_curves,
                                }
                            )
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
                continue

        # Convert files_data to times and channels_curves for plotting compatibility
        # Average all files and all curves within each channel
        files_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"].get(
            "files_data", []
        )
        if len(files_data) > 0:
            import numpy as np

            # Get metadata from first file
            first_metadata = self.app.reader_data["fitting"]["spectroscopy_metadata"][0]
            laser_period_ns = first_metadata.get("laser_period_ns", 25)
            num_bins = 256

            # Create unified time array
            unified_times = np.linspace(0, laser_period_ns, num_bins)

            # Collect all curves for each channel across all files
            all_channels_data = {}

            for file_entry in files_data:
                file_times = file_entry["times"]
                file_channels_curves = file_entry["channels_curves"]

                for channel_idx, curves_list in file_channels_curves.items():
                    if channel_idx not in all_channels_data:
                        all_channels_data[channel_idx] = []

                    # Each file has multiple curves (acquisitions) for this channel
                    for curve in curves_list:
                        # Interpolate curve to unified time array if needed
                        if len(file_times) == len(curve):
                            interp_curve = np.interp(
                                unified_times, np.array(file_times) * 1000, curve
                            )
                            all_channels_data[channel_idx].append(interp_curve)
                        else:
                            # If times don't match, just use the curve as is
                            all_channels_data[channel_idx].append(curve)
            # Keep files_data intact for multi-file visualization
            # The plotting logic will handle showing individual curves with different colors
            self.app.reader_data["fitting"]["data"]["spectroscopy_data"][
                "times"
            ] = unified_times.tolist()
            self.app.reader_data["fitting"]["metadata"] = first_metadata

        # Update UI with loaded files count
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self.app)
        self.app.control_inputs["bin_metadata_button"].setVisible(
            bin_metadata_btn_visible
        )
        self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
            False
        )  # Not visible for fitting tab

        widget_key = f"load_{file_type}_input"
        display_text = f"{len(valid_files)} file(s) loaded"
        self.widgets[widget_key].setText(display_text)

        # Salva i file caricati nelle settings
        self.app.settings.setValue("fitting_read_last_spectroscopy_files", valid_files)

        # Rebuild channels grid
        self.remove_channels_grid()
        channels_layout = self.init_channels_layout()
        if channels_layout is not None:
            self.layout.insertLayout(2, channels_layout)

        # Update plot button enabled state
        if "plot_btn" in self.widgets:
            spectroscopy_files = self.app.reader_data["fitting"]["files"][
                "spectroscopy"
            ]
            has_spectroscopy = (
                isinstance(spectroscopy_files, list) and len(spectroscopy_files) > 0
            )

            if (
                len(
                    self.app.reader_data["fitting"]["data"]["spectroscopy_data"].get(
                        "files_data", []
                    )
                )
                > 0
            ):
                first_file = self.app.reader_data["fitting"]["data"][
                    "spectroscopy_data"
                ]["files_data"][0]
            self.widgets["plot_btn"].setEnabled(has_spectroscopy)
            if has_spectroscopy:
                self.widgets["plot_btn"].setText("PLOT DATA")
                ControlsController.fit_button_show(self.app)

    def auto_start_fitting_for_loaded_files(self):
        """Automatically start fitting calculations for loaded spectroscopy files."""
        from core.controls_controller import ControlsController
        from PyQt6.QtCore import QTimer

        # Use a timer to delay the fitting start, allowing the UI to update first
        QTimer.singleShot(500, self._delayed_fitting_start)

    def _delayed_fitting_start(self):
        """Start fitting calculations with a slight delay to allow UI updates."""
        from core.controls_controller import ControlsController

        try:
            ControlsController.on_fit_btn_click(self.app)
        except Exception as e:
            import traceback

            traceback.print_exc()

    def on_load_file_btn_clicked_phasors_metadata(
        self, file_type="laserblood_metadata"
    ):
        """Handle metadata file load button click for phasors mode with multi-selection.

        Args:
            file_type (str): Type of metadata file to load.
        """
        from core.controls_controller import ControlsController

        valid_results = ReadData.read_multiple_json_data(
            self, self.app, self.tab_selected, file_type
        )

        if not valid_results:
            return

        # Store metadata files as list
        self.app.reader_data[self.data_type]["files"][file_type] = [
            result[0] for result in valid_results
        ]

        # Store metadata data (list of metadata dicts)
        self.app.reader_data[self.data_type][file_type] = [
            result[1] for result in valid_results
        ]

        # Update UI
        widget_key = f"load_{file_type}_input"
        if len(valid_results) == 1:
            display_text = valid_results[0][0]
        else:
            display_text = f"{len(valid_results)} file(s) loaded"

        self.widgets[widget_key].setText(display_text)

        # Update visibility
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self.app)
        self.app.control_inputs["bin_metadata_button"].setVisible(
            bin_metadata_btn_visible
        )
        self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
            bin_metadata_btn_visible and self.tab_selected != s.TAB_FITTING
        )

    def on_load_file_btn_clicked_phasors(self, file_type):
        """
        Handle file load button click event specifically for phasors files in PHASORS mode.
        Allows multiple file selection, validation, and data accumulation.

        Args:
            file_type (str): Type of file to load ('spectroscopy' or 'phasors')

        Returns:
        None: Reads multiple selected files, accumulates data, and updates the UI
        """
        from core.controls_controller import ControlsController

        valid_files = ReadData.read_multiple_bin_data(
            self, self.app, self.tab_selected, file_type
        )
        if not valid_files:
            return

        # Clear previous data when loading new files
        # This ensures that each new file selection replaces the previous one
        self.app.reader_data[self.data_type]["files"][file_type] = []
        if file_type == "phasors":
            self.app.reader_data[self.data_type]["phasors_metadata"] = []
            self.app.reader_data[self.data_type]["data"]["phasors_data"] = {}
        elif file_type == "spectroscopy":
            self.app.reader_data[self.data_type]["spectroscopy_metadata"] = []
            self.app.reader_data[self.data_type]["laserblood_metadata"] = []  # Reset auto-loaded metadata
            self.app.reader_data[self.data_type]["data"]["spectroscopy_data"] = {
                "files_data": []
            }

        # Set the files list
        self.app.reader_data[self.data_type]["files"][file_type] = valid_files

        # Leggi e accumula dati da ciascun file valido
        magic_bytes = b"SP01" if file_type == "spectroscopy" else b"SPF1"
        read_function = (
            ReadData.read_spectroscopy_data
            if file_type == "spectroscopy"
            else ReadData.read_phasors_data
        )

        for file_path in valid_files:
            try:
                with open(file_path, "rb") as f:
                    if f.read(4) == magic_bytes:  # Rivalida (opzionale, già fatto)
                        result = read_function(
                            f, file_path, file_type, self.tab_selected, self.app
                        )
                        if result:
                            file_name, file_type_result, *data, metadata = result

                            # Accumula metadata
                            if file_type == "spectroscopy":
                                self.app.reader_data[self.data_type][
                                    "spectroscopy_metadata"
                                ].append(metadata)
                                
                                # Auto-load laserblood_metadata if exists (for spectroscopy files)
                                import glob
                                file_dir = os.path.dirname(file_path)
                                file_base = os.path.basename(file_path).replace('.bin', '')
                                # Extract timestamp (format: YYYYMMDD_HHMMSS)
                                timestamp = '_'.join(file_base.split('_')[:2])
                                
                                # Search for matching metadata file
                                metadata_pattern = os.path.join(file_dir, f"{timestamp}_*_laserblood_metadata.json")
                                metadata_files = glob.glob(metadata_pattern)
                                
                                if metadata_files:
                                    metadata_file = metadata_files[0]
                                    try:
                                        import json
                                        with open(metadata_file, 'r') as mf:
                                            auto_loaded_metadata = json.load(mf)
                                            
                                            # Initialize laserblood_metadata list if not exists or convert dict to list
                                            if "laserblood_metadata" not in self.app.reader_data[self.data_type]:
                                                self.app.reader_data[self.data_type]["laserblood_metadata"] = []
                                            elif not isinstance(self.app.reader_data[self.data_type]["laserblood_metadata"], list):
                                                self.app.reader_data[self.data_type]["laserblood_metadata"] = []
                                            
                                            # Append metadata to list (only for internal use, not shown in UI)
                                            self.app.reader_data[self.data_type]["laserblood_metadata"].append(auto_loaded_metadata)
                                            
                                            # Extract and update channel_names in app.channel_names
                                            from utils.channel_name_utils import extract_channel_names_from_metadata
                                            channel_names = extract_channel_names_from_metadata(auto_loaded_metadata)
                                            if channel_names:
                                                # Update app.channel_names with custom names from metadata
                                                self.app.channel_names.update(channel_names)
                                    except Exception as e:
                                        pass
                                        
                            elif file_type == "phasors":
                                self.app.reader_data[self.data_type][
                                    "phasors_metadata"
                                ].append(metadata)

                            # Accumula dati
                            if file_type == "spectroscopy":
                                times, channels_curves = data
                                # Store per-file data as list instead of accumulating
                                if (
                                    "files_data"
                                    not in self.app.reader_data[self.data_type]["data"][
                                        "spectroscopy_data"
                                    ]
                                ):
                                    self.app.reader_data[self.data_type]["data"][
                                        "spectroscopy_data"
                                    ]["files_data"] = []
                                self.app.reader_data[self.data_type]["data"][
                                    "spectroscopy_data"
                                ]["files_data"].append(
                                    {
                                        "file_path": file_path,
                                        "times": times,
                                        "channels_curves": channels_curves,
                                    }
                                )
                            elif file_type == "phasors":
                                phasors_data = data[0]
                                for ch, harmonics in phasors_data.items():
                                    if (
                                        ch
                                        not in self.app.reader_data[self.data_type][
                                            "data"
                                        ]["phasors_data"]
                                    ):
                                        self.app.reader_data[self.data_type]["data"][
                                            "phasors_data"
                                        ][ch] = {}
                                    for h, points in harmonics.items():
                                        if (
                                            h
                                            not in self.app.reader_data[self.data_type][
                                                "data"
                                            ]["phasors_data"][ch]
                                        ):
                                            self.app.reader_data[self.data_type][
                                                "data"
                                            ]["phasors_data"][ch][h] = []
                                            self.app.reader_data[self.data_type][
                                                "data"
                                            ]["phasors_data"][ch][h].extend(
                                                [
                                                    (p[0], p[1], file_path)
                                                    for p in points
                                                ]
                                            )
            except Exception as e:
                ReadData.show_warning_message(
                    "Error reading file", f"Error reading {file_path}: {str(e)}"
                )

        # Aggiorna UI
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self.app)
        self.app.control_inputs["bin_metadata_button"].setVisible(
            bin_metadata_btn_visible
        )
        self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
            bin_metadata_btn_visible and self.tab_selected != s.TAB_FITTING
        )
        widget_key = f"load_{file_type}_input"
        # Modifica: mostra il numero di file selezionati nell'operazione corrente
        display_text = f"{len(valid_files)} file(s) loaded"
        self.widgets[widget_key].setText(display_text)

        if "plot_btn" in self.widgets:
            phasors_files = self.app.reader_data["phasors"]["files"]["phasors"]
            spectroscopy_files = self.app.reader_data["phasors"]["files"][
                "spectroscopy"
            ]
            both_files_present = len(phasors_files) > 0 and len(spectroscopy_files) > 0
            self.widgets["plot_btn"].setEnabled(both_files_present)

    def errors_in_data(self, file_type):
        """Checks for data consistency errors, like channel mismatches between files.

        Args:
            file_type (str): The data type to check.

        Returns:
            bool: True if an error is found, False otherwise.
        """
        if file_type == "fitting":
            file_fitting = self.app.reader_data["fitting"]["files"]["fitting"]
            file_spectroscopy = self.app.reader_data["fitting"]["files"]["spectroscopy"]
            has_fitting = (
                isinstance(file_fitting, list) and len(file_fitting) > 0
            ) or (isinstance(file_fitting, str) and len(file_fitting.strip()) > 0)
            has_spectroscopy = (
                isinstance(file_spectroscopy, list) and len(file_spectroscopy) > 0
            ) or (
                isinstance(file_spectroscopy, str)
                and len(file_spectroscopy.strip()) > 0
            )
            if not has_fitting or not has_spectroscopy:
                return False
            channels = ReadData.get_fitting_active_channels(self.app)
            return not (
                ReadData.are_spectroscopy_and_fitting_from_same_acquisition(self.app)
            )
        elif file_type == "phasors":
            return ReadData.has_laser_period_mismatch(self.app.reader_data["phasors"])
        return False

    def on_plot_data_btn_clicked(self):
        """Handles the click event for the main 'Plot Data' or 'Fit Data' button."""
        from core.controls_controller import ControlsController
        from core.plots_controller import PlotsController

        file_type = self.data_type
        if self.errors_in_data(file_type):
            return
        fitting_data = self.app.reader_data["fitting"]["data"]["fitting_data"]
        spectroscopy_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"]
        has_fitting = (isinstance(fitting_data, list) and len(fitting_data) > 0) or (
            isinstance(fitting_data, dict) and bool(fitting_data)
        )
        has_spectroscopy = bool(spectroscopy_data)
        if has_fitting and not has_spectroscopy:
            ControlsController.on_fit_btn_click(self.app)
        else:
            # Regenerate plots with correct frequency from loaded files
            freq = ReadData.get_frequency_mhz(self.app)
            if freq > 0:
                PlotsController.clear_plots(self.app)
                PlotsController.generate_plots(self.app, freq)
                ControlsController.toggle_intensities_widgets_visibility(self.app)
            ReadData.plot_data(self.app)

            # Show FIT button if fitting is enabled after plotting
            if ReadDataControls.fit_button_enabled(self.app):
                ControlsController.fit_button_show(self.app)
            else:
                ControlsController.fit_button_hide(self.app)
        self.close()

    def closeEvent(self, event):
        """Handle window close event to restore file type selection if needed."""
        # Check if fitting files selection was made but no files were loaded
        self.check_and_restore_file_type_selection()
        super().closeEvent(event)

    def center_window(self):
        """Centers the popup window on the primary screen."""
        self.setMinimumWidth(500)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())


class ReaderMetadataPopup(QWidget):
    """A popup window to display the metadata from a loaded data file."""

    def __init__(self, window, tab_selected):
        """Initializes the ReaderMetadataPopup.

        Args:
            window: The main application window instance.
            tab_selected (str): The identifier of the tab that opened the popup.
        """
        super().__init__()
        self.app = window
        self.tab_selected = tab_selected
        self.data_type = ReadData.get_data_type(self.tab_selected)
        self.setWindowTitle(f"{self.data_type.capitalize()} file metadata")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg=QColor(20, 20, 20))
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        metadata_table = self.create_metadata_table()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_widget.setLayout(metadata_table)
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        main_layout.addSpacing(10)
        self.setLayout(main_layout)
        self.setStyleSheet(GUIStyles.plots_config_popup_style())
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        self.app.widgets[s.READER_METADATA_POPUP] = self
        self.center_window()

    def get_metadata_keys_dict(self):
        """Returns a dictionary mapping metadata keys to human-readable labels.

        Returns:
            dict: The mapping of keys to labels.
        """
        return {
            "channels": "Enabled Channels",
            "bin_width_micros": "Bin width (μs)",
            "acquisition_time_millis": "Acquisition time (s)",
            "laser_period_ns": "Laser period (ns)",
            "harmonics": "Harmonics",
            "tau_ns": "Tau (ns)",
        }

    def parse_laserblood_metadata(self, laserblood_metadata):
        """Parses the LaserBlood-specific metadata list into a dictionary.

        Args:
            laserblood_metadata (list): The list of metadata items.

        Returns:
            dict: The parsed metadata as key-value pairs.
        """
        data = {}
        for item in laserblood_metadata:
            key = (
                item["label"] + " (" + item["unit"] + ")"
                if item["unit"]
                else item["label"]
            )
            value = item["value"]
            data[key] = value
        return data

    def create_label_row(self, key, value, key_bg_color, value_bg_color):
        """Creates a styled horizontal layout for a key-value pair.

        Args:
            key (str): The key (label).
            value (str): The value.
            key_bg_color (str): The background color for the key label.
            value_bg_color (str): The background color for the value label.

        Returns:
            QHBoxLayout: The layout containing the styled labels.
        """
        h_box = QHBoxLayout()
        h_box.setContentsMargins(0, 0, 0, 0)
        h_box.setSpacing(0)
        key_label = QLabel(key)
        key_label.setStyleSheet(
            f"width: 200px; font-size: 14px; border: 1px solid {key_bg_color}; padding: 8px; color: white; background-color: {key_bg_color}"
        )
        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"width: 500px; font-size: 14px; border: 1px solid {value_bg_color}; padding: 8px; color: white"
        )
        h_box.addWidget(key_label)
        h_box.addWidget(value_label)
        return h_box

    def create_compact_label_row(self, key, value, key_bg_color, value_bg_color):
        """Create a compact label row for grid layout.

        Args:
            key (str): The key (label).
            value (str): The value.
            key_bg_color (str): The background color for the key label.
            value_bg_color (str): The background color for the value label.

        Returns:
            QHBoxLayout: The layout containing the compact styled labels.
        """
        h_box = QHBoxLayout()
        h_box.setContentsMargins(0, 0, 0, 0)
        h_box.setSpacing(0)
        key_label = QLabel(key)
        key_label.setStyleSheet(
            f"min-width: 210px; font-size: 12px; border: 1px solid {key_bg_color}; padding: 6px; color: white; background-color: {key_bg_color}"
        )
        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"min-width: 500px; font-size: 12px; border: 1px solid {value_bg_color}; padding: 6px; color: white"
        )
        h_box.addWidget(key_label, 0)
        h_box.addWidget(value_label, 1)
        return h_box

    def create_metadata_table(self):
        """Creates the main layout displaying all metadata in a table-like format.

        Returns:
            QVBoxLayout: The layout containing all metadata rows.
        """
        from core.phasors_controller import PhasorsController
        from PyQt6.QtCore import Qt
        import os

        metadata_keys = self.get_metadata_keys_dict()
        v_box = QVBoxLayout()
        v_box.setAlignment(Qt.AlignmentFlag.AlignTop)

        # For Phasors mode, show spectroscopy files metadata
        if self.data_type == "phasors":
            spectroscopy_metadata = self.app.reader_data[self.data_type].get(
                "spectroscopy_metadata", []
            )
            spectroscopy_files = self.app.reader_data[self.data_type]["files"][
                "spectroscopy"
            ]
            phasors_metadata = self.app.reader_data[self.data_type].get(
                "phasors_metadata", []
            )
            phasors_files = self.app.reader_data[self.data_type]["files"]["phasors"]
            laserblood_metadata = self.app.reader_data[self.data_type].get(
                "laserblood_metadata", []
            )
            laserblood_files = self.app.reader_data[self.data_type]["files"].get(
                "laserblood_metadata", []
            )

            # Convert to list if needed
            if isinstance(spectroscopy_files, str):
                spectroscopy_files = (
                    [spectroscopy_files] if spectroscopy_files.strip() else []
                )
            if isinstance(phasors_files, str):
                phasors_files = [phasors_files] if phasors_files.strip() else []
            if isinstance(laserblood_files, str):
                laserblood_files = (
                    [laserblood_files] if laserblood_files.strip() else []
                )

            # SPECTROSCOPY FILES SECTION - GRID LAYOUT
            if len(spectroscopy_files) > 0 or (
                isinstance(laserblood_metadata, list) and len(laserblood_metadata) > 0
            ):
                from PyQt6.QtWidgets import QGridLayout

                spectroscopy_title = QLabel("PHASORS FILE METADATA")
                spectroscopy_title.setStyleSheet(
                    "font-size: 16px; font-family: 'Montserrat'; margin-bottom: 10px;"
                )
                v_box.addWidget(spectroscopy_title)
                v_box.addSpacing(10)

                # Create grid layout (2 columns)
                grid_layout = QGridLayout()
                grid_layout.setSpacing(12)
                grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

                # Determine how many files to show (max of spectroscopy files and laserblood metadata)
                max_files = max(
                    len(spectroscopy_metadata),
                    (
                        len(laserblood_metadata)
                        if isinstance(laserblood_metadata, list)
                        else 0
                    ),
                )

                for file_idx in range(max_files):
                    row = file_idx // 2
                    col = file_idx % 2

                    color = PhasorsController.get_color_for_file_index(file_idx)
                    # Prefer spectroscopy (.bin) file name, not laserblood (.json) file name
                    if (
                        file_idx < len(spectroscopy_files)
                        and spectroscopy_files[file_idx]
                    ):
                        file_path = spectroscopy_files[file_idx]
                        file_name = (
                            os.path.basename(file_path)
                            if isinstance(file_path, str)
                            else str(file_path)
                        )
                    elif (
                        file_idx < len(laserblood_files) and laserblood_files[file_idx]
                    ):
                        file_path = laserblood_files[file_idx]
                        file_name = (
                            os.path.basename(file_path)
                            if isinstance(file_path, str)
                            else str(file_path)
                        )
                    else:
                        file_name = f"Metadata {file_idx + 1}"

                    # Create content widget for this file's metadata
                    content_widget = QWidget()
                    file_layout = QVBoxLayout()
                    file_layout.setSpacing(0)
                    file_layout.setContentsMargins(0, 0, 0, 0)

                    # File row with colored header
                    file_info_row = self.create_compact_label_row(
                        "File", file_name, color, color
                    )
                    file_layout.addLayout(file_info_row)

                    # Extract channel_names from binary metadata instead of laserblood JSON
                    channel_names = {}
                    if file_idx < len(spectroscopy_metadata):
                        metadata = spectroscopy_metadata[file_idx]
                        channel_names = metadata.get("channels_name", {}) if isinstance(metadata, dict) else {}

                    # Standard metadata (only if spectroscopy metadata exists for this index)
                    if file_idx < len(spectroscopy_metadata):
                        metadata = spectroscopy_metadata[file_idx]
                        for key, label in metadata_keys.items():
                            if key in metadata:
                                metadata_value = str(metadata[key])
                                if key == "channels":
                                    # Use custom channel names if available
                                    from utils.channel_name_utils import format_channel_list
                                    metadata_value = format_channel_list(metadata[key], channel_names)
                                if key == "acquisition_time_millis":
                                    metadata_value = str(metadata[key] / 1000)
                                metadata_row = self.create_compact_label_row(
                                    label, metadata_value, "#11468F", "#11468F"
                                )
                                file_layout.addLayout(metadata_row)

                    content_widget.setLayout(file_layout)

                    # Create scroll area for this file
                    from PyQt6.QtWidgets import QScrollArea

                    scroll_area = QScrollArea()
                    scroll_area.setWidget(content_widget)
                    scroll_area.setWidgetResizable(False)
                    scroll_area.setHorizontalScrollBarPolicy(
                        Qt.ScrollBarPolicy.ScrollBarAsNeeded
                    )
                    scroll_area.setVerticalScrollBarPolicy(
                        Qt.ScrollBarPolicy.ScrollBarAsNeeded
                    )
                    scroll_area.setMinimumWidth(750)
                    scroll_area.setMaximumHeight(550)
                    scroll_area.setStyleSheet("QScrollArea { border: none; }")

                    grid_layout.addWidget(
                        scroll_area, row, col, Qt.AlignmentFlag.AlignTop
                    )

                v_box.addLayout(grid_layout)
        else:
            # FITTING TAB - Support multi-file metadata display like PHASORS
            if self.data_type == "fitting":
                spectroscopy_metadata = self.app.reader_data["fitting"].get(
                    "spectroscopy_metadata", []
                )
                spectroscopy_files = self.app.reader_data["fitting"]["files"][
                    "spectroscopy"
                ]

                # Convert to list if needed
                if isinstance(spectroscopy_files, str):
                    spectroscopy_files = (
                        [spectroscopy_files] if spectroscopy_files.strip() else []
                    )

                if len(spectroscopy_files) > 0 and len(spectroscopy_metadata) > 0:
                    from PyQt6.QtWidgets import QGridLayout
                    from core.phasors_controller import PhasorsController
                    import os

                    spectroscopy_title = QLabel("SPECTROSCOPY FILES METADATA")
                    spectroscopy_title.setStyleSheet(
                        "font-size: 16px; font-family: 'Montserrat'; margin-bottom: 10px;"
                    )
                    v_box.addWidget(spectroscopy_title)
                    v_box.addSpacing(10)

                    # Get laserblood_metadata if available
                    laserblood_metadata = self.app.reader_data["fitting"].get(
                        "laserblood_metadata", []
                    )

                    # Create grid layout (2 columns)
                    grid_layout = QGridLayout()
                    grid_layout.setSpacing(12)
                    grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

                    for file_idx in range(len(spectroscopy_metadata)):
                        row = file_idx // 2
                        col = file_idx % 2

                        color = PhasorsController.get_color_for_file_index(file_idx)
                        file_path = (
                            spectroscopy_files[file_idx]
                            if file_idx < len(spectroscopy_files)
                            else f"File {file_idx + 1}"
                        )
                        file_name = (
                            os.path.basename(file_path)
                            if isinstance(file_path, str)
                            else str(file_path)
                        )

                        # Create content widget for this file's metadata
                        content_widget = QWidget()
                        file_layout = QVBoxLayout()
                        file_layout.setSpacing(0)
                        file_layout.setContentsMargins(0, 0, 0, 0)

                        # File row with colored header
                        file_info_row = self.create_compact_label_row(
                            "File", file_name, color, color
                        )
                        file_layout.addLayout(file_info_row)

                        # Extract channel_names from laserblood_metadata if available (but don't display it)
                        channel_names = {}
                        if (
                            isinstance(laserblood_metadata, list)
                            and file_idx < len(laserblood_metadata)
                            and laserblood_metadata[file_idx]
                        ):
                            from utils.channel_name_utils import extract_channel_names_from_metadata
                            channel_names = extract_channel_names_from_metadata(laserblood_metadata[file_idx])

                        # Add metadata for this file
                        metadata = spectroscopy_metadata[file_idx]
                        for key, label in metadata_keys.items():
                            if key in metadata:
                                metadata_value = str(metadata[key])
                                if key == "channels":
                                    # Use custom channel names if available
                                    from utils.channel_name_utils import format_channel_list
                                    metadata_value = format_channel_list(metadata[key], channel_names)
                                if key == "acquisition_time_millis":
                                    metadata_value = str(metadata[key] / 1000)
                                metadata_row = self.create_compact_label_row(
                                    label, metadata_value, "#11468F", "#11468F"
                                )
                                file_layout.addLayout(metadata_row)

                        content_widget.setLayout(file_layout)

                        # Create scroll area for this file
                        from PyQt6.QtWidgets import QScrollArea

                        scroll_area = QScrollArea()
                        scroll_area.setWidget(content_widget)
                        scroll_area.setWidgetResizable(False)
                        scroll_area.setHorizontalScrollBarPolicy(
                            Qt.ScrollBarPolicy.ScrollBarAsNeeded
                        )
                        scroll_area.setVerticalScrollBarPolicy(
                            Qt.ScrollBarPolicy.ScrollBarAsNeeded
                        )
                        scroll_area.setMinimumWidth(750)
                        scroll_area.setMaximumHeight(550)
                        scroll_area.setStyleSheet("QScrollArea { border: none; }")

                        grid_layout.addWidget(
                            scroll_area, row, col, Qt.AlignmentFlag.AlignTop
                        )

                    v_box.addLayout(grid_layout)
                else:
                    # Fallback to single file display
                    self._create_single_file_metadata_display(v_box, metadata_keys)
            else:
                # Original single-file behavior for Spectroscopy tabs
                self._create_single_file_metadata_display(v_box, metadata_keys)

        return v_box

    def _create_single_file_metadata_display(self, v_box, metadata_keys):
        """Helper method to create single-file metadata display for backward compatibility."""
        metadata = self.app.reader_data[self.data_type]["metadata"]
        laserblood_metadata = self.app.reader_data[self.data_type][
            "laserblood_metadata"
        ]
        file = self.app.reader_data[self.data_type]["files"][self.data_type]

        file = (
            self.app.reader_data[self.data_type]["files"][self.data_type]
            if self.data_type != "fitting"
            else self.app.reader_data[self.data_type]["files"]["spectroscopy"]
        )

        title = QLabel(f"{self.data_type.upper()} FILE METADATA")
        title.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
        v_box.addWidget(title)
        v_box.addSpacing(10)
        # Convert file list to readable format
        if isinstance(file, list):
            file_display = "\n".join(file) if file else "No files"
        else:
            file_display = str(file) if file else "No file"
        file_info_row = self.create_compact_label_row(
            "File", file_display, "#DA1212", "#DA1212"
        )
        v_box.addLayout(file_info_row)
        
        # Extract channel_names from binary metadata instead of laserblood JSON
        channel_names_dict = metadata.get("channels_name", {}) if isinstance(metadata, dict) else {}
        
        # Show standard metadata from the .bin file
        if metadata:
            for key, value in metadata_keys.items():
                if key in metadata:
                    metadata_value = str(metadata[key])
                    if key == "channels":
                        # Use custom channel names if available
                        from utils.channel_name_utils import format_channel_list
                        metadata_value = format_channel_list(metadata[key], channel_names_dict)
                    if key == "acquisition_time_millis":
                        metadata_value = str(metadata[key] / 1000)
                    metadata_row = self.create_compact_label_row(
                        value, metadata_value, "#11468F", "#11468F"
                    )
                    v_box.addLayout(metadata_row)

    def center_window(self):
        """Centers the popup window on the primary screen."""
        self.setMinimumWidth(900)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())


class WorkerSignals(QObject):
    """Defines signals available from a running worker thread."""

    success = pyqtSignal(str)
    error = pyqtSignal(str)


class SavePlotTask(QRunnable):
    """A QRunnable task for saving a plot in a separate thread."""

    def __init__(self, plot, base_path, signals):
        """Initializes the SavePlotTask.

        Args:
            plot (matplotlib.figure.Figure): The plot to save.
            base_path (str): The base file path for the saved images.
            signals (WorkerSignals): The signals object to communicate results.
        """
        super().__init__()
        self.plot = plot
        self.base_path = base_path
        self.signals = signals

    @pyqtSlot()
    def run(self):
        """Executes the task: saves the plot to PNG and EPS formats."""
        try:
            # png
            png_path = (
                f"{self.base_path}.png"
                if not self.base_path.endswith(".png")
                else self.base_path
            )
            self.plot.savefig(png_path, format="png", bbox_inches="tight")
            # eps
            eps_path = (
                f"{self.base_path}.eps"
                if not self.base_path.endswith(".eps")
                else self.base_path
            )
            self.plot.savefig(eps_path, format="eps", bbox_inches="tight")
            plt.close(self.plot)
            self.signals.success.emit(
                f"Plot images saved successfully as {png_path} and {eps_path}"
            )
        except Exception as e:
            plt.close(self.plot)
            self.signals.error.emit(str(e))
