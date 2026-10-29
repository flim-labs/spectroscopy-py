"""
reader_metadata_popup.py
========================
ReaderMetadataPopup — QWidget popup that displays metadata from loaded data files.
"""

import os

from utils.gui_styles import GUIStyles
import settings.settings as s
from utils.logo_utilities import TitlebarIcon

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QApplication,
    QScrollArea,
    QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class ReaderMetadataPopup(QWidget):
    """A popup window to display the metadata from a loaded data file."""

    def __init__(self, window, tab_selected):
        """Initializes the ReaderMetadataPopup.

        Args:
            window: The main application window instance.
            tab_selected (str): The identifier of the tab that opened the popup.
        """
        from components.reader.read_data_utils import get_data_type

        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)
        self.app = window
        self.tab_selected = tab_selected
        self.data_type = get_data_type(self.tab_selected)
        self.setWindowTitle(f"{self.data_type.capitalize()} file metadata")
        TitlebarIcon.setup(self)
        GUIStyles.customize_theme(self, bg=QColor(20, 20, 20))
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        metadata_table = self.create_metadata_table()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_widget.setLayout(metadata_table)
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        main_layout.addSpacing(10)
        self.setLayout(main_layout)
        self.setStyleSheet(GUIStyles.plots_config_popup_style())
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        self.app.widgets[s.READER_METADATA_POPUP] = self
        self.center_window()
        self.setUpdatesEnabled(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)

    # ------------------------------------------------------------------
    # Metadata key mapping
    # ------------------------------------------------------------------

    def get_metadata_keys_dict(self):
        """Returns a dict mapping metadata keys to human-readable labels."""
        return {
            "channels": "Enabled Channels",
            "bin_width_micros": "Bin width (μs)",
            "acquisition_time_millis": "Acquisition time (s)",
            "laser_period_ns": "Laser period (ns)",
            "harmonics": "Harmonics",
            "tau_ns": "Tau (ns)",
        }

    def parse_laserblood_metadata(self, laserblood_metadata):
        """Parses the LaserBlood-specific metadata list into a dictionary.

        Args:
            laserblood_metadata (list): The list of metadata items.

        Returns:
            dict: The parsed metadata as key-value pairs.
        """
        data = {}
        for item in laserblood_metadata:
            key = (
                item["label"] + " (" + item["unit"] + ")"
                if item["unit"]
                else item["label"]
            )
            data[key] = item["value"]
        return data

    # ------------------------------------------------------------------
    # Row builders
    # ------------------------------------------------------------------

    def create_label_row(self, key, value, key_bg_color, value_bg_color):
        """Creates a styled horizontal layout for a key-value pair.

        Args:
            key (str): The key label.
            value (str): The value.
            key_bg_color (str): Background colour for the key cell.
            value_bg_color (str): Background colour for the value cell.

        Returns:
            QHBoxLayout: The layout containing the styled labels.
        """
        h_box = QHBoxLayout()
        h_box.setContentsMargins(0, 0, 0, 0)
        h_box.setSpacing(0)
        key_label = QLabel(key)
        key_label.setStyleSheet(
            f"width: 200px; font-size: 14px; border: 1px solid {key_bg_color}; "
            f"padding: 8px; color: white; background-color: {key_bg_color}"
        )
        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"width: 500px; font-size: 14px; border: 1px solid {value_bg_color}; "
            f"padding: 8px; color: white"
        )
        h_box.addWidget(key_label)
        h_box.addWidget(value_label)
        return h_box

    def create_compact_label_row(self, key, value, key_bg_color, value_bg_color):
        """Creates a compact label row for grid layout.

        Args:
            key (str): The key label.
            value (str): The value.
            key_bg_color (str): Background colour for the key cell.
            value_bg_color (str): Background colour for the value cell.

        Returns:
            QHBoxLayout: The layout containing the compact styled labels.
        """
        h_box = QHBoxLayout()
        h_box.setContentsMargins(0, 0, 0, 0)
        h_box.setSpacing(0)
        key_label = QLabel(key)
        key_label.setStyleSheet(
            f"min-width: 210px; font-size: 12px; border: 1px solid {key_bg_color}; "
            f"padding: 6px; color: white; background-color: {key_bg_color}"
        )
        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"min-width: 500px; font-size: 12px; border: 1px solid {value_bg_color}; "
            f"padding: 6px; color: white"
        )
        h_box.addWidget(key_label, 0)
        h_box.addWidget(value_label, 1)
        return h_box

    # ------------------------------------------------------------------
    # Table builder (dispatches by data_type)
    # ------------------------------------------------------------------

    def create_metadata_table(self):
        """Creates the main layout displaying all metadata in a table-like format.

        Returns:
            QVBoxLayout: The layout containing all metadata rows.
        """
        from core.phasors_controller import PhasorsController
        from utils.channel_name_utils import format_channel_list

        metadata_keys = self.get_metadata_keys_dict()
        v_box = QVBoxLayout()
        v_box.setAlignment(Qt.AlignmentFlag.AlignTop)

        if self.data_type == "phasors":
            self._build_phasors_metadata(v_box, metadata_keys, PhasorsController, format_channel_list)
        elif self.data_type == "fitting":
            self._build_fitting_metadata(v_box, metadata_keys, PhasorsController, format_channel_list)
        else:
            # Spectroscopy tab — single-file display
            self._create_single_file_metadata_display(v_box, metadata_keys)

        return v_box

    # ------------------------------------------------------------------
    # Per-tab metadata builders
    # ------------------------------------------------------------------

    def _build_phasors_metadata(self, v_box, metadata_keys, PhasorsController, format_channel_list):
        """Builds the metadata grid for the Phasors tab."""
        spectroscopy_metadata = self.app.reader_data[self.data_type].get(
            "spectroscopy_metadata", []
        )
        spectroscopy_files = self.app.reader_data[self.data_type]["files"]["spectroscopy"]
        phasors_metadata = self.app.reader_data[self.data_type].get("phasors_metadata", [])
        phasors_files = self.app.reader_data[self.data_type]["files"]["phasors"]
        laserblood_metadata = self.app.reader_data[self.data_type].get("laserblood_metadata", [])
        laserblood_files = self.app.reader_data[self.data_type]["files"].get("laserblood_metadata", [])

        if isinstance(spectroscopy_files, str):
            spectroscopy_files = [spectroscopy_files] if spectroscopy_files.strip() else []
        if isinstance(phasors_files, str):
            phasors_files = [phasors_files] if phasors_files.strip() else []
        if isinstance(laserblood_files, str):
            laserblood_files = [laserblood_files] if laserblood_files.strip() else []

        if len(spectroscopy_files) > 0 or (
            isinstance(laserblood_metadata, list) and len(laserblood_metadata) > 0
        ):
            title = QLabel("PHASORS FILE METADATA")
            title.setStyleSheet(
                "font-size: 16px; font-family: 'Montserrat'; margin-bottom: 10px;"
            )
            v_box.addWidget(title)
            v_box.addSpacing(10)

            grid_layout = QGridLayout()
            grid_layout.setSpacing(12)
            grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            max_files = max(
                len(spectroscopy_metadata),
                len(laserblood_metadata) if isinstance(laserblood_metadata, list) else 0,
            )

            for file_idx in range(max_files):
                row = file_idx // 2
                col = file_idx % 2
                color = PhasorsController.get_color_for_file_index(file_idx)

                if file_idx < len(spectroscopy_files) and spectroscopy_files[file_idx]:
                    file_path = spectroscopy_files[file_idx]
                    file_name = (
                        os.path.basename(file_path)
                        if isinstance(file_path, str)
                        else str(file_path)
                    )
                elif file_idx < len(laserblood_files) and laserblood_files[file_idx]:
                    file_path = laserblood_files[file_idx]
                    file_name = (
                        os.path.basename(file_path)
                        if isinstance(file_path, str)
                        else str(file_path)
                    )
                else:
                    file_name = f"Metadata {file_idx + 1}"

                content_widget = QWidget()
                file_layout = QVBoxLayout()
                file_layout.setSpacing(0)
                file_layout.setContentsMargins(0, 0, 0, 0)

                file_info_row = self.create_compact_label_row("File", file_name, color, color)
                file_layout.addLayout(file_info_row)

                channel_names = {}
                if file_idx < len(spectroscopy_metadata):
                    meta = spectroscopy_metadata[file_idx]
                    channel_names = (
                        meta.get("channels_name", {}) if isinstance(meta, dict) else {}
                    )
                    for key, label in metadata_keys.items():
                        if key in meta:
                            val = str(meta[key])
                            if key == "channels":
                                val = format_channel_list(meta[key], channel_names)
                            if key == "acquisition_time_millis":
                                val = str(meta[key] / 1000)
                            file_layout.addLayout(
                                self.create_compact_label_row(label, val, "#11468F", "#11468F")
                            )

                content_widget.setLayout(file_layout)
                scroll_area = self._make_scroll_area(content_widget)
                grid_layout.addWidget(scroll_area, row, col, Qt.AlignmentFlag.AlignTop)

            v_box.addLayout(grid_layout)

    def _build_fitting_metadata(self, v_box, metadata_keys, PhasorsController, format_channel_list):
        """Builds the metadata grid for the Fitting tab."""
        spectroscopy_metadata = self.app.reader_data["fitting"].get("spectroscopy_metadata", [])
        spectroscopy_files = self.app.reader_data["fitting"]["files"]["spectroscopy"]

        if isinstance(spectroscopy_files, str):
            spectroscopy_files = [spectroscopy_files] if spectroscopy_files.strip() else []

        if len(spectroscopy_files) > 0 and len(spectroscopy_metadata) > 0:
            title = QLabel("SPECTROSCOPY FILES METADATA")
            title.setStyleSheet(
                "font-size: 16px; font-family: 'Montserrat'; margin-bottom: 10px;"
            )
            v_box.addWidget(title)
            v_box.addSpacing(10)

            grid_layout = QGridLayout()
            grid_layout.setSpacing(12)
            grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            for file_idx in range(len(spectroscopy_metadata)):
                row = file_idx // 2
                col = file_idx % 2
                color = PhasorsController.get_color_for_file_index(file_idx)
                file_path = (
                    spectroscopy_files[file_idx]
                    if file_idx < len(spectroscopy_files)
                    else f"File {file_idx + 1}"
                )
                file_name = (
                    os.path.basename(file_path)
                    if isinstance(file_path, str)
                    else str(file_path)
                )

                content_widget = QWidget()
                file_layout = QVBoxLayout()
                file_layout.setSpacing(0)
                file_layout.setContentsMargins(0, 0, 0, 0)

                file_info_row = self.create_compact_label_row("File", file_name, color, color)
                file_layout.addLayout(file_info_row)

                meta = spectroscopy_metadata[file_idx]
                channel_names = (
                    meta.get("channels_name", {}) if isinstance(meta, dict) else {}
                )
                for key, label in metadata_keys.items():
                    if key in meta:
                        val = str(meta[key])
                        if key == "channels":
                            val = format_channel_list(meta[key], channel_names)
                        if key == "acquisition_time_millis":
                            val = str(meta[key] / 1000)
                        file_layout.addLayout(
                            self.create_compact_label_row(label, val, "#11468F", "#11468F")
                        )

                content_widget.setLayout(file_layout)
                scroll_area = self._make_scroll_area(content_widget)
                grid_layout.addWidget(scroll_area, row, col, Qt.AlignmentFlag.AlignTop)

            v_box.addLayout(grid_layout)
        else:
            self._create_single_file_metadata_display(v_box, metadata_keys)

    def _make_scroll_area(self, content_widget):
        """Creates a standardized scroll area for a metadata content widget."""
        scroll_area = QScrollArea()
        scroll_area.setWidget(content_widget)
        scroll_area.setWidgetResizable(False)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setMinimumWidth(750)
        scroll_area.setMaximumHeight(550)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        return scroll_area

    def _create_single_file_metadata_display(self, v_box, metadata_keys):
        """Creates a single-file metadata display (used as fallback and for spectroscopy tab)."""
        from utils.channel_name_utils import format_channel_list

        metadata = self.app.reader_data[self.data_type]["metadata"]
        file = (
            self.app.reader_data[self.data_type]["files"][self.data_type]
            if self.data_type != "fitting"
            else self.app.reader_data[self.data_type]["files"]["spectroscopy"]
        )

        title = QLabel(f"{self.data_type.upper()} FILE METADATA")
        title.setStyleSheet("font-size: 16px; font-family: 'Montserrat'")
        v_box.addWidget(title)
        v_box.addSpacing(10)

        if isinstance(file, list):
            file_display = "\n".join(file) if file else "No files"
        else:
            file_display = str(file) if file else "No file"

        file_info_row = self.create_compact_label_row(
            "File", file_display, "#DA1212", "#DA1212"
        )
        v_box.addLayout(file_info_row)

        # Extract channel_names from binary metadata
        channel_names_dict = (
            metadata.get("channels_name", {}) if isinstance(metadata, dict) else {}
        )

        if metadata:
            for key, label in metadata_keys.items():
                if key in metadata:
                    val = str(metadata[key])
                    if key == "channels":
                        val = format_channel_list(metadata[key], channel_names_dict)
                    if key == "acquisition_time_millis":
                        val = str(metadata[key] / 1000)
                    v_box.addLayout(
                        self.create_compact_label_row(label, val, "#11468F", "#11468F")
                    )

    # ------------------------------------------------------------------
    # Window positioning
    # ------------------------------------------------------------------

    def center_window(self):
        """Centers the popup window on the primary screen."""
        self.setMinimumWidth(900)
        window_geometry = self.frameGeometry()
        screen_geometry = QApplication.primaryScreen().availableGeometry().center()
        window_geometry.moveCenter(screen_geometry)
        self.move(window_geometry.topLeft())