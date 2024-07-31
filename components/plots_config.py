
import os
import re
import json

from PyQt6.QtWidgets import QWidget, QPushButton, QCheckBox, QHBoxLayout, QGridLayout, QVBoxLayout, QLabel, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor
from components.logo_utilities import TitlebarIcon
from components.resource_path import resource_path
from components.gui_styles import GUIStyles
from settings import *
current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class PlotsConfigPopup(QWidget): 
    def __init__(self, window, start_acquisition = False, is_reference_loaded = False, reference_channels = []):
        super().__init__()
        self.app = window
        self.setWindowTitle("Spectroscopy - Plots config")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg= QColor(20, 20, 20))
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        reference_loaded_desc = "To avoid cluttering the interface, only a maximum of 4 chart groups (intensity + decay or decay + phasors) will be displayed. However, all data can be reconstructed by exporting the acquisition. From the moment you have loaded a reference, you will only be able to choose to show the plots relating to the reference acquisition channels. Please select which channels chart groups you would like to be shown."
        no_reference_desc = "To avoid cluttering the interface, only a maximum of 4 chart groups (intensity + decay or decay + phasors) will be displayed. However, all data can be reconstructed by exporting the acquisition. Please select which channels chart groups you would like to be shown."
        desc = QLabel(reference_loaded_desc) if is_reference_loaded else QLabel(no_reference_desc)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        layout.addSpacing(20)
        desc.setStyleSheet("font-size: 14px; color: #cecece")
        prompt = QLabel("CHART GROUPS (MAX 4):")
        prompt.setStyleSheet("font-size: 18px; color: white")
        self.ch_grid = QGridLayout()
        self.checkboxes = []
        self.checkboxes_wrappers = []
        layout.addWidget(prompt)
        
        if len(self.app.selected_channels) == 0:
            layout.addLayout(self.set_data_empty_row("No channels enabled."))
        else:
            self.init_ch_grid(reference_channels, is_reference_loaded)
            layout.addLayout(self.ch_grid) 
        layout.addSpacing(20)       
        
        self.start_btn = QPushButton("START")
        self.start_btn.setEnabled(len(self.app.plots_to_show) > 0)
        self.start_btn.setObjectName("btn")
        GUIStyles.set_start_btn_style(self.start_btn)
        self.start_btn.setFixedHeight(40)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_acquisition)  
        
        layout.addSpacing(20)
        row_btn = QHBoxLayout()
        row_btn.addStretch(1)
        row_btn.addWidget(self.start_btn)
        layout.addLayout(row_btn)
              
        self.setLayout(layout)
        self.setStyleSheet(GUIStyles.plots_config_popup_style())
        self.app.widgets[PLOTS_CONFIG_POPUP] = self
        
        self.center_window()
        
        
    def center_window(self):   
        self.setMinimumWidth(500)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())

    def init_ch_grid(self, reference_channels, is_reference_loaded):
        selected_channels = [ch for ch in reference_channels if ch in self.app.selected_channels] if is_reference_loaded else self.app.selected_channels
        selected_channels.sort()
        for ch in selected_channels:
            checkbox = self.set_checkboxes(f"Channel {ch + 1}")
            isChecked = ch in self.app.plots_to_show
            checkbox.setChecked(isChecked)
            if len(self.app.plots_to_show) >=4 and ch not in self.app.plots_to_show:
                checkbox.setEnabled(False)
        self.update_layout(self.checkboxes_wrappers, self.ch_grid)        


    def set_checkboxes(self, text):
        checkbox_wrapper = QWidget()
        checkbox_wrapper.setObjectName(f"simple_checkbox_wrapper")
        row = QHBoxLayout()
        checkbox = QCheckBox(text)
        checkbox.setStyleSheet(GUIStyles.set_simple_checkbox_style(color = PALETTE_BLUE_1))
        checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        checkbox.toggled.connect(lambda state, checkbox=checkbox: self.on_ch_intensity_toggled(state, checkbox) )
        row.addWidget(checkbox)
        checkbox_wrapper.setLayout(row)
        checkbox_wrapper.setStyleSheet(GUIStyles.checkbox_wrapper_style())
        self.checkboxes_wrappers.append(checkbox_wrapper)
        self.checkboxes.append(checkbox)
        return checkbox  

    def set_data_empty_row(self, text):    
        row = QHBoxLayout()
        remove_icon_label = QLabel()
        remove_icon_label.setPixmap(QPixmap(resource_path("assets/close-icon-red.png")).scaledToWidth(15))
        label = QLabel(text)
        label.setStyleSheet("color: #c90404; font-size: 14px")
        row.addWidget(remove_icon_label)
        row.addWidget(label)
        row.addStretch(1)
        return row

    def update_layout(self, widgets, grid):       
        screen_width = self.width()
        if screen_width < 500:
            num_columns = 4 
        elif 500 <= screen_width <= 1200:
            num_columns = 6 
        elif 1201 <= screen_width <= 1450:
            num_columns = 8 
        else:
            num_columns = 12 
        for i, widget in enumerate(widgets):
            row, col = divmod(i, num_columns)
            grid.addWidget(widget, row, col)
            

    def on_ch_intensity_toggled(self, state, checkbox):
        label_text = checkbox.text() 
        ch_num_index = self.extract_channel_from_label(label_text) 
        if state:
            if ch_num_index not in self.app.plots_to_show:
                self.app.plots_to_show.append(ch_num_index)
        else:
            if ch_num_index in self.app.plots_to_show:
                self.app.plots_to_show.remove(ch_num_index) 
        self.app.plots_to_show.sort()        
        self.app.settings.setValue(SETTINGS_PLOTS_TO_SHOW, json.dumps(self.app.plots_to_show)) 
        if len(self.app.plots_to_show) >= 4:
            for checkbox in self.checkboxes:
                if checkbox.text() != label_text and not checkbox.isChecked():
                    checkbox.setEnabled(False)
        else:
            for checkbox in self.checkboxes:
                checkbox.setEnabled(True) 
        if hasattr(self, 'start_btn'):        
            start_btn_enabled = len(self.app.plots_to_show) > 0
            self.start_btn.setEnabled(start_btn_enabled)
        self.app.clear_plots()   
        self.app.cached_decay_values.clear()
        self.app.generate_plots() 
        
                           
    def start_acquisition(self):
        self.close()
        self.app.begin_spectroscopy_experiment()
        
        
    def extract_channel_from_label(self,text):
        ch = re.search(r'\d+', text).group()  
        ch_num = int(ch) 
        ch_num_index = ch_num - 1 
        return ch_num_index

    
 