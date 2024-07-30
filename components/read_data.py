import json
import struct
import numpy as np
from components.box_message import BoxMessage
from components.gui_styles import GUIStyles
from settings import TAB_PHASORS, TAB_SPECTROSCOPY
from PyQt6.QtWidgets import QFileDialog, QMessageBox


class ReadData:

    @staticmethod
    def read_bin_data(app, tab_active):
        if tab_active == TAB_SPECTROSCOPY:
            result = ReadData.read_bin(app, b"SP01", "Spectroscopy", ReadData.read_spectroscopy_data)
            if result:
                times, channels_curves = result
                ReadData.plot_spectroscopy_data(app, times, channels_curves)
            else:
                print("Error reading bin data or no data returned.")
        elif tab_active == TAB_PHASORS:
            pass  

        
    @staticmethod
    def plot_spectroscopy_data(app, times, channels_curves):
        app.clear_plots()
        app.generate_plots()
        frequency_mhz = app.get_frequency_mhz()
        laser_period_ns = ReadData.mhz_to_ns(frequency_mhz)
        num_bins = 256
        x = np.linspace(0, laser_period_ns, num_bins)
        x_values = x / 1_000 
        for channel, curves in channels_curves.items():
            if channel in app.plots_to_show:
                y_values = np.sum(curves, axis=0)
                app.cached_decay_values[channel] = y_values
                app.update_plots2(channel, x_values, y_values, reader_mode=True)

    @staticmethod
    def read_bin(app, magic_bytes, file_type, read_data_cb):
        try:
            dialog = QFileDialog()
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setNameFilter("Bin files (*.bin)")
            file_name, _ = dialog.getOpenFileName(
                app,
                f"Load {file_type} file",
                "",
                "Bin files (*.bin)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if not file_name or not file_name.endswith(".bin"):
                BoxMessage.setup(
                    "Invalid extension",
                    "Invalid extension. File should be a .bin",
                    QMessageBox.Icon.Warning,
                    GUIStyles.set_msg_box_style(),
                )
                return None
            
            with open(file_name, 'rb') as f:
                if f.read(4) != magic_bytes:
                    BoxMessage.setup(
                        "Invalid file",
                        f"Invalid file. The file is not a valid {file_type} file.",
                        QMessageBox.Icon.Warning,
                        GUIStyles.set_msg_box_style(),
                    )
                    return None
                return read_data_cb(f)

        except Exception as e:
            BoxMessage.setup(
                "Error reading file",
                "Error reading .bin file",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return None

    @staticmethod
    def read_spectroscopy_data(file):
        try:
            (json_length,) = struct.unpack("I", file.read(4))
            json_data = file.read(json_length).decode("utf-8")
            metadata = json.loads(json_data)
            channel_curves = {channel: [] for channel in range(len(metadata["channels"]))}
            times = []
            number_of_channels = len(metadata["channels"])
            channel_values_unpack_string = 'I' * 256 
            while True:
                data = file.read(8)
                if not data:
                    break
                (time,) = struct.unpack('d', data)
                times.append(time / 1_000_000_000)
                
                for i in range(number_of_channels):
                    data = file.read(4 * 256)
                    if len(data) < 4 * 256:
                        return times, channel_curves
                    curve = struct.unpack(channel_values_unpack_string, data)
                    channel_curves[i].append(np.array(curve))
            
            return times, channel_curves
        except Exception as e:
            print(f"Error reading spectroscopy data: {e}")
            BoxMessage.setup(
                "Error reading file",
                "Error reading Spectroscopy file",
                QMessageBox.Icon.Warning,
                GUIStyles.set_msg_box_style(),
            )
            return None
        
    @staticmethod
    def mhz_to_ns(frequency_mhz):
        frequency_hz = frequency_mhz * 1e6
        period_s = 1 / frequency_hz
        period_ns = period_s * 1e9
        return period_ns               