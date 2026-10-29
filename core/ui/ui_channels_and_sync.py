"""
ui_channel_and_sync.py
=============================================
Handles creation of channel-related UI components:
- Channel selection checkboxes with inline rename modal and custom-name support
  (loads names from settings at construction time, updates app.channel_names on rename)
- Full channel selector row (detect button, type dropdown, checkboxes, plots config)
- Sync mode buttons (Sync In / Sync Out frequencies) and pico mode toggle
  (visibility is driven by frequency + selected channels, unlike the standard edition)
"""

import json
from functools import partial

from components.channels_detection import DetectChannelsButton
from components.check_card import CheckCard
from components.fancy_checkbox import FancyButton
from utils.gui_styles import GUIStyles
from components.select_control import SelectControl
from components.switch_control import SwitchControl
from utils.resource_path import resource_path
import settings.settings as s
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
)


def _create_channel_checkboxes(app, layout):
    """
    Creates and adds channel selection checkboxes to the given layout,
    supporting custom names and the inline rename modal.

    Args:
        app: The main application instance.
        layout (QLayout): The layout to add the checkboxes to.
    """
    from core.controls_controller import ControlsController
    from components.rename_channel_modal import RenameChannelModal
    from utils.channel_name_utils import get_channel_name, get_channel_name_parts

    app.channel_checkboxes.clear()

    # Load custom channel names from settings
    custom_names = {}
    if hasattr(app, "settings"):
        custom_names_json = app.settings.value("channel_names", "{}")
        try:
            custom_names = json.loads(custom_names_json)
        except Exception:
            custom_names = {}

    for i in range(s.MAX_CHANNELS):
        ch_wrapper = QWidget()
        ch_wrapper.setObjectName("ch_checkbox_wrapper")
        ch_wrapper.setFixedHeight(40)
        row = QHBoxLayout()
        from components.fancy_checkbox import FancyCheckbox

        custom_part, default_part = get_channel_name_parts(i, custom_names)
        fancy_checkbox = FancyCheckbox(
            text=f"Channel {i + 1}",
            label_custom_part=custom_part,
            label_default_part=default_part,
            label_clickable=True,
        )
        fancy_checkbox.setStyleSheet(GUIStyles.set_checkbox_style())
        if app.selected_channels:
            fancy_checkbox.set_checked(i in app.selected_channels)
        fancy_checkbox.toggled.connect(
            lambda checked, channel=i: ControlsController.on_channel_selected(
                app, checked, channel
            )
        )

        def open_rename_modal(channel_idx=i, checkbox=fancy_checkbox):
            current_name = custom_names.get(str(channel_idx), "")
            modal = RenameChannelModal(channel_idx, current_name, app)

            def on_renamed(idx, new_name):
                # Persist to both local dict and app state
                custom_names[str(idx)] = new_name if new_name else ""
                app.settings.setValue("channel_names", json.dumps(custom_names))
                app.channel_names[str(idx)] = new_name if new_name else ""
                # Refresh checkbox label
                c_part, d_part = get_channel_name_parts(idx, custom_names)
                checkbox.set_text_parts(c_part, d_part)
                # Update plot titles immediately when channel is visible
                if idx in app.plots_to_show:
                    if idx in app.intensity_plot_widgets:
                        title = get_channel_name(idx, custom_names)
                        app.intensity_plot_widgets[idx].setTitle(f"{title} intensity")
                    if (
                        app.acquire_read_mode == "acquire"
                        and idx in app.decay_widgets
                    ):
                        title = get_channel_name(idx, custom_names)
                        app.decay_widgets[idx].setTitle(f"{title} decay")

            modal.channelRenamed.connect(on_renamed)
            modal.exec()

        fancy_checkbox.labelClicked.connect(open_rename_modal)
        row.addWidget(fancy_checkbox)
        ch_wrapper.setLayout(row)
        ch_wrapper.setStyleSheet(GUIStyles.checkbox_wrapper_style())
        layout.addWidget(ch_wrapper, alignment=Qt.AlignmentFlag.AlignBottom)
        app.channel_checkboxes.append(fancy_checkbox)


def create_channel_selector(app):
    """
    Creates the channel selector widget.

    This includes the 'Detect Channels' button, channel type selector,
    individual channel checkboxes, and the 'Plots Config' button.

    Args:
        app: The main application instance.

    Returns:
        QHBoxLayout: The layout containing the channel selection controls.
    """
    from core.controls_controller import ControlsController

    grid = QHBoxLayout()
    grid.addWidget(DetectChannelsButton(app))

    plots_config_btn = QPushButton(" PLOTS CONFIG")
    plots_config_btn.setIcon(QIcon(resource_path("assets/chart-icon.png")))
    GUIStyles.set_stop_btn_style(plots_config_btn)
    plots_config_btn.setFixedWidth(150)
    plots_config_btn.setFixedHeight(40)
    plots_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    plots_config_btn.clicked.connect(
        lambda: ControlsController.open_plots_config_popup(app)
    )

    widget_channel_type = QWidget()
    row_channel_type = QHBoxLayout()
    row_channel_type.setContentsMargins(0, 0, 0, 0)
    # Laserblood edition: SelectControl.setup returns 4 values (includes container)
    _, inp, __, container = SelectControl.setup(
        "Channel type:",
        int(
            app.settings.value(
                s.SETTINGS_CONNECTION_TYPE, s.DEFAULT_CONNECTION_TYPE
            )
        ),
        row_channel_type,
        ["USB", "SMA"],
        partial(ControlsController.on_connection_type_value_change, app),
        spacing=None,
    )
    inp.setFixedHeight(40)
    inp.setStyleSheet(GUIStyles.set_input_select_style())
    widget_channel_type.setLayout(row_channel_type)
    app.control_inputs["channel_type"] = inp
    grid.addWidget(widget_channel_type, alignment=Qt.AlignmentFlag.AlignBottom)

    _create_channel_checkboxes(app, grid)

    grid.addWidget(plots_config_btn, alignment=Qt.AlignmentFlag.AlignBottom)
    app.widgets[s.CHANNELS_GRID] = grid
    return grid


def create_sync_buttons(app):
    """
    Creates the row of synchronization mode selection buttons.

    Pico mode (100ps) visibility is computed dynamically based on frequency
    and selected channels. LaserbloodMetadataPopup.set_FPGA_firmware is called
    after building the layout (edition-specific side effect).

    Args:
        app: The main application instance.

    Returns:
        QHBoxLayout: The layout containing the sync buttons.
    """
    from core.controls_controller import ControlsController
    from components.laserblood_metadata_popup import LaserbloodMetadataPopup

    buttons_layout = QHBoxLayout()
    check_card_widget = CheckCard(app)
    buttons_layout.addWidget(check_card_widget)
    buttons_layout.addSpacing(20)

    # SYNC BUTTONS (FREQUENCY)
    sync_in_button = FancyButton("Sync In")
    buttons_layout.addWidget(sync_in_button)
    app.sync_buttons.append((sync_in_button, "sync_in"))
    ControlsController.update_sync_in_button(app)
    sync_out_80_button = FancyButton("Sync Out (80MHz)")
    buttons_layout.addWidget(sync_out_80_button)
    app.sync_buttons.append((sync_out_80_button, "sync_out_80"))
    sync_out_40_button = FancyButton("Sync Out (40MHz)")
    buttons_layout.addWidget(sync_out_40_button)
    app.sync_buttons.append((sync_out_40_button, "sync_out_40"))
    sync_out_20_button = FancyButton("Sync Out (20MHz)")
    buttons_layout.addWidget(sync_out_20_button)
    app.sync_buttons.append((sync_out_20_button, "sync_out_20"))
    sync_out_10_button = FancyButton("Sync Out (10MHz)")
    buttons_layout.addWidget(sync_out_10_button)
    app.sync_buttons.append((sync_out_10_button, "sync_out_10"))

    for button, name in app.sync_buttons:

        def on_toggle(toggled_name):
            for b, n in app.sync_buttons:
                b.set_selected(n == toggled_name)
            ControlsController.on_sync_selected(app, toggled_name)

        button.clicked.connect(lambda _, n=name: on_toggle(n))
        button.set_selected(app.selected_sync == name)
    app.widgets["sync_buttons_layout"] = buttons_layout

    # PICO MODE (100ps) — visibility driven by frequency + channel selection
    # frequency_mhz = ControlsController.get_frequency_mhz(app)
    # selected_channels = ControlsController.get_selected_channels_from_settings(app)
    #pico_mode_visible = ControlsController.is_pico_mode_active(
    #    app, selected_channels, frequency_mhz
    #)
    # buttons_layout.addSpacing(20)
    ## pico_mode_widget = QWidget()
    # pico_mode_widget.setFixedWidth(100)
    # switch_control_layout = QHBoxLayout()
    # switch_control_layout.setContentsMargins(0, 0, 0, 0)
    # switch_control_layout.setSpacing(0)
    # inp = SwitchControl(
    #     active_color="#11468F",
    #     checked=app.settings.value(s.SETTINGS_PICO_MODE, s.DEFAULT_PICO_MODE)
    #     == "true",
    #)
    # inp.toggled.connect(partial(ControlsController.on_pico_mode_changed, app))
    # label_100ps = QLabel("100ps:")
    # switch_control_layout.addWidget(label_100ps)
    # switch_control_layout.addWidget(inp)
    # pico_mode_widget.setLayout(switch_control_layout)
    # app.control_inputs[s.SETTINGS_PICO_MODE] = inp
    # app.widgets["pico_mode_switch_control"] = pico_mode_widget
    # pico_mode_widget.setVisible(pico_mode_visible)
    # buttons_layout.addWidget(pico_mode_widget)

    # Edition-specific: notify Laserblood metadata about FPGA firmware
    LaserbloodMetadataPopup.set_FPGA_firmware(app)

    return buttons_layout