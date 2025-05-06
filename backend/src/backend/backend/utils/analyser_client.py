import time
import logging

import grpc

from analyser.client import AnalyserClient
from interface import analyser_pb2
from interface import analyser_pb2_grpc
from backend.models import PluginRun
from backend.utils import RetryOnRpcErrorClientInterceptor, ExponentialBackoff


logger = logging.getLogger(__name__)


def analyser_status_to_task_status(analyser_status):
    if analyser_status == analyser_pb2.GetPluginStatusResponse.WAITING:
        return PluginRun.STATUS_WAITING
    if analyser_status == analyser_pb2.GetPluginStatusResponse.RUNNING:
        return PluginRun.STATUS_RUNNING
    if analyser_status == analyser_pb2.GetPluginStatusResponse.ERROR:
        return PluginRun.STATUS_ERROR
    return None


class TaskAnalyserClient(AnalyserClient):
    def __init__(self, *args, plugin_run_db=None, timeout=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_run_db = plugin_run_db
        self.timeout = timeout
        self.host = kwargs.get("host")
        self.port = kwargs.get("port")

        interceptors = (
            RetryOnRpcErrorClientInterceptor(
                max_attempts=4,
                sleeping_policy=ExponentialBackoff(
                    init_backoff_ms=100, max_backoff_ms=1600, multiplier=2
                ),
                status_for_retry=(grpc.StatusCode.UNAVAILABLE,),
            ),
        )

        self.channel = grpc.intercept_channel(
            grpc.insecure_channel(
                f"{self.host}:{self.port}",
                options=[
                    ("grpc.max_send_message_length", 50 * 1024 * 1024),
                    ("grpc.max_receive_message_length", 50 * 1024 * 1024),
                ],
            ),
            *interceptors,
        )

    def list_plugins(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().list_plugins(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logger.error(
                f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}"
            )
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def upload_data(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().upload_data(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logger.error(
                f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}"
            )
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def upload_file(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().upload_file(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logger.error(
                f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}"
            )
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def run_plugin(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().run_plugin(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logger.error(
                f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}"
            )
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def get_plugin_status(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().get_plugin_status(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logger.error(
                f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}"
            )
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def download_data(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().download_data(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logger.error(
                f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}"
            )
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    def download_data_to_blob(self, *args, **kwargs):
        plugin_run_db = self.plugin_run_db
        try:
            return super().download_data_to_blob(*args, **kwargs)
        except grpc.RpcError as rpc_error:
            logger.error(
                f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}"
            )
            if plugin_run_db:
                plugin_run_db.status = PluginRun.STATUS_ERROR
                plugin_run_db.save()
        return None

    # 24 hours timeout
    def get_plugin_results(
        self, job_id, plugin_run_db=None, status_fn=None, timeout=86400
    ):
        plugin_run_db = (
            plugin_run_db if plugin_run_db is not None else self.plugin_run_db
        )

        result = None

        start_time = time.time()
        if status_fn is None:
            status_fn = analyser_status_to_task_status
        while True:
            if timeout:
                if time.time() - start_time > timeout:
                    logger.error(f"Timeout")
                    if plugin_run_db:
                        plugin_run_db.status = PluginRun.STATUS_ERROR
                        plugin_run_db.save()
                    return None
            try:
                result = self.get_plugin_status(job_id)
            except grpc.RpcError as rpc_error:
                logger.error(
                    f"GRPC error: code={rpc_error.code()} message={rpc_error.details()}"
                )
                if plugin_run_db:
                    plugin_run_db.status = PluginRun.STATUS_ERROR
                    plugin_run_db.save()

                return None
            if result is None:
                logger.error(f"GRPC error: not valid return Code")
                if plugin_run_db:
                    plugin_run_db.status = PluginRun.STATUS_ERROR
                    plugin_run_db.save()

                return None

            if plugin_run_db is not None:
                status = status_fn(result.status)
                if status is not None:
                    plugin_run_db.status = status

                plugin_run_db.save()

            if result.status == analyser_pb2.GetPluginStatusResponse.UNKNOWN:
                logger.error("Job is unknown by the analyser")
                return
            elif result.status == analyser_pb2.GetPluginStatusResponse.WAITING:
                pass
            elif result.status == analyser_pb2.GetPluginStatusResponse.RUNNING:
                pass
            elif result.status == analyser_pb2.GetPluginStatusResponse.ERROR:
                logger.error("Job is crashing")
                return
            elif result.status == analyser_pb2.GetPluginStatusResponse.DONE:
                break
            time.sleep(1.0)

        return result
