import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import  Qt
from PyQt6.QtGui import QFont


from utils.helpers import mhz_to_ns
import settings.settings as s



class PhasorsController:
    """
    A controller class with static methods to manage phasor plot operations.

    This class handles the drawing, updating, and interaction with phasor plots,
    including calculating lifetimes, drawing reference points, and managing UI
    features like crosshairs and legends. It operates on the main application
    instance.
    """
    
    @staticmethod
    def get_empty_phasors_points():
        """
        Initializes an empty data structure for storing phasor points.

        Returns:
            list[dict[int, list]]: A list of dictionaries, where each list
                                   represents a channel and each dictionary
                                   holds empty lists for harmonics 1 through 4.
        """
        empty = []
        for i in range(8):
            empty.append({1: [], 2: [], 3: [], 4: []})
        return empty
    
    @staticmethod
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
        
        
    @staticmethod
    def draw_points_in_phasors(app, channel, harmonic, phasors):
        """
        Draws a set of phasor points on the specified channel's plot.

        Args:
            app: The main application instance.
            channel (int): The channel index to draw the points on.
            harmonic (int): The harmonic number of the phasor points.
            phasors (list[tuple[float, float]]): A list of (g, s) coordinates to plot.
        """
        if channel in app.plots_to_show:
            x, y = app.phasors_charts[channel].getData()
            if x is None:
                x = np.array([])
                y = np.array([])
            new_x = [p[0] for p in phasors]
            new_y = [p[1] for p in phasors]
            x = np.concatenate((x, new_x))
            y = np.concatenate((y, new_y))
            app.phasors_charts[channel].setData(x, y)
            pass  
        
        
    @staticmethod
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
        if channel in app.plots_to_show and channel in app.phasors_widgets:
            if channel in app.phasors_lifetime_points:
                app.phasors_widgets[channel].removeItem(
                    app.phasors_lifetime_points[channel]
                )
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
            fex = (1 / laser_period_ns) * 10e8
            k = 1 / (2 * np.pi * harmonic * fex)
            phi = np.arctan(tau_phi / k)
            factor = (tau_m / k) ** 2
            m = np.sqrt(1 / (1 + factor))
            g = m * np.cos(phi)
            s = m * np.sin(phi)
            scatter = pg.ScatterPlotItem(
                x=g, y=s, size=8, pen=None, brush="red", symbol="o"
            )
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
        
        
    @staticmethod
    def initialize_phasor_feature(app):
        """
        Initializes all features for the phasor plots.

        This includes setting the cursor, drawing crosshairs, and adding the
        reference lifetime points.

        Args:
            app: The main application instance.
        """
        from core.controls_controller import ControlsController
        frequency_mhz = ControlsController.get_current_frequency_mhz(app)
        if frequency_mhz != 0:
            laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0
            for _, channel in enumerate(app.plots_to_show):
                if app.acquire_read_mode == "acquire":
                    if channel in app.phasors_widgets:
                        app.phasors_widgets[channel].setCursor(
                            Qt.CursorShape.BlankCursor
                        )
                        PhasorsController.generate_coords(app, channel)
                        PhasorsController.create_phasor_crosshair(app,
                            channel, app.phasors_widgets[channel]
                        )
                PhasorsController.draw_lifetime_points_in_phasors(
                    app,
                    channel,
                    app.control_inputs[s.HARMONIC_SELECTOR].currentIndex() + 1,
                    laser_period_ns,
                    frequency_mhz,
                )         
        
    
    @staticmethod
    def clear_phasors_points(app):
        """
        Clears all raw data points from the phasor plots.

        Args:
            app: The main application instance.
        """
        for ch in app.plots_to_show:
            if ch in app.phasors_charts:
                app.phasors_charts[ch].setData([], [])   
                
                
    @staticmethod
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
                app.phasors_widgets[ch].removeItem(feature[ch])            
                
    
    @staticmethod
    def calculate_phasors_points_mean(app, channel_index, harmonic):
        """
        Calculates the mean G and S values for a given channel and harmonic.

        Args:
            app: The main application instance.
            channel_index (int): The channel to perform the calculation for.
            harmonic (int): The harmonic number.

        Returns:
            tuple[float | None, float | None]: A tuple containing the mean G and S
                                               values, or (None, None) if no
                                               data is available.
        """
        x = [p[0] for p in app.all_phasors_points[channel_index][harmonic]]
        y = [p[1] for p in app.all_phasors_points[channel_index][harmonic]]
        g_values = np.array(x)
        s_values = np.array(y)
        if (
            g_values.size == 0
            or s_values.size == 0
            or np.all(np.isnan(g_values))
            or np.all(np.isnan(s_values))
        ):
            return None, None
        mean_g = np.nanmean(g_values)
        mean_s = np.nanmean(s_values)
        return mean_g, mean_s
    
    
    @staticmethod
    def generate_phasors_cluster_center(app, harmonic):
        """
        Calculates and draws the center of the phasor data cluster.

        The center is marked with a yellow 'x' on the plot.

        Args:
            app: The main application instance.
            harmonic (int): The harmonic number to use for the calculation.
        """
        for i, channel_index in enumerate(app.plots_to_show):
            if channel_index in app.phasors_widgets:
                cluster_center_in_list = channel_index in app.phasors_clusters_center
                if cluster_center_in_list:
                    app.phasors_widgets[channel_index].removeItem(
                        app.phasors_clusters_center[channel_index]
                    )
                mean_g, mean_s = PhasorsController.calculate_phasors_points_mean(
                    app, channel_index, harmonic
                )
                if mean_g is None or mean_s is None:
                    continue
                scatter = pg.ScatterPlotItem(
                    [mean_g],
                    [mean_s],
                    size=20,
                    pen={
                        "color": "yellow",
                        "width": 4,
                    },
                    symbol="x",
                )
                scatter.setZValue(2)
                app.phasors_widgets[channel_index].addItem(scatter)
                app.phasors_clusters_center[channel_index] = scatter    
                
                
    @staticmethod
    def generate_phasors_legend(app, harmonic):
        """
        Generates and displays a legend with mean G/S and calculated tau values.

        Args:
            app: The main application instance.
            harmonic (int): The harmonic number for which to calculate the values.
        """
        from core.controls_controller import ControlsController
        for i, channel_index in enumerate(app.plots_to_show):
            # Use the fixed legend label if available, otherwise fall back to plot-based legend
            if hasattr(app, 'phasors_legend_labels') and channel_index in app.phasors_legend_labels:
                legend_label = app.phasors_legend_labels[channel_index]
                
                mean_g, mean_s = PhasorsController.calculate_phasors_points_mean(
                    app, channel_index, harmonic
                )
                if mean_g is None or mean_s is None:
                    legend_label.setVisible(False)
                    continue
                    
                freq_mhz = ControlsController.get_frequency_mhz(app)
                tau_phi, tau_m, tau_n = PhasorsController.calculate_tau(mean_g, mean_s, freq_mhz, harmonic)
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
   
                
    
    @staticmethod
    def hide_phasors_legends(app):
        """
        Hides all phasor legends (both fixed labels and plot-based legends).

        Args:
            app: The main application instance.
        """
        # Hide fixed legend labels
        if hasattr(app, 'phasors_legend_labels'):
            for channel_index, legend_label in app.phasors_legend_labels.items():
                legend_label.setVisible(False)
        
        # Hide plot-based legends
        for channel_index in app.phasors_legends:
            if channel_index in app.phasors_widgets:
                app.phasors_widgets[channel_index].removeItem(
                    app.phasors_legends[channel_index]
                )
        app.phasors_legends.clear()        
         
         
    @staticmethod       
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
            
        
        
    @staticmethod
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
                lambda event, ccc=channel_index: PhasorsController.on_phasors_mouse_moved(app, event, ccc)
            )
            app.phasors_coords[channel_index] = coord_text
        else:
            app.phasors_coords[channel_index] = coord_text
        coord_text.setZValue(10)
        crosshair.setZValue(6)
        app.phasors_widgets[channel_index].addItem(coord_text, ignoreBounds=True)
        app.phasors_widgets[channel_index].addItem(crosshair, ignoreBounds=True)
        
    
    @staticmethod
    def calculate_tau(g, s, freq_mhz, harmonic):
        """
        Calculates phase (𝜏ϕ), modulation (𝜏m) and 𝜏n lifetimes from G/S coordinates.

        Args:
            g (float): The G coordinate.
            s (float): The S coordinate.
            freq_mhz (float): The laser frequency in MHz.
            harmonic (int): The harmonic number.

        Returns:
            tuple[float | None, float | None, float | None]: A tuple containing (tau_phi, tau_m, tau_n).
                                               Returns (None, None, None) if calculation
                                               is not possible.
        """
        if freq_mhz == 0.0:
            return None, None, None
        tau_phi = (1 / (2 * np.pi * freq_mhz * harmonic)) * (s / g) * 1e3
        tau_m_component = (1 / (s**2 + g**2)) - 1
        if tau_m_component < 0:
            tau_m = None
        else:
            tau_m = (1 / (2 * np.pi * freq_mhz * harmonic)) * np.sqrt(tau_m_component) * 1e3
        tau_n = PhasorsController.calculate_tau_n(complex(g, s), freq_mhz * harmonic) * 1e3  # Convert to ns
        return tau_phi, tau_m, tau_n
    
    
    
    @staticmethod
    def calculate_tau_n(r, freq):
        """
        Compute fluorescence lifetime from phasor projection.

        The function projects the phasor point(s) normally onto the
        universal semicircle (the "single-lifetime semicircle"),
        yielding the corresponding fluorescence lifetime.

        Parameters
        ----------
        r : array-like (complex or ndarray of complex)
            Phasor values, where the real part corresponds to the
            cosine component and the imaginary part to the sine component
            of the Fourier transform at the given modulation frequency.
            - r can be a single complex number, a 1D array, or an nD array.
        freq : float, optional
            Modulation frequency (same frequency at which r was calculated).
            Units do not matter (Hz, MHz, etc.), as the lifetime will
            simply be expressed in the inverse unit (s, ns, etc.).

        Returns
        -------
        tau : ndarray of floats
            Estimated fluorescence lifetime(s), with the same shape as `r`.

        Notes
        -----
        - r is dimensionless, but it must have been obtained by Fourier
        transform at the same `freq` you provide here.
        - The projection formula comes from phasor FLIM theory, where
        a single-exponential decay maps onto a semicircle in phasor space.
        - The method ensures that the estimated lifetime corresponds to
        the perpendicular projection from the phasor point to the semicircle.
        """
        shifted = r - 0.5
        phi = np.angle(shifted)
        tau = np.tan(phi / 2) / (2 * np.pi * freq)
        return tau
    
            
        
    @staticmethod
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
        except:
            return
        mouse_point = phasor_widget.plotItem.vb.mapSceneToView(event)
        crosshair.setPos(mouse_point.x(), mouse_point.y())
        crosshair.setText(s.CURSOR_TEXT)
        text.setPos(mouse_point.x(), mouse_point.y())
        freq_mhz = ControlsController.get_current_frequency_mhz(app)
        harmonic = int(app.control_inputs[s.HARMONIC_SELECTOR].currentText())
        g = mouse_point.x()
        s_coord = mouse_point.y()
        tau_phi, tau_m, tau_n = PhasorsController.calculate_tau(g, s_coord, freq_mhz, harmonic)
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
            text.setText(f"𝜏ϕ={round(tau_phi, 2)} ns; 𝜏m={round(tau_m, 2)} ns; 𝜏n={round(tau_n, 2)} ns")
            text.setHtml(
                '<div style="background-color: rgba(0, 0, 0, 0.5);">{}</div>'.format(
                    f"𝜏ϕ={round(tau_phi, 2)} ns; 𝜏n={round(tau_n, 2)} ns; 𝜏m={round(tau_m, 2)} ns"
                )
            )
                     
   
    @staticmethod
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
            image_item.setLookupTable(
                PhasorsController.create_cool_colormap().getLookupTable(0, 1.0)
            )
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
                PhasorsController.generate_colorbar(app, channel_index, h_min, h_max)
            PhasorsController.clear_phasors_points(app) 
            
    
    @staticmethod
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
        colorbar.setColorMap(PhasorsController.create_cool_colormap(0, 1))
        colorbar.setLabels({f"{min_value}": 0, f"{max_value}": 1})
        app.phasors_widgets[channel_index].addItem(colorbar)
        app.phasors_colorbars[channel_index] = colorbar
        
        
        
    @staticmethod
    def create_hot_colormap():
        """
        Creates a 'hot' colormap (black -> red -> yellow -> white).

        Returns:
            pg.ColorMap: A pyqtgraph ColorMap object.
        """
        # Create the color stops from black to red to yellow to white
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
    
    
    @staticmethod
    def create_cool_colormap(start=0.0, end=1.0):
        """
        Creates a 'cool' colormap (cyan -> magenta).

        Args:
            app: The main application instance (currently unused).
            start (float, optional): The starting position for the colormap. Defaults to 0.0.
            end (float, optional): The ending position for the colormap. Defaults to 1.0.

        Returns:
            pg.ColorMap: A pyqtgraph ColorMap object.
        """
        # Define the color stops from cyan to magenta
        pos = np.array([start, end])
        color = np.array(
            [[0, 255, 255, 255], [255, 0, 255, 255]],  # Cyan  # Magenta
            dtype=np.float32,
        )
        cmap = pg.ColorMap(pos, color)
        return cmap

