from functools import partial
import os
import json

from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QApplication,
    QFormLayout,
    QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon
from components.input_text_control import InputTextControl
from components.logo_utilities import TitlebarIcon
from components.resource_path import resource_path
from components.gui_styles import GUIStyles
from settings import *

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class ExportDataSettingsPopup(QWidget):
    def __init__(self, window, start_acquisition=False):
        super().__init__()
        self.app = window
        self.setWindowTitle("Spectroscopy - Export Data Settings")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg=QColor(20, 20, 20))
        
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        desc_text = "Choose the folder where you want to export all your .bin files (Spectroscopy, Phasors) and Laserblood metadata JSON. Then, choose a filename for each exportable file. The chosen filename will be appended to the default .bin/JSON name."
        desc = QLabel(desc_text)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 14px; color: #cecece")
        main_layout.addWidget(desc)
        main_layout.addSpacing(20)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(20)
        main_layout.addLayout(form_layout)
        self.start_btn = QPushButton("START" if start_acquisition is True  else "OK") 
        self.start_btn.setEnabled(ExportDataSettingsPopup.exported_data_settings_valid(self.app))
        self.start_btn.setObjectName("btn")
        GUIStyles.set_start_btn_style(self.start_btn)
        self.start_btn.setFixedHeight(40)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(partial(self.on_action_btn_clicked, start_acquisition))
        row_btn = QHBoxLayout()
        row_btn.addStretch(1)
        row_btn.addWidget(self.start_btn)  
        
        main_layout.addSpacing(40)
        main_layout.addLayout(row_btn)
        
        folder_widget = QWidget() 
        folder_layout = QHBoxLayout(folder_widget)
        folder_layout.setSpacing(0)
        folder_layout.setContentsMargins(0,0,0,0)
        
        folder_label = QLabel("FOLDER PATH:")
        folder_label.setStyleSheet("font-size: 14px")
        folder_label.setMinimumWidth(180)  
        
        folder_inp = InputTextControl.setup(
            label="",
            placeholder="",
             text= self.app.exported_data_settings["folder"],
            event_callback=partial(self.on_input_change, inp_type="folder"),
        )
        
        folder_button = QPushButton()
        folder_button.clicked.connect(self.on_folder_button_clicked)
        folder_button.setIcon(QIcon(resource_path("assets/folder-white.png")))
        folder_button.setFixedWidth(60)
        folder_button.setFixedHeight(40)
        folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_button.setStyleSheet("background-color: #11468F")
        
        folder_layout.addWidget(folder_inp[1])
        folder_layout.addWidget(folder_button)
        folder_layout.setSpacing(0) 
        
        form_layout.addRow(folder_label, folder_widget)
        
        spectroscopy_inp = InputTextControl.setup(
            label="SPECTROSCOPY NAME:",
            placeholder="",
             text= self.app.exported_data_settings["spectroscopy_filename"],
            event_callback=partial(self.on_input_change, inp_type="spectroscopy_filename"),
        )
        phasors_inp = InputTextControl.setup(
            label="PHASORS NAME:",
            placeholder="",
             text= self.app.exported_data_settings["phasors_filename"],
            event_callback=partial(self.on_input_change, inp_type="phasors_filename"),
        )
        spectro_phasors_ref_inp = InputTextControl.setup(
            label="SPECTROSCOPY-PHASORS REF NAME:",
            placeholder="",
             text= self.app.exported_data_settings["spectroscopy_phasors_ref_filename"],
            event_callback=partial(self.on_input_change, inp_type="spectroscopy_phasors_ref_filename"),
        )
        laserblood_metadata_inp = InputTextControl.setup(
            label="LASERBLOOD METADATA NAME:",
            placeholder="",
             text= self.app.exported_data_settings["laserblood_metadata_filename"],
            event_callback=partial(self.on_input_change, inp_type="laserblood_metadata_filename"),
        )
        
        form_layout.addRow(*spectroscopy_inp)
        form_layout.addRow(*phasors_inp)
        form_layout.addRow(*spectro_phasors_ref_inp)
        form_layout.addRow(*laserblood_metadata_inp)
        
        self.setLayout(main_layout)
        self.app.widgets[EXPORT_DATA_SETTINGS_POPUP] = self

        self.inputs = {
            "folder_inp": folder_inp[1],
            "spectroscopy_inp": spectroscopy_inp[1],
            "phasors_inp": phasors_inp[1],
            "spectro_phasors_ref_inp": spectro_phasors_ref_inp[1],
            "laserblood_metadata_inp": laserblood_metadata_inp[1]
        }

        for input_widget in self.inputs.values():
            input_widget.setStyleSheet(GUIStyles.set_input_text_style())
            
        self.center_window()
        
    def center_window(self):   
        self.setMinimumWidth(700)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())
        
    def on_input_change(self, text, inp_type):
        text_trimmed = text.strip()
        self.app.exported_data_settings[inp_type] = text_trimmed
        self.app.settings.setValue(SETTINGS_EXPORTED_DATA_PATHS, json.dumps(self.app.exported_data_settings))
        self.start_btn.setEnabled(ExportDataSettingsPopup.exported_data_settings_valid(self.app))   
        
    def directory_selector(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        return folder_path     
            
    def on_folder_button_clicked(self):
        folder_path = self.directory_selector()
        if folder_path:
            self.inputs["folder_inp"].setText(folder_path)
            self.on_input_change(folder_path, "folder")
    
    @staticmethod
    def exported_data_settings_valid(app):
        for value in app.exported_data_settings.values():
            if not value.strip():
                return False
        return True      
    
    def on_action_btn_clicked(self, start_acquisition):    
        self.close()
        if start_acquisition:
            self.app.begin_spectroscopy_experiment()  
            
            
