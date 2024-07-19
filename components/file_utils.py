import os
import json
from datetime import datetime
import shutil
from PyQt6.QtWidgets import QFileDialog
from laserblood_settings import LASER_TYPES
from settings import DEFAULT_BIN_WIDTH, SETTINGS_BIN_WIDTH, SETTINGS_TAU_NS


def directory_selector(window):
    folder_path = QFileDialog.getExistingDirectory(window, "Select Directory")
    return folder_path


def get_recent_spectroscopy_file():
    data_folder = os.path.join(os.environ["USERPROFILE"], ".flim-labs", "data")
    files = [
        f
        for f in os.listdir(data_folder)
        if f.startswith("spectroscopy") and not ("calibration" in f) and not ("phasors" in f)
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


def rename_bin_file(source_file, new_filename, window):
    filter_wavelength_input = next((input for input in window.laserblood_settings if input["LABEL"] == "Emission filter wavelength"), None)
    laser_key, filter_key = get_laser_info_slug(window, filter_wavelength_input)    
    _, file_extension = os.path.splitext(source_file)
    base_name = os.path.basename(source_file).replace(file_extension, "")
    dest_file_name = f"{new_filename}_{laser_key}_{filter_key}_{base_name}{file_extension}"
    return dest_file_name


def save_spectroscopy_file(new_filename, dest_path, window):
    source_file = get_recent_spectroscopy_file()
    if not source_file:
        return
    try:
        dest_file_name = rename_bin_file(source_file, new_filename, window)
        destination_file = os.path.join(dest_path, dest_file_name)
        shutil.copy2(source_file, destination_file)
        window.exported_data_file_paths["spectroscopy"] = destination_file
    except Exception as e:
        print("Error saving spectroscopy file")
        
        
def save_phasor_files(spectroscopy_new_filename, phasors_new_filename, dest_path, window):
    spectroscopy_ref_source_file = get_recent_spectroscopy_file()
    phasors_source_file = get_recent_phasors_file()
    if not spectroscopy_ref_source_file or not phasors_source_file:
        return
    try:
        dest_spectroscopy_file_name = rename_bin_file(spectroscopy_ref_source_file, spectroscopy_new_filename, window)
        destination_spectroscopy_file = os.path.join(dest_path, dest_spectroscopy_file_name)
        shutil.copy2(spectroscopy_ref_source_file, destination_spectroscopy_file)
        dest_phasors_file_name = rename_bin_file(phasors_source_file, phasors_new_filename, window)
        destination_phasors_file = os.path.join(dest_path, dest_phasors_file_name)
        shutil.copy2(phasors_source_file, destination_phasors_file)
        window.exported_data_file_paths["phasors"] = destination_phasors_file
        window.exported_data_file_paths["spectroscopy_phasors_ref"] = destination_spectroscopy_file    
    except Exception as e:
        print("Error saving phasors file")
        
        

def save_laserblood_metadata_json(filename, dest_path, window):
    filter_wavelength_input = next((input for input in window.laserblood_settings if input["LABEL"] == "Emission filter wavelength"), None)
    parsed_data = parse_metadata_output(window)
    laser_key, filter_key = get_laser_info_slug(window, filter_wavelength_input)    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    new_filename = f"{filename}_{laser_key}_{filter_key}_{timestamp}.laserblood_metadata.json"
    file_path = os.path.join(dest_path, new_filename)
    window.exported_data_file_paths["laserblood_metadata"] = file_path
    try:
        with open(file_path, 'w') as json_file:
            json.dump(parsed_data, json_file, indent=4)
    except Exception as e:
        print("Error saving laserblood metadata file")
        

def parse_metadata_output(app):    
    laser_type = app.laserblood_laser_type
    filter_type = app.laserblood_filter_type
    metadata_settings = app.laserblood_settings
    custom_fields_settings = app.laserblood_new_added_inputs
    filter_wavelength_input = next((input for input in app.laserblood_settings if input["LABEL"] == "Emission filter wavelength"), None)
    parsed_filter_type = f"{filter_type} {filter_wavelength_input["VALUE"]}" if filter_type in ["LP", "SP"] else f"{filter_wavelength_input["VALUE"]}"
    frequency_mhz = app.get_frequency_mhz()
    firmware_selected, connection_type = app.get_firmware_selected(frequency_mhz)
    parsed_data = [
        {"label": "Laser type", "unit": "", "value": laser_type},
        {"label": "Emission filter type", "unit": "", "value": parsed_filter_type},
        {"label": "Firmware selected", "unit": "", "value": firmware_selected},
        {"label": "Connection type", "unit": "", "value": connection_type},
        {"label": "Frequency", "unit": "Mhz", "value": laser_type},
        {"label": "Enabled channels", "unit": "", "value": [ch + 1 for ch in app.selected_channels]},
        {"label": "Acquisition time", "unit": "s", "value": round((app.cps_counts[app.selected_channels[0]]["last_time_ns"])/1_000_000_000, 2)},
        {"label": "Bin width", "unit": "µs", "value":  int( app.settings.value(SETTINGS_BIN_WIDTH, DEFAULT_BIN_WIDTH))},
        {"label": "Tau", "unit": "ns", "value": app.settings.value(SETTINGS_TAU_NS, '0')},
        {"label": "Harmonics", "unit": "", "value": app.harmonic_selector_value},   
    ]
    def map_values(data):
        new_data = data.copy()
        for d in new_data:
            if isinstance(d['VALUE'], float) and d['VALUE'].is_integer():
                value = int(d["VALUE"])
            else: 
                if d["INPUT_TYPE"] == "select":
                    value = d["OPTIONS"][d["VALUE"]] 
                else:
                    value = d["VALUE"]     
            parsed_data.append({
                "label": d["LABEL"],
                "unit": d["UNIT"] if d["UNIT"] is not None else "",
                "value": value
            })
    map_values(metadata_settings)  
    map_values(custom_fields_settings) 
    return parsed_data    

        
        
def get_laser_info_slug(window, filter_input):
        laser_type = window.laserblood_laser_type
        filter_type = filter_input["VALUE"]
        laser_key = next((d["KEY"] for d in LASER_TYPES if d["LABEL"].strip() == laser_type.strip()), "")
        filter_key = filter_type.strip().replace(" ", "").replace("/", "_") 
        laser_key = laser_key.strip().replace(" ", "").replace("/", "_")  
        return laser_key, filter_key      
            
            
            

    
    


    



