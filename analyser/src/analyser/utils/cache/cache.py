import logging
from typing import Dict

from analyser.utils.plugin import Plugin
from analyser.utils.plugin import Factory


class Cache(Plugin):
    def __init__(self, config=None):
        super().__init__(config)


class CacheManager(Factory):
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
            logging.error(f"Unknown cache server: {name}")
            return None

        return cls._plugins[name](config)


import hashlib
import json
import logging
from typing import List, Dict
from analyser.utils import flat_dict


def get_hash_for_plugin(
    plugin: str,
    output: str,
    version: str = None,
    parameters: List = [],
    inputs: List = [],
    config: Dict = {},
):
    plugin_call_dict = {
        "plugin": plugin,
        "output": output,
        "parameters": parameters,
        "inputs": inputs,
        "config": config,
        "version": version,
    }
    # logging.info(f"[HASH] {plugin_call_dict}")

    # logging.info(f"[HASH] {flat_dict(plugin_call_dict)}")
    plugin_hash = hashlib.sha256(
        json.dumps(
            flat_dict(
                {
                    "plugin": plugin,
                    "output": output,
                    "parameters": parameters,
                    "inputs": inputs,
                    "config": config,
                    "version": version,
                }
            )
        ).encode()
    ).hexdigest()

    # logging.info(f"[HASH] {plugin_hash}")
    return plugin_hash
