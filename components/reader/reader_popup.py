"""
reader_popup.py
===============
ReaderPopup — QWidget popup for loading data files and selecting plots to display.
"""

import glob
import json
import os
from functools import partial

import numpy as np
from utils.gui_styles import GUIStyles
from utils.helpers import extract_channel_from_label
from components.input_text_control import InputTextControl
from utils.layout_utilities import clear_layout
from utils.resource_path import resource_path
import settings.settings as s
from utils.logo_utilities import TitlebarIcon

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGridLayout,
    QCheckBox,
    QLabel,
    QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon


class ReaderPopup(QWidget):
    """A popup window for loading data files and selecting plots to display."""

    def __init__(self, window, tab_selected):
        """Initializes the ReaderPopup.

        Args:
            window: The main application window instance.
            tab_selected (str): The identifier of the tab that opened the popup.
        """
        from components.reader.read_data_utils import get_data_type

        super().__init__()
        # Prevent widget from being shown during construction to avoid visual glitches
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)
        self.app = window
        self.tab_selected = tab_selected
        self.widgets = {}
        self.layouts = {}
        self.channels_checkboxes = []
        self.channels_checkbox_first_toggle = True
        self.data_type = get_data_type(self.tab_selected)
        self.file_type_checkboxes = {}
        self.file_input_containers = {}
        self.setWindowTitle("Read data")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg=QColor(20, 20, 20))
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        plot_btn_row = self.create_plot_btn_layout()
        load_file_row = self.init_file_load_ui()
        self.layout.addSpacing(10)
        self.layout.insertLayout(1, load_file_row)
        self.layout.addSpacing(20)
        channels_layout = self.init_channels_layout()
        if channels_layout is not None:
            self.layout.insertLayout(2, channels_layout)
        self.layout.addSpacing(20)
        self.layout.insertLayout(3, plot_btn_row)
        self.setLayout(self.layout)
        self.setStyleSheet(GUIStyles.plots_config_popup_style())
        self.app.widgets[s.READER_POPUP] = self
        self.center_window()
        self.setUpdatesEnabled(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)

    # ------------------------------------------------------------------
    # File type selector (fitting tab only)
    # ------------------------------------------------------------------

    def create_file_type_selector(self):
        """Creates radio button selector for choosing which file types to load (fitting tab only).

        Returns:
            QVBoxLayout: The layout containing the radio button controls.
        """
        from PyQt6.QtWidgets import QRadioButton, QButtonGroup

        v_box = QVBoxLayout()
        v_box.setSpacing(10)

        title = QLabel("SELECT FILE TYPE TO LOAD:")
        title.setStyleSheet(
            "font-size: 16px; font-family: 'Montserrat'; font-weight: bold;"
        )
        v_box.addWidget(title)

        radio_layout = QHBoxLayout()
        radio_layout.setSpacing(20)
        button_group = QButtonGroup(self)

        _rb_style = """
            QRadioButton {
                font-size: 14px;
                font-family: 'Montserrat';
                color: white;
            }
            QRadioButton::indicator { width: 13px; height: 13px; }
            QRadioButton::indicator::unchecked {
                border: 2px solid gray;
                background-color: transparent;
                border-radius: 6px;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #DA1212;
                background-color: #DA1212;
                border-radius: 6px;
            }
        """

        last_selection = self.app.settings.value(
            "fitting_read_last_file_type", "spectroscopy"
        )

        spectroscopy_rb = QRadioButton("Spectroscopy files")
        spectroscopy_rb.setStyleSheet(_rb_style)
        spectroscopy_rb.setChecked(last_selection == "spectroscopy")
        spectroscopy_rb.toggled.connect(
            lambda checked: self.on_file_type_changed("spectroscopy", checked)
        )
        button_group.addButton(spectroscopy_rb)
        self.file_type_checkboxes["spectroscopy"] = spectroscopy_rb
        radio_layout.addWidget(spectroscopy_rb)

        fitting_rb = QRadioButton("Fitting files")
        fitting_rb.setStyleSheet(_rb_style)
        fitting_rb.setChecked(last_selection == "fitting")
        fitting_rb.toggled.connect(
            lambda checked: self.on_file_type_changed("fitting", checked)
        )
        button_group.addButton(fitting_rb)
        self.file_type_checkboxes["fitting"] = fitting_rb
        radio_layout.addWidget(fitting_rb)

        radio_layout.addStretch()
        v_box.addLayout(radio_layout)
        return v_box

    def on_file_type_changed(self, file_type, checked):
        """Handles radio button changes to show/hide file input rows.

        Args:
            file_type (str): The file type ('spectroscopy' or 'fitting').
            checked (bool): Whether this radio button is now checked.
        """
        if not checked:
            return
        self.app.settings.setValue("fitting_read_last_file_type", file_type)
        if (
            hasattr(self, "file_type_stack")
            and file_type in self.file_type_stack_indices
        ):
            self.file_type_stack.setCurrentIndex(self.file_type_stack_indices[file_type])
        if (
            hasattr(self.app, "control_inputs")
            and "bin_metadata_button" in self.app.control_inputs
        ):
            self.app.control_inputs["bin_metadata_button"].setVisible(
                file_type == "spectroscopy"
            )
        self.current_file_type_selection = file_type

    def check_and_restore_file_type_selection(self):
        """Check if fitting files are actually loaded; if not, restore spectroscopy selection."""
        if (
            hasattr(self, "current_file_type_selection")
            and self.current_file_type_selection == "fitting"
        ):
            fitting_files = self.app.reader_data["fitting"]["files"]["fitting"]
            has_fitting_files = (
                isinstance(fitting_files, list) and len(fitting_files) > 0
            ) or (isinstance(fitting_files, str) and len(fitting_files.strip()) > 0)
            if not has_fitting_files:
                if "spectroscopy" in self.file_type_checkboxes:
                    self.file_type_checkboxes["spectroscopy"].setChecked(True)
            else:
                if (
                    hasattr(self.app, "control_inputs")
                    and "bin_metadata_button" in self.app.control_inputs
                ):
                    self.app.control_inputs["bin_metadata_button"].setVisible(False)

    # ------------------------------------------------------------------
    # File load UI
    # ------------------------------------------------------------------

    def init_file_load_ui(self):
        """Initializes the UI for loading different types of data files.

        Returns:
            QVBoxLayout: The layout containing the file input controls.
        """
        from PyQt6.QtWidgets import QStackedWidget

        v_box = QVBoxLayout()

        if self.data_type == "fitting":
            selector_layout = self.create_file_type_selector()
            v_box.addLayout(selector_layout)
            v_box.addSpacing(20)
            self.file_type_stack = QStackedWidget()
            self.file_type_stack_indices = {}

        files = self.app.reader_data[self.data_type]["files"]
        for file_type, file_path in files.items():
            # laserblood_metadata is auto-loaded — never shown in UI
            if file_type == "laserblood_metadata":
                continue

            container = QWidget()
            container_layout = QVBoxLayout()
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(10)

            if (file_type == "phasors" and self.data_type == "phasors") or (
                file_type == "fitting" and self.data_type == "fitting"
            ):
                input_desc = QLabel(f"LOAD RELATED {file_type.upper()} FILE:")
            elif file_type == "spectroscopy":
                input_desc = QLabel(f"LOAD A {file_type.upper()} FILE:")
            else:
                input_desc = QLabel(f"LOAD A {file_type.upper().replace('_', ' ')} FILE:")
            if self.data_type in ("phasors", "fitting"):
                input_desc.setText(input_desc.text().replace("FILE", "FILES (MAX 4)"))
            input_desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")

            file_extension = (
                ".json"
                if file_type in ("fitting", "laserblood_metadata")
                else ".bin"
            )

            def on_change(file_type=file_type):
                def callback(text):
                    self.on_loaded_file_change(text, file_type)
                return callback

            if isinstance(file_path, list):
                display_text = (
                    file_path[0]
                    if len(file_path) == 1
                    else (f"{len(file_path)} file(s) loaded" if len(file_path) > 1 else "")
                )
            else:
                display_text = file_path

            _, input_widget = InputTextControl.setup(
                label="",
                placeholder=f"Load {file_extension} file",
                event_callback=on_change(),
                text=display_text,
            )
            input_widget.setStyleSheet(GUIStyles.set_input_text_style())
            widget_key = f"load_{file_type}_input"
            self.widgets[widget_key] = input_widget

            load_file_btn = QPushButton()
            load_file_btn.setIcon(QIcon(resource_path("assets/folder-white.png")))
            load_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            GUIStyles.set_start_btn_style(load_file_btn)
            load_file_btn.setFixedHeight(36)

            if self.data_type == "phasors":
                if file_type in ("spectroscopy", "phasors"):
                    load_file_btn.clicked.connect(
                        partial(self.on_load_file_btn_clicked_phasors, file_type)
                    )
                elif file_type == "laserblood_metadata":
                    load_file_btn.clicked.connect(
                        partial(self.on_load_file_btn_clicked_phasors_metadata, file_type)
                    )
                else:
                    load_file_btn.clicked.connect(
                        partial(self.on_load_file_btn_clicked, file_type)
                    )
            elif self.data_type == "fitting":
                if file_type == "spectroscopy":
                    load_file_btn.clicked.connect(
                        partial(self.on_load_file_btn_clicked_main_branch_logic, file_type)
                    )
                elif file_type == "fitting":
                    load_file_btn.clicked.connect(
                        partial(self.on_load_file_btn_clicked, file_type)
                    )
            else:
                load_file_btn.clicked.connect(
                    partial(self.on_load_file_btn_clicked, file_type)
                )

            control_row = QHBoxLayout()
            control_row.addWidget(input_widget)
            control_row.addWidget(load_file_btn)
            container_layout.addWidget(input_desc)
            container_layout.addSpacing(10)
            container_layout.addLayout(control_row)
            container.setLayout(container_layout)
            self.file_input_containers[file_type] = container

            if self.data_type == "fitting" and hasattr(self, "file_type_stack"):
                index = self.file_type_stack.addWidget(container)
                self.file_type_stack_indices[file_type] = index
            else:
                v_box.addWidget(container)
                v_box.addSpacing(10)

        if self.data_type == "fitting" and hasattr(self, "file_type_stack"):
            v_box.addWidget(self.file_type_stack)
            last_selection = self.app.settings.value(
                "fitting_read_last_file_type", "spectroscopy"
            )
            if last_selection == "fitting" and "fitting" in self.file_type_stack_indices:
                self.file_type_stack.setCurrentIndex(
                    self.file_type_stack_indices["fitting"]
                )
            elif "spectroscopy" in self.file_type_stack_indices:
                self.file_type_stack.setCurrentIndex(
                    self.file_type_stack_indices["spectroscopy"]
                )

        return v_box

    # ------------------------------------------------------------------
    # Channels layout
    # ------------------------------------------------------------------

    def init_channels_layout(self):
        """Initializes the grid of checkboxes for selecting which channels to plot.

        Returns:
            QVBoxLayout or None: The layout for channel selection, or None if unavailable.
        """
        from core.controls_controller import ControlsController

        if self.tab_selected == s.TAB_PHASORS:
            return None
        self.channels_checkboxes.clear()
        file_metadata = self.app.reader_data[self.data_type]["metadata"]
        plots_to_show = self.app.reader_data[self.data_type]["plots"]
        if "channels" in file_metadata and file_metadata["channels"] is not None:
            selected_channels = [
                ch for ch in file_metadata["channels"] if ch is not None
            ]
            selected_channels.sort()
            self.app.selected_channels = selected_channels
            for i, ch in enumerate(self.app.channel_checkboxes):
                ch.set_checked(i in self.app.selected_channels)
            ControlsController.set_selected_channels_to_settings(self.app)
            if len(plots_to_show) == 0:
                plots_to_show = selected_channels[:2]

            # FITTING READ: show only the first channel (average of all channels)
            if self.data_type == "fitting" and self.app.acquire_read_mode == "read":
                plots_to_show = (
                    [selected_channels[0]] if len(selected_channels) > 0 else []
                )
                self.app.plots_to_show = plots_to_show
                self.app.settings.setValue(
                    s.SETTINGS_PLOTS_TO_SHOW, json.dumps(plots_to_show)
                )
                self.app.reader_data[self.data_type]["plots"] = plots_to_show
                return None

            self.app.plots_to_show = plots_to_show
            self.app.settings.setValue(
                s.SETTINGS_PLOTS_TO_SHOW, json.dumps(plots_to_show)
            )

            from utils.channel_name_utils import get_channel_name
            binary_metadata = self.app.reader_data[self.data_type].get("metadata", {})
            channel_names = (
                binary_metadata.get("channels_name", {})
                if isinstance(binary_metadata, dict)
                else {}
            )

            channels_layout = QVBoxLayout()
            desc = QLabel("CHOOSE MAX 4 PLOTS TO DISPLAY:")
            desc.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
            grid = QGridLayout()
            for ch in selected_channels:
                label = get_channel_name(ch, channel_names)
                checkbox, checkbox_wrapper = self.set_checkboxes(label)
                checkbox.setChecked(ch in plots_to_show)
                if len(plots_to_show) >= 4 and ch not in plots_to_show:
                    checkbox.setEnabled(False)
                grid.addWidget(checkbox_wrapper)
            channels_layout.addWidget(desc)
            channels_layout.addSpacing(10)
            channels_layout.addLayout(grid)
            self.layouts["ch_layout"] = channels_layout
            return channels_layout
        return None

    def remove_channels_grid(self):
        """Removes the channel selection grid from the layout."""
        if "ch_layout" in self.layouts:
            clear_layout(self.layouts["ch_layout"])
            del self.layouts["ch_layout"]

    # ------------------------------------------------------------------
    # Plot button
    # ------------------------------------------------------------------

    def create_plot_btn_layout(self):
        """Creates the layout containing the 'Plot Data' or 'Fit Data' button.

        Returns:
            QHBoxLayout: The layout with the main action button.
        """
        fitting_data = self.app.reader_data["fitting"]["data"]["fitting_data"]
        spectroscopy_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"]
        has_fitting = (isinstance(fitting_data, list) and len(fitting_data) > 0) or (
            isinstance(fitting_data, dict) and bool(fitting_data)
        )
        has_spectroscopy = bool(spectroscopy_data)

        plot_btn = QPushButton("FIT DATA" if has_fitting and not has_spectroscopy else "PLOT DATA")
        plot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plot_btn.setObjectName("btn")
        GUIStyles.set_stop_btn_style(plot_btn)
        plot_btn.setFixedHeight(40)
        plot_btn.setFixedWidth(200)

        plots_to_show = self.app.reader_data[self.data_type]["plots"]
        if self.data_type == "phasors":
            phasors_file = self.app.reader_data["phasors"]["files"]["phasors"]
            spectroscopy_file = self.app.reader_data["phasors"]["files"]["spectroscopy"]
            phasors_loaded = (
                isinstance(phasors_file, list)
                and len(phasors_file) > 0
                and any(f.strip() for f in phasors_file if isinstance(f, str))
            ) or (isinstance(phasors_file, str) and len(phasors_file.strip()) > 0)
            spectroscopy_loaded = (
                isinstance(spectroscopy_file, list)
                and len(spectroscopy_file) > 0
                and any(f.strip() for f in spectroscopy_file if isinstance(f, str))
            ) or (
                isinstance(spectroscopy_file, str) and len(spectroscopy_file.strip()) > 0
            )
            should_enable = phasors_loaded and spectroscopy_loaded
        else:
            should_enable = len(plots_to_show) > 0

        plot_btn.setEnabled(should_enable)
        plot_btn.clicked.connect(self.on_plot_data_btn_clicked)
        self.widgets["plot_btn"] = plot_btn

        row_btn = QHBoxLayout()
        row_btn.addStretch(1)
        row_btn.addWidget(plot_btn)
        return row_btn

    # ------------------------------------------------------------------
    # Checkbox helpers
    # ------------------------------------------------------------------

    def set_checkboxes(self, text):
        """Creates a styled checkbox widget for channel selection.

        Args:
            text (str): The label for the checkbox.

        Returns:
            tuple: (QCheckBox, wrapper QWidget).
        """
        checkbox_wrapper = QWidget()
        checkbox_wrapper.setObjectName("simple_checkbox_wrapper")
        row = QHBoxLayout()
        checkbox = QCheckBox(text)
        checkbox.setStyleSheet(
            GUIStyles.set_simple_checkbox_style(color=s.PALETTE_BLUE_1)
        )
        checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        checkbox.toggled.connect(
            lambda state, cb=checkbox: self.on_channel_toggled(state, cb)
        )
        row.addWidget(checkbox)
        checkbox_wrapper.setLayout(row)
        checkbox_wrapper.setStyleSheet(GUIStyles.checkbox_wrapper_style())
        return checkbox, checkbox_wrapper

    def on_channel_toggled(self, state, checkbox):
        """Handles the toggling of a channel selection checkbox.

        Args:
            state (bool): The new checked state.
            checkbox (QCheckBox): The checkbox that was toggled.
        """
        from core.plots_controller import PlotsController
        from core.controls_controller import ControlsController
        from components.reader.read_data_controls import ReadDataControls

        label_text = checkbox.text()
        ch_index = extract_channel_from_label(label_text)
        if state:
            if ch_index not in self.app.plots_to_show:
                self.app.plots_to_show.append(ch_index)
        else:
            if ch_index in self.app.plots_to_show:
                self.app.plots_to_show.remove(ch_index)
        self.app.plots_to_show.sort()
        self.app.settings.setValue(
            s.SETTINGS_PLOTS_TO_SHOW, json.dumps(self.app.plots_to_show)
        )
        self.app.reader_data[self.data_type]["plots"] = self.app.plots_to_show
        if len(self.app.plots_to_show) >= 4:
            for cb in self.channels_checkboxes:
                if cb.text() != label_text and not cb.isChecked():
                    cb.setEnabled(False)
        else:
            for cb in self.channels_checkboxes:
                cb.setEnabled(True)
        if "plot_btn" in self.widgets:
            self.widgets["plot_btn"].setEnabled(len(self.app.plots_to_show) > 0)
        PlotsController.clear_plots(self.app)
        PlotsController.generate_plots(self.app)
        ControlsController.toggle_intensities_widgets_visibility(self.app)
        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)

    # ------------------------------------------------------------------
    # File input change
    # ------------------------------------------------------------------

    def on_loaded_file_change(self, text, file_type):
        """Handles changes to the file path input field.

        Args:
            text (str): The new file path.
            file_type (str): The type of file associated with the input.
        """
        from core.plots_controller import PlotsController
        from core.controls_controller import ControlsController
        from components.reader.read_data_controls import ReadDataControls

        if "file(s) loaded" in text:
            return
        if (
            text != self.app.reader_data[self.data_type]["files"][file_type]
            and file_type != "laserblood_metadata"
        ):
            PlotsController.clear_plots(self.app)
            PlotsController.generate_plots(self.app)
            ControlsController.toggle_intensities_widgets_visibility(self.app)
        self.app.reader_data[self.data_type]["files"][file_type] = text
        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)

    # ------------------------------------------------------------------
    # Load button handlers
    # ------------------------------------------------------------------

    def on_load_file_btn_clicked(self, file_type):
        """Handles the click event for the generic 'load file' button.

        Args:
            file_type (str): The type of file to load.
        """
        from core.controls_controller import ControlsController
        from components.reader.read_data_controls import ReadDataControls
        from components.reader.read_data_io import (
            read_laserblood_metadata,
            read_fitting_data,
            read_bin_data,
        )

        if self.data_type == "fitting":
            if file_type == "spectroscopy":
                self.app.reader_data["fitting"]["files"]["fitting"] = ""
                self.app.reader_data["fitting"]["data"]["fitting_data"] = []
            elif file_type == "fitting":
                self.app.reader_data["fitting"]["files"]["spectroscopy"] = ""
                self.app.reader_data["fitting"]["data"]["spectroscopy_data"] = {}

        if file_type == "laserblood_metadata":
            read_laserblood_metadata(self, self.app, self.tab_selected)
        elif file_type == "fitting":
            read_fitting_data(self, self.app)
            if (
                hasattr(self.app, "control_inputs")
                and "bin_metadata_button" in self.app.control_inputs
            ):
                self.app.control_inputs["bin_metadata_button"].setVisible(False)
        else:
            read_bin_data(self, self.app, self.tab_selected, file_type)

        file_path = self.app.reader_data[self.data_type]["files"][file_type]
        file_name = (
            file_path[0]
            if isinstance(file_path, list) and len(file_path) > 0
            else file_path if isinstance(file_path, str) else ""
        )
        has_files = (isinstance(file_path, list) and len(file_path) > 0) or (
            isinstance(file_path, str) and len(file_path) > 0
        )

        if has_files:
            bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self.app)
            if file_type == "fitting":
                self.app.control_inputs["bin_metadata_button"].setVisible(False)
            else:
                self.app.control_inputs["bin_metadata_button"].setVisible(
                    bin_metadata_btn_visible
                )
            self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
                bin_metadata_btn_visible and self.tab_selected != s.TAB_FITTING
            )
            widget_key = f"load_{file_type}_input"
            display_name = (
                f"{len(file_path)} file(s) loaded"
                if isinstance(file_path, list) and len(file_path) > 1
                else file_name
            )
            self.widgets[widget_key].setText(display_name)
            if file_type != "laserblood_metadata":
                self.remove_channels_grid()
                channels_layout = self.init_channels_layout()
                if channels_layout is not None:
                    self.layout.insertLayout(2, channels_layout)
                if "plot_btn" in self.widgets:
                    plots_to_show = self.app.reader_data[self.data_type]["plots"]
                    if self.data_type == "phasors":
                        phasors_file = self.app.reader_data["phasors"]["files"]["phasors"]
                        spectroscopy_file = self.app.reader_data["phasors"]["files"]["spectroscopy"]
                        phasors_loaded = (
                            isinstance(phasors_file, list) and len(phasors_file) > 0
                        ) or (isinstance(phasors_file, str) and len(phasors_file.strip()) > 0)
                        spectroscopy_loaded = (
                            isinstance(spectroscopy_file, list) and len(spectroscopy_file) > 0
                        ) or (
                            isinstance(spectroscopy_file, str)
                            and len(spectroscopy_file.strip()) > 0
                        )
                        should_enable = phasors_loaded and spectroscopy_loaded
                    else:
                        should_enable = len(plots_to_show) > 0
                    self.widgets["plot_btn"].setEnabled(should_enable)

        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)

        if "plot_btn" in self.widgets:
            fitting_data = self.app.reader_data["fitting"]["data"]["fitting_data"]
            spectroscopy_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"]
            has_fitting = (
                isinstance(fitting_data, list) and len(fitting_data) > 0
            ) or (isinstance(fitting_data, dict) and bool(fitting_data))
            has_spectroscopy = bool(spectroscopy_data)
            self.widgets["plot_btn"].setText(
                "FIT DATA" if has_fitting and not has_spectroscopy else "PLOT DATA"
            )

    def on_load_file_btn_clicked_main_branch_logic(self, file_type):
        """Handle file load button click using multi-file logic (fitting tab, spectroscopy files)."""
        from core.controls_controller import ControlsController
        from components.reader.read_data_controls import ReadDataControls

        self.app.reader_data["fitting"]["files"]["fitting"] = ""
        self.app.reader_data["fitting"]["data"]["fitting_data"] = []
        self.on_load_file_btn_clicked_fitting_spectroscopy(file_type)

        if ReadDataControls.fit_button_enabled(self.app):
            ControlsController.fit_button_show(self.app)
        else:
            ControlsController.fit_button_hide(self.app)

        if "plot_btn" in self.widgets:
            spectroscopy_files = self.app.reader_data["fitting"]["files"]["spectroscopy"]
            if isinstance(spectroscopy_files, list):
                has_spectroscopy = len(spectroscopy_files) > 0
            else:
                has_spectroscopy = bool(
                    spectroscopy_files and len(spectroscopy_files.strip()) > 0
                )
            self.widgets["plot_btn"].setEnabled(has_spectroscopy)
            if has_spectroscopy:
                self.widgets["plot_btn"].setText("PLOT DATA")
                ControlsController.fit_button_show(self.app)

    def on_load_file_btn_clicked_fitting_spectroscopy(self, file_type):
        """Handle multi-file spectroscopy load for the FITTING tab (up to 4 files).

        Args:
            file_type (str): Type of file to load (should be 'spectroscopy').
        """
        from core.controls_controller import ControlsController
        from components.reader.read_data_controls import ReadDataControls
        from components.reader.read_data_io import (
            read_multiple_bin_data,
            read_spectroscopy_data,
            show_warning_message,
        )

        valid_files = read_multiple_bin_data(
            self, self.app, self.tab_selected, file_type
        )
        if not valid_files:
            return

        # Reset all fitting and spectroscopy state
        self.app.reader_data["fitting"]["files"]["fitting"] = ""
        self.app.reader_data["fitting"]["data"]["fitting_data"] = []
        self.app.reader_data["fitting"]["files"]["spectroscopy"] = []
        self.app.reader_data["fitting"]["spectroscopy_metadata"] = []
        self.app.reader_data["fitting"]["laserblood_metadata"] = []
        self.app.reader_data["fitting"]["data"]["spectroscopy_data"] = {"files_data": []}

        for channel in list(self.app.decay_widgets.keys()):
            if channel in self.app.decay_widgets:
                self.app.decay_widgets[channel].clear()
        if s.TAB_FITTING in self.app.cached_decay_values:
            self.app.cached_decay_values[s.TAB_FITTING] = {}

        self.app.reader_data["fitting"]["files"]["spectroscopy"] = valid_files
        magic_bytes = b"SP01"

        for file_path in valid_files:
            try:
                with open(file_path, "rb") as f:
                    if f.read(4) == magic_bytes:
                        result = read_spectroscopy_data(
                            f, file_path, file_type, self.tab_selected, self.app
                        )
                        if result:
                            file_name, _, times, channels_curves, metadata = result
                            metadata["file_name"] = os.path.basename(file_path)
                            self.app.reader_data["fitting"]["spectroscopy_metadata"].append(
                                metadata
                            )

                            # Auto-load laserblood_metadata if exists
                            file_dir = os.path.dirname(file_path)
                            timestamp = "_".join(
                                os.path.basename(file_path).replace(".bin", "").split("_")[:2]
                            )
                            pattern = os.path.join(
                                file_dir, f"{timestamp}_*_laserblood_metadata.json"
                            )
                            meta_files = glob.glob(pattern)
                            if meta_files:
                                try:
                                    with open(meta_files[0], "r") as mf:
                                        auto_meta = json.load(mf)
                                        lb_list = self.app.reader_data["fitting"].get(
                                            "laserblood_metadata", []
                                        )
                                        if not isinstance(lb_list, list):
                                            lb_list = []
                                        lb_list.append(auto_meta)
                                        self.app.reader_data["fitting"][
                                            "laserblood_metadata"
                                        ] = lb_list
                                        # Update channel names from binary metadata
                                        ch_names = (
                                            metadata.get("channels_name", {})
                                            if isinstance(metadata, dict)
                                            else {}
                                        )
                                        if ch_names:
                                            self.app.channel_names.update(ch_names)
                                except Exception:
                                    pass

                            spect_data = self.app.reader_data["fitting"]["data"][
                                "spectroscopy_data"
                            ]
                            if "files_data" not in spect_data:
                                spect_data["files_data"] = []
                            spect_data["files_data"].append(
                                {
                                    "file_path": file_path,
                                    "times": times,
                                    "channels_curves": channels_curves,
                                }
                            )
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
                continue

        # Build unified time array for plotting compatibility
        files_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"].get(
            "files_data", []
        )
        if len(files_data) > 0:
            first_metadata = self.app.reader_data["fitting"]["spectroscopy_metadata"][0]
            laser_period_ns = first_metadata.get("laser_period_ns", 25)
            unified_times = np.linspace(0, laser_period_ns, 256)

            all_channels_data = {}
            for file_entry in files_data:
                file_times = file_entry["times"]
                for channel_idx, curves_list in file_entry["channels_curves"].items():
                    if channel_idx not in all_channels_data:
                        all_channels_data[channel_idx] = []
                    for curve in curves_list:
                        if len(file_times) == len(curve):
                            interp_curve = np.interp(
                                unified_times, np.array(file_times) * 1000, curve
                            )
                            all_channels_data[channel_idx].append(interp_curve)
                        else:
                            all_channels_data[channel_idx].append(curve)

            self.app.reader_data["fitting"]["data"]["spectroscopy_data"][
                "times"
            ] = unified_times.tolist()
            self.app.reader_data["fitting"]["metadata"] = first_metadata

        # Update UI
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self.app)
        self.app.control_inputs["bin_metadata_button"].setVisible(
            bin_metadata_btn_visible
        )
        self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(False)

        widget_key = f"load_{file_type}_input"
        self.widgets[widget_key].setText(f"{len(valid_files)} file(s) loaded")
        self.app.settings.setValue("fitting_read_last_spectroscopy_files", valid_files)

        self.remove_channels_grid()
        channels_layout = self.init_channels_layout()
        if channels_layout is not None:
            self.layout.insertLayout(2, channels_layout)

        if "plot_btn" in self.widgets:
            spectroscopy_files = self.app.reader_data["fitting"]["files"]["spectroscopy"]
            has_spectroscopy = isinstance(spectroscopy_files, list) and len(
                spectroscopy_files
            ) > 0
            self.widgets["plot_btn"].setEnabled(has_spectroscopy)
            if has_spectroscopy:
                self.widgets["plot_btn"].setText("PLOT DATA")
                ControlsController.fit_button_show(self.app)

    def auto_start_fitting_for_loaded_files(self):
        """Automatically start fitting calculations for loaded spectroscopy files."""
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(500, self._delayed_fitting_start)

    def _delayed_fitting_start(self):
        """Start fitting calculations with a slight delay to allow UI updates."""
        from core.controls_controller import ControlsController
        import traceback

        try:
            ControlsController.on_fit_btn_click(self.app)
        except Exception:
            traceback.print_exc()

    def on_load_file_btn_clicked_phasors_metadata(
        self, file_type="laserblood_metadata"
    ):
        """Handle metadata file load button click for phasors mode (multi-selection).

        Args:
            file_type (str): Type of metadata file to load.
        """
        from components.reader.read_data_controls import ReadDataControls
        from components.reader.read_data_io import read_multiple_json_data

        valid_results = read_multiple_json_data(
            self, self.app, self.tab_selected, file_type
        )
        if not valid_results:
            return

        self.app.reader_data[self.data_type]["files"][file_type] = [
            r[0] for r in valid_results
        ]
        self.app.reader_data[self.data_type][file_type] = [
            r[1] for r in valid_results
        ]

        widget_key = f"load_{file_type}_input"
        self.widgets[widget_key].setText(
            valid_results[0][0] if len(valid_results) == 1
            else f"{len(valid_results)} file(s) loaded"
        )

        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self.app)
        self.app.control_inputs["bin_metadata_button"].setVisible(
            bin_metadata_btn_visible
        )
        self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
            bin_metadata_btn_visible and self.tab_selected != s.TAB_FITTING
        )

    def on_load_file_btn_clicked_phasors(self, file_type):
        """Handle multi-file load for spectroscopy or phasors files in PHASORS mode.

        Args:
            file_type (str): Type of file to load ('spectroscopy' or 'phasors').
        """
        from components.reader.read_data_controls import ReadDataControls
        from components.reader.read_data_io import (
            read_multiple_bin_data,
            read_spectroscopy_data,
            read_phasors_data,
            show_warning_message,
        )

        valid_files = read_multiple_bin_data(
            self, self.app, self.tab_selected, file_type
        )
        if not valid_files:
            return

        # Reset state for this file type
        self.app.reader_data[self.data_type]["files"][file_type] = []
        if file_type == "phasors":
            self.app.reader_data[self.data_type]["phasors_metadata"] = []
            self.app.reader_data[self.data_type]["data"]["phasors_data"] = {}
        elif file_type == "spectroscopy":
            self.app.reader_data[self.data_type]["spectroscopy_metadata"] = []
            self.app.reader_data[self.data_type]["laserblood_metadata"] = []
            self.app.reader_data[self.data_type]["data"]["spectroscopy_data"] = {
                "files_data": []
            }

        self.app.reader_data[self.data_type]["files"][file_type] = valid_files

        magic_bytes = b"SP01" if file_type == "spectroscopy" else b"SPF1"
        read_function = (
            read_spectroscopy_data if file_type == "spectroscopy" else read_phasors_data
        )

        for file_path in valid_files:
            try:
                with open(file_path, "rb") as f:
                    if f.read(4) == magic_bytes:
                        result = read_function(
                            f, file_path, file_type, self.tab_selected, self.app
                        )
                        if result:
                            file_name, _, *data, metadata = result

                            if file_type == "spectroscopy":
                                self.app.reader_data[self.data_type][
                                    "spectroscopy_metadata"
                                ].append(metadata)

                                # Auto-load laserblood_metadata if exists
                                file_dir = os.path.dirname(file_path)
                                timestamp = "_".join(
                                    os.path.basename(file_path)
                                    .replace(".bin", "")
                                    .split("_")[:2]
                                )
                                pattern = os.path.join(
                                    file_dir,
                                    f"{timestamp}_*_laserblood_metadata.json",
                                )
                                meta_files = glob.glob(pattern)
                                if meta_files:
                                    try:
                                        with open(meta_files[0], "r") as mf:
                                            auto_meta = json.load(mf)
                                            lb_key = "laserblood_metadata"
                                            lb_list = self.app.reader_data[
                                                self.data_type
                                            ].get(lb_key, [])
                                            if not isinstance(lb_list, list):
                                                lb_list = []
                                            lb_list.append(auto_meta)
                                            self.app.reader_data[self.data_type][
                                                lb_key
                                            ] = lb_list
                                            ch_names = (
                                                metadata.get("channels_name", {})
                                                if isinstance(metadata, dict)
                                                else {}
                                            )
                                            if ch_names:
                                                self.app.channel_names.update(ch_names)
                                    except Exception:
                                        pass

                                times, channels_curves = data
                                spect_data = self.app.reader_data[self.data_type][
                                    "data"
                                ]["spectroscopy_data"]
                                if "files_data" not in spect_data:
                                    spect_data["files_data"] = []
                                spect_data["files_data"].append(
                                    {
                                        "file_path": file_path,
                                        "times": times,
                                        "channels_curves": channels_curves,
                                    }
                                )

                            elif file_type == "phasors":
                                self.app.reader_data[self.data_type][
                                    "phasors_metadata"
                                ].append(metadata)
                                phasors_data = data[0]
                                for ch, harmonics in phasors_data.items():
                                    ch_store = self.app.reader_data[self.data_type][
                                        "data"
                                    ]["phasors_data"]
                                    if ch not in ch_store:
                                        ch_store[ch] = {}
                                    for h, points in harmonics.items():
                                        if h not in ch_store[ch]:
                                            ch_store[ch][h] = []
                                            ch_store[ch][h].extend(
                                                [(p[0], p[1], file_path) for p in points]
                                            )
            except Exception as e:
                show_warning_message(
                    "Error reading file", f"Error reading {file_path}: {str(e)}"
                )

        # Update UI
        bin_metadata_btn_visible = ReadDataControls.read_bin_metadata_enabled(self.app)
        self.app.control_inputs["bin_metadata_button"].setVisible(
            bin_metadata_btn_visible
        )
        self.app.control_inputs[s.EXPORT_PLOT_IMG_BUTTON].setVisible(
            bin_metadata_btn_visible and self.tab_selected != s.TAB_FITTING
        )
        widget_key = f"load_{file_type}_input"
        self.widgets[widget_key].setText(f"{len(valid_files)} file(s) loaded")

        if "plot_btn" in self.widgets:
            phasors_files = self.app.reader_data["phasors"]["files"]["phasors"]
            spectroscopy_files = self.app.reader_data["phasors"]["files"]["spectroscopy"]
            both_files_present = len(phasors_files) > 0 and len(spectroscopy_files) > 0
            self.widgets["plot_btn"].setEnabled(both_files_present)

    # ------------------------------------------------------------------
    # Validation and plot button click
    # ------------------------------------------------------------------

    def errors_in_data(self, file_type):
        """Checks for data consistency errors (e.g. channel mismatches between files).

        Args:
            file_type (str): The data type to check.

        Returns:
            bool: True if an error is found, False otherwise.
        """
        from components.reader.read_data_utils import (
            get_fitting_active_channels,
            are_spectroscopy_and_fitting_from_same_acquisition,
            has_laser_period_mismatch,
        )

        if file_type == "fitting":
            file_fitting = self.app.reader_data["fitting"]["files"]["fitting"]
            file_spectroscopy = self.app.reader_data["fitting"]["files"]["spectroscopy"]
            has_fitting = (
                isinstance(file_fitting, list) and len(file_fitting) > 0
            ) or (isinstance(file_fitting, str) and len(file_fitting.strip()) > 0)
            has_spectroscopy = (
                isinstance(file_spectroscopy, list) and len(file_spectroscopy) > 0
            ) or (
                isinstance(file_spectroscopy, str)
                and len(file_spectroscopy.strip()) > 0
            )
            if not has_fitting or not has_spectroscopy:
                return False
            get_fitting_active_channels(self.app)
            return not are_spectroscopy_and_fitting_from_same_acquisition(self.app)
        elif file_type == "phasors":
            return has_laser_period_mismatch(self.app.reader_data["phasors"])
        return False

    def on_plot_data_btn_clicked(self):
        """Handles the click event for the main 'Plot Data' or 'Fit Data' button."""
        from core.controls_controller import ControlsController
        from core.plots_controller import PlotsController
        from components.reader.read_data_controls import ReadDataControls
        from components.reader.read_data_utils import get_frequency_mhz
        from components.reader.read_data_plot import plot_data

        file_type = self.data_type
        if self.errors_in_data(file_type):
            return

        fitting_data = self.app.reader_data["fitting"]["data"]["fitting_data"]
        spectroscopy_data = self.app.reader_data["fitting"]["data"]["spectroscopy_data"]
        has_fitting = (isinstance(fitting_data, list) and len(fitting_data) > 0) or (
            isinstance(fitting_data, dict) and bool(fitting_data)
        )
        has_spectroscopy = bool(spectroscopy_data)

        if has_fitting and not has_spectroscopy:
            ControlsController.on_fit_btn_click(self.app)
        else:
            freq = get_frequency_mhz(self.app)
            if freq > 0:
                PlotsController.clear_plots(self.app)
                PlotsController.generate_plots(self.app, freq)
                ControlsController.toggle_intensities_widgets_visibility(self.app)
            plot_data(self.app)
            if ReadDataControls.fit_button_enabled(self.app):
                ControlsController.fit_button_show(self.app)
            else:
                ControlsController.fit_button_hide(self.app)
        self.close()

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        """Handle window close event to restore file type selection if needed."""
        self.check_and_restore_file_type_selection()
        super().closeEvent(event)

    def center_window(self):
        """Centers the popup window on the primary screen."""
        self.setMinimumWidth(500)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())