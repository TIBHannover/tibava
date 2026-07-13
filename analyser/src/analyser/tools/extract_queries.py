import os
import sys
import re
import argparse
import time
import logging
import traceback
import json

import numpy as np

from concurrent import futures
from multiprocessing.pool import Pool
from google.protobuf.json_format import MessageToJson, MessageToDict, ParseDict

from iart_indexer import indexer_pb2, indexer_pb2_grpc
from iart_indexer.database.elasticsearch_database import ElasticSearchDatabase
from iart_indexer.database.elasticsearch_suggester import ElasticSearchSuggester
from iart_indexer.plugins import *
from iart_indexer.plugins import ClassifierPlugin, FeaturePlugin, ImageTextPluginManager
from iart_indexer.plugins import IndexerPluginManager
from iart_indexer.utils import image_from_proto, meta_from_proto, meta_to_proto, classifier_to_proto, feature_to_proto
from iart_indexer.utils import get_features_from_db_entry, get_classifier_from_db_entry, read_chunk, image_normalize
from iart_indexer.jobs import IndexingJob
from iart_indexer.search import Searcher
from iart_indexer.aggregation import Aggregator
from iart_indexer.plugins.cache import Cache


def search(args):
    logging.info("Search: Start")

    try:
        start_time = time.time()

        query = ParseDict(args["query"], indexer_pb2.SearchRequest())
        config = args["config"]

        database = ElasticSearchDatabase(config=config.get("elasticsearch", {}))

        image_text_plugin_manager = globals().get("image_text_manager")
        feature_plugin_manager = globals().get("feature_manager")
        mapping_plugin_manager = globals().get("mapping_manager")
        indexer_plugin_manager = globals().get("indexer_manager")

        classifier_plugin_manager = None
        # indexer_plugin_manager = None

        aggregator = Aggregator(database)
        searcher = Searcher(
            database,
            feature_plugin_manager,
            image_text_plugin_manager,
            classifier_plugin_manager,
            indexer_plugin_manager,
            mapping_plugin_manager,
            aggregator=aggregator,
        )

        logging.info(f"Init done: {time.time() - start_time}")

        search_result = searcher(query)
        logging.info(f"Search done: {time.time() - start_time}")

        result = indexer_pb2.ListSearchResultReply()

        for e in search_result["entries"]:
            entry = result.entries.add()
            entry.id = e["id"]
            entry.padded = e["padded"]

            if "meta" in e:
                meta_to_proto(entry.meta, e["meta"])
            if "origin" in e:
                meta_to_proto(entry.origin, e["origin"])
            if "classifier" in e:
                classifier_to_proto(entry.classifier, e["classifier"])
            if "feature" in e:
                feature_to_proto(entry.feature, e["feature"])
            if "coordinates" in e:
                entry.coordinates.extend(e["coordinates"])
            if "distance" in e:
                entry.distance = e["distance"]
            if "cluster" in e:
                entry.cluster = e["cluster"]
            if "collection" in e:
                entry.collection.id = e["collection"]["id"]
                entry.collection.name = e["collection"]["name"]
                entry.collection.is_public = e["collection"]["is_public"]

        if "aggregations" in search_result:
            for e in search_result["aggregations"]:
                aggr = result.aggregate.add()
                aggr.field_name = e["field_name"]

                for y in e["entries"]:
                    value_field = aggr.entries.add()
                    value_field.key = y["name"]
                    value_field.int_val = y["value"]

        result_dict = MessageToDict(result)

        return result_dict
    except Exception as e:
        logging.error(f"Indexer: {repr(e)}")
        exc_type, exc_value, exc_traceback = sys.exc_info()

        traceback.print_exception(
            exc_type,
            exc_value,
            exc_traceback,
            limit=2,
            file=sys.stdout,
        )

    return None


def read_config(path):
    with open(path, "r") as f:
        return json.load(f)


def parse_args():
    parser = argparse.ArgumentParser(description="")

    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument("-i", "--input_path")
    parser.add_argument("-o", "--output_path")
    parser.add_argument("--image_path")
    parser.add_argument("-c", "--config", help="config path")
    args = parser.parse_args()
    return args


def main():
    args = parse_args()

    if args.config is not None:
        config = read_config(args.config)
    else:
        config = {}

    image_text_manager = ImageTextPluginManager(configs=config.get("image_text", []))
    image_text_manager.find()

    indexer_manager = IndexerPluginManager(configs=config.get("indexes", []))
    indexer_manager.find()

    with open(args.input_path, "r") as f_in:
        results = []
        for line in f_in:

            print(line.strip())
            feature_search = []
            feature_results = list(image_text_manager.run([line]))[0]
            for plugin in feature_results["plugins"]:
                # print(dir(plugin))
                for anno in plugin._annotations[0]:

                    feature = list(anno.feature.feature)
                    feature_search.append(
                        {
                            "plugin": plugin._plugin.name,
                            "type": anno.feature.type,
                            "value": feature,
                            "weight": 1.0,
                        }
                    )
                    # print(feature)
                # feature_results.feature
                # feature = list(anno.feature.feature)
            if len(feature_search) > 0:
                entries_feature = list(
                    indexer_manager.search(
                        feature_search,
                        # collections=query["collections"],
                        # include_default_collection=query["include_default_collection"],
                        # size=500,
                    )
                )
                print(entries_feature)
                results.extend(entries_feature)
    with open(args.output_path, "w") as f:
        # f.writelines(list(set(results)))
        for x in list(set(results)):
            # print(x)
            f.write(x+'\n')
    # list(set(results)))
    # print(len(list(set(results))))
            # return
    return 0


if __name__ == "__main__":
    sys.exit(main())
