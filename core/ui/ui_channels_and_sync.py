"""
ui_channels_and_sync.py
======================
Handles creation of channel-related UI components:
- Channel selection checkboxes (with rename support)
- Full channel selector row (detect button, type dropdown, checkboxes, plots config)
- Sync mode buttons (Sync In / Sync Out frequencies, pico mode toggle)
"""

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
    Creates and adds channel selection checkboxes to the given layout.

    Args:
        app: The main application instance.
        layout (QLayout): The layout to add the checkboxes to.
    """
    from core.controls_controller import ControlsController
    from utils.channel_name_utils import get_channel_name_parts

    for i in range(s.MAX_CHANNELS):
        ch_wrapper = QWidget()
        ch_wrapper.setObjectName("ch_checkbox_wrapper")
        ch_wrapper.setFixedHeight(40)
        row = QHBoxLayout()
        from components.fancy_checkbox import FancyCheckbox
        from core.ui.ui_channels_and_sync import open_rename_modal

        custom_part, default_part = get_channel_name_parts(i, app.channel_names)

        fancy_checkbox = FancyCheckbox(
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
        fancy_checkbox.labelClicked.connect(
            lambda channel=i: open_rename_modal(app, channel)
        )
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
    _, inp, __ = SelectControl.setup(
        "Channel type:",
        int(app.settings.value(s.SETTINGS_CONNECTION_TYPE, s.DEFAULT_CONNECTION_TYPE)),
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

    This includes the 'Check Card' widget and buttons for 'Sync In' and
    various 'Sync Out' frequencies, plus the pico mode (100ps) toggle.

    Args:
        app: The main application instance.

    Returns:
        QHBoxLayout: The layout containing the sync buttons.
    """
    from core.controls_controller import ControlsController

    buttons_layout = QHBoxLayout()
    check_card_widget = CheckCard(app)
    buttons_layout.addWidget(check_card_widget)
    buttons_layout.addSpacing(20)
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
    ## buttons_layout.addSpacing(10)
    ## pico_mode_container = QWidget()
    ## pico_mode_layout = QHBoxLayout()
    ## pico_mode_container.setFixedWidth(100)
    ## pico_mode_layout.setContentsMargins(0, 0, 0, 0)
    ## pico_mode_layout.setSpacing(0)
    ## pico_mode_label = QLabel("100ps:")
    ## pico_mode_toggle = SwitchControl(
    ##    active_color="#11468F",
    ##    checked=app.settings.value(s.SETTINGS_PICO_MODE, s.DEFAULT_PICO_MODE)
    ##    == "true",
    ##)
    ## pico_mode_toggle.toggled.connect(
    ##    partial(ControlsController.on_pico_mode_changed, app)
    ##)
    ## pico_mode_layout.addWidget(pico_mode_label)
    ## pico_mode_layout.addWidget(pico_mode_toggle)
    ## pico_mode_container.setLayout(pico_mode_layout)
    ## buttons_layout.addWidget(pico_mode_container)
    ##app.control_inputs[s.SETTINGS_PICO_MODE] = pico_mode_toggle
    ##app.widgets["pico_mode_container"] = pico_mode_container
    for button, name in app.sync_buttons:

        def on_toggle(toggled_name):
            for b, n in app.sync_buttons:
                b.set_selected(n == toggled_name)
            ControlsController.on_sync_selected(app, toggled_name)

        button.clicked.connect(lambda _, n=name: on_toggle(n))
        button.set_selected(app.selected_sync == name)
    app.widgets["sync_buttons_layout"] = buttons_layout
    ## ControlsController.update_pico_mode_toggle(
    ##     app, ControlsController.get_current_frequency_mhz(app)
    ## )
    return buttons_layout


def update_plot_titles_for_channel(app, channel_id):
    """
    Updates plot titles for a specific channel after rename.

    Args:
        app: The main application instance.
        channel_id (int): The channel index to update.
    """
    import pyqtgraph as pg
    from utils.channel_name_utils import get_channel_name

    channel_names = getattr(app, "channel_names", {})

    # Update intensity plot title
    if channel_id in app.intensities_widgets:
        wrapper = app.intensities_widgets[channel_id]
        layout = wrapper.layout()
        if layout:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    if isinstance(widget, pg.PlotWidget):
                        new_title = (
                            f"{get_channel_name(channel_id, channel_names)} intensity"
                        )
                        widget.setTitle(new_title)
                        break

    # Update decay plot title (only in acquire mode)
    if channel_id in app.decay_widgets and app.acquire_read_mode == "acquire":
        decay_widget = app.decay_widgets[channel_id]
        new_title = f"{get_channel_name(channel_id, channel_names)} decay"
        decay_widget.setTitle(new_title)

    # Update phasors plot title (only in acquire mode, not in read mode)
    if channel_id in app.phasors_widgets:
        if not (app.tab_selected == s.TAB_PHASORS and app.acquire_read_mode == "read"):
            phasors_widget = app.phasors_widgets[channel_id]
            new_title = f"{get_channel_name(channel_id, channel_names)} phasors"
            phasors_widget.setTitle(new_title)


def open_rename_modal(app, channel_id):
    """
    Opens modal to rename a channel.

    Args:
        app: The main application instance.
        channel_id (int): The channel index to rename.
    """
    from components.rename_channel_modal import RenameChannelModal

    current_name = app.channel_names.get(str(channel_id), "")
    modal = RenameChannelModal(channel_id, current_name, app)
    modal.channelRenamed.connect(lambda cid, name: on_channel_renamed(app, cid, name))
    modal.exec()


def on_channel_renamed(app, channel_id, new_name):
    """
    Handles the channel rename event: persists the name and refreshes UI.

    Args:
        app: The main application instance.
        channel_id (int): The channel index that was renamed.
        new_name (str): The new name entered by the user (empty to reset).
    """
    import json
    from utils.channel_name_utils import get_channel_name_parts

    if new_name:
        app.channel_names[str(channel_id)] = new_name
    else:
        if str(channel_id) in app.channel_names:
            del app.channel_names[str(channel_id)]

    app.settings.setValue(s.SETTINGS_CHANNEL_NAMES, json.dumps(app.channel_names))

    if channel_id < len(app.channel_checkboxes):
        custom_part, default_part = get_channel_name_parts(
            channel_id, app.channel_names
        )
        checkbox = app.channel_checkboxes[channel_id]
        checkbox.set_text_parts(custom_part, default_part)

    update_plot_titles_for_channel(app, channel_id)
