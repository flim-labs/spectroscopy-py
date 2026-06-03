"""
phasors_ui.py
============================================================
UI interaction and display management functions for phasor plots.

Provides plain functions  covering: crosshair creation and mouse
tracking, cluster center drawing, legend generation and hiding, file legend
creation and removal, and the mouse-move event handler.
"""

import os

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import settings.settings as s
from core.phasors.phasors_calculations import (
    get_color_for_file_index,
    calculate_phasors_points_mean,
    calculate_tau,
)


def create_phasors_files_legend(app, channel, file_order):
    """
    Creates a legend showing the loaded files with their colors.

    Args:
        app: The main application instance.
        channel (int): The channel index.
        file_order (list): List of file names in order.
    """
    plot_item = app.phasors_widgets[channel].getPlotItem()
    existing_legend = plot_item.legend

    if existing_legend is not None:
        plot_item.removeItem(existing_legend)
        plot_item.legend = None

    if not file_order:
        return

    legend_items = []
    for idx, file_path in enumerate(file_order):
        file_name = os.path.basename(file_path) if file_path else "Unknown"
        color = get_color_for_file_index(idx)
        symbol_scatter = pg.ScatterPlotItem(
            x=[0], y=[0], size=10, pen=None, brush=pg.mkBrush(color), symbol="o"
        )
        legend_items.append((symbol_scatter, file_name))

    legend = app.phasors_widgets[channel].addLegend(
        offset=(10, 10), brush=pg.mkBrush(0, 0, 0, 180), labelTextColor="w"
    )
    for symbol, name in legend_items:
        legend.addItem(symbol, name)

    if not hasattr(app, "phasors_files_legend"):
        app.phasors_files_legend = {}
    app.phasors_files_legend[channel] = legend


def clear_phasors_files_legend(app):
    """
    Removes legends that display file information for phasor plots.

    LaserBlood: removes legends from the widget via removeItem and clears
    the dict entirely (rather than hiding with setVisible(False)).
    """
    if hasattr(app, "phasors_files_legend"):
        for channel, legend in list(app.phasors_files_legend.items()):
            if legend is None:
                continue
            if channel in app.phasors_widgets:
                try:
                    app.phasors_widgets[channel].removeItem(legend)
                except Exception:
                    pass
        app.phasors_files_legend.clear()


def clear_phasors_file_scatters(app):
    """Removes scatter items associated with file-specific phasor points."""
    if hasattr(app, "phasors_file_scatters"):
        for channel, scatter_list in list(app.phasors_file_scatters.items()):
            if channel in app.phasors_widgets:
                for scatter in scatter_list:
                    app.phasors_widgets[channel].removeItem(scatter)
        app.phasors_file_scatters.clear()


def clear_phasors_features(app, feature):
    """
    Removes a specific feature item from all relevant phasor widgets.

    Args:
        app: The main application instance.
        feature (dict): A dictionary where keys are channel indices and
                        values are the pyqtgraph items to be removed.
    """
    for ch in feature:
        if ch in app.phasors_widgets:
            item = feature[ch]
            if isinstance(item, list):
                for single_item in item:
                    app.phasors_widgets[ch].removeItem(single_item)
            else:
                app.phasors_widgets[ch].removeItem(item)


def create_phasor_crosshair(app, channel_index, phasors_widget):
    """
    Creates a crosshair text item for a phasor widget.

    Args:
        app: The main application instance.
        channel_index (int): The channel index for which to create the crosshair.
        phasors_widget (pg.PlotWidget): The widget to add the crosshair to.
    """
    crosshair = pg.TextItem("", anchor=(0.5, 0.5), color=(30, 144, 255))
    font = QFont()
    font.setPixelSize(25)
    crosshair.setFont(font)
    crosshair.setZValue(3)
    phasors_widget.addItem(crosshair, ignoreBounds=True)
    app.phasors_crosshairs[channel_index] = crosshair


def generate_coords(app, channel_index):
    """
    Sets up mouse tracking to display coordinates and crosshair on the plot.

    Connects the mouse moved signal to the event handler.

    Args:
        app: The main application instance.
        channel_index (int): The channel index to set up tracking for.
    """
    font = QFont()
    font.setPixelSize(25)
    coord_text = pg.TextItem("", anchor=(0.5, 1))
    coord_text.setFont(font)
    crosshair = pg.TextItem("", anchor=(0.5, 0.5), color=(30, 144, 255))
    font = QFont()
    font.setPixelSize(25)
    crosshair.setFont(font)
    is_in_array = len(app.phasors_crosshairs) > channel_index
    if not is_in_array:
        app.phasors_crosshairs[channel_index] = crosshair
    else:
        app.phasors_crosshairs[channel_index] = crosshair
    is_in_array = len(app.phasors_coords) > channel_index
    if not is_in_array:
        app.phasors_widgets[channel_index].sceneObj.sigMouseMoved.connect(
            lambda event, ccc=channel_index: on_phasors_mouse_moved(app, event, ccc)
        )
        app.phasors_coords[channel_index] = coord_text
    else:
        app.phasors_coords[channel_index] = coord_text
    coord_text.setZValue(10)
    crosshair.setZValue(6)
    app.phasors_widgets[channel_index].addItem(coord_text, ignoreBounds=True)
    app.phasors_widgets[channel_index].addItem(crosshair, ignoreBounds=True)


def generate_phasors_cluster_center(app, harmonic):
    """
    Calculates and draws the center of the phasor data cluster.

    The center is marked with a yellow 'x' on the plot (or blue 'x' per file
    in read mode).

    Args:
        app: The main application instance.
        harmonic (int): The harmonic number to use for the calculation.
    """
    import settings.settings as settings

    is_phasors_read_mode = (
        app.tab_selected == settings.TAB_PHASORS and app.acquire_read_mode == "read"
    )

    for i, channel_index in enumerate(app.plots_to_show):
        if channel_index not in app.phasors_widgets:
            continue

        # Remove old cluster centers
        if channel_index in app.phasors_clusters_center:
            old_centers = app.phasors_clusters_center[channel_index]
            if isinstance(old_centers, list):
                for scatter in old_centers:
                    app.phasors_widgets[channel_index].removeItem(scatter)
            else:
                app.phasors_widgets[channel_index].removeItem(old_centers)

        if is_phasors_read_mode:
            # One blue cross per file mean
            points_by_file = {}
            for point in app.all_phasors_points[channel_index][harmonic]:
                g, s = point[0], point[1]
                file_name = point[2] if len(point) >= 3 else ""
                if file_name not in points_by_file:
                    points_by_file[file_name] = {"g": [], "s": []}
                points_by_file[file_name]["g"].append(g)
                points_by_file[file_name]["s"].append(s)

            cluster_centers = []
            for file_name, coords in points_by_file.items():
                g_values = np.array(coords["g"])
                s_values = np.array(coords["s"])
                if g_values.size == 0 or s_values.size == 0:
                    continue
                if np.all(np.isnan(g_values)) or np.all(np.isnan(s_values)):
                    continue
                mean_g = np.nanmean(g_values)
                mean_s = np.nanmean(s_values)
                scatter = pg.ScatterPlotItem(
                    [mean_g],
                    [mean_s],
                    size=20,
                    pen={"color": "#0066CC", "width": 4},
                    symbol="x",
                )
                scatter.setZValue(3)
                app.phasors_widgets[channel_index].addItem(scatter)
                cluster_centers.append(scatter)
            app.phasors_clusters_center[channel_index] = cluster_centers
        else:
            mean_g, mean_s = calculate_phasors_points_mean(app, channel_index, harmonic)
            if mean_g is None or mean_s is None:
                continue
            scatter = pg.ScatterPlotItem(
                [mean_g],
                [mean_s],
                size=20,
                pen={"color": "yellow", "width": 4},
                symbol="x",
            )
            scatter.setZValue(2)
            app.phasors_widgets[channel_index].addItem(scatter)
            app.phasors_clusters_center[channel_index] = scatter


def generate_phasors_legend(app, harmonic):
    """
    Generates and displays a legend with mean G/S and calculated tau values.

    Args:
        app: The main application instance.
        harmonic (int): The harmonic number for which to calculate the values.
    """
    from core.controls_controller import ControlsController
    import settings.settings as settings

    is_phasors_read_mode = (
        app.tab_selected == settings.TAB_PHASORS and app.acquire_read_mode == "read"
    )

    for i, channel_index in enumerate(app.plots_to_show):
        if not (
            hasattr(app, "phasors_legend_labels")
            and channel_index in app.phasors_legend_labels
        ):
            continue

        legend_label = app.phasors_legend_labels[channel_index]

        if is_phasors_read_mode:
            # Multi-file mode: colored legend per file
            points_by_file = {}
            file_order = []
            for point in app.all_phasors_points[channel_index][harmonic]:
                g, s_val = point[0], point[1]
                file_name = point[2] if len(point) >= 3 else ""
                if file_name not in points_by_file:
                    points_by_file[file_name] = {"g": [], "s": []}
                    file_order.append(file_name)
                points_by_file[file_name]["g"].append(g)
                points_by_file[file_name]["s"].append(s_val)

            if not points_by_file:
                legend_label.setVisible(False)
                continue

            freq_mhz = ControlsController.get_frequency_mhz(app)
            # Fallback: try to read frequency from phasors metadata
            if freq_mhz == 0.0 and hasattr(app, "reader_data"):
                if (
                    "phasors" in app.reader_data
                    and "phasors_metadata" in app.reader_data["phasors"]
                ):
                    metadata = app.reader_data["phasors"]["phasors_metadata"]
                    if isinstance(metadata, list) and len(metadata) > 0:
                        if "laser_period_ns" in metadata[0]:
                            from utils.helpers import ns_to_mhz

                            freq_mhz = ns_to_mhz(metadata[0]["laser_period_ns"])

            html_parts = []
            for idx, file_name in enumerate(file_order):
                coords = points_by_file[file_name]
                g_values = np.array(coords["g"])
                s_values = np.array(coords["s"])
                if g_values.size == 0 or s_values.size == 0:
                    continue
                if np.all(np.isnan(g_values)) or np.all(np.isnan(s_values)):
                    continue
                mean_g = np.nanmean(g_values)
                mean_s = np.nanmean(s_values)
                color = get_color_for_file_index(idx)

                if freq_mhz != 0.0:
                    tau_phi, tau_m, tau_n = calculate_tau(
                        mean_g, mean_s, freq_mhz, harmonic
                    )
                    tau_m_display = round(tau_m, 2) if tau_m is not None else 1.0
                    file_legend = (
                        f"<span style='color: {color};'>"
                        f"G (mean)={round(mean_g, 3)}; S (mean)={round(mean_s, 3)}; "
                        f"τϕ={round(tau_phi, 2)} ns; τn={round(tau_n, 2)} ns; "
                        f"τm={tau_m_display} ns</span>"
                    )
                else:
                    file_legend = (
                        f"<span style='color: {color};'>"
                        f"G (mean)={round(mean_g, 3)}; S (mean)={round(mean_s, 3)}</span>"
                    )
                html_parts.append(file_legend)

            if html_parts:
                rows = []
                for j in range(0, len(html_parts), 2):
                    row_items = html_parts[j : j + 2]
                    row_html = " &nbsp;|&nbsp; ".join(row_items)
                    rows.append(row_html)
                legend_label.setText("<br>".join(rows))
                legend_label.setVisible(True)
            else:
                legend_label.setVisible(False)

        else:
            # Single file / acquire mode: original behavior
            mean_g, mean_s = calculate_phasors_points_mean(app, channel_index, harmonic)
            if mean_g is None or mean_s is None:
                legend_label.setVisible(False)
                continue

            freq_mhz = ControlsController.get_frequency_mhz(app)
            tau_phi, tau_m, tau_n = calculate_tau(mean_g, mean_s, freq_mhz, harmonic)
            if tau_phi is None:
                legend_label.setVisible(False)
                continue

            if tau_m is None:
                legend_text = (
                    f"G (mean)={round(mean_g, 3)}; "
                    f"S (mean)={round(mean_s, 3)}; "
                    f"𝜏ϕ={round(tau_phi, 2)} ns; "
                    f"𝜏n={round(tau_n, 2)} ns"
                )
            else:
                legend_text = (
                    f"G (mean)={round(mean_g, 3)}; "
                    f"S (mean)={round(mean_s, 3)}; "
                    f"𝜏ϕ={round(tau_phi, 2)} ns; "
                    f"𝜏n={round(tau_n, 2)} ns; "
                    f"𝜏m={round(tau_m, 2)} ns"
                )
            legend_label.setText(legend_text)
            legend_label.setVisible(True)


def hide_phasors_legends(app):
    """
    Hides all phasor legends (both fixed labels and plot-based legends).

    Args:
        app: The main application instance.
    """
    if hasattr(app, "phasors_legend_labels"):
        for channel_index, legend_label in app.phasors_legend_labels.items():
            legend_label.setText("")
            legend_label.setVisible(False)

    for channel_index in app.phasors_legends:
        if channel_index in app.phasors_widgets:
            app.phasors_widgets[channel_index].removeItem(
                app.phasors_legends[channel_index]
            )
    app.phasors_legends.clear()


def on_phasors_mouse_moved(app, event, channel_index):
    """
    Event handler for mouse movement over a phasor plot.

    Updates the crosshair position and displays the calculated lifetime values
    at the cursor's location.

    Args:
        app: The main application instance.
        event: The mouse move event from PyQt.
        channel_index (int): The index of the channel where the event occurred.
    """
    from core.controls_controller import ControlsController

    for i, channel in enumerate(app.phasors_coords):
        if channel != channel_index:
            app.phasors_coords[channel].setText("")
            app.phasors_crosshairs[channel].setText("")
    try:
        phasor_widget = app.phasors_widgets[channel_index]
        text = app.phasors_coords[channel_index]
        crosshair = app.phasors_crosshairs[channel_index]
    except Exception:
        return
    mouse_point = phasor_widget.plotItem.vb.mapSceneToView(event)
    crosshair.setPos(mouse_point.x(), mouse_point.y())
    crosshair.setText(s.CURSOR_TEXT)
    text.setPos(mouse_point.x(), mouse_point.y())
    freq_mhz = ControlsController.get_current_frequency_mhz(app)
    harmonic = int(app.control_inputs[s.HARMONIC_SELECTOR].currentText())
    g = mouse_point.x()
    s_coord = mouse_point.y()
    tau_phi, tau_m, tau_n = calculate_tau(g, s_coord, freq_mhz, harmonic)
    if tau_phi is None:
        return
    if tau_m is None:
        text.setText(f"𝜏ϕ={round(tau_phi, 2)} ns; 𝜏n={round(tau_n, 2)} ns")
        text.setHtml(
            '<div style="background-color: rgba(0, 0, 0, 0.5);">{}</div>'.format(
                f"𝜏ϕ={round(tau_phi, 2)} ns; 𝜏n={round(tau_n, 2)} ns"
            )
        )
    else:
        text.setText(
            f"𝜏ϕ={round(tau_phi, 2)} ns; 𝜏m={round(tau_m, 2)} ns; 𝜏n={round(tau_n, 2)} ns"
        )
        text.setHtml(
            '<div style="background-color: rgba(0, 0, 0, 0.5);">{}</div>'.format(
                f"𝜏ϕ={round(tau_phi, 2)} ns; 𝜏n={round(tau_n, 2)} ns; 𝜏m={round(tau_m, 2)} ns"
            )
        )
