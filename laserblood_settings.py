import json

SETTINGS_LASER_TYPE = "laser_type"
DEFAULT_LASER_TYPE = "Laser Clean-up Filter ZET 375/10"
SETTINGS_FILTER_TYPE = "filter_type"
DEFAULT_FILTER_TYPE = None


FILTERS_TYPES = [
    "400/16 nm",
    "420/16 nm",
    "440/16 nm",
    "460/15 nm",
    "480/15 nm",
    "500/15 nm",
    "520/15 nm",
    "540/15 nm",
    "560/14 nm",
    "580/14 nm",
    "600/14 nm",
    "620/14 nm",
    "640/14 nm",
    "660/13 nm",
    "680/13 nm",
    "700/13 nm",
    "720/13 nm",
    "740/13 nm",
    "765/22 nm",
    "795/22 nm"
    ]


LASER_TYPES = [
    {"KEY": "375nm", "LABEL": "Laser Clean-up Filter ZET 375/10", "FILTERS": FILTERS_TYPES},
    {"KEY": "405nm", "LABEL": "405/10 ET Bandpass", "FILTERS": FILTERS_TYPES[2:]},
    {"KEY": "445nm", "LABEL": "Laser Clean-up Filter ZET 445/10", "FILTERS": FILTERS_TYPES[4:]},
    {"KEY": "488nm", "LABEL": " Laser Clean-up Filter ZET 488/10", "FILTERS": FILTERS_TYPES[6:]},
    {"KEY": "520nm", "LABEL": " 520/10 ET Bandpass", "FILTERS": FILTERS_TYPES[8:]},
]



SETTINGS_SAMPLE_VOL = {
    "LABEL": "Sample volume after incubation",
    "UNIT": "µL",
    "VALUE": 0,
    "INPUT_TYPE": "float",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": None,
    "POSITION": (0, 0, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False
}
CUVETTE_TOTAL_VOL = {
    "LABEL": "Cuvette total volume",
    "UNIT": "µL",
    "VALUE": 0,
    "OPTIONS": [],
    "INPUT_TYPE": "float",
    "MIN": 0,
    "MAX": None,
    "POSITION": (0, 1, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False
}
SOLVENT_TYPE = {
    "LABEL": "Solvent type",
    "UNIT": None,
    "VALUE": "",
    "OPTIONS": [],
    "INPUT_TYPE": "text",
    "MIN": None,
    "MAX": None,
    "POSITION": (0, 2, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
SOLVENT_VOL = {
    "LABEL": "Solvent volume",
    "UNIT": "µL",
    "VALUE": 0,
    "INPUT_TYPE": "float",
    "MIN": 0,
    "OPTIONS": [],
    "MAX": None,
    "POSITION": (0, 3, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
NANOPARTICLE_TYPE = {
    "LABEL": "Nanoparticle type",
    "UNIT": None,
    "VALUE": "",
    "OPTIONS": [],
    "INPUT_TYPE": "text",
    "MIN": None,
    "MAX": None,
    "POSITION": (1, 0, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
NANOPARTICLE_CONCENTRATION = {
    "LABEL": "Nanoparticle concentration",
    "UNIT": "µg/ µL",
    "VALUE": 0,
    "INPUT_TYPE": "float",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": None,
    "POSITION": (1, 1, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
PROTEIN_SOURCE = {
    "LABEL": "Protein source",
    "UNIT": None,
    "OPTIONS": ["Human plasma", "Murine plasma"],
    "VALUE": 0,
    "INPUT_TYPE": "select",
    "MIN": None,
    "MAX": None,
    "POSITION": (1, 2, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
PROTEIN_SOURCE_VOL = {
    "LABEL": "Protein source volume",
    "UNIT": "µL",
    "VALUE": 0,
    "INPUT_TYPE": "float",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": None,
    "POSITION": (1, 3, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
DILUITION_FACTOR = {
    "LABEL": "Dilution factor after incubation",
    "UNIT": None,
    "VALUE": 0,
    "INPUT_TYPE": "float",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": None,
    "POSITION": (2, 0, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
PROTEIN_SOURCE_INCUBATION = {
    "LABEL": "Protein Source incubation",
    "UNIT": "%",
    "VALUE": 0,
    "INPUT_TYPE": "float",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": None,
    "POSITION": (2, 1, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
INCUBATION_TIME = {
    "LABEL": "Incubation time",
    "UNIT": "min",
    "VALUE": 0,
    "INPUT_TYPE": "float",
    "MIN": 0,
    "OPTIONS": [],
    "MAX": None,
    "POSITION": (2, 2, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
INCUBATION_TEMPERATURE = {
    "LABEL": "Incubation temperature",
    "UNIT": "°C",
    "VALUE": 0,
    "INPUT_TYPE": "float",
    "OPTIONS": [],
    "MIN": None,
    "MAX": None,
    "POSITION": (2, 3, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
INCUBATION_TYPE = {
    "LABEL": "Incubation type",
    "UNIT": None,
    "OPTIONS": ["Static", "Dynamic"],
    "VALUE": 0,
    "INPUT_TYPE": "select",
    "MIN": None,
    "MAX": None,
    "POSITION": (3, 0, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
NANOPARTICLES_PROTEIN_RATIO = {
    "LABEL": "Ratio Nanoparticles/Protein Source",
    "UNIT": None,
    "VALUE": 0,
    "INPUT_TYPE": "int",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": None,
    "POSITION": (3, 1, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
CENTRIFUGE = {
    "LABEL": "Centrifuge",
    "UNIT": None,
    "VALUE": False,
    "INPUT_TYPE": "boolean",
    "OPTIONS": [],
    "MIN": None,
    "MAX": None,
    "POSITION": (3, 2, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
PELLET = {
    "LABEL": "Pellet",
    "UNIT": None,
    "VALUE": False,
    "INPUT_TYPE": "boolean",
    "OPTIONS": [],
    "MIN": None,
    "MAX": None,
    "POSITION": (3, 3, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
SURNATANT = {
    "LABEL": "Surnatant",
    "UNIT": None,
    "VALUE": False,
    "INPUT_TYPE": "boolean",
    "OPTIONS": [],
    "MIN": None,
    "MAX": None,
    "POSITION": (4, 0, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
WASHING = {
    "LABEL": "Washing",
    "UNIT": None,
    "VALUE": 0,
    "OPTIONS": ["1", "2", "3", "NO"],
    "INPUT_TYPE": "select",
    "MIN": None,
    "MAX": None,
    "POSITION": (4, 1, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
LASER_POWER = {
    "LABEL": "Laser power",
    "UNIT": "%",
    "VALUE": 0,
    "INPUT_TYPE": "int",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": 100,
    "POSITION": (4, 2, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
THAW_CYCLES = {
    "LABEL": "Number of thaw cycles",
    "UNIT": None,
    "VALUE": 0,
    "INPUT_TYPE": "int",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": None,
    "POSITION": (4, 3, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
PLASMA_COLOR = {
    "LABEL": "Plasma color",
    "UNIT": None,
    "VALUE": 0,
    "OPTIONS": ["Yellow", "Red"],
    "INPUT_TYPE": "select",
    "MIN": None,
    "MAX": None,
    "POSITION": (5, 0, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
AVERAGE_CPS = {
    "LABEL": "Average CPS",
    "UNIT": "CPS",
    "VALUE": 0,
    "INPUT_TYPE": "float",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": None,
    "POSITION": (5, 1, 1, 1),
    "ENABLED": False,
    "REMOVABLE": False    
}
CUVETTE_MATERIAL = {
    "LABEL": "Cuvette material",
    "UNIT": None,
    "VALUE": 0,
    "OPTIONS": ["Plastic", "Glass", "Quartz"],
    "INPUT_TYPE": "select",
    "MIN": None,
    "MAX": None,
    "POSITION": (5, 2, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
CUVETTE_DIMENSIONS = {
    "LABEL": "Cuvette dimensions",
    "UNIT": "mm",
    "VALUE": "",
    "INPUT_TYPE": "text",
    "OPTIONS": [],
    "MIN": None,
    "MAX": None,
    "POSITION": (5, 3, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
LASER_CENTRAL_WAVE_LENGTH = {
    "LABEL": "Laser central wavelength",
    "UNIT": "nm",
    "VALUE": 0,
    "INPUT_TYPE": "int",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": None,
    "POSITION": (6, 0, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
EMISSION_FILTER = {
    "LABEL": "Emission filter",
    "UNIT": "nm",
    "VALUE": "",
    "INPUT_TYPE": "text",
    "OPTIONS": [],
    "MIN": None,
    "MAX": None,
    "POSITION": (6, 1, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
LASER_REPETITION_RATE = {
    "LABEL": "Laser repetition rate",
    "UNIT": "MHz",
    "VALUE": 0,
    "INPUT_TYPE": "int",
    "OPTIONS": [],
    "MIN": 0,
    "MAX": None,
    "POSITION": (6, 2, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
FPGA_FIRMWARE_TYPE = {
    "LABEL": "FPGA firmware type",
    "UNIT": None,
    "VALUE": "",
    "INPUT_TYPE": "text",
    "OPTIONS": [],
    "MIN": None,
    "MAX": None,
    "POSITION": (6, 3, 1, 1),
    "ENABLED": True,
    "REMOVABLE": False    
}
NOTES = {
    "LABEL": "Notes",
    "UNIT": None,
    "VALUE": "",
    "INPUT_TYPE": "textarea",
    "OPTIONS": [],
    "MIN": None,
    "MAX": None,
    "POSITION": (7, 0, 1, 4),
    "ENABLED": True,
    "REMOVABLE": False    
}

LASERBLOOD_METADATA = [
    SETTINGS_SAMPLE_VOL,
    CUVETTE_TOTAL_VOL,
    SOLVENT_TYPE,
    SOLVENT_VOL,
    NANOPARTICLE_TYPE,
    NANOPARTICLE_CONCENTRATION,
    PROTEIN_SOURCE,
    PROTEIN_SOURCE_VOL,
    DILUITION_FACTOR,
    PROTEIN_SOURCE_INCUBATION,
    INCUBATION_TYPE,
    INCUBATION_TIME,
    INCUBATION_TEMPERATURE,
    NANOPARTICLES_PROTEIN_RATIO,
    CENTRIFUGE,
    PELLET,
    SURNATANT,
    WASHING,
    LASER_POWER,
    THAW_CYCLES,
    PLASMA_COLOR,
    AVERAGE_CPS,
    CUVETTE_MATERIAL,
    CUVETTE_DIMENSIONS,
    LASER_CENTRAL_WAVE_LENGTH,
    EMISSION_FILTER,
    LASER_REPETITION_RATE,
    FPGA_FIRMWARE_TYPE,
    NOTES,
]

METADATA_LASERBLOOD_KEY = "laserblood_settings"

NEW_ADDED_LASERBLOOD_INPUTS_KEY = "laserblood_new_added_inputs"
NEW_ADDED_LASERBLOOD_INPUTS_JSON = json.dumps([], indent=4)

LASERBLOOD_METADATA_JSON = json.dumps(LASERBLOOD_METADATA, indent=4)

LASERBLOOD_METADATA_POPUP = "laserblood_metadata_popup"
