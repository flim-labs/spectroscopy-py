import numpy as np


def format_size(size_in_bytes):
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0

    while size_in_bytes >= 1024 and unit_index < len(units) - 1:
        size_in_bytes /= 1024.0
        unit_index += 1

    return f"{size_in_bytes:.2f}{units[unit_index]}"


def ns_to_mhz(laser_period_ns):
    period_s = laser_period_ns * 1e-9
    frequency_hz = 1 / period_s
    frequency_mhz = frequency_hz / 1e6
    return frequency_mhz


def mhz_to_ns(frequency_mhz):
    frequency_hz = frequency_mhz * 1e6
    period_s = 1 / frequency_hz
    period_ns = period_s * 1e9
    return period_ns


def convert_ndarray_to_list(data):
    if isinstance(data, np.ndarray):
        return data.tolist()
    return data


def convert_np_num_to_py_num(data):
    if isinstance(data, (np.int64, np.float64)):
        return data.item()
    return data


def convert_py_num_to_np_num(output_data):
    if isinstance(output_data, (int, float)):
        return (
            np.float64(output_data)
            if isinstance(output_data, float)
            else np.int64(output_data)
        )
    return output_data



def get_realtime_adjustment_value(enabled_channels, is_phasors):
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