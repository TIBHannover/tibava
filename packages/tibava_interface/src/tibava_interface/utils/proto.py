import pickle
import numbers

import numpy as np


def meta_from_proto_old(proto):
    result_dict = {}

    for m in proto:
        field = m.WhichOneof("value")

        if field == "string_val":
            result_dict[m.key] = m.string_val
        if field == "int_val":
            result_dict[m.key] = m.int_val
        if field == "float_val":
            result_dict[m.key] = m.float_val

    return result_dict


def meta_to_proto_old(proto, data):
    for k, v in data.items():
        meta = proto.add()

        if isinstance(v, numbers.Integral):
            meta.int_val = v
            meta.key = k
        elif isinstance(v, numbers.Real):
            meta.float_val = v
            meta.key = k
        elif isinstance(v, str):
            meta.string_val = v
            meta.key = k

    return proto


def meta_from_proto(proto):
    result_list = []

    for m in proto:
        field = m.WhichOneof("value")

        if field == "string_val":
            result_list.append(
                {
                    "name": m.key,
                    "value_str": m.string_val,
                }
            )
        if field == "int_val":
            result_list.append(
                {
                    "name": m.key,
                    "value_int": m.int_val,
                    "value_str": str(m.int_val),
                }
            )
        if field == "float_val":
            result_list.append(
                {
                    "name": m.key,
                    "value_float": m.float_val,
                    "value_str": str(m.float_val),
                }
            )

    return result_list


def dict_from_proto(proto):
    result = {}

    for m in proto:
        field = m.WhichOneof("value")

        if field == "string_val":
            result.update({m.key: m.string_val})
        if field == "int_val":
            result.update({m.key: m.int_val})
        if field == "float_val":
            result.append({m.key: m.float_val})

    return result


def meta_to_proto(proto, data):
    for k, v in data.items():
        meta = proto.add()

        meta.key = k
        if isinstance(v, int):
            meta.int_val = v
        elif isinstance(v, float):
            meta.float_val = v
        else:
            meta.string_val = str(v)

    return proto


def classifier_from_proto(proto):
    result_list = []

    for c in proto:
        result_list.append(
            {
                "plugin": c.plugin,
                "annotations": [
                    {"name": a.concept, "value": a.prob} for a in c.concepts
                ],
            }
        )

    return result_list


def classifier_to_proto(proto, data):
    for c in data:
        classifier = proto.add()
        classifier.plugin = c["plugin"]

        for a in c["annotations"]:
            concept = classifier.concepts.add()
            concept.concept = a["name"]
            concept.type = a["type"]
            concept.prob = a["value"]

    return proto


def feature_from_proto(proto):
    result_list = []

    for f in proto:
        result_list.append(
            {
                "plugin": f.plugin,
                "annotations": [{"feature": list(f.feature), "type": f.type}],
            }
        )

    return result_list


def feature_to_proto(proto, data):
    for f in data:
        feature = proto.add()
        feature.plugin = f["plugin"]

        for a in f["annotations"]:
            if "value" in a:
                feature.feature.extend(a["value"])

            feature.type = a["type"]

    return proto


def suggestions_from_proto(proto):
    result_list = []

    for g in proto.groups:
        group_dict = {"group": g.group, "suggestions": list(g.suggestions)}

        result_list.append(group_dict)

    return result_list


def numpy_to_proto(proto, name, value, frame_number, timestamp):
    ENCODE_DTYPE_LUP = {
        np.dtype("float16"): indexer_pb2.DT_HALF,
        np.dtype("float32"): indexer_pb2.DT_FLOAT,
        np.dtype("float64"): indexer_pb2.DT_DOUBLE,
        np.dtype("int32"): indexer_pb2.DT_INT32,
        np.dtype("int64"): indexer_pb2.DT_INT64,
        np.dtype("uint8"): indexer_pb2.DT_UINT8,
        np.dtype("uint16"): indexer_pb2.DT_UINT16,
        np.dtype("uint32"): indexer_pb2.DT_UINT32,
        np.dtype("uint64"): indexer_pb2.DT_UINT64,
        np.dtype("int16"): indexer_pb2.DT_INT16,
        np.dtype("int8"): indexer_pb2.DT_INT8,
        np.dtype("object"): indexer_pb2.DT_STRING,
        np.dtype("bool"): indexer_pb2.DT_BOOL,
    }

    proto.name = name
    proto.frame_number = frame_number
    proto.timestamp = timestamp
    proto.dtype = ENCODE_DTYPE_LUP[value.dtype]
    proto.proto_content = pickle.dumps(value)
    proto.shape.extend(value.shape)

    return proto


def numpy_from_proto(proto):
    DECODE_DTYPE_LUP = {
        indexer_pb2.DT_HALF: np.float16,
        indexer_pb2.DT_FLOAT: np.float32,
        indexer_pb2.DT_DOUBLE: np.float64,
        indexer_pb2.DT_INT32: np.int32,
        indexer_pb2.DT_UINT8: np.uint8,
        indexer_pb2.DT_UINT16: np.uint16,
        indexer_pb2.DT_UINT32: np.uint32,
        indexer_pb2.DT_UINT64: np.uint64,
        indexer_pb2.DT_INT16: np.int16,
        indexer_pb2.DT_INT8: np.int8,
        indexer_pb2.DT_STRING: np.object,
        indexer_pb2.DT_INT64: np.int64,
        indexer_pb2.DT_BOOL: np.bool,
    }

    content = pickle.loads(proto.proto_content)
    content.reshape(proto.shape)

    return proto.name, content, proto.frame_number, proto.timestamp
