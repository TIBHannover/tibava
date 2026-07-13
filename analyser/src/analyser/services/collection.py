import logging
import uuid
import copy
import grpc
import re

from tibava_interface import collection_pb2, collection_pb2_grpc
from jobs import IndexingJob
import imageio.v3 as iio
from concurrent import futures


class CollectionServicer(collection_pb2_grpc.CollectionServicer):
    def __init__(self, config, shared_object):
        self.config = config

        self.shared_object = shared_object

        self.add_points_process_pool = futures.ThreadPoolExecutor()
        self.futures = []

    def add(self, request, context):
        logging.info(f"Received analyse request, plugins: {request}")

        self.managers["indexer_manager"].create_collection(
            name=request.name,
            indexes=[{"name": x.name, "size": x.size} for x in request.indexes],
        )

        return collection_pb2.CollectionAddResponse()

    def delete(self, request, context):
        logging.info(f"Received analyse request, plugins: {request}")

        self.shared_object.indexer_plugin_manager.delete_collection(
            collection_name=request.name,
        )

        return collection_pb2.CollectionDeleteResponse()

    def list(self, request, context):
        logging.info(f"Received analyse request, plugins:")

        result = collection_pb2.CollectionListResponse()
        result.names.extend(
            self.shared_object.indexer_plugin_manager.list_collections()
        )

        return result

    def query(self, request, context):
        logging.info(f"Received analyse request, plugins: {request.plugin}")

        return

    def add_points(self, request_iterator, context):
        logging.info(f"Received analyse request, plugins")

        job_id = uuid.uuid4().hex

        point_ids = []
        collection_name = None

        for data_point in request_iterator:
            # TODO check if key already exists
            point_id = data_point.id if data_point.id else uuid.uuid4().hex

            point_ids.append(point_id)
            collection_name = data_point.collection_name

            with self.shared_object.data_manager.create_data(
                "ListData", data_id=point_id
            ) as list_data:
                for i, data in enumerate(data_point.data):
                    data_type = data.WhichOneof("data")

                    data_id = data.id if data.id else uuid.uuid4().hex

                    if data_type == "image":
                        with list_data.create_data(
                            "ImageData", data.name, data_id=data_id
                        ) as image_data:
                            image_data.ext = data.image.ext

                            image = iio.imread(data.image.content)
                            image_data.save_image(image)

                    elif data_type == "bool":
                        with list_data.create_data(
                            "BoolData", data.name, data_id=data_id
                        ) as bool_data:
                            bool_data.value = data.bool.value

                    elif data_type == "int":
                        with list_data.create_data(
                            "IntData", data.name, data_id=data_id
                        ) as int_data:
                            int_data.value = data.int.value

                    elif data_type == "float":
                        with list_data.create_data(
                            "FloatData", data.name
                        ) as float_data:
                            float_data.value = data.float.value

                    elif data_type == "text":
                        with list_data.create_data(
                            "TextData", data.name, data_id=data_id
                        ) as text_data:
                            text_data.text = data.text.text

                    elif data_type == "geo":
                        with list_data.create_data(
                            "GeoData", data.name, data_id=data_id
                        ) as geo_data:
                            geo_data.lat = data.geo.lat
                            geo_data.lon = data.geo.lon

                    else:
                        logging.warning(
                            f"[Collection::add_points] Data type '{data_type}' is not supported."
                        )

            self.shared_object.collection_database.add_point(list_data)

            yield collection_pb2.AddPointsReply(
                status="ok", id=data_id, indexing_job_id=job_id
            )

        #
        variable = {
            "future": None,
            "id": job_id,
            "points_list": point_ids,
            "collection_name": collection_name,
        }

        # indexing_job = IndexingJob()
        # indexing_job.init_worker(self.config)
        # indexing_job(copy.deepcopy(variable))

        future = self.add_points_process_pool.submit(
            IndexingJob(shared_object=self.shared_object), copy.deepcopy(variable)
        )
        variable["future"] = future
        self.futures.append(variable)

    def get(
        self, request: collection_pb2.GetRequest, context: grpc.ServicerContext
    ) -> collection_pb2.GetResponse:
        response = collection_pb2.GetResponse(id=request.id)
        with self.shared_object.data_manager.load(request.id) as list_data:
            for name, data in list_data:
                pb_data = response.data.add()
                pb_data.CopyFrom(data.to_proto())
                pb_data.name = name

                data_type = pb_data.WhichOneof("data")

                if data_type == "text":
                    if match := re.match(r"^(.*)\/_(.{2})$", name):
                        pb_data.name = match.group(1)
                        pb_data.text.language = match.group(2)

        return response
