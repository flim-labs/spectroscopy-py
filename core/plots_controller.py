from copy import deepcopy
import time
import numpy as np
import pyqtgraph as pg

from components.animations import VibrantAnimation
from utils.gui_styles import GUIStyles
from utils.helpers import get_realtime_adjustment_value
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
    QApplication,
)

from utils.layout_utilities import clear_layout_tree


class PlotsController:
    """
    A controller class with static methods to manage plot generation and updates.

    This class is responsible for creating, clearing, and updating all plots
    within the application, including intensity graphs, decay curves, and
    phasor plots. It acts as a centralized manager for all pyqtgraph-related
    operations, interacting with the main application instance (`app`) to access
    and store state.
    """
    
    @staticmethod
    def initialize_intensity_plot_data(app, channel):
        """
        Initializes data for an intensity plot.

        It first checks if data already exists for the given channel in the
        current tab. If so, it returns the existing data. Otherwise, it returns
        a default, empty dataset.

        Args:
            app: The main application instance.
            channel (int): The channel index for which to initialize data.

        Returns:
            tuple[np.ndarray, np.ndarray]: A tuple containing the x and y numpy arrays for the plot.
        """
        if app.tab_selected in app.intensity_lines:
            if channel in app.intensity_lines[app.tab_selected]:
                x, y = app.intensity_lines[app.tab_selected][channel].getData()
                return x, y
        x = np.arange(1)
        y = x * 0
        return x, y
    
    
    @staticmethod
    def initialize_decay_curves(app, channel, frequency_mhz):
        """
        Initializes data for a decay curve plot.

        Handles different logic based on the selected tab (Spectroscopy, Fitting, etc.)
        and the display mode (Linear/Logarithmic). It can retrieve cached data or
        generate default data based on the laser frequency.

        Args:
            app: The main application instance.
            channel (int): The channel index.
            frequency_mhz (float): The current laser frequency in MHz, used to
                                   calculate the time axis.

        Returns:
            tuple[np.ndarray, np.ndarray]: A tuple containing the x and y numpy arrays for the plot.
        """
        def get_default_x():
            # Use bin indices for FITTING READ mode only if data has been loaded
            if (app.tab_selected == s.TAB_FITTING and 
                app.acquire_read_mode == "read" and
                hasattr(app, 'reader_data') and 
                app.reader_data.get("fitting", {}).get("data", {}).get("spectroscopy_data")):
                return np.arange(256)
            # Use time values for other modes when frequency is available
            if frequency_mhz != 0.0:
                period = 1_000 / frequency_mhz
                return np.linspace(0, period, 256)
            # For SPECTROSCOPY/other modes with no frequency, return minimal array
            return np.arange(1)

        decay_curves = app.decay_curves[app.tab_selected]
        if app.tab_selected in [s.TAB_SPECTROSCOPY, s.TAB_FITTING]:
            cached_decay_values = app.cached_decay_values[app.tab_selected]
            if channel in cached_decay_values and channel in decay_curves:
                x, _ = decay_curves[channel].getData()
                y = cached_decay_values[channel]
            else:
                x = get_default_x()
                if (
                    channel not in app.lin_log_mode
                    or app.lin_log_mode[channel] == "LIN"
                ):
                    y = np.zeros(len(x))
                else:
                    y = np.linspace(0, 100_000_000, len(x))
        else:
            if channel in decay_curves:
                x, y = decay_curves[channel].getData()
            else:
                x = get_default_x()
                y = np.zeros(len(x))
        return x, y
    
    
    
    @staticmethod
    def _create_intensity_section(app, channel, for_phasor_tab=False):
        """
        Creates the UI section for the intensity plot.

        This private helper method builds a compound widget containing the
        intensity plot itself, a CPS (Counts Per Second) label with animation,
        and a countdown timer label.

        Args:
            app: The main application instance.
            channel (int): The channel index.
            for_phasor_tab (bool, optional): If True, uses a different color
                                             scheme for the CPS label. Defaults to False.

        Returns:
            QWidget: The container widget for the entire intensity section.
        """
        intensity_widget_wrapper = QWidget()
        h_layout = QHBoxLayout()
        cps_contdown_v_box = QVBoxLayout()
        cps_contdown_v_box.setContentsMargins(0, 0, 0, 0)
        cps_contdown_v_box.setSpacing(0)

        # --- CPS Label and Animation ---
        cps_color = "#f72828" if for_phasor_tab else "#285da6"
        cps_label = QLabel("No CPS")
        cps_label.setStyleSheet(f"QLabel {{ color : {cps_color}; font-size: 42px; font-weight: bold; background-color: transparent; padding: 8px 8px 0 8px;}}")
        app.cps_widgets[channel] = cps_label
        app.cps_widgets_animation[channel] = VibrantAnimation(cps_label, stop_color=cps_color, bg_color="transparent", start_color="#eed202")
        app.cps_counts[channel] = {"last_time_ns": 0, "last_count": 0, "current_count": 0}

        # --- Countdown Label ---
        countdown_label = QLabel("Remaining time:")
        countdown_label.setStyleSheet(GUIStyles.acquisition_time_countdown_style())
        countdown_label.setVisible(False)
        app.acquisition_time_countdown_widgets[channel] = countdown_label

        # --- Intensity Plot Widget ---
        intensity_widget = pg.PlotWidget()
        intensity_widget.setLabel("left", ("AVG. Photon counts" if len(app.plots_to_show) < 4 else "AVG. Photons"), units="")
        intensity_widget.setLabel("bottom", "Time", units="s")
        channel_names = getattr(app, 'channel_names', {})
        intensity_widget.setTitle(f"{get_channel_name(channel, channel_names)} intensity")
        intensity_widget.setBackground("#141414")
        intensity_widget.plotItem.setContentsMargins(0, 0, 0, 0)
        x, y = PlotsController.initialize_intensity_plot_data(app, channel)
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
        return intensity_widget_wrapper

    @staticmethod
    def _create_decay_curve_widget(app, channel, frequency_mhz):
        """
        Creates and configures a decay curve plot widget.

        This private helper sets up a pyqtgraph PlotWidget for displaying a
        decay curve, handling both linear and logarithmic scale displays.

        Args:
            app: The main application instance.
            channel (int): The channel index.
            frequency_mhz (float): The laser frequency, used for initialization.

        Returns:
            pg.PlotWidget: The configured plot widget for the decay curve.
        """
        curve_widget = pg.PlotWidget()
        curve_widget.setLabel("left", "Photon counts", units="")
        # Use "Bin" label for FITTING in READ mode with data loaded, "Time (ns)" for others
        if (app.tab_selected == s.TAB_FITTING and 
            app.acquire_read_mode == "read" and
            hasattr(app, 'reader_data') and 
            app.reader_data.get("fitting", {}).get("data", {}).get("spectroscopy_data")):
            curve_widget.setLabel("bottom", "Bin", units="")
        else:
            curve_widget.setLabel("bottom", "Time", units="ns")
        # Show channel title only in ACQUIRE mode, hide in READ mode
        if app.acquire_read_mode == "acquire":
            channel_names = getattr(app, 'channel_names', {})
            curve_widget.setTitle(f"{get_channel_name(channel, channel_names)} decay")
        elif app.tab_selected == s.TAB_PHASORS and app.acquire_read_mode == "read":
            curve_widget.setTitle(f"Decay")
        else:
            curve_widget.setTitle("")
        curve_widget.setBackground("#0a0a0a")
        
        x, y = PlotsController.initialize_decay_curves(app, channel, frequency_mhz)
        
        if channel not in app.lin_log_mode or app.lin_log_mode[channel] == "LIN":
            static_curve = curve_widget.plot(x, y, pen=pg.mkPen(color="#f72828", width=2))
        else: # LOG mode
            log_values, ticks, _ = LinLogControl.calculate_log_ticks(y)
            static_curve = curve_widget.plot(x, log_values, pen=pg.mkPen(color="#f72828", width=2))
            axis = curve_widget.getAxis("left")
            curve_widget.showGrid(x=False, y=True, alpha=0.3)
            axis.setTicks([ticks])
            PlotsController.set_plot_y_range(curve_widget)
            
        curve_widget.plotItem.getAxis("left").enableAutoSIPrefix(False)
        curve_widget.plotItem.getAxis("bottom").enableAutoSIPrefix(False)
        
        app.decay_curves[app.tab_selected][channel] = static_curve
        app.decay_widgets[channel] = curve_widget
        return curve_widget

    @staticmethod
    def _create_spectroscopy_plot_widget(app, channel, frequency_mhz):
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
        intensity_section = PlotsController._create_intensity_section(app, channel)
        v_layout.addWidget(intensity_section, 2)

        # --- Decay Curve Section ---
        h_decay_layout = QHBoxLayout()
        time_shifts = SpectroscopyTimeShift.get_channel_time_shift(app, channel) if app.acquire_read_mode == "acquire" else 0
        lin_log_widget = LinLogControl(app, channel, time_shifts=time_shifts, lin_log_modes=app.lin_log_mode, lin_log_switches=app.lin_log_switches)
        
        v_decay_layout = QVBoxLayout()
        v_decay_layout.setSpacing(0)
        v_decay_layout.addWidget(SpectroscopyTimeShift(app, channel))

        if app.acquire_read_mode != "read":
            SBR_label = QLabel("SBR: 0 ㏈")
            SBR_label.setStyleSheet(GUIStyles.SBR_label())
            if not app.show_SBR: SBR_label.hide()
            app.SBR_items[channel] = SBR_label
            v_decay_layout.addWidget(SBR_label)
        
        curve_widget = PlotsController._create_decay_curve_widget(app, channel, frequency_mhz)
        v_decay_layout.addWidget(curve_widget)
        
        h_decay_layout.addWidget(lin_log_widget, 1)
        h_decay_layout.addLayout(v_decay_layout, 11)
        v_layout.addLayout(h_decay_layout, 3)
        
        v_widget.setLayout(v_layout)
        ControlsController.fit_button_hide(app)
        return v_widget

    @staticmethod
    def _create_phasor_plot_widget(app, channel, frequency_mhz):
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
        cps_label.setStyleSheet(f"QLabel {{ color : {cps_color}; font-size: 42px; font-weight: bold; background-color: transparent; padding: 8px 8px 0 8px; }}")
        app.cps_widgets[channel] = cps_label
        app.cps_widgets_animation[channel] = VibrantAnimation(cps_label, stop_color=cps_color, bg_color="transparent", start_color="#eed202")
        app.cps_counts[channel] = {"last_time_ns": 0, "last_count": 0, "current_count": 0}
        countdown_label = QLabel("Remaining time:")
        countdown_label.setStyleSheet(GUIStyles.acquisition_time_countdown_style())
        countdown_label.setVisible(False)
        app.acquisition_time_countdown_widgets[channel] = countdown_label
        cps_contdown_v_box.addWidget(cps_label)
        cps_contdown_v_box.addWidget(countdown_label)
        
        # Decay Curve
        curve_widget_container = QVBoxLayout()
        curve_widget_container.setContentsMargins(0,0,0,0)
        curve_widget_container.setSpacing(0)
        if app.acquire_read_mode != "read":
            SBR_label = QLabel("SBR: 0 ㏈")
            SBR_label.setStyleSheet(GUIStyles.SBR_label(font_size="16px", background_color="#000000"))
            if not app.show_SBR: SBR_label.hide()
            app.SBR_items[channel] = SBR_label
            curve_widget_container.addWidget(SBR_label)
        
        curve_widget = PlotsController._create_decay_curve_widget(app, channel, frequency_mhz)
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
           channel_names = getattr(app, 'channel_names', {})
           phasors_widget.setTitle(f"{get_channel_name(channel, channel_names)} phasors")
        PhasorsController.draw_semi_circle(phasors_widget)
        app.phasors_charts[channel] = phasors_widget.plot([], [], pen=None, symbol="o", symbolPen="#1E90FF", symbolSize=1, symbolBrush="#1E90FF")
        app.phasors_widgets[channel] = phasors_widget
        v_layout.addWidget(phasors_widget, 3)
        
        # --- Legend Section (Fixed bottom area) ---
        legend_label = QLabel("")
        legend_label.setStyleSheet(GUIStyles.phasors_legend_label())
        legend_label.setVisible(False)  # Hidden by default
        legend_label.setAlignment(Qt.AlignmentFlag.AlignHCenter) 
        # Initialize the legend widgets dictionary if it doesn't exist
        if not hasattr(app, 'phasors_legend_labels'):
            app.phasors_legend_labels = {}
        app.phasors_legend_labels[channel] = legend_label
        v_layout.addWidget(legend_label)
        
        if app.acquire_read_mode == "read":
            phasors_widget.setCursor(Qt.CursorShape.BlankCursor)
            PhasorsController.generate_coords(app, channel)
            PhasorsController.create_phasor_crosshair(app, channel, app.phasors_widgets[channel])
            
        v_widget.setLayout(v_layout)
        return v_widget

    @staticmethod
    def generate_plots(app, frequency_mhz=0.0):
        """
        Generates and arranges all plots in the main grid layout.

        This is the main entry point for building the plot area. It iterates
        through the channels selected for display and, based on the active tab,
        calls the appropriate helper method to create the plot widget.

        Args:
            app: The main application instance.
            frequency_mhz (float, optional): The current laser frequency. Defaults to 0.0.
        """
        app.lin_log_switches.clear()
        if not app.plots_to_show:
            app.grid_layout.addWidget(QWidget(), 0, 0)
            return

        plots_to_show = app.plots_to_show
        
        # In FITTING READ mode, force only first channel to be shown
        if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode == "read":
            if len(plots_to_show) > 0:
                plots_to_show = [plots_to_show[0]]
              
        for i, channel in enumerate(plots_to_show):
            plot_widget = None
            if app.tab_selected in [s.TAB_SPECTROSCOPY, s.TAB_FITTING]:
                plot_widget = PlotsController._create_spectroscopy_plot_widget(app, channel, frequency_mhz)
            elif app.tab_selected == s.TAB_PHASORS:
                plot_widget = PlotsController._create_phasor_plot_widget(app, channel, frequency_mhz)

            if plot_widget:
                col_map = {1: 1, 2: 2, 3: 3}
                col_length = col_map.get(len(plots_to_show), 2)
                plot_widget.setStyleSheet(GUIStyles.chart_wrapper_style())
                app.grid_layout.addWidget(plot_widget, i // col_length, i % col_length)
            
            
    
    @staticmethod
    def update_intensity_plots(app, channel_index, time_ns, curve):
        """
        Updates the intensity plot for a specific channel with new data.

        It appends the new data point (total counts in the curve vs. time)
        and trims the data from the left to maintain a fixed time window,
        creating a scrolling effect.

        Args:
            app: The main application instance.
            channel_index (int): The channel to update.
            time_ns (int): The timestamp of the new data in nanoseconds.
            curve (np.ndarray): The array of photon counts for the new data slice.
        """
        bin_width_micros = int(
            app.settings.value(s.SETTINGS_BIN_WIDTH, s.DEFAULT_BIN_WIDTH)
        )
        adjustment = (
            get_realtime_adjustment_value(
                app.selected_channels, app.tab_selected == s.TAB_PHASORS
            )
            / bin_width_micros
        )
        curve = tuple(x / adjustment for x in curve)
        if app.tab_selected in app.intensity_lines:
            if channel_index in app.intensity_lines[app.tab_selected]:
                intensity_line = app.intensity_lines[app.tab_selected][channel_index]
                if intensity_line is not None:
                    x, y = intensity_line.getData()
                    # Initialize or append data
                    if x is None or (len(x) == 1 and x[0] == 0):
                        x = np.array([time_ns / 1_000_000_000])
                        y = np.array([np.sum(curve)])
                    else:
                        x = np.append(x, time_ns / 1_000_000_000)
                        y = np.append(y, np.sum(curve))
                    # Trim data based on time span
                    if len(x) > 2:
                        while x[-1] - x[0] > app.cached_time_span_seconds:
                            x = x[1:]
                            y = y[1:]
                    intensity_line.setData(x, y) 
                    
                    
                    
    @staticmethod
    def update_spectroscopy_plots(app, x, y, channel_index, decay_curve):
        """
        Updates the decay curve plot, handling linear/log scales and time shifts.

        Args:
            app: The main application instance.
            x (np.ndarray): The x-axis data (time).
            y (np.ndarray): The y-axis data (counts).
            channel_index (int): The channel to update.
            decay_curve (pg.PlotDataItem): The plot item to update.
        """
        # Apply time_shift in both ACQUIRE and READ modes
        time_shift = (
                0
                if channel_index not in app.time_shifts
                else app.time_shifts[channel_index]
            )
        
        # Check if decay_widget exists for this channel
        if channel_index not in app.decay_widgets:
            return
            
        # Handle linear/logarithmic mode
        decay_widget = app.decay_widgets[channel_index]
        if (
            channel_index not in app.lin_log_mode
            or app.lin_log_mode[channel_index] == "LIN"
        ):
            decay_widget.showGrid(x=False, y=False, alpha=0.3)
            decay_curve.setData(x, np.roll(y, time_shift))
            PlotsController.set_plot_y_range(decay_widget)
        else:
            decay_widget.showGrid(x=False, y=True, alpha=0.3)
            sum_decay = y
            log_values, ticks, _ = LinLogControl.calculate_log_ticks(sum_decay)
            decay_curve.setData(x, np.roll(log_values, time_shift))
            axis = decay_widget.getAxis("left")
            axis.setTicks([ticks])
            PlotsController.set_plot_y_range(decay_widget)   
            
            
            
    @staticmethod
    def update_plots(app, channel_index, time_ns, curve, reader_mode=False):
        """
        Main function to update plots with new data during an acquisition.

        This function is called repeatedly with new data chunks. It dispatches
        the data to the intensity and decay curve update functions.

        Args:
            app: The main application instance.
            channel_index (int): The channel the data belongs to.
            time_ns (int): The timestamp of the data.
            curve (np.ndarray): The photon count data.
            reader_mode (bool, optional): True if data comes from a file reader,
                                          which affects how data is handled. Defaults to False.
        """
        if not reader_mode:
            # Update intensity plots
            PlotsController.update_intensity_plots(app, channel_index, time_ns, curve)
        
        # Get decay_curve if it exists, but don't fail if it doesn't (especially in reader_mode)
        decay_curve = None
        if (app.tab_selected in app.decay_curves and 
            channel_index in app.decay_curves[app.tab_selected]):
            decay_curve = app.decay_curves[app.tab_selected][channel_index]
        
        # In reader_mode with fitting data, we can proceed without decay_curve
        if decay_curve is not None or (reader_mode and app.tab_selected == s.TAB_FITTING):
            if reader_mode:
                x, y = time_ns, curve
            elif decay_curve is not None:
                x, y = decay_curve.getData()
                if app.tab_selected == s.TAB_PHASORS:
                    decay_curve.setData(x, curve + y)
                elif app.tab_selected in (s.TAB_SPECTROSCOPY, s.TAB_FITTING):
                    last_cached_decay_value = app.cached_decay_values[
                        app.tab_selected
                    ][channel_index]
                    app.cached_decay_values[app.tab_selected][channel_index] = (
                        np.array(curve) + last_cached_decay_value
                    )
                    y = app.cached_decay_values[app.tab_selected][channel_index]
            if app.tab_selected in (s.TAB_SPECTROSCOPY, s.TAB_FITTING):
                PlotsController.update_spectroscopy_plots(app, x, y, channel_index, decay_curve)
            else:
                decay_curve.setData(x, curve + y)
        QApplication.processEvents()
        time.sleep(0.01)        
            
                         
            
    @staticmethod
    def clear_plots(app, deep_clear=True):
        """
        Clears all plots and associated data structures from the UI.

        Args:
            app: The main application instance.
            deep_clear (bool, optional): If True, performs a "deep" clear,
                which also resets cached data arrays and removes all widgets
                from the grid layout. If False, only clears plot features
                like legends and clusters. Defaults to True.
        """
        from core.phasors_controller import PhasorsController
        PhasorsController.clear_phasors_features(app, app.phasors_colorbars)
        PhasorsController.clear_phasors_features(app, app.quantization_images)
        PhasorsController.clear_phasors_features(app, app.phasors_clusters_center)
        PhasorsController.clear_phasors_features(app, app.phasors_legends)
        PhasorsController.clear_phasors_features(app, app.phasors_lifetime_points)
        PhasorsController.clear_phasors_file_scatters(app)
        PhasorsController.clear_phasors_files_legend(app)
        for ch in app.phasors_lifetime_texts:
            for _, item in enumerate(app.phasors_lifetime_texts[ch]):
                app.phasors_widgets[ch].removeItem(item)
        app.quantization_images.clear()
        app.phasors_colorbars.clear()
        app.phasors_clusters_center.clear()
        app.phasors_legends.clear()
        app.phasors_legend_labels.clear()  # Clear fixed legend labels
        app.phasors_lifetime_points.clear()
        app.phasors_lifetime_texts.clear()
        app.intensities_widgets.clear()
        app.phasors_charts.clear()
        app.phasors_widgets.clear()
        app.decay_widgets.clear()
        app.phasors_coords.clear()
        for i, animation in app.cps_widgets_animation.items():
            if animation:
                animation.stop()
        app.cps_widgets_animation.clear()
        app.cps_widgets.clear()
        app.cps_counts.clear()
        app.all_cps_counts.clear()
        app.all_SBR_counts.clear()
        app.SBR_items.clear()
        app.acquisition_time_countdown_widgets.clear()
        if deep_clear:
            app.intensity_lines = deepcopy(s.DEFAULT_INTENSITY_LINES)
            app.decay_curves = deepcopy(s.DEFAULT_DECAY_CURVES)
            app.cached_decay_values = deepcopy(s.DEFAULT_CACHED_DECAY_VALUES)
            PhasorsController.clear_phasors_points(app)
            for ch in app.plots_to_show:
                if app.tab_selected != s.TAB_PHASORS:
                    app.cached_decay_values[app.tab_selected][ch] = np.array([0])
            if "time_shift_sliders" in app.control_inputs:
                app.control_inputs["time_shift_sliders"].clear()
            if "time_shift_inputs" in app.control_inputs:
                app.control_inputs["time_shift_inputs"].clear()
            for i in reversed(range(app.grid_layout.count())):
                widget = app.grid_layout.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()
                layout = app.grid_layout.itemAt(i).layout()
                if layout is not None:
                    clear_layout_tree(layout)
                    
                    
    
    @staticmethod
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
