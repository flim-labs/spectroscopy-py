"""
ui_controller.py 
======================================================
Facade / controller that delegates all UI construction and update
operations to the dedicated sub-modules in the `core/ui/` package.

Sub-module responsibilities
---------------------------
ui.ui_top_bar          — logo, title, tabs, Laserblood METADATA button,
                          export controls, Time Tagger, top bar assembly
ui.ui_channels_and_sync — channel checkboxes (with inline rename + settings-based
                          name loading), channel selector row, sync buttons
                          (pico mode visibility driven by frequency/channel helpers)
ui.ui_control_inputs   — acquisition / phasor / calibration / fitting controls;
                          replicate + harmonic selector (edition-specific);
                          LaserbloodMetadataPopup side effects on CPS threshold
ui.ui_action_buttons   — START/STOP, READ/PLOT, EXPORT, LOAD REFERENCE, style helpers
ui.ui_banners          — reference data info banner
"""

import flim_labs
from components.progress_bar import ProgressBar
from utils.gui_styles import GUIStyles
from utils.logo_utilities import TitlebarIcon
import settings.settings as s
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QApplication, QGridLayout, QVBoxLayout

# Sub-module imports
from core.ui.ui_top_bar import create_top_bar
from core.ui.ui_banners import (
    create_ref_data_info_banner,
    update_reference_info_banner_label,
    show_ref_info_banner,
)
from core.ui.ui_action_buttons import style_start_button
from core.ui.ui_control_inputs import create_control_inputs
from core.ui.ui_channels_and_sync import create_channel_selector, create_sync_buttons


class UIController:
    """
    Facade controller for all UI construction and update operations.

    Every method delegates to the appropriate `ui/` sub-module, keeping
    this class thin and easy to navigate.

    Laserblood-specific differences vs. the standard edition are fully
    encapsulated inside the sub-modules; this facade exposes the same
    public API surface.
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    @staticmethod
    def init_ui(app):
        """
        Initializes the main application window and its core layout.

        Sets the window title (Laserblood branding), icon, theme, and
        restores previous size/position. Creates the main layout structure.

        Args:
            app: The main application instance (subclass of QWidget).

        Returns:
            tuple[QWidget, QGridLayout]: Top bar container and plot grid layout.
        """
        app.setWindowTitle(
            "FlimLabs - SPECTROSCOPY LASERBLOOD v"
            + s.VERSION
            + " - API v"
            + flim_labs.get_version()
        )
        TitlebarIcon.setup(app)
        GUIStyles.customize_theme(app)
        main_layout = QVBoxLayout()
        top_bar = create_top_bar(app)
        main_layout.addWidget(top_bar, 0, Qt.AlignmentFlag.AlignTop)
        # Time tagger progress bar
        time_tagger_progress_bar = ProgressBar(
            visible=False, indeterminate=True, label_text="Time tagger processing..."
        )
        app.widgets[s.TIME_TAGGER_PROGRESS_BAR] = time_tagger_progress_bar
        main_layout.addWidget(time_tagger_progress_bar)
        reference_banner = create_ref_data_info_banner(app)
        main_layout.addLayout(reference_banner[0])
        main_layout.addSpacing(5)
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        app.setLayout(main_layout)
        app.resize(
            app.settings.value("size", QSize(s.APP_DEFAULT_WIDTH, s.APP_DEFAULT_HEIGHT))
        )
        app.move(
            app.settings.value(
                "pos",
                QApplication.primaryScreen().geometry().center()
                - app.frameGeometry().center(),
            )
        )
        return top_bar, grid_layout

    # ------------------------------------------------------------------
    # Top bar
    # ------------------------------------------------------------------

    @staticmethod
    def create_top_bar(app):
        return create_top_bar(app)

    # ------------------------------------------------------------------
    # Control inputs
    # ------------------------------------------------------------------

    @staticmethod
    def create_control_inputs(app):
        return create_control_inputs(app)

    # ------------------------------------------------------------------
    # Channel selector & sync buttons
    # ------------------------------------------------------------------

    @staticmethod
    def create_channel_selector(app):
        return create_channel_selector(app)

    @staticmethod
    def create_sync_buttons(app):
        return create_sync_buttons(app)

    # ------------------------------------------------------------------
    # Action buttons
    # ------------------------------------------------------------------

    @staticmethod
    def style_start_button(app):
        style_start_button(app)

    # ------------------------------------------------------------------
    # Reference info banner
    # ------------------------------------------------------------------

    @staticmethod
    def create_ref_data_info_banner(app):
        return create_ref_data_info_banner(app)

    @staticmethod
    def update_reference_info_banner_label(app):
        update_reference_info_banner_label(app)

    @staticmethod
    def show_ref_info_banner(app):
        return show_ref_info_banner(app)