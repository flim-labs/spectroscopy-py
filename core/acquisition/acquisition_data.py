"""
acquisition_data.py
=========================================================
Handles real-time data processing during acquisition:
- pull_from_queue
- update_acquisition_countdowns
- update_SBR
- update_cps
- acquired_spectroscopy_data_to_fit

"""

import numpy as np
import flim_labs

from utils.helpers import calc_SBR, humanize_number
from core.phasors_controller import PhasorsController
import settings.settings as s

from PyQt6.QtWidgets import QApplication


def pull_from_queue(app):
    """
    Pulls data from the FLIM-LABS output queue and processes it.

    Connected to a timer and runs continuously during acquisition.

    Args:
        app: The main application instance.
    """
    from core.plots_controller import PlotsController
    from core.ui_controller import UIController
    from core.acquisition.acquisition_lifecycle import stop_spectroscopy_experiment

    val = flim_labs.pull_from_queue()
    if len(val) > 0:
        for v in val:
            if v == ("end",):
                print("Got end of acquisition, stopping")
                UIController.style_start_button(app)
                app.acquisition_stopped = True
                stop_spectroscopy_experiment(app)
                break
            if app.mode == s.MODE_STOPPED:
                break
            if "sp_phasors" in v[0]:
                channel = v[1][0]
                harmonic = v[2][0]
                phasors = v[3]
                channel_index = next(
                    (item for item in app.plots_to_show if item == channel), None
                )
                if harmonic == 1:
                    if channel_index is not None:
                        PhasorsController.draw_points_in_phasors(
                            app, channel, harmonic, phasors
                        )
                if channel_index is not None:
                    app.all_phasors_points[channel_index][harmonic].extend(phasors)
                continue
            try:
                ((channel,), (time_ns,), intensities) = v
            except Exception:
                print(v)
            ((channel,), (time_ns,), intensities) = v
            channel_index = next(
                (item for item in app.plots_to_show if item == channel), None
            )
            if channel_index is not None:
                PlotsController.update_plots(app, channel_index, time_ns, intensities)
                update_acquisition_countdowns(app, time_ns)
                update_cps(app, channel_index, time_ns, intensities)
            QApplication.processEvents()


def update_acquisition_countdowns(app, time_ns):
    """
    Updates the acquisition countdown timer widgets.

    Args:
        app: The main application instance.
        time_ns (int): The elapsed time of the acquisition in nanoseconds.
    """
    free_running = app.settings.value(s.SETTINGS_FREE_RUNNING, s.DEFAULT_FREE_RUNNING)
    acquisition_time = app.control_inputs[s.SETTINGS_ACQUISITION_TIME].value()
    if free_running is True or free_running == "true":
        return
    elapsed_time_sec = time_ns / 1_000_000_000
    remaining_time_sec = max(0, acquisition_time - elapsed_time_sec)
    seconds = int(remaining_time_sec)
    milliseconds = int((remaining_time_sec - seconds) * 1000) // 10
    for _, countdown_widget in app.acquisition_time_countdown_widgets.items():
        if countdown_widget:
            if not countdown_widget.isVisible():
                countdown_widget.setVisible(True)
            countdown_widget.setText(
                f"Remaining time: {seconds:02}:{milliseconds:02} (s)"
            )


def update_SBR(app, channel_index, curve):
    """
    Calculates and updates the Signal-to-Background Ratio (SBR) for a channel.

    Args:
        app: The main application instance.
        channel_index (int): The index of the channel to update.
        curve (np.ndarray): The decay curve data used for calculation.
    """
    if channel_index in app.SBR_items:
        SBR_value = calc_SBR(np.array(curve))
        app.SBR_items[channel_index].setText(f"SBR: {SBR_value:.2f} ㏈")


def update_cps(app, channel_index, time_ns, curve):
    """
    Updates the Counts Per Second (CPS) display for a given channel.

    Args:
        app: The main application instance.
        channel_index (int): The index of the channel to update.
        time_ns (int): The timestamp of the current data chunk in nanoseconds.
        curve (np.ndarray): The intensity data for the current chunk.
    """
    if channel_index not in app.cps_counts:
        return
    cps = app.cps_counts[channel_index]
    curve_sum = np.sum(curve)
    SBR_count = calc_SBR(np.array(curve))
    app.all_SBR_counts.append(SBR_count)
    if cps["last_time_ns"] == 0:
        cps["last_time_ns"] = time_ns
        cps["last_count"] = curve_sum
        cps["current_count"] = curve_sum
        return
    cps["current_count"] += np.sum(curve)
    time_elapsed = time_ns - cps["last_time_ns"]
    if time_elapsed > 330_000_000:
        cps_value = (cps["current_count"] - cps["last_count"]) / (
            time_elapsed / 1_000_000_000
        )
        app.all_cps_counts.append(cps_value)
        humanized_number = humanize_number(cps_value)
        app.cps_widgets[channel_index].setText(f"{humanized_number} CPS")
        cps_threshold = app.control_inputs[s.SETTINGS_CPS_THRESHOLD].value()
        if cps_threshold > 0:
            if cps_value > cps_threshold:
                app.cps_widgets_animation[channel_index].start()
            else:
                app.cps_widgets_animation[channel_index].stop()
        if app.show_SBR:
            update_SBR(app, channel_index, curve)
        cps["last_time_ns"] = time_ns
        cps["last_count"] = cps["current_count"]


def acquired_spectroscopy_data_to_fit(app, read):
    """
    Prepares and formats the acquired spectroscopy data for the fitting process.

    Uses a plain "Channel N" title string (Laserblood edition).
    Standard edition uses get_channel_name() from app.channel_names instead.

    Args:
        app: The main application instance.
        read (bool): True if data comes from a loaded file (scales x by 1000),
                     False for live acquisition.

    Returns:
        tuple[list[dict], float]: List of prepared data dicts and the last
                                  channel's time shift.
    """
    data = []
    time_shift = 0
    channels_shown = [
        channel for channel in app.plots_to_show if channel in app.selected_channels
    ]
    for channel, channel_index in enumerate(channels_shown):
        time_shift = (
            0
            if channel_index not in app.time_shifts
            else app.time_shifts[channel_index]
        )
        if (
            app.tab_selected not in app.decay_curves
            or channel_index not in app.decay_curves[app.tab_selected]
            or app.decay_curves[app.tab_selected][channel_index] is None
        ):
            continue
        if (
            app.tab_selected not in app.cached_decay_values
            or channel_index not in app.cached_decay_values[app.tab_selected]
        ):
            continue

        x, _ = app.decay_curves[app.tab_selected][channel_index].getData()
        y = app.cached_decay_values[app.tab_selected][channel_index]

        is_bin_indices = len(x) > 0 and np.max(x) <= 256
        x_data = x * 1000 if (read and not is_bin_indices) else x

        data.append(
            {
                "x": x_data,
                "y": y,
                "title": "Channel " + str(channel_index + 1),
                "channel_index": channel_index,
                "time_shift": time_shift,
            }
        )
    return data, time_shift