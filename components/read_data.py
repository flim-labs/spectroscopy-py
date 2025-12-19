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
from utils.fitting_utilities import convert_json_serializable_item_into_np_fitting_result
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
    QScrollArea
)
from PyQt6.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, QObject, pyqtSlot
from PyQt6.QtGui import QColor, QIcon
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
    def read_laserblood_metadata(window, app, tab_selected):
        """Reads LaserBlood-specific metadata from a JSON file.

        Args:
            window: The parent window for the file dialog.
            app: The main application instance.
            tab_selected (str): The currently active tab identifier.
        """
        active_tab = ReadData.get_data_type(tab_selected)
        result = ReadData.read_json(window, "Laserblood metadata", "laserblood_metadata")
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
        """Reads fitting results from a JSON file.

        Args:
            window: The parent window for the file dialog.
            app: The main application instance.
        """
        result = ReadData.read_json(window, "Fitting", "fitting_result")
        if None in result:
            return
        file_name, data = result
        if data is not None:
            active_channels = [item["channel"] for item in data]
            app.reader_data["fitting"]["files"]["fitting"] = file_name
            app.reader_data["fitting"]["data"]["fitting_data"] = data
            app.reader_data["fitting"]["metadata"]["channels"] = active_channels

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
            return [item["channel"] for item in data]
        return []


    @staticmethod
    def preloaded_fitting_data(app):
        """Retrieves and parses preloaded fitting data if available.

        Args:
            app: The main application instance.

        Returns:
            list or None: A list of parsed fitting results, or None if not available.
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
    def read_json(window, file_type, filter_string = None):
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
            times (list): A list of timestamps for the measurements.
            channels_curves (dict): A dictionary of decay curve data per channel.
            laser_period_ns (float): The laser period in nanoseconds.
            metadata_channels (list): A list of active channel indices from metadata.
        """
        from core.plots_controller import PlotsController
        num_bins = 256
        x_values = np.linspace(0, laser_period_ns, num_bins) / 1_000
        for channel, curves in channels_curves.items():
            if metadata_channels[channel] in app.plots_to_show:
                y_values = np.sum(curves, axis=0)
                if app.tab_selected != s.TAB_PHASORS:
                    app.cached_decay_values[app.tab_selected][
                        metadata_channels[channel]
                    ] = y_values
                PlotsController.update_plots(
                    app,
                    metadata_channels[channel], x_values, y_values, reader_mode=True
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
            app: The main application instance.
            data (dict): The phasor data grouped by harmonic {harmonic: [(g, s, file_name), ...]}.
            harmonics (int): Maximum harmonic value.
            laser_period_ns (float): Laser period in nanoseconds.
        
        This method now handles multi-file data where each point is tagged with its source file.
        """
        from core.controls_controller import ControlsController
        from core.phasors_controller import PhasorsController
        frequency_mhz = ns_to_mhz(laser_period_ns)
        app.all_phasors_points = PhasorsController.get_empty_phasors_points()
        app.control_inputs[s.HARMONIC_SELECTOR].setCurrentIndex(0)
        if harmonics > 1:
            app.harmonic_selector_shown = True
            ControlsController.show_harmonic_selector(app, harmonics)
        for harmonic, values in data.items():
            print("harmonic", harmonic)
            if harmonic == 1:
                PhasorsController.draw_points_in_phasors(app, 0, harmonic, values)
            app.all_phasors_points[0][harmonic].extend(values)       
        #PhasorsController.generate_phasors_cluster_center(app, app.phasors_harmonic_selected)
        #PhasorsController.generate_phasors_legend(app, app.phasors_harmonic_selected)       
        #for i, channel_index in enumerate(app.plots_to_show):
            #PhasorsController.draw_lifetime_points_in_phasors(
                #app,
                #channel_index,
                #app.phasors_harmonic_selected,
                #laser_period_ns,
                #frequency_mhz,
            #)

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
    def read_bin(window, app, magic_bytes, file_type, read_data_cb, tab_selected, filter_string = None):
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
                app.reader_data["phasors"]["data"]["phasors_data"].setdefault(channel_name, {}).setdefault(harmonic_name, []).append((g, s, file_name))           
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
        if "laser_period_ns" in metadata:
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
        if "laser_period_ns" in metadata:
            return ns_to_mhz(metadata["laser_period_ns"])
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
            return ReadData.get_spectroscopy_frequency_mhz(app)
        elif app.tab_selected == s.TAB_PHASORS:
            return ReadData.get_phasors_frequency_mhz(app)
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
        if app.acquire_read_mode == 'read':
            metadata = app.reader_data[ReadData.get_data_type(app.tab_selected)]["metadata"]
            if metadata and "laser_period_ns" in metadata:
                x_values = np.linspace(0, metadata["laser_period_ns"], 256) / 1_000
                return x_values
        return None    
        
    def prepare_spectroscopy_data_for_export_img(app):
        """Prepares spectroscopy data for exporting as an image.

        Args:
            app: The main application instance.

        Returns:
            tuple: A tuple containing channels_curves, times, and metadata.
        """
        metadata = app.reader_data["spectroscopy"]["metadata"]
        channels_curves = app.reader_data["spectroscopy"]["data"]["channels_curves"]
        times = app.reader_data["spectroscopy"]["data"]["times"]
        return channels_curves, times, metadata

    @staticmethod
    def prepare_phasors_data_for_export_img(app):
        """Prepares phasors and related spectroscopy data for exporting as an image.

        Args:
            app: The main application instance.

        Returns:
            tuple: A tuple containing all necessary data for plotting.
        """
        phasors_data = app.reader_data["phasors"]["data"]["phasors_data"]
        laser_period = app.reader_data["phasors"]["metadata"]["laser_period_ns"]
        active_channels = app.reader_data["phasors"]["metadata"]["channels"]
        spectroscopy_curves = app.reader_data["phasors"]["data"]["spectroscopy_data"][
            "channels_curves"
        ]
        spectroscopy_times = app.reader_data["phasors"]["data"]["spectroscopy_data"][
            "times"
        ]
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
            PlotsController.generate_plots(app, ReadData.get_frequency_mhz(app))
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
            phasors_file = app.reader_data[data_type]["files"]["phasors"]
            return (
                not (len(metadata) == 0)
                and not (len(phasors_file) == 0)
                and app.acquire_read_mode == "read"
            )

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
        fitting_file = app.reader_data["fitting"]["files"]["fitting"]
        spectroscopy_file = app.reader_data["fitting"]["files"]["spectroscopy"]
        fitting_file_exists = len(fitting_file.strip()) > 0
        spectroscopy_file_exists = len(spectroscopy_file.strip()) > 0
        return tab_selected_fitting and read_mode and (
            fitting_file_exists or spectroscopy_file_exists
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
        """Initializes the UI for loading different types of data files.

        Returns:
            QVBoxLayout: The layout containing the file input controls.
        """
        v_box = QVBoxLayout()
        files = self.app.reader_data[self.data_type]["files"]
        for file_type, file_path in files.items():
            if (file_type == "phasors" and self.data_type == "phasors") or (
                file_type == "fitting" and self.data_type == "fitting"
            ):
                input_desc = QLabel(f"LOAD RELATED {file_type.upper()} FILE:")
            elif file_type == "spectroscopy":
                input_desc = QLabel(f"LOAD A {file_type.upper()} FILE:")
            else:
                file_name = file_type.upper().replace('_', ' ')
                input_desc = QLabel(f"LOAD A {file_name} FILE:")
            # Modifica: aggiungi "S" a "FILE" solo per PHASORS-READ
            if self.data_type == "phasors":
                input_desc.setText(input_desc.text().replace("FILE", "FILES"))
            input_desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
            control_row = QHBoxLayout()

            file_extension = ".json" if file_type == "fitting" or  file_type == "laserblood_metadata" else ".bin"

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
            # ma solo per file binari (spectroscopy e phasors), non per laserblood_metadata
            if self.data_type == "phasors" and file_type in ["spectroscopy", "phasors"]:
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
        """Creates the layout containing the 'Plot Data' or 'Fit Data' button.

        Returns:
            QHBoxLayout: The layout with the main action button.
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
        """Handles changes to the file path input field.

        Args:
            text (str): The new file path.
            file_type (str): The type of file associated with the input.
        """
        from core.plots_controller import PlotsController
        from core.controls_controller import ControlsController
        if (text != self.app.reader_data[self.data_type]["files"][file_type] 
            and file_type != "laserblood_metadata"):
            PlotsController.clear_plots(self.app)
            PlotsController.generate_plots(self.app)
            ControlsController.toggle_intensities_widgets_visibility(self.app)
        self.app.reader_data[self.data_type]["files"][file_type] = text
   
        

    def on_load_file_btn_clicked(self, file_type):
        """Handles the click event for the 'load file' button.

        Args:
            file_type (str): The type of file to load.
        """
        from core.controls_controller import ControlsController
        
        if file_type == "laserblood_metadata":
            ReadData.read_laserblood_metadata(self, self.app, self.tab_selected)
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
            if file_type != "laserblood_metadata":
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
    
        # Assicurati che files[file_type] sia una lista per PHASORS
        if not isinstance(self.app.reader_data[self.data_type]["files"][file_type], list):
            # Converte stringa esistente in lista (se non vuota) o crea lista vuota
            existing_file = self.app.reader_data[self.data_type]["files"][file_type]
            if existing_file and existing_file.strip():
                self.app.reader_data[self.data_type]["files"][file_type] = [existing_file]
            else:
                self.app.reader_data[self.data_type]["files"][file_type] = []
                
        # Accumula i path dei file
        self.app.reader_data[self.data_type]["files"][file_type].extend(valid_files)
    
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
                                if "times" not in self.app.reader_data[self.data_type]["data"]["spectroscopy_data"]:
                                    self.app.reader_data[self.data_type]["data"]["spectroscopy_data"] = {"times": [], "channels_curves": {}}
                                self.app.reader_data[self.data_type]["data"]["spectroscopy_data"]["times"].extend(times)
                                for ch, curves in channels_curves.items():
                                    if ch not in self.app.reader_data[self.data_type]["data"]["spectroscopy_data"]["channels_curves"]:
                                        self.app.reader_data[self.data_type]["data"]["spectroscopy_data"]["channels_curves"][ch] = []
                                    self.app.reader_data[self.data_type]["data"]["spectroscopy_data"]["channels_curves"][ch].extend(curves)
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
        """Checks for data consistency errors, like channel mismatches between files.

        Args:
            file_type (str): The data type to check.

        Returns:
            bool: True if an error is found, False otherwise.
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
        """Handles the click event for the main 'Plot Data' or 'Fit Data' button."""
        from core.controls_controller import ControlsController
        file_type = self.data_type
        if self.errors_in_data(file_type):
            return
        fitting_data = self.app.reader_data["fitting"]["data"]["fitting_data"]
        spectroscopy_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"]
        if fitting_data and not spectroscopy_data:
           ControlsController.on_fit_btn_click(self.app)           
        else:
            ReadData.plot_data(self.app)
        self.close()

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
            key = item["label"] + " (" + item["unit"] + ")" if item["unit"] else item["label"]
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
        key_label.setStyleSheet(f"width: 200px; font-size: 14px; border: 1px solid {key_bg_color}; padding: 8px; color: white; background-color: {key_bg_color}")
        value_label = QLabel(value)
        value_label.setStyleSheet(f"width: 500px; font-size: 14px; border: 1px solid {value_bg_color}; padding: 8px; color: white")
        h_box.addWidget(key_label)
        h_box.addWidget(value_label)
        return h_box

    def create_metadata_table(self):
        """Creates the main layout displaying all metadata in a table-like format.

        Returns:
            QVBoxLayout: The layout containing all metadata rows.
        """
        metadata_keys = self.get_metadata_keys_dict()
        metadata = self.app.reader_data[self.data_type]["metadata"]
        laserblood_metadata = self.app.reader_data[self.data_type]["laserblood_metadata"]
        file = self.app.reader_data[self.data_type]["files"][self.data_type]
        
        file = (
            self.app.reader_data[self.data_type]["files"][self.data_type]
            if self.data_type != "fitting"
            else self.app.reader_data[self.data_type]["files"]["spectroscopy"]
        )
        v_box = QVBoxLayout()
        v_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        title = QLabel(f"{self.data_type.upper()} FILE METADATA")
        title.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
        v_box.addWidget(title)
        v_box.addSpacing(10)
        file_info_row = self.create_label_row("File", file, "#DA1212", "#DA1212")
        v_box.addLayout(file_info_row)
        if laserblood_metadata:            
            parsed_laserblood_metadata = self.parse_laserblood_metadata(laserblood_metadata)        
            for key, value in parsed_laserblood_metadata.items():
                metadata_row = self.create_label_row(key, str(value), "#11468F", "#11468F")
                v_box.addLayout(metadata_row)
        else:
            if metadata:
                for key, value in metadata_keys.items():
                    if key in metadata:
                        metadata_value = str(metadata[key])
                        if key == "channels":
                            metadata_value = ", ".join(["Channel " + str(ch + 1) for ch in metadata[key]])
                        if key == "acquisition_time_millis":
                            metadata_value = str(metadata[key] / 1000)
                        metadata_row = self.create_label_row(value, metadata_value, "#11468F", "#11468F")
                        v_box.addLayout(metadata_row)
        return v_box
    
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
