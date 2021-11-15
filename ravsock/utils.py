import glob
import json
import os
import shutil
import time

import numpy as np
from sqlalchemy_utils import database_exists

from .config import DATA_FILES_PATH, RDF_DATABASE_URI


def save_data_to_file(data_id, data):
    """
    Method to save data in a pickle file
    """
    file_path = os.path.join(DATA_FILES_PATH, "data_{}.json".format(data_id))

    if os.path.exists(file_path):
        os.remove(file_path)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        if isinstance(data, np.ndarray):
            data = data.tolist()
        json.dump(data, f)

    return file_path


def load_data_from_file():
    pass


def delete_data_file(data_id):
    file_path = os.path.join(DATA_FILES_PATH, "data_{}.json".format(data_id))
    if os.path.exists(file_path):
        os.remove(file_path)


class Singleton:
    def __init__(self, cls):
        self._cls = cls

    def Instance(self):
        try:
            return self._instance
        except AttributeError:
            self._instance = self._cls()
            return self._instance

    def __call__(self):
        raise TypeError("Singletons must be accessed through `Instance()`.")

    def __instancecheck__(self, inst):
        return isinstance(inst, self._cls)


def dump_data(data_id, value):
    """
    Dump ndarray to file
    """
    file_path = os.path.join(DATA_FILES_PATH, "data_{}.pkl".format(data_id))
    if os.path.exists(file_path):
        os.remove(file_path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    value.dump(file_path)
    return file_path


def copy_data(source, destination):
    try:
        shutil.copy(source, destination)
        print("File copied successfully.")
    # If source and destination are same
    except shutil.SameFileError:
        print("Source and destination represents the same file.")
    # If there is any permission issue
    except PermissionError:
        print("Permission denied.")
    # For other errors
    except:
        print("Error occurred while copying file.")


def reset_database():
    from .db import ravdb

    ravdb.drop_database()
    ravdb.create_database()
    ravdb.create_tables()


def create_database():
    from .db import ravdb
    while not database_exists(RDF_DATABASE_URI):
        ravdb.create_database()
        return True

    return False


def create_tables():
    from .db import ravdb
    if database_exists(RDF_DATABASE_URI):
        ravdb.create_tables()
        print("Tables created")


def reset():
    for file_path in glob.glob("files/*"):
        if os.path.exists(file_path):
            os.remove(file_path)

    if not os.path.exists("files"):
        os.makedirs("files")

    # Delete and create database
    reset_database()

    # Clear redis queues
    from .db import clear_redis_queues

    clear_redis_queues()
