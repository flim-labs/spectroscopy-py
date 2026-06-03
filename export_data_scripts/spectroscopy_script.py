import json
import struct
import matplotlib.pyplot as plt
import numpy as np

file_path = "<FILE-PATH>"
laserblood_metadata_file_path = "<LASERBLOOD-METADATA-FILE-PATH>"


# Read laserblood experiment metadata
with open(laserblood_metadata_file_path, 'r', encoding='utf-8') as file:
    print("\n") 
    data = json.load(file)  
    for item in data:
        label = f"{item['label']} ({item['unit']})" if len(item['unit'].strip()) > 0 else f"{item['label']}"
        print(f"{label}: {item['value']}")
        

with open(file_path, 'rb') as f:
    # first 4 bytes must be SP01
    # 'SP01' is an identifier for spectroscopy bin files
    if f.read(4) != b"SP01":
        print("Invalid data file")
        exit(0)

    # read metadata from file
    (json_length,) = struct.unpack("I", f.read(4))
    null = None
    metadata = eval(f.read(json_length).decode("utf-8"))

    # BIN WIDTH (us)    
    if "bin_width_micros" in metadata and metadata["bin_width_micros"] is not None:
        print("Bin width: " + str(metadata["bin_width_micros"]) + "us")    
    # ACQUISITION TIME (duration of the acquisition)
    if "acquisition_time_millis" in metadata and metadata["acquisition_time_millis"] is not None:
        print("Acquisition time: " + str(metadata["acquisition_time_millis"] / 1000) + "s")
    # LASER PERIOD (ns)
    if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None:
        laser_period_ns = metadata["laser_period_ns"]
        print("Laser period: " + str(laser_period_ns) + "ns") 
    else:
        print("Laser period not found in metadata.")
        exit(0)
    # TAU (ns)
    if "tau_ns" in metadata and metadata["tau_ns"] is not None:
        print("Tau: " + str(metadata["tau_ns"]) + "ns")   
    
    # Extract channel names from binary metadata
    channel_names = metadata.get("channels_name", {})
    
    def get_channel_label(channel_index, channel_names_dict):
        """Get channel label with custom name if available.
        
        Args:
            channel_index: 0-based channel index from metadata['channels']
            channel_names_dict: dict with channel names (keys as strings, 0-based)
        """
        # The channel_names_dict uses string keys with 0-based indices
        custom_name = channel_names_dict.get(str(channel_index), None)
        
        # If not found with 0-based, try 1-based (for backward compatibility)
        if not custom_name:
            custom_name = channel_names_dict.get(str(channel_index + 1), None)
        
        if custom_name:
            return f"{custom_name} (Ch{channel_index + 1})"
        return f"Channel {channel_index + 1}"
        
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
        # Use custom channel name if available
        label = get_channel_label(metadata['channels'][i], channel_names)
        plt.plot(x_values, sum_curve, label=label)  
        plt.legend()  
    plt.ylim(total_min * 0.99, total_max * 1.01) 
    plt.xlim(0, laser_period_ns)
    plt.tight_layout()   
    plt.show()
