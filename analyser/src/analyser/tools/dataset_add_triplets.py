import logging
import argparse
import sys
import os
import json
from typing import Any, Generator, List, Dict, Union

import uuid


def parse_args():
    parser = argparse.ArgumentParser(description="Indexing a set of images")

    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument("-d", "--debug", action="store_true", help="verbose output")

    parser.add_argument("-i", "--input-path")
    parser.add_argument("-t", "--triplets-path")
    parser.add_argument("-o", "--output-path")

    args = parser.parse_args()
    return args


def read_input_data(path):
    data = []
    with open(path) as f:
        for line in f:
            data.append(json.loads(line))

    return data


def read_triplets_data(path):
    data = {}
    for x in os.listdir(path):
        if x.split(".")[-1] != "json":
            continue
        triplet_path = os.path.join(path, x)
        triplet_item = "".join(x.split(".json")[:-1])
        with open(triplet_path) as f:
            data[triplet_item] = json.loads(f.read())

    return data


def add_triplets_to_entries(data, iconclass_dict):
    results = []
    concept_total = 0
    concept_tuple_total = 0
    triplets_total = 0
    failed_iconclass = []
    for point in data:
        new_entries = []
        for entry in point["entries"]:
            if entry["path"] == "image":
                entry["id"] = uuid.uuid5(uuid.NAMESPACE_URL, entry["url"]).hex

            if entry["path"] == "meta/iconclass":
                if entry["value"] not in iconclass_dict:
                    continue

                prediction = iconclass_dict[entry["value"]]

                concepts = prediction.get("concept_list")
                if concepts is None:
                    concepts = prediction.get("concepts")
                tuples = prediction.get("concept_tuples")
                if tuples is None:
                    tuples = prediction.get("tuples")
                triples = prediction.get("concept_triples")
                if triples is None:
                    triples = prediction.get("triples")
                try:
                    concept_total += len(concepts)
                    concept_tuple_total += len(tuples)
                    triplets_total += len(triples)

                except:
                    print("#######<")
                    print(prediction)
                    print("#######<")

                    failed_iconclass.append(entry["value"])

                    continue

                new_entries.append(
                    {
                        "path": "meta/iconclass/prediction",
                        "value": entry["value"],
                        "prediction": {
                            "concept_list": concepts,
                            "concept_tuples": tuples,
                            "concept_triples": triples,
                        },
                    }
                )

        results.append({**point, "entries": [*point["entries"], *new_entries]})

    print(len(list(set(failed_iconclass))))
    print("concept_total: ", concept_total)
    print("concept_tuple_total: ", concept_tuple_total)
    print("triplets_total: ", triplets_total)
    return results


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
    triplets = read_triplets_data(args.triplets_path)
    results = add_triplets_to_entries(input_data, triplets)

    with open(args.output_path, "w") as f:
        for line in results:
            f.write(json.dumps(line) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
