"""
plot_builders.py
============================================================
UI widget construction for all plot types

Provides plain functions (no class) that build and wire up pyqtgraph
PlotWidgets into the app state dictionaries. Covers intensity sections,
decay curve widgets, spectroscopy composite panels, and phasor panels.
"""

import pyqtgraph as pg

from components.animations import VibrantAnimation
from utils.gui_styles import GUIStyles
from components.lin_log_control import LinLogControl
from components.spectroscopy_curve_time_shift import SpectroscopyTimeShift
from utils.channel_name_utils import get_channel_name

import settings.settings as s

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)


def create_intensity_section(app, channel, for_phasor_tab=False):
    """
    Creates the UI section for the intensity plot.

    Builds a compound widget containing the intensity plot itself, a CPS
    (Counts Per Second) label with animation, and a countdown timer label.

    LaserBlood difference: uses app.channel_names directly and also stores
    a direct reference to the PlotWidget in app.intensity_plot_widgets.

    Args:
        app: The main application instance.
        channel (int): The channel index.
        for_phasor_tab (bool, optional): If True, uses a different color
                                         scheme for the CPS label. Defaults to False.

    Returns:
        QWidget: The container widget for the entire intensity section.
    """

    from core.plots.plot_initializers import (
        initialize_intensity_plot_data,
    )

    intensity_widget_wrapper = QWidget()
    h_layout = QHBoxLayout()
    cps_contdown_v_box = QVBoxLayout()
    cps_contdown_v_box.setContentsMargins(0, 0, 0, 0)
    cps_contdown_v_box.setSpacing(0)

    # --- CPS Label and Animation ---
    cps_color = "#f72828" if for_phasor_tab else "#285da6"
    cps_label = QLabel("No CPS")
    cps_label.setStyleSheet(
        f"QLabel {{ color : {cps_color}; font-size: 42px; font-weight: bold; background-color: transparent; padding: 8px 8px 0 8px;}}"
    )
    app.cps_widgets[channel] = cps_label
    app.cps_widgets_animation[channel] = VibrantAnimation(
        cps_label, stop_color=cps_color, bg_color="transparent", start_color="#eed202"
    )
    app.cps_counts[channel] = {"last_time_ns": 0, "last_count": 0, "current_count": 0}

    # --- Countdown Label ---
    countdown_label = QLabel("Remaining time:")
    countdown_label.setStyleSheet(GUIStyles.acquisition_time_countdown_style())
    countdown_label.setVisible(False)
    app.acquisition_time_countdown_widgets[channel] = countdown_label

    # --- Intensity Plot Widget ---
    intensity_widget = pg.PlotWidget()
    intensity_widget.setLabel(
        "left",
        ("AVG. Photon counts" if len(app.plots_to_show) < 4 else "AVG. Photons"),
        units="",
    )
    intensity_widget.setLabel("bottom", "Time", units="s")
    # Use custom channel name directly from app.channel_names
    channel_title = get_channel_name(channel, app.channel_names)
    intensity_widget.setTitle(f"{channel_title} intensity")
    intensity_widget.setBackground("#141414")
    intensity_widget.plotItem.setContentsMargins(0, 0, 0, 0)
    x, y = initialize_intensity_plot_data(app, channel)
    intensity_plot = intensity_widget.plot(x, y, pen=pg.mkPen(color="#1E90FF", width=2))
    app.intensity_lines[app.tab_selected][channel] = intensity_plot

    # --- Layout Assembly ---
    cps_contdown_v_box.addWidget(cps_label)
    cps_contdown_v_box.addWidget(countdown_label)
    h_layout.addLayout(cps_contdown_v_box, stretch=1)

    stretch_map = {1: 6, 2: 4, 3: 2}
    intensity_plot_stretch = stretch_map.get(len(app.plots_to_show), 4)
    h_layout.addWidget(intensity_widget, stretch=intensity_plot_stretch)

    intensity_widget_wrapper.setLayout(h_layout)
    app.intensities_widgets[channel] = intensity_widget_wrapper
    # LaserBlood-specific: also store a direct reference to the PlotWidget
    app.intensity_plot_widgets[channel] = intensity_widget
    return intensity_widget_wrapper


def create_decay_curve_widget(app, channel, frequency_mhz):
    """
    Creates and configures a decay curve plot widget.

    Sets up a pyqtgraph PlotWidget for displaying a decay curve, handling
    both linear and logarithmic scale displays.

    LaserBlood difference: uses app.channel_names directly and applies
    simplified READ-mode title logic (no per-tab metadata lookup).

    Args:
        app: The main application instance.
        channel (int): The channel index.
        frequency_mhz (float): The laser frequency, used for initialization.

    Returns:
        pg.PlotWidget: The configured plot widget for the decay curve.
    """

    from core.plots.plot_initializers import (
        initialize_decay_curves,
    )

    curve_widget = pg.PlotWidget()
    curve_widget.setLabel("left", "Photon counts", units="")
    # Use "Bin" label for FITTING in READ mode with data loaded, "Time (ns)" for others
    if (
        app.tab_selected == s.TAB_FITTING
        and app.acquire_read_mode == "read"
        and hasattr(app, "reader_data")
        and app.reader_data.get("fitting", {}).get("data", {}).get("spectroscopy_data")
    ):
        curve_widget.setLabel("bottom", "Bin", units="")
    else:
        curve_widget.setLabel("bottom", "Time", units="ns")
    # Show channel title only in ACQUIRE mode; simplified READ-mode logic
    if app.acquire_read_mode == "acquire":
        # Use custom channel name directly from app.channel_names
        channel_title = get_channel_name(channel, app.channel_names)
        curve_widget.setTitle(f"{channel_title} decay")
    elif app.tab_selected == s.TAB_PHASORS and app.acquire_read_mode == "read":
        curve_widget.setTitle(f"Decay")
    else:
        curve_widget.setTitle("")
    curve_widget.setBackground("#0a0a0a")

    x, y = initialize_decay_curves(app, channel, frequency_mhz)

    if channel not in app.lin_log_mode or app.lin_log_mode[channel] == "LIN":
        static_curve = curve_widget.plot(x, y, pen=pg.mkPen(color="#f72828", width=2))
    else:  # LOG mode
        log_values, ticks, _ = LinLogControl.calculate_log_ticks(y)
        static_curve = curve_widget.plot(
            x, log_values, pen=pg.mkPen(color="#f72828", width=2)
        )
        axis = curve_widget.getAxis("left")
        curve_widget.showGrid(x=False, y=True, alpha=0.3)
        axis.setTicks([ticks])
        set_plot_y_range(curve_widget)

    curve_widget.plotItem.getAxis("left").enableAutoSIPrefix(False)
    curve_widget.plotItem.getAxis("bottom").enableAutoSIPrefix(False)

    app.decay_curves[app.tab_selected][channel] = static_curve
    app.decay_widgets[channel] = curve_widget
    return curve_widget


def create_spectroscopy_plot_widget(app, channel, frequency_mhz):
    """
    Creates a complete plot widget for the Spectroscopy or Fitting tab.

    This widget is a composite of the intensity section and the decay curve
    section, along with controls for linear/logarithmic scale and time shift.

    Args:
        app: The main application instance.
        channel (int): The channel index.
        frequency_mhz (float): The laser frequency.

    Returns:
        QWidget: The container widget for the entire spectroscopy plot area.
    """
    from core.controls_controller import ControlsController

    v_widget = QWidget()
    v_widget.setObjectName("chart_wrapper")
    v_layout = QVBoxLayout()

    # --- Intensity Section ---
    intensity_section = create_intensity_section(app, channel)
    v_layout.addWidget(intensity_section, 2)

    # --- Decay Curve Section ---
    h_decay_layout = QHBoxLayout()
    time_shifts = (
        SpectroscopyTimeShift.get_channel_time_shift(app, channel)
        if app.acquire_read_mode == "acquire"
        else 0
    )
    lin_log_widget = LinLogControl(
        app,
        channel,
        time_shifts=time_shifts,
        lin_log_modes=app.lin_log_mode,
        lin_log_switches=app.lin_log_switches,
    )

    v_decay_layout = QVBoxLayout()
    v_decay_layout.setSpacing(0)
    v_decay_layout.addWidget(SpectroscopyTimeShift(app, channel))

    if app.acquire_read_mode != "read":
        SBR_label = QLabel("SBR: 0 ㏈")
        SBR_label.setStyleSheet(GUIStyles.SBR_label())
        if not app.show_SBR:
            SBR_label.hide()
        app.SBR_items[channel] = SBR_label
        v_decay_layout.addWidget(SBR_label)

    curve_widget = create_decay_curve_widget(app, channel, frequency_mhz)
    v_decay_layout.addWidget(curve_widget)

    h_decay_layout.addWidget(lin_log_widget, 1)
    h_decay_layout.addLayout(v_decay_layout, 11)
    v_layout.addLayout(h_decay_layout, 3)

    v_widget.setLayout(v_layout)
    ControlsController.fit_button_hide(app)
    return v_widget


def create_phasor_plot_widget(app, channel, frequency_mhz):
    """
    Creates a complete plot widget for the Phasor tab.

    This widget is a composite of a compact decay curve/CPS section and the
    main phasor plot.

    Args:
        app: The main application instance.
        channel (int): The channel index.
        frequency_mhz (float): The laser frequency.

    Returns:
        QWidget: The container widget for the entire phasor plot area.
    """
    from core.phasors_controller import PhasorsController

    v_widget = QWidget()
    v_widget.setObjectName("chart_wrapper")
    v_layout = QVBoxLayout()

    # --- Top Section (CPS and Decay) ---
    h_layout = QHBoxLayout()
    # CPS and Countdown
    cps_contdown_v_box = QVBoxLayout()
    cps_contdown_v_box.setContentsMargins(0, 0, 0, 0)
    cps_contdown_v_box.setSpacing(0)
    cps_color = "#f72828"
    cps_label = QLabel("No CPS")
    cps_label.setStyleSheet(
        f"QLabel {{ color : {cps_color}; font-size: 42px; font-weight: bold; background-color: transparent; padding: 8px 8px 0 8px; }}"
    )
    app.cps_widgets[channel] = cps_label
    app.cps_widgets_animation[channel] = VibrantAnimation(
        cps_label, stop_color=cps_color, bg_color="transparent", start_color="#eed202"
    )
    app.cps_counts[channel] = {"last_time_ns": 0, "last_count": 0, "current_count": 0}
    countdown_label = QLabel("Remaining time:")
    countdown_label.setStyleSheet(GUIStyles.acquisition_time_countdown_style())
    countdown_label.setVisible(False)
    app.acquisition_time_countdown_widgets[channel] = countdown_label
    cps_contdown_v_box.addWidget(cps_label)
    cps_contdown_v_box.addWidget(countdown_label)

    # Decay Curve
    curve_widget_container = QVBoxLayout()
    curve_widget_container.setContentsMargins(0, 0, 0, 0)
    curve_widget_container.setSpacing(0)
    if app.acquire_read_mode != "read":
        SBR_label = QLabel("SBR: 0 ㏈")
        SBR_label.setStyleSheet(
            GUIStyles.SBR_label(font_size="16px", background_color="#000000")
        )
        if not app.show_SBR:
            SBR_label.hide()
        app.SBR_items[channel] = SBR_label
        curve_widget_container.addWidget(SBR_label)

    curve_widget = create_decay_curve_widget(app, channel, frequency_mhz)
    curve_widget_container.addWidget(curve_widget)

    h_layout.addLayout(cps_contdown_v_box, stretch=1)
    h_layout.addLayout(curve_widget_container, stretch=1)
    v_layout.addLayout(h_layout, 1)

    # --- Phasor Chart Section ---
    phasors_widget = pg.PlotWidget()
    phasors_widget.setAspectLocked(True)
    phasors_widget.setLabel("left", "s", units="")
    phasors_widget.setLabel("bottom", "g", units="")
    if app.tab_selected == s.TAB_PHASORS and app.acquire_read_mode == "read":
        phasors_widget.setTitle(f"Phasors")
    else:
        # Use custom channel name directly from app.channel_names
        channel_title = get_channel_name(channel, app.channel_names)
        phasors_widget.setTitle(f"{channel_title} phasors")
    PhasorsController.draw_semi_circle(phasors_widget)
    app.phasors_charts[channel] = phasors_widget.plot(
        [],
        [],
        pen=None,
        symbol="o",
        symbolPen="#1E90FF",
        symbolSize=1,
        symbolBrush="#1E90FF",
    )
    app.phasors_widgets[channel] = phasors_widget
    v_layout.addWidget(phasors_widget, 3)

    # --- Legend Section (Fixed bottom area) ---
    legend_label = QLabel("")
    legend_label.setStyleSheet(GUIStyles.phasors_legend_label())
    legend_label.setVisible(False)  # Hidden by default
    legend_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    # Initialize the legend widgets dictionary if it doesn't exist
    if not hasattr(app, "phasors_legend_labels"):
        app.phasors_legend_labels = {}
    app.phasors_legend_labels[channel] = legend_label
    v_layout.addWidget(legend_label)

    if app.acquire_read_mode == "read":
        phasors_widget.setCursor(Qt.CursorShape.BlankCursor)
        PhasorsController.generate_coords(app, channel)
        PhasorsController.create_phasor_crosshair(
            app, channel, app.phasors_widgets[channel]
        )

    v_widget.setLayout(v_layout)
    return v_widget


def set_plot_y_range(plot):
    """
    Adjusts the Y-axis range of a plot for better visualization.

    It performs an auto-range and then sets the lower bound to a small
    negative value to avoid the curve touching the bottom axis.

    Args:
        plot (pg.PlotWidget): The plot widget to adjust.
    """
    plot.plotItem.autoRange()
    view_range = plot.viewRange()
    _, y_max = view_range[1]
    plot.setYRange(-1, y_max, padding=0)
