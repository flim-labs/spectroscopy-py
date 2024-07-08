import json
import struct
import matplotlib.pyplot as plt
import numpy as np


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


def plot_data(data):
    plt.figure()
    for channel, curve in data.items():
        plt.plot(curve, label='Channel ' + str(channel))
    plt.legend()
    plt.title('Decay curves')
    plt.xlabel('Bin')
    plt.ylabel('Counts')
    plt.grid(True)
    plt.show()


def main():
    # File paths
    data_file = 'spectroscopy_2024-07-08_17-13-11.bin'
    phasors_file = 'spectroscopy-phasors_2024-07-08_17-13-11.bin'

    # Extract metadata
    metadata = extract_metadata(data_file, b'SP01')
    selected_channels = metadata['channels']

    # Load and plot data
    data = load_data(data_file, selected_channels)
    plot_data(data)

    # Load and plot phasors
    phasors = load_phasors(phasors_file, selected_channels)
    plot_phasors(phasors)


if __name__ == '__main__':
    main()
