import grpc
import uuid
import logging
from concurrent import futures

from tibava_interface import analyser_pb2, analyser_pb2_grpc


class AnalyserServicer(analyser_pb2_grpc.AnalyserServicer):
    def __init__(self, config, shared_object):
        self.config = config
        self.shared_object = shared_object
        # self.managers = init_plugins(config)

        self.add_points_process_pool = futures.ThreadPoolExecutor(
            max_workers=8, initargs=(config, shared_object)
        )
        # self.search_process_pool = futures.ProcessPoolExecutor(
        #     max_workers=8, initializer=SearchJob().init_worker, initargs=(config,)
        # )
        self.futures = []

        self.max_results = config.get("indexer", {}).get("max_results", 100)

    def analyse(self, request, context):
        # logging.info(f"[AnalyserServicer::analyse] Request {request}")

        logging.info(f"[AnalyserServicer::analyse] Request")
        results = self.shared_object.inference_server_manager(
            self.shared_object.compute_plugin_manager,
            request.plugin_run.plugin,
            request=request.plugin_run,
        )

        # results = request

        # results = list(self.managers["compute_manager"].run([image], [plugins], plugins=plugins))
        print(results, flush=True)

        return results

    def list_plugins(self, request, context):
        logging.info(f"[AnalyserServicer::list_plugins] Request {request}")
        reply = analyser_pb2.ListPluginsReply()

        for (
            plugin_name,
            plugin_class,
        ) in self.shared_object.compute_plugin_manager:
            pluginInfo = reply.plugin_infos.add()
            pluginInfo.name = plugin_name
            pluginInfo.type = str(plugin_class["compute_plugin"])

        return reply

    def indexing(self, request_iterator, context):
        logging.info(f"[Server] Indexing: start indexing")
        job_id = uuid.uuid4().hex

        with (
            self.managers["data_manager"].create_data("ImagesData") as images_data,
            self.managers["data_manager"].create_data("ListData") as list_data,
        ):
            for data_point in request_iterator:
                # TODO check if key already exists
                data_id = (
                    data_point.image.id if data_point.image.id else uuid.uuid4().hex
                )
                meta = meta_from_proto(data_point.image.meta)
                origin = meta_from_proto(data_point.image.origin)

                collection = {}

                if data_point.image.collection.id != "":
                    collection["id"] = data_point.image.collection.id
                    collection["name"] = data_point.image.collection.name
                    collection["is_public"] = data_point.image.collection.is_public

                index_data = {
                    # "image_data": data_point.image.encoded,
                    "meta": meta,
                    "origin": origin,
                    "collection": collection,
                }
                try:
                    image = iio.imread(data_point.image.encoded)
                except Exception as e:
                    yield analyser_pb2.IndexingReply(
                        status="error", id=data_id, indexing_job_id=job_id
                    )
                    logging.error(e)
                    continue

                yield analyser_pb2.IndexingReply(
                    status="ok", id=data_id, indexing_job_id=job_id
                )

                with list_data.create_data("MetaData") as meta_data:
                    meta_data.meta = index_data
                    meta_data.ref_id = data_id

                images_data.save_image(image, id=data_id)
        logging.error(images_data.id)

        #
        variable = {
            "future": None,
            "id": job_id,
            "object_id": images_data.id,
            "meta_id": list_data.id,
        }

        indexing_job = IndexingJob()
        indexing_job.init_worker(self.config)
        indexing_job(copy.deepcopy(variable))

        # future = self.indexing_process_pool.submit(
        #     IndexingJob(), copy.deepcopy(variable)
        # )
        # variable["future"] = future
        # self.futures.append(variable)

    def status(self, request, context):
        futures_lut = {x["id"]: i for i, x in enumerate(self.futures)}

        if request.id in futures_lut:
            job_data = self.futures[futures_lut[request.id]]
            done = job_data["future"].done()

            if not done:
                return analyser_pb2.StatusReply(status="running")

            result = job_data["future"].result()

            if result is None:
                return analyser_pb2.StatusReply(status="error")

            return analyser_pb2.StatusReply(status="done", indexing=result)

        return analyser_pb2.StatusReply(status="error")

    # def get(self, request, context):
    #     database = ElasticSearchDatabase(config=self.config.get("elasticsearch", {}))

    #     entry = database.get_entry(request.id)

    #     if entry is None:
    #         context.set_code(grpc.StatusCode.NOT_FOUND)
    #         context.set_details("Entry unknown")

    #         return analyser_pb2.GetReply()

    #     result = analyser_pb2.GetReply()
    #     result.id = entry["id"]

    #     if "meta" in entry:
    #         meta_to_proto(result.meta, entry["meta"])
    #     if "collection" in entry:
    #         logging.info(entry["collection"])
    #         result.collection.id = entry["collection"]["id"]
    #         result.collection.name = entry["collection"]["name"]
    #         result.collection.is_public = entry["collection"]["is_public"]
    #     if "origin" in entry:
    #         meta_to_proto(result.origin, entry["origin"])
    #     if "classifier" in entry:
    #         classifier_to_proto(result.classifier, entry["classifier"])
    #     if "feature" in entry:
    #         feature_to_proto(result.feature, entry["feature"])

    #     return result

    def search(self, request, context):
        logging.info(f"[Server] Search")
        job_id = uuid.uuid4().hex

        jsonObj = MessageToDict(request)
        logging.info(jsonObj)

        job_id = uuid.uuid4().hex
        variable = {
            "config": self.config,
            "future": None,
            "id": job_id,
            "request": jsonObj,
        }

        future = self.search_process_pool.submit(SearchJob(), copy.deepcopy(variable))
        variable["future"] = future
        self.futures.append(variable)

        return analyser_pb2.SearchReply(id=job_id)

    def list_search_result(self, request, context):
        futures_lut = {x["id"]: i for i, x in enumerate(self.futures)}
        logging.error(futures_lut)

        if request.id in futures_lut:
            job_data = self.futures[futures_lut[request.id]]
            done = job_data["future"].done()

            if not done:
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Still running")
                return analyser_pb2.ListSearchResultReply()
            try:
                result = job_data["future"].result()
                logging.error(result)
                result = result
                result = ParseDict(result, analyser_pb2.ListSearchResultReply())
            except Exception as e:
                logging.error(f"Indexer: {repr(e)}")
                logging.error(traceback.format_exc())
                result = None

            if result is None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details("Search error")
                return analyser_pb2.ListSearchResultReply()

            return result

        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details("Job unknown")

        return analyser_pb2.ListSearchResultReply()
