import os
import re
import sys
import time
import imageio
import logging
import urllib.error
import urllib.request

from tqdm import tqdm
from multiprocessing import Pool

from .image import image_resize

from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def download_image(url, max_dim=1024, try_count=2):
    error = None
    while try_count > 0:
        try:
            request = urllib.request.Request(
                url=url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_3)"
                        " AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/48.0.2564.116 Safari/537.36"
                    )
                },
            )

            with urllib.request.urlopen(request, timeout=60) as response:
                image = imageio.imread(response.read(), pilmode="RGB")
                image = image_resize(image, max_dim=max_dim)

                return image

        except urllib.error.URLError as e:
            error = e
            time.sleep(1.0)
        except urllib.error.HTTPError as e:
            error = e
            time.sleep(1.0)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            error = e
            time.sleep(0.5)

        try_count -= 1
    logging.warning(f"Unable to download {url}: {error}")

    return None


def download_entry(
    entry, resolutions=[{"min_dim": 200, "suffix": "_m"}, {"suffix": ""}]
):
    if os.path.splitext(entry["url"])[1].lower()[1:] in [
        "svg",
        "djvu",
        "webm",
        "ogv",
        "gif",
        "pdf",
        "ogg",
        "oga",
        "mid",
    ]:
        return False

    image = download_image(entry["url"])

    if image is None:
        return False

    image_id = entry["id"]
    output_dir = os.path.dirname(entry["file_path"])
    os.makedirs(output_dir, exist_ok=True)

    for res in resolutions:
        if "min_dim" in res:
            new_image = image_resize(image, min_dim=res["min_dim"])
        else:
            new_image = image

        image_output_file = os.path.join(output_dir, f"{image_id}{res['suffix']}.jpg")
        imageio.imwrite(image_output_file, new_image)

    image_output_file = os.path.abspath(os.path.join(output_dir, f"{image_id}.jpg"))

    return True


def _download_entry(args):
    return download_entry(*args)


def download_entries(
    entries,
    resolutions=[{"min_dim": 200, "suffix": "_m"}, {"suffix": ""}],
):
    new_entries = []

    with Pool(40) as p:
        values = [(e, resolutions) for e in entries]

        for i, x in enumerate(
            tqdm(
                p.imap(_download_entry, values),
                desc="Downloading",
                total=len(entries),
            )
        ):
            if x is None:
                continue

            new_entries.append(x)

    return new_entries
