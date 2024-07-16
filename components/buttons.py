from functools import partial
import os
from PyQt6.QtCore import QPropertyAnimation, QPoint, Qt, QSize
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QVBoxLayout, QMenu
from PyQt6.QtGui import QIcon, QAction
from components.resource_path import resource_path
from components.gui_styles import GUIStyles
from export_data_scripts.script_files_utils import MatlabScriptUtils, PythonScriptUtils
from settings import *

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class CollapseButton(QWidget):
    def __init__(self, collapsible_widget, parent=None):
        super().__init__(parent)
        self.collapsible_widget = collapsible_widget
        self.collapsed = True
        self.toggle_button = QPushButton()
        self.toggle_button.setIcon(
            QIcon(resource_path("assets/arrow-up-dark-grey.png"))
        )
        self.toggle_button.setFixedSize(30, 30)
        self.toggle_button.setStyleSheet(GUIStyles.toggle_collapse_button())
        self.toggle_button.clicked.connect(self.toggle_collapsible)
        self.toggle_button.move(self.toggle_button.x(), self.toggle_button.y() - 100)
        layout = QHBoxLayout()
        layout.addStretch(1)
        layout.addWidget(self.toggle_button)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.animation = QPropertyAnimation(self.collapsible_widget, b"maximumHeight")
        self.animation.setDuration(300)

    def toggle_collapsible(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.animation.setStartValue(0)
            self.animation.setEndValue(self.collapsible_widget.sizeHint().height())
            self.toggle_button.setIcon(
                QIcon(resource_path("assets/arrow-up-dark-grey.png"))
            )
        else:
            self.animation.setStartValue(self.collapsible_widget.sizeHint().height())
            self.animation.setEndValue(0)
            self.toggle_button.setIcon(
                QIcon(resource_path("assets/arrow-down-dark-grey.png"))
            )
        self.animation.start()


class DownloadButton(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.app = window
        self.download_button, self.download_menu = self.create_download_files_menu()
        layout = QHBoxLayout()
        layout.addWidget(self.download_button)
        self.setLayout(layout)

    def create_download_files_menu(self):
        # download button
        export_data = self.app.write_data_gui
        download_button = QPushButton(" DOWNLOAD")
        download_button.setFixedHeight(40)
        download_button.setObjectName("download_btn")
        download_button.setStyleSheet(
            GUIStyles.button_style("#1E90FF", "#1E90FF", "#1E90FF", "#1E90FF", "150px")
        )
        download_button.setIconSize(QSize(16, 16))
        download_button.clicked.connect(self.show_download_options)
        download_button.setEnabled(export_data and self.app.acquisition_stopped)
        download_button.setVisible(export_data)
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(download_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.setDirection(QHBoxLayout.Direction.RightToLeft)
        # context menu
        download_menu = QMenu()
        spectroscopy_script_action_py = QAction("PYTHON SPECTROSCOPY", self)
        spectroscopy_script_action_m = QAction("MATLAB SPECTROSCOPY", self)
        phasors_script_action_py = QAction("PYTHON PHASORS", self)
        phasors_script_action_m = QAction("MATLAB PHASORS", self)
        download_menu.setStyleSheet(
            GUIStyles.set_context_menu_style("#1E90FF", "#1E90FF", "#1E90FF")
        )
        download_menu.addAction(spectroscopy_script_action_py)
        download_menu.addAction(spectroscopy_script_action_m)
        download_menu.addAction(phasors_script_action_py)
        download_menu.addAction(phasors_script_action_m)
        phasors_script_action_py.setVisible(False)
        phasors_script_action_m.setVisible(False)
        spectroscopy_script_action_py.triggered.connect(
            partial(self.download_spectroscopy_script, self.app, "py")
        )
        spectroscopy_script_action_m.triggered.connect(
            partial(self.download_spectroscopy_script, self.app, "m")
        )
        phasors_script_action_py.triggered.connect(
            partial(self.download_phasors_script, self.app, "py")
        )
        phasors_script_action_m.triggered.connect(
            partial(self.download_phasors_script, self.app, "m")
        )
        self.app.control_inputs[SPECTROSCOPY_SCRIPT_ACTION_PY] = (
            spectroscopy_script_action_py
        )
        self.app.control_inputs[SPECTROSCOPY_SCRIPT_ACTION_M] = (
            spectroscopy_script_action_m
        )
        self.app.control_inputs[PHASORS_SCRIPT_ACTION_PY] = phasors_script_action_py
        self.app.control_inputs[PHASORS_SCRIPT_ACTION_M] = phasors_script_action_m
        self.app.control_inputs[DOWNLOAD_BUTTON] = download_button
        self.app.control_inputs[DOWNLOAD_MENU] = download_menu
        DownloadButton.set_download_button_icon(self.app)
        return download_button, download_menu

    def show_download_options(self):
        self.app.control_inputs[DOWNLOAD_MENU].exec(
            self.app.control_inputs[DOWNLOAD_BUTTON].mapToGlobal(
                QPoint(0, self.app.control_inputs[DOWNLOAD_BUTTON].height())
            )
        )

    @staticmethod
    def download_spectroscopy_script(app, script_type):
        bin_file_path = app.exported_data_file_paths["spectroscopy"]
        (
            PythonScriptUtils.download_spectroscopy(app, bin_file_path)
            if script_type == "py"
            else MatlabScriptUtils.download_spectroscopy(app, bin_file_path)
        )
        app.control_inputs[DOWNLOAD_BUTTON].setEnabled(False)
        app.control_inputs[DOWNLOAD_BUTTON].setEnabled(True)

    @staticmethod
    def download_phasors_script(app, script_type):
        spectroscopy_ref_bin_file_path = app.exported_data_file_paths["spectroscopy_phasors_ref"]
        phasors_bin_file_path = app.exported_data_file_paths["phasors"]
        (
            PythonScriptUtils.download_phasors(app, spectroscopy_ref_bin_file_path, phasors_bin_file_path)
            if script_type == "py"
            else MatlabScriptUtils.download_phasors(app, spectroscopy_ref_bin_file_path, phasors_bin_file_path)
        )
        app.control_inputs[DOWNLOAD_BUTTON].setEnabled(False)
        app.control_inputs[DOWNLOAD_BUTTON].setEnabled(True)
        
    @staticmethod     
    def change_download_script_options(app):
        if app.tab_selected == "tab_spectroscopy":
            DownloadButton.set_action_visibility(app, False, True)
        elif app.tab_selected == "tab_data":
            DownloadButton.set_action_visibility(app, True, False)

    @staticmethod 
    def set_action_visibility(app, phasors_visible, spectroscopy_visible):
        app.control_inputs[PHASORS_SCRIPT_ACTION_PY].setVisible(phasors_visible)
        app.control_inputs[PHASORS_SCRIPT_ACTION_M].setVisible(phasors_visible)
        app.control_inputs[SPECTROSCOPY_SCRIPT_ACTION_PY].setVisible(spectroscopy_visible)
        app.control_inputs[SPECTROSCOPY_SCRIPT_ACTION_M].setVisible(spectroscopy_visible)    

    @staticmethod
    def set_download_button_icon(app):
        icon = resource_path("assets/arrow-down-icon-white.png")
        app.control_inputs[DOWNLOAD_BUTTON].setIcon(QIcon(icon))
        
        
