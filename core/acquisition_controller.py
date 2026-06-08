"""
acquisition_controller.py 
=============================================================
Facade / controller that delegates all acquisition logic to the dedicated
sub-modules in `core/acquisition/`.

Sub-module responsibilities
---------------------------
core.acquisition.acquisition_lifecycle  — full start/stop lifecycle, parameter
                                          preparation, hardware calls, UI updates
core.acquisition.acquisition_reference  — reference file validation (IRF, phasors)
core.acquisition.acquisition_data       — real-time data processing, CPS, SBR,
                                          countdown, data-to-fit formatting
"""

from core.acquisition.acquisition_lifecycle import (
    begin_spectroscopy_experiment,
    stop_spectroscopy_experiment,
    check_card_connection,
    _validate_parameters,
    _prepare_spectroscopy_parameters,
    _start_acquisition_process,
    _update_ui_post_start,
    _stop_hardware_and_update_state,
    _finalize_ui_after_stop,
    _handle_reference_file_after_stop,
    _process_phasor_results,
    _handle_post_acquisition_tasks,
)
from core.acquisition.acquisition_reference import (
    _validate_reference_file,
    _validate_irf_reference,
    _validate_phasors_reference,
    _show_error_popup,
    _validate_reference_data,
)
from core.acquisition.acquisition_data import (
    pull_from_queue,
    update_acquisition_countdowns,
    update_SBR,
    update_cps,
    acquired_spectroscopy_data_to_fit,
)


class AcquisitionController:
    """
    Facade controller for the full data acquisition lifecycle.

    Every method is a thin static wrapper that delegates to the appropriate
    `core/acquisition/` sub-module.
    """

    # ------------------------------------------------------------------
    # Main experiment flow
    # ------------------------------------------------------------------

    @staticmethod
    def begin_spectroscopy_experiment(app):
        begin_spectroscopy_experiment(app)

    @staticmethod
    def stop_spectroscopy_experiment(app):
        stop_spectroscopy_experiment(app)

    # ------------------------------------------------------------------
    # Hardware connection
    # ------------------------------------------------------------------

    @staticmethod
    def check_card_connection(app, start_experiment=False):
        check_card_connection(app, start_experiment)

    # ------------------------------------------------------------------
    # Lifecycle helpers (private convention preserved)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_parameters(app):
        return _validate_parameters(app)

    @staticmethod
    def _prepare_spectroscopy_parameters(app, frequency_mhz):
        return _prepare_spectroscopy_parameters(app, frequency_mhz)

    @staticmethod
    def _start_acquisition_process(app, params):
        return _start_acquisition_process(app, params)

    @staticmethod
    def _update_ui_post_start(app):
        _update_ui_post_start(app)

    @staticmethod
    def _stop_hardware_and_update_state(app):
        _stop_hardware_and_update_state(app)

    @staticmethod
    def _finalize_ui_after_stop(app):
        _finalize_ui_after_stop(app)

    @staticmethod
    def _handle_reference_file_after_stop(app):
        _handle_reference_file_after_stop(app)

    @staticmethod
    def _process_phasor_results(app):
        _process_phasor_results(app)

    @staticmethod
    def _handle_post_acquisition_tasks(app):
        _handle_post_acquisition_tasks(app)

    # ------------------------------------------------------------------
    # Reference validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_reference_file(app, frequency_mhz):
        return _validate_reference_file(app, frequency_mhz)

    @staticmethod
    def _validate_irf_reference(app, frequency_mhz):
        return _validate_irf_reference(app, frequency_mhz)

    @staticmethod
    def _validate_phasors_reference(app, frequency_mhz):
        return _validate_phasors_reference(app, frequency_mhz)

    @staticmethod
    def _show_error_popup(title, message):
        return _show_error_popup(title, message)

    @staticmethod
    def _validate_reference_data(ref_file, required_keys):
        return _validate_reference_data(ref_file, required_keys)

    # ------------------------------------------------------------------
    # Real-time data processing
    # ------------------------------------------------------------------

    @staticmethod
    def pull_from_queue(app):
        pull_from_queue(app)

    @staticmethod
    def update_acquisition_countdowns(app, time_ns):
        update_acquisition_countdowns(app, time_ns)

    @staticmethod
    def update_SBR(app, channel_index, curve):
        update_SBR(app, channel_index, curve)

    @staticmethod
    def update_cps(app, channel_index, time_ns, curve):
        update_cps(app, channel_index, time_ns, curve)

    @staticmethod
    def acquired_spectroscopy_data_to_fit(app, read):
        return acquired_spectroscopy_data_to_fit(app, read)