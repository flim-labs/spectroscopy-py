import os
import json
from datetime import datetime
import shutil
from PyQt6.QtWidgets import QFileDialog
from laserblood_settings import LASER_TYPES



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


def rename_bin_file(source_file, new_filename):
    _, file_extension = os.path.splitext(source_file)
    base_name = os.path.basename(source_file).replace(file_extension, "")
    dest_file_name = f"{new_filename}_{base_name}{file_extension}"
    return dest_file_name


def save_spectroscopy_file(new_filename, dest_path, window):
    source_file = get_recent_spectroscopy_file()
    if not source_file:
        return
    try:
        dest_file_name = rename_bin_file(source_file, new_filename)
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
        dest_spectroscopy_file_name = rename_bin_file(spectroscopy_ref_source_file, spectroscopy_new_filename)
        destination_spectroscopy_file = os.path.join(dest_path, dest_spectroscopy_file_name)
        shutil.copy2(spectroscopy_ref_source_file, destination_spectroscopy_file)
        dest_phasors_file_name = rename_bin_file(phasors_source_file, phasors_new_filename)
        destination_phasors_file = os.path.join(dest_path, dest_phasors_file_name)
        shutil.copy2(phasors_source_file, destination_phasors_file)
        window.exported_data_file_paths["phasors"] = destination_phasors_file
        window.exported_data_file_paths["spectroscopy_phasors_ref"] = destination_spectroscopy_file    
    except Exception as e:
        print("Error saving phasors file")
        
        

def save_laserblood_metadata_json(filename, dest_path, window):
    laser_type = window.laserblood_laser_type
    filter_type = window.laserblood_filter_type
    metadata_settings = window.laserblood_settings
    custom_fields_settings = window.laserblood_new_added_inputs
    parsed_data = {
        "Laser type": laser_type,
        "Filter type": filter_type,
    }
    def map_values(data):
        new_data = data.copy()
        label = f"{new_data['LABEL']} ({new_data['UNIT']})" if new_data['UNIT'] is not None else f"{new_data['LABEL']}"
        if isinstance(new_data['VALUE'], float) and new_data['VALUE'].is_integer():
            parsed_data[label] = int(new_data['VALUE'])
        else:
            parsed_data[label] = new_data['VALUE']
    for data in metadata_settings:
        map_values(data)
    for data in custom_fields_settings:
        map_values(data)
    laser_key = next((d["KEY"] for d in LASER_TYPES if d["LABEL"].strip() == laser_type.strip()), "")
    filter_key = filter_type.strip().replace(" ", "").replace("/", "_")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    new_filename = f"{filename}_{laser_key}_{filter_key}_{timestamp}.laserblood_metadata.json"
    file_path = os.path.join(dest_path, new_filename)
    try:
        with open(file_path, 'w') as json_file:
            json.dump(parsed_data, json_file, indent=4)
    except Exception as e:
        print("Error saving laserblood metadata file")


    
    


    



