from copy import deepcopy


VERSION = "2.9"
APP_DEFAULT_WIDTH = 1000
APP_DEFAULT_HEIGHT = 800
TOP_BAR_HEIGHT = 250
MAX_CHANNELS = 8


SETTINGS_BIN_WIDTH = "bin_width"
DEFAULT_BIN_WIDTH = 1000
SETTINGS_TIME_SPAN = "time_span"
DEFAULT_TIME_SPAN = 10
SETTINGS_CONNECTION_TYPE = "connection_type"
SETTINGS_CALIBRATION_TYPE = "calibration"
DEFAULT_SETTINGS_CALIBRATION_TYPE = 0
DEFAULT_CONNECTION_TYPE = "1"
SETTINGS_FREE_RUNNING = "free_running"
DEFAULT_FREE_RUNNING = "false"
SETTINGS_ACQUISITION_TIME = "acquisition_time"
SETTINGS_TAU_NS = "tau_ns"
SETTINGS_HARMONIC = "harmonic"
HARMONIC_SELECTOR = "harmonic_selector"
HARMONIC_SELECTOR_LABEL = "harmonic_selector_label"
SETTINGS_HARMONIC_LABEL = "harmonic_label"
SETTINGS_HARMONIC_DEFAULT = 1
DEFAULT_ACQUISITION_TIME = 10
SETTINGS_SYNC = "sync"
DEFAULT_SYNC = "sync_in"
SETTINGS_SYNC_IN_FREQUENCY_MHZ = "sync_in_frequency_mhz"
DEFAULT_SYNC_IN_FREQUENCY_MHZ = 0.0
SETTINGS_WRITE_DATA = "write_data"
DEFAULT_WRITE_DATA = True
SETTINGS_TIME_TAGGER = "time_tagger"
DEFAULT_TIME_TAGGER = False
SETTINGS_TIME_SHIFTS = "time_shift"
SETTINGS_CPS_THRESHOLD = "cps_threshold"
DEFAULT_CPS_THRESHOLD = 0
SETTINGS_SHOW_SBR = "show_SBR"
DEFAULT_SHOW_SBR = False
SETTINGS_REPLICATES = "replicates"
DEFAULT_REPLICATES = 1


SETTINGS_PICO_MODE = "pico_mode"
DEFAULT_PICO_MODE = False


TIME_TAGGER_PROGRESS_BAR = "time_tagger_progress_bar"
TIME_TAGGER_WIDGET = "time_tagger_widget"

TIME_SHIFTS_NS = "time_shifts_ns"


FIT_BTN = "fit_button"
FIT_BTN_PLACEHOLDER = "fit_button_placeholder"
TAB_FITTING = "tab_deconv"

TAB_PHASORS = "tab_data"
TAB_SPECTROSCOPY = "tab_spectroscopy"

DEFAULT_TIME_SHIFTS = "{}"
CURSOR_TEXT = "⨁"

LOAD_REF_BTN = "load_reference_btn"

MODE_STOPPED = "stopped"
MODE_RUNNING = "running"

PALETTE_RED_1 = "#DA1212"
PALETTE_BLUE_1 = "#11468F"

TOP_COLLAPSIBLE_WIDGET = "top_collapsible_widget"
PLOTS_CONFIG_POPUP = "plots_config_popup"

SETTINGS_PLOTS_TO_SHOW = "plots_to_show"
DEFAULT_PLOTS_TO_SHOW = "[]"

SETTINGS_LIN_LOG_MODE = "lin_log_mode"
DEFAULT_LIN_LOG_MODE = "{}"

SETTINGS_ROI = "roi"
DEFAULT_ROI = "{}"

CHANNELS_GRID = "channels_grid"



UNICODE_SUP = {
    "0": "\u2070",
    "1": "\u00B9",
    "2": "\u00B2",
    "3": "\u00B3",
    "4": "\u2074",
    "5": "\u2075",
    "6": "\u2076",
    "7": "\u2077",
    "8": "\u2078",
    "9": "\u2079",
}

REALTIME_MS = 50
REALTIME_ADJUSTMENT = REALTIME_MS * 1000
HETERODYNE_FACTOR = 255.0 / 256.0
DEFAULT_TICKS_LOG = [0, 1, 2, 3, 4, 5, 6]
DEFAULT_TICKS_LIN = [0, 10, 100, 1000, 10000, 100000, 1000000]


PHASORS_RESOLUTIONS = ["16", "32", "64", "128", "256", "512"]
SETTINGS_PHASORS_RESOLUTION = "phasors_resolution"
DEFAULT_PHASORS_RESOLUTION = 2
SETTINGS_QUANTIZE_PHASORS = "quantize_phasors"
DEFAULT_QUANTIZE_PHASORS = True


READER_POPUP = "reader_popup"
READER_METADATA_POPUP = "reader_metadata_popup"
FITTING_POPUP = "fitting_popup"

SETTINGS_ACQUIRE_READ_MODE = "acquire_read_mode"
DEFAULT_ACQUIRE_READ_MODE = "acquire"
ACQUIRE_BUTTON = "acquire_button"
READ_BUTTON = "read_button"
EXPORT_PLOT_IMG_BUTTON = "export_plot_img_button"

CHECK_CARD_BUTTON = "check_card_button"
CHECK_CARD_MESSAGE = "check_card_message"

CHANNELS_DETECTION_BUTTON = "channels_detection_button"



READER_DATA = {
    "spectroscopy": {
        "files": {"spectroscopy": "", "laserblood_metadata": ""},
        "plots": [],
        "metadata": {},
        "laserblood_metadata": {},
        "data": {},
    },
    "phasors": {
        "files": {"spectroscopy": [], "phasors": [], "laserblood_metadata": ""},
        "spectroscopy_metadata": [],
        "phasors_metadata": [],
        "plots": [],
        "metadata": [],
        "laserblood_metadata": {},
        "data": {"phasors_data": {}, "spectroscopy_data": {}},
    },
    "fitting": {
        "files": {"spectroscopy": "", "fitting": "", "laserblood_metadata": ""},
        "plots": [],
        "spectroscopy_metadata": {},
        "fitting_metadata": {},
        "laserblood_metadata": {},
        "metadata": {},
        "data": {"fitting_data": {}, "spectroscopy_data": {}},
    },
}

DEFAULT_READER_DATA = deepcopy(READER_DATA)


INTENSITY_LINES = {TAB_SPECTROSCOPY: {}, TAB_FITTING: {}}

DEFAULT_INTENSITY_LINES = deepcopy(INTENSITY_LINES)
DECAY_CURVES = {
    TAB_SPECTROSCOPY: {},
    TAB_PHASORS: {},
    TAB_FITTING: {},
}
DEFAULT_DECAY_CURVES = deepcopy(DECAY_CURVES)
CACHED_DECAY_VALUES =  {
            TAB_SPECTROSCOPY: {},
            TAB_FITTING: {},
        }
DEFAULT_CACHED_DECAY_VALUES = deepcopy(CACHED_DECAY_VALUES)

AVAILABLE_FREQUENCIES_MHZ = [80.0, 40.0, 20.0, 10.0]