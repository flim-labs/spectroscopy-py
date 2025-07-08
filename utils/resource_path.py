import os
import sys

def resource_path(relative_path):
    """
    Get the absolute path to a resource, works for dev and for PyInstaller.

    This function is crucial for accessing data files (like images, icons, etc.)
    in a way that works both when running the script directly and when it's
    packaged into a single executable file by PyInstaller.

    Args:
        relative_path (str): The path to the resource relative to the project root.

    Returns:
        str: The absolute path to the resource.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # If not running as a PyInstaller bundle, use the current directory
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)