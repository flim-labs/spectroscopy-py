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


def load_bin_metadata(fid, expected_prefix):
    """Load metadata from a binary file and verify the expected prefix."""
    prefix = fid.read(4).decode()
    if prefix != expected_prefix:
        raise ValueError(f"Invalid data file format ({expected_prefix} not found)")
    json_length = int.from_bytes(fid.read(4), byteorder="little")
    metadata_json = fid.read(json_length)
    return json.loads(metadata_json.decode())


def is_valid_file(filename, file_type):
    """Check if the file is valid for spectroscopy or phasors."""
    if file_type == "spectroscopy":
        return ".bin" in filename and "phasors_spectroscopy" in filename
    if file_type == "phasors":
        return (
            ".bin" in filename
            and "phasors" in filename
            and "spectroscopy" not in filename
        )
    return False


def load_json(filename):
    with open(filename, "r") as f:
        return json.load(f)


def find_corresponding_laserblood_metadata(phasor_file, metadata_files):
    """Find the corresponding metadata file for a given phasor file."""
    base_name = phasor_file.replace("_phasors.bin", "")
    metadata_file = f"{base_name}_laserblood_metadata.json"
    return metadata_file if metadata_file in metadata_files else None


def collect_laserblood_metadata_info(metadata_file):
    """Collect the laserblood metadata information and return a structured format."""
    metadata = load_json(metadata_file)
    result = {}
    for item in metadata:
        label = item["label"]
        unit = item["unit"]
        key = f"{label} ({unit})" if unit else label
        result[key] = item["value"]
    return result


def export_phasors_data_to_excel(spectroscopy_files, X_VALUES, CURVES, phasors_data):
    """Export phasors processed data to an Excel file with multiple sheets."""
    if X_VALUES.shape[0] != CURVES.shape[0]:
        raise ValueError("Mismatch in number of rows between X_VALUES and CURVES.")
    # Spectroscopy reference dataframe
    spectroscopy_df = pd.DataFrame(
        data=np.column_stack((X_VALUES[:, 0], CURVES)),
        columns=["t (ns)"] + [f"{file}" for file in spectroscopy_files],
    )
    # Phasors dataframe
    phasors_df = pd.DataFrame(phasors_data)
    with tqdm(
        total=1, desc="Exporting Phasors Data to Excel...", colour="blue"
    ) as pbar:
        with pd.ExcelWriter(
            os.path.join(output_dir, "phasors_summary_data.xlsx")
        ) as writer:
            phasors_df.to_excel(writer, sheet_name="Phasors Analysis", index=False)
            spectroscopy_df.to_excel(
                writer, sheet_name="Spectroscopy Reference Analysis", index=False
            )
            pbar.update(1)


def export_spectroscopy_reference_data_to_parquet(spectroscopy_files, X_VALUES, CURVES):
    """Export spectroscopy reference processed data to a Parquet file."""
    if X_VALUES.shape[0] != CURVES.shape[0]:
        raise ValueError("Mismatch in number of rows between X_VALUES and CURVES.")
    # Create DataFrame with the first column as X_VALUES and subsequent columns as CURVES
    export_data = pd.DataFrame(
        data=np.column_stack((X_VALUES[:, 0], CURVES)),
        columns=["t (ns)"] + [f"{file}" for file in spectroscopy_files],
    )
    # Progress bar for Parquet export
    with tqdm(
        total=1,
        desc="Exporting Spectroscopy Reference Summary Data to Parquet...",
        colour="blue",
    ) as pbar:
        export_data.to_parquet(
            os.path.join(
                output_dir, "spectroscopy_phasors_reference_summary_data.parquet"
            ),
            index=False,
        )
        pbar.update(1)  # Update progress bar after export


def export_phasors_data_to_parquet(phasors_data):
    """Export phasors processed data to a Parquet file."""
    export_data = pd.DataFrame(data=phasors_data)
    # Progress bar for Parquet export
    with tqdm(
        total=1,
        desc="Exporting Phasors Summary Data to Parquet...",
        colour="blue",
    ) as pbar:
        export_data.to_parquet(
            os.path.join(output_dir, "phasors_summary_data.parquet"), index=False
        )
        pbar.update(1)  # Update progress bar after export


def export_laserblood_metadata_to_excel(metadata_df, metadata_files):
    """Export Laserblood metadata to an Excel file"""
    metadata_files_col = pd.DataFrame(metadata_files, columns=["File"])
    export_data = pd.concat(
        [metadata_files_col, metadata_df.reset_index(drop=True)], axis=1
    )
    # Progress bar for Excel export
    with tqdm(
        total=1,
        desc="Exporting Laserblood Metadata Summary to Excel...",
        colour="blue",
    ) as pbar:
        export_data.to_excel(
            os.path.join(output_dir, "phasors_metadata_summary.xlsx"), index=False
        )
        pbar.update(1)  # Update progress bar after export


def export_laserblood_metadata_to_parquet(metadata_df, metadata_files):
    """Export Laserblood metadata to a Parquet file"""
    metadata_files_col = pd.DataFrame(metadata_files, columns=["File"])
    export_data = pd.concat(
        [metadata_files_col, metadata_df.reset_index(drop=True)], axis=1
    )
    # Progress bar for Parquet export
    with tqdm(
        total=1,
        desc="Exporting Laserblood Metadata Summary to Parquet...",
        colour="blue",
    ) as pbar:
        export_data.to_parquet(
            os.path.join(output_dir, "phasors_metadata_summary.parquet"), index=False
        )
        pbar.update(1)  # Update progress bar after export


def process_spectroscopy_reference_file(filename):
    """Process a single spectroscopy reference file to extract data and metadata."""
    with open(filename, "rb") as fid:
        metadata = load_bin_metadata(fid, "SP01")
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
        metadata = load_bin_metadata(fid, "SPF1")
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
    tau_m = (
        ((1 / (2 * np.pi * freq_mhz * harmonic)) * np.sqrt(tau_m_component) * 1e3)
        if tau_m_component >= 0
        else None
    )
    return tau_phi, tau_m

def extract_phasor_points_data(phasors_files, PHASORS_DATA, laser_period_ns):
    harmonics = []
    files_phasor_info = []
    seen = set()
    for i, filename in enumerate(phasors_files):
        phasor_data = PHASORS_DATA[i]
        for j, (_, harmonics_dict) in enumerate(phasor_data.items(), start=1):
            for harmonic, values in harmonics_dict.items():
                if values:
                    g_values, s_values = zip(*values)
                    g_values = np.array(g_values)
                    s_values = np.array(s_values)
                    mask = (np.abs(g_values) < 1e9) & (np.abs(s_values) < 1e9)
                    g_values = g_values[mask]
                    s_values = s_values[mask]
                    mean_g = np.mean(g_values)
                    mean_s = np.mean(s_values)
                    tau_phi, tau_m = calculate_phasor_tau_components(
                        laser_period_ns, harmonic, mean_s, mean_g
                    )
                    identifier = (filename, harmonic)
                    if identifier not in seen:
                        files_phasor_info.append(
                            {
                                "File": filename,
                                "Harmonic": harmonic,
                                "G (mean)": mean_g,
                                "S (mean)": mean_s,
                                "τϕ (ns)": tau_phi,
                                "τm (ns)": tau_m,
                            }
                        )
                        seen.add(identifier)  
                    if harmonic not in harmonics:
                        harmonics.append(harmonic)
    return harmonics, files_phasor_info



def plot_spectroscopy(spectroscopy_files, SPECTROSCOPY_X_VALUES, SPECTROSCOPY_CURVES):
    """Plot and save spectroscopy reference results."""
    plt.figure(figsize=(8, 6)) 
    for i in range(len(spectroscopy_files)):
        plt.plot(
            SPECTROSCOPY_X_VALUES[:, i],
            SPECTROSCOPY_CURVES[:, i],
            label=spectroscopy_files[i],
        )
    plt.xlabel("Time (ns)")
    plt.ylabel("Intensity")
    plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=1, fontsize=8) 
    plt.grid(True)
    plt.title("Spectroscopy Reference - Summary")
    plt.tight_layout(pad=4.0)  
    plt.savefig(os.path.join(output_dir, "phasors_spectroscopy_reference_summary_plot.png"), dpi=300, bbox_inches='tight')
    plt.savefig(os.path.join(output_dir, "phasors_spectroscopy_reference_summary_plot.eps"), bbox_inches='tight')


    

def plot_phasors(harmonics, phasors_info):
    """Plot and save phasors results."""
    plt.figure(figsize=(12, 6)) 
    x = np.linspace(0, 1, 1000)
    y = np.sqrt(0.5**2 - (x - 0.5) ** 2)
    plt.plot(x, y)
    plt.gca().set_aspect('equal')  
    total_points = sum(len([phasor for phasor in phasors_info if phasor["Harmonic"] == harmonic]) for harmonic in harmonics)
    colors = plt.cm.viridis(np.linspace(0, 1, total_points))
    color_idx = 0
    for phasor in phasors_info:
        mean_g = phasor["G (mean)"]
        mean_s = phasor["S (mean)"]
        tau_phi = phasor["τϕ (ns)"]
        tau_m = phasor["τm (ns)"]
        mean_label = f"{phasor['File']}; Harmonic: {phasor["Harmonic"]}; G (mean): {round(mean_g, 2)}; S (mean): {round(mean_s, 2)}; τϕ={round(tau_phi, 2)} ns"
        if tau_m is not None:
            mean_label += f"; τm={round(tau_m, 2)} ns"
        plt.scatter(
            mean_g,
            mean_s,
            color=colors[color_idx],
            edgecolor='black',
            zorder=3,
            s=24,
            linewidths=0.6, 
            label=mean_label,
        )
        color_idx += 1
    plt.legend(loc="center left", bbox_to_anchor=(1.05, 0.5), fontsize="small", ncol=1)
    plt.title("Phasors - Summary")
    plt.xlabel("G")
    plt.ylabel("S")
    plt.grid(True)
    plt.tight_layout(pad=1.0)
    plt.savefig(os.path.join(output_dir, "phasors_summary_plot.png"), dpi=300, bbox_inches='tight')
    plt.savefig(os.path.join(output_dir, "phasors_summary_plot.eps"), bbox_inches='tight')


    


if __name__ == "__main__":
    current_folder = os.getcwd()
    folder_info = os.listdir(current_folder)
    spectroscopy_references_files = [
        f for f in folder_info if is_valid_file(f, "spectroscopy")
    ]
    phasors_files = [f for f in folder_info if is_valid_file(f, "phasors")]
    metadata_files = [f for f in folder_info if f.endswith("_laserblood_metadata.json")]
    filtered_metadata_files = []
    if len(phasors_files) == 0 or len(spectroscopy_references_files) == 0 or len(metadata_files) == 0:
        print("Phasors files or Spectroscopy Reference files or Laserblood metadata files not found")
    else:    
        SPECTROSCOPY_X_VALUES = []
        SPECTROSCOPY_CURVES = []
        PHASORS_DATA = []
        laser_period_ns = None
        metadata_data = {}

        # Process Spectroscopy Reference Files
        for filename in tqdm(
            spectroscopy_references_files,
            desc="Processing Spectroscopy Reference files...",
            colour="blue",
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
                # Find the corresponding metadata file
                metadata_file = find_corresponding_laserblood_metadata(
                    filename, metadata_files
                )
                if metadata_file:
                    filtered_metadata_files.append(metadata_file)
                    metadata_info = collect_laserblood_metadata_info(metadata_file)
                    metadata_data[metadata_file] = metadata_info  # Store metadata info
            except ValueError as e:
                print(f"Error processing {filename}: {e}")
                continue

        harmonics, files_phasor_info = (
            extract_phasor_points_data(phasors_files, PHASORS_DATA, laser_period_ns)
        )

        # Create a DataFrame from the collected metadata
        metadata_df = pd.DataFrame.from_dict(metadata_data, orient="index")

        # Export Phasors Data Summary to Excel
        export_phasors_data_to_excel(
            spectroscopy_references_files,
            SPECTROSCOPY_X_VALUES,
            SPECTROSCOPY_CURVES,
            files_phasor_info,
        )

        # Export Spectroscopy Reference Data Summary to Parquet
        export_spectroscopy_reference_data_to_parquet(
            spectroscopy_references_files, SPECTROSCOPY_X_VALUES, SPECTROSCOPY_CURVES
        )

        # Export Phasors Data Summary to Parquet
        export_phasors_data_to_parquet(files_phasor_info)

        # Export Laserblood Metadata Summary to Excel
        export_laserblood_metadata_to_excel(metadata_df, filtered_metadata_files)

        # Export Laserblood Metadata Summary to Parquet
        export_laserblood_metadata_to_parquet(metadata_df, filtered_metadata_files)
        
        # Plot and save phasors images
        plot_phasors(harmonics, files_phasor_info)

        # Plot and save spectroscopy reference images
        plot_spectroscopy(
        spectroscopy_references_files,
        SPECTROSCOPY_X_VALUES,
        SPECTROSCOPY_CURVES,
        )

