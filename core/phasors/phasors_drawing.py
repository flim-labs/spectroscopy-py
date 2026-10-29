"""
phasors_drawing.py
============================================================
Pyqtgraph drawing functions for phasor plot elements.

Provides plain functions  that render visual elements onto
phasor PlotWidgets: the universal semi-circle, phasor data points
(with per-file coloring in read mode), lifetime reference markers,
density quantization images, and the associated colorbar.
"""

import numpy as np
import pyqtgraph as pg

from core.phasors.phasors_calculations import get_color_for_file_index


def draw_semi_circle(widget):
    """
    Draws the universal semi-circle on a given phasor plot widget.

    Args:
        widget (pg.PlotWidget): The pyqtgraph widget to draw on.
    """
    x = np.linspace(0, 1, 1000)
    y = np.sqrt(0.5**2 - (x - 0.5) ** 2)
    widget.plot(x, y, pen=pg.mkPen(color="#1E90FF", width=2))
    widget.plot([-0.1, 1.1], [0, 0], pen=pg.mkPen(color="#1E90FF", width=2))


def draw_points_in_phasors(app, channel, harmonic, phasors):
    """
    Draws a set of phasor points on the specified channel's plot.
    Points are colored based on their source file when in phasors read mode.

    Args:
        app: The main application instance.
        channel (int): The channel index to draw the points on.
        harmonic (int): The harmonic number of the phasor points.
        phasors (list[tuple]): A list of (g, s) or (g, s, file_name) tuples to plot.
    """
    if channel not in app.plots_to_show:
        return

    import settings.settings as settings
    from core.phasors.phasors_ui import create_phasors_files_legend

    is_phasors_read_mode = (
        app.tab_selected == settings.TAB_PHASORS and app.acquire_read_mode == "read"
    )

    if is_phasors_read_mode:
        # Clear existing scatter plots for this channel before adding new ones
        if (
            hasattr(app, "phasors_file_scatters")
            and channel in app.phasors_file_scatters
        ):
            for scatter in app.phasors_file_scatters[channel]:
                app.phasors_widgets[channel].removeItem(scatter)
            app.phasors_file_scatters[channel] = []

        # Group points by file name, preserving insertion order
        points_by_file = {}
        file_order = []
        for point in phasors:
            g, s = point[0], point[1]
            file_name = point[2] if len(point) >= 3 else ""
            if file_name not in points_by_file:
                points_by_file[file_name] = {"x": [], "y": []}
                file_order.append(file_name)
            points_by_file[file_name]["x"].append(g)
            points_by_file[file_name]["y"].append(s)

        # Draw each file's points with its own color based on insertion order
        for idx, file_name in enumerate(file_order):
            coords = points_by_file[file_name]
            color = get_color_for_file_index(idx)
            x_array = np.array(coords["x"])
            y_array = np.array(coords["y"])

            scatter = pg.ScatterPlotItem(
                x=x_array,
                y=y_array,
                size=5,
                pen=None,
                brush=pg.mkBrush(color),
                symbol="o",
            )
            scatter.setZValue(1)
            app.phasors_widgets[channel].addItem(scatter)

            # Store reference for potential cleanup
            if not hasattr(app, "phasors_file_scatters"):
                app.phasors_file_scatters = {}
            if channel not in app.phasors_file_scatters:
                app.phasors_file_scatters[channel] = []
            app.phasors_file_scatters[channel].append(scatter)

        create_phasors_files_legend(app, channel, file_order)
    else:
        # Original behavior for acquisition mode or other tabs
        x, y = app.phasors_charts[channel].getData()
        if x is None:
            x = np.array([])
            y = np.array([])
        new_x = [p[0] for p in phasors]
        new_y = [p[1] for p in phasors]
        x = np.concatenate((x, new_x))
        y = np.concatenate((y, new_y))
        app.phasors_charts[channel].setData(x, y)


def draw_lifetime_points_in_phasors(
    app, channel, harmonic, laser_period_ns, frequency_mhz
):
    """
    Draws reference lifetime points (tau markers) on the phasor plot.

    These points serve as a visual guide for estimating lifetimes from
    the phasor plot.

    Args:
        app: The main application instance.
        channel (int): The channel index to draw on.
        harmonic (int): The harmonic number.
        laser_period_ns (float): The laser period in nanoseconds.
        frequency_mhz (float): The laser frequency in MHz.
    """
    if channel not in app.plots_to_show or channel not in app.phasors_widgets:
        return

    if channel in app.phasors_lifetime_points:
        app.phasors_widgets[channel].removeItem(app.phasors_lifetime_points[channel])
    if channel in app.phasors_lifetime_texts:
        for _, item in enumerate(app.phasors_lifetime_texts[channel]):
            app.phasors_widgets[channel].removeItem(item)

    tau_m = np.array(
        [
            0.1e-9,
            0.5e-9,
            1e-9,
            2e-9,
            3e-9,
            4e-9,
            5e-9,
            6e-9,
            7e-9,
            8e-9,
            9e-9,
            10e-9,
        ]
    )
    if frequency_mhz in [10, 20]:
        additional_tau = np.arange(10e-9, 26e-9, 5e-9)
        tau_m = np.concatenate((tau_m, additional_tau))
    tau_phi = tau_m
    if laser_period_ns == 0 or laser_period_ns is None:
        return
    fex = (1 / laser_period_ns) * 10e8
    k = 1 / (2 * np.pi * harmonic * fex)
    phi = np.arctan(tau_phi / k)
    factor = (tau_m / k) ** 2
    m = np.sqrt(1 / (1 + factor))
    g = m * np.cos(phi)
    s = m * np.sin(phi)
    scatter = pg.ScatterPlotItem(x=g, y=s, size=8, pen=None, brush="red", symbol="o")
    scatter.setZValue(5)
    app.phasors_widgets[channel].addItem(scatter)
    app.phasors_lifetime_points[channel] = scatter
    texts = []
    for i in range(len(g)):
        text = pg.TextItem(
            f"{tau_m[i] * 1e9:.1f} ns",
            anchor=(0, 0),
            color="white",
            border=None,
        )
        text.setPos(g[i] + 0.01, s[i] + 0.01)
        text.setZValue(5)
        texts.append(text)
        app.phasors_widgets[channel].addItem(text)
    app.phasors_lifetime_texts[channel] = texts


def quantize_phasors(app, harmonic, bins=64):
    """
    Creates a 2D histogram (density map) of the phasor points.

    This replaces individual points with a colormapped image representing
    point density, improving performance and visualization for large datasets.

    Args:
        app: The main application instance.
        harmonic (int): The harmonic number to quantize.
        bins (int, optional): The number of bins for the histogram. Defaults to 64.
    """
    for i, channel_index in enumerate(app.plots_to_show):
        x = [p[0] for p in app.all_phasors_points[channel_index][harmonic]]
        y = [p[1] for p in app.all_phasors_points[channel_index][harmonic]]
        if x is None or y is None or len(x) == 0 or len(y) == 0:
            continue
        h, xedges, yedges = np.histogram2d(
            x, y, bins=bins * 4, range=[[-2, 2], [-2, 2]]
        )
        non_zero_h = h[h > 0]
        all_zeros = len(non_zero_h) == 0
        h_min = np.min(non_zero_h)
        h_max = np.max(h)
        h = h / np.max(h)
        h[h == 0] = np.nan
        image_item = pg.ImageItem()
        image_item.setImage(h, levels=(0, 1))
        image_item.setLookupTable(create_cool_colormap().getLookupTable(0, 1.0))
        image_item.setOpacity(1)
        image_item.resetTransform()
        image_item.setScale(1 / bins)
        image_item.setPos(-2, -2)
        if channel_index in app.quantization_images:
            app.phasors_widgets[channel_index].removeItem(
                app.quantization_images[channel_index]
            )
        if channel_index in app.phasors_colorbars:
            app.phasors_widgets[channel_index].removeItem(
                app.phasors_colorbars[channel_index]
            )
        image_item.setZValue(-1)
        app.phasors_widgets[channel_index].addItem(image_item, ignoreBounds=True)
        app.quantization_images[channel_index] = image_item
        if not all_zeros:
            generate_colorbar(app, channel_index, h_min, h_max)
        # Import here to avoid circular dependency
        from core.phasors_controller import PhasorsController

        PhasorsController.clear_phasors_points(app)


def generate_colorbar(app, channel_index, min_value, max_value):
    """
    Generates and adds a color bar for the quantized phasor plot.

    Args:
        app: The main application instance.
        channel_index (int): The channel to add the color bar to.
        min_value (float): The minimum value for the color bar label.
        max_value (float): The maximum value for the color bar label.
    """
    colorbar = pg.GradientLegend((10, 100), (10, 100))
    colorbar.setColorMap(create_cool_colormap(0, 1))
    colorbar.setLabels({f"{min_value}": 0, f"{max_value}": 1})
    app.phasors_widgets[channel_index].addItem(colorbar)
    app.phasors_colorbars[channel_index] = colorbar


def create_hot_colormap():
    """
    Creates a 'hot' colormap (black -> red -> yellow -> white).

    Returns:
        pg.ColorMap: A pyqtgraph ColorMap object.
    """
    pos = np.array([0.0, 0.33, 0.67, 1.0])
    color = np.array(
        [
            [0, 0, 0, 255],  # Black
            [255, 0, 0, 255],  # Red
            [255, 255, 0, 255],  # Yellow
            [255, 255, 255, 255],  # White
        ],
        dtype=np.ubyte,
    )
    cmap = pg.ColorMap(pos, color)
    return cmap


def create_cool_colormap(start=0.0, end=1.0):
    """
    Creates a 'cool' colormap (cyan -> magenta).

    Args:
        start (float, optional): The starting position for the colormap. Defaults to 0.0.
        end (float, optional): The ending position for the colormap. Defaults to 1.0.

    Returns:
        pg.ColorMap: A pyqtgraph ColorMap object.
    """
    pos = np.array([start, end])
    color = np.array(
        [[0, 255, 255, 255], [255, 0, 255, 255]],  # Cyan  # Magenta
        dtype=np.float32,
    )
    cmap = pg.ColorMap(pos, color)
    return cmap
