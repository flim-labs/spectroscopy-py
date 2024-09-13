import struct
import pandas as pd
import os
import json
from tqdm import tqdm
import pyarrow as pa
import pyarrow.parquet as pq
from colorama import Fore, init
import keyboard  
import warnings  

file_path = "<FILE-PATH>"

init(autoreset=True)  
warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")

def read_time_tagger_bin(file_path, chunk_size=100000):
    if not os.path.exists(file_path):
        print(Fore.RED + f"File not found: {file_path}")
        return

    record_size = 17  # 1 byte per channel, 8 bytes per micro_time (f64), 8 bytes per macro_time (f64)

    def read_header(f):
        if f.read(4) != b"STT1":
            print(Fore.RED + "Invalid data file")
            exit(0)
        header_length_bytes = f.read(4)
        header_length = struct.unpack("<I", header_length_bytes)[0]
        header_json = f.read(header_length).decode("utf-8")
        header = json.loads(header_json)
        return header

    def record_generator(file_path, record_size):
        with open(file_path, "rb") as f:
            header = read_header(f)
            if "channels" in header and header["channels"] is not None:
                enabled_channels = ", ".join(
                    ["Channel " + str(ch + 1) for ch in header["channels"]]
                )
            if "laser_period_ns" in header and header["laser_period_ns"] is not None:
                laser_period = str(header["laser_period_ns"]) + "ns"

            while True:
                record = f.read(record_size)
                if len(record) < record_size:
                    break
                yield struct.unpack("<Bdd", record), enabled_channels, laser_period

    records = []
    for i, (record, enabled_channels, laser_period) in enumerate(
        record_generator(file_path, record_size)
    ):
        channel, micro_time, macro_time = record
        records.append((f"ch{channel + 1}", round(micro_time, 1), round(macro_time, 1)))

        if (i + 1) % chunk_size == 0:
            yield pd.DataFrame(
                records, columns=["Event", "Micro Time (ns)", "Macro Time (ns)"]
            ), enabled_channels, laser_period
            records = []

    if records:
        yield pd.DataFrame(
            records, columns=["Event", "Micro Time (ns)", "Macro Time (ns)"]
        ), enabled_channels, laser_period

def save_to_parquet(file_path, output_file):
    if not os.path.exists(file_path):
        print(Fore.RED + f"File not found: {file_path}")
        return

    # Check if the Parquet file already exists
    if os.path.exists(output_file):
        print(Fore.YELLOW + f"{output_file} already exists. Skipping save.")
        return  # If it exists, skip saving

    print(Fore.CYAN + f"Saving data to {output_file}...")

    # Read all chunks and count the total number of chunks
    records_list = []
    enabled_channels = laser_period = None
    chunk_count = 0

    for chunk, channels, period in read_time_tagger_bin(file_path):
        records_list.append(chunk)
        enabled_channels = channels
        laser_period = period
        chunk_count += 1

    # Set up the progress bar
    with tqdm(
        total=chunk_count,
        desc="Progress",
        unit="chunk",
        ncols=100,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {percentage:.1f}%"
    ) as pbar:
        existing_data = pd.concat(records_list, ignore_index=True)
        existing_data.sort_values(by="Macro Time (ns)", inplace=True)
        pbar.update(chunk_count)

    # Save the DataFrame as Parquet and add metadata (enabled_channels and laser_period)
    table = pa.Table.from_pandas(existing_data)
    metadata = {"enabled_channels": enabled_channels, "laser_period": laser_period}
    table = table.replace_schema_metadata(
        {**table.schema.metadata, **{k: v.encode() for k, v in metadata.items()}}
    )

    pq.write_table(table, output_file, compression="snappy")
    print(Fore.GREEN + f"Data and metadata saved to {output_file}.")

def read_from_parquet(parquet_file):
    if not os.path.exists(parquet_file):
        print(Fore.RED + f"File not found: {parquet_file}")
        return

    print(Fore.CYAN + f"Reading data from {parquet_file}...")

    # Read the Parquet file
    table = pq.read_table(parquet_file)
    metadata = table.schema.metadata

    # Retrieve metadata
    enabled_channels = (
        metadata.get(b"enabled_channels").decode()
        if b"enabled_channels" in metadata
        else None
    )
    laser_period = (
        metadata.get(b"laser_period").decode() if b"laser_period" in metadata else None
    )

    print("\n")
    print(Fore.GREEN + f"Enabled channels: {enabled_channels}")
    print(Fore.GREEN + f"Laser period: {laser_period}")
    print("\n")

    # Convert the table to a DataFrame
    df = table.to_pandas()

    # Choose the display option
    print(Fore.CYAN + "Choose display option:")
    print(Fore.YELLOW + "1. Overview (first and last rows)")
    print(
        Fore.YELLOW
        + "2. Read full data (may take time if you select many rows per chunk)"
    )

    choice = input(Fore.CYAN + "Enter your choice (1 or 2): ")

    if choice == "1":
        print(Fore.CYAN + "Showing an overview of the data:")
        print("\n")
        print(Fore.GREEN + df.head().to_string())
        print("\n...\n")
        print(Fore.GREEN + df.tail().to_string())
        print("\n")
    elif choice == "2":
        # Ask the user for the maximum number of rows per chunk
        max_rows = int(
            input(Fore.CYAN + "Enter the maximum number of rows to read per chunk: ")
        )
        # Display the data in chunks to avoid memory overload
        for start in range(0, len(df), max_rows):
            end = start + max_rows
            print("\n")
            print(Fore.GREEN + df.iloc[start:end].to_string(index=False))
            print("\n")
            if end < len(df):
                # Check if the user pressed ESC
                print(
                    Fore.CYAN + "Press Enter to load the next chunk or ESC to exit..."
                )
                if keyboard.read_event().name == "esc":
                    print(Fore.RED + "Exiting...")
                    exit(0)
    else:
        print(Fore.RED + "Invalid choice. Showing default overview.")
        print("\n")
        print(Fore.GREEN + df.head().to_string())
        print("\n...\n")
        print(Fore.GREEN + df.tail().to_string())
        print("\n")
    return df

def main():
    print(Fore.CYAN + "Select an operation:")
    print(Fore.YELLOW + "1. Save data to Parquet")
    print(Fore.YELLOW + "2. Read data from an existing Parquet file")

    choice = input(Fore.CYAN + "Enter your choice (1 or 2): ")

    if choice == "1":
        output_file = input(
            Fore.CYAN + "Enter the output Parquet file path (e.g., output.parquet): "
        )
        save_to_parquet(file_path, output_file)
    elif choice == "2":
        parquet_file = input(Fore.CYAN + "Enter the Parquet file path to read: ")
        read_from_parquet(parquet_file)
    else:
        print(Fore.RED + "Invalid choice. Please enter either 1 or 2.")

if __name__ == "__main__":
    main()
