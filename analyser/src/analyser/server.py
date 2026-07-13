import grpc
import sys
import time
import tomllib

import argparse
import logging

from tibava_interface import (
    analyser_pb2_grpc,
    searcher_pb2_grpc,
    collection_pb2_grpc,
)

from concurrent import futures

from shared_object import SharedObject
from plugins import IndexerPluginManager

from services import AnalyserServicer, CollectionServicer, SearcherServicer
from inference import InferenceServerManager
from plugins import ComputePluginManager
from plugins.cache import Cache
from tibava_data import DataManager
from database.filesystem_database import FilesystemCollectionDatabase
from database.valkey_database import CollectionDatabase, ValkeyCollectionRegister


class Server:
    def __init__(self, config):
        self.config = config
        inference_server_manager = InferenceServerManager(config)
        compute_plugin_manager = ComputePluginManager(
            config, inference_server_manager=inference_server_manager
        )

        indexer_plugin_manager = IndexerPluginManager(
            config, compute_plugin_manager=compute_plugin_manager
        )

        cache = Cache(cache_dir=config.get("cache", {"path": None})["path"], mode="r")

        data_config = config.get("data", None)
        data_dir = None
        if data_config is not None:
            data_dir = data_config.get("path", None)
            cache_config = data_config.get("cache")
            if cache_config is not None:
                cache = CacheManager.build(
                    name=cache_config["type"], config=cache_config["params"]
                )

        data_manager = DataManager(data_dir=data_dir, cache=cache)

        collection_database = CollectionDatabase(
            ValkeyCollectionRegister(), data_manager
        )

        self.shared_object = SharedObject(
            config,
            inference_server_manager=inference_server_manager,
            compute_plugin_manager=compute_plugin_manager,
            indexer_plugin_manager=indexer_plugin_manager,
            data_manager=data_manager,
            collection_database=collection_database,
        )

        self.indexer_servicer = AnalyserServicer(config, self.shared_object)
        self.collection_servicer = CollectionServicer(config, self.shared_object)
        self.searcher_servicer = SearcherServicer(config, self.shared_object)

        self.server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )

        searcher_pb2_grpc.add_SearcherServicer_to_server(
            self.searcher_servicer,
            self.server,
        )

        analyser_pb2_grpc.add_AnalyserServicer_to_server(
            self.indexer_servicer,
            self.server,
        )

        collection_pb2_grpc.add_CollectionServicer_to_server(
            self.collection_servicer,
            self.server,
        )

        grpc_config = config.get("grpc", {})
        port = grpc_config.get("port", 50051)
        self.server.add_insecure_port(f"[::]:{port}")

        logging.info("Start all inference servers")
        inference_server_manager.start()

    def run(self):
        self.server.start()
        logging.info("[Server] Ready")

        try:
            while True:
                num_jobs = len(self.indexer_servicer.futures)
                num_jobs_done = len(
                    [x for x in self.indexer_servicer.futures if x["future"].done()]
                )
                logging.info(
                    f"[Server] num_jobs:{num_jobs} num_jobs_done:{num_jobs_done}"
                )

                time.sleep(60 * 60)
        except KeyboardInterrupt:
            self.server.stop(0)


def parse_args():
    parser = argparse.ArgumentParser(description="Indexing a set of images")

    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument("-d", "--debug", action="store_true", help="verbose output")

    parser.add_argument("--port", type=int, help="")

    parser.add_argument("-c", "--config", help="config path")
    args = parser.parse_args()
    return args


def read_config(path):
    with open(path, "rb") as f:
        return tomllib.load(f)
    return {}


def main():
    args = parse_args()
    level = logging.ERROR
    if args.debug:
        print("LOGGING::DEBUG")
        level = logging.DEBUG
    elif args.verbose:
        print("LOGGING::INFO")
        level = logging.INFO

    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%d-%m-%Y %H:%M:%S",
        level=level,
    )

    if args.config is not None:
        config = read_config(args.config)
    else:
        config = {}

    server = Server(config)
    server.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
