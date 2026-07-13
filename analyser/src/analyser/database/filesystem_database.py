import os
from tibava_interface.collection_pb2 import CollectionItem


class FilesystemCollectionDatabase:
    def __init__(self, dir_path):
        self.dir_path = dir_path

    def save(self, item: CollectionItem):
        output_dir = os.path.join(self.dir_path, item.id[0:2], item.id[2:4])
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, f"{item.id}.proto"), "wb") as f:
            f.write(item.SerializeToString())

    def load(self, id: str) -> CollectionItem:
        item_dir = os.path.join(self.dir_path, item.id[0:2], item.id[2:4])

        item = CollectionItem()

        # Read the existing address book.
        with open(os.path.join(item_dir, f"{id}.proto"), "rb") as f:
            item.ParseFromString(f.read())

        return item
