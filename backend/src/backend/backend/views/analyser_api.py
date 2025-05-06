# import json
# import logging
# import traceback


# from django.views import View
# from django.http import JsonResponse
# import tempfile
# import uuid
# import os

# from pathlib import Path

# from backend.utils import download_file, media_url_to_video

# from analyser.client import AnalyserClient
# from analyser.data import DataManager
# from analyser import analyser_pb2, analyser_pb2_grpc

# from django.views.decorators.csrf import csrf_exempt
# from django.http import FileResponse


# class AnalyserUploadFile(View):
#     def __init__(self):
#         self.config = {
#             "analyser_host": "localhost",
#             "analyser_port": 50051,
#         }

#     @csrf_exempt
#     def post(self, request):
#         try:
#             if request.method != "POST":
#                 logger.error("AnalyserUploadFile::wrong_method")
#                 return JsonResponse({"status": "error"})
#             tempdir = tempfile.mkdtemp()

#             video_id_uuid = uuid.uuid4()
#             video_id = video_id_uuid.hex
#             if "file" in request.FILES:
#                 output_dir = os.path.join(tempdir)

#                 download_result = download_file(
#                     output_dir=output_dir,
#                     output_name=video_id,
#                     file=request.FILES["file"],
#                     max_size=10 * 1024 * 1024 * 1024,
#                     extensions=(".mkv", ".mp4", ".ogv"),
#                 )

#                 if download_result["status"] != "ok":
#                     logger.error("AnalyserUploadFile::download_failed")
#                     return JsonResponse(download_result)

#                 client = AnalyserClient(self.config["analyser_host"], self.config["analyser_port"])

#                 # print(f"Start uploading", flush=True)
#                 data_id = client.upload_file(download_result["path"])
#                 print(f"{download_result['path']}")

#                 return JsonResponse({"status": "ok", "data_id": data_id})

#             return JsonResponse({"status": "error"})

#         except Exception as e:
#             print(e, flush=True)
#             logger.error(traceback.format_exc())
#             return JsonResponse({"status": "error"})

#     @classmethod
#     def as_view(cls):
#         return csrf_exempt(super(AnalyserUploadFile, cls).as_view())


# class AnalyserPluginRun(View):
#     def __init__(self):
#         self.config = {
#             "analyser_host": "localhost",
#             "analyser_port": 50051,
#         }

#     @csrf_exempt
#     def post(self, request):
#         print(request.POST)
#         try:
#             if request.method != "POST":
#                 logger.error("AnalyserUploadFile::wrong_method")
#                 return JsonResponse({"status": "error"})

#             try:
#                 body = request.body.decode("utf-8")
#             except (UnicodeDecodeError, AttributeError):
#                 body = request.body

#             try:
#                 data = json.loads(body)
#             except Exception as e:
#                 return JsonResponse({"status": "error", "type": "wrong_request_body"})

#             client = AnalyserClient(self.config["analyser_host"], self.config["analyser_port"])

#             # print(f"Start uploading", flush=True)
#             job_id = client.run_plugin(data.get("plugin"), data.get("inputs"), data.get("parameters"))
#             if job_id is None:
#                 return JsonResponse({"status": "error"})

#             return JsonResponse({"status": "ok", "job_id": job_id})

#         except Exception as e:
#             print(e, flush=True)
#             logger.error(traceback.format_exc())
#             return JsonResponse({"status": "error"})

#     @classmethod
#     def as_view(cls):
#         return csrf_exempt(super(AnalyserPluginRun, cls).as_view())


# class AnalyserPluginStatus(View):
#     def __init__(self):
#         self.config = {
#             "analyser_host": "localhost",
#             "analyser_port": 50051,
#         }

#     @csrf_exempt
#     def post(self, request):
#         print(request.POST)
#         try:
#             if request.method != "POST":
#                 logger.error("AnalyserUploadFile::wrong_method")
#                 return JsonResponse({"status": "error"})

#             try:
#                 body = request.body.decode("utf-8")
#             except (UnicodeDecodeError, AttributeError):
#                 body = request.body

#             try:
#                 data = json.loads(body)
#             except Exception as e:
#                 return JsonResponse({"status": "error", "type": "wrong_request_body"})

#             client = AnalyserClient(self.config["analyser_host"], self.config["analyser_port"])

#             # print(f"Start uploading", flush=True)
#             result = client.get_plugin_status(data.get("job_id"))
#             if result is None:
#                 return JsonResponse({"status": "error"})

#             if result.status == analyser_pb2.GetPluginStatusResponse.RUNNING:
#                 return JsonResponse({"status": "ok", "plugin_status": "running"})
#             elif result.status == analyser_pb2.GetPluginStatusResponse.ERROR:
#                 return JsonResponse({"status": "ok", "plugin_status": "error"})
#             elif result.status == analyser_pb2.GetPluginStatusResponse.DONE:
#                 outputs = [{"name": x.name, "id": x.id} for x in result.outputs]
#                 return JsonResponse({"status": "ok", "plugin_status": "done", "outputs": outputs})

#             return JsonResponse({"status": "ok", "plugin_status": "unknown"})

#         except Exception as e:
#             print(e, flush=True)
#             logger.error(traceback.format_exc())
#             return JsonResponse({"status": "error"})

#     @classmethod
#     def as_view(cls):
#         return csrf_exempt(super(AnalyserPluginStatus, cls).as_view())


# class AnalyserDownloadData(View):
#     def __init__(self):
#         self.config = {
#             "analyser_host": "localhost",
#             "analyser_port": 50051,
#         }

#     @csrf_exempt
#     def post(self, request):
#         print(request.POST)
#         try:
#             if request.method != "POST":
#                 logger.error("AnalyserUploadFile::wrong_method")
#                 return JsonResponse({"status": "error"})

#             try:
#                 body = request.body.decode("utf-8")
#             except (UnicodeDecodeError, AttributeError):
#                 body = request.body

#             try:
#                 data = json.loads(body)
#             except Exception as e:
#                 return JsonResponse({"status": "error", "type": "wrong_request_body"})

#             client = AnalyserClient(self.config["analyser_host"], self.config["analyser_port"])

#             tempdir = tempfile.mkdtemp()

#             output_dir = os.path.join(tempdir)
#             data_path = client.download_data_to_blob(data.get("data_id"), output_dir)
#             if data is None:
#                 return JsonResponse({"status": "error"})
#             response = FileResponse(open(data_path, "rb"))
#             response["Content-Type"] = "application/x-binary"
#             response["Content-Disposition"] = 'attachment; filename="{}.bin"'.format(
#                 data.get("data_id")
#             )  # You can set custom filename, which will be visible for clients.
#             return response

#         except Exception as e:
#             print(e, flush=True)
#             logger.error(traceback.format_exc())
#             return JsonResponse({"status": "error"})

#     @classmethod
#     def as_view(cls):
#         return csrf_exempt(super(AnalyserDownloadData, cls).as_view())
