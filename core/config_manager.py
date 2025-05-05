# core/config_manager.py
import configparser
import os
from pathlib import Path
from PyQt6.QtCore import QStandardPaths

APP_NAME = "GeminiChatApp"
CONFIG_FILE = "config.ini"

DEFAULT_CONFIG = {
    'API': {'api_key': 'AIzaSyADIrgaKzSh613rIj4DRodWq18XzBhvitU'},
    'Models': {'available_models': 'gemini-1.0-pro,gemini-1.5-flash-latest', 'selected_model': 'gemini-1.5-flash-latest'},
    'Hotkeys': {'toggle_visibility': 'Ctrl+Alt+G', 'screenshot_full': 'Ctrl+Alt+S'},
    'UI': {'always_on_top': 'False'} # Example extra setting
}

def get_config_dir():
    """Gets the application's configuration directory."""
    # Use AppDataLocation which is more standard for user-specific config
    # AppConfigLocation might point to ProgramData on Windows if not careful
    path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_config_path():
    """Gets the full path to the config file."""
    return get_config_dir() / CONFIG_FILE

def load_config():
    """Loads configuration from the INI file."""
    config_path = get_config_path()
    config = configparser.ConfigParser()

    # Set defaults first using DEFAULT_CONFIG
    for section, options in DEFAULT_CONFIG.items():
        if not config.has_section(section):
            config.add_section(section)
        for key, value in options.items():
             # Set default value directly - read() will overwrite if file exists
             config.set(section, key, value)

    # Read existing file if it exists, overwriting defaults
    if config_path.exists():
        try:
            config.read(config_path)
            # Ensure all default sections/options exist even after reading
            # This adds sections/keys missing from the file but present in defaults
            for section, options in DEFAULT_CONFIG.items():
                if not config.has_section(section):
                    config.add_section(section)
                    for key, value in options.items():
                        config.set(section, key, value)
                else:
                    # Section exists, check for missing keys within it
                    for key, value in options.items():
                        if not config.has_option(section, key):
                            config.set(section, key, value) # Add missing keys with default value

        except configparser.Error as e:
            print(f"Error reading config file {config_path}: {e}. Using defaults and attempting to overwrite.")
            # Re-create config parser with defaults if file is corrupt
            config = configparser.ConfigParser()
            for section, options in DEFAULT_CONFIG.items():
                config[section] = options
            # Attempt to save the default config immediately
            save_config(config)
    else:
         # If file doesn't exist, save the default config now
         print(f"Config file not found at {config_path}. Creating with defaults.")
         save_config(config)


    return config

def save_config(config):
    """Saves the configuration object to the INI file."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    except IOError as e:
        print(f"Error saving config file {config_path}: {e}")

def get_setting(section, key):
    """Gets a specific setting value."""
    config = load_config() # Load ensures defaults are handled
    try:
        # Use get() which handles NoSectionError/NoOptionError gracefully by default if needed
        # but our load_config logic should prevent needing fallback here.
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        # This path should ideally not be hit due to load_config's default handling
        print(f"Warning: Setting {section}/{key} not found after load, returning hardcoded default.")
        return DEFAULT_CONFIG.get(section, {}).get(key, None)


def set_setting(section, key, value):
    """Sets a specific setting value and saves."""
    config = load_config()
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, key, str(value)) # Ensure value is string for configparser
    save_config(config)

# Ensure config file exists with defaults on first import/run
# load_config() is called by get_setting/set_setting, but calling it here ensures
# the file is created immediately if it's missing.
if not get_config_path().exists():
    load_config()

