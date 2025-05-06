import os

from django.conf import settings


def media_url_to_video(id, ext):
    # todo
    return "http://localhost" + settings.MEDIA_URL + id[0:2] + "/" + id[2:4] + "/" + id + ext


def media_path_to_video(id, ext):
    # todo
    return settings.MEDIA_ROOT + id[0:2] + "/" + id[2:4] + "/" + id + ext


def media_dir_to_video(id):
    # todo
    return settings.MEDIA_ROOT + id[0:2] + "/" + id[2:4] + "/"


# def media_url_to_image(id):
#     # todo
#     return "http://localhost:8000" + settings.MEDIA_URL + id[0:2] + "/" + id[2:4] + "/" + id + ".jpg"


# def media_url_to_preview(id):
#     # todo
#     return "http://localhost:8000" + settings.MEDIA_URL + id[0:2] + "/" + id[2:4] + "/" + id + "_m.jpg"


# def upload_url_to_image(id):
#     # todo
#     return "http://localhost:8000" + settings.UPLOAD_URL + id[0:2] + "/" + id[2:4] + "/" + id + ".jpg"


# def upload_url_to_preview(id):
#     # todo
#     return "http://localhost:8000" + settings.UPLOAD_URL + id[0:2] + "/" + id[2:4] + "/" + id + "_m.jpg"


# def upload_path_to_image(id):
#     # todo
#     return os.path.join(settings.UPLOAD_ROOT, id[0:2], id[2:4], id + ".jpg")
