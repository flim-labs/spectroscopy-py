import os
import json
import struct
import matplotlib.pyplot as plt
import numpy as np

spectroscopy_file_path = "<FILE-PATH>"
laserblood_metadata_file_path = "<LASERBLOOD-METADATA-FILE-PATH>"


# Read laserblood experiment metadata
with open(laserblood_metadata_file_path, 'r', encoding='utf-8') as file:
    print("\n") 
    data = json.load(file)  
    for key, value in data.items():
        print(f"{key}: {value}")
    print("\n")    
        

with open(spectroscopy_file_path, 'rb') as f:
    # first 4 bytes must be SP01
    # 'SP01' is an identifier for spectroscopy bin files
    if f.read(4) != b"SP01":
        print("Invalid data file")
        exit(0)

    # read bin metadata from file
    (json_length,) = struct.unpack("I", f.read(4))
    null = None
    metadata = eval(f.read(json_length).decode("utf-8"))
    laser_period_ns = metadata["laser_period_ns"]
        
    channel_curves = [[] for _ in range(len(metadata["channels"]))]
    times = []
    number_of_channels = len(metadata["channels"])
    channel_values_unpack_string = 'I' * 256 
    
    while True:        
        data = f.read(8)
        if not data:
            break
        (time,) = struct.unpack('d', data)    
        for i in range(number_of_channels):
            data = f.read(4 * 256)  
            if len(data) < 4 * 256:
                break
            curve = struct.unpack(channel_values_unpack_string, data)    
            channel_curves[i].append(np.array(curve))
        times.append(time / 1_000_000_000)    

    # PLOTTING
    plt.xlabel(f"Time (ns, Laser period = {laser_period_ns} ns)")
    plt.ylabel("Intensity")
    plt.yscale('log')
    plt.title("Spectroscopy (time: " + str(round(times[-1])) + "s, curves stored: " + str(len(times)) + ")")

    num_bins = 256
    x_values = np.linspace(0, laser_period_ns, num_bins)
    
    # plot all channels summed up    
    total_max = 0
    total_min = 9999999999999
    for i in range(len(channel_curves)):
        sum_curve = np.sum(channel_curves[i], axis=0)
        max = np.max(sum_curve)
        min = np.min(sum_curve)
        if max > total_max:
            total_max = max
        if min < total_min:    
            total_min = min
        plt.plot(x_values, sum_curve, label=f"Channel {metadata['channels'][i] + 1}")  
        plt.legend()  
    plt.ylim(total_min * 0.99, total_max * 1.01) 
    plt.tight_layout()   
    plt.show()
