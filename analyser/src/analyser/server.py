import logging
import sys
import argparse
import time
import uuid

import yaml
import copy
import traceback
from concurrent import futures
import multiprocessing as mp

from google.protobuf.json_format import MessageToDict


import grpc


from interface import analyser_pb2, analyser_pb2_grpc
from inference_ray.plugin import AnalyserProgressCallback
from inference_ray.plugin import AnalyserPluginManager
from data import DataManager, Data
from utils.cache import get_hash_for_plugin
from utils.cache import CacheManager


class AnalyserCacheWrapper:
    def __init__(self, plugin: AnalyserPluginManager, cache: CacheManager):
        self.plugin = plugin
        self.cache = cache

    def plugin_status(self):
        return self.plugin.plugin_status()

    def plugins(self):
        return self.plugin._plugins

    def __call__(self, plugin, inputs, parameters, data_manager, callbacks):
        cached = False
        if self.cache:
            plugins = {x["plugin"]: x for x in self.plugin.plugin_status()}

            run_id = uuid.uuid4().hex[:4]
            if plugin not in plugins:
                logging.error(
                    f"[AnalyserCacheWrapper] {run_id} plugin: {plugin} not found"
                )
                return None

            plugin_to_run = plugins[plugin]
            results = {}
            logging.info(f"[AnalyserPluginManager] {run_id} Cache {plugin_to_run}")
            logging.info(
                f"[AnalyserPluginManager] {run_id} Cache {plugin_to_run['provides']}"
            )
            logging.info(
                f"[AnalyserPluginManager] {run_id} Cache {plugin_to_run['requires']}"
            )

            print(inputs, flush=True)
            cached = True
            for output in plugin_to_run["provides"]:
                result_hash = get_hash_for_plugin(
                    plugin=plugin,
                    output=output,
                    inputs=[x.id for _, x in inputs.items()],
                    parameters=parameters,
                    version=plugin_to_run["version"],
                    config={},  # plugin_to_run.config, TODO
                )

                logging.info(f"[AnalyserPluginManager] {run_id} Cache {result_hash}")
                cached_data = self.cache.get(result_hash)
                if cached_data is None:
                    cached = False
                    break

                logging.info(
                    f"[AnalyserPluginManager] {run_id} Cache get {result_hash} {cached_data}"
                )
                results[output] = cached_data.get("data_id")

        if not cached:
            logging.info(f"[AnalyserPluginManager] {run_id} plugin: {plugin_to_run}")
            logging.info(
                f"[AnalyserPluginManager] {run_id} data: {[{k:x.id} for k,x in inputs.items()]}"
            )
            logging.info(f"[AnalyserPluginManager] {run_id} parameters: {parameters}")
            results = self.plugin(
                plugin=plugin,
                inputs=inputs,
                data_manager=data_manager,
                parameters=parameters,
                callbacks=callbacks,
            )
            logging.info(
                f"[AnalyserPluginManager] {run_id} results: {[{k:x} for k,x in results.items()]}"
            )

        if self.cache:
            for output, data in results.items():
                data_id = data
                logging.error(f"#####DEBUG {data_id} {data} {isinstance(data, Data)}")

                result_hash = get_hash_for_plugin(
                    plugin=plugin,
                    output=output,
                    inputs=[x.id for _, x in inputs.items()],
                    parameters=parameters,
                    version=plugin_to_run["version"],
                    config={},  # plugin_to_run.config, TODO
                )
                logging.info(
                    f"[AnalyserPluginManager] Cache set {result_hash} {data_id}"
                )

                self.cache.set(
                    result_hash,
                    {"data_id": data_id, "time": time.time(), "type": "plugin_result"},
                )
        return results


def run_plugin(args):
    try:
        plugin_manager = globals().get("plugin_manager")
        data_manager = globals().get("data_manager")
        params = args.get("params")
        shared = args.get("shared")
        shared["progress"] = 0.0
        shared["status"] = analyser_pb2.GetPluginStatusResponse.RUNNING
        plugin_inputs = {}
        if "inputs" in params:
            for data_in in params.get("inputs"):
                data = data_manager.load(data_in.get("id"))
                if data is None:
                    logging.error(f"Data not found {data_in.get('id')}")
                    return []
                plugin_inputs[data_in.get("name")] = data

        plugin_parameters = {}
        if "parameters" in params:
            for parameter in params.get("parameters"):
                if parameter.get("type") == "FLOAT_TYPE":
                    plugin_parameters[parameter.get("name")] = float(
                        parameter.get("value")
                    )
                if parameter.get("type") == "INT_TYPE":
                    plugin_parameters[parameter.get("name")] = int(
                        parameter.get("value")
                    )
                if parameter.get("type") == "STRING_TYPE":
                    plugin_parameters[parameter.get("name")] = str(
                        parameter.get("value")
                    )
                if parameter.get("type") == "BOOL_TYPE":
                    if parameter.get("value") == "False":
                        plugin_parameters[parameter.get("name")] = False
                    else:
                        plugin_parameters[parameter.get("name")] = True

        callbacks = [AnalyserProgressCallback(shared)]
        results = plugin_manager(
            plugin=params.get("plugin"),
            inputs=plugin_inputs,
            parameters=plugin_parameters,
            data_manager=data_manager,
            callbacks=callbacks,
        )
        if results is None:
            logging.error(f"[Analyser] {params.get('plugin')} without results")
            return []

        result_map = []
        for key, id in results.items():
            # data_manager.save(data)
            result_map.append({"name": key, "id": id})

        return result_map
    except Exception as e:
        # raise e
        logging.error(f"[Analyser] {repr(e)}")
        exc_type, exc_value, exc_traceback = sys.exc_info()

        traceback.print_exception(
            exc_type,
            exc_value,
            exc_traceback,
            limit=2,
            file=sys.stdout,
        )


def init_plugins(config):
    data_dict = {}

    # building datamanager
    data_config = config.get("data", None)
    data_dir = None
    cache = None

    if data_config is not None:
        data_dir = data_config.get("data_dir", None)
        cache_config = data_config.get("cache")
        if cache_config is not None:
            cache = CacheManager.build(
                name=cache_config["type"], config=cache_config["params"]
            )

    data_manager = DataManager(data_dir=data_dir, cache=cache)
    data_dict["data_manager"] = data_manager

    ray_config = config.get("inference", {})
    if "type" not in ray_config:
        ray_config["type"] = "ray"

    if "params" not in ray_config:
        ray_config["params"] = {"host": "inference_ray", "port": 52365}

    manager = AnalyserCacheWrapper(
        AnalyserPluginManager(ray_config["params"]), cache=cache
    )
    data_dict["plugin_manager"] = manager

    return data_dict


def init_process(config):
    globals().update(init_plugins(config))


class Commune(analyser_pb2_grpc.AnalyserServicer):
    def __init__(self, config):
        self.config = config
        self.managers = init_plugins(config)
        self.process_pool = futures.ThreadPoolExecutor(
            max_workers=self.config.get("num_workers", 4),
            initializer=init_process,
            initargs=(config,),
        )
        self.shared_manager = mp.Manager()
        self.futures = []

        # self.max_results = config.get("Analyser", {}).get("max_results", 100)

    def list_plugins(self, request, context):
        reply = analyser_pb2.ListPluginsReply()

        # print(self.managers["plugin_manager"].plugin_status())

        for _, plugin_class in self.managers["plugin_manager"].plugins().items():
            reply.plugins.extend([analyser_pb2.PluginInfo(name=plugin_class._name)])

        return reply

    def upload_data(self, request_iterator, context):
        try:
            data, hash = self.managers["data_manager"].load_data_from_stream(
                request_iterator
            )
            data_id = None
            with data:
                data_id = data.id

            return analyser_pb2.UploadDataResponse(success=True, id=data_id, hash=hash)

        except Exception as e:
            logging.error(f"[Analyser] {repr(e)}")
            logging.error(traceback.format_exc())
            context.set_code(grpc.StatusCode.DATA_LOSS)
            context.set_details(f"Error transferring data with id {data.id}")
            return analyser_pb2.UploadDataResponse(success=False)

    def upload_file(self, request_iterator, context):
        # try:
        data, hash = self.managers["data_manager"].load_file_from_stream(
            request_iterator
        )

        # data, hash = self.managers["data_manager"].load_data_from_stream(request_iterator)

        return analyser_pb2.UploadDataResponse(success=True, id=data.id, hash=hash)

        # except Exception as e:
        #     logging.error(f"[Analyser] {repr(e)}")
        #     logging.error(traceback.format_exc())
        #     context.set_code(grpc.StatusCode.DATA_LOSS)
        #     context.set_details(f"Error transferring data with id {data.id}")
        #     return analyser_pb2.UploadDataResponse(success=False)

    def check_data(self, request, context):
        try:
            data = self.managers["data_manager"].check(request.id)
            if data is not None:
                return analyser_pb2.CheckDataResponse(exists=True)
            return analyser_pb2.CheckDataResponse(exists=False)

        except Exception as e:
            logging.error(f"[Analyser] {repr(e)}")
            logging.error(traceback.format_exc())
            return analyser_pb2.CheckDataResponse(exists=False)

    def run_plugin(self, request, context):
        # if request.plugin not in self.managers["plugin_manager"].plugins():
        #     return analyser_pb2.RunPluginResponse(success=False)

        job_id = uuid.uuid4().hex
        variable = {
            "params": MessageToDict(request),
            "config": self.config,
            "future": None,
            "id": job_id,
        }
        process_args = copy.deepcopy(variable)

        d = self.shared_manager.dict()
        d["progress"] = 0.0
        d["status"] = analyser_pb2.GetPluginStatusResponse.WAITING
        variable["shared"] = d
        process_args["shared"] = d
        future = self.process_pool.submit(run_plugin, process_args)
        variable["future"] = future
        self.futures.append(variable)

        return analyser_pb2.RunPluginResponse(success=True, id=job_id)

    def get_plugin_status(self, request, context):
        futures_lut = {x["id"]: i for i, x in enumerate(self.futures)}
        response = analyser_pb2.GetPluginStatusResponse()
        if request.id in futures_lut:
            job_data = self.futures[futures_lut[request.id]]
            done = job_data["future"].done()

            status = job_data["shared"].get(
                "status", analyser_pb2.GetPluginStatusResponse.UNKNOWN
            )
            response.status = status

            progress = job_data["shared"].get("progress", 0.0)
            response.progress = progress
            if not done:
                return response

            try:
                results = job_data["future"].result()

                if results is None:
                    response.status = analyser_pb2.GetPluginStatusResponse.ERROR
                    return response
                for k in results:
                    output = response.outputs.add()
                    output.name = k["name"]
                    output.id = k["id"]

            except Exception as e:
                logging.error(f"[Analyser] {repr(e)}")
                logging.error(traceback.format_exc())
                logging.error(traceback.print_stack())

                response.status = analyser_pb2.GetPluginStatusResponse.ERROR
                return response

            response.status = analyser_pb2.GetPluginStatusResponse.DONE
            return response
        response.status = analyser_pb2.GetPluginStatusResponse.UNKNOWN

        return response

    def download_data(self, request, context):
        try:
            for x in self.managers["data_manager"].dump_to_stream(request.id):
                yield analyser_pb2.DownloadDataResponse(
                    id=x["id"], data_encoded=x["data_encoded"]
                )

        except Exception as e:
            logging.error(f"[Analyser] {repr(e)}")
            logging.error(traceback.format_exc())
            context.set_code(grpc.StatusCode.DATA_LOSS)
            context.set_details(f"Error transferring data with id {request.id}")
            return analyser_pb2.DownloadDataResponse()


class Server:
    def __init__(self, config):
        self.config = config

        self.commune = Commune(config)

        pool = futures.ThreadPoolExecutor(max_workers=10)

        self.server = grpc.server(
            pool,
            options=[
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )
        analyser_pb2_grpc.add_AnalyserServicer_to_server(
            self.commune,
            self.server,
        )

        grpc_config = config.get("grpc", {})
        port = grpc_config.get("port", 50051)
        self.server.add_insecure_port(f"[::]:{port}")

    def run(self):
        logging.info("[Server] starting")
        self.server.start()
        logging.info("[Server] ready")

        try:
            while True:
                num_jobs = len(self.commune.futures)
                num_jobs_done = len(
                    [x for x in self.commune.futures if x["future"].done()]
                )
                time.sleep(10)
        except KeyboardInterrupt:
            self.server.stop(0)


def read_config(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def parse_args():
    parser = argparse.ArgumentParser(description="")

    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument("-d", "--debug", action="store_true", help="debug output")
    parser.add_argument("-c", "--config", help="config path")
    parser.add_argument("--port", type=int, help="port")
    parser.add_argument("--host", help="host")
    parser.add_argument("--data_dir", help="data dir")
    parser.add_argument("--no_cache", action="store_true", help="disable cache")
    parser.add_argument("--cache_valkey_host", help="valkey cache host")
    parser.add_argument("--cache_valkey_port", type=int, help="valkey cache port")
    parser.add_argument("--num_workers", type=int, help="number of workers")
    parser.add_argument("--inference_ray_host", help="inference ray host")
    parser.add_argument("--inference_ray_port", type=int, help="inference ray port")
    parser.add_argument(
        "--inference_ray_status_port", type=int, help="inference ray port"
    )

    args = parser.parse_args()

    return args


def main():
    args = parse_args()

    level = logging.ERROR
    if args.debug:
        level = logging.DEBUG
    elif args.verbose:
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

    if args.port:
        if "grpc" not in config:
            config["grpc"] = {}
        config["grpc"]["port"] = args.port

    if args.host:
        if "grpc" not in config:
            config["grpc"] = {}
        config["grpc"]["host"] = args.host

    if args.data_dir:
        if "data" not in config:
            config["data"] = {}
        config["data"]["data_dir"] = args.data_dir

    if args.no_cache:
        if "data" not in config:
            config["data"] = {}
        config["data"]["cache"] = None

    if args.cache_valkey_host:
        if "data" not in config:
            config["data"] = {}
        if "cache" not in config["data"]:
            config["data"]["cache"] = {"type": "valkey", "params": {}}
        config["data"]["cache"]["params"]["host"] = args.cache_valkey_host

    if args.cache_valkey_port:
        if "data" not in config:
            config["data"] = {}
        if "cache" not in config["data"]:
            config["data"]["cache"] = {"type": "valkey", "params": {}}
        config["data"]["cache"]["params"]["port"] = args.cache_valkey_port

    if args.inference_ray_host:
        if "inference" not in config:
            config["inference"] = {
                "type": "ray",
                "params": {"host": "inference_ray", "status_port": 52365, "port": 8000},
            }
        if "params" not in config["inference"]:
            config["inference"]["params"] = {
                "host": "inference_ray",
                "status_port": 52365,
                "port": 8000,
            }
        config["inference"]["params"]["host"] = args.inference_ray_host

    if args.inference_ray_status_port:
        if "inference" not in config:
            config["inference"] = {
                "type": "ray",
                "params": {"host": "inference_ray", "status_port": 52365, "port": 8000},
            }
        if "params" not in config["inference"]:
            config["inference"]["params"] = {
                "host": "inference_ray",
                "status_port": 52365,
                "port": 8000,
            }
        config["inference"]["params"]["status_port"] = args.inference_ray_status_port

    if args.inference_ray_port:
        if "inference" not in config:
            config["inference"] = {
                "type": "ray",
                "params": {"host": "inference_ray", "status_port": 52365, "port": 8000},
            }
        if "params" not in config["inference"]:
            config["inference"]["params"] = {
                "host": "inference_ray",
                "status_port": 52365,
                "port": 8000,
            }
        config["inference"]["params"]["port"] = args.inference_ray_port

    if args.num_workers:
        config["num_workers"] = args.num_workers

    server = Server(config)
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
