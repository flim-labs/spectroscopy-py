
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
from components.file_utils import save_laserblood_metadata_json
from components.input_number_control import InputFloatControl, InputNumberControl
from components.input_text_control import InputTextControl, InputTextareaControl
from components.layout_utilities import draw_layout_separator
from components.logo_utilities import TitlebarIcon
from components.resource_path import resource_path
from components.gui_styles import GUIStyles
from components.select_control import SelectControl
from components.switch_control import SwitchControl
from laserblood_settings import LASER_TYPES, LASERBLOOD_METADATA_POPUP, METADATA_LASERBLOOD_KEY, NEW_ADDED_LASERBLOOD_INPUTS_KEY, SETTINGS_FILTER_TYPE, SETTINGS_LASER_TYPE
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
        self.init_inputs_grid()
        self.init_new_input_added_layout()
        self.q_v_box_inputs_container.addLayout(self.inputs_grid)
        self.q_v_box_inputs_container.addLayout(self.new_added_inputs_grid)
        self.init_laser_filter_settings_layout()
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
        lasers_v_box = self.create_laser_layout()
        self.create_filters_layout()
        add_inputs_layout = self.create_add_new_input_layout()
        main_container.addLayout(lasers_v_box)
        main_container.addSpacing(20)
        main_container.addLayout(self.filters_grid)
        main_container.addStretch(1)
        main_container.addLayout(add_inputs_layout)
        main_container.addSpacing(20)
        self.laser_settings_container.addLayout(main_container) 
        
                    
    def create_laser_layout(self):
        laser_types = LASER_TYPES
        title = QLabel("LASER TYPE")
        lasers_v_box = QVBoxLayout()
        lasers_v_box.addWidget(title)
        for laser in laser_types:
            laser_button = FancyButton(laser["LABEL"])
            lasers_v_box.addWidget(laser_button)
            self.laser_buttons.append((laser_button, laser["LABEL"]))
        for button, name in self.laser_buttons:
            button.set_selected(name == self.selected_laser)
            def on_toggle(toggled_name):
                for b, n in self.laser_buttons:
                    b.set_selected(n == toggled_name)
                    self.on_laser_selected(toggled_name) 
            button.clicked.connect(lambda _, n=name: on_toggle(n))
            button.set_selected(self.selected_laser == name) 
        return lasers_v_box
    
    
    def create_filters_layout(self):
        laser_selected = next((laser for laser in LASER_TYPES if laser["LABEL"] == self.selected_laser), None)
        filter_types = laser_selected["FILTERS"]
        title = QLabel("FILTER TYPE")
        self.filters_grid.addWidget(title, 0, 0, 1, 2) 
        row, col = 1, 0
        for filter in filter_types:
            filter_button = FancyButton(
                filter,
                selected_color="#DA1212",
                hover_color="#E23B3B",
                pressed_color="#B01010"
                )
            self.filters_grid.addWidget(filter_button, row, col)
            self.filter_buttons.append((filter_button, filter))
            col += 1
            if col == 2:  
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
            
        
    def on_laser_selected(self, laser):
        self.selected_laser = laser 
        self.app.laserblood_laser_type = laser
        self.app.settings.setValue(SETTINGS_LASER_TYPE, self.selected_laser)
        self.selected_filter = None
        self.app.settings.setValue(SETTINGS_FILTER_TYPE, None)
        self.app.clear_layout_tree(self.filters_grid)
        self.filter_buttons.clear()
        self.create_filters_layout()
        
    def on_filter_selected(self, filter):
        self.selected_filter = filter  
        self.app.laserblood_filter_type = filter
        self.app.settings.setValue(SETTINGS_FILTER_TYPE, self.selected_filter)        

    def set_add_button_enabled(self):
        if "add_button" in self.widgets:
            add_button_enabled = len(self.new_input_type.strip()) > 0 and len(self.new_input_label.strip()) > 0
            self.widgets["add_button"].setEnabled(add_button_enabled)
            
    
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
            "MAX": None,
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
        self.widgets["inp_unit"].clear()
        self.widgets["inp_label"].clear()

    def create_add_new_input_layout(self):
        h_box = QHBoxLayout()
        def on_inp_type_change(value):
            self.new_input_type = "number" if value == 0 else "text"
            if "inp_unit_control" in self.layouts:
                self.app.show_layout(self.layouts["inp_unit_control"]) if value == 0 else self.app.hide_layout(self.layouts["inp_unit_control"])
            if value == 1:
                self.new_input_unit = ""
                if "inp_unit" in self.widgets:
                    self.widgets["inp_unit"].clear()
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
        self.widgets["inp_type"] = inp_type
        inp_type.setStyleSheet(GUIStyles.set_input_select_style())
        # LABEL
        inp_label_control = QVBoxLayout() 
        inp_label_label, inp_label = InputTextControl.setup(
            label="Input label:",
            text="",
            placeholder="",
            event_callback=lambda text: on_inp_label_change(text),
        )
        inp_label.setStyleSheet(GUIStyles.set_input_text_style(border_color="#3b3b3b")) 
        inp_label_control.addWidget(inp_label_label)
        inp_label_control.addWidget(inp_label)
        self.widgets["inp_label"] = inp_label
        # UNIT 
        inp_unit_control = QVBoxLayout()        
        inp_unit_label, inp_unit = InputTextControl.setup(
            label="Input unit:",
            text="",
            placeholder="",
            event_callback=lambda text: on_inp_unit_change(text),
        )
        inp_unit.setStyleSheet(GUIStyles.set_input_text_style(border_color="#3b3b3b"))  
        self.widgets["inp_unit"] = inp_unit
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
        self.widgets["add_button"] = add_button
        h_box.addLayout(h_box_inp_type)
        h_box.addLayout(inp_label_control)
        h_box.addLayout(inp_unit_control)
        h_box.addWidget(add_button)
        return h_box

    def dispatch_create_input(self, input, new_added):
        input_type = input["INPUT_TYPE"] 
        match input_type:
            case "int":
                widget_container = self.create_int_input(input, new_added_inp=new_added)
            case "float":
                widget_container = self.create_float_input(input, new_added_inp=new_added)
            case "text":
                widget_container = self.create_text_input(input, new_added_inp=new_added)
            case "select":
                widget_container = self.create_select_input(input, new_added_inp=new_added)
            case "boolean":
                widget_container = self.create_switch_input(input, new_added_inp=new_added)
            case "textarea":
                widget_container = self.create_textarea_input(input, new_added_inp=new_added)  
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
        _, inp = InputNumberControl.setup(
            label = f"{input["LABEL"]}:" if not input["UNIT"] else f"{input["LABEL"]} ({input["UNIT"]}):",
            min = input["MIN"],
            max = input["MAX"],
            value = input["VALUE"],
            row = row,
            event_callback=lambda value, inp=input, new_input = new_added_inp: self.on_input_value_change(value, inp, new_input),
        )
        inp.setEnabled(input["ENABLED"])
        self.dispatch_input_warning_styles(inp, input["INPUT_TYPE"], input["VALUE"])
        self.widgets[input["LABEL"]] = inp
        widget_container.setLayout(row)
        if not new_added_inp:
            widget_container.setFixedWidth(236)        
        if not new_added_inp:            
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3],)
        return widget_container    
    
    def create_float_input(self, input, new_added_inp = False):
        widget_container = QWidget()
        row = QHBoxLayout()
        row.setContentsMargins(0,10,0, 10)         
        position = input["POSITION"]
        _, inp = InputFloatControl.setup(
            label = f"{input["LABEL"]}:" if not input["UNIT"] else f"{input["LABEL"]} ({input["UNIT"]}):",
            min = input["MIN"],
            max = input["MAX"],
            value = input["VALUE"],
            row = row,
            event_callback=lambda value, inp=input, new_input=new_added_inp: self.on_input_value_change(value, inp, new_input),
            action_widget=self.create_remove_btn(input) if new_added_inp else None
            )
        inp.setEnabled(input["ENABLED"])
        self.dispatch_input_warning_styles(inp, input["INPUT_TYPE"], input["VALUE"])
        self.widgets[input["LABEL"]] = inp         
        widget_container.setLayout(row)   
        if not new_added_inp:
            widget_container.setFixedWidth(236)         
        if not new_added_inp:         
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3],)
        return widget_container    

    def create_text_input(self, input, new_added_inp=False):
        widget_container = QWidget()
        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 10)
        control = QVBoxLayout()
        position = input["POSITION"]
        label, inp = InputTextControl.setup(
            label=f"{input['LABEL']}:",
            text=input['VALUE'],
            placeholder="",
            event_callback=lambda text, inp=input, new_input=new_added_inp: self.on_input_text_change(text, inp, new_input),
        )
        inp.setEnabled(input["ENABLED"])
        self.dispatch_input_warning_styles(inp, input["INPUT_TYPE"], input["VALUE"])
        self.widgets[input["LABEL"]] = inp        
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
            widget_container.setFixedWidth(220)
        if not new_added_inp:
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3])
        return widget_container

    
    def create_switch_input(self, input, new_added_inp = False):
        position = input["POSITION"]
        widget_container = QWidget()
        v_box = QVBoxLayout()
        label = QLabel(f"{input["LABEL"]}:")
        inp = SwitchControl(
            active_color=PALETTE_BLUE_1, width=100, height=30, checked=input["VALUE"]
        )
        inp.setEnabled(input["ENABLED"])
        inp.toggled.connect(lambda state, inp=input, new_input=new_added_inp: self.on_input_state_change(state, inp, new_input))
        self.widgets[input["LABEL"]] = inp
        v_box.addWidget(label)
        v_box.addWidget(inp)
        widget_container.setLayout(v_box)
        if not new_added_inp:
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3], )
        return widget_container    
    
    def create_textarea_input(self, input, new_added_inp = False):
        widget_container = QWidget()
        control = QVBoxLayout() 
        control.setContentsMargins(0, 10, 12, 10)    
        position = input["POSITION"]
        label, self.textarea = InputTextareaControl.setup(
            label = f"{input["LABEL"]}:",
            text = input["VALUE"] if input["VALUE"] is not None else "",
            placeholder="",
            event_callback=self.create_textarea_event_callback(input, new_added_inp),
            )
        self.textarea.setEnabled(input["ENABLED"])
        self.textarea.setStyleSheet(GUIStyles.set_input_text_style(border_color="#3b3b3b"))
        control.addWidget(label)
        control.addWidget(self.textarea)
        widget_container.setLayout(control) 
        if not new_added_inp:   
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3], )
        return widget_container              
        
    def create_textarea_event_callback(self, input, new_input):       
        return lambda: self.on_input_textarea_change(input, self.textarea, new_input)    
            
    def create_select_input(self, input, new_added_inp = False):
        widget_container = QWidget()
        h_box = QHBoxLayout()
        h_box.setContentsMargins(0,10,0, 10)      
        position = input["POSITION"]
        control, inp, _, container = SelectControl.setup(
            label=f"{input['LABEL']}:",
            options=input["OPTIONS"],
            selectedValue=input["VALUE"],
            container=h_box,
            prevent_default_value=True,
            event_callback=lambda value, inp=input, new_input=new_added_inp: self.on_input_value_change(value, inp, new_input),
        ) 
        widget_container.setLayout(container)
        inp.setEnabled(input["ENABLED"])
        self.dispatch_input_warning_styles(inp, input["INPUT_TYPE"], input["VALUE"])
        self.widgets[input["LABEL"]] = inp  
        if not new_added_inp:
            widget_container.setFixedWidth(236)              
        if not new_added_inp:           
            self.inputs_grid.addWidget(widget_container, position[0], position[1], position[2], position[3]) 
        return widget_container              
        
    
    def on_input_value_change(self, value, input, new_input):
        self.dispatch_input_warning_styles(self.widgets[input["LABEL"]], input["INPUT_TYPE"], value)
        if new_input:
            self.update_new_added_inputs_settings(value, input)
        else:    
            self.update_settings(value, input)
    
    def on_input_state_change(self, state, input, new_input):
        if new_input:
            self.update_new_added_inputs_settings(state, input)
        else:    
            self.update_settings(state, input)
    
    def on_input_text_change(self, text, input, new_input):
        self.dispatch_input_warning_styles(self.widgets[input["LABEL"]], input["INPUT_TYPE"], text)
        if new_input:
            self.update_new_added_inputs_settings(text, input)
        else:    
            self.update_settings(text, input)
        
    def on_input_textarea_change(self, input, textarea, new_input):
        text_content = textarea.toPlainText()
        if not new_input:
            self.update_settings(text_content, input)
        else:
            self.update_new_added_inputs_settings(text_content, input)      
    
    
    def dispatch_input_warning_styles(self, input, input_type, value):
        str_value = str(value)
        if value is not None and str_value != "0" and str_value != "0.0" and len(str_value.strip()) > 0:
            self.toggle_input_border_style(input_type, input, "#3b3b3b")
            return
        if (input_type == "int" or input_type == "float") and (str_value == "0" or str_value == "0.0"):
            self.toggle_input_border_style(input_type, input, "#EEBA56")
            return
        self.toggle_input_border_style(input_type, input, "#DA1212")
        
    
    def toggle_input_border_style(self, input_type, input, color):
        if input_type == 'int' or input_type == 'float':
            input.setStyleSheet(GUIStyles.set_input_number_style(border_color = color))
        if input_type == 'select':
            input.setStyleSheet(GUIStyles.set_input_select_style(border_color = color)) 
        if input_type == 'text':
           input.setStyleSheet(GUIStyles.set_input_text_style(border_color = color))         
    
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

    
    @staticmethod
    def laserblood_metadata_valid(app):
        settings = app.laserblood_settings
        custom_settings = app.laserblood_new_added_inputs
        def check_required_values(data):
            return all(
            d['REQUIRED'] is False or (
                d['VALUE'] is not None and (
                    (d['INPUT_TYPE'] == 'select' and d['VALUE'] != 0) or
                    (d['INPUT_TYPE'] != 'select' and str(d['VALUE']).strip())
                )
            )
            for d in data
        )
        settings_valid = check_required_values(settings)
        custom_settings_valid = check_required_values(custom_settings)
        print(settings_valid)
        print(custom_settings_valid)
        return settings_valid and custom_settings_valid

    
    def update_new_added_inputs_settings(self, value, input):
        next((setting.update({"VALUE": value}) for setting in self.app.laserblood_new_added_inputs if setting.get("LABEL") == input["LABEL"]), None)
        self.app.settings.setValue(NEW_ADDED_LASERBLOOD_INPUTS_KEY, json.dumps(self.app.laserblood_new_added_inputs))        
          
    
    def update_settings(self, value, input):
        next((setting.update({"VALUE": value}) for setting in self.app.laserblood_settings if setting.get("LABEL") == input["LABEL"]), None)
        self.app.settings.setValue(METADATA_LASERBLOOD_KEY, json.dumps(self.app.laserblood_settings))
        
    def center_window(self):   
        self.setMinimumWidth(700)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())
        
        

        

 
    

            
