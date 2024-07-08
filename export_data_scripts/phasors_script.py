import os
import struct
import matplotlib.pyplot as plt
import numpy as np


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

file_path = get_recent_phasors_file()
print("Using data file: " + file_path)


with open(file_path, 'rb') as f:
    # First 4 bytes must be SPF1
    if f.read(4) != b"SPF1":
        print("Invalid data file")
        exit(0)

    # Read metadata from file
    (json_length,) = struct.unpack("I", f.read(4))
    null = None
    metadata = eval(f.read(json_length).decode("utf-8"))

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
        print("Bin width: " + str(bin_width_micros) + "us")
    
    # Acquisition time (duration of the acquisition)
    acquisition_time_millis = metadata.get("acquisition_time_millis")
    if acquisition_time_millis is not None:
        print("Acquisition time: " + str(acquisition_time_millis / 1000) + "s")
    
    # Laser period (ns)
    laser_period_ns = metadata.get("laser_period_ns")
    if laser_period_ns is not None:
        print("Laser period: " + str(laser_period_ns) + "ns")
        
    # Harmonics
    harmonics = metadata.get("harmonics")
    if harmonics is not None:
        print("Harmonics: " + str(harmonics))    
    
    # Tau (ns)
    tau_ns = metadata.get("tau_ns")
    if tau_ns is not None:
        print("Tau: " + str(tau_ns) + "ns")

    data = {}
    try:
        while True:
            for channel in metadata["channels"]:
                if channel not in data:
                    data[channel] = {}
                for harmonic in range(1, metadata['harmonics'] + 1):    
                    if harmonic not in data[channel]:
                        data[channel][harmonic] = []
                    bytes_read = f.read(32)
                    if not bytes_read:
                        raise StopIteration 
                    try:
                        time_ns, channel_name, harmonic_name, g, s = struct.unpack('QIIdd', bytes_read)
                    except struct.error as e:    
                        print(f"Error unpacking data: {e}")
                        raise StopIteration  
                    data[channel][harmonic].append((g, s))
    except StopIteration:
        pass  

# PLOTTING
fig, ax = plt.subplots()
harmonic_colors = plt.cm.viridis(np.linspace(0, 1, max(h for ch in data.values() for h in ch.keys())))
harmonic_colors_dict = {harmonic: color for harmonic, color in enumerate(harmonic_colors, 1)}
for channel, harmonics in data.items():
    theta = np.linspace(0, np.pi, 100)
    x = np.cos(theta)
    y = np.sin(theta)
    ax.plot(x, y, label=f'Channel: {channel + 1}')
    for harmonic, values in harmonics.items():
        if values:
            g_values, s_values = zip(*values)
            g_values = np.array(g_values)
            s_values = np.array(s_values)
            mask = (np.abs(g_values) < 1e9) & (np.abs(s_values) < 1e9)
            g_values = g_values[mask]
            s_values = s_values[mask]
            ax.scatter(g_values, s_values, label=f'Channel: {channel + 1} Harmonic: {harmonic}',
                       color=harmonic_colors_dict[harmonic])

ax.set_aspect('equal')    
ax.legend()
plt.title('Phasors Plot')
plt.xlabel('G')
plt.ylabel('S')
plt.grid(True)
plt.show()            
            
    
