import glob
import json
import os
import shutil

import numpy as np
from sqlalchemy_utils import database_exists

from .config import DATA_FILES_PATH, RDF_DATABASE_URI
from sqlalchemy.orm import class_mapper


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


def load_data_from_file(file_path):
    print("File path:", file_path)
    x = np.load(file_path)
    return x


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
    file_path = os.path.join(DATA_FILES_PATH, "data_{}.npy".format(data_id))
    if os.path.exists(file_path):
        os.remove(file_path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    np.save(file_path, value)
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
    # Delete and create database
    reset_database()

    for file_path in glob.glob(os.path.join(DATA_FILES_PATH, "*")):
        if os.path.exists(file_path):
            os.remove(file_path)

    if not os.path.exists(DATA_FILES_PATH):
        os.makedirs(DATA_FILES_PATH)

    # Clear redis queues
    from .db import clear_redis_queues

    clear_redis_queues()


def convert_to_ndarray(x):
    if isinstance(x, str):
        x = np.array(json.loads(x))
        # print(type(x).__name__, '\n\n\n\n')
    elif (
        isinstance(x, list)
        or isinstance(x, tuple)
        or isinstance(x, int)
        or isinstance(x, float)
    ):
        x = np.array(x)
        # print('DTYPE    SECOND',type(x), '\n\n\n\n')

    return x


def parse_string(x):
    x = json.loads(x)


def convert_ndarray_to_str(x):
    return str(x.tolist())


def find_dtype(x):
    if isinstance(x, np.ndarray):
        return "ndarray"
    elif isinstance(x, int):
        return "int"
    elif isinstance(x, float):
        return "float"
    else:
        return None


def get_rank_dtype(data):
    rank = len(np.array(data).shape)

    if rank == 0:
        return rank, np.array(data).dtype.name
    elif rank == 1:
        return rank, np.array(data).dtype.name
    else:
        return rank, np.array(data).dtype.name


def get_op_stats(ops):

    pending_ops = 0
    computed_ops = 0
    computing_ops = 0
    failed_ops = 0

    for op in ops:
        if op.status == "pending":
            pending_ops += 1
        elif op.status == "computed":
            computed_ops += 1
        elif op.status == "computing":
            computing_ops += 1
        elif op.status == "failed":
            failed_ops += 1

    total_ops = len(ops)

    return {
        "total_ops": total_ops,
        "pending_ops": pending_ops,
        "computing_ops": computing_ops,
        "computed_ops": computed_ops,
        "failed_ops": failed_ops,
    }


def serialize(model):
    """
    db_object => python_dict
    """
    # first we get the names of all the columns on your model
    columns = [c.key for c in class_mapper(model.__class__).columns]
    # then we return their values in a dict
    return dict((c, getattr(model, c)) for c in columns)
