import logging
import json


logger = logging.getLogger(__name__)


def unflat_dict(data_dict, parse_json=False):
    result_map = {}
    if parse_json:
        data_dict_new = {}
        for k, v in data_dict.items():
            try:
                data = json.loads(v)
                data_dict_new[k] = data
            except:
                data_dict_new[k] = v
        data_dict = data_dict_new
    for k, v in data_dict.items():
        path = k.split(".")
        prev = result_map
        for p in path[:-1]:
            if p not in prev:
                prev[p] = {}
            prev = prev[p]
        prev[path[-1]] = v
    return result_map


def flat_dict(data_dict, parse_json=False):
    result_map = {}
    for k, v in data_dict.items():
        if isinstance(v, dict):
            embedded = flat_dict(v)
            for s_k, s_v in embedded.items():
                s_k = f"{k}.{s_k}"
                if s_k in result_map:
                    logger.error(f"flat_dict: {s_k} alread exist in output dict")

                result_map[s_k] = s_v
            continue

        if k not in result_map:
            result_map[k] = []
        result_map[k] = v
    return result_map


import hashlib


def flat_dict(data_dict, parse_json=False):
    result_map = {}
    for k, v in data_dict.items():
        if isinstance(v, dict):
            embedded = flat_dict(v)
            for s_k, s_v in embedded.items():
                s_k = f"{k}.{s_k}"
                if s_k in result_map:
                    logger.error(f"flat_dict: {s_k} alread exist in output dict")

                result_map[s_k] = s_v
            continue

        if k not in result_map:
            result_map[k] = []
        result_map[k] = v
    return result_map


def get_hash_for_plugin(plugin, parameters=[], inputs=[]):
    hashlib.sha256(
        json.dumps(
            flat_dict(
                {
                    "plugin": plugin,
                    "parameters": parameters,
                    "inputs": inputs,
                }
            )
        ).encode()
    )
