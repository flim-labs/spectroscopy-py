"""
read_data.py  (facade)
======================
Public API for the components/reader package.

Imports all sub-modules and re-exports them under a single ReadData class
"""

# --- sub-module imports ---------------------------------------------------

from components.reader import read_data_io as _io
from components.reader import read_data_utils as _utils
from components.reader import read_data_plot as _plot
from components.reader.read_data_controls import ReadDataControls
from components.reader.reader_popup import ReaderPopup
from components.reader.reader_metadata_popup import ReaderMetadataPopup
from components.reader.reader_workers import WorkerSignals, SavePlotTask


class ReadData:
    """Facade class — static methods delegating to the appropriate sub-module."""

    # ---- IO ---------------------------------------------------------------
    read_bin_data               = staticmethod(_io.read_bin_data)
    read_multiple_bin_data      = staticmethod(_io.read_multiple_bin_data)
    read_multiple_json_data     = staticmethod(_io.read_multiple_json_data)
    read_laserblood_metadata    = staticmethod(_io.read_laserblood_metadata)
    read_fitting_data           = staticmethod(_io.read_fitting_data)
    read_json                   = staticmethod(_io.read_json)
    read_bin                    = staticmethod(_io.read_bin)
    read_spectroscopy_data      = staticmethod(_io.read_spectroscopy_data)
    read_phasors_data           = staticmethod(_io.read_phasors_data)
    get_bin_filter_file_string  = staticmethod(_io.get_bin_filter_file_string)

    # ---- Utils ------------------------------------------------------------
    get_data_type                                    = staticmethod(_utils.get_data_type)
    show_warning_message                             = staticmethod(_utils.show_warning_message)
    has_laser_period_mismatch                        = staticmethod(_utils.has_laser_period_mismatch)
    get_fitting_active_channels                      = staticmethod(_utils.get_fitting_active_channels)
    are_spectroscopy_and_fitting_from_same_acquisition = staticmethod(
        _utils.are_spectroscopy_and_fitting_from_same_acquisition
    )
    preloaded_fitting_data      = staticmethod(_utils.preloaded_fitting_data)
    _average_channels_for_file  = staticmethod(_utils._average_channels_for_file)
    get_phasors_laser_period_ns = staticmethod(_utils.get_phasors_laser_period_ns)
    get_phasors_frequency_mhz   = staticmethod(_utils.get_phasors_frequency_mhz)
    get_spectroscopy_frequency_mhz = staticmethod(_utils.get_spectroscopy_frequency_mhz)
    get_frequency_mhz           = staticmethod(_utils.get_frequency_mhz)
    get_spectroscopy_file_x_values = staticmethod(_utils.get_spectroscopy_file_x_values)

    # ---- Plot -------------------------------------------------------------
    plot_data                               = staticmethod(_plot.plot_data)
    plot_spectroscopy_data                  = staticmethod(_plot.plot_spectroscopy_data)
    group_phasors_data_without_channels     = staticmethod(_plot.group_phasors_data_without_channels)
    get_spectroscopy_data_to_fit            = staticmethod(_plot.get_spectroscopy_data_to_fit)
    plot_phasors_data                       = staticmethod(_plot.plot_phasors_data)
    save_plot_image                         = staticmethod(_plot.save_plot_image)
    prepare_spectroscopy_data_for_export_img = staticmethod(
        _plot.prepare_spectroscopy_data_for_export_img
    )
    prepare_phasors_data_for_export_img     = staticmethod(
        _plot.prepare_phasors_data_for_export_img
    )
