import os
import sys
import re
import json
import argparse

import copy


def parse_args():
    parser = argparse.ArgumentParser(description="")

    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument("-i", "--input_path")
    parser.add_argument("-o", "--output_path")
    parser.add_argument("-u", "--update_all")
    args = parser.parse_args()
    return args


def merge_dict(origin, update):

    for k, v in update.items():
        if k in origin:
            if isinstance(origin[k], dict):
                update[k] = merge_dict(origin[k], v)

    origin.update(update)
    return origin


def main():
    args = parse_args()

    update = json.loads(args.update_all)

    with open(args.input_path, "r") as f_in, open(args.output_path, "w") as f_out:
        for line in f_in:
            d = json.loads(line)
            d = merge_dict(d, copy.deepcopy(update))

            f_out.write(json.dumps(d) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
