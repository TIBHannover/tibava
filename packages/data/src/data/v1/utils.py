import os
import uuid


def create_data_path(data_dir, data_id, file_ext):
    os.makedirs(os.path.join(data_dir, data_id[0:2], data_id[2:4]), exist_ok=True)
    data_path = os.path.join(data_dir, data_id[0:2], data_id[2:4], f"{data_id}.{file_ext}")
    return data_path


def generate_id():
    return uuid.uuid4().hex
