import threading

import flim_labs


def stop():
    print("stop")


def process(time, _x, counts):
    seconds = round(time / 1_000_000_000, 5)
    seconds = str(seconds).zfill(5)
    print("[" + seconds + "s] " + str(counts[0]))


def thread_function():
    print("Thread: Start reading from queue")
    continue_reading = True
    while continue_reading:
        val = flim_labs.pull_from_queue()

        if len(val) > 0:
            for v in val:
                if v == ('end',):
                    print("Experiment ended")
                    continue_reading = False
                    break
                ((ch,), (time,),(decay)) = v
                print("Channel=" + str(ch) + " Time=" + str(time) + " Decay=" + str(decay))
                # print (v)
                

def detect_laser_sync_in_frequency():
    try: 
        print(
            "Measuring frequency... The process can take a few seconds. Please wait. After 30 seconds, the process "
            "will be interrupted automatically.") 
        res= flim_labs.detect_laser_frequency()
        if res is None or res == 0.0:
                    frequency_mhz = 0.0
                    print("Frequency not detected. Please check the connection and try again.")
        else:
            frequency_mhz = round(res, 3)
            print(f"Frequency detected: {frequency_mhz} MHz")
    except Exception as e:
            frequency_mhz = 0.0
            print("Error: " + str(e))  



def select_firmware():
    firmware_selected = flim_labs.get_spectroscopy_firmware(
            sync="in" if selected_sync == "sync_in" else "out",
            frequency_mhz=frequency_mhz,
            channel=connection_type.lower(),
            sync_connection="sma"
        )
    return firmware_selected



def select_frequency_mhz():
     if selected_sync == "sync_in":
        frequency_mhz = sync_in_frequency_mhz
     else:
        frequency_mhz = int(selected_sync.split("_")[-1])
     if frequency_mhz == 0.0:
            print("Error", "Frequency not detected"),
            return
     return frequency_mhz

     
            
if __name__ == "__main__":

    
    #SELECTED SYNC
    #choose between:
     
    #  -  "sync_in": conseguently set the field sync_in_frequency_mhz 
    #  -  "sync_out_10": 10Mhz, the field 'sync_in_frequency'_mhz will not be taken into account accordingly
    #  -  "sync_out_20": 20Mhz, the field 'sync_in_frequency'_mhz will not be taken into account accordingly 
    #  -  "sync_out_40": 40Mhz, the field 'sync_in_frequency'_mhz will not be taken into account accordingly
    #  -  "sync_out_80": 80Mhz,the field 'sync_in_frequency'_mhz will not be taken into account accordingly

    selected_sync= "sync_out_80"
# -------------------------------------------------------------------------------------------------------------------
    if selected_sync=="sync_in":

    # SYNC IN FREQUENCY
    # leaves this line uncommented to set manually the frequency
     sync_in_frequency_mhz=0.0

    #or uncomment this line to run the automatic laser frequency detecion and comment the line above
    #  sync_in_frequency_mhz= detect_laser_sync_in_frequency() 

# -------------------------------------------------------------------------------------------------------------------

    frequency_mhz=select_frequency_mhz()

    # choose between USB or SMA
    connection_type="USB" 
   
    if frequency_mhz:
        result = flim_labs.start_spectroscopy(
            enabled_channels=[0],
            bin_width_micros=1000,
            frequency_mhz=frequency_mhz,
            firmware_file= select_firmware(),
            acquisition_time_millis=3000,
        )
        x = threading.Thread(target=thread_function)
        x.start()
        x.join()
        # print result
        bin_file = result.bin_file
        data_file = result.data_file
        print("Binary file=" + str(bin_file))
        print("Data file=" + str(data_file))
