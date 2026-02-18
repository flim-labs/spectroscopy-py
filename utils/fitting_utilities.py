import numpy as np
from scipy.optimize import curve_fit
from scipy.optimize import minimize
from scipy.signal import fftconvolve, correlate
from utils.helpers import (
    convert_ndarray_to_list,
    convert_np_num_to_py_num,
    convert_py_num_to_np_num,
)


def decay_model_1_with_B(t, A1, tau1, B):
    """Single-exponential decay model with a constant background.

    Args:
        t (np.ndarray): Time values.
        A1 (float): Amplitude of the first exponential component.
        tau1 (float): Decay time of the first exponential component.
        B (float): Constant background offset.

    Returns:
        np.ndarray: The calculated decay curve.
    """
    return A1 * np.exp(-t / tau1) + B


def decay_model_2_with_B(t, A1, tau1, A2, tau2, B):
    """Double-exponential decay model with a constant background.

    Args:
        t (np.ndarray): Time values.
        A1 (float): Amplitude of the first exponential component.
        tau1 (float): Decay time of the first exponential component.
        A2 (float): Amplitude of the second exponential component.
        tau2 (float): Decay time of the second exponential component.
        B (float): Constant background offset.

    Returns:
        np.ndarray: The calculated decay curve.
    """
    return A1 * np.exp(-t / tau1) + A2 * np.exp(-t / tau2) + B


def decay_model_3_with_B(t, A1, tau1, A2, tau2, A3, tau3, B):
    """Triple-exponential decay model with a constant background.

    Args:
        t (np.ndarray): Time values.
        A1 (float): Amplitude of the first exponential component.
        tau1 (float): Decay time of the first exponential component.
        A2 (float): Amplitude of the second exponential component.
        tau2 (float): Decay time of the second exponential component.
        A3 (float): Amplitude of the third exponential component.
        tau3 (float): Decay time of the third exponential component.
        B (float): Constant background offset.

    Returns:
        np.ndarray: The calculated decay curve.
    """
    return A1 * np.exp(-t / tau1) + A2 * np.exp(-t / tau2) + A3 * np.exp(-t / tau3) + B


def decay_model_4_with_B(t, A1, tau1, A2, tau2, A3, tau3, A4, tau4, B):
    """Quadruple-exponential decay model with a constant background.

    Args:
        t (np.ndarray): Time values.
        A1 (float): Amplitude of the first exponential component.
        tau1 (float): Decay time of the first exponential component.
        A2 (float): Amplitude of the second exponential component.
        tau2 (float): Decay time of the second exponential component.
        A3 (float): Amplitude of the third exponential component.
        tau3 (float): Decay time of the third exponential component.
        A4 (float): Amplitude of the fourth exponential component.
        tau4 (float): Decay time of the fourth exponential component.
        B (float): Constant background offset.

    Returns:
        np.ndarray: The calculated decay curve.
    """
    return (
        A1 * np.exp(-t / tau1)
        + A2 * np.exp(-t / tau2)
        + A3 * np.exp(-t / tau3)
        + A4 * np.exp(-t / tau4)
        + B
    )


model_formulas = {
    decay_model_1_with_B: "A1 * exp(-t / tau1) + B",
    decay_model_2_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + B",
    decay_model_3_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + A3 * exp(-t / tau3) + B",
    decay_model_4_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + A3 * exp(-t / tau3) + A4 * exp(-t / tau4) + B",
}


def _prepare_data(x_values, y_values):
    """Prepare and validate the data for fitting.

    Args:
        x_values (np.ndarray): The x-axis data (time).
        y_values (np.ndarray): The y-axis data (counts).

    Returns:
        dict: Contains prepared data or error message.
    """
    if sum(y_values) == 0:
        return {"error": "All counts are zero."}

    decay_start = np.argmax(y_values)

    # Scale data if needed
    scale_factor = np.float64(1)
    if max(y_values) > 1000:
        scale_factor = np.float64(max(y_values) / 1000)
        y_values = [np.float64(y / scale_factor) for y in y_values]

    t_data = x_values[decay_start:]
    y_data = y_values[decay_start:]

    # Ensure same length
    min_len = min(len(t_data), len(y_data))
    if len(t_data) != len(y_data):
        t_data = t_data[:min_len]
        y_data = y_data[:min_len]

    return {
        "t_data": t_data,
        "y_data": y_data,
        "decay_start": decay_start,
        "scale_factor": scale_factor,
    }


def _estimate_initial_parameters(t_data, y_data):
    """Estimate initial parameters for fitting based on data characteristics.

    Args:
        t_data (np.ndarray): Time data.
        y_data (np.ndarray): Count data.

    Returns:
        tuple: (y_amplitude, tau_estimate, y_background)
    """
    y_max = np.max(y_data)
    y_min = np.min(y_data)
    y_background = y_min
    y_amplitude = y_max - y_min

    # Estimate tau from the decay curve (time to reach 1/e of max)
    target_value = y_background + y_amplitude / np.e
    tau_estimate = 1000  # Default fallback in ns
    for i in range(1, len(y_data)):
        if y_data[i] <= target_value:
            tau_estimate = t_data[i] - t_data[0]
            break

    return y_amplitude, tau_estimate, y_background


def _build_decay_models(y_amplitude, tau_estimate, y_background):
    """Build list of decay models with initial guesses.

    Args:
        y_amplitude (float): Estimated amplitude.
        tau_estimate (float): Estimated tau value.
        y_background (float): Estimated background.

    Returns:
        list: List of (model_function, initial_guess) tuples.
    """
    return [
        (decay_model_1_with_B, [y_amplitude, tau_estimate, y_background]),
        (
            decay_model_2_with_B,
            [
                y_amplitude / 2,
                tau_estimate,
                y_amplitude / 2,
                tau_estimate * 2,
                y_background,
            ],
        ),
        (
            decay_model_3_with_B,
            [
                y_amplitude / 3,
                tau_estimate,
                y_amplitude / 3,
                tau_estimate * 2,
                y_amplitude / 3,
                tau_estimate * 3,
                y_background,
            ],
        ),
        (
            decay_model_4_with_B,
            [
                y_amplitude / 4,
                tau_estimate,
                y_amplitude / 4,
                tau_estimate * 2,
                y_amplitude / 4,
                tau_estimate * 3,
                y_amplitude / 4,
                tau_estimate * 4,
                y_background,
            ],
        ),
    ]


def _find_best_fit(decay_models, t_data, y_data):
    """Try all decay models and find the best fit based on chi-square.

    Args:
        decay_models (list): List of (model, initial_guess) tuples.
        t_data (np.ndarray): Time data.
        y_data (np.ndarray): Count data.

    Returns:
        tuple: (best_fit, best_model, best_popt, best_chi2) or (None, None, None, None)
    """
    best_chi2 = np.inf
    best_fit = None
    best_model = None
    best_popt = None

    for model, initial_guess in decay_models:
        try:
            popt, pcov = curve_fit(
                model, t_data, y_data, p0=initial_guess, maxfev=50000
            )
            fitted_values = model(t_data, *popt)

            # Chi-square calculation
            epsilon = 1e-10
            chi2 = np.sum(
                (np.array(y_data) - fitted_values) ** 2 / (fitted_values + epsilon)
            )
            reduced_chi2 = chi2 / (len(y_data) - len(popt))

            if reduced_chi2 < best_chi2:
                best_chi2 = reduced_chi2
                best_fit = fitted_values
                best_model = model
                best_popt = popt
        except:
            continue

    return best_fit, best_model, best_popt, best_chi2


def _identify_redundant_components(best_popt, tau_similarity_threshold):
    """Identify groups of similar tau values to detect redundant components.

    Args:
        best_popt (np.ndarray): Fitted parameters.
        tau_similarity_threshold (float): Threshold for tau similarity.

    Returns:
        tuple: (has_redundant_components, unique_components)
    """
    num_components = (len(best_popt) - 1) // 2
    tau_values = [best_popt[2 * i + 1] for i in range(num_components)]

    similar_groups = []
    used_indices = set()

    for i in range(len(tau_values)):
        if i in used_indices:
            continue

        group = [i]
        for j in range(i + 1, len(tau_values)):
            if j in used_indices:
                continue

            denominator = max(abs(tau_values[i]), abs(tau_values[j]), 1e-10)
            relative_diff = abs(tau_values[i] - tau_values[j]) / denominator

            if relative_diff < tau_similarity_threshold:
                group.append(j)
                used_indices.add(j)

        similar_groups.append(group)
        used_indices.add(i)

    has_redundant_components = any(len(group) > 1 for group in similar_groups)
    unique_components = len(similar_groups)

    return has_redundant_components, unique_components


def _refit_with_simplified_model(
    unique_components, t_data, y_data, y_amplitude, tau_estimate, y_background
):
    """Refit the data with a simplified model based on unique components.

    Args:
        unique_components (int): Number of unique components.
        t_data (np.ndarray): Time data.
        y_data (np.ndarray): Count data.
        y_amplitude (float): Estimated amplitude.
        tau_estimate (float): Estimated tau.
        y_background (float): Estimated background.

    Returns:
        tuple: (model, best_fit, best_popt, best_chi2) or None if refit fails.
    """
    model_map = {
        1: (decay_model_1_with_B, [y_amplitude, tau_estimate, y_background]),
        2: (
            decay_model_2_with_B,
            [
                y_amplitude / 2,
                tau_estimate,
                y_amplitude / 2,
                tau_estimate * 2,
                y_background,
            ],
        ),
        3: (
            decay_model_3_with_B,
            [
                y_amplitude / 3,
                tau_estimate,
                y_amplitude / 3,
                tau_estimate * 2,
                y_amplitude / 3,
                tau_estimate * 3,
                y_background,
            ],
        ),
    }

    if unique_components not in model_map:
        return None

    model, initial_guess = model_map[unique_components]

    try:
        popt, pcov = curve_fit(model, t_data, y_data, p0=initial_guess, maxfev=50000)
        best_fit = model(t_data, *popt)

        epsilon = 1e-10
        best_chi2 = np.sum(
            (np.array(y_data) - best_fit) ** 2 / (best_fit + epsilon)
        ) / (len(y_data) - len(popt))

        return model, best_fit, popt, best_chi2
    except:
        return None


def _generate_output_data(best_popt, best_chi2, best_model, y_data, best_fit):
    """Generate the output data dictionary with fitting results.

    Args:
        best_popt (np.ndarray): Fitted parameters.
        best_chi2 (float): Chi-square value.
        best_model (function): The fitted model.
        y_data (np.ndarray): Original y data.
        best_fit (np.ndarray): Fitted values.

    Returns:
        tuple: (output_data, fitted_params_text, r2)
    """
    num_components = (len(best_popt) - 1) // 2
    output_data = {}
    fitted_params_text = "Fitted parameters:\n"

    for i in range(num_components):
        y = i * 2
        SUM = sum(
            best_popt[even_index] for even_index in range(0, len(best_popt) - 1, 2)
        )
        percentage_tau = best_popt[y] / (SUM + best_popt[-1])
        fitted_params_text += (
            f"τ{i + 1} = {best_popt[y + 1]:.4f} ns, {percentage_tau:.2%} of total\n"
        )
        output_data[f"component_A{i + 1}"] = {
            "tau_ns": best_popt[y + 1],
            "percentage": percentage_tau,
        }

    SUM = sum(best_popt[even_index] for even_index in range(0, len(best_popt) - 1, 2))
    percentage_tau = best_popt[-1] / (SUM + best_popt[-1])
    fitted_params_text += f"B = {percentage_tau:.2%} of total\n"
    output_data["component_B"] = best_popt[-1]

    fitted_params_text += f"X² = {best_chi2:.4f}\n"
    fitted_params_text += f"Model = {model_formulas[best_model]}\n"

    residuals = np.array(y_data) - best_fit
    SStot = np.sum((y_data - np.mean(y_data)) ** 2)
    SSres = np.sum(residuals**2)
    r2 = 1 - SSres / SStot

    fitted_params_text += f"R² = {r2:.4f}\n"

    return output_data, fitted_params_text, r2, residuals


def fit_decay_curve(
    x_values,
    y_values,
    channel,
    y_shift=0,
    tau_similarity_threshold=0.01,
):
    """Fits a decay curve to the provided data using multiple exponential models.

    It automatically selects the best model (from 1 to 4 exponential components)
    based on the reduced chi-square value. It also handles data scaling and
    identifies the start of the decay.

    Supports optional IRF deconvolution:
    - If use_deconvolution=True and irf is provided, signal is deconvolved before fitting
    - Automatic time shift correction between IRF and signal

    Args:
        x_values (np.ndarray): The x-axis data (time).
        y_values (np.ndarray): The y-axis data (counts).
        channel (int): The channel index associated with this data.
        y_shift (int, optional): A vertical shift to apply to the data. Defaults to 0.
        tau_similarity_threshold (float, optional): The threshold for considering
            decay times (tau) as similar. Defaults to 0.01.

    Returns:
        dict: A dictionary containing the fitting results, including the fitted
              parameters, R-squared, chi-squared, residuals, and the model used.
              Returns a dictionary with an 'error' key if fitting fails.
    """
    # Prepare data
    prep_result = _prepare_data(x_values, y_values)
    if "error" in prep_result:
        return prep_result

    t_data = prep_result["t_data"]
    y_data = prep_result["y_data"]
    decay_start = prep_result["decay_start"]
    scale_factor = prep_result["scale_factor"]

    # Estimate initial parameters
    y_amplitude, tau_estimate, y_background = _estimate_initial_parameters(
        t_data, y_data
    )

    # Build decay models with initial guesses
    decay_models = _build_decay_models(y_amplitude, tau_estimate, y_background)

    # Find best fit among all models
    best_fit, best_model, best_popt, best_chi2 = _find_best_fit(
        decay_models, t_data, y_data
    )

    if best_fit is None:
        return {"error": "Optimal parameters not found for any model."}

    # Identify redundant components
    has_redundant_components, unique_components = _identify_redundant_components(
        best_popt, tau_similarity_threshold
    )

    num_components = (len(best_popt) - 1) // 2

    # Refit with simplified model if redundant components detected
    if has_redundant_components and unique_components < num_components:
        refit_result = _refit_with_simplified_model(
            unique_components, t_data, y_data, y_amplitude, tau_estimate, y_background
        )
        if refit_result is not None:
            best_model, best_fit, best_popt, best_chi2 = refit_result

    # Generate output data
    output_data, fitted_params_text, r2, residuals = _generate_output_data(
        best_popt, best_chi2, best_model, y_data, best_fit
    )

    result = {
        "x_values": x_values,
        "t_data": t_data,
        "y_data": y_data,
        "fitted_values": best_fit,
        "residuals": residuals,
        "fitted_params_text": fitted_params_text,
        "output_data": output_data,
        "scale_factor": scale_factor,
        "decay_start": decay_start,
        "channel": channel,
        "chi2": best_chi2,
        "r2": r2,
        "model": model_formulas[best_model],
    }

    return result


def convert_fitting_result_into_json_serializable_item(
    results,
    raw_signals=[],
    use_deconvolution=False,
    irfs=[],
    laser_period_ns=None,
    irf_tau_ns=None,
):
    """Converts a list of fitting result dictionaries into a JSON-serializable format.

    This involves converting NumPy arrays and numbers to standard Python lists and numbers.

    Args:
        results (list): A list of fitting result dictionaries from fit_decay_curve.

    Returns:
        list: A list of JSON-serializable dictionaries.
    """
    parsed_results = []
    for index, result in enumerate(results):
        parsed_result = {
            "x_values": convert_ndarray_to_list(result.get("x_values")),
            "t_data": convert_ndarray_to_list(result.get("t_data")),
            "y_data": convert_ndarray_to_list(result.get("y_data")),
            "fitted_values": convert_ndarray_to_list(result.get("fitted_values")),
            "residuals": convert_ndarray_to_list(result.get("residuals")),
            "fitted_params_text": result.get("fitted_params_text"),
            "output_data": convert_np_num_to_py_num(result.get("output_data")),
            "scale_factor": convert_np_num_to_py_num(result.get("scale_factor")),
            "decay_start": convert_np_num_to_py_num(result.get("decay_start")),
            "channel": result.get("channel"),
            "chi2": convert_np_num_to_py_num(result.get("chi2")),
            "r2": convert_np_num_to_py_num(result.get("r2")),
            "model": result.get("model"),
            "use_deconvolution": use_deconvolution,
        }
        if use_deconvolution:
            parsed_result["raw_signal"] = (
                convert_ndarray_to_list(raw_signals[index]["y"])
                if raw_signals and index < len(raw_signals) and raw_signals[index] is not None
                else None
            )
            parsed_result["irf_reference"] = (
                convert_ndarray_to_list(irfs[index]) if irfs and index < len(irfs) and irfs[index] is not None else None
            )
            parsed_result["irf_tau_ns"] = (
                convert_np_num_to_py_num(irf_tau_ns) if irf_tau_ns is not None else None
            )
            parsed_result["laser_period_ns"] = (
                convert_np_num_to_py_num(laser_period_ns)
                if laser_period_ns is not None
                else None   
            )
        parsed_results.append(parsed_result)
    return parsed_results


def convert_json_serializable_item_into_np_fitting_result(parsed_results):
    """Converts a list of JSON-serializable fitting results back into the standard format with NumPy objects.

    Args:
        parsed_results (list): A list of JSON-serializable fitting result dictionaries.

    Returns:
        list: A list of fitting result dictionaries with NumPy arrays and numbers.
    """
    results = []
    for parsed_result in parsed_results:
        # Skip results where all critical fields are None (invalid/placeholder results)
        if parsed_result.get("channel") is None or parsed_result.get("decay_start") is None:
            continue
            
        result = {
            "x_values": np.array(parsed_result.get("x_values")) if parsed_result.get("x_values") is not None else None,
            "t_data": np.array(parsed_result.get("t_data")) if parsed_result.get("t_data") is not None else None,
            "y_data": np.array(parsed_result.get("y_data")) if parsed_result.get("y_data") is not None else None,
            "fitted_values": np.array(parsed_result.get("fitted_values")) if parsed_result.get("fitted_values") is not None else None,
            "residuals": np.array(parsed_result.get("residuals")) if parsed_result.get("residuals") is not None else None,
            "fitted_params_text": parsed_result.get("fitted_params_text"),
            "output_data": convert_py_num_to_np_num(parsed_result.get("output_data")) if parsed_result.get("output_data") is not None else None,
            "scale_factor": np.float64(parsed_result.get("scale_factor")) if parsed_result.get("scale_factor") is not None else None,
            "decay_start": np.int64(parsed_result.get("decay_start")),
            "channel": parsed_result.get("channel"),
            "chi2": np.float64(parsed_result.get("chi2")) if parsed_result.get("chi2") is not None else None,
            "r2": np.float64(parsed_result.get("r2")) if parsed_result.get("r2") is not None else None,
            "model": parsed_result.get("model"),
        }
        results.append(result)
    return results


def estimate_time_shift_between_irf_and_signal(signal, irf, max_shift_fraction=0.3):
    """
    Estimate the temporal shift between IRF and signal using cross-correlation.

    This function detects time offset between IRF reference and measured signal,
    which can occur due to:
    - Electronic drift
    - Laser trigger instability
    - Changes in optical path length
    - Temperature variations

    Parameters
    ----------
    signal : np.array or list
        Measured TCSPC signal (256 bins)
    irf : np.array or list
        Instrument Response Function (256 bins)
    max_shift_fraction : float, optional
        Maximum allowed shift as fraction of signal length.
        Default: 0.3 (30% of window)

    Returns
    -------
    result : dict
        Dictionary containing:
        - 'shift_bins': Shift in bins (positive = signal delayed vs IRF)
        - 'shift_ns': Shift in nanoseconds (requires dt to convert)
        - 'correlation': Cross-correlation coefficient at optimal shift
        - 'needs_correction': True if shift is significant (> 1 bin)
    """
    signal = np.array(signal, dtype=np.float64)
    irf = np.array(irf, dtype=np.float64)

    # Ensure same length
    if len(signal) != len(irf):
        min_len = min(len(signal), len(irf))
        signal = signal[:min_len]
        irf = irf[:min_len]

    # Normalize signals for correlation
    signal_norm = signal / (signal.sum() + 1e-10)
    irf_norm = irf / (irf.sum() + 1e-10)

    # Compute cross-correlation
    # Mode 'same' ensures output has same length as input
    correlation = correlate(signal_norm, irf_norm, mode="same", method="auto")

    # Find peak of correlation (optimal shift)
    center = len(correlation) // 2
    max_shift_bins = int(len(signal) * max_shift_fraction)

    # Search for peak in allowed range
    search_start = max(0, center - max_shift_bins)
    search_end = min(len(correlation), center + max_shift_bins)
    search_region = correlation[search_start:search_end]

    peak_idx_in_region = np.argmax(search_region)
    peak_idx = search_start + peak_idx_in_region

    # Calculate shift in bins (positive = signal delayed vs IRF)
    shift_bins = peak_idx - center

    # Get correlation value at peak
    correlation_value = correlation[peak_idx]

    # Determine if correction is needed (threshold: 1 bin)
    needs_correction = abs(shift_bins) > 1

    return {
        "shift_bins": shift_bins,
        "correlation": correlation_value,
        "needs_correction": needs_correction,
    }


def apply_time_shift_to_signal(signal, shift_bins):
    """
    Apply temporal shift to a signal by rolling the array.

    Positive shift moves signal to the right (delays it).
    Negative shift moves signal to the left (advances it).

    Parameters
    ----------
    signal : np.array
        Signal to shift
    shift_bins : int
        Number of bins to shift (positive = delay, negative = advance)

    Returns
    -------
    shifted_signal : np.array
        Time-shifted signal
    """
    signal = np.array(signal, dtype=np.float64)

    if shift_bins == 0:
        return signal

    # Use numpy roll for circular shift
    # Negative sign because we want to align signal TO irf
    # If signal is delayed (+shift), we need to advance it (-roll)
    shifted = np.roll(signal, -shift_bins)

    return shifted


def deconvolve_signal_with_irf_and_alignment(
    signal,
    irf,
    method="wiener",
    noise_power=None,
    reg_param=0.1,
    auto_align_irf=True,
    time_window_ns=12.5,
):
    """
    Deconvolve a TCSPC signal with IRF, with optional automatic time shift correction.

    This is a standalone function to be called BEFORE fitting, allowing you to:
    1. Detect and correct temporal shift between IRF and signal
    2. Deconvolve the aligned signal
    3. Display the deconvolved signal before fitting

    Parameters
    ----------
    signal : np.array or list
        Measured TCSPC signal (256 bins)
    irf : np.array or list
        Instrument Response Function (256 bins)
    method : str, optional
        Deconvolution method:
        - 'wiener': Frequency-dependent Wiener filter (recommended, robust to noise)
        - 'tikhonov': Tikhonov regularization (standard formulation)
        Default: 'wiener'
    noise_power : float, optional
        Noise variance for Wiener filter. If None, auto-estimated using MAD.
        Only used for 'wiener' method.
    reg_param : float, optional
        Regularization parameter for Tikhonov deconvolution (λ²).
        Higher values = more smoothing, less noise amplification.
        Default: 0.1
    auto_align_irf : bool, optional
        If True, automatically detect and correct temporal shift between IRF and signal.
        Default: True
    time_window_ns : float, optional
        Total time window in nanoseconds (used to convert shift from bins to ns).
        Default: 12.5 ns

    Returns
    -------
    result : dict
        Dictionary containing:
        - 'deconvolved_signal': np.array - Deconvolved signal (same length as input)
        - 'irf_shift_bins': int - Detected shift in bins (0 if no shift or auto_align_irf=False)
        - 'irf_shift_ns': float - Detected shift in nanoseconds
        - 'irf_shift_corrected': bool - Whether shift correction was applied
        - 'correlation': float - Cross-correlation value at optimal shift
    """
    signal = np.array(signal, dtype=np.float64)
    irf = np.array(irf, dtype=np.float64)

    # Initialize shift info
    shift_info = {
        "irf_shift_bins": 0,
        "irf_shift_ns": 0.0,
        "irf_shift_corrected": False,
        "correlation": 0.0,
    }

    # Step 1: Estimate and correct temporal shift if requested
    if auto_align_irf:
        shift_result = estimate_time_shift_between_irf_and_signal(signal, irf)
        shift_bins = shift_result["shift_bins"]

        if shift_result["needs_correction"]:
            # Apply shift correction to signal (align signal to IRF)
            signal = apply_time_shift_to_signal(signal, shift_bins)

            # Calculate shift in nanoseconds
            dt = time_window_ns / len(signal)
            shift_ns = shift_bins * dt

            # Store shift information
            shift_info = {
                "irf_shift_bins": shift_bins,
                "irf_shift_ns": shift_ns,
                "irf_shift_corrected": True,
                "correlation": shift_result["correlation"],
            }
        else:
            # No significant shift detected
            shift_info = {
                "irf_shift_bins": shift_bins,
                "irf_shift_ns": 0.0,
                "irf_shift_corrected": False,
                "correlation": shift_result["correlation"],
            }

    # Step 2: Deconvolve the (possibly aligned) signal
    deconvolved = _deconvolve_signal_with_irf_internal(
        signal, irf, method=method, noise_power=noise_power, reg_param=reg_param
    )

    # Return deconvolved signal + shift info
    return {"deconvolved_signal": deconvolved, **shift_info}


def _estimate_background(signal):
    """
    Estimate background level from pre-peak region.
    
    Uses median of first 10% of signal to robustly estimate background.
    
    Parameters
    ----------
    signal : np.array
        TCSPC signal
        
    Returns
    -------
    background : float
        Estimated background level
    """
    pre_peak_region = signal[:max(1, len(signal) // 10)]
    return np.median(pre_peak_region) if len(pre_peak_region) > 0 else 0.0


def _estimate_noise_mad(signal):
    """
    Estimate noise standard deviation using Median Absolute Deviation (MAD).
    
    MAD is robust to outliers and provides better noise estimation than variance
    when signal has sharp features.
    
    Parameters
    ----------
    signal : np.array
        TCSPC signal
        
    Returns
    -------
    noise_std : float
        Estimated noise standard deviation
    """
    # Use tail region (last 30%) for noise estimation
    tail = signal[int(len(signal) * 0.7):]
    if len(tail) < 2:
        return signal.max() * 0.01
    
    # MAD = median(|x - median(x)|)
    # σ ≈ 1.4826 * MAD for Gaussian noise
    median = np.median(tail)
    mad = np.median(np.abs(tail - median))
    noise_std = 1.4826 * mad
    
    # Fallback to variance if MAD is too small
    if noise_std < 1e-10:
        noise_std = np.sqrt(np.var(tail)) if np.var(tail) > 0 else signal.max() * 0.01
    
    return noise_std


def _wiener_deconvolution_improved(signal, irf, noise_std=None):
    """
    Wiener deconvolution with frequency-dependent SNR.
    
    Improved version using proper Signal-to-Noise Ratio calculation
    for each frequency component.
    
    Parameters
    ----------
    signal : np.array
        Background-subtracted signal
    irf : np.array
        Normalized IRF
    noise_std : float, optional
        Noise standard deviation (estimated if None)
        
    Returns
    -------
    deconvolved : np.array
        Deconvolved signal
    """
    if noise_std is None:
        noise_std = _estimate_noise_mad(signal)
    
    # Fourier transforms
    signal_fft = np.fft.fft(signal)
    irf_fft = np.fft.fft(irf)
    
    # Frequency-dependent SNR: SNR(f) = |Signal(f)|² / noise_power
    signal_power = np.abs(signal_fft) ** 2
    noise_power = noise_std ** 2 * len(signal)
    
    # Wiener filter: H = conj(IRF) * SNR / (|IRF|² * SNR + 1)
    # Equivalent to: H = conj(IRF) / (|IRF|² + 1/SNR)
    irf_power = np.abs(irf_fft) ** 2
    irf_conj = np.conj(irf_fft)
    
    # SNR per frequency (avoid division by zero)
    snr = signal_power / (noise_power + 1e-10)
    
    # Wiener filter with frequency-dependent regularization
    wiener_filter = (irf_conj * snr) / (irf_power * snr + 1.0)
    
    # Apply filter
    deconv_fft = signal_fft * wiener_filter
    deconvolved = np.real(np.fft.ifft(deconv_fft))
    
    return deconvolved


def _tikhonov_deconvolution(signal, irf, reg_param=0.1):
    """
    Tikhonov regularized deconvolution (standard formulation).
    
    Solves: H = conj(IRF) / (|IRF|² + reg_param²)
    
    Parameters
    ----------
    signal : np.array
        Background-subtracted signal
    irf : np.array
        Normalized IRF
    reg_param : float
        Regularization parameter (higher = more smoothing)
        
    Returns
    -------
    deconvolved : np.array
        Deconvolved signal
    """
    # Fourier transforms
    signal_fft = np.fft.fft(signal)
    irf_fft = np.fft.fft(irf)
    
    # Tikhonov regularization (standard formulation)
    irf_power = np.abs(irf_fft) ** 2
    irf_conj = np.conj(irf_fft)
    
    # Regularized inverse filter
    tikhonov_filter = irf_conj / (irf_power + reg_param ** 2)
    
    # Apply filter
    deconv_fft = signal_fft * tikhonov_filter
    deconvolved = np.real(np.fft.ifft(deconv_fft))
    
    return deconvolved



def _deconvolve_signal_with_irf_internal(
    signal, irf, method="wiener", noise_power=None, reg_param=0.1
):
    """
    Internal deconvolution with automatic background removal and quality metrics.
    
    Improved version with:
    - Automatic background subtraction
    - Robust noise estimation (MAD)
    - Frequency-dependent Wiener filter
    - Standard Tikhonov regularization
    - Quality metrics computation
    
    Parameters
    ----------
    signal : np.array
        Measured TCSPC signal (256 bins)
    irf : np.array
        Instrument Response Function (256 bins)
    method : str, optional
        Deconvolution method:
        - 'wiener': Frequency-dependent Wiener filter (recommended)
        - 'tikhonov': Tikhonov regularization
        Default: 'wiener'
    noise_power : float, optional
        Noise variance (auto-estimated if None)
    reg_param : float, optional
        Regularization parameter for Tikhonov (default: 0.1)
        
    Returns
    -------
    deconvolved : np.array
        Deconvolved signal (non-negative)
    """
    signal = np.array(signal, dtype=np.float64)
    irf = np.array(irf, dtype=np.float64)
    
    # Ensure same length
    if len(signal) != len(irf):
        min_len = min(len(signal), len(irf))
        signal = signal[:min_len]
        irf = irf[:min_len]
    
    # Step 1: Estimate and remove background
    background = _estimate_background(signal)
    signal_clean = signal - background
    signal_clean = np.maximum(signal_clean, 0)  # Ensure non-negative
    
    # Step 2: Normalize IRF (preserve photon count information)
    irf_norm = irf / (irf.sum() + 1e-10)
    
    # Step 3: Deconvolve with selected method
    if method == "wiener":
        # Convert noise_power to noise_std if provided
        noise_std = np.sqrt(noise_power) if noise_power is not None else None
        deconvolved = _wiener_deconvolution_improved(signal_clean, irf_norm, noise_std)
        
    elif method == "tikhonov":
        deconvolved = _tikhonov_deconvolution(signal_clean, irf_norm, reg_param)
        
    else:
        raise ValueError(f"Unknown method '{method}'. Use 'wiener' or 'tikhonov'.")
    
    # Step 4: Apply physical constraints
    deconvolved = np.maximum(deconvolved, 0)  # Non-negative photon counts
    
    return deconvolved


def estimate_irf(signal, tau_ns, time_window_ns=12.5, background=0.0):
    """
    Estimate IRF from mono-exponential signal using BIRFI algorithm.
    
    BIRFI (Blind IRF Inference) extracts the Instrument Response Function
    from a measured fluorescence decay with known lifetime, without requiring
    a direct IRF measurement (scatter/Ludox).
    
    This function uses L-BFGS-B optimization with Tikhonov regularization
    to extract a parametric IRF (Gaussian shape) that is physically realistic.
    
    The IRF is modeled as a Gaussian:
        IRF(t) = exp(-((t - t0)² / (2 * σ²)))
        
    where t0 is the peak position and σ controls the width.
    
    The optimization minimizes:
        Loss = ||signal - (A * IRF ⊗ decay + bg)||² + λ(σ - σ_target)²

    Parameters
    ----------
    signal : np.array (N,)
        Observed fluorescence decay histogram from TCSPC measurement.
        Typically 256 bins.
    tau_ns : float
        Known fluorescence lifetime in nanoseconds.
        Example: Rhodamine B in water ≈ 1.7 ns, Coumarin 6 ≈ 2.5 ns
    time_window_ns : float, optional
        Total time window in nanoseconds (laser period).
        Default: 12.5 ns
    background : float, optional
        Constant background level (dark counts, ambient light).
        Default: 0.0

    Returns
    -------
    result : dict
        Dictionary containing:
        - 'irf': Estimated IRF, shape (N,)
        - 'amplitude': Fitted amplitude scaling factor
        - 't_peak': IRF peak position in nanoseconds
        - 'sigma': IRF standard deviation in nanoseconds
        - 'fwhm': IRF FWHM in nanoseconds (= 2.355 * sigma)
        - 'background': Background level (input parameter)
        - 'success': True if optimization converged
        - 'shift_applied': Number of bins shifted (circular shift correction)
        
    Notes
    -----
    - Uses parametric Gaussian IRF (only 3 parameters: amplitude, t_peak, sigma)
    - Tikhonov regularization favors realistic IRF widths (~200-500 ps FWHM)
    - Automatic detection and correction of temporal offset (circular shift)
    - For non-Gaussian IRFs, this may introduce systematic errors
    """
    signal = np.array(signal, dtype=np.float64)
    n_points = len(signal)

    # Time axis in nanoseconds
    dt = time_window_ns / n_points
    t = np.arange(n_points) * dt
    
    # -------------------------------------------------------------------------
    # Step 1: Detect and correct temporal offset (circular shift)
    # -------------------------------------------------------------------------
    # If peak is in the second half of the window, apply circular shift
    # to bring it to the beginning (typical for TCSPC data with timing offset)
    peak_bin = np.argmax(signal)
    
    if peak_bin > n_points // 2:
        shift_amount = n_points - peak_bin
        signal = np.roll(signal, shift_amount)
        shift_applied = shift_amount
    else:
        shift_applied = 0

    # -------------------------------------------------------------------------
    # Step 2: Setup BIRFI optimization
    # -------------------------------------------------------------------------
    # Mono-exponential decay model
    decay = np.exp(-t / tau_ns)

    # Initial guess for parametric IRF: [amplitude, t_peak, sigma]
    # IRF should appear in first ~10% of time window
    amplitude_guess = signal.max()
    t_peak_guess = time_window_ns * 0.08  # 8% of window (~1 ns for 12.5 ns)
    sigma_guess = 0.15  # ~150 ps sigma -> ~350 ps FWHM (realistic for TCSPC)
    
    params_guess = np.array([amplitude_guess, t_peak_guess, sigma_guess])

    def loss(params):
        """
        Loss function for parametric IRF fitting with Tikhonov regularization.
        """
        amplitude, t_peak, sigma = params

        # Construct Gaussian IRF
        irf = np.exp(-((t - t_peak) ** 2) / (2 * sigma**2))
        irf /= irf.sum()  # Normalize

        # Forward model: convolve IRF with decay
        conv = fftconvolve(irf, decay, mode="same")
        model = amplitude * conv + background

        # Data fidelity: chi-square (least squares)
        chi2 = np.sum((signal - model) ** 2)
        
        # Regularization: penalize very wide IRFs (favor narrow, realistic IRFs)
        # Typical TCSPC IRF: FWHM = 200-500 ps, sigma = 85-212 ps
        target_sigma = 0.15  # ns (target ~350 ps FWHM)
        lambda_reg = 1e8  # Regularization strength
        reg_term = lambda_reg * (sigma - target_sigma)**2

        return chi2 + reg_term

    # Bounds: amplitude > 0, t_peak in [0, time_window/5], sigma constrained to realistic values
    bounds = [
        (0.01, signal.max() * 10),              # amplitude
        (0, time_window_ns * 0.2),              # t_peak (first 20% of window, ~0-2.5 ns)
        (0.05, 0.4)                             # sigma: 50-400 ps -> FWHM 118-940 ps (realistic range)
    ]

    # Run L-BFGS-B optimization with loose tolerance for speed
    opt_result = minimize(
        loss,
        params_guess,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 500, "ftol": 1e-6},
    )

    # Extract results
    amplitude, t_peak, sigma = opt_result.x

    # Reconstruct IRF from fitted parameters
    irf = np.exp(-((t - t_peak) ** 2) / (2 * sigma**2))
    irf /= irf.sum()

    # Compute FWHM
    fwhm = 2.355 * sigma  # Conversion from sigma to FWHM for Gaussian

    return {
        "irf": irf,
        "amplitude": amplitude,
        "t_peak": t_peak,
        "sigma": sigma,
        "fwhm": fwhm,
        "background": background,
        "success": opt_result.success,
        "shift_applied": shift_applied,
    }
