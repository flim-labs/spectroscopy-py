import os
import struct
import matplotlib.pyplot as plt
import numpy as np


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


spectroscopy_file_path = get_recent_spectroscopy_file()
# spectroscopy_file_path = "INSERT DATA FILE PATH HERE" # You can also manually insert the path to the spectroscopy_data file here
phasors_file_path = get_recent_phasors_file()
# phasors_file_path = "INSERT DATA FILE PATH HERE" # You can also manually insert the path to the phasors_data file here
print("Using phasors_data file: " + phasors_file_path)


def ns_to_mhz(laser_period_ns):
    period_s = laser_period_ns * 1e-9
    frequency_hz = 1 / period_s
    frequency_mhz = frequency_hz / 1e6
    return frequency_mhz


# READ PHASORS FILE
phasors_data = {}
with open(phasors_file_path, "rb") as f:
    # First 4 bytes must be SPF1
    if f.read(4) != b"SPF1":
        print("Invalid phasors_data file")
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
        "Enabled channels: " + ", ".join(["Channel " + str(ch + 1) for ch in channels])
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
    try:
        while True:
            bytes_read = f.read(32)
            if not bytes_read:
                raise StopIteration
            try:
                time_ns, channel_name, harmonic_name, g, s = struct.unpack(
                    "QIIdd", bytes_read
                )
            except struct.error as e:
                print(f"Error unpacking phasors_data: {e}")
                raise StopIteration
            if channel_name not in phasors_data:                
                phasors_data[channel_name] = {}
            if harmonic_name not in phasors_data[channel_name]:                    
                phasors_data[channel_name][harmonic_name] = []        
            phasors_data[channel_name][harmonic_name].append((g, s))    
    except StopIteration:
        pass


# READ SPECTROSCOPY FILE
spectroscopy_channels_curves = []
spectroscopy_times = []

with open(spectroscopy_file_path, 'rb') as f:
    # first 4 bytes must be SP01
    # 'SP01' is an identifier for spectroscopy bin files
    if f.read(4) != b"SP01":
        print("Invalid data file")
        exit(0)
    # read metadata from file
    (json_length,) = struct.unpack("I", f.read(4))
    null = None
    metadata = eval(f.read(json_length).decode("utf-8"))      
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
    spectroscopy_times = times 
    spectroscopy_channels_curves = channel_curves     

# PLOTTING
harmonic_colors = plt.cm.viridis(
    np.linspace(0, 1, max(h for ch in phasors_data.values() for h in ch.keys()))
)
harmonic_means_colors = plt.cm.brg(
    np.linspace(0, 1, max(h for ch in phasors_data.values() for h in ch.keys()))
)
harmonic_colors_dict = {
    harmonic: color for harmonic, color in enumerate(harmonic_colors, 1)
}
harmonic_means_colors_dict = {
    harmonic: color for harmonic, color in enumerate(harmonic_means_colors, 1)
}

num_channels = len(phasors_data)
max_channels_per_row = 3
num_rows = (num_channels + max_channels_per_row - 1) // max_channels_per_row
fig, axs = plt.subplots(num_rows + 1, max_channels_per_row, figsize=(20, (num_rows + 1) * 6))

# Spectroscopy plot
ax = axs[0, 0]
ax.set_title("Spectroscopy (time: " + str(round(spectroscopy_times[-1])) + "s, curves stored: " + str(len(spectroscopy_times)) + ")")
ax.set_xlabel("Bin")
ax.set_ylabel("Intensity")
ax.set_yscale("log")
ax.grid(True)
total_max = 0
total_min = 9999999999999
for i in range(number_of_channels):
    sum_curve = np.sum(spectroscopy_channels_curves[i], axis=0)
    max_val = np.max(sum_curve)
    min_val = np.min(sum_curve)
    if max_val > total_max:
        total_max = max_val
    if min_val < total_min:        
        total_min = min_val
    ax.plot(sum_curve, label=f"Channel {metadata['channels'][i] + 1}")   
ax.set_ylim(total_min * 0.99, total_max * 1.01)        
ax.legend()

# Phasors plots
for i, (channel, harmonics) in enumerate(phasors_data.items(), start=1):
    row = i // max_channels_per_row
    col = i % max_channels_per_row
    ax = axs[row, col]
    x = np.linspace(0, 1, 1000)
    y = np.sqrt(0.5**2 - (x - 0.5) ** 2)
    ax.plot(x, y)
    
 
    for harmonic, values in harmonics.items():
        if values:
            g_values, s_values = zip(*values)
            g_values = np.array(g_values)
            s_values = np.array(s_values)
            mask = (np.abs(g_values) < 1e9) & (np.abs(s_values) < 1e9)
            g_values = g_values[mask]
            s_values = s_values[mask]
            ax.scatter(
                g_values,
                s_values,
                label=f"Harmonic: {harmonic}",
                zorder=2,
                color=harmonic_colors_dict[harmonic],
            )
            mean_g = np.mean(g_values)
            mean_s = np.mean(s_values)
            freq_mhz = ns_to_mhz(laser_period_ns)
            tau_phi = (1 / (2 * np.pi * freq_mhz * harmonic)) * (mean_s / mean_g) * 1e3
            tau_m_component = (1 / (mean_s**2 + mean_g**2)) - 1
            tau_m = (
                (
                    (1 / (2 * np.pi * freq_mhz * harmonic))
                    * np.sqrt(tau_m_component)
                    * 1e3
                )
                if tau_m_component >= 0
                else None
            )
            mean_label = f"G (mean): {round(mean_g, 2)}; S (mean): {round(mean_s, 2)}; τϕ={round(tau_phi, 2)} ns"
            if tau_m is not None:
                mean_label += f"; τm={round(tau_m, 2)} ns"
            ax.scatter(
                mean_g,
                mean_s,
                color=harmonic_means_colors_dict[harmonic],
                marker="x",
                s=100,
                zorder=3,
                label=mean_label,
            )

    ax.legend(fontsize="small")
    ax.set_title(f"Phasor - Channel {channel + 1}")
    ax.set_xlabel("G")
    ax.set_ylabel("S")
    ax.grid(True)

for i in range(num_channels + 1, (num_rows + 1) * max_channels_per_row):
    row = i // max_channels_per_row
    col = i % max_channels_per_row
    fig.delaxes(axs[row, col])

plt.tight_layout(pad=4.0, w_pad=4.0, h_pad=4.0)
plt.show()