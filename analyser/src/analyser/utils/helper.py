import re


def read_chunk(iterator, chunksize=64):
    chunk = []
    for x in range(chunksize):
        try:
            chunk.append(next(iterator))
        except StopIteration:
            return chunk

    return chunk


def get_element(data_dict: dict, path: str, split_element: str = "."):
    if path is None:
        return data_dict

    if callable(path):
        elem = path(data_dict)

    if isinstance(path, str):
        elem = data_dict
        try:
            for x in path.strip(split_element).split(split_element):
                try:
                    x = int(x)
                    elem = elem[x]
                except ValueError:
                    elem = elem.get(x)
        except:
            pass

    if isinstance(path, (list, set)):
        elem = [get_element(data_dict, x) for x in path]

    return elem


def convert_name(name):
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
