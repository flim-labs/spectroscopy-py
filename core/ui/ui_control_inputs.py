"""
ui_control_inputs.py
==========================================
Handles creation of the main control input widgets row:
- Basic acquisition controls (bin width, time span, free running, acquisition time)
- Pile-up threshold (also sets cps_threshold on LaserbloodMetadataPopup) and SBR
- Fitting controls (deconvolution toggle)
- Phasor controls (quantize, resolution — SelectControl returns 4 values here)
- Calibration controls (calibration type, TAU, harmonics — SelectControl returns 4 values)
- Replicates and harmonic display selector (edition-specific, replaces _create_harmonic_control)
- Assembly of the full controls row
"""

from functools import partial

from utils.gui_styles import GUIStyles
from components.buttons import CollapseButton
from components.input_number_control import InputFloatControl, InputNumberControl
from utils.layout_utilities import hide_layout, show_layout
from components.select_control import SelectControl
from components.switch_control import SwitchControl
import settings.settings as s
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)


def _create_basic_controls(app, layout):
    """
    Creates basic acquisition controls like bin width, time span, etc.

    Args:
        app: The main application instance.
        layout (QLayout): The layout to add the controls to.
    """
    from core.controls_controller import ControlsController

    _, inp = InputNumberControl.setup(
        "Bin width (µs):",
        1000,
        1000000,
        int(app.settings.value(s.SETTINGS_BIN_WIDTH, s.DEFAULT_BIN_WIDTH)),
        layout,
        partial(ControlsController.on_bin_width_change, app),
    )
    inp.setStyleSheet(GUIStyles.set_input_number_style())
    app.control_inputs[s.SETTINGS_BIN_WIDTH] = inp

    _, inp = InputNumberControl.setup(
        "Time span (s):",
        1,
        300,
        int(app.settings.value(s.SETTINGS_TIME_SPAN, s.DEFAULT_TIME_SPAN)),
        layout,
        partial(ControlsController.on_time_span_change, app),
    )
    inp.setStyleSheet(GUIStyles.set_input_number_style())
    app.control_inputs[s.SETTINGS_TIME_SPAN] = inp

    switch_control = QVBoxLayout()
    inp = SwitchControl(
        active_color="#11468F",
        checked=app.settings.value(s.SETTINGS_FREE_RUNNING, s.DEFAULT_FREE_RUNNING)
        == "true",
    )
    inp.toggled.connect(partial(ControlsController.on_free_running_changed, app))
    switch_control.addWidget(QLabel("Free running:"))
    switch_control.addSpacing(8)
    switch_control.addWidget(inp)
    layout.addLayout(switch_control)
    layout.addSpacing(20)
    app.control_inputs[s.SETTINGS_FREE_RUNNING] = inp

    _, inp = InputNumberControl.setup(
        "Acquisition time (s):",
        1,
        1800,
        int(
            app.settings.value(
                s.SETTINGS_ACQUISITION_TIME, s.DEFAULT_ACQUISITION_TIME
            )
        ),
        layout,
        partial(ControlsController.on_acquisition_time_change, app),
    )
    inp.setStyleSheet(GUIStyles.set_input_number_style())
    app.control_inputs[s.SETTINGS_ACQUISITION_TIME] = inp
    ControlsController.on_free_running_changed(
        app,
        app.settings.value(s.SETTINGS_FREE_RUNNING, s.DEFAULT_FREE_RUNNING)
        == "true",
    )


def _create_pileup_sbr_controls(app, layout):
    """
    Creates controls for pile-up threshold and SBR display.

    Also notifies LaserbloodMetadataPopup of the initial CPS threshold value
    (edition-specific side effect).

    Args:
        app: The main application instance.
        layout (QLayout): The layout to add the controls to.
    """
    from core.controls_controller import ControlsController
    from components.laserblood_metadata_popup import LaserbloodMetadataPopup

    cps_threshold = int(
        app.settings.value(s.SETTINGS_CPS_THRESHOLD, s.DEFAULT_CPS_THRESHOLD)
    )
    _, inp = InputNumberControl.setup(
        "Pile-up threshold (CPS):",
        0,
        100000000,
        cps_threshold,
        layout,
        partial(ControlsController.on_cps_threshold_change, app),
    )
    inp.setStyleSheet(GUIStyles.set_input_number_style(min_width="70px"))
    app.control_inputs[s.SETTINGS_CPS_THRESHOLD] = inp
    # Edition-specific: propagate initial value to Laserblood metadata popup
    LaserbloodMetadataPopup.set_cps_threshold(app, cps_threshold)

    show_SBR_control = QVBoxLayout()
    show_SBR_control.setContentsMargins(0, 0, 0, 0)
    show_SBR_control.setSpacing(0)
    show_SBR_label = QLabel("Show SBR:")
    inp = SwitchControl(
        active_color=s.PALETTE_BLUE_1, width=60, height=30, checked=app.show_SBR
    )
    app.control_inputs[s.SETTINGS_SHOW_SBR] = inp
    inp.toggled.connect(partial(ControlsController.on_show_SBR_changed, app))
    show_SBR_control.addWidget(show_SBR_label)
    show_SBR_control.addSpacing(5)
    show_SBR_control.addWidget(inp)
    layout.addLayout(show_SBR_control)
    layout.addSpacing(10)


def _create_phasor_controls(app, layout):
    """
    Creates controls specific to the Phasor tab.

    Note: SelectControl.setup returns 4 values in the Laserblood edition
    (layout container, input widget, label, container widget).

    Args:
        app: The main application instance.
        layout (QLayout): The layout to add the controls to.
    """
    from core.controls_controller import ControlsController

    quantize_phasors_switch_control = QVBoxLayout()
    inp_quantize = SwitchControl(
        active_color="#11468F", checked=app.quantized_phasors
    )
    inp_quantize.toggled.connect(
        partial(ControlsController.on_quantize_phasors_changed, app)
    )
    app.control_inputs[s.SETTINGS_QUANTIZE_PHASORS] = inp_quantize
    quantize_phasors_switch_control.addWidget(QLabel("Quantize Phasors:"))
    quantize_phasors_switch_control.addSpacing(8)
    quantize_phasors_switch_control.addWidget(inp_quantize)
    app.control_inputs["quantize_phasors_container"] = quantize_phasors_switch_control
    (
        show_layout(quantize_phasors_switch_control)
        if app.tab_selected == s.TAB_PHASORS and app.acquire_read_mode != "read"
        else hide_layout(quantize_phasors_switch_control)
    )
    layout.addLayout(quantize_phasors_switch_control)
    layout.addSpacing(20)

    # SelectControl returns 4 values in the Laserblood edition
    phasors_resolution_container, inp, __, container = SelectControl.setup(
        "Squares:",
        app.phasors_resolution,
        layout,
        s.PHASORS_RESOLUTIONS,
        partial(ControlsController.on_phasors_resolution_changed, app),
        width=70,
    )
    inp.setStyleSheet(GUIStyles.set_input_select_style())
    (
        show_layout(phasors_resolution_container)
        if (
            app.tab_selected == s.TAB_PHASORS
            and app.quantized_phasors
            and app.acquire_read_mode != "read"
        )
        else hide_layout(phasors_resolution_container)
    )
    app.control_inputs[s.SETTINGS_PHASORS_RESOLUTION] = inp
    app.control_inputs["phasors_resolution_container"] = phasors_resolution_container


def _create_calibration_controls(app, layout):
    """
    Creates controls for calibration, TAU, and harmonics.

    Note: SelectControl.setup returns 4 values in the Laserblood edition.

    Args:
        app: The main application instance.
        layout (QLayout): The layout to add the controls to.
    """
    from core.controls_controller import ControlsController

    # SelectControl returns 4 values in the Laserblood edition
    _, inp, label, container = SelectControl.setup(
        "Calibration:",
        int(
            app.settings.value(
                s.SETTINGS_CALIBRATION_TYPE, s.DEFAULT_SETTINGS_CALIBRATION_TYPE
            )
        ),
        layout,
        s.CALIBRATION_TYPES,
        partial(ControlsController.on_calibration_change, app),
    )
    inp.setStyleSheet(GUIStyles.set_input_select_style())
    app.control_inputs["calibration"] = inp
    app.control_inputs["calibration_label"] = label

    label, inp = InputFloatControl.setup(
        "TAU (ns):",
        0,
        1000,
        float(app.settings.value(s.SETTINGS_TAU_NS, "0")),
        layout,
        partial(ControlsController.on_tau_change, app),
    )
    inp.setStyleSheet(GUIStyles.set_input_number_style())
    app.control_inputs["tau"] = inp
    app.control_inputs["tau_label"] = label

    label, inp = InputNumberControl.setup(
        "Harmonics:",
        1,
        4,
        int(app.settings.value(s.SETTINGS_HARMONIC, "1")),
        layout,
        partial(ControlsController.on_harmonic_change, app),
    )
    inp.setStyleSheet(GUIStyles.set_input_number_style())
    app.control_inputs[s.SETTINGS_HARMONIC] = inp
    app.control_inputs[s.SETTINGS_HARMONIC_LABEL] = label


def _create_replicate_and_harmonic_controls(app, layout):
    """
    Creates controls for the harmonic display selector and replicate count.

    This is an edition-specific method that replaces the simpler
    _create_harmonic_control of the standard edition. It adds both the
    harmonic selector dropdown and an N° Replicate numeric input.

    Note: SelectControl.setup returns 4 values in the Laserblood edition.

    Args:
        app: The main application instance.
        layout (QLayout): The layout to add the controls to.
    """
    from core.controls_controller import ControlsController

    # Harmonic selector (SelectControl returns 4 values)
    ctl, inp, label, container = SelectControl.setup(
        "Harmonic displayed:",
        0,
        layout,
        ["1", "2", "3", "4"],
        partial(ControlsController.on_harmonic_selector_change, app),
    )
    inp.setStyleSheet(GUIStyles.set_input_select_style())
    app.control_inputs[s.HARMONIC_SELECTOR_LABEL] = label
    app.control_inputs[s.HARMONIC_SELECTOR] = inp
    label.hide()
    inp.hide()

    # Replicates input (edition-specific)
    label, inp = InputNumberControl.setup(
        "N° Replicate:",
        1,
        100000,
        int(app.replicates),
        layout,
        partial(ControlsController.on_replicate_change, app),
    )
    inp.setStyleSheet(
        GUIStyles.set_input_number_style(min_width="40px", border_color="#11468F")
    )
    app.control_inputs[s.SETTINGS_REPLICATES] = inp
    app.control_inputs["replicates_label"] = label


def _create_fitting_controls(app, layout):
    """
    Creates controls for the Fitting tab (deconvolution toggle).

    Args:
        app: The main application instance.
        layout (QLayout): The layout to add the controls to.
    """
    from core.controls_controller import ControlsController

    use_deconv_switch_control = QVBoxLayout()
    use_deconv_switch_control.setContentsMargins(0, 0, 0, 0)
    use_deconv_switch_control.setSpacing(0)
    inp_use_deconv = SwitchControl(
        active_color="#11468F", checked=app.use_deconvolution
    )
    inp_use_deconv.toggled.connect(
        partial(ControlsController.on_use_deconvolution_changed, app)
    )
    app.control_inputs[s.SETTINGS_USE_DECONVOLUTION] = inp_use_deconv
    use_deconv_switch_control.addWidget(QLabel("Use Deconvolution:"))
    use_deconv_switch_control.addSpacing(5)
    use_deconv_switch_control.addWidget(inp_use_deconv)
    app.control_inputs["use_deconv_container"] = use_deconv_switch_control
    (
        show_layout(use_deconv_switch_control)
        if app.tab_selected == s.TAB_FITTING and app.acquire_read_mode != "read"
        else hide_layout(use_deconv_switch_control)
    )
    layout.addLayout(use_deconv_switch_control)
    layout.addSpacing(20)


def create_control_inputs(app):
    """
    Creates and assembles the main row of control inputs.

    This function orchestrates the creation of all control widgets by
    calling the respective private helper functions and arranging them
    in a horizontal layout.

    Args:
        app: The main application instance.

    Returns:
        QHBoxLayout: The layout containing all control inputs.
    """
    from core.ui.ui_action_buttons import create_action_buttons

    controls_row = QHBoxLayout()
    controls_row.setContentsMargins(0, 10, 0, 0)
    controls_row.addSpacing(10)

    _create_basic_controls(app, controls_row)
    _create_pileup_sbr_controls(app, controls_row)
    _create_fitting_controls(app, controls_row)
    _create_phasor_controls(app, controls_row)
    _create_calibration_controls(app, controls_row)

    spacer = QWidget()
    controls_row.addWidget(spacer, 1)

    # Edition-specific: replicate + harmonic (vs. harmonic-only in standard)
    _create_replicate_and_harmonic_controls(app, controls_row)
    create_action_buttons(app, controls_row)

    collapse_button = CollapseButton(app.widgets[s.TOP_COLLAPSIBLE_WIDGET])
    controls_row.addWidget(collapse_button)
    app.widgets["collapse_button"] = collapse_button
    controls_row.addSpacing(10)

    return controls_row