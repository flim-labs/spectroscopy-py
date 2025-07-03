import os
import json
from datetime import datetime
import re
from PyQt6.QtWidgets import QFileDialog
from laserblood_settings import LASER_TYPES
from settings import DEFAULT_BIN_WIDTH, SETTINGS_BIN_WIDTH, SETTINGS_TAU_NS


class FileUtils:
    @staticmethod
    def directory_selector(window):
        folder_path = QFileDialog.getExistingDirectory(window, "Select Directory")
        return folder_path

    @staticmethod
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

    @staticmethod
    def get_recent_time_tagger_file():
        data_folder = os.path.join(os.environ["USERPROFILE"], ".flim-labs", "data")
        files = [
            f
            for f in os.listdir(data_folder)
            if f.startswith("time_tagger_spectroscopy")
        ]
        files.sort(
            key=lambda x: os.path.getmtime(os.path.join(data_folder, x)), reverse=True
        )
        return os.path.join(data_folder, files[0])

    @staticmethod
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

    @staticmethod
    def rename_bin_file(source_file, new_filename, window):
        laser_key, filter_key = FileUtils.get_laser_and_filter_names_info(window)
        _, file_extension = os.path.splitext(source_file)
        base_name = os.path.basename(source_file).replace(file_extension, "")
        base_name = base_name.replace("spectroscopy-phasors", "phasors-spectroscopy")
        dest_file_name = (
            f"{new_filename}_{laser_key}_{filter_key}_{base_name}{file_extension}"
        )
        return dest_file_name

    @staticmethod
    def get_laser_and_filter_names_info(window):
        filter_wavelength_input = next(
            (
                input
                for input in window.laserblood_settings
                if input["LABEL"] == "Emission filter wavelength"
            ),
            None,
        )
        laser_key, filter_key = FileUtils.get_laser_info_slug(
            window, filter_wavelength_input
        )
        return laser_key, filter_key

    @staticmethod
    def save_laserblood_metadata_json(
        filename, dest_path, window, timestamp, reference_files
    ):
        filter_wavelength_input = next(
            (
                input
                for input in window.laserblood_settings
                if input["LABEL"] == "Emission filter wavelength"
            ),
            None,
        )
        parsed_data = FileUtils.parse_metadata_output(window, reference_files, timestamp)
        laser_key, filter_key = FileUtils.get_laser_info_slug(
            window, filter_wavelength_input
        )
        filename = FileUtils.clean_filename(
            f"{timestamp}_{laser_key}_{filter_key}_{filename}_laserblood_metadata"
        )
        new_filename = f"{filename}.json"
        file_path = os.path.join(dest_path, new_filename)
        with open(file_path, "w") as json_file:
            json.dump(parsed_data, json_file, indent=4)
        return file_path

    @staticmethod
    def parse_metadata_output(app, reference_files, timestamp):
        from core.controls_controller import ControlsController
        reference_filenames = [file.rsplit("\\", 1)[-1] for file in reference_files]
        reference_filenames = [os.path.basename(file) for file in reference_filenames]
        filenames_string = ", ".join(reference_filenames)
        laser_type = app.laserblood_laser_type
        filter_type = app.laserblood_filter_type
        metadata_settings = app.laserblood_settings
        custom_fields_settings = app.laserblood_new_added_inputs
        filter_wavelength_input = next(
            (
                input
                for input in app.laserblood_settings
                if input["LABEL"] == "Emission filter wavelength"
            ),
            None,
        )
        parsed_filter_type = (
            filter_type + " " + filter_wavelength_input["VALUE"]
            if filter_type in ["LP", "SP"]
            else filter_wavelength_input["VALUE"]
        )
        frequency_mhz = ControlsController.get_frequency_mhz(app)
        firmware_selected, connection_type = ControlsController.get_firmware_selected(app, frequency_mhz)
        firmware_selected_name = os.path.basename(firmware_selected)
        num_replicate = app.replicates
        parsed_data = [
            {"label": "Acquisition Files", "unit": "", "value": filenames_string},
            {"label": "Acquisition Timestamp", "unit": "", "value": timestamp},
            {"label": "Replicate", "unit": "", "value": num_replicate},
            {"label": "Laser type", "unit": "", "value": laser_type},
            {"label": "Emission filter type", "unit": "", "value": parsed_filter_type},
            {"label": "Firmware selected", "unit": "", "value": firmware_selected_name},
            {"label": "Connection type", "unit": "", "value": connection_type},
            {"label": "Frequency", "unit": "Mhz", "value": frequency_mhz},
            {
                "label": "Enabled channels",
                "unit": "",
                "value": [ch + 1 for ch in app.selected_channels],
            },
            {
                "label": "Acquisition time",
                "unit": "s",
                "value": round(
                    (app.cps_counts[app.selected_channels[0]]["last_time_ns"])
                    / 1_000_000_000,
                    2,
                ),
            },
            {
                "label": "Bin width",
                "unit": "µs",
                "value": int(app.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH)),
            },
            {
                "label": "Tau",
                "unit": "ns",
                "value": app.settings.value(SETTINGS_TAU_NS, "0"),
            },
            {"label": "Harmonics", "unit": "", "value": app.harmonic_selector_value},
        ]
        
        pdac_healthy = [obj["VALUE"] for obj in metadata_settings if obj["LABEL"] == "PDAC/Healthy"]
        
        def map_values(data):
            new_data = data.copy()
             
            for d in new_data:
                if isinstance(d["VALUE"], float) and d["VALUE"].is_integer():
                    value = int(d["VALUE"])
                else:
                    if d["INPUT_TYPE"] == "select":
                        value = d["OPTIONS"][d["VALUE"]]
                    elif d["LABEL"] == "Weeks":
                        v = d["VALUE"]
                        if isinstance(v, str):
                            v_stripped = v.strip()
                            if v_stripped == "":
                                value = None
                            else:
                                try:
                                    value = int(v_stripped)
                                except Exception:
                                    value = 0
                        else:
                            value = v
                    else:
                        value = d["VALUE"]
                parsed_data.append(
                    {
                        "label": d["LABEL"],
                        "unit": d["UNIT"] if d["UNIT"] is not None else "",
                        "value": value,
                    }
                )

        map_values(metadata_settings)
        map_values(custom_fields_settings)
        return parsed_data

    @staticmethod
    def get_laser_info_slug(window, filter_input):
        laser_type = window.laserblood_laser_type
        filter_type = filter_input["VALUE"]
        laser_key = next(
            (d["KEY"] for d in LASER_TYPES if d["LABEL"].strip() == laser_type.strip()),
            "",
        )
        filter_key = filter_type.strip().replace(" ", "").replace("/", "_")
        laser_key = laser_key.strip().replace(" ", "").replace("/", "_")
        return laser_key, filter_key

    @staticmethod
    def compare_file_timestamps(file_path1, file_path2):
        ctime1 = os.path.getctime(file_path1)
        ctime2 = os.path.getctime(file_path2)
        time_diff = abs(ctime1 - ctime2)
        return time_diff

    @staticmethod
    def clean_filename(filename):
        # Keep only letters, numbers and underscores
        filename = filename.replace(" ", "_")
        return re.sub(r"[^a-zA-Z0-9_]", "", filename)
