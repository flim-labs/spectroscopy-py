import json
import struct
import matplotlib.pyplot as plt
import numpy as np

from components.helpers import ns_to_mhz


def extract_metadata(file_path, magic_number):
    with open(file_path, 'rb') as f:
        assert f.read(4) == magic_number
        header_length = int.from_bytes(f.read(4), byteorder='little')
        header = f.read(header_length)
        metadata = json.loads(header)
    return metadata


def load_data(file_path, selected_channels):
    data = {}
    with open(file_path, 'rb') as f:
        assert f.read(4) == b'SP01'
        header_length = int.from_bytes(f.read(4), byteorder='little')
        header = f.read(header_length)
        metadata = json.loads(header)
        selected_channels = metadata['channels']
        while True:
            time_ns = f.read(8)
            if not time_ns:
                print('End of file data')
                break
            for channel in selected_channels:
                current_curve = [
                    int.from_bytes(f.read(4), byteorder='little') for _ in range(256)
                ]
                data[channel] = data.get(channel, [0 for _ in range(256)])
                data[channel] = [sum(x) for x in zip(data[channel], current_curve)]
    return data


def load_phasors(file_path, selected_channels):
    data = {}
    with open(file_path, 'rb') as f:
        assert f.read(4) == b'SPF1'
        header_length = int.from_bytes(f.read(4), byteorder='little')
        header = f.read(header_length)
        metadata = json.loads(header)
        while True:
            for channel in selected_channels:
                if channel not in data:
                    data[channel] = {}

                for harmonic in range(1, metadata['harmonics'] + 1):
                    if harmonic not in data[channel]:
                        data[channel][harmonic] = []

                    bytes_read = f.read(32)
                    if not bytes_read:
                        print('End of file phasors')
                        return data  # Exit the function if no more data

                    # Unpack the read bytes
                    try:
                        time_ns, channel_name, harmonic_name, g, s = struct.unpack('QIIdd', bytes_read)
                    except struct.error as e:
                        print(f"Error unpacking data: {e}")
                        return data

                    data[channel][harmonic].append((g, s))
    return data


def plot_phasors(data):
    fig, ax = plt.subplots()

    harmonic_colors = plt.cm.viridis(np.linspace(0, 1, max(h for ch in data.values() for h in ch.keys())))
    harmonic_colors_dict = {harmonic: color for harmonic, color in enumerate(harmonic_colors, 1)}

    for channel, harmonics in data.items():
        theta = np.linspace(0, np.pi, 100)
        x = np.cos(theta)
        y = np.sin(theta)

        # Plot semi-circle for the channel
        ax.plot(x, y, label=f'Channel: {channel}')

        for harmonic, values in harmonics.items():
            if values:  # Ensure there are values to plot
                g_values, s_values = zip(*values)

                # Filter out extreme values to prevent overflow
                g_values = np.array(g_values)
                s_values = np.array(s_values)
                mask = (np.abs(g_values) < 1e9) & (np.abs(s_values) < 1e9)
                g_values = g_values[mask]
                s_values = s_values[mask]

                ax.scatter(g_values, s_values, label=f'Channel: {channel} Harmonic: {harmonic}',
                           color=harmonic_colors_dict[harmonic])
    ax.set_aspect('equal')
    ax.legend()
    plt.title('Phasors Plot')
    plt.xlabel('G')
    plt.ylabel('S')
    plt.grid(True)
    plt.show()
    
    
    
def plot_phasors_data(phasors_data, laser_period, active_channels, spectroscopy_times, spectroscopy_curves, show_plot=True):
    # Colormaps
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
    # plot layout config
    num_channels = len(phasors_data)
    max_channels_per_row = 3
    num_rows = (num_channels + max_channels_per_row - 1) // max_channels_per_row
    fig, axs = plt.subplots(num_rows + 1, max_channels_per_row, figsize=(20, (num_rows + 1) * 6))               
    # Spectroscopy plot
    num_bins = 256
    x_values = np.linspace(0, laser_period, num_bins)
    ax = axs[0, 0]
    ax.set_title("Spectroscopy (time: " + str(round(spectroscopy_times[-1])) + "s, curves stored: " + str(len(spectroscopy_times)) + ")")
    ax.set_xlabel(f"Time (ns, Laser period = {laser_period} ns)")
    ax.set_ylabel("Intensity")
    ax.set_yscale("log")
    ax.grid(True)
    total_max = 0
    total_min = 9999999999999
    for i in range(len(active_channels)):
        sum_curve = np.sum(spectroscopy_curves[i], axis=0)
        max_val = np.max(sum_curve)
        min_val = np.min(sum_curve)
        if max_val > total_max:
            total_max = max_val
        if min_val < total_min:        
            total_min = min_val
        ax.plot(x_values, sum_curve, label=f"Channel {active_channels[i] + 1}")   
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
                freq_mhz = ns_to_mhz(laser_period)
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
    if show_plot:
        plt.show()
    return fig    


def plot_spectroscopy_data(channel_curves, times, metadata, show_plot=True):
   fig, ax = plt.subplots()
   ax.set_xlabel(f"Time (ns, Laser period = {metadata['laser_period_ns']} ns)")
   ax.set_ylabel("Intensity")
   ax.set_yscale('log')
   ax.set_title("Spectroscopy (time: " + str(round(times[-1])) + "s, curves stored: " + str(len(times)) + ")")
   num_bins = 256
   x_values = np.linspace(0, metadata["laser_period_ns"], num_bins)
   # plot all channels summed up 
   total_max = 0
   total_min = float('inf')
   for i in range(len(channel_curves)):
       sum_curve = np.sum(channel_curves[i], axis=0)
       max_value = np.max(sum_curve)
       min_value = np.min(sum_curve)
       if max_value > total_max:
           total_max = max_value
       if min_value < total_min: 
           total_min = min_value
       ax.plot(x_values, sum_curve, label=f"Channel {metadata['channels'][i] + 1}")   
       ax.legend()
   ax.set_ylim(total_min * 0.99, total_max * 1.01)  
   fig.tight_layout()  
   if show_plot:
       plt.show()
   return fig     

