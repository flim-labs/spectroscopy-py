"""
ui_action_buttons.py
====================
Handles creation and styling of the main action buttons:
- LOAD REFERENCE button
- EXPORT button
- FIT button placeholder
- START / STOP button
- BIN METADATA button
- EXPORT PLOT IMAGE button
- READ/PLOT button
- style_start_button: applies correct style based on app state
"""

from functools import partial

from utils.gui_styles import GUIStyles
from components.read_data import ReadDataControls
from utils.resource_path import resource_path
import settings.settings as s
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QSizePolicy,
    QPushButton,
)


def create_action_buttons(app, layout):
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
    app.control_inputs[s.FIT_BTN_PLACEHOLDER].layout().setContentsMargins(0, 0, 0, 0)
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

    style_start_button(app)


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