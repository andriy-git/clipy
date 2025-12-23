
import os
import hashlib
import time

def get_data_dir():
    """Returns the data directory for clipy."""
    data_dir = os.path.expanduser("~/.local/share/clipy")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_image_dir():
    """Returns the directory for storing image clips (non-persistent)."""
    image_dir = "/tmp/clipy/images"
    os.makedirs(image_dir, exist_ok=True)
    return image_dir

def get_config_dir():
    """Returns the configuration directory for clipy."""
    config_dir = os.path.expanduser("~/.config/clipy")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir

def calculate_hash(content: bytes) -> str:
    """Calculates SHA256 hash of content."""
    return hashlib.sha256(content).hexdigest()

def format_timestamp(timestamp: float) -> str:
    """Formats timestamp for display."""
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
