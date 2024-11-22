import os
from configparser import ConfigParser

from settings import VERSION


def check_and_update_ini():
    ini_file = "settings.ini"
    config = ConfigParser()

    if os.path.exists(ini_file):
        config.read(ini_file)
        if "General" in config:
            stored_version = config["General"].get("app_version", None)
            if stored_version != VERSION:
                print(
                    f"Version mismatch: {stored_version} != {VERSION}. Updating '{ini_file}'."
                )
                recreate_ini_file(ini_file)
        else:
            recreate_ini_file(ini_file)
    else:
        recreate_ini_file(ini_file)


def recreate_ini_file(ini_file):
    config = ConfigParser()
    config["General"] = {
        "app_version": VERSION,
    }
    with open(ini_file, "w") as f:
        config.write(f)
