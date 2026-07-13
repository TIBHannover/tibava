import logging
import argparse
import sys
import json
from typing import Any, Generator, List, Dict, Union

from tqdm import tqdm
import uuid


def parse_args():
    parser = argparse.ArgumentParser(description="Indexing a set of images")

    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument("-d", "--debug", action="store_true", help="verbose output")

    parser.add_argument("-i", "--input-path")
    parser.add_argument("-o", "--output-path")

    args = parser.parse_args()
    return args


def read_input_data(path: str) -> Generator[Dict, Any, Any]:
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            yield d


class StringParser:
    def __init__(self, path: str, geo_path: str = None):
        self.path = path
        self.geo_path = geo_path

    def __call__(self, entry: Union[Dict, List]) -> List[Dict]:
        results = []
        if isinstance(entry, Dict):
            entry = [entry]

        for e in entry:
            results.append(
                {
                    "path": self.path,
                    "type": "string",
                    "value": e["label"],
                    "lang": e["lang"],
                }
            )

            if (
                self.geo_path
                and (lat := e.get("lat", None))
                and (lon := e.get("lon", None))
            ):
                results.append(
                    {
                        "path": self.geo_path,
                        "type": "geo",
                        "lat": float(lat),
                        "lon": float(lon),
                    }
                )

        return results


class URLParser:
    def __init__(self, path: str):
        self.path = path

    def __call__(self, entry: Union[Dict, List]) -> List[Dict]:
        results = []
        if isinstance(entry, str):
            entry = {"label": entry}

        if isinstance(entry, Dict):
            entry = [entry]

        for e in entry:
            results.append(
                {
                    "path": self.path,
                    "type": "url",
                    "url": e["label"],
                }
            )
        return results


class ImageParser:
    def __init__(self, path: str):
        self.path = path

    def __call__(self, entry: Union[Dict, List]) -> List[Dict]:
        results = []
        if isinstance(entry, Dict):
            entry = [entry]

        for e in entry:
            results.append(
                {
                    "path": self.path,
                    "type": "image",
                    "url": e["label"],
                }
            )
        return results


class TimeParser:
    def __init__(self, path: str):
        self.path = path

    def __call__(self, entry: Union[Dict, List]) -> List[Dict]:
        results = []
        if isinstance(entry, Dict):
            entry = [entry]

        for e in entry:
            results.append(
                {
                    "path": self.path,
                    "type": "time",
                    "value": e["label"],
                }
            )
        return results


class FloatParser:
    def __init__(self, path: str):
        self.path = path

    def __call__(self, entry: Union[Dict, List]) -> List[Dict]:
        results = []
        if isinstance(entry, Dict):
            entry = [entry]

        for e in entry:
            results.append(
                {
                    "path": self.path,
                    "type": "float",
                    "value": float(e["label"]),
                }
            )
        return results


mapping = {
    "genre": StringParser("meta/genre"),
    "id": URLParser("ref/url"),
    "image": ImageParser("image"),
    "instance of": StringParser("meta/instance_of"),
    "director": StringParser("meta/director"),
    "creator": StringParser("meta/creator"),
    "title": StringParser("meta/title"),
    "country of origin": StringParser(
        "meta/country_of_origin", "meta/country_of_origin/geo"
    ),
    "country": StringParser("meta/country", "meta/country/geo"),
    "location": StringParser("meta/location", "meta/location/geo"),
    "start time": TimeParser("meta/time/start"),
    "end time": TimeParser("meta/time/end"),
    "height": FloatParser("meta/dimension/height"),
    "width": FloatParser("meta/dimension/width"),
    "depicts": StringParser("meta/depicts", "meta/depicts/geo"),
    "made from material": StringParser("meta/made_from_material"),
    "main subject": StringParser("meta/main_subject", "meta/main_subject/geo"),
    "collection": StringParser("meta/collection", "meta/collection/geo"),
    "architect": StringParser("meta/architect"),
    "depicts Iconclass notation": StringParser("meta/iconclass"),
    "movement": StringParser("meta/movement"),
}


def parse_wikidata(entries: List[Dict]) -> Generator[Dict, Any, Any]:
    for entry in entries:
        result = {"id": uuid.uuid5(uuid.NAMESPACE_URL, entry["id"]).hex, "entries": []}

        try:
            keys_to_delete = []
            for key, value in entry.items():
                if key in mapping:
                    try:
                        result["entries"].extend(mapping[key](value))
                    except Exception as e:
                        print(e)
                        print(entry)

                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del entry[key]

            if len(entry) > 0:
                print(entry)
                exit()
        except Exception as e:
            print(e)
            print(entry)
            exit()
        yield result


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

    with open(args.output_path, "w") as f:
        for entry in tqdm(parse_wikidata(read_input_data(args.input_path))):
            f.write(json.dumps(entry) + " \n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
