import logging
from typing import List
from fnmatch import fnmatch


from data import DataManager
from data.plugins.list_data import ListData
from interface.data_pb2 import Data


def data_list_to_proto_data(
    data_manager: DataManager, data_id: str, include_fields: List[str] | None = None
) -> List[Data] | None:
    if include_fields is None:
        include_fields = []

    results = []

    list_data = data_manager.load(data_id)
    if list_data is None:
        return None

    if isinstance(list_data, ListData)

    with data_manager.load(x["id"]) as list_data:
        for name, data in list_data:
            with data as data:
                # check if we should filter the results
                to_include = False
                if len(include_fields) == 0:
                    to_include = True

                for x in include_fields:
                    if fnmatch(name, x):
                        to_include = True

                if to_include:
                    # copy the data stored in Data to the proto response
                    pb_data = entry.data.add()
                    pb_data.CopyFrom(data.to_proto())
                    pb_data.name = name

                    data_type = pb_data.WhichOneof("data")

                    if data_type == "text":
                        if match := re.match(r"^(.*)\/_(.{2})$", name):
                            pb_data.name = match.group(1)
                            pb_data.text.language = match.group(2)
