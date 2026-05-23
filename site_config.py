import os
import yaml

_CONFIG_FILE = 'config.yaml'
_config = None


def get_config():
    global _config
    if _config is None:
        if os.path.exists(_CONFIG_FILE):
            with open(_CONFIG_FILE) as f:
                _config = yaml.safe_load(f) or {}
        else:
            _config = {}
    return _config
