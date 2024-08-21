import numpy as np
from scipy.optimize import curve_fit
from components.helpers import convert_ndarray_to_list, convert_np_num_to_py_num, convert_py_num_to_np_num

def decay_model_1_with_B(t, A1, tau1, B):
    return A1 * np.exp(-t / tau1) + B

def decay_model_2_with_B(t, A1, tau1, A2, tau2, B):
    return A1 * np.exp(-t / tau1) + A2 * np.exp(-t / tau2) + B

def decay_model_3_with_B(t, A1, tau1, A2, tau2, A3, tau3, B):
    return A1 * np.exp(-t / tau1) + A2 * np.exp(-t / tau2) + A3 * np.exp(-t / tau3) + B

def decay_model_4_with_B(t, A1, tau1, A2, tau2, A3, tau3, A4, tau4, B):
    return A1 * np.exp(-t / tau1) + A2 * np.exp(-t / tau2) + A3 * np.exp(-t / tau3) + A4 * np.exp(-t / tau4) + B

model_formulas = {  
    decay_model_1_with_B: "A1 * exp(-t / tau1) + B",
    decay_model_2_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + B",
    decay_model_3_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + A3 * exp(-t / tau3) + B",
    decay_model_4_with_B: "A1 * exp(-t / tau1) + A2 * exp(-t / tau2) + A3 * exp(-t / tau3) + A4 * exp(-t / tau4) + B",
}

def fit_decay_curve(x_values, y_values, channel, y_shift=0):
    decay_models = [
        (decay_model_1_with_B, [1, 1, 1]),
        (decay_model_2_with_B, [1, 1, 1, 1, 1]),
        (decay_model_3_with_B, [1, 1, 1, 1, 1, 1, 1]),
        (decay_model_4_with_B, [1, 1, 1, 1, 1, 1, 1, 1, 1]),
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

    best_chi2 = np.inf
    best_fit = None
    best_model = None
    best_popt = None

    for model, initial_guess in decay_models:
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

    fitted_params_text += f'X² = {best_chi2:.4f}\n'
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
        'chi2': best_chi2,
        'model': model_formulas[best_model]  
    }

def convert_fitting_result_into_json_serializable_item(results):
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