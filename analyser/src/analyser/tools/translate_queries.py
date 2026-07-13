import os
import sys
import re
import argparse
import torch
import msgpack
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


def parse_args():
    parser = argparse.ArgumentParser(description="")

    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument("-m", "--model", default="Helsinki-NLP/opus-mt-de-en")
    parser.add_argument("-i", "--input_path")
    parser.add_argument("-o", "--output_path")
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model)

    model.to(device)
    model.eval()
    with open(args.input_path, "r") as f_in:
        with open(args.output_path, "w") as f_out:
            for sample in f_in:

                tokens = tokenizer([sample], return_tensors="pt")

                output_tokens = model.generate(**tokens)
                outputs = tokenizer.batch_decode(output_tokens.to("cpu"), skip_special_tokens=True)
                f_out.write(outputs[0] + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
