import os
import struct

import matplotlib.pyplot as plt
import numpy as np


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


def plot_last_file_phasor_calc():

    #file_path = get_last_spectroscopy_file()
    file_path_ref = get_recent_spectroscopy_file()

    with open(file_path_ref, 'rb') as f:
        if f.read(4) != b'SP01':
            print("Invalid data file")
            exit(0)

        (json_length,) = struct.unpack('I', f.read(4))
        null = None
        metadata = eval(f.read(json_length).decode("utf-8"))

        if "channels" in metadata and metadata["channels"]:
            print("Enabled channels: " + (", ".join(["Channel " + str(ch + 1) for ch in metadata["channels"]])))

        if "bin_width_micros" in metadata and metadata["bin_width_micros"] is not None:
            print("Bin width: " + str(metadata["bin_width_micros"]) + "\u00B5s")

        if "acquisition_time_millis" in metadata and metadata["acquisition_time_millis"] is not None:
            print("Acquisition time: " + str(metadata["acquisition_time_millis"] / 1000) + "s")

        if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None:
            print("Laser period: " + str(metadata["laser_period_ns"]) + "ns")

        # create array of len(channel) arrays
        curves = [[] for _ in range(len(metadata["channels"]))]
        times = []

        number_of_channels = len(metadata["channels"])
        channel_values_unpack_string = 'I' * number_of_channels * 256
        bin_width_seconds = metadata["bin_width_micros"] / 1000000

        while True:
            data = f.read(8)
            if not data:
                break
            (time,) = struct.unpack('d', data)
            for i in range(len(curves)):
                data = f.read(4 * 256)
                curve = struct.unpack(channel_values_unpack_string, data)
                curves[i].append(np.array(curve))
            times.append(time / 1_000_000_000)

        plt.xlabel("Bin")
        plt.ylabel("Intensity")
        plt.yscale('log')
        plt.title("Spectroscopy (time: " + str(round(times[-1])) + "s, curves stored: " + str(len(times)) + ")")

        # plot all channels summed up
        total_max = 0
        total_min = 9999999999999
        for i in range(len(curves)):
            sum_curve = np.sum(curves[i], axis=0)
            max = np.max(sum_curve)
            min = np.min(sum_curve)
            if max > total_max:
                total_max = max
            if min < total_min:
                total_min = min
            plt.plot(sum_curve, label=f"Channel {i + 1}")

        plt.ylim(min * 0.99, max * 1.01)

        plt.show()


if __name__ == "__main__":
    plot_last_file_phasor_calc()
