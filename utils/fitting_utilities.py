import numpy as np
from scipy.optimize import curve_fit
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
        "scale_factor": scale_factor
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


def _refit_with_simplified_model(unique_components, t_data, y_data, y_amplitude, tau_estimate, y_background):
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
        2: (decay_model_2_with_B, [y_amplitude / 2, tau_estimate, y_amplitude / 2, tau_estimate * 2, y_background]),
        3: (decay_model_3_with_B, [y_amplitude / 3, tau_estimate, y_amplitude / 3, tau_estimate * 2, y_amplitude / 3, tau_estimate * 3, y_background]),
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
    x_values, y_values, channel, y_shift=0, tau_similarity_threshold=0.01
):
    """Fits a decay curve to the provided data using multiple exponential models.

    It automatically selects the best model (from 1 to 4 exponential components)
    based on the reduced chi-square value. It also handles data scaling and
    identifies the start of the decay.

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
    y_amplitude, tau_estimate, y_background = _estimate_initial_parameters(t_data, y_data)

    # Build decay models with initial guesses
    decay_models = _build_decay_models(y_amplitude, tau_estimate, y_background)
    
    # Find best fit among all models
    best_fit, best_model, best_popt, best_chi2 = _find_best_fit(decay_models, t_data, y_data)
    
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

    return {
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


def convert_fitting_result_into_json_serializable_item(results):
    """Converts a list of fitting result dictionaries into a JSON-serializable format.

    This involves converting NumPy arrays and numbers to standard Python lists and numbers.

    Args:
        results (list): A list of fitting result dictionaries from fit_decay_curve.

    Returns:
        list: A list of JSON-serializable dictionaries.
    """
    parsed_results = []
    for result in results:
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
            "model": result.get("model"),
        }
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
        result = {
            "x_values": np.array(parsed_result.get("x_values")),
            "t_data": np.array(parsed_result.get("t_data")),
            "y_data": np.array(parsed_result.get("y_data")),
            "fitted_values": np.array(parsed_result.get("fitted_values")),
            "residuals": np.array(parsed_result.get("residuals")),
            "fitted_params_text": parsed_result.get("fitted_params_text"),
            "output_data": convert_py_num_to_np_num(parsed_result.get("output_data")),
            "scale_factor": np.float64(parsed_result.get("scale_factor")),
            "decay_start": np.int64(parsed_result.get("decay_start")),
            "channel": parsed_result.get("channel"),
            "chi2": np.float64(parsed_result.get("chi2")),
            "model": parsed_result.get("model"),
        }
        results.append(result)
    return results
