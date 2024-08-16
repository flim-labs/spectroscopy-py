import numpy as np
from scipy.optimize import curve_fit
from scipy.special import wofz

from components.helpers import convert_ndarray_to_list, convert_np_num_to_py_num


def decay_model_1_with_B(t, A1, tau1, B):
    return A1 * np.exp(-t / tau1) + B

def decay_model_2_with_B(t, A1, tau1, A2, tau2, B):
    return A1 * np.exp(-t / tau1) + A2 * np.exp(-t / tau2) + B

def decay_model_3_with_B(t, A1, tau1, A2, tau2, A3, tau3, B):
    return A1 * np.exp(-t / tau1) + A2 * np.exp(-t / tau2) + A3 * np.exp(-t / tau3) + B

def decay_model_4_with_B(t, A1, tau1, A2, tau2, A3, tau3, A4, tau4, B):
    return A1 * np.exp(-t / tau1) + A2 * np.exp(-t / tau2) + A3 * np.exp(-t / tau3) + A4 * np.exp(-t / tau4) + B

def decay_model_gaussian(t, A, mu, sigma):
    return A * np.exp(-(t - mu)**2 / (2 * sigma**2))

def decay_model_exp_gaussian(t, A, tau, mu, sigma):
    return A * np.exp(-t / tau) * np.exp(-(t - mu)**2 / (2 * sigma**2))

def decay_model_lorentzian(t, A, mu, gamma):
    return A * gamma**2 / ((t - mu)**2 + gamma**2)

def decay_model_lorentzian_gaussian(t, A, mu, gamma, sigma):
    return A * (gamma**2 / ((t - mu)**2 + gamma**2)) * np.exp(-(t - mu)**2 / (2 * sigma**2))

def decay_model_voigt_profile(t, A, mu, sigma, gamma):
    z = ((t - mu) + 1j * gamma) / (sigma * np.sqrt(2))
    return A * np.real(wofz(z))

def decay_model_power_law(t, A, alpha):
    return A * t**(-alpha)


model_formulas = {  
    decay_model_1_with_B: "A1 * exp(-t / tau1) + B",
    decay_model_2_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + B",
    decay_model_3_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + A3 * exp(-t / tau3) + B",
    decay_model_4_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + A3 * exp(-t / tau3) + A4 * exp(-t / tau4) + B",
    decay_model_gaussian: "A * exp(-(t - mu)**2 / (2 * sigma**2))",
    decay_model_exp_gaussian: "A * exp(-t / tau) * exp(-(t - mu)**2 / (2 * sigma**2))",
    decay_model_lorentzian: "A * gamma**2 / ((t - mu)**2 + gamma**2)",
    decay_model_lorentzian_gaussian: "A * (gamma**2 / ((t - mu)**2 + gamma**2)) * exp(-(t - mu)**2 / (2 * sigma**2))",
    decay_model_voigt_profile: "A * real(wofz(((t - mu) + 1j * gamma) / (sigma * sqrt(2))))",
    decay_model_power_law: "A * t**(-alpha)"
}

def fit_decay_curve(x_values, y_values, channel):

    decay_models = [
        (decay_model_1_with_B, [1, 1, 1]),
        (decay_model_2_with_B, [1, 1, 1, 1, 1]),
        (decay_model_3_with_B, [1, 1, 1, 1, 1, 1, 1]),
        (decay_model_4_with_B, [1, 1, 1, 1, 1, 1, 1, 1, 1]),
        (decay_model_gaussian, [1, 0, 1]),
        (decay_model_exp_gaussian, [1, 1, 0, 1]),
        (decay_model_lorentzian, [1, 0, 1]),
        (decay_model_lorentzian_gaussian, [1, 0, 1, 1]),
        (decay_model_voigt_profile, [1, 0, 1, 1]),
        (decay_model_power_law, [1, 1])
    ]

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

    best_r2 = -np.inf
    best_fit = None
    best_model = None
    best_popt = None

    # Calculate best fitting model depending on R² value
    for model, initial_guess in decay_models:
        try:
            popt, pcov = curve_fit(model, t_data, y_data, p0=initial_guess, maxfev=50000)
            fitted_values = model(t_data, *popt)
            residuals = np.array(y_data) - fitted_values
            
            # Calculate R²
            SStot = np.sum((y_data - np.mean(y_data))**2)
            SSres = np.sum(residuals**2)
            r2 = 1 - SSres / SStot

            if r2 > best_r2:
                best_r2 = r2
                best_fit = fitted_values
                best_model = model
                best_popt = popt

        except RuntimeError as e:
            continue
    
    if best_fit is None:
        return {"error": "Optimal parameters not found for any model."}

    output_data = {}
    num_components = (len(best_popt) - 1) // 2

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

    fitted_params_text += f'R² = {best_r2:.4f}\n'
    fitted_params_text += f'Model = {model_formulas[best_model]}\n'

    return {
        'x_values': x_values,
        't_data': t_data,
        'y_data': y_data,
        'fitted_values': best_fit,
        'residuals': np.array(y_data) - best_fit,
        'fitted_params_text': fitted_params_text,
        'output_data': output_data,
        'scale_factor': scale_factor,
        'decay_start': decay_start,
        'channel': channel,
        'r2': best_r2,
        'model': model_formulas[best_model]  
    }


def convert_fitting_result_into_json_serializable_item(results):
    parsed_results = []
    for result in results:
        parsed_result = {
            'x_values': convert_ndarray_to_list(result[1].get("x_values")),
            't_data': convert_ndarray_to_list(result[1].get("t_data")),
            'y_data': convert_ndarray_to_list(result[1].get("y_data")),
            'fitted_values': convert_ndarray_to_list(result[1].get("fitted_values")),
            'residuals': convert_ndarray_to_list(result[1].get("residuals")),
            'fitted_params_text': result[1].get('fitted_params_text'),
            'output_data': convert_np_num_to_py_num(result[1].get('output_data')),
            'scale_factor': convert_np_num_to_py_num(result[1].get('scale_factor')),
            'decay_start': convert_np_num_to_py_num(result[1].get('decay_start')),
            'channel': result[1].get('channel'),
            'r2': convert_np_num_to_py_num(result[1].get('r2')),
            'model': result[1].get('model')
        }
        parsed_results.append(parsed_result)
    return parsed_results
        