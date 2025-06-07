import os
import json

# Configuration file to store channel IDs
CONFIG_FILE = 'data/config.json'

# Default configuration
default_config = {
    'dismissal_channel': None,
    'audit_channel': None,
    'blacklist_channel': None
}

# Load configuration
def load_config():
    """Load configuration from JSON file."""
    try:
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Create default config file if it doesn't exist
        save_config(default_config)
        return default_config.copy()

# Save configuration
def save_config(config):
    """Save configuration to JSON file."""
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)
