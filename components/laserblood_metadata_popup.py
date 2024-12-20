
from functools import partial
import os
import json

from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QApplication,
    QScrollArea,
    QSpacerItem, QSizePolicy
 
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon
from components.fancy_checkbox import FancyButton
from components.input_number_control import InputFloatControl, InputNumberControl
from components.input_text_control import InputTextControl, InputTextareaControl
from components.layout_utilities import draw_layout_separator
from components.logo_utilities import TitlebarIcon
from components.resource_path import resource_path
from components.gui_styles import GUIStyles
from components.select_control import SelectControl
from components.switch_control import SwitchControl
from laserblood_settings import FILTERS_TYPES, FILTERS_TYPES_NO_BANDPASS, LASER_TYPES, LASERBLOOD_METADATA_POPUP, METADATA_LASERBLOOD_KEY, NEW_ADDED_LASERBLOOD_INPUTS_KEY, SETTINGS_FILTER_TYPE, SETTINGS_LASER_TYPE
from settings import *


current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path))


class LaserbloodMetadataPopup(QWidget):
    def __init__(self, window, start_acquisition=False):
        super().__init__()
        self.app = window
        self.setWindowTitle("Spectroscopy - Laserblood Metadata")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg=QColor(20, 20, 20))
        self.filters_grid = QGridLayout()
        self.filters_no_bandpass_grid = QGridLayout()
        self.laser_buttons = []
        self.filter_buttons = []
        self.selected_laser = self.app.laserblood_laser_type
        self.selected_filter = self.app.laserblood_filter_type
        self.new_input_type = "number"
        self.new_input_label = ""
        self.new_input_unit = ""
        self.widgets = {}
        self.layouts = {}
        self.laser_settings_container = QVBoxLayout()
        self.laser_settings_container.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.laser_settings_container.addSpacing(20)
        self.q_v_box_inputs_container = QVBoxLayout()
        self.inputs_grid = QGridLayout()
        self.new_added_inputs_grid = QGridLayout()
        
        start_btn_row = QHBoxLayout()
        start_btn_row.setContentsMargins(0,0,10,0)
        start_btn_row.addStretch(1)
        self.start_btn = QPushButton("SAVE")
        self.start_btn.setFixedWidth(150)
        self.start_btn.setFixedHeight(55)
        self.start_btn.setObjectName("btn")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        GUIStyles.set_start_btn_style(self.start_btn)
        self.start_btn.setEnabled(LaserbloodMetadataPopup.laserblood_metadata_valid(self.app))
        self.start_btn.clicked.connect(self.on_save_btn_click)
        start_btn_row.addWidget(self.start_btn)
        
        self.init_inputs_grid()
        self.init_new_input_added_layout()
        self.q_v_box_inputs_container.addLayout(self.inputs_grid)
        self.q_v_box_inputs_container.addLayout(self.new_added_inputs_grid)
        self.q_v_box_inputs_container.addSpacing(20)
        self.q_v_box_inputs_container.addLayout(start_btn_row)
        
        self.init_laser_filter_settings_layout()
        self.no_bandpass_input = self.create_no_bandpass_filter_input()
        self.filters_no_bandpass_grid.addLayout(self.no_bandpass_input, 1, 3)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setWidget(QWidget())
        self.scroll_area.widget().setLayout(self.q_v_box_inputs_container)
        h_box = QHBoxLayout()
        h_box.addLayout(self.laser_settings_container)
        h_box.setStretch(0, 2)
        h_box.addWidget(draw_layout_separator(type="vertical"))
        h_box.addWidget(self.scroll_area)
        h_box.setStretch(2, 4)
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.addLayout(h_box)
        self.setLayout(main_layout)
        self.app.widgets[LASERBLOOD_METADATA_POPUP] = self
        self.setObjectName("laserblood_popup")
        self.setStyleSheet(GUIStyles.set_laserblood_popup_style())
        self.showMaximized()
    
    
    def init_laser_filter_settings_layout(self):
        main_container = QVBoxLayout()
        lasers_v_box = self.create_laser_layout(title="LASER WAVELENGTH (BANDPASS)", bandpass=True)
        lasers_no_bandpass_v_box = self.create_laser_layout(title="LASER WAVELENGTH (NO BANDPASS)", bandpass=False)
        self.create_filters_layout(title="EMISSION FILTER WAVELENGTH (BANDPASS)", bandpass=True, container=self.filters_grid)
        self.create_filters_layout(title="EMISSION FILTER WAVELENGTH (NO BANDPASS)", bandpass=False, container=self.filters_no_bandpass_grid)
        add_inputs_layout = self.create_add_new_input_layout()
        main_container.addLayout(lasers_v_box)
        main_container.addSpacing(20)
        main_container.addLayout(lasers_no_bandpass_v_box)
        main_container.addSpacing(20)
        main_container.addLayout(self.filters_grid)
        main_container.addSpacing(20)
        main_container.addLayout(self.filters_no_bandpass_grid)
        main_container.addStretch(1)
        main_container.addLayout(add_inputs_layout)
        main_container.addSpacing(20)
        self.laser_settings_container.addLayout(main_container) 
        
                    
    def create_laser_layout(self, title, bandpass):
        laser_types = [l for l in LASER_TYPES if l["BANDPASS"] == bandpass]
        title = QLabel(title)
        lasers_v_box = QVBoxLayout()
        lasers_v_box.addWidget(title)
        grid_layout = QGridLayout()
        row, col = 0, 0
        for laser in laser_types:
            laser_button = FancyButton(laser["LABEL"])
            grid_layout.addWidget(laser_button, row, col)
            self.laser_buttons.append((laser_button, laser["LABEL"]))
            col += 1
            if col == 2:  
                col = 0
                row += 1
        for button, name in self.laser_buttons:
            button.set_selected(name == self.selected_laser)
            def on_toggle(toggled_name):
                for b, n in self.laser_buttons:
                    b.set_selected(n == toggled_name)
                    self.on_laser_selected(toggled_name)
            button.clicked.connect(lambda _, n=name: on_toggle(n))
            button.set_selected(self.selected_laser == name)
        lasers_v_box.addLayout(grid_layout)    
        return lasers_v_box
        
    
    def create_filters_layout(self, title, bandpass, container):
        laser_selected = next((laser for laser in LASER_TYPES if laser["LABEL"] == self.selected_laser), None)
        if bandpass:
            filter_types = laser_selected["FILTERS"] if laser_selected is not None else []
        else:
            filter_types = FILTERS_TYPES_NO_BANDPASS  if self.selected_laser else []  
        title = QLabel(title)
        if laser_selected is not None:
            container.addWidget(title, 0, 0, 1, 4)
        row, col = 1, 0
        for filter in filter_types:
            filter_button = FancyButton(
                filter,
                selected_color="#DA1212",
                hover_color="#E23B3B",
                pressed_color="#B01010"
            )
            container.addWidget(filter_button, row, col)
            self.filter_buttons.append((filter_button, filter))
            col += 1
            if col == 4:
                col = 0
                row += 1
        for button, name in self.filter_buttons:
            button.set_selected(name == self.selected_filter)
            def on_toggle(toggled_name):
                for b, n in self.filter_buttons:
                    b.set_selected(n == toggled_name)
                self.on_filter_selected(toggled_name)
            button.clicked.connect(lambda _, n=name: on_toggle(n))
            button.set_selected(self.selected_filter == name)    
                
            
    def create_no_bandpass_filter_input(self):
        row = QHBoxLayout()
        filter_wavelength_input = next((input for input in self.app.laserblood_settings if input["LABEL"] == "Emission filter wavelength"), None)
        if len(filter_wavelength_input["VALUE"].strip()) == 0:
            value = 0
        else:
            number_str = ''.join(filter(str.isdigit, filter_wavelength_input["VALUE"]))
            value = int(number_str) if number_str else 0    
        label , inp = InputNumberControl.setup(
            label = "Wavelength:",
            min = 0,
            max = 1000000,
            value = value,
            row = row,
            control_layout="horizontal",
            event_callback=lambda value: self.on_filter_no_bandpass_value_change(value),
        )
        self.app.laserblood_widgets["Wavelength"] = inp
        self.app.laserblood_widgets["no_bandpass_filter_label"] = label
        inp.setStyleSheet(GUIStyles.set_input_number_style(border_color = "#3b3b3b", disabled_border_color="#3c3c3c"))
        is_no_bandpass = self.selected_filter is not None and ("LP" in self.selected_filter or "SP" in self.selected_filter)
        inp.setVisible(is_no_bandpass)
        label.setVisible(is_no_bandpass)
        return row

        
    def on_filter_no_bandpass_value_change(self, value):
        filter_wavelength_input = next((input for input in self.app.laserblood_settings if input["LABEL"] == "Emission filter wavelength"), None) 
        text = str(value) + " nm"    
        self.app.laserblood_widgets[filter_wavelength_input["LABEL"]].setText(text) 
        self.start_btn.setEnabled(LaserbloodMetadataPopup.laserblood_metadata_valid(self.app)) 
                  
        
    def on_laser_selected(self, laser):
        laser_selected = next((laser_opt for laser_opt in LASER_TYPES if laser_opt["LABEL"] == laser), None)
        laser_wavelength_input = next((input for input in self.app.laserblood_settings if input["LABEL"] == "Laser wavelength"), None)
        filter_wavelength_input = next((input for input in self.app.laserblood_settings if input["LABEL"] == "Emission filter wavelength"), None)
        self.selected_laser = laser 
        self.app.laserblood_laser_type = laser
        self.app.settings.setValue(SETTINGS_LASER_TYPE, self.selected_laser)
        self.app.laserblood_widgets[laser_wavelength_input["LABEL"]].setText(laser_selected["KEY"])
        self.app.laserblood_widgets[filter_wavelength_input["LABEL"]].setText("")
        self.selected_filter = None
        self.app.laserblood_filter_type = None
        self.app.settings.remove(SETTINGS_FILTER_TYPE)
        self.app.clear_layout_tree(self.filters_grid)
        self.app.clear_layout_tree(self.filters_no_bandpass_grid)
        self.filter_buttons.clear()
        self.create_filters_layout(title="EMISSION FILTER WAVELENGTH (BANDPASS)", bandpass=True, container=self.filters_grid)
        self.create_filters_layout(title="EMISSION FILTER WAVELENGTH (NO BANDPASS)", bandpass=False, container=self.filters_no_bandpass_grid)
        self.no_bandpass_input = self.create_no_bandpass_filter_input()
        self.filters_no_bandpass_grid.addLayout(self.no_bandpass_input, 1, 3)
        self.start_btn.setEnabled(LaserbloodMetadataPopup.laserblood_metadata_valid(self.app))
        
    def on_filter_selected(self, filter):
        self.selected_filter = filter
        if filter not in ['SP', 'LP']:
            filter_selected = next(f for f in FILTERS_TYPES if f == filter)
            filter_wavelength_input = next(input for input in self.app.laserblood_settings if input["LABEL"] == "Emission filter wavelength")
            self.app.laserblood_filter_type = filter
            self.app.settings.setValue(SETTINGS_FILTER_TYPE, filter)  
            self.app.laserblood_widgets[filter_wavelength_input["LABEL"]].setText(filter_selected)
            self.app.laserblood_widgets["Wavelength"].setVisible(False)
            self.app.laserblood_widgets["no_bandpass_filter_label"].setVisible(False)
        else:
            self.app.laserblood_widgets["Wavelength"].setVisible(True)
            self.app.laserblood_widgets["no_bandpass_filter_label"].setVisible(True)
            self.selected_filter = filter   
            self.app.laserblood_filter_type = filter
            self.app.settings.setValue(SETTINGS_FILTER_TYPE, filter) 
            self.app.laserblood_widgets["Emission filter wavelength"].setText("")
        self.start_btn.setEnabled(LaserbloodMetadataPopup.laserblood_metadata_valid(self.app))    
      

    def set_add_button_enabled(self):
        if "add_button" in self.app.laserblood_widgets:
            add_button_enabled = len(self.new_input_type.strip()) > 0 and len(self.new_input_label.strip()) > 0
            self.app.laserblood_widgets["add_button"].setEnabled(add_button_enabled)
            
    
    def init_new_input_added_layout(self):
        max_cols = 4
        for i, new_input in enumerate(self.app.laserblood_new_added_inputs):
            row = i // max_cols
            col = i % max_cols
            widget = self.dispatch_create_input(new_input, new_added=True)
            self.new_added_inputs_grid.addWidget(widget, row, col)
            
            
    def add_new_input_to_settings(self):
        is_numeric_input = self.new_input_type == "number"
        new_input = {
            "LABEL": self.new_input_label,
            "UNIT": self.new_input_unit if is_numeric_input else None,
            "VALUE": 0 if is_numeric_input else "",
            "OPTIONS": [],
            "INPUT_TYPE": "float" if is_numeric_input else "text",
            "MIN": None,
            "MAX": 10000000,
            "POSITION": (),
            "ENABLED": True,
            "REMOVABLE": True,
            "REQUIRED": True 
        }
        self.app.laserblood_new_added_inputs.append(new_input)
        self.app.settings.setValue(NEW_ADDED_LASERBLOOD_INPUTS_KEY, json.dumps(self.app.laserblood_new_added_inputs))
        
    def on_add_new_input_btn_clicked(self):
        self.add_new_input_to_settings()
        self.app.clear_layout_tree(self.new_added_inputs_grid)  
        self.init_new_input_added_layout()
        self.new_input_label = ""
        self.new_input_unit = ""
        self.app.laserblood_widgets["inp_unit"].clear()
        self.app.laserblood_widgets["inp_label"].clear()

    def create_add_new_input_layout(self):
        h_box = QHBoxLayout()
        def on_inp_type_change(value):
            self.new_input_type = "number" if value == 0 else "text"
            if "inp_unit_control" in self.layouts:
                self.app.show_layout(self.layouts["inp_unit_control"]) if value == 0 else self.app.hide_layout(self.layouts["inp_unit_control"])
            if value == 1:
                self.new_input_unit = ""
                if "inp_unit" in self.app.laserblood_widgets:
                    self.app.laserblood_widgets["inp_unit"].clear()
            self.set_add_button_enabled() 
               
        def on_inp_label_change(text):
            self.new_input_label = text
            self.set_add_button_enabled()
            
        def on_inp_unit_change(text):
            self.new_input_unit = text
            self.set_add_button_enabled()
        # TYPE
        h_box_inp_type = QHBoxLayout()
        control, inp_type, _, container = SelectControl.setup(
            label="Input type:",
            options=["number", "text"],
            selectedValue=0,
            container=h_box_inp_type,
            event_callback=lambda value: on_inp_type_change(value),
            spacing=0,
            width=100
        )
        self.app.laserblood_widgets["inp_type"] = inp_type
        inp_type.setStyleSheet(GUIStyles.set_input_select_style())
        # LABEL
        inp_label_control = QVBoxLayout() 
        inp_label_label, inp_label = InputTextControl.setup(
            label="Input label:",
            text="",
            placeholder="",
            event_callback=lambda text: on_inp_label_change(text),
        )
        inp_label.setStyleSheet(GUIStyles.set_input_text_style(border_color="#3b3b3b", disabled_border_color="#3c3c3c")) 
        inp_label_control.addWidget(inp_label_label)
        inp_label_control.addWidget(inp_label)
        self.app.laserblood_widgets["inp_label"] = inp_label
        # UNIT 
        inp_unit_control = QVBoxLayout()        
        inp_unit_label, inp_unit = InputTextControl.setup(
            label="Input unit:",
            text="",
            placeholder="",
            event_callback=lambda text: on_inp_unit_change(text),
        )
        inp_unit.setStyleSheet(GUIStyles.set_input_text_style(border_color="#3b3b3b", disabled_border_color="#3c3c3c"))  
        self.app.laserblood_widgets["inp_unit"] = inp_unit
        inp_unit_control.addWidget(inp_unit_label)
        inp_unit_control.addWidget(inp_unit)
        self.layouts["inp_unit_control"] = inp_unit_control
        add_button = QPushButton(" ADD")
        add_button.setIcon(QIcon(resource_path("assets/add-icon-white.png")))
        add_button.setFixedHeight(60)
        add_button.setFixedWidth(100)
        add_button.setStyleSheet(
            """
            QPushButton {
                font-family: Montserrat; 
                font-weight: bold; 
                color: white; background-color: #4BB543;
            }
            QPushButton:disabled {
                background-color: #9e9d9d;
            }
            """
        )
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.setEnabled(False)
        add_button.clicked.connect(self.on_add_new_input_btn_clicked)
        self.app.laserblood_widgets["add_button"] = add_button
        h_box.addLayout(h_box_inp_type)
        h_box.addLayout(inp_label_control)
        h_box.addLayout(inp_unit_control)
        h_box.addWidget(add_button)
        return h_box

    def dispatch_create_input(self, input, new_added):
        input_type = input["INPUT_TYPE"]
        if input_type == "int":
            widget_container = self.create_int_input(input, new_added_inp=new_added)
        elif input_type == "float":
            widget_container = self.create_float_input(input, new_added_inp=new_added)
        elif input_type == "text":
            widget_container = self.create_text_input(input, new_added_inp=new_added)
        elif input_type == "select":
            widget_container = self.create_select_input(input, new_added_inp=new_added)
        elif input_type == "boolean":
            widget_container = self.create_switch_input(input, new_added_inp=new_added)
        elif input_type == "textarea":
            widget_container = self.create_textarea_input(input, new_added_inp=new_added)
        else:
            raise ValueError(f"Unknown input type: {input_type}")
        return widget_container


    def init_inputs_grid(self):
        inputs = self.app.laserblood_settings 
        for input in inputs:
            self.dispatch_create_input(input, new_added=False)      
    
    def create_int_input(self, input, new_added_inp = False):
        widget_container = QWidget()
        row = QHBoxLayout()
        row.setContentsMargins(0,10,0, 10)        
        position = input["POSITION"]
        label = input["LABEL"] + ":" if not input["UNIT"] else input["LABEL"] + " (" + input["UNIT"] + "):"
        _, inp = InputNumberControl.setup(
            label = label,
            min = input["MIN"],
            max = input["MAX"],
            value = input["VALUE"],
            row = row,
            event_callback=lambda value, inp=input, new_input = new_added_inp: self.on_input_value_change(value, inp, new_input),
        )
        if input["LABEL"] == "Weeks (only PDAC)":
            pdac_healthy = [obj["VALUE"] for obj in self.app.laserblood_settings if obj["LABEL"] == "PDAC/Healthy"][0]
            pdac_weeks_enabled = pdac_healthy == 1
            inp.setEnabled(pdac_weeks_enabled)
        else:
            inp.setEnabled(input["ENABLED"])
        self.dispatch_input_warning_styles(inp, input["INPUT_TYPE"], input["VALUE"], input["REQUIRED"], input["LABEL"])
        self.app.laserblood_widgets[input["LABEL"]] = inp
        widget_container.setLayout(row)      
        if not new_added_inp:            
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3],)
            self.inputs_grid.setColumnStretch(position[1], input["STRETCH"])
        return widget_container    
    
    def create_float_input(self, input, new_added_inp = False):
        widget_container = QWidget()
        row = QHBoxLayout()
        row.setContentsMargins(0,10,0, 10)         
        position = input["POSITION"]
        label = input["LABEL"] + ":" if not input["UNIT"] else input["LABEL"] + " (" + input["UNIT"] + "):"
        _, inp = InputFloatControl.setup(
            label = label,
            min = input["MIN"],
            max = input["MAX"],
            value = input["VALUE"],
            row = row,
            event_callback=lambda value, inp=input, new_input=new_added_inp: self.on_input_value_change(value, inp, new_input),
            action_widget=self.create_remove_btn(input) if new_added_inp else None
            )
        inp.setEnabled(input["ENABLED"])
        self.dispatch_input_warning_styles(inp, input["INPUT_TYPE"], input["VALUE"], input["REQUIRED"], input["LABEL"])
        self.app.laserblood_widgets[input["LABEL"]] = inp         
        widget_container.setLayout(row)          
        if not new_added_inp:         
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3],)
            self.inputs_grid.setColumnStretch(position[1], input["STRETCH"])
        return widget_container    

    def create_text_input(self, input, new_added_inp=False):
        widget_container = QWidget()
        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 10)
        control = QVBoxLayout()
        position = input["POSITION"]
        label = input['LABEL'] + ":"
        label, inp = InputTextControl.setup(
            label=label,
            text=input['VALUE'],
            placeholder="",
            event_callback=lambda text, inp=input, new_input=new_added_inp: self.on_input_text_change(text, inp, new_input),
        )
        inp.setEnabled(input["ENABLED"])
        self.dispatch_input_warning_styles(inp, input["INPUT_TYPE"], input["VALUE"], input["REQUIRED"], input["LABEL"])
        self.app.laserblood_widgets[input["LABEL"]] = inp        
        h_box_header = QHBoxLayout()
        label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        h_box_header.addWidget(label)
        if new_added_inp:
            remove_btn = self.create_remove_btn(input)
            remove_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
            spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            h_box_header.addItem(spacer)
            h_box_header.addWidget(remove_btn)    
        control.addLayout(h_box_header)
        control.addWidget(inp)
        row.addLayout(control)
        widget_container.setLayout(row)
        if not new_added_inp:
            widget_container.setFixedWidth(234)
        if not new_added_inp:
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3])
            self.inputs_grid.setColumnStretch(position[1], input["STRETCH"])
        return widget_container

    
    def create_switch_input(self, input, new_added_inp = False):
        position = input["POSITION"]
        widget_container = QWidget()
        v_box = QVBoxLayout()
        label = input["LABEL"] + ":"
        label = QLabel(label)
        inp = SwitchControl(
            active_color=PALETTE_BLUE_1, width=100, height=30, checked=input["VALUE"]
        )
        inp.setEnabled(input["ENABLED"])
        inp.toggled.connect(lambda state, inp=input, new_input=new_added_inp: self.on_input_state_change(state, inp, new_input))
        self.app.laserblood_widgets[input["LABEL"]] = inp
        v_box.addWidget(label)
        v_box.addWidget(inp)
        widget_container.setLayout(v_box)
        if not new_added_inp:
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3], )
            self.inputs_grid.setColumnStretch(position[1], input["STRETCH"])
        return widget_container    
    
    def create_textarea_input(self, input, new_added_inp = False):
        widget_container = QWidget()
        control = QVBoxLayout() 
        control.setContentsMargins(0, 10, 12, 10)    
        position = input["POSITION"]
        label = input["LABEL"] + ":"
        label, self.textarea = InputTextareaControl.setup(
            label = label,
            text = input["VALUE"] if input["VALUE"] is not None else "",
            placeholder="",
            event_callback=self.create_textarea_event_callback(input, new_added_inp),
            )
        self.textarea.setEnabled(input["ENABLED"])
        self.textarea.setStyleSheet(GUIStyles.set_input_text_style(border_color="#3b3b3b", disabled_border_color="#3c3c3c"))
        control.addWidget(label)
        control.addWidget(self.textarea)
        widget_container.setLayout(control) 
        if not new_added_inp:   
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3], )
            self.inputs_grid.setColumnStretch(position[1], input["STRETCH"])
        return widget_container              
        
    def create_textarea_event_callback(self, input, new_input):       
        return lambda: self.on_input_textarea_change(input, self.textarea, new_input)    
            
    def create_select_input(self, input, new_added_inp = False):
        widget_container = QWidget()
        h_box = QHBoxLayout()
        h_box.setContentsMargins(0,10,0, 10)      
        position = input["POSITION"]
        label = input['LABEL'] + ":"
        control, inp, _, container = SelectControl.setup(
            label=label,
            options=input["OPTIONS"],
            selectedValue=input["VALUE"],
            container=h_box,
            prevent_default_value=True,
            event_callback=lambda value, inp=input, new_input=new_added_inp: self.on_input_value_change(value, inp, new_input),
        ) 
        widget_container.setLayout(container)
        inp.setEnabled(input["ENABLED"])
        self.dispatch_input_warning_styles(inp, input["INPUT_TYPE"], input["VALUE"], input["REQUIRED"], input["LABEL"])
        self.app.laserblood_widgets[input["LABEL"]] = inp       
        if not new_added_inp:           
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3]) 
        return widget_container              
    
    
    def handle_pdac_healty(self, value):
        pdac_weeks_enabled = value == 1 
        self.app.laserblood_widgets["Weeks (only PDAC)"].setEnabled(pdac_weeks_enabled)
    
    def on_input_value_change(self, value, input, new_input):
        if input["LABEL"] == "PDAC/Healthy":
            self.handle_pdac_healty(value)
        
        self.dispatch_input_warning_styles(self.app.laserblood_widgets[input["LABEL"]], input["INPUT_TYPE"], value, input["REQUIRED"], input["LABEL"])
        if new_input:
            self.update_new_added_inputs_settings(value, input)
        else:    
            self.update_settings(value, input)
        self.start_btn.setEnabled(LaserbloodMetadataPopup.laserblood_metadata_valid(self.app))    
    
    def on_input_state_change(self, state, input, new_input):
        if new_input:
            self.update_new_added_inputs_settings(state, input)
        else:    
            self.update_settings(state, input)
        self.start_btn.setEnabled(LaserbloodMetadataPopup.laserblood_metadata_valid(self.app))    
            
    
    def on_input_text_change(self, text, input, new_input):
        self.dispatch_input_warning_styles(self.app.laserblood_widgets[input["LABEL"]], input["INPUT_TYPE"], text, input["REQUIRED"], input["LABEL"])
        if new_input:
            self.update_new_added_inputs_settings(text, input)
        else:    
            self.update_settings(text, input)
        self.start_btn.setEnabled(LaserbloodMetadataPopup.laserblood_metadata_valid(self.app))    
        
    
    def on_input_textarea_change(self, input, textarea, new_input):
        text_content = textarea.toPlainText()
        if not new_input:
            self.update_settings(text_content, input)
        else:
            self.update_new_added_inputs_settings(text_content, input)      
    
    
    def dispatch_input_warning_styles(self, input, input_type, value, required, input_label):
        str_value = str(value)
        if not required or (required and value is not None and str_value != "0" and str_value != "0.0" and len(str_value.strip()) > 0) or input_label == "Weeks (only PDAC)":
            self.toggle_input_border_style(input_type, input, "#3b3b3b")
            return
        if (input_type == "int" or input_type == "float") and (str_value == "0" or str_value == "0.0") :
            self.toggle_input_border_style(input_type, input, "#EEBA56")
            return
        self.toggle_input_border_style(input_type, input, "#DA1212")
        
    
    def toggle_input_border_style(self, input_type, input, color):
        if input_type == 'int' or input_type == 'float':
            input.setStyleSheet(GUIStyles.set_input_number_style(border_color = color, disabled_border_color=color))
        if input_type == 'select':
            input.setStyleSheet(GUIStyles.set_input_select_style(border_color = color, disabled_border_color=color)) 
        if input_type == 'text':
           input.setStyleSheet(GUIStyles.set_input_text_style(border_color = color, disabled_border_color=color))         
    
    def create_remove_btn(self, input):
        remove_btn = QPushButton("")
        remove_btn.setStyleSheet("background-color: transparent; border: none")
        remove_btn.setIcon(QIcon(resource_path("assets/close-red-icon.png")))
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(partial(self.remove_input, input))
        return remove_btn
    
    def remove_input(self, input):
        filtered_inputs  = [inp for inp in self.app.laserblood_new_added_inputs if inp.get('LABEL') != input["LABEL"]]
        self.app.laserblood_new_added_inputs = filtered_inputs
        self.app.settings.setValue(NEW_ADDED_LASERBLOOD_INPUTS_KEY, json.dumps(self.app.laserblood_new_added_inputs)) 
        self.app.clear_layout_tree(self.new_added_inputs_grid)   
        self.init_new_input_added_layout()    
    
    
    def on_save_btn_click(self):
        self.close()
    
    @staticmethod
    def laserblood_metadata_valid(app):
        settings = app.laserblood_settings
        custom_settings = app.laserblood_new_added_inputs
        def check_required_values(data):
            return all(
                d['REQUIRED'] is False or (
                    d['VALUE'] is not None and (
                        (d['INPUT_TYPE'] == 'select' and  d['VALUE'] != 0) or
                        (d['INPUT_TYPE'] != 'select' and str(d['VALUE']).strip())
                    )
                )
                for d in data
            )
         
        settings_valid = check_required_values(settings)
        custom_settings_valid = check_required_values(custom_settings)
        laser_type_valid = app.laserblood_laser_type is not None
        filter_type_valid = app.laserblood_filter_type is not None
        return settings_valid and custom_settings_valid and laser_type_valid and filter_type_valid
    
    def update_new_added_inputs_settings(self, value, input):
        next((setting.update({"VALUE": value}) for setting in self.app.laserblood_new_added_inputs if setting.get("LABEL") == input["LABEL"]), None)
        self.app.settings.setValue(NEW_ADDED_LASERBLOOD_INPUTS_KEY, json.dumps(self.app.laserblood_new_added_inputs))        
          
    
    def update_settings(self, value, input):
        next((setting.update({"VALUE": value}) for setting in self.app.laserblood_settings if setting.get("LABEL") == input["LABEL"]), None)
        self.app.settings.setValue(METADATA_LASERBLOOD_KEY, json.dumps(self.app.laserblood_settings))
 
    @staticmethod
    def set_average_CPS(cps_counts, app):
        if cps_counts:
            total_avg = sum(cps_counts) / len(cps_counts)
            total_avg_rounded = round(total_avg, 2)
        else:
            total_avg_rounded = 0
        next((setting.update({"VALUE": total_avg_rounded}) for setting in app.laserblood_settings if setting.get("LABEL") == "Average CPS"), None)
        app.settings.setValue(METADATA_LASERBLOOD_KEY, json.dumps(app.laserblood_settings))
        
    
    @staticmethod
    def set_frequency_mhz(frequency_mhz, app):
        if frequency_mhz != 0.0:
             next((setting.update({"VALUE": frequency_mhz}) for setting in app.laserblood_settings if setting.get("LABEL") == "Laser repetition rate"), None)
             app.settings.setValue(METADATA_LASERBLOOD_KEY, json.dumps(app.laserblood_settings))   
        

    @staticmethod
    def set_average_SBR(SBR_counts, app):
        if SBR_counts:
            total_avg = sum(SBR_counts) / len(SBR_counts)
            total_avg_rounded = round(total_avg, 2)
        else:
            total_avg_rounded = 0   
        next((setting.update({"VALUE": total_avg_rounded}) for setting in app.laserblood_settings if setting.get("LABEL") == "Average SBR"), None)
        app.settings.setValue(METADATA_LASERBLOOD_KEY, json.dumps(app.laserblood_settings))        

        
    @staticmethod     
    def set_FPGA_firmware(app):
        frequency_mhz = app.get_frequency_mhz()
        firmware_selected, _ = app.get_firmware_selected(frequency_mhz)
        fpga = ""
        if firmware_selected is not None and "100ps" in firmware_selected:
            fpga = "100ps"
        if firmware_selected is not None and "100ps" not in firmware_selected: 
            fpga = "300ps"   
        next((setting.update({"VALUE": fpga}) for setting in app.laserblood_settings if setting.get("LABEL") == "FPGA firmware type"), "")
        app.settings.setValue(METADATA_LASERBLOOD_KEY, json.dumps(app.laserblood_settings))   
   
   
    @staticmethod
    def set_cps_threshold(app, cps_threshold):
        next((setting.update({"VALUE": cps_threshold}) for setting in app.laserblood_settings if setting.get("LABEL") == "Pile-up Threshold"), 0)
        app.settings.setValue(METADATA_LASERBLOOD_KEY, json.dumps(app.laserblood_settings))   
        
          
        
    def center_window(self):   
        self.setMinimumWidth(700)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())
        
        

        

 
    

            
