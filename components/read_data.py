"""
Read Data Module for Spectroscopy Application.

This module provides functionality for reading, processing, and managing spectroscopy
and phasors data files. It includes classes for data reading, UI controls, and popup
windows for file management and metadata display.

Classes:
    ReadData: Main class for reading and processing data files
    ReadDataControls: Handles UI controls and visibility logic
    ReaderPopup: Popup window for data loading configuration
    ReaderMetadataPopup: Popup window for displaying file metadata
    WorkerSignals: Qt signals for background tasks
    SavePlotTask: Background task for saving plot images
"""

from functools import partial
import json
import os
import struct
from matplotlib import pyplot as plt
import numpy as np
from components.box_message import BoxMessage
from components.input_text_control import InputTextControl
from utils.gui_styles import GUIStyles
from utils.helpers import extract_channel_from_label, ns_to_mhz
from utils.layout_utilities import clear_layout, hide_layout, show_layout
from utils.messages_utilities import MessagesUtilities
from utils.resource_path import resource_path
from utils.fitting_utilities import convert_json_serializable_item_into_np_fitting_result
from utils.logo_utilities import TitlebarIcon
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
)
from PyQt6.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, QObject, pyqtSlot
from PyQt6.QtGui import QColor, QIcon
import pdb
import pprint


current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class ReadData:
    """
    Main class for reading and processing spectroscopy and phasors data files.
    
    This class provides static methods for reading binary and JSON files,
    plotting data, and managing file operations for the spectroscopy application.
    """

    @staticmethod
    def read_bin_data(window, app, tab_selected, file_type):
        """
        Read binary data files based on the selected tab and file type.
        
        Args:
            window: Parent window for file dialogs
            app: Main application instance
            tab_selected: Currently selected tab identifier
            file_type (str): Type of file to read ('spectroscopy' or 'phasors')
            
        Returns:
            None: Updates app.reader_data with loaded data
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
            spectroscopy_files = [spectroscopy_files] if spectroscopy_files.strip() else []
        if isinstance(phasors_files, str):
            phasors_files = [phasors_files] if phasors_files.strip() else []
        
        # Contatore dei metadati con laser_period_ns valido
        valid_metadata_count = 0
        laser_periods = set()
        
        # Analizza file spectroscopy
        for i, meta in enumerate(spectroscopy_metadata):
            file_name = spectroscopy_files[i] if i < len(spectroscopy_files) else f"spectroscopy_file_{i}"
            # Estrai solo il nome del file dal path completo
            file_display_name = os.path.basename(file_name) if isinstance(file_name, str) else file_name
            if isinstance(meta, dict) and "laser_period_ns" in meta:
                laser_period = meta["laser_period_ns"]
                laser_periods.add(laser_period)
                valid_metadata_count += 1
        
        # Analizza file phasors
        for i, meta in enumerate(phasors_metadata):
            file_name = phasors_files[i] if i < len(phasors_files) else f"phasors_file_{i}"
            # Estrai solo il nome del file dal path completo
            file_display_name = os.path.basename(file_name) if isinstance(file_name, str) else file_name
            if isinstance(meta, dict) and "laser_period_ns" in meta:
                laser_period = meta["laser_period_ns"]
                laser_periods.add(laser_period)
                valid_metadata_count += 1

        # Controllo mismatch
        if len(laser_periods) > 1:
            ReadData.show_warning_message("Frequency mismatch", "Loaded files must have the same frequency MHz")
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
            window,
            f"Load multiple {file_type} files (max 4)",
            "",
            filter_pattern
        )
        
        if not file_names:
            return []
        if len(file_names) > 4:
            ReadData.show_warning_message(
                "Too many files", "You can select a maximum of 4 files. Only the first 4 will be loaded."
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
            ReadData.show_warning_message("Invalid file type", f"Unsupported file type: {file_type}")
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
                f"{invalid_count} out of {len(file_names)} selected files are not valid {file_type} files. No files were loaded."
            )
            return []
        
        return valid_files

    
    
    @staticmethod
    def get_bin_filter_file_string(file_type):
        """
        Get the filter string for binary file dialogs.
        
        Args:
            file_type (str): Type of file ('spectroscopy' or 'phasors')
            
        Returns:
            str or None: Filter string for file dialog
        """
        if file_type == "spectroscopy":
            return "_spectroscopy"
        elif file_type == "phasors":
            return "phasors_spectroscopy"      
        else:
            return None     

    @staticmethod
    def read_fitting_data(window, app):
        """
        Read fitting data from JSON files.
        
        Args:
            window: Parent window for file dialogs
            app: Main application instance
            
        Returns:
            None: Updates app.reader_data with fitting data
        """
        result = ReadData.read_json(window, "Fitting")
        if not result:
            return
        file_name, data = result
        if data is not None:
            active_channels = [item["channel"] for item in data]
            app.reader_data["fitting"]["files"]["fitting"] = file_name
            app.reader_data["fitting"]["data"]["fitting_data"] = data
            app.reader_data["fitting"]["metadata"]["channels"] = active_channels

    @staticmethod
    def get_fitting_active_channels(app):
        """
        Get active channels from fitting data.
        
        Args:
            app: Main application instance
            
        Returns:
            list: List of active channel indices
        """
        data = app.reader_data["fitting"]["data"]["fitting_data"]
        if data:
            return [item["channel"] for item in data]
        return []

    @staticmethod
    def preloaded_fitting_data(app):
        """
        Get preloaded fitting data if available.
        
        Args:
            app: Main application instance
            
        Returns:
            dict or None: Parsed fitting results or None if not available
        """
        fitting_file = app.reader_data["fitting"]["files"]["fitting"]
        if len(fitting_file.strip()) > 0 and app.acquire_read_mode == "read":
            fitting_results = app.reader_data["fitting"]["data"]["fitting_data"]
            parsed_fitting_results = convert_json_serializable_item_into_np_fitting_result(fitting_results)
            return parsed_fitting_results
        else:
            return None

    @staticmethod
    def are_spectroscopy_and_fitting_from_same_acquisition(app):
        """
        Verify if spectroscopy and fitting files are from the same acquisition.
        
        Args:
            app: Main application instance
            
        Returns:
            bool: True if files match, False otherwise
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
    def read_json(window, file_type, filter_string = None):
        """
        Read JSON files with optional filtering.
        
        Args:
            window: Parent window for file dialogs
            file_type (str): Type of file being read
            filter_string (str, optional): Filter pattern for file dialog
            
        Returns:
            tuple: (file_name, data) or (None, None) if failed
            
        Raises:
            json.JSONDecodeError: If file contains invalid JSON
            Exception: For other file reading errors
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
        """
        Map tab identifier to data type string.
        
        Args:
            active_tab: Tab identifier constant
            
        Returns:
            str: Data type ('spectroscopy', 'phasors', or 'fitting')
        """
        return {s.TAB_SPECTROSCOPY: "spectroscopy", s.TAB_PHASORS: "phasors"}.get(
            active_tab, "fitting"
        )

    @staticmethod
    def plot_data(app):
        """
        Plot data based on current tab selection and available data.
        
        Args:
            app: Main application instance
            
        Returns:
            None: Updates application plots
        """
        data_type = ReadData.get_data_type(app.tab_selected)
        if data_type != "phasors" :
            
            spectroscopy_data = (
                app.reader_data[data_type]["data"]
                if data_type == "spectroscopy"
                else app.reader_data[data_type]["data"]["spectroscopy_data"]
            )
            metadata = app.reader_data[data_type]["metadata"]
            laser_period_ns = (
                metadata["laser_period_ns"]
                if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None
                else 25
            )
            channels = metadata["channels"] if "channels" in metadata else []
            if (
                "times" in spectroscopy_data
                and "channels_curves" in spectroscopy_data
                and not (metadata == {})
            ):
                ReadData.plot_spectroscopy_data(
                    app,
                    spectroscopy_data["times"],
                    spectroscopy_data["channels_curves"],
                    laser_period_ns,
                    channels,
                )
                
        phasors_metadata = app.reader_data["phasors"]["phasors_metadata"]        
        if data_type == "phasors" and len(phasors_metadata) > 0 :                      
            laser_period_ns = phasors_metadata[0]["laser_period_ns"]
            
            spectroscopy_metadata = app.reader_data["phasors"]["spectroscopy_metadata"]
            all_metadata = spectroscopy_metadata + phasors_metadata
            harmonics_values = []
            for meta in all_metadata:
                h = meta.get('harmonics')
                if isinstance(h, int):
                    harmonics_values.append(h)
                elif isinstance(h, list) and h:
                    harmonics_values.append(max(h))
            max_harmonic = max(harmonics_values)
            
            # Plot spectroscopy decay curves if multi-file data available
            spectroscopy_data = app.reader_data["phasors"]["data"]["spectroscopy_data"]
            if "files_data" in spectroscopy_data and len(spectroscopy_data["files_data"]) > 0:
                # Get channels from first file's metadata
                channels = spectroscopy_metadata[0]["channels"] if len(spectroscopy_metadata) > 0 else []
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
        """
        Plot spectroscopy decay curves for selected channels.
        
        Args:
            app: Main application instance
            times (list): Time values for x-axis (unused in multi-file mode)
            channels_curves (dict): Channel data with decay curves (unused in multi-file mode)
            laser_period_ns (float): Laser period in nanoseconds
            metadata_channels (list): Channel metadata
            
        Returns:
            None: Updates application plots
        """
        import pyqtgraph as pg
        from core.plots_controller import PlotsController
        from core.phasors_controller import PhasorsController
        
        # Check if we're in phasors read mode with multi-file data
        spectroscopy_data = app.reader_data["phasors"]["data"]["spectroscopy_data"]
        is_multi_file = "files_data" in spectroscopy_data
        
        if is_multi_file and app.tab_selected == s.TAB_PHASORS:
            # Multi-file mode: plot each file's curve with a different color
            files_data = spectroscopy_data["files_data"]
            num_bins = 256
            frequency_mhz = ns_to_mhz(laser_period_ns)
            period_ns = 1_000 / frequency_mhz if frequency_mhz != 0.0 else laser_period_ns
            x_values = np.linspace(0, period_ns, num_bins)
                        
            # Clear decay widgets first
            for ch in app.plots_to_show:
                if ch in app.decay_widgets:
                    app.decay_widgets[ch].clear()
            
            # Plot each file's data with its own color
            for file_idx, file_data in enumerate(files_data):
                file_channels_curves = file_data["channels_curves"]
                color = PhasorsController.get_color_for_file_index(file_idx)
                                
                for channel, curves in file_channels_curves.items():
                    if channel in app.plots_to_show:
                        y_values = np.sum(curves, axis=0)
                        
                        # Plot with specific color for this file
                        if channel in app.decay_widgets:
                            pen = pg.mkPen(color=color, width=2)
                            app.decay_widgets[channel].plot(x_values, y_values, pen=pen)
        else:
            # Single-file mode (original behavior)
            num_bins = 256
            frequency_mhz = ns_to_mhz(laser_period_ns)
            period_ns = 1_000 / frequency_mhz if frequency_mhz != 0.0 else laser_period_ns
            x_values = np.linspace(0, period_ns, num_bins) / 1_000
            
            for channel, curves in channels_curves.items():
                if metadata_channels[channel] in app.plots_to_show:
                    y_values = np.sum(curves, axis=0)
                    if app.tab_selected != s.TAB_PHASORS:
                        app.cached_decay_values[app.tab_selected][
                            metadata_channels[channel]
                        ] = y_values
                    # Use calculated x_values with same approach as multi-file mode
                    PlotsController.update_plots(
                        app, metadata_channels[channel], x_values, y_values, reader_mode=True
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
        """
        Prepare spectroscopy data for fitting operations.
        
        Args:
            app: Main application instance
            
        Returns:
            list: List of dictionaries containing x, y, title, channel_index, and time_shift
        """
        spectroscopy_data = app.reader_data["fitting"]["data"]["spectroscopy_data"]
        metadata = app.reader_data["fitting"]["metadata"]
        channels_curves = spectroscopy_data["channels_curves"]
        channels = metadata["channels"]
        laser_period_ns = (
            metadata["laser_period_ns"]
            if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None
            else 25
        )
        data = []
        num_bins = 256
        x_values = np.linspace(0, laser_period_ns, num_bins)
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
                        "title": "Channel " + str(channels[channel]  + 1),
                        "channel_index": channels[channel] ,
                        "time_shift": 0
                    }
                )
        return data        

    @staticmethod
    def plot_phasors_data(app, data, harmonics, laser_period_ns):
        """
        Plot phasors data with harmonic analysis.
        
        Args:
            app: Main application instance
            data (dict): Phasors data by channel and harmonic
            harmonics (list or int): Available harmonics
            
        Returns:
            None: Updates phasors plots and related UI elements
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
        
        PhasorsController.generate_phasors_cluster_center(app, app.phasors_harmonic_selected)
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
        """
        Show a warning message box to the user.
        
        Args:
            title (str): Title of the message box
            message (str): Message content
            
        Returns:
            None: Displays the message box
        """
        BoxMessage.setup(
            title, message, QMessageBox.Icon.Warning, GUIStyles.set_msg_box_style()
        )
        
    @staticmethod
    def read_bin(window, app, magic_bytes, file_type, read_data_cb, tab_selected, filter_string = None):
        """
        Read binary files with specified magic bytes and data callback.
        
        Args:
            window: Parent window for file dialogs
            app: Main application instance
            magic_bytes (bytes): Expected file magic bytes
            file_type (str): Type of file being read
            read_data_cb: Callback function to read and process file data
            tab_selected: Currently selected tab identifier
            filter_string (str, optional): Filter pattern for file dialog
            
        Returns:
            None: Calls read_data_cb with file handle and other parameters
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
        """
        Read spectroscopy data from binary file.
        
        Args:
            file: Open file handle
            file_name (str): Name of the file
            file_type (str): Type of file being read
            tab_selected: Currently selected tab
            app: Main application instance
            
        Returns:
            tuple: (file_name, file_type, times, channel_curves, metadata) or None if error
            
        Raises:
            Exception: If file reading or parsing fails
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
        """
        Read phasors data from binary file.
        
        Args:
            file: Open file handle
            file_name (str): Name of the file
            file_type (str): Type of file being read
            tab_selected: Currently selected tab
            app: Main application instance
            
        Returns:
            tuple: (file_name, file_type, phasors_data, metadata) or None if error
            
        Raises:
            struct.error: If binary data unpacking fails
            Exception: For other file reading errors
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
                app.reader_data["phasors"]["data"]["phasors_data"].setdefault(channel_name, {}).setdefault(harmonic_name, []).append((g, s, file_name))           
            return file_name, "phasors", phasors_data, metadata
        except Exception:
            ReadData.show_warning_message(
                "Error reading file", "Error reading Phasors file"
            )
            return None

    @staticmethod
    def save_plot_image(plot):
        """
        Save plot as PNG and EPS images using background thread.
        
        Args:
            plot: Matplotlib plot object to save
            
        Returns:
            None: Saves files and shows success/error messages
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
        """
        Get laser period from phasors metadata.
        
        Args:
            app: Main application instance
            
        Returns:
            float: Laser period in nanoseconds or 0.0 if not available
        """
        metadata = app.reader_data["phasors"]["phasors_metadata"]
        if "laser_period_ns" in metadata:
            return metadata["laser_period_ns"]
        else:
            return 0.0

    @staticmethod
    def get_phasors_frequency_mhz(app):
        """
        Get phasors frequency in MHz from metadata.
        
        Args:
            app: Main application instance
            
        Returns:
            float: Frequency in MHz or 0.0 if not available
        """
        metadata = app.reader_data["phasors"]["phasors_metadata"]
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
    def get_spectroscopy_frequency_mhz(app):
        """
        Get spectroscopy frequency in MHz from metadata.
        
        Args:
            app: Main application instance
            
        Returns:
            float: Frequency in MHz or 0.0 if not available
        """
        metadata = app.reader_data["spectroscopy"]["metadata"]
        # Handle both single file (dict) and multiple files (list of dicts)
        if isinstance(metadata, list) and len(metadata) > 0:
            metadata = metadata[0]  # Get first file's metadata
        if isinstance(metadata, dict) and "laser_period_ns" in metadata:
            return ns_to_mhz(metadata["laser_period_ns"])
        return 0.0

    @staticmethod
    def get_frequency_mhz(app):
        """
        Get the current frequency in MHz based on selected tab.
        
        Args:
            app: Main application instance
            
        Returns:
            float: Frequency in MHz or 0.0 if not available
        """
        if app.tab_selected == s.TAB_SPECTROSCOPY:
            return ReadData.get_spectroscopy_frequency_mhz(app)
        elif app.tab_selected == s.TAB_PHASORS:
            return ReadData.get_phasors_frequency_mhz(app)
        else:
            return 0.0

    @staticmethod
    def prepare_spectroscopy_data_for_export_img(app):
        """
        Prepare spectroscopy data for image export.
        
        Args:
            app: Main application instance
            
        Returns:
            tuple: (channels_curves, times, metadata) for export
        """
        metadata = app.reader_data["spectroscopy"]["metadata"]
        channels_curves = app.reader_data["spectroscopy"]["data"]["channels_curves"]
        times = app.reader_data["spectroscopy"]["data"]["times"]
        return channels_curves, times, metadata

    @staticmethod
    def prepare_phasors_data_for_export_img(app):
        """
        Prepare phasors data for image export.
        
        Args:
            app: Main application instance
            
        Returns:
            tuple: (phasors_data, laser_period, active_channels, spectroscopy_times, spectroscopy_curves) for export
        """
        phasors_data = app.reader_data["phasors"]["data"]["phasors_data"]
        # phasors metadata can be stored as a list (multi-file) or a dict (single file)
        phasors_meta = app.reader_data["phasors"].get("phasors_metadata") or app.reader_data["phasors"].get("metadata")
        if isinstance(phasors_meta, list):
            meta = phasors_meta[0] if len(phasors_meta) > 0 else {}
        elif isinstance(phasors_meta, dict):
            meta = phasors_meta
        else:
            meta = {}

        laser_period = meta.get("laser_period_ns", 0)
        active_channels = meta.get("channels", [])

        # spectroscopy data can be stored per-file under 'files_data' or as aggregated times/channels_curves
        spectroscopy_section = app.reader_data["phasors"]["data"].get("spectroscopy_data", {})
        if isinstance(spectroscopy_section, dict) and "files_data" in spectroscopy_section:
            # multi-file mode: individual file infos will be passed separately when exporting
            spectroscopy_curves = None
            spectroscopy_times = None
        else:
            spectroscopy_curves = spectroscopy_section.get("channels_curves") if isinstance(spectroscopy_section, dict) else None
            spectroscopy_times = spectroscopy_section.get("times") if isinstance(spectroscopy_section, dict) else None
        return (
            phasors_data,
            laser_period,
            active_channels,
            spectroscopy_times,
            spectroscopy_curves,
        )


class ReadDataControls:
    """
    Handles UI controls visibility and state management for read mode operations.
    
    This class provides static methods to manage widget visibility,
    plot configuration, and user interaction based on application state.
    """

    @staticmethod
    def handle_widgets_visibility(app, read_mode):
        """
        Update widget visibility based on read mode state.
        
        Args:
            app: Main application instance
            read_mode (bool): True if in read mode, False for acquisition mode
            
        Returns:
            None: Updates widget visibility states
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
        app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
            bin_metadata_btn_visible and app.tab_selected != s.TAB_FITTING
        ) 
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
            if read_mode : 
                app.control_inputs[s.LOAD_REF_BTN].hide()
                hide_layout(app.control_inputs["phasors_resolution_container"])
                hide_layout(app.control_inputs["quantize_phasors_container"])
                ControlsController.on_quantize_phasors_changed(app, False)
                app.settings.setValue(s.SETTINGS_QUANTIZE_PHASORS, False)
            else : 
                show_layout(app.control_inputs["quantize_phasors_container"])
                if app.quantized_phasors :
                    show_layout(app.control_inputs["phasors_resolution_container"])  

    @staticmethod
    def handle_plots_config(app, file_type):
        """
        Configure plot settings based on loaded file metadata.
        
        Args:
            app: Main application instance
            file_type (str): Type of file being processed
            
        Returns:
            None: Updates plot configuration
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
        """
        Handle plot updates when switching between tabs in read mode.
        
        Args:
            app: Main application instance
            
        Returns:
            None: Updates plots and UI for current tab
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
        """
        Determine if binary metadata button should be enabled.
        
        Args:
            app: Main application instance
            
        Returns:
            bool: True if metadata button should be visible
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
            spectroscopy_metadata = app.reader_data[data_type].get("spectroscopy_metadata", [])
            
            # Check if at least one type of file is loaded
            has_phasors = (isinstance(phasors_files, list) and len(phasors_files) > 0) or \
                         (isinstance(phasors_files, str) and len(phasors_files.strip()) > 0)
            has_spectroscopy = (isinstance(spectroscopy_files, list) and len(spectroscopy_files) > 0) or \
                              (isinstance(spectroscopy_files, str) and len(spectroscopy_files.strip()) > 0)
            
            return (has_phasors or has_spectroscopy) and app.acquire_read_mode == "read"

    @staticmethod
    def fit_button_enabled(app):
        """
        Determine if fit button should be enabled based on loaded files.
        
        Args:
            app: Main application instance
            
        Returns:
            bool: True if fit button should be enabled
        """
        tab_selected_fitting = app.tab_selected == s.TAB_FITTING
        read_mode = app.acquire_read_mode == "read"
        fitting_file = app.reader_data["fitting"]["files"]["fitting"]
        spectroscopy_file = app.reader_data["fitting"]["files"]["spectroscopy"]
        fitting_file_exists = len(fitting_file.strip()) > 0
        spectroscopy_file_exists = len(spectroscopy_file.strip()) > 0
        return tab_selected_fitting and read_mode and (
            fitting_file_exists or spectroscopy_file_exists
        )


class ReaderPopup(QWidget):
    """
    Popup window for configuring data loading and channel selection.
    
    This widget provides an interface for loading data files,
    selecting channels to display, and configuring plot settings.
    
    Attributes:
        app: Reference to main application
        tab_selected: Currently selected tab identifier
        widgets (dict): Dictionary of UI widgets
        layouts (dict): Dictionary of layouts
        channels_checkboxes (list): List of channel selection checkboxes
        data_type (str): Current data type being handled
    """

    def __init__(self, window, tab_selected):
        """
        Initialize the reader popup window.
        
        Args:
            window: Main application window
            tab_selected: Currently selected tab identifier
        """
        super().__init__()
        self.app = window
        self.tab_selected = tab_selected
        self.widgets = {}
        self.layouts = {}
        self.channels_checkboxes = []
        self.channels_checkbox_first_toggle = True
        self.data_type = ReadData.get_data_type(self.tab_selected)
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

    def init_file_load_ui(self):
        """
        Initialize file loading UI components.
        
        Returns:
            QVBoxLayout: Layout containing file loading controls
        """
        v_box = QVBoxLayout()
        files = self.app.reader_data[self.data_type]["files"]
        for file_type, file_path in files.items():
            if (file_type == "phasors" and self.data_type == "phasors") or (
                file_type == "fitting" and self.data_type == "fitting"
            ):
                input_desc = QLabel(f"LOAD RELATED {file_type.upper()} FILE:")
            else:
                input_desc = QLabel(f"LOAD A {file_type.upper()} FILE:")
            # Modifica: aggiungi "S" a "FILE" solo per PHASORS-READ
            if self.data_type == "phasors":
                input_desc.setText(input_desc.text().replace("FILE", "FILES"))
            input_desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
            control_row = QHBoxLayout()

            file_extension = ".json" if file_type == "fitting" else ".bin"

            def on_change(file_type=file_type):
                def callback(text):
                    self.on_loaded_file_change(text, file_type)

                return callback

            # Modifica: assicurati che display_text sia sempre una stringa
            display_text = ""
            if isinstance(file_path, list):
                if len(file_path) == 1:
                    display_text = file_path[0]  # Primo file come stringa
                elif len(file_path) > 1:
                    display_text = f"{len(file_path)} file(s) loaded"  # Riassunto come stringa
                # Se vuota, lascia placeholder
            else:
                display_text = file_path  # Stringa esistente
            
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
            # Modifica: collega alla funzione specifica per phasors se siamo in PHASORS-READ
            if self.data_type == "phasors":
                load_file_btn.clicked.connect(
                    partial(self.on_load_file_btn_clicked_phasors, file_type)
                )
            else:
                load_file_btn.clicked.connect(
                    partial(self.on_load_file_btn_clicked, file_type)
            )
            control_row.addWidget(input)
            control_row.addWidget(load_file_btn)
            v_box.addWidget(input_desc)
            v_box.addSpacing(10)
            v_box.addLayout(control_row)
            v_box.addSpacing(10)
        return v_box

    def init_channels_layout(self):
        """
        Initialize channel selection layout based on loaded file metadata.
        
        Returns:
            QVBoxLayout or None: Layout with channel checkboxes or None if no channels
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
            self.app.plots_to_show = plots_to_show
            self.app.settings.setValue(
                s.SETTINGS_PLOTS_TO_SHOW, json.dumps(plots_to_show)
            )
            channels_layout = QVBoxLayout()
            desc = QLabel("CHOOSE MAX 4 PLOTS TO DISPLAY:")
            desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
            grid = QGridLayout()
            for ch in selected_channels:
                checkbox, checkbox_wrapper = self.set_checkboxes(f"Channel {ch + 1}")
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
        """
        Create layout with plot/fit button.
        
        Returns:
            QHBoxLayout: Layout containing the action button
        """
        fitting_data = self.app.reader_data["fitting"]["data"]["fitting_data"]
        spectroscopy_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"]        
        row_btn = QHBoxLayout()
        # PLOT BTN
        plot_btn = QPushButton("")
        if fitting_data and not spectroscopy_data:
                plot_btn.setText("FIT DATA")   
        else:     
            plot_btn.setText("PLOT DATA")     
        plot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plot_btn.setObjectName("btn")
        GUIStyles.set_stop_btn_style(plot_btn)
        plot_btn.setFixedHeight(40)
        plot_btn.setFixedWidth(200)
        plots_to_show = self.app.reader_data[self.data_type]["plots"]
        plot_btn.setEnabled(len(plots_to_show) > 0)
        plot_btn.clicked.connect(self.on_plot_data_btn_clicked)
        self.widgets["plot_btn"] = plot_btn
        row_btn.addStretch(1)
        row_btn.addWidget(plot_btn)
        return row_btn

    def remove_channels_grid(self):
        """
        Remove channel selection grid layout.
        
        Returns:
            None: Clears the channels layout
        """
        if "ch_layout" in self.layouts:
            clear_layout(self.layouts["ch_layout"])
            del self.layouts["ch_layout"]

    def set_checkboxes(self, text):
        """
        Create and style a checkbox for channel selection.
        
        Args:
            text (str): Text label for the checkbox
            
        Returns:
            tuple: (QCheckBox, QWidget) - checkbox and its wrapper widget
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
        """
        Handle channel checkbox toggle events.
        
        Args:
            state (bool): New checkbox state
            checkbox (QCheckBox): Checkbox that was toggled
            
        Returns:
            None:Updates channel selection and UI state
        """
        from core.controls_controller import ControlsController
        from core.plots_controller import PlotsController
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
            # If phasors tab is selected, both phasors and spectroscopy files must be loaded to be able to plot data
            if self.data_type == "phasors":
                phasors_file = self.app.reader_data["phasors"]["files"]["phasors"]
                spectroscopy_file = self.app.reader_data["phasors"]["files"]["spectroscopy"]
                both_files_present = len(phasors_file.strip()) > 0 and len(spectroscopy_file.strip()) > 0
                self.widgets["plot_btn"].setEnabled(both_files_present and plot_btn_enabled)  
            else:                 
                self.widgets["plot_btn"].setEnabled(plot_btn_enabled)
        PlotsController.clear_plots(self.app)
        PlotsController.generate_plots(self.app)
        ControlsController.toggle_intensities_widgets_visibility(self.app)
        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)            
      

    def on_loaded_file_change(self, text, file_type):
        """
        Handle changes to loaded file paths in the input fields.
        
        Args:
            text (str): New file path
            file_type (str): Type of file ('fitting', 'spectroscopy', or 'phasors')
            
        Returns:
            None: Updates file path in app.reader_data and refreshes UI if needed
        """
        from core.controls_controller import ControlsController
        from core.plots_controller import PlotsController
        
        if "file(s) loaded" in text:
            return
        
        if text != self.app.reader_data[self.data_type]["files"][file_type]:
            PlotsController.clear_plots(self.app)
            PlotsController.generate_plots(self.app, ReadData.get_frequency_mhz(self.app))
            ControlsController.toggle_intensities_widgets_visibility(self.app)
        self.app.reader_data[self.data_type]["files"][file_type] = text
        

    def on_load_file_btn_clicked(self, file_type):
        """
        Handle file load button click event.
        
        Args:
            file_type (str): Type of file to load ('fitting', 'spectroscopy', or 'phasors')
            
        Returns:
            None: Reads the selected file and updates the UI
        """
        from core.controls_controller import ControlsController
        
        if file_type == "fitting":
            ReadData.read_fitting_data(self, self.app)
        else:
            ReadData.read_bin_data(self, self.app, self.tab_selected, file_type)
        file_name = self.app.reader_data[self.data_type]["files"][file_type]
        if file_name is not None and len(file_name) > 0:
            bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(
                self.app
            )
            self.app.control_inputs["bin_metadata_button"].setVisible(
                bin_metadata_btn_visible
            )
            self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
                bin_metadata_btn_visible and self.tab_selected != s.TAB_FITTING
            )
            widget_key = f"load_{file_type}_input"
            self.widgets[widget_key].setText(file_name)
            self.remove_channels_grid()
            channels_layout = self.init_channels_layout()
            if channels_layout is not None:
                self.layout.insertLayout(2, channels_layout)
        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)
        if "plot_btn" in self.widgets:
            fitting_data = self.app.reader_data["fitting"]["data"]["fitting_data"]
            spectroscopy_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"]
            if fitting_data and not spectroscopy_data:
                self.widgets["plot_btn"].setText("FIT DATA")   
            else: 
                self.widgets["plot_btn"].setText("PLOT DATA") 
            
    
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
    
        valid_files = ReadData.read_multiple_bin_data(self, self.app, self.tab_selected, file_type)
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
            self.app.reader_data[self.data_type]["data"]["spectroscopy_data"] = {"files_data": []}
        
        # Set the files list
        self.app.reader_data[self.data_type]["files"][file_type] = valid_files
    
        # Leggi e accumula dati da ciascun file valido
        magic_bytes = b"SP01" if file_type == "spectroscopy" else b"SPF1"
        read_function = ReadData.read_spectroscopy_data if file_type == "spectroscopy" else ReadData.read_phasors_data
    
        for file_path in valid_files:
            try:
                with open(file_path, "rb") as f:
                    if f.read(4) == magic_bytes:  # Rivalida (opzionale, già fatto)
                        result = read_function(f, file_path, file_type, self.tab_selected, self.app)
                        if result:
                            file_name, file_type_result, *data, metadata = result
                        
                        # Accumula metadata
                            if file_type == "spectroscopy":
                                self.app.reader_data[self.data_type]["spectroscopy_metadata"].append(metadata)
                            elif file_type == "phasors":
                                self.app.reader_data[self.data_type]["phasors_metadata"].append(metadata)
                        
                            # Accumula dati
                            if file_type == "spectroscopy":
                                times, channels_curves = data
                                # Store per-file data as list instead of accumulating
                                if "files_data" not in self.app.reader_data[self.data_type]["data"]["spectroscopy_data"]:
                                    self.app.reader_data[self.data_type]["data"]["spectroscopy_data"]["files_data"] = []
                                self.app.reader_data[self.data_type]["data"]["spectroscopy_data"]["files_data"].append({
                                    "file_path": file_path,
                                    "times": times,
                                    "channels_curves": channels_curves
                                })
                            elif file_type == "phasors":
                                phasors_data = data[0]
                                for ch, harmonics in phasors_data.items():
                                    if ch not in self.app.reader_data[self.data_type]["data"]["phasors_data"]:
                                        self.app.reader_data[self.data_type]["data"]["phasors_data"][ch] = {}
                                    for h, points in harmonics.items():
                                        if h not in self.app.reader_data[self.data_type]["data"]["phasors_data"][ch]:
                                            self.app.reader_data[self.data_type]["data"]["phasors_data"][ch][h] = []
                                            self.app.reader_data[self.data_type]["data"]["phasors_data"][ch][h].extend([(p[0], p[1], file_path) for p in points])
            except Exception as e:
                ReadData.show_warning_message("Error reading file", f"Error reading {file_path}: {str(e)}")
    
        # Aggiorna UI
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self.app)
        self.app.control_inputs["bin_metadata_button"].setVisible(bin_metadata_btn_visible)
        self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
            bin_metadata_btn_visible and self.tab_selected != s.TAB_FITTING
        )
        widget_key = f"load_{file_type}_input"
        # Modifica: mostra il numero di file selezionati nell'operazione corrente
        display_text = f"{len(valid_files)} file(s) loaded"
        self.widgets[widget_key].setText(display_text)
            
        if "plot_btn" in self.widgets:
            phasors_files = self.app.reader_data["phasors"]["files"]["phasors"]
            spectroscopy_files = self.app.reader_data["phasors"]["files"]["spectroscopy"]
            both_files_present = len(phasors_files) > 0 and len(spectroscopy_files) > 0
            self.widgets["plot_btn"].setEnabled(both_files_present)                          
                        
                    
    def errors_in_data(self, file_type):
        """
        Check for data consistency errors between loaded files.
        
        Args:
            file_type (str): Type of file to validate
            
        Returns:
            bool: True if errors found, False otherwise
        """        
        if file_type == "fitting":
            file_fitting = self.app.reader_data["fitting"]["files"]["fitting"]
            file_spectroscopy = self.app.reader_data["fitting"]["files"]["spectroscopy"]
            if len(file_fitting.strip()) == 0 or len(file_spectroscopy.strip()) == 0:
                return False
            channels = ReadData.get_fitting_active_channels(self.app)
            return not (ReadData.are_spectroscopy_and_fitting_from_same_acquisition(self.app))
        elif file_type == "phasors":
            return ReadData.has_laser_period_mismatch(self.app.reader_data["phasors"]) 
        return False
    

    def on_plot_data_btn_clicked(self):
        """
        Handle plot data button click event.
        
        Validates data consistency and either plots data or initiates fitting
        based on available data and current mode.
        
        Returns:
            None: Plots data or shows error messages
        """
        from core.controls_controller import ControlsController
        from core.plots_controller import PlotsController
        #self.app.reset_time_shifts_values()
        file_type = self.data_type
        if self.errors_in_data(file_type):
            return        
        fitting_data = self.app.reader_data["fitting"]["data"]["fitting_data"]
        spectroscopy_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"]
        if fitting_data and not spectroscopy_data:
           ControlsController.on_fit_btn_click(self.app)           
        else:
            # Regenerate plots with correct frequency from loaded files
            freq = ReadData.get_frequency_mhz(self.app)
            if freq > 0:
                PlotsController.clear_plots(self.app)
                PlotsController.generate_plots(self.app, freq)
                ControlsController.toggle_intensities_widgets_visibility(self.app)
            ReadData.plot_data(self.app)
        self.close()

    def center_window(self):
        """
        Center the popup window on the screen.
        
        Returns:
            None: Moves window to center of screen
        """
        self.setMinimumWidth(500)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())

  

class ReaderMetadataPopup(QWidget):
    """
    Popup window for displaying file metadata in a formatted table.
    
    This widget shows detailed information about loaded data files
    including channels, acquisition parameters, and file paths.
    
    Attributes:
        app: Reference to main application
        tab_selected: Currently selected tab identifier
        data_type (str): Type of data being displayed
        metadata_table: Layout containing metadata display
    """

    def __init__(self, window, tab_selected):
        """
        Initialize the metadata popup window.
        
        Args:
            window: Main application window
            tab_selected: Currently selected tab identifier
        """
        super().__init__()
        self.app = window
        self.tab_selected = tab_selected
        self.data_type = ReadData.get_data_type(self.tab_selected)
        self.setWindowTitle(f"{self.data_type.capitalize()} file metadata")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg=QColor(20, 20, 20))
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # METADATA TABLE
        self.metadata_table = self.create_metadata_table()
        layout.addSpacing(10)
        layout.addLayout(self.metadata_table)
        layout.addSpacing(10)
        self.setLayout(layout)
        self.setStyleSheet(GUIStyles.plots_config_popup_style())
        self.app.widgets[s.READER_METADATA_POPUP] = self
        self.center_window()

    def get_metadata_keys_dict(self):
        """
        Get mapping of metadata keys to display labels.
        
        Returns:
            dict: Mapping of metadata keys to human-readable labels
        """
        return {
            "channels": "Enabled Channels",
            "bin_width_micros": "Bin width (μs)",
            "acquisition_time_millis": "Acquisition time (s)",
            "laser_period_ns": "Laser period (ns)",
            "harmonics": "Harmonics",
            "tau_ns": "Tau (ns)",
        }

    def create_metadata_table(self):
        """
        Create formatted table displaying file metadata.
        
        Returns:
            QVBoxLayout: Layout containing metadata table
        """
        from core.phasors_controller import PhasorsController
        import os
        
        metadata_keys = self.get_metadata_keys_dict()
        v_box = QVBoxLayout()
        
        # For Phasors mode, show spectroscopy files metadata
        if self.data_type == "phasors":
            spectroscopy_metadata = self.app.reader_data[self.data_type].get("spectroscopy_metadata", [])
            spectroscopy_files = self.app.reader_data[self.data_type]["files"]["spectroscopy"]
            
            # Convert to list if needed
            if isinstance(spectroscopy_files, str):
                spectroscopy_files = [spectroscopy_files] if spectroscopy_files.strip() else []
            
            # Create grid layout (2 columns)
            from PyQt6.QtWidgets import QGridLayout
            grid_layout = QGridLayout()
            grid_layout.setSpacing(20)
            
            # Show each spectroscopy file with its metadata
            for file_idx, metadata in enumerate(spectroscopy_metadata):
                row = file_idx // 2
                col = file_idx % 2
                
                # Get color for this file
                color = PhasorsController.get_color_for_file_index(file_idx)
                file_path = spectroscopy_files[file_idx] if file_idx < len(spectroscopy_files) else f"file_{file_idx}"
                file_name = os.path.basename(file_path) if isinstance(file_path, str) else file_path
                
                # Create container for this file
                file_container = QVBoxLayout()
                file_container.setSpacing(0)
                
                def get_key_label_style(bg_color):
                    return f"width: 120px; font-size: 12px; border: 1px solid {bg_color}; padding: 6px; color: white; background-color: {bg_color}"

                def get_value_label_style(bg_color):
                    return f"width: 280px; font-size: 12px; border: 1px solid {bg_color}; padding: 6px; color: white"
                
                # File row with colored header
                h_box = QHBoxLayout()
                h_box.setContentsMargins(0, 0, 0, 0)
                h_box.setSpacing(0)
                key_label = QLabel("File")
                key_label.setStyleSheet(get_key_label_style(color))
                value_label = QLabel(file_name)
                value_label.setStyleSheet(get_value_label_style(color))
                h_box.addWidget(key_label)
                h_box.addWidget(value_label)
                file_container.addLayout(h_box)
                
                # Metadata rows (blue)
                for key, value in metadata_keys.items():
                    if key in metadata:
                        metadata_value = str(metadata[key])
                        if key == "channels":
                            metadata_value = ", ".join(
                                ["Channel " + str(ch + 1) for ch in metadata[key]]
                            )
                        if key == "acquisition_time_millis":
                            metadata_value = str(metadata[key] / 1000)
                        h_box = QHBoxLayout()
                        h_box.setContentsMargins(0, 0, 0, 0)
                        h_box.setSpacing(0)
                        key_label = QLabel(value)
                        value_label = QLabel(metadata_value)
                        key_label.setStyleSheet(get_key_label_style("#11468F"))
                        value_label.setStyleSheet(get_value_label_style("#11468F"))
                        h_box.addWidget(key_label)
                        h_box.addWidget(value_label)
                        file_container.addLayout(h_box)
                
                # Add file container to grid
                grid_layout.addLayout(file_container, row, col)
            
            v_box.addLayout(grid_layout)
        else:
            # Original single-file behavior for Spectroscopy/Fitting tabs
            metadata = self.app.reader_data[self.data_type]["metadata"]
            file = (
                self.app.reader_data[self.data_type]["files"][self.data_type]
                if self.data_type != "fitting"
                else self.app.reader_data[self.data_type]["files"]["spectroscopy"]
            )
            
            if metadata:
                title = QLabel(f"{self.data_type.upper()} FILE METADATA")
                title.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")

                def get_key_label_style(bg_color):
                    return f"width: 200px; font-size: 14px; border: 1px solid  {bg_color}; padding: 8px; color: white; background-color: {bg_color}"

                def get_value_label_style(bg_color):
                    return f"width: 500px; font-size: 14px; border: 1px solid  {bg_color}; padding: 8px; color: white"

                v_box.addWidget(title)
                v_box.addSpacing(10)
                h_box = QHBoxLayout()
                h_box.setContentsMargins(0, 0, 0, 0)
                h_box.setSpacing(0)
                key_label = QLabel("File")
                key_label.setStyleSheet(get_key_label_style("#DA1212"))
                value_label = QLabel(file)
                value_label.setStyleSheet(get_value_label_style("#DA1212"))
                h_box.addWidget(key_label)
                h_box.addWidget(value_label)
                v_box.addLayout(h_box)
                for key, value in metadata_keys.items():
                    if key in metadata:
                        metadata_value = str(metadata[key])
                        if key == "channels":
                            metadata_value = ", ".join(
                                ["Channel " + str(ch + 1) for ch in metadata[key]]
                            )
                        if key == "acquisition_time_millis":
                            metadata_value = str(metadata[key] / 1000)
                        h_box = QHBoxLayout()
                        h_box.setContentsMargins(0, 0, 0, 0)
                        h_box.setSpacing(0)
                        key_label = QLabel(value)
                        value_label = QLabel(metadata_value)
                        key_label.setStyleSheet(get_key_label_style("#11468F"))
                        value_label.setStyleSheet(get_value_label_style("#11468F"))
                        h_box.addWidget(key_label)
                        h_box.addWidget(value_label)
                        v_box.addLayout(h_box)
        return v_box

    def center_window(self):
        """
        Center the popup window on the screen.
        
        Returns:
            None: Moves window to center of screen
        """
        self.setMinimumWidth(500)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())


class WorkerSignals(QObject):
    """
    Qt signals for background worker tasks.
    
    Signals:
        success (str): Emitted when task completes successfully
        error (str): Emitted when task encounters an error
    """
    success = pyqtSignal(str)
    error = pyqtSignal(str)


class SavePlotTask(QRunnable):
    """
    Background task for saving plot images in multiple formats.
    
    This class handles saving matplotlib plots as PNG and EPS files
    in a background thread to prevent UI blocking.
    
    Attributes:
        plot: Matplotlib plot object to save
        base_path (str): Base file path for saving
        signals (WorkerSignals): Signal emitter for task completion
    """

    def __init__(self, plot, base_path, signals):
        """
        Initialize the save plot task.
        
        Args:
            plot: Matplotlib plot object to save
            base_path (str): Base file path for saving
            signals (WorkerSignals): Signal emitter for task completion
        """
        super().__init__()
        self.plot = plot
        self.base_path = base_path
        self.signals = signals

    @pyqtSlot()
    def run(self):
        """
        Execute the plot saving task.
        
        Saves the plot in both PNG and EPS formats and emits
        appropriate success or error signals.
        
        Returns:
            None: Emits signals based on operation result
        """
        try:
            # png
            png_path = (
                f"{self.base_path}.png"
                if not self.base_path.endswith(".png")
                else self.base_path
            )
            self.plot.savefig(png_path, format="png")
            # eps
            eps_path = (
                f"{self.base_path}.eps"
                if not self.base_path.endswith(".eps")
                else self.base_path
            )
            self.plot.savefig(eps_path, format="eps")
            plt.close(self.plot)
            self.signals.success.emit(
                f"Plot images saved successfully as {png_path} and {eps_path}"
            )
        except Exception as e:
            plt.close(self.plot)
            self.signals.error.emit(str(e))
