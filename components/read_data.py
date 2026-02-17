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
from utils.channel_name_utils import get_channel_name
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
                    file_magic_bytes = f.read(4)
                    if file_magic_bytes == magic_bytes:
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
        Read fitting data from JSON files (max 4 files).
        
        Args:
            window: Parent window for file dialogs
            app: Main application instance
            
        Returns:
            None: Updates app.reader_data with fitting data
        """
        dialog = QFileDialog()
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        filter_pattern = "JSON files (*fitting_result*.json)"
        dialog.setNameFilter(filter_pattern)
        file_names, _ = dialog.getOpenFileNames(window, "Load fitting files (max 4)", "", filter_pattern)
        
        if not file_names:
            return
        
        if len(file_names) > 4:
            ReadData.show_warning_message("Too many files", "You can select a maximum of 4 files. Only the first 4 will be loaded.")
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
                        valid_data.append({"file": file_name, "data": data, "channels": [item["channel"] for item in data]})
                        all_channels.extend([item["channel"] for item in data])
            except:
                pass
        
        if valid_data:
            app.reader_data["fitting"]["files"]["fitting"] = [item["file"] for item in valid_data]
            app.reader_data["fitting"]["data"]["fitting_data"] = [item["data"] for item in valid_data]
            app.reader_data["fitting"]["fitting_metadata"] = [item["channels"] for item in valid_data]
            app.reader_data["fitting"]["metadata"]["channels"] = list(set(all_channels))
            
            # Salva i file fitting caricati nelle settings
            app.settings.setValue("fitting_read_last_fitting_files", [item["file"] for item in valid_data])

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
        """
        Get preloaded fitting data if available.
        
        For multiple files, calculates the average of all channels per file.
        
        Args:
            app: Main application instance
            
        Returns:
            list or None: A list of averaged fitting results per file, or None if not available
        """
        fitting_files = app.reader_data["fitting"]["files"]["fitting"]
        has_files = (isinstance(fitting_files, list) and len(fitting_files) > 0) or (isinstance(fitting_files, str) and len(fitting_files.strip()) > 0)
        if has_files and app.acquire_read_mode == "read":
            fitting_data = app.reader_data["fitting"]["data"]["fitting_data"]
            if isinstance(fitting_data, list) and len(fitting_data) > 0:
                # Multiple files: calculate average of channels for each file
                averaged_results = []
                for file_index, file_data in enumerate(fitting_data):
                    file_results = convert_json_serializable_item_into_np_fitting_result(file_data)
                    if len(file_results) > 0:
                        # Get file name from path
                        file_name = os.path.basename(fitting_files[file_index]) if isinstance(fitting_files, list) else f"File {file_index + 1}"
                        averaged_result = ReadData._average_channels_for_file(file_results, file_index, file_name)
                        if averaged_result:
                            averaged_results.append(averaged_result)
                return averaged_results
            else:
                # Single file
                results = convert_json_serializable_item_into_np_fitting_result(fitting_data)
                # Add file_name and file_index to each result
                if results:
                    file_name = os.path.basename(fitting_files) if isinstance(fitting_files, str) else "File 1"
                    for result in results:
                        if "error" not in result:
                            result["file_name"] = file_name
                            result["file_index"] = 0
                return results
        return None

    @staticmethod
    def _average_channels_for_file(file_results, file_index, file_name=""):
        """
        Calculate the average of all channels for a single fitting file.
        
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
        min_len_y = min(len(r['y_data']) for r in valid_results)
        min_len_fitted = min(len(r['fitted_values']) for r in valid_results)
        min_len_residuals = min(len(r['residuals']) for r in valid_results)
        min_len_x = min(len(r['x_values']) for r in valid_results)
        min_len_t = min(len(r['t_data']) for r in valid_results)
        
        # Calculate averages with truncated arrays
        avg_chi2 = np.mean([r['chi2'] for r in valid_results])
        # Check if r2 exists in results (may not be present in older saved files)
        avg_r2 = np.mean([r.get('r2', 0) for r in valid_results]) if all('r2' in r for r in valid_results) else 0
        output_data = valid_results[0]['output_data']
        model = valid_results[0]['model']
        
        # Build fitted_params_text like in fitting_utilities.py (without file name)
        fitted_params_text = ""
        
        # Extract tau components from output_data
        component_num = 1
        while f'component_A{component_num}' in output_data:
            comp = output_data[f'component_A{component_num}']
            fitted_params_text += f'τ{component_num} = {comp["tau_ns"]:.4f} ns, {comp["percentage"]:.2%} of total\n'
            component_num += 1
        
        # Add B component
        if 'component_B' in output_data:
            # Calculate B percentage (this is approximation from first result)
            fitted_params_text += f'B component included\n'
        
        fitted_params_text += f'X² = {avg_chi2:.4f}\n'
        fitted_params_text += f'Model = {model}\n'
        fitted_params_text += f'R² = {avg_r2:.4f}\n'
        
        avg_result = {
            'x_values': valid_results[0]['x_values'][:min_len_x],
            't_data': valid_results[0]['t_data'][:min_len_t],
            'y_data': np.mean([r['y_data'][:min_len_y] for r in valid_results], axis=0),
            'fitted_values': np.mean([r['fitted_values'][:min_len_fitted] for r in valid_results], axis=0),
            'residuals': np.mean([r['residuals'][:min_len_residuals] for r in valid_results], axis=0),
            'fitted_params_text': fitted_params_text,
            'output_data': output_data,
            'scale_factor': np.mean([r['scale_factor'] for r in valid_results]),
            'decay_start': valid_results[0]['decay_start'],
            'channel': 0,
            'chi2': avg_chi2,
            'r2': avg_r2,
            'model': model,
            'file_index': file_index,
            'file_name': file_name
        }
        return avg_result

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
            
            # Check if we have multi-file data or traditional single-file data
            has_files_data = "files_data" in spectroscopy_data and len(spectroscopy_data["files_data"]) > 0
            has_traditional_data = "times" in spectroscopy_data and "channels_curves" in spectroscopy_data
            
            if (has_files_data or has_traditional_data) and not (metadata == {}):
                ReadData.plot_spectroscopy_data(
                    app,
                    spectroscopy_data.get("times"),
                    spectroscopy_data.get("channels_curves"),
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
        
        # Check if we're in read mode with multi-file data (works for both PHASORS and FITTING)
        data_type = "phasors" if app.tab_selected == s.TAB_PHASORS else "fitting"
        spectroscopy_data = app.reader_data[data_type]["data"]["spectroscopy_data"] if data_type == "fitting" else app.reader_data["phasors"]["data"]["spectroscopy_data"]
        is_multi_file = "files_data" in spectroscopy_data and len(spectroscopy_data.get("files_data", [])) > 0
        
        # In FITTING READ mode with multi-file data, collect all unique channels from all files
        if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read" and is_multi_file:
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
            period_ns = 1_000 / frequency_mhz if frequency_mhz != 0.0 else laser_period_ns
            
            # Use bin indices for FITTING READ, time values for PHASORS
            if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                x_values = np.arange(num_bins)
            else:
                x_values = np.linspace(0, period_ns, num_bins) if app.tab_selected == s.TAB_PHASORS else np.linspace(0, period_ns, num_bins) / 1_000
            
            # Get metadata for file names
            metadata_list = app.reader_data[data_type]["spectroscopy_metadata"] if data_type == "fitting" else app.reader_data["phasors"]["spectroscopy_metadata"]
            
            # Initialize structure to store multi-file plot items for time shift (FITTING READ only)
            if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                if not hasattr(app, 'multi_file_plots'):
                    app.multi_file_plots = {}
                if app.tab_selected not in app.multi_file_plots:
                    app.multi_file_plots[app.tab_selected] = {}
                        
            # Clear decay widgets first and add legend to the correct widgets
            widgets_to_clear = []
            if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                # In multi-file FITTING mode, use actual widget keys
                widgets_to_clear = list(app.decay_widgets.keys()) if hasattr(app, 'decay_widgets') else []
            else:
                # Normal mode, use plots_to_show
                widgets_to_clear = app.plots_to_show
            
            for ch in widgets_to_clear:
                if ch in app.decay_widgets:
                    widget = app.decay_widgets[ch]
                    widget.clear()
                    # Clear multi-file plots for this channel (FITTING READ only)
                    if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                        if hasattr(app, 'multi_file_plots') and app.tab_selected in app.multi_file_plots:
                            app.multi_file_plots[app.tab_selected][ch] = []
                    # Add legend if not already present
                    if widget.plotItem.legend is None:
                        legend = widget.addLegend(offset=(10, 10))
                        legend.setLabelTextColor('w')
            
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
                    file_name = metadata_list[file_idx].get("file_name", os.path.basename(file_data.get("file_path", f"File {file_idx + 1}")))
                elif "file_path" in file_data:
                    file_name = os.path.basename(file_data["file_path"])
                else:
                    file_name = f"File {file_idx + 1}"
                                
                for channel, curves in file_channels_curves.items():
                    # In multi-file FITTING READ, map all first channels to the display channel
                    if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                        # In FITTING READ multi-file mode, always map first channel to widget 0
                        # Use the first channel of each file, regardless of its physical number
                        if channel == 0:  # First channel index in channels_curves dict
                            logical_channel = app.plots_to_show[0] if app.plots_to_show else 0
                            # Always use widget key 0 for multi-file display
                            widget_key = list(app.decay_widgets.keys())[0] if app.decay_widgets else 0
                        else:
                            continue  # Skip other channels in multi-file READ mode
                    else:
                        # Normal mapping for PHASORS: use actual channel index from file
                        logical_channel = channel
                        widget_key = logical_channel
                    
                    if logical_channel in app.plots_to_show:
                        y_values = np.sum(curves, axis=0)
                        
                        # Accumulate y_values for caching
                        ch_idx = logical_channel
                        if ch_idx not in all_y_values_by_channel:
                            all_y_values_by_channel[ch_idx] = []
                        all_y_values_by_channel[ch_idx].append(y_values)
                        
                        # Apply time_shift first (from app.time_shifts)
                        time_shift = 0 if ch_idx not in app.time_shifts else app.time_shifts[ch_idx]
                        y_shifted = np.roll(y_values, time_shift)
                        
                        # Apply lin/log transformation based on current mode
                        y_to_plot = y_shifted
                        if ch_idx in current_lin_log_modes:
                            if current_lin_log_modes[ch_idx] == "LOG":
                                ticks, y_to_plot, _ = LinLogControl.calculate_log_mode(y_shifted)
                                ticks_by_channel[ch_idx] = ticks
                                if widget_key in app.decay_widgets:
                                    app.decay_widgets[widget_key].showGrid(x=False, y=True, alpha=0.3)
                            else:
                                ticks, y_to_plot = LinLogControl.calculate_lin_mode(y_shifted)
                                ticks_by_channel[ch_idx] = ticks
                                if widget_key in app.decay_widgets:
                                    app.decay_widgets[widget_key].showGrid(x=False, y=False)
                        
                        # Plot with specific color for this file and add to legend
                        if widget_key in app.decay_widgets:
                            pen = pg.mkPen(color=color, width=2)
                            # Clean file name for legend (remove path and extension)
                            legend_name = os.path.splitext(os.path.basename(file_name))[0] if file_name else f"File {file_idx + 1}"
                            plot_item = app.decay_widgets[widget_key].plot(x_values, y_to_plot, pen=pen, name=legend_name)
                            
                            # Save plot item with original y_values for time shift (FITTING READ only)
                            if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                                if hasattr(app, 'multi_file_plots') and app.tab_selected in app.multi_file_plots:
                                    # Use widget_key for multi-file plots storage
                                    if widget_key not in app.multi_file_plots[app.tab_selected]:
                                        app.multi_file_plots[app.tab_selected][widget_key] = []
                                    app.multi_file_plots[app.tab_selected][widget_key].append({
                                        'plot_item': plot_item,
                                        'y_values': y_values,  # Original values
                                        'file_idx': file_idx,
                                        'file_name': file_name
                                    })
            
            # Update ticks for each channel after plotting - use widget_key mapping
            for ch_idx, ticks in ticks_by_channel.items():
                # For multi-file FITTING mode, use widget key 0 instead of logical channel
                if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                    widget_key_for_ticks = list(app.decay_widgets.keys())[0] if app.decay_widgets else ch_idx
                else:
                    widget_key_for_ticks = ch_idx
                    
                if widget_key_for_ticks in app.decay_widgets:
                    app.decay_widgets[widget_key_for_ticks].getAxis("left").setTicks([ticks])
                    PlotsController.set_plot_y_range(app.decay_widgets[widget_key_for_ticks])
            
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
            period_ns = 1_000 / frequency_mhz if frequency_mhz != 0.0 else laser_period_ns
            x_values = np.linspace(0, period_ns, num_bins) if app.tab_selected == s.TAB_PHASORS else np.linspace(0, period_ns, num_bins) / 1_000
            
            # In FITTING tab READ mode, calculate average of all channels and show single plot
            if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
                all_y_values = []
                first_channel = None
                
                for channel, curves in channels_curves.items():
                    if channel < len(metadata_channels) and metadata_channels[channel] in app.plots_to_show:
                        y_values = np.sum(curves, axis=0)
                        all_y_values.append(y_values)
                        if first_channel is None:
                            first_channel = metadata_channels[channel]
                        # Cache individual channel values for fitting
                        app.cached_decay_values[app.tab_selected][metadata_channels[channel]] = y_values
                
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
                    if channel < len(metadata_channels) and metadata_channels[channel] in app.plots_to_show:
                        y_values = np.sum(curves, axis=0)
                        if app.tab_selected != s.TAB_PHASORS:
                            app.cached_decay_values[app.tab_selected][
                                metadata_channels[channel]
                            ] = y_values
                        PlotsController.update_plots(
                            app, metadata_channels[channel], x_values, y_values, reader_mode=True
                        )
        
        # Force refresh for all plot widgets to ensure curves are visible (same fix as popup)
        from PyQt6.QtCore import QTimer
        
        def force_main_plots_refresh():            
            # Use actual decay_widgets keys instead of plots_to_show to avoid channel mapping issues
            widgets_to_refresh = list(app.decay_widgets.keys()) if hasattr(app, 'decay_widgets') else []
            
            refreshed_count = 0
            for ch_key in widgets_to_refresh:
                if ch_key in app.decay_widgets:
                    plot_widget = app.decay_widgets[ch_key]

                    # Force update and autoRange to ensure curves are visible
                    plot_widget.update()
                    plot_widget.repaint()
                    plot_widget.autoRange()  # This is the key fix
                    
                    # Process Qt events to ensure changes are applied
                    from PyQt6.QtWidgets import QApplication
                    QApplication.processEvents()
                    
                    refreshed_count += 1
        
        # Schedule delayed refresh with longer delay to ensure data is loaded
        QTimer.singleShot(250, force_main_plots_refresh)

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
            list: List of dictionaries containing x, y, title, channel_index, time_shift, 
                  and optionally file_index and file_name for multi-file support
        """
        from utils.channel_name_utils import get_channel_name
        
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
        if "files_data" in spectroscopy_data and len(spectroscopy_data["files_data"]) > 0:
            # Multi-file mode: use the actual file times
            files_data = spectroscopy_data["files_data"]
            spectroscopy_metadata = app.reader_data["fitting"]["spectroscopy_metadata"]
            
            for file_idx, file_data in enumerate(files_data):
                file_channels_curves = file_data["channels_curves"]
                file_metadata = spectroscopy_metadata[file_idx] if file_idx < len(spectroscopy_metadata) else metadata
                file_name = file_metadata.get("file_name", f"File {file_idx + 1}")
                channels = file_metadata["channels"]
                
                # Get times for this specific file
                file_times = file_data["times"]
                
                # In multi-file mode, map all first channels to the display channel
                for channel, curves in file_channels_curves.items():
                    # Only process the first channel of each file
                    if channel == 0:
                        y_values = np.sum(curves, axis=0)
                        
                        # Match x_values length to y_values length
                        if len(file_times) >= len(y_values):
                            # Take first len(y_values) elements of times
                            x_values = np.array(file_times[:len(y_values)])
                        else:
                            # Times is shorter, generate x_values
                            x_values = np.linspace(0, laser_period_ns, len(y_values))
                        
                        # Use the display channel from plots_to_show
                        display_channel = app.plots_to_show[0] if app.plots_to_show else 0
                        channel_id = channels[channel]
                        # Get time_shift for this channel from app.time_shifts
                        channel_time_shift = 0 if display_channel not in app.time_shifts else app.time_shifts[display_channel]
                        data.append(
                            {
                                "x": x_values,
                                "y": y_values,
                                "title": get_channel_name(channel_id, app.channel_names),
                                "channel_index": display_channel,
                                "time_shift": channel_time_shift,
                                "file_index": file_idx,
                                "file_name": file_name
                            }
                        )
        else:
            # Single-file mode: check if we have actual times data
            if "times" in spectroscopy_data and spectroscopy_data["times"]:
                # Use actual times from data (already in correct units)
                x_values = np.array(spectroscopy_data["times"])  # Don't multiply by 1000
            else:
                # Fallback to linspace
                x_values = np.linspace(0, laser_period_ns, num_bins)
                        
            channels_curves = spectroscopy_data.get("channels_curves", {})
            channels = metadata["channels"]
            display_channel = app.plots_to_show[0] if app.plots_to_show else 0
            
            for channel, curves in channels_curves.items():
                if channels[channel] in app.plots_to_show:
                    y_values = np.sum(curves, axis=0)
                    
                    if app.tab_selected != s.TAB_PHASORS:
                        app.cached_decay_values[app.tab_selected][
                            channels[channel]
                        ] = y_values
                    
                    # Get time_shift for this channel from app.time_shifts
                    channel_time_shift = 0 if channels[channel] not in app.time_shifts else app.time_shifts[channels[channel]]
                    
                    data_entry = {
                        "x": x_values,
                        "y": y_values,
                        "title": get_channel_name(channels[channel], app.channel_names),
                        "channel_index": channels[channel],
                        "time_shift": channel_time_shift
                    }
                    data.append(data_entry)
                    
        for i, d in enumerate(data):
            has_file_info = 'file_index' in d
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
        from core.ui_controller import UIController
        if not read_mode:
            ControlsController.fit_button_hide(app)
        else:
            if ReadDataControls.fit_button_enabled(app):
                ControlsController.fit_button_show(app)  
            else:
                ControlsController.fit_button_hide(app)
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(app)
        app.control_inputs["bin_metadata_button"].setVisible(bin_metadata_btn_visible)
        app.control_inputs["start_button"].setVisible(not read_mode)
        app.control_inputs["read_bin_button"].setVisible(read_mode)
        app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
            bin_metadata_btn_visible and app.tab_selected != s.TAB_FITTING
        )
        
        if app.tab_selected == s.TAB_FITTING:
            app.control_inputs[s.LOAD_REF_BTN].setText("LOAD IRF")
            app.control_inputs[s.LOAD_REF_BTN].setVisible(not read_mode and app.use_deconvolution)
            if read_mode:
                app.control_inputs[s.LOAD_REF_BTN].hide()
                hide_layout(app.control_inputs["use_deconv_container"]) 
                if  UIController.show_ref_info_banner(app) == False:
                    hide_layout(app.widgets[s.REFERENCE_INFO_BANNER])
            else:
                show_layout(app.control_inputs["use_deconv_container"])
                if UIController.show_ref_info_banner(app):
                    UIController.update_reference_info_banner_label(app) 
                    show_layout(app.widgets[s.REFERENCE_INFO_BANNER])
         
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
            app.control_inputs[s.LOAD_REF_BTN].setText("LOAD REFERENCE")
            app.control_inputs[s.LOAD_REF_BTN].setVisible(not read_mode)
            if read_mode : 
                app.control_inputs[s.LOAD_REF_BTN].hide()
                if UIController.show_ref_info_banner(app) == False:
                    hide_layout(app.widgets[s.REFERENCE_INFO_BANNER])
                hide_layout(app.control_inputs["phasors_resolution_container"])
                hide_layout(app.control_inputs["quantize_phasors_container"])
                ControlsController.on_quantize_phasors_changed(app, False)
                app.settings.setValue(s.SETTINGS_QUANTIZE_PHASORS, False)
            else : 
                show_layout(app.control_inputs["quantize_phasors_container"])
                if UIController.show_ref_info_banner(app):
                    UIController.update_reference_info_banner_label(app)
                    show_layout(app.widgets[s.REFERENCE_INFO_BANNER])
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
        fitting_files = app.reader_data["fitting"]["files"]["fitting"]
        spectroscopy_file = app.reader_data["fitting"]["files"]["spectroscopy"]
        fitting_file_exists = (isinstance(fitting_files, list) and len(fitting_files) > 0) or (isinstance(fitting_files, str) and len(fitting_files.strip()) > 0)
        spectroscopy_file_exists = (isinstance(spectroscopy_file, list) and len(spectroscopy_file) > 0) or (isinstance(spectroscopy_file, str) and len(spectroscopy_file.strip()) > 0)
        
        result = tab_selected_fitting and read_mode and (fitting_file_exists or spectroscopy_file_exists)
        
        return result


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
        title.setStyleSheet("font-size: 16px; font-family: 'Montserrat'; font-weight: bold;")
        v_box.addWidget(title)
        
        radio_layout = QHBoxLayout()
        radio_layout.setSpacing(20)
        
        # Create button group for exclusive selection
        button_group = QButtonGroup(self)
        
        # Spectroscopy radio button
        spectroscopy_rb = QRadioButton("Spectroscopy files")
        spectroscopy_rb.setStyleSheet("""
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
        """)
        
        # Ripristina l'ultima selezione salvata (default: spectroscopy)
        last_selection = self.app.settings.value("fitting_read_last_file_type", "spectroscopy")
        
        spectroscopy_rb.setChecked(last_selection == "spectroscopy")
        spectroscopy_rb.toggled.connect(lambda checked: self.on_file_type_changed("spectroscopy", checked))
        button_group.addButton(spectroscopy_rb)
        self.file_type_checkboxes["spectroscopy"] = spectroscopy_rb
        radio_layout.addWidget(spectroscopy_rb)
        
        # Fitting radio button
        fitting_rb = QRadioButton("Fitting files")
        fitting_rb.setStyleSheet("""
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
        """)
        
        fitting_rb.setChecked(last_selection == "fitting")
        fitting_rb.toggled.connect(lambda checked: self.on_file_type_changed("fitting", checked))
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
        if hasattr(self, 'file_type_stack') and file_type in self.file_type_stack_indices:
            self.file_type_stack.setCurrentIndex(self.file_type_stack_indices[file_type])
        
        # Control metadata button visibility based on file type selection
        # Only for FITTING tab - other tabs are handled by read_bin_metadata_enabled()
        if hasattr(self.app, 'control_inputs') and 'bin_metadata_button' in self.app.control_inputs:
            current_tab = getattr(self.app, 'tab_selected', None)
            
            if current_tab == s.TAB_FITTING:
                metadata_button = self.app.control_inputs['bin_metadata_button']
                if file_type == "fitting":
                    # Hide metadata button when "Fitting files" is selected IN FITTING tab
                    metadata_button.setVisible(False)
                elif file_type == "spectroscopy":
                    # Show metadata button when "Spectroscopy files" is selected IN FITTING tab
                    metadata_button.setVisible(True)
            # For other tabs (PHASORS, etc.), visibility is handled by read_bin_metadata_enabled()
        
        # Store the current selection to check later if files were actually loaded
        self.current_file_type_selection = file_type
    
    def check_and_restore_file_type_selection(self):
        """Check if fitting files are actually loaded, if not restore to spectroscopy selection."""
        if hasattr(self, 'current_file_type_selection') and self.current_file_type_selection == "fitting":
            # Check if fitting files are actually loaded
            fitting_files = self.app.reader_data["fitting"]["files"]["fitting"]
            has_fitting_files = (isinstance(fitting_files, list) and len(fitting_files) > 0) or \
                               (isinstance(fitting_files, str) and len(fitting_files.strip()) > 0)
            
            if not has_fitting_files:
                # No fitting files loaded, restore to spectroscopy selection
                if hasattr(self, 'file_type_checkboxes') and "spectroscopy" in self.file_type_checkboxes:
                    self.file_type_checkboxes["spectroscopy"].setChecked(True)
                    # This will trigger on_file_type_changed with spectroscopy=True
            else:
                # Fitting files are loaded, ensure metadata button stays hidden
                if hasattr(self.app, 'control_inputs') and 'bin_metadata_button' in self.app.control_inputs:
                    metadata_button = self.app.control_inputs['bin_metadata_button']
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
            if (file_type == "phasors" and self.data_type == "phasors") or (
                file_type == "fitting" and self.data_type == "fitting"
            ):
                input_desc = QLabel(f"LOAD RELATED {file_type.upper()} FILE:")
            else:
                input_desc = QLabel(f"LOAD {file_type.upper()} FILE:")
            if self.data_type == "phasors" or self.data_type == "fitting":
                input_desc.setText(input_desc.text().replace("FILE", "FILES (MAX 4)"))
            input_desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
            control_row = QHBoxLayout()

            file_extension = ".json" if file_type == "fitting" else ".bin"

            def on_change(file_type=file_type):
                def callback(text):
                    self.on_loaded_file_change(text, file_type)

                return callback

            display_text = ""
            if isinstance(file_path, list):
                display_text = file_path[0] if len(file_path) == 1 else f"{len(file_path)} file(s) loaded" if len(file_path) > 1 else ""
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
                    load_file_btn.clicked.connect(partial(self.on_load_file_btn_clicked_phasors, file_type))
                elif file_type == "laserblood_metadata":
                    load_file_btn.clicked.connect(partial(self.on_load_file_btn_clicked_phasors_metadata, file_type))
                else:
                    load_file_btn.clicked.connect(partial(self.on_load_file_btn_clicked, file_type))
            elif self.data_type == "fitting":
                if file_type == "spectroscopy":
                    # Use main branch logic extended for multi-file support
                    load_file_btn.clicked.connect(partial(self.on_load_file_btn_clicked_main_branch_logic, file_type))
                elif file_type == "fitting":
                    load_file_btn.clicked.connect(partial(self.on_load_file_btn_clicked, file_type))
            else:
                load_file_btn.clicked.connect(partial(self.on_load_file_btn_clicked, file_type))
            
            # Create container for this input row
            container = QWidget()
            container_layout = QVBoxLayout()
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(10)
            
            control_row.addWidget(input)
            control_row.addWidget(load_file_btn)
            container_layout.addWidget(input_desc)
            container_layout.addSpacing(10)
            container_layout.addLayout(control_row)
            container.setLayout(container_layout)
            
            # Store container for show/hide control
            self.file_input_containers[file_type] = container
            
            # For fitting tab, add container to stacked widget instead of directly to layout
            if self.data_type == "fitting" and hasattr(self, 'file_type_stack'):
                index = self.file_type_stack.addWidget(container)
                self.file_type_stack_indices[file_type] = index
            else:
                # For other tabs, add directly to layout
                v_box.addWidget(container)
                v_box.addSpacing(10)
        
        # Add the stacked widget to layout for fitting tab
        if self.data_type == "fitting" and hasattr(self, 'file_type_stack'):
            v_box.addWidget(self.file_type_stack)
            # Set initial visible widget based on last selection saved in settings
            last_selection = self.app.settings.value("fitting_read_last_file_type", "spectroscopy")
            
            # Show the correct section based on the saved selection
            if last_selection == "fitting" and "fitting" in self.file_type_stack_indices:
                self.file_type_stack.setCurrentIndex(self.file_type_stack_indices["fitting"])
            elif "spectroscopy" in self.file_type_stack_indices:
                self.file_type_stack.setCurrentIndex(self.file_type_stack_indices["spectroscopy"])
        
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
            
            # In FITTING READ mode, show only first channel (will display average)
            if self.data_type == "fitting" and self.app.acquire_read_mode == "read":
                plots_to_show = [selected_channels[0]] if len(selected_channels) > 0 else []
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
            channels_layout = QVBoxLayout()
            desc = QLabel("CHOOSE MAX 4 PLOTS TO DISPLAY:")
            desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
            grid = QGridLayout()
            
            # Get channel names from binary metadata (not from session)
            binary_metadata = self.app.reader_data.get(self.data_type, {}).get("metadata", {})
            metadata_channel_names = binary_metadata.get("channels_name", {}) if isinstance(binary_metadata, dict) else {}
            # Ensure it's always a dict, never None
            if not isinstance(metadata_channel_names, dict):
                metadata_channel_names = {}
            
            for ch in selected_channels:
                channel_name = get_channel_name(ch, metadata_channel_names)
                checkbox, checkbox_wrapper = self.set_checkboxes(channel_name)
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
        has_fitting = (isinstance(fitting_data, list) and len(fitting_data) > 0) or (isinstance(fitting_data, dict) and bool(fitting_data))
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
        
        # Enable button based on data type
        if self.data_type == "phasors":
            phasors_files = self.app.reader_data["phasors"]["files"]["phasors"]
            spectroscopy_files = self.app.reader_data["phasors"]["files"]["spectroscopy"]
            both_files_present = len(phasors_files) > 0 and len(spectroscopy_files) > 0
            plot_btn.setEnabled(both_files_present)
        else:
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
        
        # Update FIT button visibility when files change
        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)
        

    def on_load_file_btn_clicked(self, file_type):
        """
        Handle file load button click event.
        
        Args:
            file_type (str): Type of file to load ('fitting', 'spectroscopy', or 'phasors')
            
        Returns:
            None: Reads the selected file and updates the UI
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
        
        if file_type == "fitting":
            ReadData.read_fitting_data(self, self.app)
            # After loading fitting data, ensure metadata button remains hidden
            if hasattr(self.app, 'control_inputs') and 'bin_metadata_button' in self.app.control_inputs:
                metadata_button = self.app.control_inputs['bin_metadata_button']
                metadata_button.setVisible(False)
        else:
            ReadData.read_bin_data(self, self.app, self.tab_selected, file_type)
        file_path = self.app.reader_data[self.data_type]["files"][file_type]
        file_name = file_path[0] if isinstance(file_path, list) and len(file_path) > 0 else file_path if isinstance(file_path, str) else ""
        has_files = (isinstance(file_path, list) and len(file_path) > 0) or (isinstance(file_path, str) and len(file_path) > 0)
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
            display_name = f"{len(file_path)} file(s) loaded" if isinstance(file_path, list) and len(file_path) > 1 else file_name
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
                        phasors_file = self.app.reader_data["phasors"]["files"]["phasors"]
                        spectroscopy_file = self.app.reader_data["phasors"]["files"]["spectroscopy"]
                        phasors_loaded = (isinstance(phasors_file, list) and len(phasors_file) > 0) or (isinstance(phasors_file, str) and len(phasors_file.strip()) > 0)
                        spectroscopy_loaded = (isinstance(spectroscopy_file, list) and len(spectroscopy_file) > 0) or (isinstance(spectroscopy_file, str) and len(spectroscopy_file.strip()) > 0)
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
            spectroscopy_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"]
            has_fitting = (isinstance(fitting_data, list) and len(fitting_data) > 0) or (isinstance(fitting_data, dict) and bool(fitting_data))
            has_spectroscopy = bool(spectroscopy_data)
            if has_fitting and not has_spectroscopy:
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
            has_fitting = (isinstance(file_fitting, list) and len(file_fitting) > 0) or (isinstance(file_fitting, str) and len(file_fitting.strip()) > 0)
            has_spectroscopy = (isinstance(file_spectroscopy, list) and len(file_spectroscopy) > 0) or (isinstance(file_spectroscopy, str) and len(file_spectroscopy.strip()) > 0)
            if not has_fitting or not has_spectroscopy:
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
        has_fitting = (isinstance(fitting_data, list) and len(fitting_data) > 0) or (isinstance(fitting_data, dict) and bool(fitting_data))
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
            spectroscopy_files = self.app.reader_data["fitting"]["files"]["spectroscopy"]
            # Handle both string and list formats
            if isinstance(spectroscopy_files, list):
                has_spectroscopy = len(spectroscopy_files) > 0
            else:
                has_spectroscopy = bool(spectroscopy_files and len(spectroscopy_files.strip()) > 0)
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
        valid_files = ReadData.read_multiple_bin_data(self, self.app, self.tab_selected, file_type)
        if not valid_files:
            return
    
        # Clear fitting data when loading new spectroscopy files
        self.app.reader_data["fitting"]["files"]["fitting"] = ""
        self.app.reader_data["fitting"]["data"]["fitting_data"] = []
    
        # Clear previous spectroscopy data
        self.app.reader_data["fitting"]["files"]["spectroscopy"] = []
        self.app.reader_data["fitting"]["spectroscopy_metadata"] = []
        self.app.reader_data["fitting"]["data"]["spectroscopy_data"] = {"files_data": []}
        
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
                        result = ReadData.read_spectroscopy_data(f, file_path, file_type, self.tab_selected, self.app)
                        if result:
                            file_name, file_type_result, times, channels_curves, metadata = result
                        
                            # Add file_name to metadata for multi-file tracking
                            metadata["file_name"] = os.path.basename(file_path)
                        
                            # Accumulate metadata
                            self.app.reader_data["fitting"]["spectroscopy_metadata"].append(metadata)
                        
                            # Store per-file data
                            if "files_data" not in self.app.reader_data["fitting"]["data"]["spectroscopy_data"]:
                                self.app.reader_data["fitting"]["data"]["spectroscopy_data"]["files_data"] = []
                            self.app.reader_data["fitting"]["data"]["spectroscopy_data"]["files_data"].append({
                                "file_path": file_path,
                                "times": times,
                                "channels_curves": channels_curves
                            })
            except Exception as e:
                continue
        
        # Convert files_data to times and channels_curves for plotting compatibility
        # Average all files and all curves within each channel
        files_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"].get("files_data", [])
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
                            interp_curve = np.interp(unified_times, np.array(file_times) * 1000, curve)
                            all_channels_data[channel_idx].append(interp_curve)
                        else:
                            # If times don't match, just use the curve as is
                            all_channels_data[channel_idx].append(curve)
            # Keep files_data intact for multi-file visualization
            # The plotting logic will handle showing individual curves with different colors
            self.app.reader_data["fitting"]["data"]["spectroscopy_data"]["times"] = unified_times.tolist()
            self.app.reader_data["fitting"]["metadata"] = first_metadata
        
        # Update UI with loaded files count
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self.app)
        self.app.control_inputs["bin_metadata_button"].setVisible(bin_metadata_btn_visible)
        self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(False)  # Not visible for fitting tab
        
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
            spectroscopy_files = self.app.reader_data["fitting"]["files"]["spectroscopy"]
            has_spectroscopy = isinstance(spectroscopy_files, list) and len(spectroscopy_files) > 0
            
            if len(self.app.reader_data['fitting']['data']['spectroscopy_data'].get('files_data', [])) > 0:
                first_file = self.app.reader_data['fitting']['data']['spectroscopy_data']['files_data'][0]
            self.widgets["plot_btn"].setEnabled(has_spectroscopy)
            if has_spectroscopy:
                self.widgets["plot_btn"].setText("PLOT DATA")
                ControlsController.fit_button_show(self.app)
    
    def closeEvent(self, event):
        """Handle window close event to restore file type selection if needed."""
        # Check if fitting files selection was made but no files were loaded
        self.check_and_restore_file_type_selection()
        super().closeEvent(event)

  

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
        
        # Check if we have multi-file metadata (phasors mode OR spectroscopy/fitting with multiple files)
        spectroscopy_metadata = []
        spectroscopy_files = []
        
        if self.data_type == "phasors":
            spectroscopy_metadata = self.app.reader_data[self.data_type].get("spectroscopy_metadata", [])
            spectroscopy_files = self.app.reader_data[self.data_type]["files"]["spectroscopy"]
        elif self.data_type in ["spectroscopy", "fitting"]:
            # Check if spectroscopy_metadata exists for multi-file mode
            spectroscopy_metadata = self.app.reader_data[self.data_type].get("spectroscopy_metadata", [])
            if spectroscopy_metadata:
                # Multi-file mode for spectroscopy/fitting
                spectroscopy_files = (
                    self.app.reader_data[self.data_type]["files"][self.data_type]
                    if self.data_type != "fitting"
                    else self.app.reader_data[self.data_type]["files"]["spectroscopy"]
                )
        
        # Use multi-file layout if we have multiple metadata entries
        if spectroscopy_metadata and len(spectroscopy_metadata) > 0:
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
                            # Get channel names from this file's metadata
                            file_channel_names = metadata.get("channels_name", {}) if isinstance(metadata, dict) else {}
                            if not isinstance(file_channel_names, dict):
                                file_channel_names = {}
                            metadata_value = ", ".join(
                                [get_channel_name(ch, file_channel_names) for ch in metadata[key]]
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
            
            # Handle case where file is a list (multi-file)
            if isinstance(file, list):
                file = ", ".join(file) if file else "No files loaded"
            elif not file:
                file = "No file loaded"
            
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
                            # Get channel names from binary metadata
                            metadata_channel_names = metadata.get("channels_name", {}) if isinstance(metadata, dict) else {}
                            if not isinstance(metadata_channel_names, dict):
                                metadata_channel_names = {}
                            metadata_value = ", ".join(
                                [get_channel_name(ch, metadata_channel_names) for ch in metadata[key]]
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
