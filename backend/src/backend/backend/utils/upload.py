import os

from pathlib import Path
from urllib import response
import requests

import mimetypes
import logging


logger = logging.getLogger(__name__)


def check_extension(filename: Path, extensions: list):
    if isinstance(filename, str):
        filename = Path(filename)
    extension = "".join(filename.suffixes)
    extension.lower()
    return extension in extensions


def download_file(file, output_dir, output_name=None, max_size=None, extensions=None):
    try:
        path = Path(file.name)
        ext = "".join(path.suffixes)
        if output_name is not None:
            output_path = os.path.join(output_dir, f"{output_name}{ext}")
        else:
            output_path = os.path.join(output_dir, f"{file.name}")

        if extensions is not None:
            if not check_extension(path, extensions):
                return {"status": "error", "type": "wrong_file_extension"}
        # TODO add parameter
        if max_size is not None and max_size > 0:
            if file.size > max_size:
                return {"status": "error", "type": "file_too_large"}

        os.makedirs(output_dir, exist_ok=True)

        with open(os.path.join(output_dir, output_path), "wb") as f:
            for i, chunk in enumerate(file.chunks()):
                f.write(chunk)

        return {"status": "ok", "path": Path(output_path), "origin": file.name}
    except Exception:
        logger.exception("Failed to download file")
        return {"status": "error", "type": "downloading_error"}
