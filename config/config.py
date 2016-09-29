import config.config_default
config = config.config_default.configs

try:
import config_override
    config = merge(configs, config_override.configs)
except ImportError:
    pass
