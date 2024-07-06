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
        if f.startswith("spectroscopy") and not ("calibration" in f)
    ]
    files.sort(
        key=lambda x: os.path.getmtime(os.path.join(data_folder, x)), reverse=True
    )
    return os.path.join(data_folder, files[0])


file_path = get_recent_spectroscopy_file()
print("Using data file: " + file_path)


with open(file_path, "rb") as f:
    # first 4 bytes must be SP01
    # 'SP01' is an identifier for spectroscopy bin files
    if f.read(4) != b"SP01":
        print("Invalid data file")
        exit(0)

    # read metadata from file
    (json_length,) = struct.unpack("I", f.read(4))
    null = None
    metadata = eval(f.read(json_length).decode("utf-8"))
    print(metadata)

    
    # ENABLED CHANNELS
    if "channels" in metadata and metadata["channels"] is not None:
        print(
            "Enabled channels: "
            + (
                ", ".join(
                    ["Channel " + str(ch + 1) for ch in metadata["channels"]]
                )
            )
        )   
    # BIN WIDTH (us)    
    if "bin_width_micros" in metadata and metadata["bin_width_micros"] is not None:
        print("Bin width: " + str(metadata["bin_width_micros"]) + "\u00B5s")    
    # ACQUISITION TIME (duration of the acquisition)
    if "acquisition_time_millis" in metadata and metadata["acquisition_time_millis"] is not None:
        print("Acquisition time: " + str(metadata["acquisition_time_millis"] / 1000) + "s")
    # LASER PERIOD (ns)
    if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None:
        print("Laser period: " + str(metadata["laser_period_ns"]) + "ns") 
    # TAU (ns)
    if "tau_ns" in metadata and metadata["tau_ns"] is not None:
        print("Tau: " + str(metadata["tau_ns"]) + "ns")   
        
              
    channel_lines = [[] for _ in range(len(metadata["channels"]))]
    number_of_channels = len(metadata["channels"])
    channel_values_unpack_string = 'I' * number_of_channels
    
    
    
    while True:
        data = f.read(4 * number_of_channels + 8)  
        if not data:
            break

        channel_values = struct.unpack(channel_values_unpack_string, data[:4 * number_of_channels])

    
        harmonic = struct.unpack('d', data[4 * number_of_channels:4 * number_of_channels + 8])
        print(harmonic)
                
            
     

    
            
            

    # PLOTTING    
    """
     This example script samples and plots all acquired photons counts. 
     To avoid graphical overload, given the very high number of points, 
     it is recommended to use reduced sampling for analysis.
    """
 
   
    num_plots = number_of_channels
    num_plots_per_row = 1
    if num_plots < 2:
        num_plots_per_row = 1
    if num_plots > 1 and num_plots < 4:
        num_plots_per_row = 2
    if num_plots >= 4:
        num_plots_per_row = 4

    num_rows = (num_plots + num_plots_per_row - 1) // num_plots_per_row
    fig, axs = plt.subplots(num_rows, num_plots_per_row, figsize=(12, 3*num_rows), constrained_layout=True)
    fig.suptitle("Phasors")

        
        