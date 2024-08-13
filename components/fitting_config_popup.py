import os
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QSize
from PyQt6.QtGui import QCursor, QGuiApplication, QIcon, QMovie
from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QApplication,
    QSizePolicy,
    QScrollArea,
    QGridLayout,
)
from components.gui_styles import GUIStyles
from components.layout_utilities import draw_layout_separator
from components.resource_path import resource_path
from components.select_control import SelectControl
from components.switch_control import SwitchControl
from fit_decay_curve import fit_decay_curve

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))

# Define style constants
DARK_THEME_BG_COLOR = "#141414"
DARK_THEME_TEXT_COLOR = "#cecece"
DARK_THEME_TEXT_FONT_SIZE = "20px"
DARK_THEME_HEADER_FONT_SIZE = "20px"
DARK_THEME_FONT_FAMILY = "Montserrat"
DARK_THEME_RADIO_BTN_STYLE = (
    f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: {DARK_THEME_TEXT_COLOR}"
)
DARK_THEME_LABEL_STYLE = (
    f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: {DARK_THEME_TEXT_COLOR}"
)

class FittingDecayConfigPopup(QWidget):
    def __init__(self, window, data):
        super().__init__()
        self.app = window
        self.data = data
        self.setWindowTitle("Spectroscopy - Fitting Decay Config")
        self.setWindowIcon(QIcon(resource_path("assets/spectroscopy-logo.png")))
        self.setStyleSheet(
            f"background-color: {DARK_THEME_BG_COLOR}; color: {DARK_THEME_TEXT_COLOR}"
        )
        self.setWindowState(Qt.WindowState.WindowMaximized)
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_bar = self.create_controls_bar()
        self.main_layout.addWidget(self.controls_bar)
        self.main_layout.addSpacing(10)
        self.loading_row = self.create_loading_row()
        self.main_layout.addLayout(self.loading_row)
        self.main_layout.addSpacing(10)
        self.plot_widgets = {}
        self.residuals_widgets = {}
        self.fitted_params_labels = {}
        self.placeholder_labels = {}
        
        # Create a scroll area for the plots
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("background-color: #141414; border: none;")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.scroll_widget = QWidget()
        self.plot_layout = QGridLayout(self.scroll_widget)
        self.plot_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        for index, data_point in enumerate(self.data):
            self.display_plot(data_point["title"], index)
        self.scroll_widget.setLayout(self.plot_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area)
        self.main_layout.addSpacing(20)
        self.setLayout(self.main_layout)
        self.update_model_text()

    def create_controls_bar(self):
        controls_bar_widget = QWidget()
        controls_bar_widget.setStyleSheet("background-color: #1c1c1c")
        controls_bar = QVBoxLayout()
        controls_bar.setContentsMargins(0, 20, 0, 0)
        controls_row = QHBoxLayout()
        controls_row.setAlignment(Qt.AlignmentFlag.AlignBaseline)
        controls_row.addSpacing(20)
        # Components select
        n_components_options = [f"{i} Component(s)" for i in range(1, 5)]
        _, self.components_select, __ = SelectControl.setup(
            "Components number:",
            0,
            controls_row,
            n_components_options,
            self.update_model_text,
            width=150,
            control_layout="horizontal"
        )
        self.components_select.setStyleSheet(GUIStyles.set_input_select_style())
        self.components_select.setFixedHeight(40)
        # B component switch
        b_component_container = QHBoxLayout()
        self.b_component_switch = SwitchControl(
            active_color="#11468F",
            checked=False,
        )
        self.b_component_switch.toggled.connect(self.update_model_text)
        b_component_container.addWidget(QLabel("Include B Component:"))
        b_component_container.addSpacing(8)
        b_component_container.addWidget(self.b_component_switch)
        controls_row.addLayout(b_component_container)
        controls_row.addSpacing(20)
        # Model text
        self.model_text = QLabel("")
        self.model_text.setStyleSheet(
            f"font-size: 14px; color: #1E90FF; font-family: {DARK_THEME_FONT_FAMILY};"
        )
        controls_row.addWidget(self.model_text)
        controls_row.addSpacing(20)
        # Export fitting data btn
        self.export_fitting_btn = QPushButton("EXPORT")
        self.export_fitting_btn.setStyleSheet(
            "border: 1px solid #11468F; font-family: Montserrat; color:  #11468F; font-weight: bold; padding: 8px; border-radius: 4px;"
        )
        self.export_fitting_btn.setFixedHeight(55)
        self.export_fitting_btn.setFixedWidth(90)
        self.export_fitting_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_fitting_btn.setEnabled(False)
        # Start fitting btn
        start_fitting_btn = QPushButton("START FITTING")
        start_fitting_btn.setObjectName("btn")
        GUIStyles.set_start_btn_style(start_fitting_btn)
        start_fitting_btn.setFixedHeight(55)
        start_fitting_btn.setFixedWidth(150)
        start_fitting_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_fitting_btn.clicked.connect(self.start_fitting)
        controls_row.addStretch(1)
        controls_row.addWidget(self.export_fitting_btn)
        controls_row.addSpacing(10)
        controls_row.addWidget(start_fitting_btn)
        controls_row.addSpacing(20)
        controls_bar.addLayout(controls_row)
        controls_bar.addWidget(draw_layout_separator())
        controls_bar_widget.setLayout(controls_bar)
        return controls_bar_widget


    def create_loading_row(self):
        loading_row = QHBoxLayout()
        loading_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_row.addSpacing(20)
        self.loading_text = QLabel("Processing data...")
        self.loading_text.setStyleSheet("font-family: Montserrat; font-size: 18px; font-weight: bold; color: #50b3d7")
        loading_gif = QMovie(resource_path("assets/loading.gif"))
        self.gif_label = QLabel()
        self.gif_label.setMovie(loading_gif)
        loading_gif.setScaledSize(QSize(36, 36))
        loading_gif.start()
        loading_row.addWidget(self.loading_text)
        loading_row.addSpacing(5)
        loading_row.addWidget(self.gif_label)
        self.loading_text.setVisible(False)
        self.gif_label.setVisible(False)  
        return loading_row
        
    def update_model_text(self):
        num_components = self.components_select.currentIndex() + 1
        include_b = self.b_component_switch.isChecked()
        if num_components == -1:
            self.model_text.setText("")
            return
        model_text = "Model: "
        terms = [f"A{i} * exp(-t / tau{i})" for i in range(1, num_components + 1)]
        if include_b:
            terms.append("B")
        model_text += " + ".join(terms)
        self.model_text.setText(model_text)

    def start_fitting(self):
        num_components = self.components_select.currentIndex() + 1
        include_b = self.b_component_switch.isChecked()
        if num_components == -1:
            print("Please select the number of components.")
            return
        self.loading_text.setVisible(True)
        self.gif_label.setVisible(True)
        self.worker = FittingWorker(self.data, num_components, include_b)
        self.worker.fitting_done.connect(self.handle_fitting_done)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.start()
        
        
    @pyqtSlot(list)
    def handle_fitting_done(self, results):
        self.loading_text.setVisible(False)
        self.gif_label.setVisible(False)        
        # Process results
        for title, result in results:
            if "error" in result:
                self.display_error(result["error"], title)
            else:
                index = next((i for i, item in enumerate(self.data) if item["title"] == title), None)
                if index is not None:
                    self.update_plot(result, index)
        # Enable and style the export button
        self.export_fitting_btn.setEnabled(True)
        self.export_fitting_btn.setStyleSheet(
            "border: 1px solid #11468F; font-family: Montserrat; color:#11468F; background-color: white; font-weight: bold; padding: 8px; border-radius: 4px;"
        )
        
    @pyqtSlot(str)
    def handle_error(self, error_message):
        self.loading_text.setVisible(False)
        self.gif_label.setVisible(False)        
        print(f"Error: {error_message}")

    def perform_fitting(self):
        num_components = self.components_select.currentIndex() + 1
        include_b = self.b_component_switch.isChecked()
        for index, data_point in enumerate(self.data):
            result = self.get_plotted_data(
                data_point["x"],
                data_point["y"],
                data_point["title"],
                num_components,
                include_b,
            )
            if "error" in result:
                self.display_error(result["error"], data_point["title"])
            else:
                self.update_plot(result, index)
        self.export_fitting_btn.setEnabled(True)
        self.export_fitting_btn.setStyleSheet(
            "border: 1px solid #11468F; font-family: Montserrat; color:#11468F; background-color: white; font-weight: bold; padding: 8px; border-radius: 4px;"
        )

    def clear_plots(self):
        for i in reversed(range(self.plot_layout.count())):
            widget_to_remove = self.plot_layout.itemAt(i).widget()
            self.plot_layout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)

    def get_plotted_data(
        self, x_values, y_values, plot_title, num_components, B_component
    ):
        result = fit_decay_curve(
            x_values, y_values, plot_title, num_components, B_component
        )
        if "error" in result:
            return {"error": result["error"]}
        return result

    def display_plot(self, title, index):
        layout = QVBoxLayout()
        title_layout = QHBoxLayout()
        chart_title = QLabel(title)
        chart_title.setStyleSheet("color: #cecece; font-size: 18px; font-family: Montserrat; text-align: center;")
        title_layout.addWidget(chart_title)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(title_layout)
        placeholder_label = QLabel("Plot will be available after fitting is complete...")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setStyleSheet("color: #cecece; font-size: 14px; font-family: Montserrat;")
        plot_widget = pg.PlotWidget()
        plot_widget.setMinimumHeight(250)
        plot_widget.setBackground("#0a0a0a")
        plot_widget.setLabel("left", "Counts", color="white")
        plot_widget.setLabel("bottom", "Time", color="white")
        plot_widget.getAxis("left").setPen("white")
        plot_widget.getAxis("bottom").setPen("white")        
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        residuals_widget = pg.PlotWidget()
        residuals_widget.setMinimumHeight(150)
        residuals_widget.setBackground("#0a0a0a")
        residuals_widget.setLabel("left", "Residuals", color="white")
        residuals_widget.setLabel("bottom", "Time", color="white")
        residuals_widget.getAxis("left").setPen("white")
        residuals_widget.getAxis("bottom").setPen("white")        
        residuals_widget.showGrid(x=True, y=True, alpha=0.3)
        layout.addWidget(placeholder_label)
        layout.addWidget(plot_widget, stretch=2)
        layout.addWidget(residuals_widget, stretch=1)
        fitted_params_text = QLabel("Fitted parameters will be displayed here.")
        fitted_params_text.setStyleSheet("color: #cecece; font-family: Montserrat;")
        layout.addWidget(fitted_params_text)
        charts_wrapper = QWidget()
        charts_wrapper.setContentsMargins(10, 10, 10, 10)
        charts_wrapper.setObjectName("chart_wrapper")
        charts_wrapper.setLayout(layout)
        charts_wrapper.setStyleSheet(GUIStyles.chart_wrapper_style())
        self.add_chart_to_grid(charts_wrapper, index)
        self.plot_widgets[index] = plot_widget
        self.residuals_widgets[index] = residuals_widget
        self.fitted_params_labels[index] = fitted_params_text
        self.placeholder_labels[index] = placeholder_label

    def update_plot(self, result, index):
        plot_widget = self.plot_widgets[index]
        residuals_widget = self.residuals_widgets[index]
        fitted_params_text = self.fitted_params_labels[index]
        placeholder_label = self.placeholder_labels[index]
        placeholder_label.setVisible(False)
        truncated_x_values = result["x_values"][result["decay_start"] :]
        plot_widget.clear() 
        legend = plot_widget.addLegend(offset=(0, 20))
        legend.setParent(plot_widget)        
        plot_widget.plot(
            truncated_x_values,
            np.array(result["y_data"]) * result["scale_factor"],
            pen=None,
            symbol="o",
            symbolSize=3,
            symbolBrush="lime",
            name="Counts",
        )
        plot_widget.plot(
            result["t_data"],
            result["fitted_values"] * result["scale_factor"],
            pen=pg.mkPen("#f72828", width=2),
            name="Fitted curve",
        )
        residuals = np.concatenate(
            (np.full(result["decay_start"], 0), result["residuals"])
        )
        residuals_widget.clear()
        residuals_widget.plot(
            result["x_values"], residuals, pen=pg.mkPen("#1E90FF", width=2)
        )
        residuals_widget.addLine(y=0, pen=pg.mkPen("w", style=Qt.PenStyle.DashLine))
        fitted_params_text.setText(result["fitted_params_text"])

    def add_chart_to_grid(self, chart_widget, index):
        col_length = 1
        if len(self.data) > 4:
            col_length = 4
        else:
            col_length = len(self.data)
        self.plot_layout.addWidget(
            chart_widget, index // col_length, index % col_length
        )

    def display_error(self, error_message, title):
        error_label = QLabel(f"Error in {title}: {error_message}")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet(
            f"font-size: {DARK_THEME_TEXT_FONT_SIZE}; color: red; background-color: {DARK_THEME_BG_COLOR};"
        )
        self.plot_layout.addWidget(error_label)

    def center_window(self):
        screen_number = self.get_current_screen()
        if screen_number == -1:
            screen = QGuiApplication.primaryScreen()
        else:
            screen = QGuiApplication.screens()[screen_number]

        screen_geometry = screen.geometry()
        frame_gm = self.frameGeometry()
        screen_center = screen_geometry.center()
        frame_gm.moveCenter(screen_center)
        self.move(frame_gm.topLeft())

    @staticmethod
    def get_current_screen():
        cursor_pos = QCursor.pos()
        screens = QGuiApplication.screens()
        for screen_number, screen in enumerate(screens):
            if screen.geometry().contains(cursor_pos):
                return screen_number
        return -1
    
    
    
class FittingWorker(QThread):
    fitting_done = pyqtSignal(list)  # Emit a list of tuples (chart title (channel),  fitting result)
    error_occurred = pyqtSignal(str)  # Emit an error message
    def __init__(self, data, num_components, include_b, parent=None):
        super().__init__(parent)
        self.data = data
        self.num_components = num_components
        self.include_b = include_b
    def run(self):
        results = []
        for data_point in self.data:
            try:
                result = fit_decay_curve(
                    data_point["x"],
                    data_point["y"],
                    data_point["title"],
                    self.num_components,
                    self.include_b,
                )
                results.append((data_point["title"], result))
            except Exception as e:
                self.error_occurred.emit(f"An error occurred: {str(e)}")
                return
        self.fitting_done.emit(results)    


if __name__ == "__main__":

    def generate_fake_decay_data(num_bins=256, x_max=12.5):
        import numpy as np

        x_values = np.linspace(0, x_max, num_bins)

        # Create an initial rapid increase using a sigmoid function
        increase_length = num_bins // 10
        decay_length = num_bins - increase_length

        sigmoid = 1 / (
            1
            + np.exp(
                -10 * (x_values[:increase_length] - 0.5 * x_values[increase_length])
            )
        )
        sigmoid = sigmoid / sigmoid[-1] * 1000  # Normalize to a range of counts

        # Create a smooth exponential decay that starts from the last point of increase
        decay = np.exp(-0.3 * (x_values[increase_length:] - x_values[increase_length]))
        decay = decay * sigmoid[-1]  # Ensure continuity

        # Concatenate the increase and decay parts
        y_values = np.concatenate([sigmoid, decay])
        y_values = y_values[
            :num_bins
        ]  # Ensure y_values has the same length as x_values

        # Add random noise with lower amplitude
        noise = np.random.normal(0, 0.02 * np.max(y_values), num_bins)
        y_values = y_values + noise
        y_values = np.maximum(y_values, 0)  # Ensure no negative counts

        return x_values, y_values

    def main():
        sample_data = [
            {"x": channel_data[0], "y": channel_data[1], "title": f"Channel {i + 1}"}
            for i, channel_data in enumerate(
                [generate_fake_decay_data() for _ in range(3)]
            )
        ]
        app = QApplication([])
        window = FittingDecayConfigPopup(None, sample_data)
        window.show()
        app.exec()

    main()
