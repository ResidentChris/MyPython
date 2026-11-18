"""Loads the user's settings for `my`.

Settings live in settings.toml next to this file, which git ignores.
settings.defaults.toml is the starting point for creating it.
"""

import os
import tomllib

FOLDER = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(FOLDER, 'settings.toml')
DEFAULTS_FILE = os.path.join(FOLDER, 'settings.defaults.toml')


class MissingSettings(Exception):
    pass


def load_settings(repository: str, path: str = SETTINGS_FILE) -> dict:
    """Read the settings file, filling in {root} and {repository} in every string."""
    if not os.path.isfile(path):
        raise MissingSettings(
            'No settings file at %s. Copy %s to it and change the values for your machine.'
            % (path, DEFAULTS_FILE))
    with open(path, 'rb') as f:
        settings = tomllib.load(f)
    placeholders = {'root': settings.get('root', ''), 'repository': repository}
    return _fill(settings, placeholders)


def _fill(value, placeholders):
    if isinstance(value, str):
        return value.format_map(placeholders)
    if isinstance(value, dict):
        return {key: _fill(item, placeholders) for key, item in value.items()}
    if isinstance(value, list):
        return [_fill(item, placeholders) for item in value]
    return value
