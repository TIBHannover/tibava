from inference import InferenceServerFactory

from tibava_data import DataManager

from plugins.cache import Cache


class SharedObject:
    def __init__(
        self,
        config,
        inference_server_manager,
        compute_plugin_manager,
        indexer_plugin_manager,
        data_manager,
        collection_database,
    ):
        self.inference_server_manager = inference_server_manager
        self.compute_plugin_manager = compute_plugin_manager
        self.indexer_plugin_manager = indexer_plugin_manager
        self.data_manager = data_manager
        self.collection_database = collection_database

        self.config = config
