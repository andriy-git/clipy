
import json
import os
from .utils import get_config_dir

CONFIG_PATH = os.path.join(get_config_dir(), "config.json")

DEFAULT_CONFIG = {
    "max_entries": 100,
    "blacklist": []
}

def load_config():
    """Loads configuration from file or returns defaults."""
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
            # Ensure all default keys are present
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    except (json.JSONDecodeError, IOError):
        return DEFAULT_CONFIG

def save_config(config):
    """Saves configuration to file."""
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=4)
    except IOError:
        pass
