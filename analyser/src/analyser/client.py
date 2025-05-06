import os
import sys
import re
import argparse
import logging
import hashlib
import mimetypes
from typing import Iterator, Any

import grpc
import json
from interface import analyser_pb2
from interface import analyser_pb2_grpc

from data import DataManager

import time
import msgpack


def parse_args():
    parser = argparse.ArgumentParser(description="")

    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument("-d", "--debug", action="store_true", help="debug output")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=50051, type=int)
    parser.add_argument(
        "-t",
        "--task",
        choices=[
            "list_plugins",
            "upload_file",
            "run_plugin",
            "download_data",
            "get_plugin_status",
        ],
    )
    parser.add_argument("--path")
    parser.add_argument("--plugin")
    parser.add_argument("--inputs")
    parser.add_argument("--parameters")
    parser.add_argument("--id")
    args = parser.parse_args()
    return args


class AnalyserClient:
    def __init__(self, host, port, manager=None):
        self.host = host
        self.port = port
        if manager is None:
            self.manager = DataManager()
        else:
            self.manager = manager
        self.channel = grpc.insecure_channel(f"{self.host}:{self.port}")

    def list_plugins(self):
        stub = analyser_pb2_grpc.AnalyserStub(self.channel)

        response = stub.list_plugins(analyser_pb2.ListPluginsRequest())

        return response

    def upload_data(self, data):
        stub = analyser_pb2_grpc.AnalyserStub(self.channel)

        def generate_requests(data, chunk_size=128 * 1024):
            # data_manager.save(data)
            # data = data_manager.load(data.id)
            """Lazy function (generator) to read a file piece by piece.
            Default chunk size: 1k"""
            for x in self.manager.dump_to_stream(data.id):
                yield analyser_pb2.UploadDataRequest(
                    id=data.id, data_encoded=x["data_encoded"]
                )

        response = stub.upload_data(generate_requests(data))

        if response.success:
            return response.id

        logging.error("Error while copying data ...")
        return None

    def upload_file(self, path, id=None):
        ext = os.path.splitext(path)[-1][1:]
        filename = os.path.basename(path)

        mimetype = mimetypes.guess_type(path)
        if re.match(r"video/*", mimetype[0]):
            data_type = analyser_pb2.VIDEO_DATA
        if re.match(r"audio/*", mimetype[0]):
            data_type = analyser_pb2.AUDIO_DATA
        if re.match(r"image/*", mimetype[0]):
            data_type = analyser_pb2.IMAGES_DATA

        stub = analyser_pb2_grpc.AnalyserStub(self.channel)

        class RequestGenerator:
            def __init__(self, path, chunk_size=128 * 1024):
                self.chunk_size = chunk_size
                self.path = path
                self.hash_stream = None

            def __call__(self):
                self.hash_stream = hashlib.sha1()
                with open(self.path, "rb") as f:
                    while True:
                        data = f.read(self.chunk_size)
                        if not data:
                            break
                        self.hash_stream.update(data)
                        yield analyser_pb2.UploadFileRequest(
                            type=data_type,
                            data_encoded=data,
                            id=None,
                            ext=ext,
                            filename=filename,
                        )

            def hash(self):
                return self.hash_stream.hexdigest()

        try_count = 3
        while try_count > 0:
            generator = RequestGenerator(path)

            response = stub.upload_file(generator())

            if response.hash == generator.hash() and response.success:
                print(response.id)
                return response.id

            logging.warning("Retry to upload the data again ...")
            try_count -= 1

        logging.error("Error while copying data ...")
        return None

    def check_data(self, data_id):
        run_request = analyser_pb2.CheckDataRequest(id=data_id)

        stub = analyser_pb2_grpc.AnalyserStub(self.channel)

        response = stub.check_data(run_request)
        return response.exists

    def run_plugin(self, plugin, inputs, parameters):
        run_request = analyser_pb2.RunPluginRequest()
        run_request.plugin = plugin
        for i in inputs:
            x = run_request.inputs.add()
            x.name = i.get("name")
            x.id = i.get("id")

        for i in parameters:
            x = run_request.parameters.add()
            x.name = i.get("name")
            x.value = str(i.get("value"))
            if isinstance(i.get("value"), float):
                x.type = analyser_pb2.FLOAT_TYPE
            if isinstance(i.get("value"), int):
                x.type = analyser_pb2.INT_TYPE
            if isinstance(i.get("value"), str):
                x.type = analyser_pb2.STRING_TYPE
            if isinstance(i.get("value"), bool):
                x.type = analyser_pb2.BOOL_TYPE

        stub = analyser_pb2_grpc.AnalyserStub(self.channel)

        response = stub.run_plugin(run_request)

        if response.success:
            return response.id

        logging.error("Error while run plugin ...")
        return None

    def get_plugin_status(self, job_id):
        get_plugin_request = analyser_pb2.GetPluginStatusRequest(id=job_id)

        stub = analyser_pb2_grpc.AnalyserStub(self.channel)

        response = stub.get_plugin_status(get_plugin_request)

        return response

    def get_plugin_results(self, job_id, timeout=None):
        result = None
        start_time = time.time()
        while True:
            if timeout:
                if time.time() - start_time > timeout:
                    return None
            result = self.get_plugin_status(job_id)

            if result.status == analyser_pb2.GetPluginStatusResponse.WAITING:
                time.sleep(0.5)
                continue
            if result.status == analyser_pb2.GetPluginStatusResponse.RUNNING:
                time.sleep(0.5)
                continue
            elif result.status == analyser_pb2.GetPluginStatusResponse.ERROR:
                logging.error("Job is crashing")
                return
            elif result.status == analyser_pb2.GetPluginStatusResponse.DONE:
                break

        return result

    def download_data(self, data_id, output_path: str = None):
        download_data_request = analyser_pb2.DownloadDataRequest(id=data_id)

        stub = analyser_pb2_grpc.AnalyserStub(self.channel)

        response = stub.download_data(download_data_request)
        if output_path is None:
            manager = self.manager
        else:
            manager = DataManager(output_path)
        data, hash = manager.load_data_from_stream(response)
        return data

    def download_data_to_blob(self, data_id, output_path):
        download_data_request = analyser_pb2.DownloadDataRequest(id=data_id)

        stub = analyser_pb2_grpc.AnalyserStub(self.channel)

        response = stub.download_data(download_data_request)
        with open(os.path.join(output_path, f"{data_id}.bin"), "wb") as f:
            for x in response:
                f.write(msgpack.packb({"d": x.SerializeToString()}))

        return os.path.join(output_path, f"{data_id}.bin")


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
    client = AnalyserClient(args.host, args.port)

    if args.task == "list_plugins":
        result = client.list_plugins()

    if args.task == "upload_file":
        result = client.upload_file(args.path)

    if args.task == "run_plugin":
        result = client.run_plugin(
            args.plugin, json.loads(args.inputs), json.loads(args.parameters)
        )

    if args.task == "get_plugin_status":
        result = client.get_plugin_status(args.id)

    if args.task == "download_data":
        result = client.download_data(args.id, args.path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
