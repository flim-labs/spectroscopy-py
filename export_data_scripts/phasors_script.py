import os
import struct
import matplotlib.pyplot as plt
import numpy as np

# Get most recent spectroscopy bin file saved
def get_recent_spectroscopy_file():
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
        raise FileNotFoundError("No suitable spectroscopy file found.")
    return os.path.join(data_folder, files[0])

file_path = get_recent_spectroscopy_file()
print("Using data file: " + file_path)


with open(file_path, "rb") as f:
    # First 4 bytes must be SPF1
    if f.read(4) != b"SPF1":
        print("Invalid data file")
        exit(0)

    # Read metadata from file
    (json_length,) = struct.unpack("I", f.read(4))
    null = None
    metadata = eval(f.read(json_length).decode("utf-8"))
    print(metadata)

    # Enabled channels
    channels = metadata.get("channels", [])
    num_channels = len(channels)
    if num_channels == 0:
        print("No enabled channels found.")
        exit(0)
    
    print(
        "Enabled channels: "
        + ", ".join(["Channel " + str(ch + 1) for ch in channels])
    )

    # Bin width (us)
    bin_width_micros = metadata.get("bin_width_micros")
    if bin_width_micros is not None:
        print("Bin width: " + str(bin_width_micros) + "\u00B5s")
    
    # Acquisition time (duration of the acquisition)
    acquisition_time_millis = metadata.get("acquisition_time_millis")
    if acquisition_time_millis is not None:
        print("Acquisition time: " + str(acquisition_time_millis / 1000) + "s")
    
    # Laser period (ns)
    laser_period_ns = metadata.get("laser_period_ns")
    if laser_period_ns is not None:
        print("Laser period: " + str(laser_period_ns) + "ns")
    
    # Tau (ns)
    tau_ns = metadata.get("tau_ns")
    if tau_ns is not None:
        print("Tau: " + str(tau_ns) + "ns")

    