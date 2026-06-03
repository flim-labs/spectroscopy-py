"""
components/fitting/__init__.py
===============================
Public API for the components/fitting package.

Re-exports the main class and worker so that existing
imports of `FittingDecayConfigPopup` and `FittingWorker` continue to work.
"""

from components.fitting.fitting_constants import (
    DARK_THEME_BG_COLOR,
    DARK_THEME_TEXT_COLOR,
    DARK_THEME_TEXT_FONT_SIZE,
    DARK_THEME_HEADER_FONT_SIZE,
    DARK_THEME_FONT_FAMILY,
    DARK_THEME_RADIO_BTN_STYLE,
    DARK_THEME_LABEL_STYLE,
)
from components.fitting.fitting_worker import FittingWorker
from components.fitting.fitting_controls_mixin import FittingControlsMixin
from components.fitting.fitting_roi_mixin import FittingROIMixin
from components.fitting.fitting_plot_mixin import FittingPlotMixin
from components.fitting.fitting_results_mixin import FittingResultsMixin

__all__ = [
    "DARK_THEME_BG_COLOR",
    "DARK_THEME_TEXT_COLOR",
    "DARK_THEME_TEXT_FONT_SIZE",
    "DARK_THEME_HEADER_FONT_SIZE",
    "DARK_THEME_FONT_FAMILY",
    "DARK_THEME_RADIO_BTN_STYLE",
    "DARK_THEME_LABEL_STYLE",
    "FittingWorker",
    "FittingControlsMixin",
    "FittingROIMixin",
    "FittingPlotMixin",
    "FittingResultsMixin",
]
