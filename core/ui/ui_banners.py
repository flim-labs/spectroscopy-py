"""
ui_banners.py
=============
Handles the reference data info banner displayed below the top bar:
- create_ref_data_info_banner: creates and registers the banner widget
- update_reference_info_banner_label: refreshes label text and styling
- show_ref_info_banner: determines whether the banner should be visible
"""

from utils.gui_styles import GUIStyles
from utils.layout_utilities import hide_layout, show_layout
import settings.settings as s
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)


def create_ref_data_info_banner(app):
    """
    Creates the reference data info banner layout and registers it in app.widgets.

    Args:
        app: The main application instance.

    Returns:
        tuple[QVBoxLayout, QLabel]: The banner container layout and the label widget.
    """
    banner_container = QVBoxLayout()
    banner = QWidget()
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    banner.setLayout(layout)
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)
    banner_container.addWidget(banner)
    app.widgets[s.REFERENCE_INFO_BANNER] = banner_container
    app.widgets["reference_banner_label"] = label
    update_reference_info_banner_label(app)
    if show_ref_info_banner(app):
        show_layout(banner_container)
    else:
        hide_layout(banner_container)
    return banner_container, label


def update_reference_info_banner_label(app):
    """
    Refreshes the banner label text and styling based on current app state.

    Args:
        app: The main application instance.
    """
    reference_file = None
    ref_type = "calibration"
    ref_required = False
    if app.tab_selected == s.TAB_PHASORS:
        reference_file = app.phasors_reference_file
        ref_type = "calibration"
        ref_required = True
    elif app.tab_selected == s.TAB_FITTING:
        reference_file = app.irf_reference_file
        ref_type = "IRF"
        ref_required = app.use_deconvolution
    is_none = reference_file is None
    ref_text = "No reference loaded" if is_none else str(reference_file)
    label = app.widgets["reference_banner_label"]
    label.setText(f"Active {ref_type} reference: {ref_text}")
    banner_container = app.widgets.get(s.REFERENCE_INFO_BANNER, None)
    if banner_container is not None and banner_container.count() > 0:
        banner = banner_container.itemAt(0).widget()
        if banner is not None:
            banner.setStyleSheet(
                GUIStyles.ref_data_banner_style(is_none, ref_required=ref_required)
            )
            label.setStyleSheet(
                GUIStyles.ref_data_banner_label_style(
                    is_none, ref_required=ref_required
                )
            )


def show_ref_info_banner(app) -> bool:
    """
    Determines whether the reference info banner should be shown.

    Args:
        app: The main application instance.

    Returns:
        bool: True if the banner should be visible, False otherwise.
    """
    if app.tab_selected == s.TAB_PHASORS and not app.acquire_read_mode == "read":
        return True
    elif (
        app.tab_selected == s.TAB_FITTING
        and app.use_deconvolution
        and not app.acquire_read_mode == "read"
    ):
        return True
    return False