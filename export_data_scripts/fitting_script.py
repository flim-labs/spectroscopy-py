import numpy as np
import struct
import matplotlib.pyplot as plt
import json

spectroscopy_file_path = "<SPECTROSCOPY-FILE-PATH>"
fitting_file_path = "<FITTING-FILE-PATH>"

# Custom channel names (if any)
channel_names_json = '<CHANNEL-NAMES>'
try:
    channel_names = json.loads(channel_names_json) if channel_names_json else {}
except:
    channel_names = {}

def get_channel_name(channel_id):
    """Get custom channel name with channel reference, or default name."""
    custom_name = channel_names.get(str(channel_id), None)
    if custom_name:
        if len(custom_name) > 30:
            custom_name = custom_name[:30] + "..."
        return f"{custom_name} (Ch{channel_id + 1})"
    return f"Channel {channel_id + 1}"

# ============================================================================
# STEP 1: Read spectroscopy metadata (no curve data)
# ============================================================================
print("=" * 70)
print("SPECTROSCOPY FILE METADATA")
print("=" * 70)

with open(spectroscopy_file_path, "rb") as f:
    # first 4 bytes must be SP01
    # 'SP01' is an identifier for spectroscopy bin files
    if f.read(4) != b"SP01":
        print("Invalid data file")
        exit(0)

    # read metadata from file
    (json_length,) = struct.unpack("I", f.read(4))
    null = None
    metadata = eval(f.read(json_length).decode("utf-8"))

    # ENABLED CHANNELS
    if "channels" in metadata and metadata["channels"] is not None:
        print(
            "Enabled channels: "
            + (", ".join(["Channel " + str(ch + 1) for ch in metadata["channels"]]))
        )
    # BIN WIDTH (us)
    if "bin_width_micros" in metadata and metadata["bin_width_micros"] is not None:
        print("Bin width: " + str(metadata["bin_width_micros"]) + "us")
    # ACQUISITION TIME (duration of the acquisition)
    if (
        "acquisition_time_millis" in metadata
        and metadata["acquisition_time_millis"] is not None
    ):
        print(
            "Acquisition time: " + str(metadata["acquisition_time_millis"] / 1000) + "s"
        )
    # LASER PERIOD (ns)
    if "laser_period_ns" in metadata and metadata["laser_period_ns"] is not None:
        laser_period_ns = metadata["laser_period_ns"]
        print("Laser period: " + str(laser_period_ns) + "ns")
    else:
        print("Laser period not found in metadata.")
        laser_period_ns = None
    # TAU (ns)
    if "tau_ns" in metadata and metadata["tau_ns"] is not None:
        print("Tau: " + str(metadata["tau_ns"]) + "ns")

print()

# ============================================================================
# STEP 2: Read fitting results from JSON
# ============================================================================
print("=" * 70)
print("FITTING RESULTS METADATA")
print("=" * 70)

with open(fitting_file_path, "r") as f:
    fitting_results = json.load(f)

if not fitting_results:
    print("No fitting results found in JSON file.")
    exit(0)

# Check deconvolution status (from first result)
uses_deconvolution = fitting_results[0].get("use_deconvolution", False)
print(f"Deconvolution: {'YES' if uses_deconvolution else 'NO'}")

if uses_deconvolution:
    # Print IRF information
    irf_tau_ns = fitting_results[0].get("irf_tau_ns", None)
    if irf_tau_ns is not None:
        print(f"IRF tau (reference): {irf_tau_ns} ns")
    irf_laser_period = fitting_results[0].get("laser_period_ns", None)
    if irf_laser_period is not None:
        print(f"IRF laser period: {irf_laser_period} ns")

print(f"Channels fitted: {len(fitting_results)}")
print()

# ============================================================================
# STEP 3: Plot fitting results
# ============================================================================
num_plots = len(fitting_results)
plots_per_row = 4
num_rows = int(np.ceil(num_plots / plots_per_row))

fig = plt.figure(figsize=(5 * plots_per_row, 5 * num_rows + 2))
gs = fig.add_gridspec(
    num_rows * 2, plots_per_row, height_ratios=[3] * num_rows + [1] * num_rows
)

axes = np.array(
    [
        [fig.add_subplot(gs[2 * row, col]) for col in range(plots_per_row)]
        for row in range(num_rows)
    ]
)
residual_axes = np.array(
    [
        [fig.add_subplot(gs[2 * row + 1, col]) for col in range(plots_per_row)]
        for row in range(num_rows)
    ]
)

for i, result in enumerate(fitting_results):
    row = i // plots_per_row
    col = i % plots_per_row

    # Extract data from JSON
    x_values = np.array(result["x_values"])
    t_data = np.array(result["t_data"])
    y_data = np.array(result["y_data"])
    fitted_values = np.array(result["fitted_values"])
    residuals = np.array(result["residuals"])
    scale_factor = result["scale_factor"]
    decay_start = result["decay_start"]
    channel = result["channel"]
    fitted_params_text = result["fitted_params_text"]

    # Scale data back to counts
    truncated_x_values = x_values[decay_start:]
    counts_y_data = y_data * scale_factor
    fitted_y_data = fitted_values * scale_factor

    # Main plot: Counts vs Fitted curve
    h1 = axes[row, col].scatter(
        truncated_x_values, counts_y_data, label="Deconv Counts", color="lime", s=1
    )
    h2 = axes[row, col].plot(
        t_data, fitted_y_data, label="Fitted curve", color="red", linewidth=2
    )[0]
    
    # Collect handles and labels for legend
    handles = [h1, h2]
    if uses_deconvolution:
        labels = ["Deconv Counts", "Fitted curve"]
    else:
        labels = ["Counts", "Fitted curve"]
    
    # If deconvolution was used, also plot raw signal and IRF
    if uses_deconvolution and "raw_signal" in result:
        raw_signal = np.array(result["raw_signal"])
        h3 = axes[row, col].scatter(
            x_values, raw_signal, label="Raw signal", color="cyan", s=1, alpha=0.5
        )
        handles.append(h3)
        labels.append("Raw signal")
        
        # Plot IRF on same axis (normalized to be visible)
        if "irf_reference" in result:
            irf_reference = np.array(result["irf_reference"])
            irf_max = np.max(irf_reference)
            if irf_max > 0:
                # Normalize IRF to same scale as counts
                irf_normalized = irf_reference / irf_max * np.max(counts_y_data) * 0.8
                h4 = axes[row, col].plot(x_values, irf_normalized, label="IRF", color="orange", 
                        linewidth=2, linestyle="--", alpha=0.9)[0]
                handles.append(h4)
                labels.append("IRF")

    axes[row, col].set_xlabel("Time (ns)", color="white")
    axes[row, col].set_ylabel("Counts", color="white")
    
    # Add deconvolution status to title
    deconv_status = " (Deconv = True)" if uses_deconvolution else " (Deconv = False)"
    axes[row, col].set_title(get_channel_name(channel) + deconv_status, color="white")
    
    # Create combined legend with all handles
    axes[row, col].legend(handles, labels, facecolor="grey", edgecolor="white", loc="upper right")
    axes[row, col].set_facecolor("black")
    axes[row, col].grid(color="white", linestyle="--", linewidth=0.5)
    axes[row, col].tick_params(colors="white")

    # Residuals plot
    residual_axes[row, col].plot(
        truncated_x_values, residuals, color="cyan", linewidth=1
    )
    residual_axes[row, col].axhline(0, color="white", linestyle="--", linewidth=0.5)
    residual_axes[row, col].set_xlabel("Time (ns)", color="white")
    residual_axes[row, col].set_ylabel("Residuals", color="white")
    residual_axes[row, col].set_facecolor("black")
    residual_axes[row, col].grid(color="white", linestyle="--", linewidth=0.5)
    residual_axes[row, col].tick_params(colors="white")

    # Display fitting parameters
    text_box_props = dict(boxstyle="round", facecolor="black", alpha=0.8)
    residual_axes[row, col].text(
        0.02,
        -0.6,
        fitted_params_text,
        transform=residual_axes[row, col].transAxes,
        fontsize=10,
        va="top",
        ha="left",
        color="white",
        bbox=text_box_props,
    )

# Hide unused subplots
for i in range(num_plots, num_rows * plots_per_row):
    row = i // plots_per_row
    col = i % plots_per_row
    axes[row, col].axis("off")
    residual_axes[row, col].axis("off")

fig.patch.set_facecolor("black")

plt.tight_layout(rect=[0, 0.1, 1, 1])
plt.show()
