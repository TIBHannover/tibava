import grpc
import uuid
import copy
from concurrent import futures
import logging
import imageio.v3 as iio
import traceback

from tibava_interface import searcher_pb2, searcher_pb2_grpc
from google.protobuf.json_format import MessageToJson, MessageToDict, ParseDict
from analyser.jobs.search import SearchJob


class SearcherServicer(searcher_pb2_grpc.SearcherServicer):
    def __init__(self, config, shared_object):
        self.config = config
        self.shared_object = shared_object

        self.search_pool = futures.ThreadPoolExecutor()
        self.futures = []

        self.max_results = config.get("indexer", {}).get("max_results", 100)

    def analyse(self, request, context):
        logging.info(f"Received analyse request, plugins: {request.plugin}")

        results = self.managers["inference_server"](
            self.managers["compute_manager"], request.plugin, request
        )

        return results

    def list_plugins(self, request, context):
        reply = searcher_pb2.ListPluginsReply()

        for plugin_name, plugin_class in (
            self.managers["compute_manager"].plugins().items()
        ):
            pluginInfo = reply.plugins.add()
            pluginInfo.name = plugin_name

        return reply

    def status(self, request, context):
        futures_lut = {x["id"]: i for i, x in enumerate(self.futures)}

        if request.id in futures_lut:
            job_data = self.futures[futures_lut[request.id]]
            done = job_data["future"].done()

            if not done:
                return searcher_pb2.StatusReply(status="running")

            result = job_data["future"].result()

            if result is None:
                return searcher_pb2.StatusReply(status="error")

            return searcher_pb2.StatusReply(status="done", indexing=result)

        return searcher_pb2.StatusReply(status="error")

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
        # search_result = SearchJob(shared_object=self.shared_object)(
        #     copy.deepcopy(variable)
        # )
        future = self.search_pool.submit(
            SearchJob(shared_object=self.shared_object), copy.deepcopy(variable)
        )
        variable["future"] = future
        self.futures.append(variable)

        return searcher_pb2.SearchReply(id=job_id)

    def list_search_result(self, request, context):
        logging.info(f"[SearcherServicer::list_search_result] id:{request.id}")
        futures_lut = {x["id"]: i for i, x in enumerate(self.futures)}

        if request.id in futures_lut:
            job_data = self.futures[futures_lut[request.id]]
            done = job_data["future"].done()

            if not done:
                logging.info(
                    f"[SearcherServicer::list_search_result] id:{request.id} running"
                )
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Still running")
                return searcher_pb2.ListSearchResultReply()
            try:
                logging.info(
                    f"[SearcherServicer::list_search_result] id:{request.id} done"
                )
                result = job_data["future"].result()
                result = ParseDict(result, searcher_pb2.ListSearchResultReply())
            except Exception as e:
                logging.error(
                    f"[SearcherServicer::list_search_result] id:{request.id} error {repr(e)}"
                )
                logging.error(traceback.format_exc())
                result = None

            if result is None:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details("Search error")
                return searcher_pb2.ListSearchResultReply()

            return result

        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details("Job unknown")

        return searcher_pb2.ListSearchResultReply()
