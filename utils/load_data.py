import json
import struct
import os
import matplotlib.pyplot as plt
import numpy as np

from utils.helpers import ns_to_mhz


def extract_metadata(file_path, magic_number):
    """Extracts JSON metadata from the header of a binary data file.

    Args:
        file_path (str): The path to the binary file.
        magic_number (bytes): The expected 4-byte magic number at the start of the file.

    Returns:
        dict: The parsed metadata from the file header.
    """
    with open(file_path, "rb") as f:
        assert f.read(4) == magic_number
        header_length = int.from_bytes(f.read(4), byteorder="little")
        header = f.read(header_length)
        metadata = json.loads(header)
    return metadata


def load_data(file_path, selected_channels):
    """Loads and aggregates spectroscopy data from a binary file.

    Args:
        file_path (str): The path to the spectroscopy data file (format SP01).
        selected_channels (list): A list of channel indices to load. Note: This is currently
                                  overridden by the channels specified in the file's metadata.

    Returns:
        dict: A dictionary where keys are channel indices and values are the summed decay curves.
    """
    data = {}
    with open(file_path, "rb") as f:
        assert f.read(4) == b"SP01"
        header_length = int.from_bytes(f.read(4), byteorder="little")
        header = f.read(header_length)
        metadata = json.loads(header)
        selected_channels = metadata["channels"]
        while True:
            time_ns = f.read(8)
            if not time_ns:
                break
            for channel in selected_channels:
                current_curve = [
                    int.from_bytes(f.read(4), byteorder="little") for _ in range(256)
                ]
                data[channel] = data.get(channel, [0 for _ in range(256)])
                data[channel] = [sum(x) for x in zip(data[channel], current_curve)]
    return data


def load_phasors(file_path, selected_channels):
    """Loads phasor data from a binary file.

    Args:
        file_path (str): The path to the phasor data file (format SPF1).
        selected_channels (list): A list of channel indices to load data for.

    Returns:
        dict: A nested dictionary of phasor data: {channel: {harmonic: [(g, s), ...]}}.
    """
    data = {}
    with open(file_path, "rb") as f:
        assert f.read(4) == b"SPF1"
        header_length = int.from_bytes(f.read(4), byteorder="little")
        header = f.read(header_length)
        metadata = json.loads(header)
        while True:
            for channel in selected_channels:
                if channel not in data:
                    data[channel] = {}

                for harmonic in range(1, metadata["harmonics"] + 1):
                    if harmonic not in data[channel]:
                        data[channel][harmonic] = []

                    bytes_read = f.read(32)
                    if not bytes_read:
                        return data  # Exit the function if no more data

                    # Unpack the read bytes
                    try:
                        time_ns, channel_name, harmonic_name, g, s = struct.unpack(
                            "QIIdd", bytes_read
                        )
                    except struct.error as e:
                        return data

                    data[channel][harmonic].append((g, s))
    return data


def plot_phasors(data):
    """Generates and displays a simple plot of phasor data.

    Args:
        data (dict): A nested dictionary of phasor data from load_phasors.
    """
    fig, ax = plt.subplots()

    harmonic_colors = plt.cm.viridis(
        np.linspace(0, 1, max(h for ch in data.values() for h in ch.keys()))
    )
    harmonic_colors_dict = {
        harmonic: color for harmonic, color in enumerate(harmonic_colors, 1)
    }

    for channel, harmonics in data.items():
        theta = np.linspace(0, np.pi, 100)
        x = np.cos(theta)
        y = np.sin(theta)

        # Plot semi-circle for the channel
        ax.plot(x, y, label=f"Channel: {channel}")

        for harmonic, values in harmonics.items():
            if values:  # Ensure there are values to plot
                g_values, s_values = zip(*values)

                # Filter out extreme values to prevent overflow
                g_values = np.array(g_values)
                s_values = np.array(s_values)
                mask = (np.abs(g_values) < 1e9) & (np.abs(s_values) < 1e9)
                g_values = g_values[mask]
                s_values = s_values[mask]

                ax.scatter(
                    g_values,
                    s_values,
                    label=f"Channel: {channel} Harmonic: {harmonic}",
                    color=harmonic_colors_dict[harmonic],
                )
    ax.set_aspect("equal")
    ax.legend()
    plt.title("Phasors Plot")
    plt.xlabel("G")
    plt.ylabel("S")
    plt.grid(True)
    plt.show()


def plot_phasors_data(
    phasors_data,
    laser_period,
    active_channels,
    spectroscopy_times,
    spectroscopy_curves,
    selected_harmonic,
    show_plot=True,
    per_file_spectroscopy=False,
    spectroscopy_files_info=None,
    show_file_legend=True,
):
    """Creates a comprehensive plot showing both spectroscopy and phasor data.

    Args:
        phasors_data (dict): The phasor data.
        laser_period (float): The laser period in nanoseconds.
        active_channels (list): List of active channel indices.
        spectroscopy_times (list): List of timestamps for spectroscopy curves.
        spectroscopy_curves (list): List of spectroscopy decay curves.
        selected_harmonic (int): The specific harmonic to plot in the phasor plots.
        show_plot (bool, optional): If True, displays the plot. Defaults to True.

    Returns:
        matplotlib.figure.Figure: The generated figure object.
    """
    # plot layout config
    num_channels = len(phasors_data)
    max_channels_per_row = 3
    ncol = 3 if num_channels > 2 else num_channels
    nrow = int(np.ceil(num_channels / ncol))
    # Make figure slightly larger to improve readability
    fig, axs = plt.subplots(nrow + 1, ncol, figsize=(24, (nrow + 1) * 7), squeeze=False)
    # Spectroscopy plot (support per-file spectroscopy export)
    num_bins = 256
    x_values = np.linspace(0, laser_period if laser_period else 1, num_bins)
    ax = axs[0, 0]
    
    # Set title based on mode
    if per_file_spectroscopy and spectroscopy_files_info:
        ax.set_title("Spectroscopy")
    else:
        # Prepare title/metadata safely (spectroscopy_times may be None for per-file mode)
        try:
            time_info = f"time: {str(round(spectroscopy_times[-1]))}s, curves stored: {str(len(spectroscopy_times))}"
        except Exception:
            time_info = "time: N/A, curves stored: N/A"
        ax.set_title(f"Spectroscopy ({time_info})")
    ax.set_xlabel(f"Time (ns, Laser period = {laser_period} ns)")
    ax.set_ylabel("Intensity")
    ax.set_yscale("log")
    ax.grid(True)
    total_max = 0
    total_min = float("inf")

    if per_file_spectroscopy and spectroscopy_files_info:
        # Plot one summed curve per file (use first matching active channel per file)
        # Try to reuse app palette (PhasorsController) for consistent colors, fallback to tab10
        try:
            from core.phasors_controller import PhasorsController

            def _spec_file_color(idx):
                return PhasorsController.get_color_for_file_index(idx)

            spec_colors = [_spec_file_color(i) for i in range(len(spectroscopy_files_info))]
        except Exception:
            spec_colors = plt.cm.tab10(np.linspace(0, 1, max(1, len(spectroscopy_files_info))))

        for file_idx, file_info in enumerate(spectroscopy_files_info):
            file_name = os.path.basename(file_info.get("file_path", f"file{file_idx}"))
            file_channels = file_info.get("channels_curves", {})
            plotted = False
            for ch in active_channels:
                if ch in file_channels:
                    ch_curves = file_channels[ch]
                    if len(ch_curves) == 0:
                        continue
                    sum_curve = np.sum(ch_curves, axis=0)
                    total_max = max(total_max, np.max(sum_curve))
                    total_min = min(total_min, np.min(sum_curve))
                    color = spec_colors[file_idx % len(spec_colors)]
                    ax.plot(x_values, sum_curve, label=f"{file_name}", color=color)
                    plotted = True
                    break
            if not plotted:
                # If no active channel found in this file, skip plotting
                continue

        # Legend will be created at figure level after all plotting is complete
        # to avoid overlapping with the spectroscopy title
    else:
        # Legacy aggregated behaviour (one curve per active channel)
        for i in range(len(active_channels)):
            if i >= len(spectroscopy_curves):
                continue
            sum_curve = np.sum(spectroscopy_curves[i], axis=0)
            max_val = np.max(sum_curve)
            min_val = np.min(sum_curve)
            if max_val > total_max:
                total_max = max_val
            if min_val < total_min:
                total_min = min_val
            ax.plot(x_values, sum_curve, label=f"Channel {active_channels[i] + 1}")
        # Legend will be created at figure level after all plotting is complete

    if total_min == float("inf") or total_max == 0:
        total_min = 1
        total_max = 1
    ax.set_ylim(total_min * 0.99, total_max * 1.01)
    ax.set_xlim(0, laser_period if laser_period else max(x_values))
    # Phasors plots
    # I plot phasors partono dalla seconda riga (row=1), la prima è la spectroscopy (row=0)
    for i, (channel, harmonics) in enumerate(phasors_data.items()):
        row = (i // ncol) + 1  # +1 per saltare la riga spectroscopy
        col = i % ncol
        ax = axs[row, col]
        x = np.linspace(0, 1, 1000)
        y = np.sqrt(0.5**2 - (x - 0.5) ** 2)
        ax.plot(x, y)
        ax.set_aspect('equal') 
        # Plot only the selected harmonic
        for harmonic, values in harmonics.items():
            if selected_harmonic is not None and harmonic != selected_harmonic:
                continue  # Skip non-selected harmonics
            if values:
                # values can be (g, s) or (g, s, file_name)
                entries = []
                for v in values:
                    try:
                        g_val = v[0]
                        s_val = v[1]
                        file_val = v[2] if len(v) > 2 else None
                    except Exception:
                        # unexpected shape, skip
                        continue
                    entries.append((g_val, s_val, file_val))

                # group points by file name (basename). Use a fallback key for points without file info
                groups = {}
                for g_val, s_val, f_val in entries:
                    key = os.path.basename(str(f_val)) if f_val else "__combined__"
                    groups.setdefault(key, []).append((g_val, s_val))

                # prepare colors for files using the same palette as the app if available
                try:
                    from core.phasors_controller import PhasorsController

                    def _file_color(idx):
                        return PhasorsController.get_color_for_file_index(idx)

                    color_map = [_file_color(i) for i in range(max(1, len(groups)))]
                except Exception:
                    color_map = plt.cm.tab10(np.linspace(0, 1, max(1, len(groups))))

                # collect all g/s for computing overall mean and per-group means
                all_g = []
                all_s = []
                mean_handles = []
                mean_labels = []
                from matplotlib.lines import Line2D
                for idx, (fname, pts) in enumerate(groups.items()):
                    g_vals = np.array([p[0] for p in pts])
                    s_vals = np.array([p[1] for p in pts])
                    mask = (np.abs(g_vals) < 1e9) & (np.abs(s_vals) < 1e9)
                    g_vals = g_vals[mask]
                    s_vals = s_vals[mask]
                    if g_vals.size == 0:
                        continue
                    all_g.extend(g_vals.tolist())
                    all_s.extend(s_vals.tolist())
                    if fname == "__combined__":
                        label = f"Harmonic: {harmonic}"
                        color = "#00FFFF"
                    else:
                        label = fname
                        color = color_map[idx % len(color_map)]
                    ax.scatter(
                        g_vals,
                        s_vals,
                        label=label,
                        zorder=2,
                        color=color,
                        alpha=0.8,
                    )
                    # Per-group mean
                    mean_g = np.mean(g_vals)
                    mean_s = np.mean(s_vals)
                    freq_mhz = ns_to_mhz(laser_period)
                    tau_phi = (
                        (1 / (2 * np.pi * freq_mhz * harmonic)) * (mean_s / mean_g) * 1e3
                    )
                    tau_m_component = (1 / (mean_s**2 + mean_g**2)) - 1
                    tau_m = (
                        (
                            (1 / (2 * np.pi * freq_mhz * harmonic))
                            * np.sqrt(tau_m_component)
                            * 1e3
                        )
                        if tau_m_component >= 0
                        else None
                    )
                    mean_label = f"G (mean): {round(mean_g, 2)}; S (mean): {round(mean_s, 2)}; τϕ={round(tau_phi, 2)} ns"
                    if tau_m is not None:
                        mean_label += f"; τm={round(tau_m, 2)} ns"
                    ax.scatter(
                        mean_g,
                        mean_s,
                        color="#0066CC",
                        marker="x",
                        s=100,
                        zorder=3
                    )
                    mean_handles.append(Line2D(
                        [],
                        [],
                        color=color,
                        marker="x",
                        linestyle="None",
                        markersize=8,
                        label=mean_label,
                    ))
                    mean_labels.append(mean_label)

                color_handles, color_labels = ax.get_legend_handles_labels()
                n_labels = len(color_labels)
                if n_labels == 3:
                    ncol = 2
                elif n_labels >= 4:
                    ncol = min(3, n_labels // 2)
                else:
                    ncol = n_labels
                color_legend = ax.legend(
                    color_handles,
                    color_labels,
                    loc="upper center",
                    bbox_to_anchor=(0.5, -0.18),
                    ncol=ncol,
                    fontsize="small"
                )
                ax.add_artist(color_legend)

                # Second legend for means below the first
                if mean_handles:
                    n_mean_labels = len(mean_labels)
                    if n_mean_labels <= 2:
                        ncol_mean = n_mean_labels
                    else:
                        ncol_mean = 2
                    mean_legend = ax.legend(
                        mean_handles,
                        mean_labels,
                        loc="upper center",
                        bbox_to_anchor=(0.5, -0.35),
                        ncol=ncol_mean,
                        fontsize="small"
                    )
                    ax.add_artist(mean_legend)

        ax.set_title(f"Phasor (harmonic {selected_harmonic})")
        ax.set_xlabel("G")
        ax.set_ylabel("S")
        ax.grid(True)
    axs_flat = axs.flatten()
    for i in range(num_channels + 1, (nrow + 1) * ncol):
        if i < len(axs_flat):
            axs_flat[i].axis("off")
    
    # Use a more aggressive approach to ensure complete removal
    legends_removed = 0
    while fig.legends:
        fig.legends[0].remove()
        legends_removed += 1
    
    # Clear the figure's legend list completely
    fig.legends.clear()
    
    if show_file_legend and per_file_spectroscopy and spectroscopy_files_info:
        from matplotlib.lines import Line2D
        legend_handles = []
        
        for idx, file_info in enumerate(spectroscopy_files_info):
            file_name = os.path.basename(file_info.get("file_path", f"file{idx}"))
            
            # Calculate time and curves info
            times = file_info.get("times", [])
            channels_curves = file_info.get("channels_curves", {})
            
            # Calculate total curves and time
            total_curves = 0
            for ch_curves in channels_curves.values():
                if isinstance(ch_curves, (list, np.ndarray)):
                    total_curves += len(ch_curves)
            
            time_s = round(times[-1], 2) if times and len(times) > 0 else 0
            
            # Format file name with metadata
            if time_s > 0 or total_curves > 0:
                file_label = f"{file_name} (time: {time_s}s, curves: {total_curves})"
            else:
                file_label = file_name
            
            # Get consistent colors from the app if available, fallback to matplotlib colors
            try:
                from core.phasors_controller import PhasorsController
                color = PhasorsController.get_color_for_file_index(idx)
            except Exception:
                color = plt.cm.tab10(idx / max(1, len(spectroscopy_files_info) - 1))
            
            legend_handles.append(Line2D([], [], color=color, linewidth=3, label=file_label))
        
        new_legend = fig.legend(
            handles=legend_handles,
            loc="upper center", 
            bbox_to_anchor=(0.5, 0.98),
            ncol=2,
            fontsize=10,
            frameon=True,
            edgecolor="black",
            framealpha=0.9
        )
    if show_plot:
        plt.show()
    return fig


def plot_spectroscopy_data(channel_curves, times, metadata, show_plot=True):
    """Generates and displays a plot of summed spectroscopy decay curves.

    Args:
        channel_curves (list): A list of lists, where each inner list contains decay curves for a channel.
        times (list): A list of timestamps for the acquisitions.
        metadata (dict): Metadata dictionary containing 'laser_period_ns' and 'channels'.
        show_plot (bool, optional): If True, displays the plot. Defaults to True.

    Returns:
        matplotlib.figure.Figure: The generated figure object.
    """
    fig, ax = plt.subplots()
    ax.set_xlabel(f"Time (ns, Laser period = {metadata['laser_period_ns']} ns)")
    ax.set_ylabel("Intensity")
    ax.set_yscale("log")
    ax.set_title(
        "Spectroscopy (time: "
        + str(round(times[-1]))
        + "s, curves stored: "
        + str(len(times))
        + ")"
    )
    num_bins = 256
    x_values = np.linspace(0, metadata["laser_period_ns"], num_bins)
    # plot all channels summed up
    total_max = 0
    total_min = float("inf")
    for i in range(len(channel_curves)):
        sum_curve = np.sum(channel_curves[i], axis=0)
        max_value = np.max(sum_curve)
        min_value = np.min(sum_curve)
        if max_value > total_max:
            total_max = max_value
        if min_value < total_min:
            total_min = min_value
        ax.plot(x_values, sum_curve, label=f"Channel {metadata['channels'][i] + 1}")
        ax.legend()
    ax.set_ylim(total_min * 0.99, total_max * 1.01)
    ax.set_xlim(0, metadata["laser_period_ns"])
    fig.tight_layout()
    if show_plot:
        plt.show()
    return fig


def plot_fitting_data_multifile(valid_results, show_plot=True):
    """Generates a single comparison plot for multi-file fitting results."""
    
    # Color palette for different files
    file_colors = ['#f72828', '#00FF00', '#FFA500', '#FF00FF']
    
    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 0.8], hspace=0.3)
    ax_main = fig.add_subplot(gs[0])
    ax_residuals = fig.add_subplot(gs[1])
    ax_params = fig.add_subplot(gs[2])
    ax_params.axis('off')
    
    # Add generic legend entries first (Counts and Fitted curve)
    ax_main.scatter([], [], color='gray', s=30, alpha=0.7, label='Counts')
    ax_main.plot([], [], color='gray', linewidth=2, label='Fitted curve')
    
    # Plot each file with its color
    for idx, result in enumerate(valid_results):
        file_index = result.get('file_index', 0)
        file_name = result.get('file_name', f'File {file_index + 1}')
        color = file_colors[file_index % len(file_colors)]
        
        truncated_x_values = result["x_values"][result["decay_start"]:]
        counts_y_data = np.array(result["y_data"]) * result["scale_factor"]
        fitted_y_data = np.array(result["fitted_values"]) * result["scale_factor"]
        
        # Apply jitter for overlapping points
        num_files = len(valid_results)
        x_range = np.max(truncated_x_values) - np.min(truncated_x_values)
        jitter_amount = 0.003 * x_range
        offset_x = (file_index - (num_files - 1) / 2) * jitter_amount
        
        # Ensure same length
        min_len = min(len(truncated_x_values), len(counts_y_data), len(result["t_data"]), len(fitted_y_data))
        truncated_x_values = truncated_x_values[:min_len]
        counts_y_data = counts_y_data[:min_len]
        t_data = result["t_data"][:min_len]
        fitted_y_data = fitted_y_data[:min_len]
        
        # Plot counts and fitted curve (no label here, to avoid duplication)
        ax_main.scatter(truncated_x_values + offset_x, counts_y_data, 
                       color=color, s=4, alpha=0.7)
        ax_main.plot(t_data, fitted_y_data, color=color, linewidth=2)
        
        # Add colored rectangle for file name in legend
        ax_main.plot([], [], color=color, linewidth=10, label=file_name)
        
        # Plot residuals
        residuals = result["residuals"][:min_len]
        ax_residuals.plot(truncated_x_values + offset_x, residuals, 
                         color=color, linewidth=2)
    
    # Style main plot
    ax_main.set_xlabel("Time (ns)")
    ax_main.set_ylabel("Counts")
    ax_main.set_title("Multi-File Comparison")
    ax_main.legend(fontsize=9, loc='upper right')
    ax_main.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    
    # Style residuals plot
    ax_residuals.axhline(0, color='black', linestyle='--', linewidth=1)
    ax_residuals.set_xlabel("Time (ns)")
    ax_residuals.set_ylabel("Residuals")
    ax_residuals.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    
    # Add fitting parameters in columns at the bottom
    num_files = len(valid_results)
    col_width = 1.0 / num_files
    
    for idx, result in enumerate(valid_results):
        file_index = result.get('file_index', 0)
        file_name = result.get('file_name', f'File {file_index + 1}')
        color = file_colors[file_index % len(file_colors)]
        params = result.get('fitted_params_text', '').strip()
        # Remove "Fitted parameters:\n" prefix if present to avoid duplication
        params = params.replace("Fitted parameters:\n", "", 1)
        
        # Position for this column using full horizontal space
        x_pos = idx * col_width + 0.01
        
        # Add colored rectangle indicator
        rect = plt.Rectangle((x_pos - 0.008, 0.92), 0.005, 0.06, 
                            transform=ax_params.transAxes, 
                            facecolor=color, edgecolor='none', clip_on=False)
        ax_params.add_patch(rect)
        
        # Add text in default color (black) - show all parameters with label
        ax_params.text(x_pos, 0.95, "Fitted parameters:\n" + params, fontsize=8, verticalalignment='top',
                      fontfamily='monospace', color='black')
    
    if show_plot:
        plt.show()
    return fig


def plot_fitting_data(data, show_plot=True):
    """Generates and displays plots for curve fitting results.

    Creates a grid of plots, each showing the original data, the fitted curve,
    and a separate subplot for the residuals.

    Args:
        data (list): A list of dictionaries, where each dictionary contains the
                     results of a single fit from `fitting_utilities.fit_decay_curve`.
        show_plot (bool, optional): If True, displays the plot. Defaults to True.

    Returns:
        matplotlib.figure.Figure: The generated figure object.
    """
    valid_results = []
    for d in data:
        if "error" in d:
            continue
        valid_results.append(d)
    
    if not valid_results:
        return None
    
    # Check if this is multi-file mode (multiple files loaded)
    has_file_index = 'file_index' in valid_results[0]
    if has_file_index:
        # Multi-file comparison mode - single plot
        return plot_fitting_data_multifile(valid_results, show_plot)
    
    # Single file mode - grid of plots per channel
    num_plots = len(valid_results)
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
    for i, result in enumerate(valid_results):
        row = i // plots_per_row
        col = i % plots_per_row

        truncated_x_values = result["x_values"][result["decay_start"] :]
        counts_y_data = np.array(result["y_data"]) * result["scale_factor"]
        fitted_y_data = np.array(result["fitted_values"]) * result["scale_factor"]

        # Ensure all arrays have the same length
        min_len = min(len(truncated_x_values), len(counts_y_data), len(result["t_data"]), len(fitted_y_data))
        truncated_x_values = truncated_x_values[:min_len]
        counts_y_data = counts_y_data[:min_len]
        t_data = result["t_data"][:min_len]
        fitted_y_data = fitted_y_data[:min_len]

        axes[row, col].scatter(
            truncated_x_values, counts_y_data, label="Counts", color="green", s=2
        )
        axes[row, col].plot(
            t_data, fitted_y_data, label="Fitted curve", color="red"
        )
        axes[row, col].set_xlabel("Time")
        axes[row, col].set_ylabel("Counts")
        axes[row, col].set_title(f"Channel {result['channel'] + 1}")
        axes[row, col].legend(edgecolor="white")
        axes[row, col].grid( linestyle="--", linewidth=0.5)
        axes[row, col].tick_params()

        residuals = result["residuals"]
        min_len_res = min(len(truncated_x_values), len(residuals))
        residual_axes[row, col].plot(
            truncated_x_values[:min_len_res], residuals[:min_len_res], color="blue", linewidth=1
        )
        residual_axes[row, col].axhline(0, linestyle="--", linewidth=0.5)
        residual_axes[row, col].set_xlabel("Time")
        residual_axes[row, col].set_ylabel("Residuals")
        residual_axes[row, col].grid( linestyle="--", linewidth=0.5)
        residual_axes[row, col].tick_params()

        # Remove "Fitted parameters:\n" prefix if present to avoid duplication
        params_text = result["fitted_params_text"].replace("Fitted parameters:\n", "", 1)
        text_box_props = dict(boxstyle="round",  facecolor="white", alpha=0.8)
        residual_axes[row, col].text(
            0.02,
            -0.6,
            "Fitted parameters:\n" + params_text,
            transform=residual_axes[row, col].transAxes,
            fontsize=10,
            va="top",
            ha="left",
            bbox=text_box_props,
        )
    for i in range(num_plots, num_rows * plots_per_row):
        row = i // plots_per_row
        col = i % plots_per_row
        axes[row, col].axis("off")
        residual_axes[row, col].axis("off")
  

    plt.tight_layout(rect=[0, 0.1, 1, 1])        
    if show_plot:
        plt.show()
    return fig
