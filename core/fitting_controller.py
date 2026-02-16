import json
import numpy as np
from utils.fitting_utilities import estimate_irf, fit_decay_curve


class FittingController:

    @staticmethod
    def apply_birfi(curves, tau_ns, laser_period_ns, background=0.0):
        """
        Extract IRF from mono-exponential curves using BIRFI algorithm.

        Parameters
        ----------
        curves : list of lists or arrays
            List of measured fluorescence decay curves (one per channel).
        tau_ns : float
            Known fluorescence lifetime in nanoseconds.
        laser_period_ns : float
            Laser period in nanoseconds (time window).
        background : float, optional
            Background level. Default: 0.0

        Returns
        -------
        irfs : list of lists
            List of extracted IRFs (Python lists).
        """
        try:
            if not curves or not isinstance(curves[0], (list, np.ndarray)):
                return []

            irfs = []
            for channel_idx, curve in enumerate(curves):
                signal = np.array(curve, dtype=np.float64)

                result = estimate_irf(
                    signal=signal,
                    tau_ns=tau_ns,
                    time_window_ns=laser_period_ns,
                    background=background,
                )

                if result["success"]:
                    irf_list = result["irf"].tolist()
                    irfs.append(irf_list)
                else:
                    print(
                        f"Warning: BIRFI failed for channel {channel_idx}, using zeros"
                    )
                    irfs.append([0.0] * len(signal))

            return irfs

        except Exception as e:
            print(f"Error applying BIRFI: {e}")
            return curves

    @staticmethod
    def update_ref_file_with_birfi_results(app, ref_file_path):
        try:
            with open(ref_file_path, "r", encoding="utf-8") as f:
                ref_file = json.load(f)
            if "ref_type" in ref_file and ref_file["ref_type"] == "birfi":
                curves = ref_file.get("curves", [])
                laser_period_ns = ref_file.get("laser_period_ns", 0.0)
                tau_ns = ref_file.get("tau_ns", 0.0)
                background = ref_file.get("background", 0.0)
                # Extract IRFs using BIRFI algorithm
                irfs = FittingController.apply_birfi(
                    curves=curves,
                    tau_ns=tau_ns,
                    laser_period_ns=laser_period_ns,
                    background=background,
                )
                ref_file["irfs"] = irfs
                app.birfi_reference_data = ref_file
                with open(ref_file_path, "w", encoding="utf-8") as f:
                    json.dump(ref_file, f, indent=2)
        except Exception as e:
            print(f"Error updating reference file with BIRFI results: {e}")

    @staticmethod
    def extract_irf_data_from_ref_file(app, ref_file_path):
        try:
            with open(ref_file_path, "r", encoding="utf-8") as f:
                ref_file = json.load(f)
            if "ref_type" in ref_file and ref_file["ref_type"] == "irf":
                app.irf_reference_data = ref_file
            if "ref_type" in ref_file and ref_file["ref_type"] == "birfi":
                app.birfi_reference_data = ref_file
        except Exception as e:
            print(f"Error extracting IRF data from reference file: {e}")
            return []

    @staticmethod
    def deconvolve_signals(app, signals, irfs, laser_period_ns=12.5):
        from utils.fitting_utilities import deconvolve_signal_with_irf_and_alignment

        if (
            app.acquire_read_mode == "read"
            or not app.use_deconvolution
            or not irfs
            or len(irfs) == 0
        ):
            return []

        def create_signal_dict(signal, y_data=None):
            return {
                "y": y_data if y_data is not None else signal["y"],
                "channel_index": signal["channel_index"],
                "x": signal["x"],
                "title": signal["title"],
                "time_shift": signal["time_shift"],
            }

        deconvolved_signals = []
        for channel_idx, signal in enumerate(signals):
            irf = irfs[channel_idx] if channel_idx < len(irfs) else None
            if irf is not None:
                try:
                    deconv_result = deconvolve_signal_with_irf_and_alignment(
                        signal=signal["y"],
                        irf=irf,
                        method="wiener",
                        auto_align_irf=True,
                        time_window_ns=laser_period_ns,
                    )
                    deconvolved_signals.append(
                        create_signal_dict(signal, deconv_result["deconvolved_signal"])
                    )
                except Exception as e:
                    deconvolved_signals.append(create_signal_dict(signal))
            else:
                deconvolved_signals.append(create_signal_dict(signal))
        return deconvolved_signals
