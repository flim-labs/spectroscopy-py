import numpy as np
from scipy.optimize import curve_fit
from utils.helpers import convert_ndarray_to_list, convert_np_num_to_py_num, convert_py_num_to_np_num

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
    return A1 * np.exp(-t / tau1) + A2 * np.exp(-t / tau2) + A3 * np.exp(-t / tau3) + A4 * np.exp(-t / tau4) + B

model_formulas = {  
    decay_model_1_with_B: "A1 * exp(-t / tau1) + B",
    decay_model_2_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + B",
    decay_model_3_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + A3 * exp(-t / tau3) + B",
    decay_model_4_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + A3 * exp(-t / tau3) + A4 * exp(-t / tau4) + B",
}

def fit_decay_curve(x_values, y_values, channel, y_shift=0, tau_similarity_threshold=0.01):
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
    decay_start = np.argmax(y_values)

    # if y_values is all zeros, return an error
    if sum(y_values) == 0:
        return {"error": "All counts are zero."}
      
    # if all y_values are too big try to scale them until reaching a reasonable range (max 10000)  
    scale_factor = np.float64(1)
    if max(y_values) > 1000:
        scale_factor = np.float64(max(y_values) / 1000)
        y_values = [np.float64(y / scale_factor) for y in y_values]

    t_data = x_values[decay_start:]
    y_data = y_values[decay_start:]
    
    # Ensure t_data and y_data have the same length (fix for multi-file with different dimensions)
    min_len = min(len(t_data), len(y_data))
    if len(t_data) != len(y_data):
        t_data = t_data[:min_len]
        y_data = y_data[:min_len]
    
    # Improve initial guesses based on actual data
    y_max = np.max(y_data)
    y_min = np.min(y_data)
    y_background = y_min  # Assume minimum value is background
    y_amplitude = y_max - y_min  # Amplitude above background
    
    # Estimate tau from the decay curve (time to reach 1/e of max)
    target_value = y_background + y_amplitude / np.e
    tau_estimate = 1000  # Default fallback in ns
    for i in range(1, len(y_data)):
        if y_data[i] <= target_value:
            tau_estimate = t_data[i] - t_data[0]
            break
        
    # Use data-driven initial guesses
    decay_models = [
        (decay_model_1_with_B, [y_amplitude, tau_estimate, y_background]),
        (decay_model_2_with_B, [y_amplitude/2, tau_estimate, y_amplitude/2, tau_estimate*2, y_background]),
        (decay_model_3_with_B, [y_amplitude/3, tau_estimate, y_amplitude/3, tau_estimate*2, y_amplitude/3, tau_estimate*3, y_background]),
        (decay_model_4_with_B, [y_amplitude/4, tau_estimate, y_amplitude/4, tau_estimate*2, y_amplitude/4, tau_estimate*3, y_amplitude/4, tau_estimate*4, y_background]),
    ]

    best_chi2 = np.inf
    best_fit = None
    best_model = None
    best_popt = None

    for i, (model, initial_guess) in enumerate(decay_models):
        try:
            popt, pcov = curve_fit(model, t_data, y_data, p0=initial_guess, maxfev=50000)
            fitted_values = model(t_data, *popt)
            
            # Chi-square (χ²) calculation to find best model
            expected_values = fitted_values
            observed_values = np.array(y_data)
            epsilon = 1e-10  
            chi2 = np.sum((observed_values - expected_values)**2 / (expected_values + epsilon))
            reduced_chi2 = chi2 / (len(observed_values) - len(popt))

            if reduced_chi2 < best_chi2:
                best_chi2 = reduced_chi2
                best_fit = fitted_values
                best_model = model
                best_popt = popt

        except RuntimeError as e:
            continue
        except Exception as e:
            continue
    
    if best_fit is None:
        return {"error": "Optimal parameters not found for any model."}

    # Check for τ values similarity
    num_components = (len(best_popt) - 1) // 2
    tau_values = [best_popt[2 * i + 1] for i in range(num_components)]
    tau_are_similar = all(
        abs(tau_values[i] - tau_values[j]) / tau_values[i] < tau_similarity_threshold
        for i in range(len(tau_values))
        for j in range(i + 1, len(tau_values))
    )

    # If τ values are similar use decay_model_1_with_B by default 
    if tau_are_similar:
        model = decay_model_1_with_B
        # Use intelligent initial guess instead of [1, 1, 1]
        initial_guess = [y_amplitude, tau_estimate, y_background]
        popt, pcov = curve_fit(model, t_data, y_data, p0=initial_guess, maxfev=50000)
        best_fit = model(t_data, *popt)
        best_model = model
        best_popt = popt
        # Recalculate num_components after model change
        num_components = (len(best_popt) - 1) // 2

    output_data = {}
    fitted_params_text = 'Fitted parameters:\n'
    
    for i in range(num_components):
        y = i * 2
        SUM = sum(best_popt[even_index] for even_index in range(0, len(best_popt) - 1, 2))
        percentage_tau = best_popt[y] / (SUM + best_popt[-1])
        fitted_params_text += f'τ{i + 1} = {best_popt[y + 1]:.4f} ns, {percentage_tau:.2%} of total\n'
        output_data[f'component_A{i + 1}'] = {'tau_ns': best_popt[y + 1], 'percentage': percentage_tau}
    
    SUM = sum(best_popt[even_index] for even_index in range(0, len(best_popt) - 1, 2))
    percentage_tau = best_popt[-1] / (SUM + best_popt[-1])
    fitted_params_text += f'B = {percentage_tau:.2%} of total\n'
    output_data['component_B'] = best_popt[-1]

    fitted_params_text += f'X² = {best_chi2:.4f}\n'
    fitted_params_text += f'Model = {model_formulas[best_model]}\n'
    
    residuals = np.array(y_data) - best_fit
    SStot = np.sum((y_data - np.mean(y_data))**2)
    SSres = np.sum(residuals**2)
    r2 = 1 - SSres / SStot    
    
    fitted_params_text += f'R² = {r2:.4f}\n'

    return {
        'x_values': x_values,
        't_data': t_data,
        'y_data': y_data,
        'fitted_values': best_fit,
        'residuals': residuals,
        'fitted_params_text': fitted_params_text,
        'output_data': output_data,
        'scale_factor': scale_factor,
        'decay_start': decay_start,
        'channel': channel,
        'chi2': best_chi2,
        'r2': r2,
        'model': model_formulas[best_model]  
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
            'x_values': convert_ndarray_to_list(result.get("x_values")),
            't_data': convert_ndarray_to_list(result.get("t_data")),
            'y_data': convert_ndarray_to_list(result.get("y_data")),
            'fitted_values': convert_ndarray_to_list(result.get("fitted_values")),
            'residuals': convert_ndarray_to_list(result.get("residuals")),
            'fitted_params_text': result.get('fitted_params_text'),
            'output_data': convert_np_num_to_py_num(result.get('output_data')),
            'scale_factor': convert_np_num_to_py_num(result.get('scale_factor')),
            'decay_start': convert_np_num_to_py_num(result.get('decay_start')),
            'channel': result.get('channel'),
            'chi2': convert_np_num_to_py_num(result.get('chi2')),
            'model': result.get('model')
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
            'x_values': np.array(parsed_result.get('x_values')),
            't_data': np.array(parsed_result.get('t_data')),
            'y_data': np.array(parsed_result.get('y_data')),
            'fitted_values': np.array(parsed_result.get('fitted_values')),
            'residuals': np.array(parsed_result.get('residuals')),
            'fitted_params_text': parsed_result.get('fitted_params_text'),
            'output_data': convert_py_num_to_np_num(parsed_result.get('output_data')),
            'scale_factor': np.float64(parsed_result.get('scale_factor')),
            'decay_start': np.int64(parsed_result.get('decay_start')),
            'channel': parsed_result.get('channel'),
            'chi2': np.float64(parsed_result.get('chi2')),
            'model': parsed_result.get('model')
        }
        results.append(result)
    return results