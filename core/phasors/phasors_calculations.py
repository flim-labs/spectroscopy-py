"""
phasors_calculations.py
============================================================
Pure mathematical and data helper functions for phasor analysis.

Provides plain functions covering lifetime calculations
(tau_phi, tau_m, tau_n), mean G/S computation, empty data structure
initialization, and file-index color mapping. These functions have no
UI side effects and are shared across all software variants.
"""

import numpy as np


def get_empty_phasors_points():
    """
    Initializes an empty data structure for storing phasor points.

    Returns:
        list[dict[int, list]]: A list of dictionaries, where each list
                               represents a channel and each dictionary
                               holds empty lists for harmonics 1 through 4.
    """
    empty = []
    for i in range(8):
        empty.append({1: [], 2: [], 3: [], 4: []})
    return empty


def get_color_for_file_index(index):
    """
    Returns a color based on the file index (0, 1, 2, 3...).
    Uses 4 distinct colors cycling through them: red, bright green, orange, yellow.

    Args:
        index (int): The index of the file (0-based).

    Returns:
        str: Hex color code for the file.
    """
    colors = [
        "#FF0000",  # Red
        "#00FF00",  # Bright green
        "#FF8C00",  # Orange
        "#FFFF00",  # Yellow
    ]
    return colors[index % len(colors)]


def calculate_phasors_points_mean(app, channel_index, harmonic):
    """
    Calculates the mean G and S values for a given channel and harmonic.

    Args:
        app: The main application instance.
        channel_index (int): The channel to perform the calculation for.
        harmonic (int): The harmonic number.

    Returns:
        tuple[float | None, float | None]: A tuple containing the mean G and S
                                           values, or (None, None) if no
                                           data is available.
    """
    x = [p[0] for p in app.all_phasors_points[channel_index][harmonic]]
    y = [p[1] for p in app.all_phasors_points[channel_index][harmonic]]
    g_values = np.array(x)
    s_values = np.array(y)
    if (
        g_values.size == 0
        or s_values.size == 0
        or np.all(np.isnan(g_values))
        or np.all(np.isnan(s_values))
    ):
        return None, None
    mean_g = np.nanmean(g_values)
    mean_s = np.nanmean(s_values)
    return mean_g, mean_s


def calculate_tau(g, s, freq_mhz, harmonic):
    """
    Calculates phase (𝜏ϕ), modulation (𝜏m) and 𝜏n lifetimes from G/S coordinates.

    Args:
        g (float): The G coordinate.
        s (float): The S coordinate.
        freq_mhz (float): The laser frequency in MHz.
        harmonic (int): The harmonic number.

    Returns:
        tuple[float | None, float | None, float | None]: A tuple containing (tau_phi, tau_m, tau_n).
                                           Returns (None, None, None) if calculation
                                           is not possible.
    """
    if freq_mhz == 0.0:
        return None, None, None
    tau_phi = (1 / (2 * np.pi * freq_mhz * harmonic)) * (s / g) * 1e3
    tau_m_component = (1 / (s**2 + g**2)) - 1
    if tau_m_component < 0:
        tau_m = None
    else:
        tau_m = (1 / (2 * np.pi * freq_mhz * harmonic)) * np.sqrt(tau_m_component) * 1e3
    tau_n = calculate_tau_n(complex(g, s), freq_mhz * harmonic) * 1e3  # Convert to ns
    return tau_phi, tau_m, tau_n


def calculate_tau_n(r, freq):
    """
    Compute fluorescence lifetime from phasor projection.

    The function projects the phasor point(s) normally onto the
    universal semicircle (the "single-lifetime semicircle"),
    yielding the corresponding fluorescence lifetime.

    Parameters
    ----------
    r : array-like (complex or ndarray of complex)
        Phasor values, where the real part corresponds to the
        cosine component and the imaginary part to the sine component
        of the Fourier transform at the given modulation frequency.
        - r can be a single complex number, a 1D array, or an nD array.
    freq : float, optional
        Modulation frequency (same frequency at which r was calculated).
        Units do not matter (Hz, MHz, etc.), as the lifetime will
        simply be expressed in the inverse unit (s, ns, etc.).

    Returns
    -------
    tau : ndarray of floats
        Estimated fluorescence lifetime(s), with the same shape as `r`.

    Notes
    -----
    - r is dimensionless, but it must have been obtained by Fourier
    transform at the same `freq` you provide here.
    - The projection formula comes from phasor FLIM theory, where
    a single-exponential decay maps onto a semicircle in phasor space.
    - The method ensures that the estimated lifetime corresponds to
    the perpendicular projection from the phasor point to the semicircle.
    """
    shifted = r - 0.5
    phi = np.angle(shifted)
    tau = np.tan(phi / 2) / (2 * np.pi * freq)
    return tau