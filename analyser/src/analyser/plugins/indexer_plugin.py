import os
import logging
from dataclasses import dataclass
from typing import List, Dict

from analyser.utils.plugin.factory import Factory
from analyser.utils.plugin.plugin import Plugin
from analyser.plugins.compute_plugin import ComputePluginManager


class IndexerPlugin(Plugin):
    def __init__(self, **kwargs):
        super(IndexerPlugin, self).__init__(**kwargs)

    def indexing(self, train_entries, index_entries):
        pass

    def search(self, queries, size=100):
        pass


class IndexerFactory(
    Factory,
    plugins_path=os.path.join(os.path.abspath(os.path.dirname(__file__)), "indexer"),
    plugin_import_path="analyser.plugins.indexer",
    plugin_cls=IndexerPlugin,
):
    pass


@dataclass
class IndexingPluginMapping:
    index_name: str
    compute_plugin: str
    input_mapping: Dict[str, str]
    fields: List[str]


@dataclass
class SearchPluginMapping:
    index_name: str
    compute_plugin: str
    input_mapping: Dict[str, str]
    fields: List[str]


@dataclass
class PayloadMapping:
    fields: List[str]


class IndexerPluginManager:
    def __init__(
        self,
        config: Dict,
        compute_plugin_manager: ComputePluginManager,
        indexer_plugin_factory: IndexerFactory = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.config = config

        if indexer_plugin_factory is None:
            indexer_plugin_factory = IndexerFactory()

        self.indexer_plugin_factory = indexer_plugin_factory
        self.compute_plugin_manager = compute_plugin_manager
        self.check_and_init_indexes()

    def init_indexes(
        self,
        indexer_plugin,
        index,
        # target_index_configuration,
        # current_index_configuration=None,
    ):
        # check what the configuration wants
        target_index_configuration = []
        for indexing_plugin in index.get("indexing_plugin", []):
            compute_plugin = self.compute_plugin_manager[
                indexing_plugin.get("compute_plugin")
            ]

            target_index_configuration.append(
                {
                    "name": indexing_plugin.get("index_name"),
                    "size": compute_plugin["compute_plugin"].embedding_size,
                }
            )

        # check if the collection exists and what are the indexes
        current_index_configuration = indexer_plugin.get_collection_indexes(
            index.get("name")
        )

        # there is nothing so we will create an index
        if current_index_configuration is None:
            logging.info(f'Create new collection "{index.get("name")}"')
            indexer_plugin.create_collection(
                name=index.get("name"),
                indexes=target_index_configuration,
            )
            return

        # check if the existing index is compatible with the target index from the config
        current_index_configuration = {
            x["name"]: x["size"] for x in current_index_configuration
        }
        match = True
        for x in target_index_configuration:
            if x["name"] in current_index_configuration:
                if x["size"] != current_index_configuration[x["name"]]:
                    logging.error(
                        f'Size different between existing index and configuration for index "{x["name"]}" ({x["size"]} vs {current_index_configuration[x["name"]]}).'
                    )
                    match = False

            else:
                logging.error(
                    f'Target index "{x["name"]}" didn\'t exists in current collection.'
                )
                match = False

        if not match:
            logging.error(
                f'Target index "{x["name"]}" is not compatible with the existing index'
            )
            # TODO fix
            exit(-1)

    def check_and_init_indexes(self):
        # Build an dict with index name to indexer plugin and config
        self.indexes = {}
        for index in self.config.get("index", []):
            index_name = index.get("name")
            if index_name is None and not isinstance(index_name, str):
                logging.error("Index has no name field or it is not a string.")
                exit(-1)

            indexer_plugin_config = index.get("indexer_plugin")
            if indexer_plugin_config is None or not isinstance(
                indexer_plugin_config, dict
            ):
                logging.error(
                    f'Index "{index_name}" has no indexer_plugin field or it is not a dictionary.'
                )
                exit(-1)

            indexer_plugin_type = indexer_plugin_config.get("type")
            if indexer_plugin_type is None or not isinstance(indexer_plugin_type, str):
                logging.error(
                    f'Index "{index_name}" has no type field or it is not a dictionary.'
                )
                exit(-1)

            indexer_plugin = self.indexer_plugin_factory.build(
                indexer_plugin_type, config=indexer_plugin_config.get("params", {})
            )

            if index_name in self.indexes:
                logging.error(
                    f'There is more than one index with the name "{index_name}".'
                )

            self.init_indexes(indexer_plugin, index)

            self.indexes[index_name] = {
                "indexer_plugin": indexer_plugin,
                "config": index,
            }

    def __contains__(self, collection_name):
        return collection_name in self.indexes

    def list_collections(self):
        # TODO add lock here
        logging.info(f"[IndexerPluginManager::list_collections]")

        result = []
        for index_name, x in self.indexes.items():
            result.append(index_name)

        return result

    def get_indexing_plugin_mappings(
        self, collection_name: str
    ) -> List[IndexingPluginMapping]:
        if collection_name not in self:
            return None
        collection_config = self.indexes[collection_name]["config"]

        results = []
        for indexing_plugin in collection_config["indexing_plugin"]:
            results.append(IndexingPluginMapping(**indexing_plugin))

        return results

    def get_search_plugin_mappings(
        self, collection_name: str
    ) -> List[SearchPluginMapping]:
        if collection_name not in self:
            return None
        collection_config = self.indexes[collection_name]["config"]

        results = []
        for search_plugin in collection_config.get("search_plugin", []):
            results.append(SearchPluginMapping(**search_plugin))

        return results

    def get_payload_mapping(self, collection_name: str) -> PayloadMapping:
        if collection_name not in self:
            return None
        collection_config = self.indexes[collection_name]["config"]

        return PayloadMapping(fields=collection_config.get("payload_fields", []))

    def add_points(self, collection_name, points: List[Dict]):
        # TODO add lock here
        logging.info(f"[IndexerPluginManager]: add_points")

        if collection_name not in self.indexes:
            logging.error(
                "[IndexerPluginManager::add_points] Unknown collection '{collection_name}'"
            )
            return None

        indexer_plugin = self.indexes[collection_name]["indexer_plugin"]

        indexer_plugin.add_points(collection_name=collection_name, points=points)

    def delete_collection(
        self,
        collection_name=None,
    ):
        # TODO add lock here
        logging.info(f"[IndexerPluginManager]: delete")
        logging.info(f"[IndexerPluginManager]: {collection_name}")

        if collection_name not in self.indexes:
            logging.error(
                "[IndexerPluginManager::delete] Unknown collection '{collection_name}'"
            )
            return None

        status = self.indexes[collection_name]["indexer_plugin"].delete_collection(
            collection_name
        )
        if status is True:
            del self.indexes[collection_name]
        return status

    def search(
        self,
        collection_name=None,
        **kwargs,
    ):
        # TODO add lock here
        logging.info(f"[IndexerPluginManager]: search")
        logging.info(f"[IndexerPluginManager]: {collection_name}")

        if collection_name not in self.indexes:
            logging.error(
                "[IndexerPluginManager::search] Unknown collection '{collection_name}'"
            )
            return None

        results = self.indexes[collection_name]["indexer_plugin"].search(**kwargs)
        return results
