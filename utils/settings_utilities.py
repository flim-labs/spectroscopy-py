import os
from configparser import ConfigParser

from settings.settings import VERSION

def check_and_update_ini():
    """Checks for the existence and version of the 'settings.ini' file.

    If the file does not exist, or if the 'app_version' stored within it
    does not match the current application VERSION constant, the file is
    recreated with the current version.
    """
    ini_file = "settings.ini"
    config = ConfigParser()

    if os.path.exists(ini_file):
        config.read(ini_file)
        if "General" in config:
            stored_version = config["General"].get("app_version", None)
            if stored_version != VERSION:
                print(f"Version mismatch: {stored_version} != {VERSION}. Updating '{ini_file}'.")
                recreate_ini_file(ini_file)
        else:
            recreate_ini_file(ini_file)
    else:
        recreate_ini_file(ini_file)
        

def recreate_ini_file(ini_file):
    """Creates or overwrites an INI file with the current application version.

    Args:
        ini_file (str): The path to the INI file to be created or overwritten.
    """
    config = ConfigParser()
    config["General"] = {
        "app_version": VERSION,
    }
    try:
        with open(ini_file, "w") as f:
            config.write(f)
    except PermissionError:
        pass
