import os
import numpy as np
import json
import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm

# Create a directory for output files ('summary analysis') if it does not exist
output_dir = os.path.join(os.getcwd(), "summary-analysis")
os.makedirs(output_dir, exist_ok=True)


def is_spectroscopy_file(filename):
    """Check if the given filename is a valid spectroscopy file."""
    return (
        ".bin" in filename
        and "phasors" not in filename
        and "fitting" not in filename
        and "time_tagger" not in filename
        and "spectroscopy" in filename
    )


def load_spectroscopy_metadata(fid):
    sp01 = fid.read(4)
    if sp01.decode() != "SP01":
        raise ValueError("Invalid data file format (SP01 not found)")
    json_length = int.from_bytes(fid.read(4), byteorder="little")
    metadata_json = fid.read(json_length)
    return json.loads(metadata_json.decode())


def process_spectroscopy_file(filename):
    """Process a single spectroscopy file to extract data and metadata."""
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


def load_json(filename):
    with open(filename, "r") as f:
        return json.load(f)


def find_corresponding_laserblood_metadata(spectroscopy_file, metadata_files):
    """Find the corresponding metadata file for a given spectroscopy file."""
    base_name = spectroscopy_file.replace("_spectroscopy.bin", "")
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


def export_spectroscopy_data_to_excel(spectroscopy_files, X_VALUES, CURVES):
    """Export spectroscopy processed data to an Excel file."""
    if X_VALUES.shape[0] != CURVES.shape[0]:
        raise ValueError("Mismatch in number of rows between X_VALUES and CURVES.")
    # Create DataFrame with the first column as X_VALUES and subsequent columns as CURVES
    export_data = pd.DataFrame(data=np.column_stack((X_VALUES[:, 0], CURVES)),
                                columns=["t (ns)"] + [f"{file}" for file in spectroscopy_files])
    # Progress bar for Excel export
    with tqdm(
        total=1, desc="Exporting Spectroscopy Summary Data to Excel...", colour="blue"
    ) as pbar:
        with pd.ExcelWriter(
            os.path.join(output_dir, "spectroscopy_summary_data.xlsx")
        ) as writer:
            export_data.to_excel(
                writer,
                sheet_name="Spectroscopy Analysis",
                index=False,
            )
            pbar.update(1)  # Update progress bar after export


def export_spectroscopy_data_to_parquet(spectroscopy_files, X_VALUES, CURVES):
    """Export spectroscopy processed data to a Parquet file."""
    if X_VALUES.shape[0] != CURVES.shape[0]:
        raise ValueError("Mismatch in number of rows between X_VALUES and CURVES.")
    # Create DataFrame with the first column as X_VALUES and subsequent columns as CURVES
    export_data = pd.DataFrame(data=np.column_stack((X_VALUES[:, 0], CURVES)),
                                columns=["t (ns)"] + [f"{file}" for file in spectroscopy_files])
    # Progress bar for Parquet export
    with tqdm(
        total=1,
        desc="Exporting Spectroscopy Summary Data to Parquet...",
        colour="blue",
    ) as pbar:
        export_data.to_parquet(
            os.path.join(output_dir, "spectroscopy_summary_data.parquet"), index=False
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
            os.path.join(output_dir, "spectroscopy_metadata_summary.xlsx"), index=False
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
            os.path.join(output_dir, "spectroscopy_metadata_summary.parquet"), index=False
        )
        pbar.update(1)  # Update progress bar after export


def plot_results(spectroscopy_files, X_VALUES, CURVES):
    """Generate/save and display a plot of spectroscopy data summary."""
    plt.figure()
    for i in range(len(spectroscopy_files)):
        plt.plot(X_VALUES[:, i], CURVES[:, i], label=spectroscopy_files[i])
    plt.xlabel("Time (ns)")
    plt.ylabel("Intensity")
    plt.legend(loc="upper right", bbox_to_anchor=(1.2, 1), fontsize=8)
    plt.grid(True)
    plt.title("Spectroscopy Summary")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "spectroscopy_summary_plot.png"), dpi=300)
    plt.savefig(os.path.join(output_dir, "spectroscopy_summary_plot.eps"))
    plt.show()


if __name__ == "__main__":
    current_folder = os.getcwd()
    folder_info = os.listdir(current_folder)
    spectroscopy_files = [f for f in folder_info if is_spectroscopy_file(f)]
    metadata_files = [f for f in folder_info if f.endswith("_laserblood_metadata.json")]
    X_VALUES = []
    CURVES = []

    # DataFrame for metadata
    metadata_data = {}

    for filename in tqdm(
        spectroscopy_files, desc="Processing Spectroscopy files...", colour="blue"
    ):
        try:
            x_values, sum_curve = process_spectroscopy_file(filename)
            X_VALUES.append(x_values)
            CURVES.append(sum_curve)

            # Find the corresponding metadata file
            metadata_file = find_corresponding_laserblood_metadata(
                filename, metadata_files
            )
            if metadata_file:
                metadata_info = collect_laserblood_metadata_info(metadata_file)
                metadata_data[metadata_file] = metadata_info  # Store metadata info
        except ValueError as e:
            print(f"Error processing {filename}: {e}")
            continue

    # Transpose the results
    X_VALUES = np.array(X_VALUES).T
    CURVES = np.array(CURVES).T

    # Create a DataFrame from the collected metadata
    metadata_df = pd.DataFrame.from_dict(metadata_data, orient="index")

    # Export Spectroscopy Data Summary to Excel
    export_spectroscopy_data_to_excel(spectroscopy_files, X_VALUES, CURVES)

    # Export Spectroscopy Data Summary to Parquet
    export_spectroscopy_data_to_parquet(spectroscopy_files, X_VALUES, CURVES)

    # Export Laserblood Metadata Summary to Excel
    export_laserblood_metadata_to_excel(metadata_df, metadata_files)

    # Export Laserblood Metadata Summary to Parquet
    export_laserblood_metadata_to_parquet(metadata_df, metadata_files)

    # Display results
    plot_results(spectroscopy_files, X_VALUES, CURVES)
