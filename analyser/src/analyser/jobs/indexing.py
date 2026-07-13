import logging
import sys
import traceback
from packaging import version

from analyser.utils import image_normalize


from tibava_interface import analyser_pb2, common_pb2, data_pb2
from fnmatch import fnmatch

from typing import Dict
from analyser.shared_object import SharedObject


class IndexingJob:
    def __init__(self, shared_object: SharedObject, config: Dict = None):
        self.shared_object = shared_object
        if config is None:
            config = {}
        self.config = config

    def __call__(self, args):
        # TODO customize the indexing path and plugin behind it
        logging.error(args)

        collection_name = args.get("collection_name")

        collection_manager = self.shared_object.indexer_plugin_manager

        if collection_name not in collection_manager:
            logging.error(f"[IndexingJob] Unknown collection '{collection_name}'")
            return

        indexing_plugin_mappings = collection_manager.get_indexing_plugin_mappings(
            collection_name
        )

        payload_mapping = collection_manager.get_payload_mapping(collection_name)

        try:
            for i, point in enumerate(args["points_list"]):
                with self.shared_object.data_manager.load(point) as point:
                    logging.info(f"{i} {point.id}")

                    data_dict = {}
                    scalar_dict = {}
                    for name, data in point:
                        with data as data:
                            if data.type in ("BoolData", "FloatData", "IntData"):
                                data_dict.update({name: data.to_proto()})
                            if data.type in ("TextData"):
                                data_dict.update({name: data.to_proto()})
                            if data.type in ("ImageData"):
                                data_dict.update({name: data.to_proto()})
                            if data.type in ("GeoData"):
                                data_dict.update({name: data.to_proto()})

                            if hasattr(data, "to_scalar"):
                                scalar_dict.update({name: data.to_scalar()})

                    # extrect payload fields
                    meta_dict = {}
                    for field in payload_mapping.fields:
                        for name, data in scalar_dict.items():
                            if fnmatch(name, field):
                                meta_dict[name] = data

                    # map (name, data) list to the (index, plugin)
                    data_plugin_mapping = []
                    for indexing_plugin_mapping in indexing_plugin_mappings:
                        for field in indexing_plugin_mapping.fields:
                            for name, data in data_dict.items():
                                if fnmatch(name, field):
                                    data_plugin_mapping.append(
                                        (indexing_plugin_mapping, name, data)
                                    )

                    feature_dict = {}
                    feature_index_dict = {}
                    for data_plugin in data_plugin_mapping:
                        data = data_plugin[2]

                        index_name = data_plugin[0].index_name
                        feature_dict.setdefault(index_name, [])
                        feature_index_dict.setdefault(
                            "_feature_data_index/" + index_name, []
                        )

                        for k, v in data_plugin[0].input_mapping.items():
                            if fnmatch(data_plugin[1], k):
                                data.name = v

                        request = common_pb2.PluginRun(
                            plugin=data_plugin[0].compute_plugin,
                            inputs=[data],
                        )

                        results = self.shared_object.inference_server_manager(
                            self.shared_object.compute_plugin_manager,
                            compute_plugin_name=data_plugin[0].compute_plugin,
                            request=request,
                        )

                        if not results or len(results.results) <= 0:
                            logging.warning(f"No outputs from plugin ({data_plugin})")
                            continue

                        self.shared_object.collection_database.add_data_to_point(
                            point.id, results, name=index_name
                        )

                        # TODO multivector plugins
                        feature_vecs = list(results.results[0].result.feature.feature)
                        feature_dict[index_name].append(feature_vecs)

                        feature_index_dict["_feature_data_index/" + index_name].append(
                            data.id
                        )

                    collection_manager.add_points(
                        collection_name="default",
                        points=[
                            {
                                "id": point.id,
                                "meta": {**meta_dict, **feature_index_dict},
                                "features": feature_dict,
                            }
                        ],
                    )

            return
        except Exception as e:
            # raise e
            logging.error(f"[Analyser] {e}")
            exc_type, exc_value, exc_traceback = sys.exc_info()

            traceback.print_exception(
                exc_type,
                exc_value,
                exc_traceback,
                limit=2,
                file=sys.stdout,
            )
