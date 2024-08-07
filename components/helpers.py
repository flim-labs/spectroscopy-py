def format_size(size_in_bytes):
    units = ['B', 'KB', 'MB', 'GB', 'TB']
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
