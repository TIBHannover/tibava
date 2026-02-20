import logging
from typing import Dict


class Factory:
    _plugins = {}

    @classmethod
    def export(cls, name: str):
        def export_helper(plugin):
            cls._plugins[name] = plugin
            return plugin

        return export_helper

    @classmethod
    def build(cls, name: str, config: Dict = None):
        if name not in cls._plugins:
            logging.error(f"Unknown inference server: {name}")
            return None

        return cls._plugins[name](config)
