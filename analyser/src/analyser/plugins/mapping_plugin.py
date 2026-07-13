import importlib
import os
import re
import sys
import logging

from analyser.utils.plugin.manager import Manager
from analyser.utils.plugin.plugin import Plugin


class MappingPlugin(Plugin):
    _type = "mapping"

    def __init__(self, **kwargs):
        super(MappingPlugin, self).__init__(**kwargs)

    def __call__(self, entries, query):
        return self.call(entries, query)


class MappingPluginManager(Manager):
    _mapping_plugins = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def export(cls, name):
        def export_helper(plugin):
            cls._mapping_plugins[name] = plugin
            return plugin

        return export_helper

    def plugins(self):
        return self._mapping_plugins

    def find(
        self, path=os.path.join(os.path.abspath(os.path.dirname(__file__)), "mapping")
    ):
        file_re = re.compile(r"(.+?)\.py$")
        for pl in os.listdir(path):
            match = re.match(file_re, pl)
            if match:
                a = importlib.import_module(
                    "analyser.plugins.mapping.{}".format(match.group(1))
                )
                # print(a)
                function_dir = dir(a)
                if "register" in function_dir:
                    a.register(self)

    def run(self, entries, query, plugins=None, configs=None, batchsize=128):
        plugin_list = self.init_plugins(plugins, configs)
        if len(plugin_list) > 1:
            logging.error("Only one mapping plugin should excecuted")
            raise ValueError
        logging.info(f"MappingPluginManager: {plugin_list}")
        # TODO use batch size
        for plugin in plugin_list:
            # logging.info(dir(plugin_class["plugin"]))
            plugin = plugin["plugin"]

            plugin_version = plugin.version
            plugin_name = plugin.name

            logging.info(f"Plugin start {plugin.name}:{plugin.version}")

            # exit()
            plugin_results = plugin(entries, query)
            for entry in plugin_results:
                yield entry
