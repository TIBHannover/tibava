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

    args = parser.parse_args()
    return args


def read_input_data(path):
    data = []
    with open(path) as f:
        for line in f:
            data.append(json.loads(line))

    return data


def generate_statistic(input):
    stats = {}
    for x in input:
        stats.setdefault("count", 0)
        stats["count"] += 1
        for y in x["entries"]:
            language = y.get("lang", None)
            if language is not None and language != "en":
                continue
            if y["path"] == "meta/dimension/width":
                print(y)
            stats.setdefault(y["path"], 0)
            stats[y["path"]] += 1

    print(stats)


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
    input_data = read_input_data(args.input_path)
    generate_statistic(input_data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
