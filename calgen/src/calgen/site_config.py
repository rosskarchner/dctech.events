import os
import yaml

_CONFIG_FILE = 'config.yaml'
_config = None


def get_config():
    global _config
    if _config is None:
        site_dir = os.environ.get('CALGEN_SITE_DIR', '.')
        config_path = os.path.join(site_dir, _CONFIG_FILE)
        if os.path.exists(config_path):
            with open(config_path) as f:
                _config = yaml.safe_load(f) or {}
        else:
            _config = {}
    return _config


def reset_config():
    """Clear cached config — call before create_app() when site_dir changes."""
    global _config
    _config = None
