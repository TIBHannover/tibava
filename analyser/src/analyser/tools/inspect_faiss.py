import os
import sys
import re
import argparse
import faiss
import msgpack
import logging


def load_index(indexes_dir, index):
    if isinstance(index, dict):
        index_id = index["id"]
    elif isinstance(index, str):
        index_id = index
    else:
        raise KeyError
    with open(os.path.join(indexes_dir, index_id + ".msg"), "rb") as f:
        index = msgpack.unpackb(f.read(), strict_map_key=False)

    index["index"] = faiss.read_index(os.path.join(indexes_dir, index_id + ".index"))
    return index


def load_collection(collections_dir, indexes_dir, collection):
    if isinstance(collection, dict):
        collection_id = collection["id"]
    elif isinstance(collection, str):
        collection_id = collection
    else:
        raise KeyError

    with open(os.path.join(collections_dir, collection_id + ".msg"), "rb") as f:
        collection = msgpack.unpackb(f.read(), strict_map_key=False)

    indexes = []
    for index in collection["indexes"]:
        indexes.append(load_index(indexes_dir, index))
    collection["indexes"] = indexes

    return collection


def parse_args():
    parser = argparse.ArgumentParser(description="")

    parser.add_argument("-p", "--path", help="verbose output")
    args = parser.parse_args()
    return args


def main():
    args = parse_args()

    if os.path.isdir(args.path):
        indexers = [os.path.join(args.path, x) for x in os.listdir(args.path) if re.match(r"^.*?\.msg$", x)]
        collections_dir = os.path.join(args.path, "collections")
        indexes_dir = os.path.join(args.path, "indexes")

    else:
        indexers = [args.path]
        collections_dir = os.path.join(os.path.dirname(args.path), "collections")
        indexes_dir = os.path.join(os.path.dirname(args.path), "indexes")

    newest_index = {"timestamp": 0.0}
    for x in indexers:
        with open(x, "rb") as f:
            try:
                data = msgpack.unpackb(f.read(), strict_map_key=False)
                if newest_index["timestamp"] < data["timestamp"]:
                    newest_index = data
            except:
                pass

    if "trained_collection" in newest_index:
        print("trained_collections: " + newest_index["trained_collection"])
        trained_collection = load_collection(collections_dir, indexes_dir, newest_index["trained_collection"])
        for index in trained_collection["indexes"]:
            print("\t" + index["id"] + " " + str(len(index["entries"])))
        print()

        print("default_collection: " + newest_index["default_collection"])
        print()
        # default_collection = load_collection(collections_dir, indexes_dir, newest_index["default_collection"])
        for collection in newest_index["collections"]:
            try:
                collection = load_collection(collections_dir, indexes_dir, collection)

                print(f"collection: {collection['id']} {collection['collection_id']}")
                # print("collection: " + str(]) + " " + str(collection["timestamp"]))
                for index in collection["indexes"]:
                    print(f"\t\t {index['id']} {index['type']} {len(index['entries'])}")
            except Exception as e:
                print(e)

    return 0


if __name__ == "__main__":
    sys.exit(main())