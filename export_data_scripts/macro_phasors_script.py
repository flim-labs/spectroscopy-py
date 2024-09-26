import os
import struct
import numpy as np
import json
import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm

# Create a directory for output files ('summary analysis') if it does not exist
output_dir = os.path.join(os.getcwd(), "summary-analysis")
os.makedirs(output_dir, exist_ok=True)


def is_spectroscopy_reference_file(filename):
    """Check if the given filename is a valid phasors spectroscopy reference file."""
    return (
        ".bin" in filename
        and "phasors_spectroscopy" in filename
    )
    
    
def is_phasors_file(filename):
    """Check if the given filename is a valid phasors file."""
    return (
        ".bin" in filename
        and "phasors" in filename
        and "spectroscopy" not in filename
    )    
    

def load_spectroscopy_metadata(fid):
    sp01 = fid.read(4)
    if sp01.decode() != "SP01":
        raise ValueError("Invalid data file format (SP01 not found)")
    json_length = int.from_bytes(fid.read(4), byteorder="little")
    metadata_json = fid.read(json_length)
    return json.loads(metadata_json.decode())


def load_phasors_metadata(fid):
    spf1 = fid.read(4)
    if spf1.decode() != "SPF1":
        raise ValueError("Invalid data file format (SPF1 not found)")
    json_length = int.from_bytes(fid.read(4), byteorder="little")
    metadata_json = fid.read(json_length)
    return json.loads(metadata_json.decode())


def process_spectroscopy_reference_file(filename):
    """Process a single spectroscopy reference file to extract data and metadata."""
    with open(filename, "rb") as fid:
        metadata = load_spectroscopy_metadata(fid)
        if "channels" not in metadata:
            raise ValueError(f"Channels not found in {filename}")
        if "laser_period_ns" not in metadata:
            raise ValueError(f"Laser period not found in {filename}")
        laser_period_ns = metadata["laser_period_ns"]
        num_channels = len(metadata["channels"])
        channel_curves = [[] for _ in range(num_channels)]
        times = []
        while True:
            time_data = np.fromfile(fid, dtype=np.float64, count=1)
            if len(time_data) == 0:
                break
            times.append(time_data[0] / 1e9)

            for i in range(num_channels):
                curve_data = np.fromfile(fid, dtype=np.uint32, count=256)
                if len(curve_data) < 256:
                    break
                channel_curves[i].append(curve_data)
        num_bins = 256
        x_values = np.linspace(0, laser_period_ns, num_bins)
        sum_curve = np.sum(channel_curves[0], axis=0)
        return x_values, sum_curve
    
    
def process_phasors_file(filename):
    """Process a single phasors file to extract data and metadata."""
    with open(filename, "rb") as fid:
        phasors_data = {}
        metadata = load_phasors_metadata(fid)
        if "channels" not in metadata:
            raise ValueError(f"Channels not found in {filename}")
        if "laser_period_ns" not in metadata:
            raise ValueError(f"Laser period not found in {filename}")
        try:
            while True:
                bytes_read = fid.read(32)  
                if not bytes_read:
                    raise StopIteration   
                try:
                    time_ns, channel_name, harmonic_name, g, s = struct.unpack(
                        "QIIdd", bytes_read
                    )
                except struct.error as e:
                    print(f"Error unpacking phasors_data: {e}")
                    raise StopIteration 
                if channel_name not in phasors_data:                
                    phasors_data[channel_name] = {}
                if harmonic_name not in phasors_data[channel_name]:                    
                    phasors_data[channel_name][harmonic_name] = []        
                phasors_data[channel_name][harmonic_name].append((g, s))                                                          
        except StopIteration:
            pass
        return phasors_data, metadata["laser_period_ns"]


def ns_to_mhz(laser_period_ns):
    period_s = laser_period_ns * 1e-9
    frequency_hz = 1 / period_s
    frequency_mhz = frequency_hz / 1e6
    return frequency_mhz    
    
def calculate_phasor_tau_components(laser_period_ns, harmonic, mean_s, mean_g):
    freq_mhz = ns_to_mhz(laser_period_ns)
    tau_phi = (1 / (2 * np.pi * freq_mhz * harmonic)) * (mean_s / mean_g) * 1e3
    tau_m_component = (1 / (mean_s**2 + mean_g**2)) - 1
    tau_m = (((1 / (2 * np.pi * freq_mhz * harmonic))* np.sqrt(tau_m_component)* 1e3) if tau_m_component >= 0 else None)    
    return tau_phi, tau_m


def plot_results(spectroscopy_files, phasors_files, SPECTROSCOPY_X_VALUES, SPECTROSCOPY_CURVES, PHASORS_DATA, laser_period_ns):
    num_plots = 2
    num_rows = 1
    fig, axs = plt.subplots(num_rows + 1, num_plots, figsize=(20, (num_rows + 1) * 6))
    sp_ax = axs[0, 0]
    # Spectroscopy plot
    for i in range(len(spectroscopy_files)):
        sp_ax.plot(SPECTROSCOPY_X_VALUES[:, i], SPECTROSCOPY_CURVES[:, i], label=spectroscopy_files[i])
    sp_ax.set_xlabel("Time (ns)")  
    sp_ax.set_ylabel("Intensity")
    sp_ax.legend(loc="upper right", bbox_to_anchor=(1.2, 1), fontsize=8)
    sp_ax.grid(True) 
    sp_ax.set_title(f"Spectroscopy Reference - Summary")
    # Phasor plot
    harmonics = []
    g_all_points = {}
    s_all_points = {}
    points_colors = ["#fde725", "#7ad151", "#22a884", "#440154"]
    for i in range(len(phasors_files)):
        phasor_data = PHASORS_DATA[i]
        for j, (_, harmonics) in enumerate(phasor_data.items(), start=1):
            for harmonic, values in harmonics.items():
                if values:
                    g_values, s_values = zip(*values)
                    g_values = np.array(g_values)
                    s_values = np.array(s_values)
                    mask = (np.abs(g_values) < 1e9) & (np.abs(s_values) < 1e9)
                    g_values = g_values[mask]
                    s_values = s_values[mask]
                    if not harmonic in g_all_points and not harmonic in s_all_points:
                        g_all_points[harmonic] = []
                        s_all_points[harmonic] = []
                    g_all_points[harmonic].extend(g_values)
                    s_all_points[harmonic].extend(s_values)
                    if harmonic not in harmonics:
                        harmonics.append(harmonic)
    ph_ax = axs[0, 1] 
    x =  np.linspace(0, 1, 1000)
    y = np.sqrt(0.5**2 - (x - 0.5) ** 2)
    ph_ax.plot(x, y)
    ph_ax.set_aspect('equal') 
    for i, harmonic in enumerate(harmonics):
        mean_g = np.mean(g_all_points[harmonic])
        mean_s = np.mean(s_all_points[harmonic])
        tau_phi, tau_m = calculate_phasor_tau_components(laser_period_ns, harmonic, mean_s, mean_g)
        mean_label = f"Harmonic: {harmonic}; G (mean): {round(mean_g, 2)}; S (mean): {round(mean_s, 2)}; τϕ={round(tau_phi, 2)} ns"
        if tau_m is not None:
            mean_label += f"; τm={round(tau_m, 2)} ns"  
        ph_ax.scatter(
            mean_g,
            mean_s,
            color=points_colors[i],
            zorder=3,
            label=mean_label,
        )            
    ph_ax.legend(fontsize="small")  
    ph_ax.set_title(f"Phasors - Summary")     
    ph_ax.set_xlabel("G")   
    ph_ax.set_ylabel("S") 
    ph_ax.grid(True)   
    for i in range(2, (num_rows + 1) * num_plots):
        row = i // num_plots
        col = i % num_plots
        fig.delaxes(axs[row, col])       
    plt.tight_layout(pad=4.0, w_pad=4.0, h_pad=4.0) 
    plt.savefig(os.path.join(output_dir, "phasors_summary_plot.png"), dpi=300)
    plt.savefig(os.path.join(output_dir, "phasors_summary_plot.eps"))         
    plt.show()                    
                    
                    
                    
        
    


if __name__ == "__main__":
    current_folder = os.getcwd()
    folder_info = os.listdir(current_folder)
    spectroscopy_references_files = [f for f in folder_info if is_spectroscopy_reference_file(f)]
    phasors_files = [f for f in folder_info if is_phasors_file(f)]
    
    SPECTROSCOPY_X_VALUES = []
    SPECTROSCOPY_CURVES = []
    PHASORS_DATA = []
    laser_period_ns = None

    # Process Spectroscopy Reference Files
    for filename in tqdm(
        spectroscopy_references_files, desc="Processing Spectroscopy Reference files...", colour="blue"
    ):
        try:
            x_values, sum_curve = process_spectroscopy_reference_file(filename)
            SPECTROSCOPY_X_VALUES.append(x_values)
            SPECTROSCOPY_CURVES.append(sum_curve)
        except ValueError as e:
            print(f"Error processing {filename}: {e}")
            continue
    # Transpose the results
    SPECTROSCOPY_X_VALUES = np.array(SPECTROSCOPY_X_VALUES).T
    SPECTROSCOPY_CURVES = np.array(SPECTROSCOPY_CURVES).T
    
    # Process Phasors Files
    for filename in tqdm(
        phasors_files, desc="Processing Phasors files...", colour="blue"
    ):
        try:
            phasor_data, laser_period = process_phasors_file(filename)
            PHASORS_DATA.append(phasor_data)
            if laser_period_ns is None:
                laser_period_ns = laser_period
        except ValueError as e:
            print(f"Error processing {filename}: {e}")
            continue    
    
    # Plot and save images
    plot_results(spectroscopy_references_files, phasors_files, SPECTROSCOPY_X_VALUES, SPECTROSCOPY_CURVES, PHASORS_DATA, laser_period_ns)


            
            
