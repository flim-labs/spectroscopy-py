"""
controls_phasors.py
===================
Handles phasor-specific controls and plot updates:
- on_quantize_phasors_changed
- on_phasors_resolution_changed
- on_harmonic_selector_change
- _update_phasor_plots_for_harmonic
- is_phasors (predicate helper)
"""

from utils.helpers import mhz_to_ns
from utils.layout_utilities import hide_layout, show_layout
from components.read_data import ReadData
from core.phasors_controller import PhasorsController
import settings.settings as s


def is_phasors(app) -> bool:
    """
    Checks if the currently selected tab is the Phasors tab.

    Args:
        app: The main application instance.

    Returns:
        bool: True if the Phasors tab is active, False otherwise.
    """
    return app.tab_selected == s.TAB_PHASORS


def on_quantize_phasors_changed(app, value):
    """
    Callback for the 'Quantize Phasors' switch.

    Args:
        app: The main application instance.
        value (bool): The new state of the switch.
    """
    PhasorsController.clear_phasors_points(app)
    harmonic_value = int(app.control_inputs[s.HARMONIC_SELECTOR].currentText())
    app.quantized_phasors = value
    app.settings.setValue(s.SETTINGS_QUANTIZE_PHASORS, value)
    container = app.control_inputs["phasors_resolution_container"]
    if value:
        show_layout(container)
        bins = int(s.PHASORS_RESOLUTIONS[app.phasors_resolution])
        PhasorsController.quantize_phasors(app, harmonic_value, bins)
    else:
        hide_layout(container)
        for channel_index in app.plots_to_show:
            if channel_index in app.quantization_images:
                widget = app.phasors_widgets[channel_index]
                widget.removeItem(app.quantization_images[channel_index])
                del app.quantization_images[channel_index]
            if channel_index in app.phasors_colorbars:
                widget.removeItem(app.phasors_colorbars[channel_index])
                del app.phasors_colorbars[channel_index]

        is_phasors_read_mode = (
            app.tab_selected == s.TAB_PHASORS and app.acquire_read_mode == "read"
        )

        if not is_phasors_read_mode and len(app.plots_to_show) <= len(
            app.all_phasors_points
        ):
            for channel_index in app.plots_to_show:
                points = app.all_phasors_points[channel_index][harmonic_value]
                PhasorsController.draw_points_in_phasors(
                    app, channel_index, harmonic_value, points
                )


def on_phasors_resolution_changed(app, value):
    """
    Callback for when the phasor quantization resolution changes.

    Args:
        app: The main application instance.
        value (int): The index of the selected resolution.
    """
    app.phasors_resolution = int(value)
    harmonic_value = int(app.control_inputs[s.HARMONIC_SELECTOR].currentText())
    app.settings.setValue(s.SETTINGS_PHASORS_RESOLUTION, value)
    PhasorsController.quantize_phasors(
        app,
        harmonic_value,
        bins=int(s.PHASORS_RESOLUTIONS[app.phasors_resolution]),
    )


def _update_phasor_plots_for_harmonic(app):
    """
    Redraws all elements on the phasor plots based on the current harmonic.

    Called when harmonic selection changes; updates points, clusters,
    legends, and lifetime curves.

    Args:
        app: The main application instance.
    """
    from core.controls.controls_acquisition import get_current_frequency_mhz

    is_phasors_read_mode = (
        app.tab_selected == s.TAB_PHASORS and app.acquire_read_mode == "read"
    )

    if app.acquire_read_mode == "read" and not is_phasors_read_mode:
        PhasorsController.clear_phasors_file_scatters(app)
        PhasorsController.clear_phasors_files_legend(app)

    if app.acquire_read_mode == "read":
        frequency_mhz = ReadData.get_frequency_mhz(app)
    else:
        frequency_mhz = get_current_frequency_mhz(app)
    laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0

    if app.harmonic_selector_value >= 1 and app.quantized_phasors:
        PhasorsController.quantize_phasors(
            app,
            app.harmonic_selector_value,
            bins=int(s.PHASORS_RESOLUTIONS[app.phasors_resolution]),
        )

    if not app.quantized_phasors:
        if is_phasors_read_mode:
            PhasorsController.clear_phasors_file_scatters(app)
            PhasorsController.clear_phasors_files_legend(app)
            for i, channel_index in enumerate(app.plots_to_show):
                if (
                    channel_index < len(app.all_phasors_points)
                    and app.harmonic_selector_value
                    in app.all_phasors_points[channel_index]
                ):
                    PhasorsController.draw_points_in_phasors(
                        app,
                        channel_index,
                        app.harmonic_selector_value,
                        app.all_phasors_points[channel_index][
                            app.harmonic_selector_value
                        ],
                    )

    PhasorsController.generate_phasors_cluster_center(app, app.harmonic_selector_value)
    PhasorsController.hide_phasors_legends(app)
    PhasorsController.generate_phasors_legend(app, app.harmonic_selector_value)

    for i, channel_index in enumerate(app.plots_to_show):
        PhasorsController.draw_lifetime_points_in_phasors(
            app,
            channel_index,
            app.harmonic_selector_value,
            laser_period_ns,
            frequency_mhz,
        )


def on_harmonic_selector_change(app, value):
    """
    Callback for when the displayed harmonic is changed via the selector.

    Args:
        app: The main application instance.
        value (int): The index of the selected harmonic.
    """
    PhasorsController.clear_phasors_points(app)
    if not app.phasors_widgets or value < 0:
        return
    app.harmonic_selector_value = int(value) + 1
    app.phasors_harmonic_selected = int(value) + 1
    _update_phasor_plots_for_harmonic(app)