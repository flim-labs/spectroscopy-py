"""
read_data_plot.py
=================
Plotting and export-preparation methods of the ReadData class:
- plot_data
- plot_spectroscopy_data
- group_phasors_data_without_channels
- get_spectroscopy_data_to_fit
- plot_phasors_data
- save_plot_image
- prepare_spectroscopy_data_for_export_img
- prepare_phasors_data_for_export_img
"""

import os

import numpy as np
from utils.helpers import ns_to_mhz
from utils.messages_utilities import MessagesUtilities
from components.box_message import BoxMessage
from utils.gui_styles import GUIStyles
import settings.settings as s

from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtCore import QThreadPool


def plot_data(app):
    """Plots the loaded data based on the currently selected tab."""
    from components.reader.read_data_utils import get_data_type

    data_type = get_data_type(app.tab_selected)
    if data_type != "phasors":
        spectroscopy_data = (
            app.reader_data[data_type]["data"]
            if data_type == "spectroscopy"
            else app.reader_data[data_type]["data"]["spectroscopy_data"]
        )
        metadata = app.reader_data[data_type]["metadata"]
        laser_period_ns = (
            metadata["laser_period_ns"]
            if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None
            else 25
        )
        channels = metadata["channels"] if "channels" in metadata else []

        has_files_data = (
            "files_data" in spectroscopy_data
            and len(spectroscopy_data["files_data"]) > 0
        )
        has_traditional_data = (
            "times" in spectroscopy_data and "channels_curves" in spectroscopy_data
        )

        if (has_files_data or has_traditional_data) and not (metadata == {}):
            plot_spectroscopy_data(
                app,
                spectroscopy_data.get("times"),
                spectroscopy_data.get("channels_curves"),
                laser_period_ns,
                channels,
            )

            # SPECTROSCOPY READ: set plot titles from binary metadata
            if (
                app.tab_selected == s.TAB_SPECTROSCOPY
                and app.acquire_read_mode == "read"
            ):
                from utils.channel_name_utils import get_channel_name

                binary_metadata = app.reader_data.get("spectroscopy", {}).get(
                    "metadata", {}
                )
                names_for_read = (
                    binary_metadata.get("channels_name", {})
                    if isinstance(binary_metadata, dict)
                    else {}
                )
                for ch in app.decay_widgets:
                    title = get_channel_name(ch, names_for_read)
                    app.decay_widgets[ch].setTitle(title)

    phasors_metadata = app.reader_data["phasors"]["phasors_metadata"]
    if data_type == "phasors" and len(phasors_metadata) > 0:
        laser_period_ns = phasors_metadata[0]["laser_period_ns"]

        spectroscopy_metadata = app.reader_data["phasors"]["spectroscopy_metadata"]
        all_metadata = spectroscopy_metadata + phasors_metadata
        harmonics_values = []
        for meta in all_metadata:
            h = meta.get("harmonics")
            if isinstance(h, int):
                harmonics_values.append(h)
            elif isinstance(h, list) and h:
                harmonics_values.append(max(h))
        max_harmonic = max(harmonics_values)

        spectroscopy_data = app.reader_data["phasors"]["data"]["spectroscopy_data"]
        if (
            "files_data" in spectroscopy_data
            and len(spectroscopy_data["files_data"]) > 0
        ):
            channels = (
                spectroscopy_metadata[0]["channels"]
                if len(spectroscopy_metadata) > 0
                else []
            )
            plot_spectroscopy_data(app, None, None, laser_period_ns, channels)

        phasors_data = app.reader_data["phasors"]["data"]["phasors_data"]
        grouped_data = group_phasors_data_without_channels(phasors_data)
        plot_phasors_data(app, grouped_data, max_harmonic, laser_period_ns)


def plot_spectroscopy_data(
    app, times, channels_curves, laser_period_ns, metadata_channels
):
    """Plots spectroscopy decay curves on the appropriate widgets.

    Args:
        app: The main application instance.
        times (list): Timestamps (unused in multi-file mode).
        channels_curves (dict): Decay curve data per channel (unused in multi-file mode).
        laser_period_ns (float): The laser period in nanoseconds.
        metadata_channels (list): Active channel indices from metadata.
    """
    import pyqtgraph as pg
    from core.plots_controller import PlotsController
    from core.phasors_controller import PhasorsController

    data_type = "phasors" if app.tab_selected == s.TAB_PHASORS else "fitting"
    spectroscopy_data = (
        app.reader_data[data_type]["data"]["spectroscopy_data"]
        if data_type == "fitting"
        else app.reader_data["phasors"]["data"]["spectroscopy_data"]
    )
    is_multi_file = (
        "files_data" in spectroscopy_data
        and len(spectroscopy_data.get("files_data", [])) > 0
    )

    if (
        app.tab_selected == s.TAB_FITTING
        and app.acquire_read_mode == "read"
        and is_multi_file
    ):
        metadata_list = app.reader_data[data_type]["spectroscopy_metadata"]
        if metadata_list and "channels" in metadata_list[0]:
            app.plots_to_show = [metadata_list[0]["channels"][0]]
    elif app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
        if len(metadata_channels) > 0:
            app.plots_to_show = [metadata_channels[0]]

    if is_multi_file and app.tab_selected in [s.TAB_PHASORS, s.TAB_FITTING]:
        files_data = spectroscopy_data["files_data"]
        num_bins = 256
        frequency_mhz = ns_to_mhz(laser_period_ns)
        period_ns = 1_000 / frequency_mhz if frequency_mhz != 0.0 else laser_period_ns
        if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
            x_values = np.arange(num_bins)
        else:
            x_values = (
                np.linspace(0, period_ns, num_bins)
                if app.tab_selected == s.TAB_PHASORS
                else np.linspace(0, period_ns, num_bins) / 1_000
            )

        metadata_list = (
            app.reader_data[data_type]["spectroscopy_metadata"]
            if data_type == "fitting"
            else app.reader_data["phasors"]["spectroscopy_metadata"]
        )

        if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
            if not hasattr(app, "multi_file_plots"):
                app.multi_file_plots = {}
            if app.tab_selected not in app.multi_file_plots:
                app.multi_file_plots[app.tab_selected] = {}

        for ch in app.plots_to_show:
            if ch in app.decay_widgets:
                widget = app.decay_widgets[ch]
                widget.clear()
                if (
                    app.tab_selected == s.TAB_FITTING
                    and app.acquire_read_mode == "read"
                ):
                    if (
                        hasattr(app, "multi_file_plots")
                        and app.tab_selected in app.multi_file_plots
                    ):
                        app.multi_file_plots[app.tab_selected][ch] = []
                if widget.plotItem.legend is None:
                    legend = widget.addLegend(offset=(10, 10))
                    legend.setLabelTextColor("w")

        all_y_values_by_channel = {}
        ticks_by_channel = {}

        from components.lin_log_control import LinLogControl

        current_lin_log_modes = {}
        if app.tab_selected == s.TAB_FITTING:
            for ch in app.plots_to_show:
                current_lin_log_modes[ch] = app.lin_log_mode.get(ch, "LIN")

        for file_idx, file_data in enumerate(files_data):
            file_channels_curves = file_data["channels_curves"]
            color = PhasorsController.get_color_for_file_index(file_idx)

            file_name = "Unknown"
            if file_idx < len(metadata_list):
                file_name = metadata_list[file_idx].get(
                    "file_name",
                    os.path.basename(
                        file_data.get("file_path", f"File {file_idx + 1}")
                    ),
                )
            elif "file_path" in file_data:
                file_name = os.path.basename(file_data["file_path"])
            else:
                file_name = f"File {file_idx + 1}"

            for channel, curves in file_channels_curves.items():
                if (
                    app.tab_selected == s.TAB_FITTING
                    and app.acquire_read_mode == "read"
                ):
                    file_metadata = (
                        metadata_list[file_idx]
                        if file_idx < len(metadata_list)
                        else None
                    )
                    if file_metadata and "channels" in file_metadata:
                        if channel == 0:
                            logical_channel = app.plots_to_show[0]
                        else:
                            continue
                    else:
                        if channel == 0:
                            logical_channel = app.plots_to_show[0]
                        else:
                            continue
                else:
                    logical_channel = channel

                if logical_channel in app.plots_to_show:
                    y_values = np.sum(curves, axis=0)
                    ch_idx = logical_channel
                    if ch_idx not in all_y_values_by_channel:
                        all_y_values_by_channel[ch_idx] = []
                    all_y_values_by_channel[ch_idx].append(y_values)

                    time_shift = (
                        0 if ch_idx not in app.time_shifts else app.time_shifts[ch_idx]
                    )
                    y_shifted = np.roll(y_values, time_shift)
                    y_to_plot = y_shifted

                    if ch_idx in current_lin_log_modes:
                        if current_lin_log_modes[ch_idx] == "LOG":
                            ticks, y_to_plot, _ = LinLogControl.calculate_log_mode(
                                y_shifted
                            )
                            ticks_by_channel[ch_idx] = ticks
                            if ch_idx in app.decay_widgets:
                                app.decay_widgets[ch_idx].showGrid(
                                    x=False, y=True, alpha=0.3
                                )
                        else:
                            ticks, y_to_plot = LinLogControl.calculate_lin_mode(
                                y_shifted
                            )
                            ticks_by_channel[ch_idx] = ticks
                            if ch_idx in app.decay_widgets:
                                app.decay_widgets[ch_idx].showGrid(x=False, y=False)

                    if ch_idx in app.decay_widgets:
                        pen = pg.mkPen(color=color, width=2)
                        plot_item = app.decay_widgets[ch_idx].plot(
                            x_values, y_to_plot, pen=pen, name=file_name
                        )
                        if (
                            app.tab_selected == s.TAB_FITTING
                            and app.acquire_read_mode == "read"
                        ):
                            if (
                                hasattr(app, "multi_file_plots")
                                and app.tab_selected in app.multi_file_plots
                            ):
                                app.multi_file_plots[app.tab_selected][ch_idx].append(
                                    {
                                        "plot_item": plot_item,
                                        "y_values": y_values,
                                        "file_idx": file_idx,
                                        "file_name": file_name,
                                    }
                                )

        for ch_idx, ticks in ticks_by_channel.items():
            if ch_idx in app.decay_widgets:
                app.decay_widgets[ch_idx].getAxis("left").setTicks([ticks])
                PlotsController.set_plot_y_range(app.decay_widgets[ch_idx])

        if app.tab_selected != s.TAB_PHASORS:
            for ch_idx, y_values_list in all_y_values_by_channel.items():
                if len(y_values_list) > 0:
                    summed_y = np.sum(y_values_list, axis=0)
                    app.cached_decay_values[app.tab_selected][ch_idx] = summed_y
    else:
        # Single-file mode
        num_bins = 256
        frequency_mhz = ns_to_mhz(laser_period_ns)
        period_ns = 1_000 / frequency_mhz if frequency_mhz != 0.0 else laser_period_ns
        x_values = (
            np.linspace(0, period_ns, num_bins)
            if app.tab_selected == s.TAB_PHASORS
            else np.linspace(0, period_ns, num_bins) / 1_000
        )

        if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
            all_y_values = []
            first_channel = None
            for channel, curves in channels_curves.items():
                if (
                    channel < len(metadata_channels)
                    and metadata_channels[channel] in app.plots_to_show
                ):
                    y_values = np.sum(curves, axis=0)
                    all_y_values.append(y_values)
                    if first_channel is None:
                        first_channel = metadata_channels[channel]
                    app.cached_decay_values[app.tab_selected][
                        metadata_channels[channel]
                    ] = y_values

            if len(all_y_values) > 0 and first_channel is not None:
                y_avg = np.mean(all_y_values, axis=0)
                PlotsController.update_plots(
                    app, first_channel, x_values, y_avg, reader_mode=True
                )
                for channel, curves in channels_curves.items():
                    if channel < len(metadata_channels):
                        ch = metadata_channels[channel]
                        if ch != first_channel and ch in app.plots_to_show:
                            if ch in app.decay_widgets:
                                parent_widget = app.decay_widgets[ch].parent()
                                if parent_widget is not None:
                                    parent_widget.hide()
                                else:
                                    app.decay_widgets[ch].hide()
        else:
            for channel, curves in channels_curves.items():
                if (
                    channel < len(metadata_channels)
                    and metadata_channels[channel] in app.plots_to_show
                ):
                    y_values = np.sum(curves, axis=0)
                    if app.tab_selected != s.TAB_PHASORS:
                        app.cached_decay_values[app.tab_selected][
                            metadata_channels[channel]
                        ] = y_values
                    PlotsController.update_plots(
                        app,
                        metadata_channels[channel],
                        x_values,
                        y_values,
                        reader_mode=True,
                    )


def group_phasors_data_without_channels(data):
    """Return {harmonic: [(g, s, file_name), ...]} without channel separation."""
    grouped_data = {}
    for channel_data in data.values():
        if not isinstance(channel_data, dict):
            continue
        for harmonic, points in channel_data.items():
            harmonic_bucket = grouped_data.setdefault(harmonic, [])
            for point in points:
                g, s = point[0], point[1]
                file_name = point[2] if len(point) >= 3 else ""
                if file_name is None:
                    file_name = ""
                harmonic_bucket.append((g, s, str(file_name)))
    return grouped_data


def get_spectroscopy_data_to_fit(app):
    """
    Prepare spectroscopy data for fitting operations.

    Args:
        app: Main application instance.

    Returns:
        list: List of dicts with x, y, title, channel_index, time_shift,
              and optionally file_index and file_name for multi-file support.
    """
    from utils.channel_name_utils import get_channel_name

    spectroscopy_data = app.reader_data["fitting"]["data"]["spectroscopy_data"]
    metadata = app.reader_data["fitting"]["metadata"]

    laser_period_ns = (
        metadata["laser_period_ns"]
        if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None
        else 25
    )
    data = []
    num_bins = 256

    if "files_data" in spectroscopy_data and len(spectroscopy_data["files_data"]) > 0:
        files_data = spectroscopy_data["files_data"]
        spectroscopy_metadata = app.reader_data["fitting"]["spectroscopy_metadata"]

        for file_idx, file_data in enumerate(files_data):
            file_channels_curves = file_data["channels_curves"]
            file_metadata = (
                spectroscopy_metadata[file_idx]
                if file_idx < len(spectroscopy_metadata)
                else metadata
            )
            file_name = file_metadata.get("file_name", f"File {file_idx + 1}")
            channels = file_metadata["channels"]
            file_times = file_data["times"]

            for channel, curves in file_channels_curves.items():
                if channel == 0:
                    y_values = np.sum(curves, axis=0)
                    if len(file_times) >= len(y_values):
                        x_values = np.array(file_times[: len(y_values)])
                    else:
                        x_values = np.linspace(0, laser_period_ns, len(y_values))

                    display_channel = app.plots_to_show[0] if app.plots_to_show else 0
                    channel_id = channels[channel]
                    channel_time_shift = (
                        0
                        if display_channel not in app.time_shifts
                        else app.time_shifts[display_channel]
                    )
                    data.append(
                        {
                            "x": x_values,
                            "y": y_values,
                            "title": get_channel_name(channel_id, app.channel_names),
                            "channel_index": display_channel,
                            "time_shift": channel_time_shift,
                            "file_index": file_idx,
                            "file_name": file_name,
                        }
                    )
    else:
        if "times" in spectroscopy_data and spectroscopy_data["times"]:
            x_values = np.array(spectroscopy_data["times"])
        else:
            x_values = np.linspace(0, laser_period_ns, num_bins)

        channels_curves = spectroscopy_data.get("channels_curves", {})
        channels = metadata["channels"]
        display_channel = app.plots_to_show[0] if app.plots_to_show else 0

        for channel, curves in channels_curves.items():
            if channels[channel] in app.plots_to_show:
                y_values = np.sum(curves, axis=0)
                if app.tab_selected != s.TAB_PHASORS:
                    app.cached_decay_values[app.tab_selected][
                        channels[channel]
                    ] = y_values
                channel_time_shift = (
                    0
                    if channels[channel] not in app.time_shifts
                    else app.time_shifts[channels[channel]]
                )
                data.append(
                    {
                        "x": x_values,
                        "y": y_values,
                        "title": get_channel_name(channels[channel], app.channel_names),
                        "channel_index": channels[channel],
                        "time_shift": channel_time_shift,
                    }
                )
    return data


def plot_phasors_data(app, data, harmonics, laser_period_ns):
    """
    Plot phasors data with harmonic analysis.

    Args:
        app: The main application instance.
        data (dict): Phasor data grouped by harmonic {harmonic: [(g, s, file_name), ...]}.
        harmonics (int): Maximum harmonic value.
        laser_period_ns (float): Laser period in nanoseconds.
    """
    from core.controls_controller import ControlsController
    from core.phasors_controller import PhasorsController

    frequency_mhz = ns_to_mhz(laser_period_ns)

    PhasorsController.clear_phasors_file_scatters(app)
    PhasorsController.clear_phasors_files_legend(app)
    PhasorsController.hide_phasors_legends(app)

    app.all_phasors_points = PhasorsController.get_empty_phasors_points()

    for harmonic, values in data.items():
        app.all_phasors_points[0][harmonic].extend(values)

    if harmonics > 1:
        app.harmonic_selector_shown = True
        ControlsController.show_harmonic_selector(app, harmonics)

    if app.control_inputs[s.HARMONIC_SELECTOR].currentIndex() == 0:
        ControlsController._update_phasor_plots_for_harmonic(app)
    else:
        app.control_inputs[s.HARMONIC_SELECTOR].setCurrentIndex(0)
    app.loaded_phasors_harmonics = harmonics

    PhasorsController.generate_phasors_cluster_center(
        app, app.phasors_harmonic_selected
    )

    for i, channel_index in enumerate(app.plots_to_show):
        PhasorsController.draw_lifetime_points_in_phasors(
            app,
            channel_index,
            app.phasors_harmonic_selected,
            laser_period_ns,
            frequency_mhz,
        )


def save_plot_image(plot):
    """Saves a matplotlib plot to an image file (PNG and EPS) using a background thread.

    Args:
        plot (matplotlib.figure.Figure): The plot figure to save.
    """
    from components.reader.reader_workers import WorkerSignals, SavePlotTask
    from components.box_message import BoxMessage
    from utils.gui_styles import GUIStyles

    dialog = QFileDialog()
    base_path, _ = dialog.getSaveFileName(
        None,
        "Save plot image",
        "",
        "PNG Files (*.png);;EPS Files (*.eps)",
        options=QFileDialog.Option.DontUseNativeDialog,
    )

    def show_success_message():
        info_title, info_msg = MessagesUtilities.info_handler("SavedPlotImage")
        BoxMessage.setup(
            info_title,
            info_msg,
            QMessageBox.Icon.Information,
            GUIStyles.set_msg_box_style(),
        )

    def show_error_message(error):
        BoxMessage.setup(
            "Error saving images",
            f"Error saving plot images: {error}",
            QMessageBox.Icon.Warning,
            GUIStyles.set_msg_box_style(),
        )

    if base_path:
        signals = WorkerSignals()
        signals.success.connect(show_success_message)
        signals.error.connect(show_error_message)
        task = SavePlotTask(plot, base_path, signals)
        QThreadPool.globalInstance().start(task)


def prepare_spectroscopy_data_for_export_img(app):
    """Prepares spectroscopy data for exporting as an image.

    Args:
        app: The main application instance.

    Returns:
        tuple: (channels_curves, times, metadata, channel_names).
    """
    metadata = app.reader_data["spectroscopy"]["metadata"]
    channels_curves = app.reader_data["spectroscopy"]["data"]["channels_curves"]
    times = app.reader_data["spectroscopy"]["data"]["times"]
    channel_names = (
        metadata.get("channels_name", {}) if isinstance(metadata, dict) else {}
    )
    return channels_curves, times, metadata, channel_names


def prepare_phasors_data_for_export_img(app):
    """Prepares phasors and related spectroscopy data for exporting as an image.

    Args:
        app: The main application instance.

    Returns:
        tuple: (phasors_data, laser_period, active_channels, spectroscopy_times,
                spectroscopy_curves, channel_names).
    """
    phasors_data = app.reader_data["phasors"]["data"]["phasors_data"]

    phasors_meta = app.reader_data["phasors"].get(
        "phasors_metadata"
    ) or app.reader_data["phasors"].get("metadata")
    if isinstance(phasors_meta, list):
        meta = phasors_meta[0] if len(phasors_meta) > 0 else {}
    elif isinstance(phasors_meta, dict):
        meta = phasors_meta
    else:
        meta = {}

    laser_period = meta.get("laser_period_ns", 0)
    active_channels = meta.get("channels", [])

    spectroscopy_section = app.reader_data["phasors"]["data"].get(
        "spectroscopy_data", {}
    )
    if isinstance(spectroscopy_section, dict) and "files_data" in spectroscopy_section:
        spectroscopy_curves = None
        spectroscopy_times = None
    else:
        spectroscopy_curves = (
            spectroscopy_section.get("channels_curves")
            if isinstance(spectroscopy_section, dict)
            else None
        )
        spectroscopy_times = (
            spectroscopy_section.get("times")
            if isinstance(spectroscopy_section, dict)
            else None
        )

    channel_names = meta.get("channels_name", {}) if isinstance(meta, dict) else {}

    return (
        phasors_data,
        laser_period,
        active_channels,
        spectroscopy_times,
        spectroscopy_curves,
        channel_names,
    )
