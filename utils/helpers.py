from math import floor, log
import re
import numpy as np
from datetime import datetime

from settings.settings import AVAILABLE_FREQUENCIES_MHZ, HETERODYNE_FACTOR


def format_size(size_in_bytes):
    """Converts a size in bytes to a human-readable string (B, KB, MB, etc.).

    Args:
        size_in_bytes (int): The size in bytes.

    Returns:
        str: A formatted string representing the size.
    """
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0

    while size_in_bytes >= 1024 and unit_index < len(units) - 1:
        size_in_bytes /= 1024.0
        unit_index += 1

    return f"{size_in_bytes:.2f}{units[unit_index]}"


def ns_to_mhz(laser_period_ns):
    """Converts a laser period from nanoseconds to frequency in megahertz.

    Args:
        laser_period_ns (float): The laser period in nanoseconds.

    Returns:
        float: The corresponding frequency in megahertz.
    """
    period_s = laser_period_ns * 1e-9
    frequency_hz = 1 / period_s
    frequency_mhz = frequency_hz / 1e6
    return frequency_mhz


def mhz_to_ns(frequency_mhz):
    """Converts a frequency from megahertz to a laser period in nanoseconds.

    Args:
        frequency_mhz (float): The frequency in megahertz.

    Returns:
        float: The corresponding laser period in nanoseconds.
    """
    frequency_hz = frequency_mhz * 1e6
    period_s = 1 / frequency_hz
    period_ns = period_s * 1e9
    return period_ns


def convert_ndarray_to_list(data):
    """Converts a NumPy ndarray to a Python list if it's an ndarray.

    Args:
        data: The input data, which may be a NumPy ndarray.

    Returns:
        list or original type: The converted list, or the original data if not an ndarray.
    """
    if isinstance(data, np.ndarray):
        return data.tolist()
    return data


def convert_np_num_to_py_num(data):
    """Converts a NumPy number (int64, float64) to a standard Python number.

    Args:
        data: The input data, which may be a NumPy number.

    Returns:
        int, float, or original type: The converted Python number, or the original data.
    """
    if isinstance(data, (np.int64, np.float64)):
        return data.item()
    return data


def convert_py_num_to_np_num(output_data):
    """Converts a Python number (int, float) to a NumPy number type.

    Args:
        output_data: The input data, which may be a Python number.

    Returns:
        np.int64, np.float64, or original type: The converted NumPy number, or the original data.
    """
    if isinstance(output_data, (int, float)):
        return (
            np.float64(output_data)
            if isinstance(output_data, float)
            else np.int64(output_data)
        )
    return output_data


def calc_micro_time_ns(bin, frequency_mhz):
    """Calculates the micro-time in nanoseconds from a bin number and frequency.

    Args:
        bin (int): The bin number (0-255).
        frequency_mhz (float): The laser frequency in MHz.

    Returns:
        float: The calculated micro-time in nanoseconds.
    """
    laser_period_ns = 0.0 if frequency_mhz == 0.0 else mhz_to_ns(frequency_mhz)
    return ((bin * laser_period_ns) / 256) * HETERODYNE_FACTOR


def calc_bin_from_micro_time_ns(micro_time_ns, frequency_mhz):
    """Calculates the bin number from a micro-time in nanoseconds and frequency.

    Args:
        micro_time_ns (float): The micro-time in nanoseconds.
        frequency_mhz (float): The laser frequency in MHz.

    Returns:
        int: The calculated bin number.
    """
    laser_period_ns = 0.0 if frequency_mhz == 0.0 else mhz_to_ns(frequency_mhz)
    if laser_period_ns == 0.0:
        return 0
    return (micro_time_ns * 256) / (HETERODYNE_FACTOR * laser_period_ns)


def calc_SBR(y):
    """Calculates the Signal-to-Background Ratio (SBR) in decibels.

    Args:
        y (np.ndarray): The array of signal data.

    Returns:
        float: The SBR value in dB.
    """
    signal_peak = np.max(y) + 1
    noise = np.min(y) + 1
    return 10 * np.log10(signal_peak / noise)


def calc_timestamp():
    """Gets the current Unix timestamp as an integer.

    Returns:
        int: The current timestamp.
    """
    return int(datetime.now().timestamp())


def get_realtime_adjustment_value(enabled_channels, is_phasors):
    """Determines an adjustment value based on the number of active channels and acquisition type.

    This value is used to adjust acquisition times in real-time modes.

    Args:
        enabled_channels (list): A list of the enabled channel indices.
        is_phasors (bool): True if the acquisition is for phasors, False for spectroscopy.

    Returns:
        int: The calculated adjustment value in microseconds.
    """
    if is_phasors:
        if len(enabled_channels) == 1:
            return 600 * 1000
        elif len(enabled_channels) == 2:
            return 800 * 1000
        elif len(enabled_channels) == 3:
            return 900 * 1000
        elif len(enabled_channels) >= 4:
            return 1000 * 1000
        else:
            return 0
    else:
        if len(enabled_channels) == 1:
            return 50 * 1000
        elif len(enabled_channels) == 2:
            return 100 * 1000
        elif len(enabled_channels) == 3:
            return 150 * 1000
        elif len(enabled_channels) >= 4:
            return 200 * 1000
        else:
            return 0


def extract_channel_from_label(text):
    """Extracts a zero-based channel index from a label string (e.g., "Channel 1" -> 0).

    Args:
        text (str): The label string containing a channel number.

    Returns:
        int: The extracted channel index.
    """
    ch = re.search(r"\d+", text).group()
    ch_num = int(ch)
    ch_num_index = ch_num - 1
    return ch_num_index


def humanize_number(number):
    """Formats a large number into a human-readable string with metric prefixes (K, M, G, etc.).

    Args:
        number (int or float): The number to format.

    Returns:
        str: The human-readable string representation of the number.
    """
    if number == 0:
        return "0"
    units = ["", "K", "M", "G", "T", "P"]
    k = 1000.0
    magnitude = int(floor(log(number, k)))
    scaled_number = number / k**magnitude
    return (
        f"{int(scaled_number)}.{str(scaled_number).split('.')[1][:2]}{units[magnitude]}"
    )


def get_nearest_frequency_mhz(
    target_freq_mhz, available_freqs_mhz=AVAILABLE_FREQUENCIES_MHZ
):
    """Finds the nearest frequency to target_freq_mhz from the available options.

    Args:
        target_freq_mhz (float): The reference frequency in MHz.
        available_freqs_mhz (list[float]): List of available frequencies in MHz.

    Returns:
        float: The nearest frequency from the options.
    """
    if not available_freqs_mhz:
        raise ValueError("The list of available frequencies is empty.")
    sorted_options = sorted(available_freqs_mhz)
    best = sorted_options[0]
    best_diff = abs(target_freq_mhz - best)
    for option in sorted_options:
        diff = abs(target_freq_mhz - option)
        if diff < best_diff:
            best = option
            best_diff = diff
    return best
