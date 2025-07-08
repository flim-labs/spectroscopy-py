from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from PyQt6.QtWidgets import QStyleFactory


class GUIStyles:
    @staticmethod
    def set_default_theme(theme):
        QApplication.setStyle(QStyleFactory.create(theme))
        
    @staticmethod        
    def customize_theme(window, bg = QColor(28, 28, 28, 128), fg = QColor(255, 255, 255)):
        palette = QPalette()
        background_color = bg
        palette.setColor(QPalette.ColorRole.Window, background_color)
        palette.setColor(QPalette.ColorRole.WindowText, fg)
        window.setPalette(palette)  
        window.setStyleSheet(
            """
        QLabel {
            color: #f8f8f8;
            font-family: "Montserrat";
        }
        """
        )  

    @staticmethod
    def set_fonts(font_name="Montserrat", font_size=10):
        general_font = QFont("Montserrat", 10)
        QApplication.setFont(general_font)

    @staticmethod
    def set_fonts_deep(root):
        if root is None:
            return
        for child in root.findChildren(QWidget):
            if child.objectName() == "font":
                child.setFont(QFont("Montserrat", 14, QFont.Weight.Thin))
            if child.metaObject().className() == "QPushButton":
                child.setFont(QFont("Montserrat", 14, QFont.Weight.Thin))
            GUIStyles.set_fonts_deep(child)
        for child in root.findChildren(QLabel):
            child.setFont(QFont("Montserrat", 14, QFont.Weight.Bold))
            GUIStyles.set_fonts_deep(child)

    @staticmethod
    def set_label_style(color="#f8f8f8"):
        return """
            QLabel{
                color: #f8f8f8;
                font-family: "Montserrat";
            }
        """

    @staticmethod
    def set_main_title_style():
        return """
            QLabel{
                color: #23F3AB;
                font-family: "Montserrat";
                font-size: 40px;
                font-weight: 100;
                font-style: italic;
            }
        """

    @staticmethod
    def button_style(
        color_base, color_border, color_hover, color_pressed, min_width, override=""
    ):
        return f"""
            QPushButton {{
                background-color: {color_base};
                border: 1px solid {color_border};
                font-family: "Montserrat";
                color: white;
                padding: 8px;
                letter-spacing: 0.1em;
                min-width: {min_width};
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }}

            QPushButton:hover {{
                background-color: {color_hover};
                border: 2px solid {color_hover};
            }}

            QPushButton:pressed {{
                background-color: {color_pressed};
                border: 2px solid {color_pressed};
            }}
            
            QPushButton#btn:disabled {{
                background-color: #cecece;
                border: 2px solid #cecece;
                color: #8c8b8b;
            }}
            QPushButton#download_btn:disabled {{
                background-color: #cecece;
                border: 2px solid #cecece;
                color: white;
            }}
            
            {override}
        """

    @staticmethod
    def _set_button_style(button, color_dict, min_width):
        color_base, color_border, color_hover, color_pressed = (
            color_dict["base"],
            color_dict["border"],
            color_dict["hover"],
            color_dict["pressed"],
        )
        button.setStyleSheet(
            GUIStyles.button_style(
                color_base, color_border, color_hover, color_pressed, min_width
            )
        )

    @staticmethod
    def set_start_btn_style(button):
        color_dict = {
            "base": "#11468F",
            "border": "#11468F",
            "hover": "#0053a4",
            "pressed": "#0D3A73",
        }
        GUIStyles._set_button_style(button, color_dict, min_width="90px")

    @staticmethod
    def set_stop_btn_style(button):
        color_dict = {
            "base": "#DA1212",
            "border": "#DA1212",
            "hover": "#E23B3B",
            "pressed": "#B01010",
        }
        GUIStyles._set_button_style(button, color_dict, min_width="90px")

    @staticmethod
    def set_reset_btn_style(button):
        color_dict = {
            "base": "#8d4ef2",
            "border": "#8d4ef2",
            "hover": "#a179ff",
            "pressed": "#6b3da5",
        }
        GUIStyles._set_button_style(button, color_dict, min_width="90px")

    @staticmethod
    def set_config_btn_style(button):
        color_dict = {
            "base": "transparent",
            "border": "transparent",
            "hover": "#E23B3B",
            "pressed": "#B01010",
        }
        GUIStyles._set_button_style(button, color_dict, min_width="90px")
        # set no rounded corners
        button.setStyleSheet(
            button.styleSheet()
            + "QPushButton {border-radius: 0px; border-bottom: 1px solid #D01B1B; padding-left: 10px; padding-right: 10px;}  QPushButton:checked {background-color: #D01B1B; border: 1px solid transparent;}"
        )
        
    @staticmethod            
    def checkbox_wrapper_style():
        return """
            QWidget#ch_checkbox_wrapper, QWidget#simple_checkbox_wrapper {
                border: 1px solid #3b3b3b;
                background-color: transparent;
                padding: 0;
            } 
            QWidget#simple_checkbox_wrapper {
                border-radius: 5px;
            } 
            QWidget{
                color: #f8f8f8;
                font-family: "Montserrat";
                font-size: 12px;
                padding: 0;
            }        
        """ 

    @staticmethod
    def set_checkbox_style():
        return """
            QCheckBox {
                spacing: 5px;
                color: #f8f8f8;
                font-family: "Montserrat";
                font-size: 14px;
                letter-spacing: 0.1em;
                border: 1px solid #252525;
                border-radius: 5px;
                padding: 10px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 10px;  
            }

            QCheckBox::indicator:unchecked {
                background-color: #6b6a6a;
            }

            QCheckBox::indicator:checked {
                background-color: #1E90FF;
            }
        """

    @staticmethod
    def set_input_number_style(min_width = "60px"):
        return f"""
            QDoubleSpinBox, QSpinBox {{
                color: #f8f8f8;
                font-family: "Montserrat";
                font-size: 14px;
                padding: 8px;
                min-width: {min_width};
                min-height: 18px;
                border: 1px solid #3b3b3b;
                border-radius: 5px;
                background-color: transparent;
            }}
            QDoubleSpinBox:disabled, QSpinBox:disabled {{
            color: #404040;  
            border-color: #3c3c3c;
            }}        
        """
    
    @staticmethod    
    def set_input_text_style():
        return """
           QLineEdit  {
                color: #f8f8f8;
                font-family: "Montserrat";
                font-size: 14px;
                padding: 8px;
                min-width: 60px;
                border: 1px solid #11468F;
                border-radius: 5px;
                background-color: transparent;
                color: #1E90FF;
            }
            QLineEdit:disabled, QLineEdit:disabled {
            color: #404040;  
            border-color: #3c3c3c;
            }        
        """    
        

    @staticmethod
    def set_input_select_style():
        return """
            QComboBox {
                color: #f8f8f8;
                font-family: "Montserrat";
                font-size: 14px;
                padding: 8px;
                border: 1px solid #3b3b3b;
                border-radius: 5px;
                background-color: transparent;
            }
            QComboBox:disabled {
                color: darkgrey;  
                border-color: #3c3c3c;
            } 
            QComboBox:on { 
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
            }

           QComboBox QAbstractItemView {
            font-family: "Montserrat";
            border: 1px solid #3b3b3b;
            border-bottom-left-radius: 5px;
            border-bottom-right-radius: 5px;
            background-color: #181818;
            color: #f8f8f8;
            selection-background-color: #8d4ef2;
            }   
        """

    @staticmethod
    def set_msg_box_style():
        return """
            QMessageBox {
                background-color: #080808;   
            }
            QMessageBox QLabel {
                color: #f8f8f8;
                font-family: "Montserrat";
                font-weight: 300;
                font-size: 16px;
            }
            QMessageBox QIcon {
                width: 20px;
            }  
            QMessageBox QPushButton {
                background-color: #181818;
                color: white;
                width: 150px;
                padding: 12px;
                font-size: 14px;
                font-family: "Montserrat";
            }   
                 
        """

    @staticmethod
    def set_cps_label_style():
        return """
            QLabel{
                color: white;
                font-weight: 700;
                font-family: "Montserrat";
                font-size: 26px;
            }
        """
        
    @staticmethod            
    def toggle_collapse_button():
        return """
            QPushButton{
                background-color: transparent;
                border-radius: 15px;
                qproperty-iconSize: 15px;
                border: 1px solid #808080;
            } 
        """   
        
   
    @staticmethod               
    def chart_wrapper_style():
        return """
            QWidget#chart_wrapper {
                border: 1px solid #3b3b3b;
                background-color: #141414;
                padding: 0;
            }       
        """      
        
    @staticmethod       
    def plots_config_popup_style():
        return """
            QWidget {
                background-color: #141414;
                color: #6e6b6b;
                font-family: Montserrat;
                font-size: 14px;
            }
            QLabel#prompt_text {
                color: white;
                font-size: 18px;
            } 
        """    
            
    @staticmethod            
    def set_simple_checkbox_style(color):
        return f"""
            QCheckBox {{
                spacing: 5px;
                color: #f8f8f8;
                font-family: "Montserrat";
                font-size: 14px;
                letter-spacing: 0.1em;
                border-radius: 5px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 7px;  
            }}

            QCheckBox::indicator:unchecked {{
                background-color: #6b6a6a;
            }}

            QCheckBox::indicator:checked {{
                background-color: {color};
            }}
        """ 
        
    @staticmethod    
    def set_context_menu_style(base, selected, pressed):
        return f"""
        QWidget {{
            background-color: #181818;  
        }}
        QMenu {{
            margin: 0;   
            border-radius: 4px;
            background: #181818;     
            padding: 5px 0;  
        }}
        QMenu::item {{
            background-color: {base}; 
            color: white; 
            height: 20px;
            margin: 2px 0px 2px 0px;
            border-radius: 4px;   
            font-family: "Montserrat";
            font-size: 12px;
            font-weight: bold;
            padding:10px 13px 10px 10px;
            width: 150px;
            min-width: 120px;
        }}
        QMenu::item:selected {{
            background-color: {selected};  
         }}
        QMenu::item:pressed {{
            background-color: {pressed};  
         }}
        """ 
        
    @staticmethod
    def set_lin_log_widget_style():
        return """
            QWidget {
                background-color: transparent;
            }
            QLabel {
                color: "#cecece";
                font-family: Montserrat;
                font-size: 14px;
            }
        """
        
    @staticmethod
    def set_slider_style():
        return """
            """        
            
    @staticmethod
    def acquire_read_btn_style():
        return f"""
            QPushButton {{
                font-family: "Montserrat";
                letter-spacing: 0.1em;
                padding: 10px 12px;
                font-size: 14px;
                font-weight: bold;;
                min-width: 60px;
            }}
            QPushButton#acquire_btn{{ 
                border-top-left-radius: 3px;
                border-bottom-left-radius: 3px;   
            }}
            QPushButton#read_btn{{  
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
                
            }}
        """   
        
    @staticmethod
    def acquisition_time_countdown_style():
        return """
            QLabel {
                color: #1E90FF;
                font-size: 18px;
                padding: 0 8px 8px 16px;
            }
        """                     
                        

    @staticmethod
    def progress_bar_style(color: str):
        return f"""
            QLabel {{
                color: {color};
                font-family: "Montserrat";
                font-size: 18px;
                font-weight: bold;
                
            }} 
            QProgressBar {{
                color: transparent;
                background-color: white;
                padding: 0;
            }}
            QProgressBar::chunk {{
                background: {color};
                color: transparent;
            }}               
        """
        
    @staticmethod
    def time_tagger_style():
        return f"""
            QWidget#container {{
                border-radius: 5px;
                border: 2px solid #0053a4;
                padding: 0;
                
            }} 
            QWidget {{
                background-color: white;
                padding: 0;
            }}    
            QCheckBox {{
                spacing: 10px;
                color: #0053a4;
                font-family: "Montserrat";
                font-weight: 800;
                font-size: 14px;
                letter-spacing: 0.1em;
                border: none;
                border-radius: 5px;
                padding: 0 10px 0 0;
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 10px;  
            }}

            QCheckBox::indicator:unchecked {{
                background-color: #6b6a6a;
            }}

            QCheckBox::indicator:checked {{
                background-color: #1fd400;
            }}                   
        """        
        
    @staticmethod
    def SBR_label(font_size="22px", background_color="#0a0a0a", color="#f72828"):
        return f"""
            QLabel {{
                color: {color};
                font-family: "Montserrat";
                font-size: {font_size};
                font-weight: bold;
                background-color: {background_color}; 
                padding: 2px;
            }} 
                     
        """     
        
    @staticmethod
    def check_card_message(color):
        return f"""
            QLabel {{
                color: {color}; 
                background-color: #242424;
                border-left: 1px solid {color}; 
                border-right: 1px solid {color}; 
                border-radius: 0; 
                padding: 0 4px;
                font-weight: 800;
                font-size: 14px;
            }}                
        """                  