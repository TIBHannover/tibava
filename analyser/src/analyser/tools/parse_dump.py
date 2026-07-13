import os
import sys
import re
import json
import argparse

import msgpack

def parse_args():
    parser = argparse.ArgumentParser(description="")

    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument("-i", "--input_path")
    parser.add_argument("-o", "--output_path")
    parser.add_argument("-u", "--update_all")
    parser.add_argument("-p", "--print", action="store_true")
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

    if args.print:
        with open(args.input_path, "rb") as f_in:
            unpacker = msgpack.Unpacker(f_in)
            print(json.dumps(next(unpacker), indent=2))
    
    if args.update_all is not None:
        update = json.loads(args.update_all)

        with open(args.input_path, "rb") as f_in, open(args.output_path, "wb") as f_out:
            for line in msgpack.Unpacker(f_in):
                d = line
                d = merge_dict(d, update)

                f_out.write(msgpack.packb(d))

    return 0


if __name__ == "__main__":
    sys.exit(main())