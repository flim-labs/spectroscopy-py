"""
ui_top_bar.py 
====================================
Handles creation of the top bar area:
- Application logo and title (smaller logo, shifted margins vs standard)
- Tab buttons (Spectroscopy, Phasors, Fitting)
- Laserblood METADATA button (edition-specific)
- Read/Acquire mode toggle
- Export data switch and info link
- File size info row
- Time Tagger widget
- Assembly of the full top bar container
"""

from functools import partial

from components.buttons import ReadAcquireModeButton, TimeTaggerWidget
from components.gradient_text import GradientText
from utils.gui_styles import GUIStyles
from utils.layout_utilities import draw_layout_separator
from components.link_widget import LinkWidget
from components.progress_bar import ProgressBar
from components.switch_control import SwitchControl
from utils.resource_path import resource_path
import settings.settings as s
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QPushButton,
)


def create_logo_and_title(app):
    """
    Creates the application logo and title section.

    Args:
        app: The main application instance.

    Returns:
        QHBoxLayout: A layout containing the logo and title.
    """
    row = QHBoxLayout()
    # Laserblood edition uses a smaller logo (width=30 vs 40 in standard)
    pixmap = QPixmap(
        resource_path("assets/spectroscopy-logo-white.png")
    ).scaledToWidth(30)
    ctl = QLabel(pixmap=pixmap)
    row.addWidget(ctl)
    row.addSpacing(10)
    ctl_layout = QVBoxLayout()
    # Laserblood edition shifts the title lower (top margin 20 vs 10 in standard)
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
    info_link_widget = LinkWidget(
        icon_filename=resource_path("assets/info-icon.png"),
        link="https://flim-labs.github.io/spectroscopy-py/v1.0/#gui-usage",
    )
    info_link_widget.setCursor(Qt.CursorShape.PointingHandCursor)
    info_link_widget.show()
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


def create_top_bar(app):
    """
    Creates the entire top bar widget containing all controls and headers.

    Includes the Laserblood-specific METADATA button in addition to
    the standard tab, export, and Time Tagger controls.

    Args:
        app: The main application instance.

    Returns:
        QWidget: A container widget for the entire top bar.
    """
    from core.controls_controller import ControlsController
    from core.ui.ui_channels_and_sync import create_channel_selector, create_sync_buttons
    from core.ui.ui_control_inputs import create_control_inputs

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
    top_bar_header.addLayout(create_logo_and_title(app))

    tabs_layout = QHBoxLayout()
    tabs_layout.setContentsMargins(0, 0, 0, 0)
    tabs_layout.setSpacing(0)
    app.control_inputs[s.TAB_SPECTROSCOPY] = QPushButton("SPECTROSCOPY")
    app.control_inputs[s.TAB_SPECTROSCOPY].setFlat(True)
    app.control_inputs[s.TAB_SPECTROSCOPY].setSizePolicy(
        QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
    )
    app.control_inputs[s.TAB_SPECTROSCOPY].setCursor(Qt.CursorShape.PointingHandCursor)
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

    # LASERBLOOD METADATA button (edition-specific – not present in standard)
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

    info_link_widget, export_data_control = create_export_data_input(app)
    file_size_info_layout = create_file_size_info_row(app)
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
    channels_widget.setLayout(create_channel_selector(app))
    sync_buttons_widget.setLayout(create_sync_buttons(app))
    top_collapsible_layout.addWidget(channels_widget, 0, Qt.AlignmentFlag.AlignTop)
    top_collapsible_layout.addWidget(
        sync_buttons_widget, 0, Qt.AlignmentFlag.AlignTop
    )
    top_collapsible_widget.setLayout(top_collapsible_layout)
    top_bar.addWidget(top_collapsible_widget)
    top_bar.addLayout(create_control_inputs(app))
    top_bar.addWidget(draw_layout_separator())
    top_bar.addSpacing(5)
    container = QWidget()
    container.setLayout(top_bar)
    return container