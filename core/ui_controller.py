import flim_labs
from functools import partial
from components.buttons import CollapseButton, ReadAcquireModeButton, TimeTaggerWidget
from components.channels_detection import DetectChannelsButton
from components.check_card import CheckCard
from components.fancy_checkbox import FancyButton
from components.gradient_text import GradientText
from utils.gui_styles import GUIStyles
from components.input_number_control import InputFloatControl, InputNumberControl
from components.laserblood_metadata_popup import LaserbloodMetadataPopup
from utils.layout_utilities import draw_layout_separator, hide_layout, show_layout
from components.link_widget import LinkWidget
from utils.logo_utilities import TitlebarIcon
from components.progress_bar import ProgressBar
from components.read_data import ReadDataControls
from utils.resource_path import resource_path
from components.select_control import SelectControl
from components.switch_control import SwitchControl
import settings.settings as s
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QPushButton,
    QGridLayout,
    QApplication,
)


class UIController:
    """
    A controller class with static methods to manage the user interface.

    This class is responsible for creating, arranging, and styling all UI
    components of the application. It centralizes UI logic to keep the main
    application class cleaner and more focused on state management.
    """

    @staticmethod
    def init_ui(app):
        """
        Initializes the main application window and its core layout.

        Sets the window title, icon, theme, and restores its previous size
        and position. It creates the main layout structure where all other
        widgets will be placed.

        Args:
            app: The main application instance (subclass of QWidget).

        Returns:
            tuple[QWidget, QGridLayout]: A tuple containing the top bar container
                                         widget and the main grid layout for plots.
        """
        app.setWindowTitle(
            "FlimLabs - SPECTROSCOPY LASERBLOOD v"
            + s.VERSION
            + " - API v"
            + flim_labs.get_version()
        )
        TitlebarIcon.setup(app)
        GUIStyles.customize_theme(app)
        main_layout = QVBoxLayout()
        top_bar = UIController.create_top_bar(app)
        main_layout.addWidget(top_bar, 0, Qt.AlignmentFlag.AlignTop)
        # Time tagger progress bar
        time_tagger_progress_bar = ProgressBar(
            visible=False, indeterminate=True, label_text="Time tagger processing..."
        )
        app.widgets[s.TIME_TAGGER_PROGRESS_BAR] = time_tagger_progress_bar
        main_layout.addWidget(time_tagger_progress_bar)
        reference_banner = UIController.create_ref_data_info_banner(app)
        main_layout.addLayout(reference_banner[0])
        main_layout.addSpacing(5)
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        app.setLayout(main_layout)
        app.resize(
            app.settings.value("size", QSize(s.APP_DEFAULT_WIDTH, s.APP_DEFAULT_HEIGHT))
        )
        app.move(
            app.settings.value(
                "pos",
                QApplication.primaryScreen().geometry().center()
                - app.frameGeometry().center(),
            )
        )
        return top_bar, grid_layout

    @staticmethod
    def create_top_bar(app):
        """
        Creates the entire top bar widget containing all controls and headers.

        This method assembles the logo, tabs, metadata buttons, and the
        collapsible area with channel selectors and control inputs.

        Args:
            app: The main application instance.

        Returns:
            QWidget: A container widget for the entire top bar.
        """
        from core.controls_controller import ControlsController

        top_bar = QVBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setAlignment(Qt.AlignmentFlag.AlignTop)
        top_collapsible_widget = QWidget()
        top_collapsible_layout = QVBoxLayout()
        top_collapsible_layout.setContentsMargins(0, 0, 0, 0)
        top_collapsible_layout.setSpacing(0)
        app.widgets[s.TOP_COLLAPSIBLE_WIDGET] = top_collapsible_widget
        top_bar_header = QHBoxLayout()
        top_bar_header.addSpacing(10)
        top_bar_header.addLayout(UIController.create_logo_and_title(app))
        # add hlayout
        tabs_layout = QHBoxLayout()
        # set height of parent
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        # no spacing
        tabs_layout.setSpacing(0)
        app.control_inputs[s.TAB_SPECTROSCOPY] = QPushButton("SPECTROSCOPY")
        app.control_inputs[s.TAB_SPECTROSCOPY].setFlat(True)
        app.control_inputs[s.TAB_SPECTROSCOPY].setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        app.control_inputs[s.TAB_SPECTROSCOPY].setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        app.control_inputs[s.TAB_SPECTROSCOPY].setCheckable(True)
        GUIStyles.set_config_btn_style(app.control_inputs[s.TAB_SPECTROSCOPY])
        app.control_inputs[s.TAB_SPECTROSCOPY].setChecked(True)
        app.control_inputs[s.TAB_SPECTROSCOPY].clicked.connect(
            lambda: ControlsController.on_tab_selected(app, s.TAB_SPECTROSCOPY)
        )
        tabs_layout.addWidget(app.control_inputs[s.TAB_SPECTROSCOPY])
        app.control_inputs[s.TAB_PHASORS] = QPushButton("PHASORS")
        app.control_inputs[s.TAB_PHASORS].setFlat(True)
        app.control_inputs[s.TAB_PHASORS].setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        app.control_inputs[s.TAB_PHASORS].setCursor(Qt.CursorShape.PointingHandCursor)
        app.control_inputs[s.TAB_PHASORS].setCheckable(True)
        GUIStyles.set_config_btn_style(app.control_inputs[s.TAB_PHASORS])
        app.control_inputs[s.TAB_PHASORS].clicked.connect(
            lambda: ControlsController.on_tab_selected(app, s.TAB_PHASORS)
        )
        tabs_layout.addWidget(app.control_inputs[s.TAB_PHASORS])
        app.control_inputs[s.TAB_FITTING] = QPushButton("FITTING")
        app.control_inputs[s.TAB_FITTING].setFlat(True)
        app.control_inputs[s.TAB_FITTING].setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        app.control_inputs[s.TAB_FITTING].setCursor(Qt.CursorShape.PointingHandCursor)
        app.control_inputs[s.TAB_FITTING].setCheckable(True)
        GUIStyles.set_config_btn_style(app.control_inputs[s.TAB_FITTING])
        app.control_inputs[s.TAB_FITTING].clicked.connect(
            lambda: ControlsController.on_tab_selected(app, s.TAB_FITTING)
        )
        tabs_layout.addWidget(app.control_inputs[s.TAB_FITTING])
        top_bar_header.addLayout(tabs_layout)
        top_bar_header.addStretch(1)
        # LASERBLOOD METADATA
        laserblood_btn_box = QVBoxLayout()
        laserblood_btn_box.setSpacing(0)
        laserblood_btn_box.setContentsMargins(0, 8, 0, 0)
        laserblood_metadata_btn = QPushButton(" METADATA")
        laserblood_metadata_btn.setIcon(
            QIcon(resource_path("assets/laserblood-logo.png"))
        )
        laserblood_metadata_btn.setIconSize(QSize(50, 100))
        laserblood_metadata_btn.setFixedWidth(160)
        laserblood_metadata_btn.setFixedHeight(45)
        laserblood_metadata_btn.setStyleSheet(
            "font-family: Montserrat; font-weight: bold; background-color: white; color: #014E9C; padding: 0 14px;"
        )
        laserblood_metadata_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        laserblood_metadata_btn.clicked.connect(
            lambda: ControlsController.open_laserblood_metadata_popup(app)
        )
        laserblood_btn_box.addWidget(laserblood_metadata_btn)
        top_bar_header.addLayout(laserblood_btn_box)
        top_bar_header.addSpacing(10)
        # ACQUIRE/READ MODE
        read_acquire_button_row = ReadAcquireModeButton(app)
        top_bar_header.addWidget(read_acquire_button_row)
        top_bar_header.addSpacing(10)

        info_link_widget, export_data_control = UIController.create_export_data_input(
            app
        )
        file_size_info_layout = UIController.create_file_size_info_row(app)
        top_bar_header.addWidget(
            info_link_widget, alignment=Qt.AlignmentFlag.AlignBottom
        )
        top_bar_header.addLayout(export_data_control)
        export_data_control.addSpacing(10)
        top_bar_header.addLayout(file_size_info_layout)
        top_bar_header.addSpacing(10)
        # Time Tagger
        time_tagger = TimeTaggerWidget(app)
        top_bar_header.addWidget(time_tagger)
        top_bar_header.addSpacing(10)
        top_bar.addLayout(top_bar_header)
        channels_widget = QWidget()
        sync_buttons_widget = QWidget()
        channels_widget.setLayout(UIController.create_channel_selector(app))
        sync_buttons_widget.setLayout(UIController.create_sync_buttons(app))
        top_collapsible_layout.addWidget(channels_widget, 0, Qt.AlignmentFlag.AlignTop)
        top_collapsible_layout.addWidget(
            sync_buttons_widget, 0, Qt.AlignmentFlag.AlignTop
        )
        top_collapsible_widget.setLayout(top_collapsible_layout)
        top_bar.addWidget(top_collapsible_widget)
        top_bar.addLayout(UIController.create_control_inputs(app))
        top_bar.addWidget(draw_layout_separator())
        top_bar.addSpacing(5)
        container = QWidget()
        container.setLayout(top_bar)
        return container

    @staticmethod
    def create_logo_and_title(app):
        """
        Creates the application logo and title section.

        Args:
            app: The main application instance.

        Returns:
            QHBoxLayout: A layout containing the logo and title.
        """
        row = QHBoxLayout()
        pixmap = QPixmap(
            resource_path("assets/spectroscopy-logo-white.png")
        ).scaledToWidth(30)
        ctl = QLabel(pixmap=pixmap)
        row.addWidget(ctl)
        row.addSpacing(10)
        ctl_layout = QVBoxLayout()
        ctl_layout.setContentsMargins(0, 20, 0, 0)
        ctl = GradientText(
            app,
            text="SPECTROSCOPY",
            colors=[(0.7, "#1E90FF"), (1.0, s.PALETTE_RED_1)],
            stylesheet=GUIStyles.set_main_title_style(),
        )
        ctl_layout.addWidget(ctl)
        row.addLayout(ctl_layout)
        ctl = QWidget()
        ctl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(ctl)
        return row

    @staticmethod
    def create_export_data_input(app):
        """
        Creates the 'Export data' switch control and an info link.

        Args:
            app: The main application instance.

        Returns:
            tuple[LinkWidget, QVBoxLayout]: A tuple containing the info link
                                            widget and the export switch layout.
        """
        from core.controls_controller import ControlsController

        export_data_active = app.write_data_gui
        # Link to export data documentation
        info_link_widget = LinkWidget(
            icon_filename=resource_path("assets/info-icon.png"),
            link="https://flim-labs.github.io/spectroscopy-py/v1.0/#gui-usage",
        )
        info_link_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        info_link_widget.show()
        # Export data switch control
        export_data_control = QVBoxLayout()
        export_data_control.setContentsMargins(0, 0, 0, 0)
        export_data_control.setSpacing(0)
        export_data_label = QLabel("Export data:")
        inp = SwitchControl(
            active_color=s.PALETTE_BLUE_1,
            width=70,
            height=30,
            checked=export_data_active,
        )
        inp.toggled.connect(partial(ControlsController.on_export_data_changed, app))
        export_data_control.addWidget(export_data_label)
        export_data_control.addSpacing(5)
        export_data_control.addWidget(inp)
        return info_link_widget, export_data_control

    @staticmethod
    def create_file_size_info_row(app):
        """
        Creates the layout for displaying the estimated file size.

        Args:
            app: The main application instance.

        Returns:
            QVBoxLayout: A layout containing the file size label.
        """
        export_data_active = app.write_data_gui
        file_size_info_layout = QVBoxLayout()
        file_size_info_layout.setContentsMargins(0, 0, 0, 0)
        file_size_info_layout.setSpacing(0)
        app.bin_file_size_label.setText("File size: " + str(app.bin_file_size))
        app.bin_file_size_label.setStyleSheet("QLabel { color : #f8f8f8; }")
        file_size_info_layout.addSpacing(15)
        file_size_info_layout.addWidget(app.bin_file_size_label)
        (
            app.bin_file_size_label.show()
            if export_data_active
            else app.bin_file_size_label.hide()
        )
        return file_size_info_layout

    @staticmethod
    def _create_basic_controls(app, layout):
        """
        Creates basic acquisition controls like bin width, time span, etc.

        Args:
            app: The main application instance.
            layout (QLayout): The layout to add the controls to.
        """
        from core.controls_controller import ControlsController

        _, inp = InputNumberControl.setup(
            "Bin width (µs):",
            1000,
            1000000,
            int(app.settings.value(s.SETTINGS_BIN_WIDTH, s.DEFAULT_BIN_WIDTH)),
            layout,
            partial(ControlsController.on_bin_width_change, app),
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        app.control_inputs[s.SETTINGS_BIN_WIDTH] = inp

        _, inp = InputNumberControl.setup(
            "Time span (s):",
            1,
            300,
            int(app.settings.value(s.SETTINGS_TIME_SPAN, s.DEFAULT_TIME_SPAN)),
            layout,
            partial(ControlsController.on_time_span_change, app),
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        app.control_inputs[s.SETTINGS_TIME_SPAN] = inp

        switch_control = QVBoxLayout()
        inp = SwitchControl(
            active_color="#11468F",
            checked=app.settings.value(s.SETTINGS_FREE_RUNNING, s.DEFAULT_FREE_RUNNING)
            == "true",
        )
        inp.toggled.connect(partial(ControlsController.on_free_running_changed, app))
        switch_control.addWidget(QLabel("Free running:"))
        switch_control.addSpacing(8)
        switch_control.addWidget(inp)
        layout.addLayout(switch_control)
        layout.addSpacing(20)
        app.control_inputs[s.SETTINGS_FREE_RUNNING] = inp

        _, inp = InputNumberControl.setup(
            "Acquisition time (s):",
            1,
            1800,
            int(
                app.settings.value(
                    s.SETTINGS_ACQUISITION_TIME, s.DEFAULT_ACQUISITION_TIME
                )
            ),
            layout,
            partial(ControlsController.on_acquisition_time_change, app),
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        app.control_inputs[s.SETTINGS_ACQUISITION_TIME] = inp
        ControlsController.on_free_running_changed(
            app,
            app.settings.value(s.SETTINGS_FREE_RUNNING, s.DEFAULT_FREE_RUNNING)
            == "true",
        )

    @staticmethod
    def _create_pileup_sbr_controls(app, layout):
        """
        Creates controls for pile-up threshold and SBR display.

        Args:
            app: The main application instance.
            layout (QLayout): The layout to add the controls to.
        """
        from core.controls_controller import ControlsController

        cps_threshold = int(
            app.settings.value(s.SETTINGS_CPS_THRESHOLD, s.DEFAULT_CPS_THRESHOLD)
        )
        _, inp = InputNumberControl.setup(
            "Pile-up threshold (CPS):",
            0,
            100000000,
            cps_threshold,
            layout,
            partial(ControlsController.on_cps_threshold_change, app),
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style(min_width="70px"))
        app.control_inputs[s.SETTINGS_CPS_THRESHOLD] = inp
        LaserbloodMetadataPopup.set_cps_threshold(app, cps_threshold)

        show_SBR_control = QVBoxLayout()
        show_SBR_control.setContentsMargins(0, 0, 0, 0)
        show_SBR_control.setSpacing(0)
        show_SBR_label = QLabel("Show SBR:")
        inp = SwitchControl(
            active_color=s.PALETTE_BLUE_1, width=60, height=30, checked=app.show_SBR
        )
        app.control_inputs[s.SETTINGS_SHOW_SBR] = inp
        inp.toggled.connect(partial(ControlsController.on_show_SBR_changed, app))
        show_SBR_control.addWidget(show_SBR_label)
        show_SBR_control.addSpacing(5)
        show_SBR_control.addWidget(inp)
        layout.addLayout(show_SBR_control)
        layout.addSpacing(10)

    @staticmethod
    def _create_phasor_controls(app, layout):
        """
        Creates controls specific to the Phasor tab.

        Args:
            app: The main application instance.
            layout (QLayout): The layout to add the controls to.
        """
        from core.controls_controller import ControlsController

        quantize_phasors_switch_control = QVBoxLayout()
        inp_quantize = SwitchControl(
            active_color="#11468F", checked=app.quantized_phasors
        )
        inp_quantize.toggled.connect(
            partial(ControlsController.on_quantize_phasors_changed, app)
        )
        app.control_inputs[s.SETTINGS_QUANTIZE_PHASORS] = inp_quantize
        quantize_phasors_switch_control.addWidget(QLabel("Quantize Phasors:"))
        quantize_phasors_switch_control.addSpacing(8)
        quantize_phasors_switch_control.addWidget(inp_quantize)
        app.control_inputs["quantize_phasors_container"] = (
            quantize_phasors_switch_control
        )
        (
            show_layout(quantize_phasors_switch_control)
            if app.tab_selected == s.TAB_PHASORS and app.acquire_read_mode != "read"
            else hide_layout(quantize_phasors_switch_control)
        )
        layout.addLayout(quantize_phasors_switch_control)
        layout.addSpacing(20)

        phasors_resolution_container, inp, __, container = SelectControl.setup(
            "Squares:",
            app.phasors_resolution,
            layout,
            s.PHASORS_RESOLUTIONS,
            partial(ControlsController.on_phasors_resolution_changed, app),
            width=70,
        )
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        (
            show_layout(phasors_resolution_container)
            if (
                app.tab_selected == s.TAB_PHASORS
                and app.quantized_phasors
                and app.acquire_read_mode != "read"
            )
            else hide_layout(phasors_resolution_container)
        )
        app.control_inputs[s.SETTINGS_PHASORS_RESOLUTION] = inp
        app.control_inputs["phasors_resolution_container"] = (
            phasors_resolution_container
        )

    @staticmethod
    def _create_calibration_controls(app, layout):
        """
        Creates controls for calibration, TAU, and harmonics.

        Args:
            app: The main application instance.
            layout (QLayout): The layout to add the controls to.
        """
        from core.controls_controller import ControlsController

        _, inp, label, container = SelectControl.setup(
            "Calibration:",
            int(
                app.settings.value(
                    s.SETTINGS_CALIBRATION_TYPE, s.DEFAULT_SETTINGS_CALIBRATION_TYPE
                )
            ),
            layout,
            s.CALIBRATION_TYPES,
            partial(ControlsController.on_calibration_change, app),
        )
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        app.control_inputs["calibration"] = inp
        app.control_inputs["calibration_label"] = label

        label, inp = InputFloatControl.setup(
            "TAU (ns):",
            0,
            1000,
            float(app.settings.value(s.SETTINGS_TAU_NS, "0")),
            layout,
            partial(ControlsController.on_tau_change, app),
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        app.control_inputs["tau"] = inp
        app.control_inputs["tau_label"] = label

        label, inp = InputNumberControl.setup(
            "Harmonics:",
            1,
            4,
            int(app.settings.value(s.SETTINGS_HARMONIC, "1")),
            layout,
            partial(ControlsController.on_harmonic_change, app),
        )
        inp.setStyleSheet(GUIStyles.set_input_number_style())
        app.control_inputs[s.SETTINGS_HARMONIC] = inp
        app.control_inputs[s.SETTINGS_HARMONIC_LABEL] = label

    @staticmethod
    def _create_replicate_and_harmonic_controls(app, layout):
        """
        Creates controls for replicates and the harmonic display selector.

        Args:
            app: The main application instance.
            layout (QLayout): The layout to add the controls to.
        """
        from core.controls_controller import ControlsController

        ctl, inp, label, container = SelectControl.setup(
            "Harmonic displayed:",
            0,
            layout,
            ["1", "2", "3", "4"],
            partial(ControlsController.on_harmonic_selector_change, app),
        )
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        app.control_inputs[s.HARMONIC_SELECTOR_LABEL] = label
        app.control_inputs[s.HARMONIC_SELECTOR] = inp
        label.hide()
        inp.hide()

        label, inp = InputNumberControl.setup(
            "N° Replicate:",
            1,
            100000,
            int(app.replicates),
            layout,
            partial(ControlsController.on_replicate_change, app),
        )
        inp.setStyleSheet(
            GUIStyles.set_input_number_style(min_width="40px", border_color="#11468F")
        )
        app.control_inputs[s.SETTINGS_REPLICATES] = inp
        app.control_inputs["replicates_label"] = label

    @staticmethod
    def _create_fitting_controls(app, layout):
        from core.controls_controller import ControlsController

        use_deconv_switch_control = QVBoxLayout()
        use_deconv_switch_control.setContentsMargins(0, 0, 0, 0)
        use_deconv_switch_control.setSpacing(0)
        inp_use_deconv = SwitchControl(
            active_color="#11468F", checked=app.use_deconvolution
        )
        inp_use_deconv.toggled.connect(
            partial(ControlsController.on_use_deconvolution_changed, app)
        )
        app.control_inputs[s.SETTINGS_USE_DECONVOLUTION] = inp_use_deconv
        use_deconv_switch_control.addWidget(QLabel("Use Deconvolution:"))
        use_deconv_switch_control.addSpacing(5)
        use_deconv_switch_control.addWidget(inp_use_deconv)
        app.control_inputs["use_deconv_container"] = use_deconv_switch_control
        (
            show_layout(use_deconv_switch_control)
            if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode != "read"
            else hide_layout(use_deconv_switch_control)
        )
        layout.addLayout(use_deconv_switch_control)
        layout.addSpacing(20)

    @staticmethod
    def _create_action_buttons(app, layout):
        """
        Creates main action buttons like START, READ, EXPORT, etc.

        Args:
            app: The main application instance.
            layout (QLayout): The layout to add the buttons to.
        """
        from components.buttons import ExportPlotImageButton
        from core.controls_controller import ControlsController

        # LOAD REFERENCE Button
        save_button = QPushButton("LOAD REFERENCE")
        save_button.setFlat(True)
        save_button.setFixedHeight(55)
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.setHidden(True)
        save_button.clicked.connect(partial(ControlsController.on_load_reference, app))
        save_button.setStyleSheet(
            "QPushButton { background-color: #1E90FF; color: white; border-radius: 5px; padding: 5px 12px; font-weight: bold; font-size: 16px; }"
        )
        app.control_inputs[s.LOAD_REF_BTN] = save_button
        layout.addWidget(save_button)

        # EXPORT Button
        export_button = QPushButton("EXPORT")
        export_button.setFlat(True)
        export_button.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        export_button.setHidden(True)
        export_button.clicked.connect(lambda: ControlsController.export_data(app))
        export_button.setStyleSheet(
            "QPushButton { background-color: #8d4ef2; color: white; border-radius: 5px; padding: 5px 10px; font-size: 16px; }"
        )
        app.control_inputs["export_button"] = export_button
        layout.addWidget(export_button)

        # FIT Button Placeholder
        app.control_inputs[s.FIT_BTN_PLACEHOLDER] = QWidget()
        app.control_inputs[s.FIT_BTN_PLACEHOLDER].setLayout(QHBoxLayout())
        app.control_inputs[s.FIT_BTN_PLACEHOLDER].layout().setContentsMargins(
            0, 0, 0, 0
        )
        layout.addWidget(app.control_inputs[s.FIT_BTN_PLACEHOLDER])

        # START Button
        start_button = QPushButton("START")
        start_button.setFixedWidth(150)
        start_button.setObjectName("btn")
        start_button.setFlat(True)
        start_button.setFixedHeight(55)
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(
            partial(ControlsController.on_start_button_click, app)
        )
        start_button.setVisible(app.acquire_read_mode == "acquire")
        app.control_inputs["start_button"] = start_button
        layout.addWidget(start_button)

        # BIN METADATA Button
        bin_metadata_button = QPushButton()
        bin_metadata_button.setIcon(QIcon(resource_path("assets/metadata-icon.png")))
        bin_metadata_button.setIconSize(QSize(30, 30))
        bin_metadata_button.setStyleSheet("background-color: white; padding: 0 14px;")
        bin_metadata_button.setFixedHeight(55)
        bin_metadata_button.setCursor(Qt.CursorShape.PointingHandCursor)
        app.control_inputs["bin_metadata_button"] = bin_metadata_button
        bin_metadata_button.clicked.connect(
            lambda: ControlsController.open_reader_metadata_popup(app)
        )
        bin_metadata_button.setVisible(ReadDataControls.read_bin_metadata_enabled(app))
        layout.addWidget(bin_metadata_button)

        # EXPORT PLOT IMG Button
        layout.addWidget(ExportPlotImageButton(app))

        # READ BIN Button
        read_bin_button = QPushButton("READ/PLOT")
        read_bin_button.setObjectName("btn")
        read_bin_button.setFlat(True)
        read_bin_button.setFixedHeight(55)
        read_bin_button.setCursor(Qt.CursorShape.PointingHandCursor)
        app.control_inputs["read_bin_button"] = read_bin_button
        read_bin_button.clicked.connect(
            lambda: ControlsController.open_reader_popup(app)
        )
        read_bin_button.setVisible(app.acquire_read_mode == "read")
        layout.addWidget(read_bin_button)

        UIController.style_start_button(app)

    @staticmethod
    def create_control_inputs(app):
        """
        Creates and assembles the main row of control inputs.

        This function orchestrates the creation of all control widgets by
        calling the respective private helper methods and arranging them in
        a horizontal layout.

        Args:
            app: The main application instance.

        Returns:
            QHBoxLayout: The layout containing all control inputs.
        """
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 10, 0, 0)
        controls_row.addSpacing(10)

        UIController._create_basic_controls(app, controls_row)
        UIController._create_pileup_sbr_controls(app, controls_row)
        UIController._create_fitting_controls(app, controls_row)
        UIController._create_phasor_controls(app, controls_row)
        UIController._create_calibration_controls(app, controls_row)

        spacer = QWidget()
        controls_row.addWidget(spacer, 1)

        UIController._create_replicate_and_harmonic_controls(app, controls_row)
        UIController._create_action_buttons(app, controls_row)

        collapse_button = CollapseButton(app.widgets[s.TOP_COLLAPSIBLE_WIDGET])
        controls_row.addWidget(collapse_button)
        app.widgets["collapse_button"] = collapse_button
        controls_row.addSpacing(10)

        return controls_row

    @staticmethod
    def style_start_button(app):
        """
        Styles the main action button based on the application's state.

        It sets the text and stylesheet for the 'START'/'STOP' button and
        the 'READ/PLOT' button depending on the current acquisition mode.

        Args:
            app: The main application instance.
        """
        GUIStyles.set_start_btn_style(app.control_inputs["read_bin_button"])
        if app.mode == s.MODE_STOPPED:
            app.control_inputs["start_button"].setText("START")
            GUIStyles.set_start_btn_style(app.control_inputs["start_button"])
        else:
            app.control_inputs["start_button"].setText("STOP")
            GUIStyles.set_stop_btn_style(app.control_inputs["start_button"])

    @staticmethod
    def _create_channel_checkboxes(app, layout):
        """
        Creates and adds channel selection checkboxes to the given layout, supporting custom names and rename modal.
        """
        import json
        from core.controls_controller import ControlsController
        from components.rename_channel_modal import RenameChannelModal
        from utils.channel_name_utils import get_channel_name_parts

        app.channel_checkboxes.clear()
        # Load custom channel names from settings
        custom_names = {}
        if hasattr(app, "settings"):
            custom_names_json = app.settings.value("channel_names", "{}")
            try:
                custom_names = json.loads(custom_names_json)
            except Exception:
                custom_names = {}
        for i in range(s.MAX_CHANNELS):
            ch_wrapper = QWidget()
            ch_wrapper.setObjectName(f"ch_checkbox_wrapper")
            ch_wrapper.setFixedHeight(40)
            row = QHBoxLayout()
            from components.fancy_checkbox import FancyCheckbox

            custom_part, default_part = get_channel_name_parts(i, custom_names)
            fancy_checkbox = FancyCheckbox(
                text=f"Channel {i + 1}",
                label_custom_part=custom_part,
                label_default_part=default_part,
                label_clickable=True,
            )
            fancy_checkbox.setStyleSheet(GUIStyles.set_checkbox_style())
            if app.selected_channels:
                fancy_checkbox.set_checked(i in app.selected_channels)
            fancy_checkbox.toggled.connect(
                lambda checked, channel=i: ControlsController.on_channel_selected(
                    app, checked, channel
                )
            )

            def open_rename_modal(channel_idx=i, checkbox=fancy_checkbox):
                current_name = custom_names.get(str(channel_idx), "")
                modal = RenameChannelModal(channel_idx, current_name, app)

                def on_renamed(idx, new_name):
                    from utils.channel_name_utils import get_channel_name

                    # Update custom_names dict and settings
                    custom_names[str(idx)] = new_name if new_name else ""
                    app.settings.setValue("channel_names", json.dumps(custom_names))
                    # Update app.channel_names as well
                    app.channel_names[str(idx)] = new_name if new_name else ""
                    # Update label
                    custom_part, default_part = get_channel_name_parts(
                        idx, custom_names
                    )
                    checkbox.set_text_parts(custom_part, default_part)

                    # Update plot titles immediately when channel is visible
                    if idx in app.plots_to_show:
                        # Update intensity plot title
                        if idx in app.intensity_plot_widgets:
                            title = get_channel_name(idx, custom_names)
                            app.intensity_plot_widgets[idx].setTitle(
                                f"{title} intensity"
                            )

                        # Update decay plot title (only in ACQUIRE mode)
                        if (
                            app.acquire_read_mode == "acquire"
                            and idx in app.decay_widgets
                        ):
                            title = get_channel_name(idx, custom_names)
                            app.decay_widgets[idx].setTitle(f"{title} decay")

                modal.channelRenamed.connect(on_renamed)
                modal.exec()

            fancy_checkbox.labelClicked.connect(open_rename_modal)
            row.addWidget(fancy_checkbox)
            ch_wrapper.setLayout(row)
            ch_wrapper.setStyleSheet(GUIStyles.checkbox_wrapper_style())
            layout.addWidget(ch_wrapper, alignment=Qt.AlignmentFlag.AlignBottom)
            app.channel_checkboxes.append(fancy_checkbox)

    @staticmethod
    def create_channel_selector(app):
        """
        Creates the channel selector widget.

        This includes the 'Detect Channels' button, channel type selector,
        individual channel checkboxes, and the 'Plots Config' button.

        Args:
            app: The main application instance.

        Returns:
            QHBoxLayout: The layout containing the channel selection controls.
        """
        from core.controls_controller import ControlsController

        grid = QHBoxLayout()
        grid.addWidget(DetectChannelsButton(app))

        plots_config_btn = QPushButton(" PLOTS CONFIG")
        plots_config_btn.setIcon(QIcon(resource_path("assets/chart-icon.png")))
        GUIStyles.set_stop_btn_style(plots_config_btn)
        plots_config_btn.setFixedWidth(150)
        plots_config_btn.setFixedHeight(40)
        plots_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plots_config_btn.clicked.connect(
            lambda: ControlsController.open_plots_config_popup(app)
        )

        widget_channel_type = QWidget()
        row_channel_type = QHBoxLayout()
        row_channel_type.setContentsMargins(0, 0, 0, 0)
        _, inp, __, container = SelectControl.setup(
            "Channel type:",
            int(
                app.settings.value(
                    s.SETTINGS_CONNECTION_TYPE, s.DEFAULT_CONNECTION_TYPE
                )
            ),
            row_channel_type,
            ["USB", "SMA"],
            partial(ControlsController.on_connection_type_value_change, app),
            spacing=None,
        )
        inp.setFixedHeight(40)
        inp.setStyleSheet(GUIStyles.set_input_select_style())
        widget_channel_type.setLayout(row_channel_type)
        app.control_inputs["channel_type"] = inp
        grid.addWidget(widget_channel_type, alignment=Qt.AlignmentFlag.AlignBottom)

        UIController._create_channel_checkboxes(app, grid)

        grid.addWidget(plots_config_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        app.widgets[s.CHANNELS_GRID] = grid
        return grid

    @staticmethod
    def create_sync_buttons(app):
        """
        Creates the row of synchronization mode selection buttons.

        This includes the 'Check Card' widget and buttons for 'Sync In' and
        various 'Sync Out' frequencies.

        Args:
            app: The main application instance.

        Returns:
            QHBoxLayout: The layout containing the sync buttons.
        """
        from core.controls_controller import ControlsController

        buttons_layout = QHBoxLayout()
        # CHECK CARD
        check_card_widget = CheckCard(app)
        buttons_layout.addWidget(check_card_widget)
        buttons_layout.addSpacing(20)
        # SYNC BUTTONS (FREQUENCY)
        sync_in_button = FancyButton("Sync In")
        buttons_layout.addWidget(sync_in_button)
        app.sync_buttons.append((sync_in_button, "sync_in"))
        ControlsController.update_sync_in_button(app)
        sync_out_80_button = FancyButton("Sync Out (80MHz)")
        buttons_layout.addWidget(sync_out_80_button)
        app.sync_buttons.append((sync_out_80_button, "sync_out_80"))
        sync_out_40_button = FancyButton("Sync Out (40MHz)")
        buttons_layout.addWidget(sync_out_40_button)
        app.sync_buttons.append((sync_out_40_button, "sync_out_40"))
        sync_out_20_button = FancyButton("Sync Out (20MHz)")
        buttons_layout.addWidget(sync_out_20_button)
        app.sync_buttons.append((sync_out_20_button, "sync_out_20"))
        sync_out_10_button = FancyButton("Sync Out (10MHz)")
        buttons_layout.addWidget(sync_out_10_button)
        app.sync_buttons.append((sync_out_10_button, "sync_out_10"))
        for button, name in app.sync_buttons:

            def on_toggle(toggled_name):
                for b, n in app.sync_buttons:
                    b.set_selected(n == toggled_name)
                ControlsController.on_sync_selected(app, toggled_name)

            button.clicked.connect(lambda _, n=name: on_toggle(n))
            button.set_selected(app.selected_sync == name)
        app.widgets["sync_buttons_layout"] = buttons_layout

        # PICO MODE (100PS)
        frequency_mhz = ControlsController.get_frequency_mhz(app)
        selected_channels = ControlsController.get_selected_channels_from_settings(app)
        pico_mode_visible = ControlsController.is_pico_mode_active(
            app, selected_channels, frequency_mhz
        )
        buttons_layout.addSpacing(20)
        pico_mode_widget = QWidget()
        pico_mode_widget.setFixedWidth(100)
        switch_control_layout = QHBoxLayout()
        switch_control_layout.setContentsMargins(0, 0, 0, 0)
        switch_control_layout.setSpacing(0)
        inp = SwitchControl(
            active_color="#11468F",
            checked=app.settings.value(s.SETTINGS_PICO_MODE, s.DEFAULT_PICO_MODE)
            == "true",
        )
        inp.toggled.connect(partial(ControlsController.on_pico_mode_changed, app))
        label_100ps = QLabel("100ps:")
        switch_control_layout.addWidget(label_100ps)
        switch_control_layout.addWidget(inp)
        pico_mode_widget.setLayout(switch_control_layout)
        app.control_inputs[s.SETTINGS_PICO_MODE] = inp
        app.widgets["pico_mode_switch_control"] = pico_mode_widget
        pico_mode_widget.setVisible(pico_mode_visible)
        buttons_layout.addWidget(pico_mode_widget)
        LaserbloodMetadataPopup.set_FPGA_firmware(app)
        return buttons_layout

    @staticmethod
    def create_ref_data_info_banner(app):
        banner_container = QVBoxLayout()
        banner = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        banner.setLayout(layout)
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        banner_container.addWidget(banner)
        app.widgets[s.REFERENCE_INFO_BANNER] = banner_container
        app.widgets["reference_banner_label"] = label
        UIController.update_reference_info_banner_label(app)
        if UIController.show_ref_info_banner(app):
            show_layout(banner_container)
        else:
            hide_layout(banner_container)
        return banner_container, label

    @staticmethod
    def update_reference_info_banner_label(app):
        reference_file = None
        ref_type = "calibration"
        ref_required = False
        if app.tab_selected == s.TAB_PHASORS:
            reference_file = app.phasors_reference_file
            ref_type = "calibration"
            ref_required = True
        elif app.tab_selected == s.TAB_FITTING:
            reference_file = app.irf_reference_file
            ref_type = "IRF"
            ref_required = app.use_deconvolution
        is_none = reference_file is None
        ref_text = "No reference loaded" if is_none else str(reference_file)
        label = app.widgets["reference_banner_label"]
        label.setText(f"Active {ref_type} reference: {ref_text}")
        banner_container = app.widgets.get(s.REFERENCE_INFO_BANNER, None)
        if banner_container is not None and banner_container.count() > 0:
            banner = banner_container.itemAt(0).widget()
            if banner is not None:
                banner.setStyleSheet(
                    GUIStyles.ref_data_banner_style(is_none, ref_required=ref_required)
                )
                label.setStyleSheet(
                    GUIStyles.ref_data_banner_label_style(
                        is_none, ref_required=ref_required
                    )
                )

    @staticmethod
    def show_ref_info_banner(app):
        if app.tab_selected == s.TAB_PHASORS and not app.acquire_read_mode == "read":
            return True
        elif (
            app.tab_selected == s.TAB_FITTING
            and app.use_deconvolution
            and not app.acquire_read_mode == "read"
        ):
            return True
        return False
