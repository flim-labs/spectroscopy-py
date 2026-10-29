"""
Utility functions for channel name management.
Handles custom channel names, formatting, and validation.
"""

def get_channel_name(channel_id: int, custom_names: dict) -> str:
    custom_name = custom_names.get(str(channel_id), None)
    if custom_name:
        return f"{custom_name} (Ch{channel_id + 1})"
    return f"Channel {channel_id + 1}"


def get_channel_short_name(channel_id: int, custom_names: dict) -> str:
    custom_name = custom_names.get(str(channel_id), None)
    if custom_name:
        return f"{custom_name} (Ch{channel_id + 1})"
    return f"Ch {channel_id + 1}"


def get_channel_name_parts(channel_id: int, custom_names: dict) -> tuple:
    custom_name = custom_names.get(str(channel_id), None)
    if custom_name:
        return (custom_name, f" (Ch{channel_id + 1})")
    return ("", f"Channel {channel_id + 1}")


def validate_channel_name(name: str) -> bool:
    if not name:
        return False
    if len(name) > 50:
        return False
    return True


def sanitize_channel_name(name: str) -> str:
    import re
    name = name.replace(' ', '_')
    name = re.sub(r'[/\\:*?"<>|]', '-', name)
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    return name


def extract_channel_names_from_metadata(laserblood_metadata) -> dict:
    """Extract channel_names from laserblood metadata."""
    if laserblood_metadata and isinstance(laserblood_metadata, list):
        for item in laserblood_metadata:
            if isinstance(item, dict) and item.get("id") == "channel_names":
                return item.get("value", {})
    return {}


def format_channel_list(channels: list, custom_names: dict) -> str:
    """Format a list of channel indices with custom names.
    
    Args:
        channels: List of channel indices (0-based)
        custom_names: Dictionary mapping channel indices (as strings) to custom names
        
    Returns:
        str: Formatted string like "test123 (Ch4), Channel 5"
    """
    return ", ".join([get_channel_name(ch, custom_names) for ch in channels])
