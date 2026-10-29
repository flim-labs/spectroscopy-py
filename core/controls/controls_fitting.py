"""
controls_fit.py
===============
Handles the FIT button lifecycle and fitting popup logic:
- fit_button_show: dynamically creates the FIT button in its placeholder
- fit_button_hide: removes and destroys the FIT button
- on_fit_btn_click: gathers data and opens the FittingDecayConfigPopup
"""

import os
from functools import partial

from utils.helpers import mhz_to_ns
from components.fitting_config_popup import FittingDecayConfigPopup
from components.read_data import ReadData
import settings.settings as s

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton


def fit_button_show(app):
    """
    Dynamically creates and displays the 'FIT' button in its placeholder.

    Args:
        app: The main application instance.
    """
    if s.FIT_BTN not in app.control_inputs:
        app.control_inputs[s.FIT_BTN] = QPushButton("FIT")
        app.control_inputs[s.FIT_BTN].setFlat(True)
        app.control_inputs[s.FIT_BTN].setFixedHeight(55)
        app.control_inputs[s.FIT_BTN].setCursor(Qt.CursorShape.PointingHandCursor)
        app.control_inputs[s.FIT_BTN].clicked.connect(
            partial(on_fit_btn_click, app)
        )
        app.control_inputs[s.FIT_BTN].setStyleSheet(
            """
        QPushButton {
            background-color: #1E90FF;
            color: white;
            width: 60px;
            border-radius: 5px;
            padding: 5px 12px;
            font-weight: bold;
            font-size: 16px;
        }
        """
        )
        app.control_inputs[s.FIT_BTN_PLACEHOLDER].layout().addWidget(
            app.control_inputs[s.FIT_BTN]
        )


def fit_button_hide(app):
    """
    Dynamically removes and hides the 'FIT' button from its placeholder.

    Args:
        app: The main application instance.
    """
    if s.FIT_BTN in app.control_inputs:
        app.control_inputs[s.FIT_BTN_PLACEHOLDER].layout().removeWidget(
            app.control_inputs[s.FIT_BTN]
        )
        app.control_inputs[s.FIT_BTN].deleteLater()
        del app.control_inputs[s.FIT_BTN]
        app.control_inputs[s.FIT_BTN_PLACEHOLDER].layout().setContentsMargins(
            0, 0, 0, 0
        )


def on_fit_btn_click(app):
    """
    Handles the 'FIT' button click event.

    Gathers the necessary data from the current state (either from a live
    acquisition or a loaded file) and opens the fitting configuration popup.

    Args:
        app: The main application instance.
    """
    from core.acquisition_controller import AcquisitionController
    from core.fitting_controller import FittingController
    from core.controls.controls_acquisition import get_frequency_mhz

    data = []
    time_shift = 0
    frequency_mhz = get_frequency_mhz(app)
    laser_period_ns = mhz_to_ns(frequency_mhz) if frequency_mhz != 0 else 0

    preloaded_fitting_results = ReadData.preloaded_fitting_data(app)
    has_multi_file_fitting = preloaded_fitting_results and any(
        "file_index" in r for r in preloaded_fitting_results if "error" not in r
    )

    if app.acquire_read_mode == "read":
        display_channel = app.plots_to_show[0] if app.plots_to_show else 0
        time_shift = (
            0
            if display_channel not in app.time_shifts
            else app.time_shifts[display_channel]
        )

        if app.reader_data["fitting"]["data"]["spectroscopy_data"]:
            if has_multi_file_fitting:
                active_channels = ReadData.get_fitting_active_channels(app)
                data.append(
                    {
                        "x": [0],
                        "y": [0],
                        "time_shift": time_shift,
                        "title": "Multi-File Comparison",
                        "channel_index": 0,
                    }
                )
            else:
                spectroscopy_data = app.reader_data["fitting"]["data"][
                    "spectroscopy_data"
                ]
                has_files_data = (
                    "files_data" in spectroscopy_data
                    and len(spectroscopy_data.get("files_data", [])) > 0
                )
                if has_files_data:
                    data = ReadData.get_spectroscopy_data_to_fit(app)
                else:
                    data, time_shift = (
                        AcquisitionController.acquired_spectroscopy_data_to_fit(
                            app, read=True
                        )
                    )
                if len(data) > 0 and "file_index" not in data[0]:
                    file_name = "Single File"
                    if hasattr(app, "reader_data") and app.reader_data:
                        if "fitting" in app.reader_data:
                            if "files" in app.reader_data["fitting"]:
                                fitting_files = app.reader_data["fitting"]["files"]
                                if (
                                    isinstance(fitting_files, dict)
                                    and "spectroscopy" in fitting_files
                                ):
                                    spectroscopy_files = fitting_files["spectroscopy"]
                                    if (
                                        isinstance(spectroscopy_files, list)
                                        and len(spectroscopy_files) > 0
                                    ):
                                        file_name = os.path.basename(
                                            spectroscopy_files[0]
                                        )
                    for entry in data:
                        entry["file_index"] = 0
                        entry["file_name"] = file_name
        else:
            from utils.channel_name_utils import get_channel_name

            active_channels = ReadData.get_fitting_active_channels(app)
            if len(active_channels) > 1:
                title = f"Average of {len(active_channels)} channel(s)"
            elif len(active_channels) > 0:
                title = get_channel_name(active_channels[0], app.channel_names)
            else:
                title = "No data"
            data.append(
                {
                    "x": [0],
                    "y": [0],
                    "time_shift": time_shift,
                    "title": title,
                    "channel_index": 0,
                }
            )
    else:
        data, time_shift = AcquisitionController.acquired_spectroscopy_data_to_fit(
            app, read=False
        )

    for i, d in enumerate(data):
        has_file_info = "file_index" in d

    read_mode = app.acquire_read_mode == "read"

    # Close existing popup if it exists
    if hasattr(app, "fitting_config_popup") and app.fitting_config_popup is not None:
        try:
            app.fitting_config_popup.close()
            app.fitting_config_popup.deleteLater()
            app.fitting_config_popup = None
        except Exception:
            pass

    # Extract IRFs from reference file
    irfs = []
    irfs_tau_ns = None
    if app.irf_reference_file is not None:
        if (
            "ref_type" in app.birfi_reference_data
            and app.birfi_reference_data["ref_type"] == "birfi"
        ):
            if "irfs" in app.birfi_reference_data:
                irfs = app.birfi_reference_data["irfs"]
            if "tau_ns" in app.birfi_reference_data:
                irfs_tau_ns = app.birfi_reference_data["tau_ns"]
        if (
            "ref_type" in app.irf_reference_data
            and app.irf_reference_data["ref_type"] == "irf"
        ):
            if "irfs" in app.irf_reference_data:
                irfs = app.irf_reference_data["irfs"]

    deconvolved_signals = FittingController.deconvolve_signals(
        app, [d for d in data], irfs, laser_period_ns
    )

    app.fitting_config_popup = FittingDecayConfigPopup(
        app,
        data=deconvolved_signals if len(deconvolved_signals) > 0 else data,
        read_mode=read_mode,
        preloaded_fitting=preloaded_fitting_results,
        save_plot_img=app.acquire_read_mode == "read",
        y_data_shift=time_shift,
        laser_period_ns=laser_period_ns,
        use_deconvolution=app.use_deconvolution
        and app.acquire_read_mode != "read"
        and len(irfs) > 0,
        irfs=irfs,
        raw_signals=data,
        irfs_tau_ns=irfs_tau_ns,
    )
    app.fitting_config_popup.show()