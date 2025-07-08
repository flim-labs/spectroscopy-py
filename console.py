import threading
import flim_labs

def stop():
    print("stop")


def process(time, _x, counts):
    seconds = round(time / 1_000_000_000, 5)
    print(f"[{str(seconds).zfill(5)}s] {counts[0]}")


def thread_function():
    print("Thread: Start reading from queue")
    while True:
        for v in flim_labs.pull_from_queue():
            if v == ('end',):
                print("Experiment ended")
                return
            (ch,), (time,), decay = v
            print(f"Channel={ch} Time={time} Decay={decay}")


def detect_laser_sync_in_frequency():
    print("Measuring frequency... Please wait (timeout: 30s).")
    try:
        res = flim_labs.detect_laser_frequency()
        if not res:
            print("Frequency not detected. Check the connection.")
            return 0.0
        freq = round(res, 3)
        print(f"Frequency detected: {freq} MHz")
        return freq
    except Exception as e:
        print(f"Error: {e}")
        return 0.0


def select_firmware(sync, freq, conn_type, channels):
    return flim_labs.get_spectroscopy_firmware(
        sync="in" if sync == "sync_in" else "out",
        frequency_mhz=freq,
        channel=conn_type.lower(),
        sync_connection="sma",
        channels = channels
    )


def select_frequency_mhz(sync, sync_in_freq):
    if sync == "sync_in":
        return sync_in_freq
    return int(sync.split("_")[-1])


if __name__ == "__main__":
    # Configuration
    enabled_channels = [2, 3]               # Channels to acquire (0-indexed)
    connection_type = "USB"                 # USB or SMA
    time_tagger = True                     # Set True to export time tagger data
    bin_width_micros = 1000                 # Bin width in microseconds
    acquisition_time_millis = 3000          # Total acquisition time in milliseconds
    
    #SELECTED SYNC
    #choose between:
     
    #  -  "sync_in": conseguently set the field sync_in_frequency_mhz 
    #  -  "sync_out_10": 10Mhz, the field 'sync_in_frequency'_mhz will not be taken into account accordingly
    #  -  "sync_out_20": 20Mhz, the field 'sync_in_frequency'_mhz will not be taken into account accordingly 
    #  -  "sync_out_40": 40Mhz, the field 'sync_in_frequency'_mhz will not be taken into account accordingly
    #  -  "sync_out_80": 80Mhz,the field 'sync_in_frequency'_mhz will not be taken into account accordingly
    selected_sync = "sync_out_40"           

    sync_in_frequency_mhz = 0.0
    if selected_sync == "sync_in":
        # Manually or automatically detect sync in frequency
        sync_in_frequency_mhz = detect_laser_sync_in_frequency()

    frequency_mhz = select_frequency_mhz(selected_sync, sync_in_frequency_mhz)

    if frequency_mhz:
        result = flim_labs.start_spectroscopy(
            enabled_channels=enabled_channels,
            bin_width_micros=bin_width_micros,
            frequency_mhz=frequency_mhz,
            firmware_file=select_firmware(selected_sync, frequency_mhz, connection_type, enabled_channels),
            acquisition_time_millis=acquisition_time_millis,
            time_tagger=time_tagger
        )

        # Start processing thread
        reader_thread = threading.Thread(target=thread_function)
        reader_thread.start()
        reader_thread.join()
       
        print(f"Data file = {result.data_file}")
        if time_tagger:
            print(f"Time tagger file = {result.data_file.replace("spectroscopy_", "time_tagger_spectroscopy_")}")
