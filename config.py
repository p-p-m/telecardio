
import yaml

_config = None

def get():
    global _config
    if _config is None:
        with open("config.yaml", 'r') as file:
            _config = yaml.safe_load(file)
    return _config


def reset():
    global _config
    _config = None
