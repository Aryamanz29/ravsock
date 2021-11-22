import json
import os

from aiohttp import web
from sqlalchemy.orm import class_mapper

from .config import BASE_DIR
from .db import ravdb
from .utils import (
    dump_data,
    copy_data,
    convert_str_to_ndarray,
    load_data_from_file,
    convert_ndarray_to_str,
)


# from ravop.core import t

# ----- Utils -----


def db_model_to_dict(obj):
    obj1 = obj.__dict__
    del obj1["_sa_instance_state"]
    del obj1["created_at"]
    return obj1


def serialize(model):
    """
    db_object => python_dict
    """
    # first we get the names of all the columns on your model
    columns = [c.key for c in class_mapper(model.__class__).columns]
    # then we return their values in a dict
    return dict((c, getattr(model, c)) for c in columns)


# ------ OPS ENDPOINTS ------

# We can define aiohttp endpoints just as we normally would with no change
async def index(request):
    with open("index.html") as f:
        return web.Response(text=f.read(), content_type="text/html")


async def op_create(request):
    # http://localhost:9999/op/create/?name=None&graph_id=None&node_type=input&inputs=null&outputs=[1]&op_type=other&operator=linear&status=computed&params={}
    """
    payload = { str : str }
    """
    try:

        data = await request.json()

        if len(data.keys()) == 0:
            return web.Response(
                text=str({"message": "Invalid parameters"}),
                content_type="text/html",
                status=400,
            )

        op = ravdb.create_op(**data)
        op_dict = serialize(op)

        # Remove datetime key
        del op_dict["created_at"]
        print(type(op_dict), op_dict)

        return web.json_response(op_dict, content_type="application/json", status=200)

    except Exception as e:

        print("\nOP CREATE ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Unable to create op"}, content_type="text/html", status=400
        )


async def op_get(request):
    # http://localhost:9999/op/get/?id=3
    """
    params = id(op_id) : int/str
    """
    try:

        op_id = request.rel_url.query["id"]
        op_object = ravdb.get_op(op_id)
        op_dict = serialize(op_object)

        # Remove datetime key
        del op_dict["created_at"]
        print(type(op_dict), op_dict)

        return web.json_response(op_dict, content_type="application/json", status=200)

    except Exception as e:

        print("\nOP GET ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid op id"}, content_type="text/html", status=400
        )


async def op_get_by_name(request):
    # http://localhost:9999/op/get/name/?op_name="None"&id="None"
    """
    params = op_name : str, id(graph_id) : int/str
    """
    try:
        op_name = request.rel_url.query["op_name"]
        graph_id = request.rel_url.query["id"]
        ops = ravdb.get_ops_by_name(op_name, graph_id)
        ops_dicts = []

        for op in ops:
            op_dict = serialize(op)
            # Remove datetime key
            del op_dict["created_at"]
            ops_dicts.append(op_dict)

        print(type(ops_dicts), ops_dicts)

        return web.json_response(ops_dicts, content_type="application/json", status=200)

    except Exception as e:

        print("\nOP GET ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid op_id or op_name"},
            content_type="text/html",
            status=400,
        )


async def op_get_all(request):
    # http://localhost:9999/op/get/all
    """
    returns : List(ops_dicts)
    """
    try:

        ops = ravdb.get_all_ops()
        print(type(ops), ops)
        ops_dicts = []
        for op in ops:
            op_dict = serialize(op)
            # Remove datetime key
            del op_dict["created_at"]
            ops_dicts.append(op_dict)

        return web.json_response(ops_dicts, content_type="application/json", status=200)

    except Exception as e:

        print("\nOP GET ALL ERROR : ", str(e))

        return web.json_response(
            {"message": "Unable to get all Ops"}, content_type="text/html", status=400
        )


async def op_status(request):
    # http://localhost:9999/op/status/?id=3
    """
    params = id(op_id) : int/str
    returns = status(str)
    """

    op_id = request.rel_url.query["id"]
    print(op_id)

    op = ravdb.get_op(op_id)

    if op is None:
        return web.json_response(
            {"message": "Invalid op id"}, content_type="text/html", status=400
        )
    else:
        return web.json_response(
            {"op_status": op.status}, content_type="application/json", status=200
        )


# ------ DATA ENDPOINTS ------


async def data_create(request):
    # http://localhost:9999/data/create/
    """
    dtype : str
    value : int, list, float, ndarray
    """
    try:
        data = await request.json()
        print("Request data:", data, type(data))
        value = convert_str_to_ndarray(data["value"])
        dtype = data["dtype"]

        data = ravdb.create_data(dtype=dtype)
        print("TYPE ===", type(data), "DATA == ", data)

        if dtype == "ndarray":
            file_path = dump_data(data.id, value)
            # Update file path
            ravdb.update_data(data, file_path=file_path)
        elif dtype in ["int", "float"]:
            ravdb.update_data(data, value=value)

        elif dtype == "file":
            filepath = os.path.join(
                os.path.join(BASE_DIR, "files"), "data_{}_{}".format(data.id, value)
            )
            copy_data(source=value, destination=filepath)
            ravdb.update_data(data, file_path=filepath)

        # Serialize db object
        data_dict = serialize(data)

        if data.file_path is not None:
            data_dict["value"] = convert_ndarray_to_str(
                load_data_from_file(data.file_path)
            )

        # Remove datetime key
        del data_dict["created_at"]
        del data_dict["file_path"]

        print("TYPE == ", type(data), data_dict)

        return web.json_response(data_dict, content_type="application/json", status=200)

    except Exception as e:

        print("\nDATA CREATE ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Unable to create Data"}, content_type="text/html", status=400
        )


async def data_get(request):
    # http://localhost:9999/data/get?id=1
    """
    params = id(data_id) : int/str
    """

    try:
        data_id = request.rel_url.query["id"]
        print(data_id)

        data = ravdb.get_data(data_id=data_id)
        data_dict = serialize(data)
        print(type(data_dict), data_dict)

        if data.file_path is not None:
            if data.dtype == "ndarray":
                data_dict["value"] = load_data_from_file(data.file_path).tolist()
            else:
                data_dict["value"] = load_data_from_file(data.file_path)

        # Remove datetime key
        del data_dict["created_at"]
        del data_dict["file_path"]

        return web.json_response(data_dict, content_type="application/json", status=200)

    except Exception as e:

        print("\nDATA GET ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid Data id"}, content_type="text/html", status=400
        )


async def data_get_data(request):
    # http://localhost:9999/data/get/data/?id=1
    """
    params = id(data_id) : int/str
    returns = data
    """

    try:
        data_id = request.rel_url.query["id"]
        print(data_id)

        data = ravdb.get_data(data_id=data_id)

        value = convert_ndarray_to_str(load_data_from_file(data.file_path))

        return web.json_response(
            {"value": value}, content_type="application/json", status=200
        )

    except Exception as e:

        print("\nDATA GET DATA ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid Data id"}, content_type="text/html", status=400
        )


async def data_delete(request):
    # http://localhost:9999/data/delete/?id=1

    try:
        data_id = request.rel_url.query["id"]
        print(data_id)

        ravdb.delete_data(data_id=data_id)

        return web.json_response(
            {"data_id": data_id, "message": "Data has been deleted successfully"},
            content_type="application/json",
            status=200,
        )

    except Exception as e:

        print("\nDATA DELETE ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid Data id"}, content_type="text/html", status=400
        )


# ------ GRAPH ENDPOINTS ------


async def graph_create(request):
    # http://localhost:9999/graph/create/
    try:
        # Create a new graph
        graph_obj = ravdb.create_graph()
        # Serialize db object
        graph_dict = serialize(graph_obj)
        # Remove datetime key
        del graph_dict["created_at"]

        print("GRAPH TYPE == ", type(graph_dict), "GRAPH == ", graph_dict)

        return web.json_response(
            graph_dict,
            text=None,
            body=None,
            status=200,
            reason=None,
            headers=None,
            content_type="application/json",
            dumps=json.dumps,
        )

    except Exception as e:

        print("\nGRAPH CREATE ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Unable to create Graph"}, content_type="text/html", status=400
        )


async def graph_get(request):
    # http://localhost:9999/graph/get/?id=1

    try:
        graph_id = request.rel_url.query["id"]
        graph_obj = ravdb.get_graph(graph_id=graph_id)
        # Serialize db object
        graph_dict = serialize(graph_obj)
        # Remove datetime key
        del graph_dict["created_at"]

        return web.json_response(
            graph_dict,
            text=None,
            body=None,
            status=200,
            reason=None,
            headers=None,
            content_type="application/json",
            dumps=json.dumps,
        )

    except Exception as e:

        print("\nGRAPH GET ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid Graph id"}, content_type="text/html", status=400
        )


async def graph_op_get(request):
    # http://localhost:9999/graph/op/get/?id=1

    try:
        graph_id = request.rel_url.query["id"]
        ops = ravdb.get_graph_ops(graph_id=graph_id)
        print(graph_id, ops)

        data = {"graph_id": graph_id, "ops": ops}

        return web.json_response(
            data,
            text=None,
            body=None,
            status=200,
            reason=None,
            headers=None,
            content_type="application/json",
            dumps=json.dumps,
        )

    except Exception as e:

        print("\nGRAPH OP GET ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid Graph id"}, content_type="text/html", status=400
        )


async def graph_op_delete(request):
    # http://localhost:9999/graph/op/delete/?id=1
    try:
        graph_db_id = request.rel_url.query["id"]
        ravdb.delete_graph_ops(graph_db_id)
        data = {
            "graph_db_id": graph_db_id,
            "message": "Graph op has been deleted successfully",
        }

        return web.json_response(
            data,
            text=None,
            body=None,
            status=200,
            reason=None,
            headers=None,
            content_type="application/json",
            dumps=json.dumps,
        )

    except Exception as e:

        print("\nGRAPH OP DELETE ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid Graph id"}, content_type="text/html", status=400
        )


async def graph_op_name_get(request):
    # http://localhost:9999/graph/op/name/get/?op_name=""&id=1

    try:
        op_name = request.rel_url.query["op_name"]
        graph_id = request.rel_url.query["id"]
        ops = ravdb.get_ops_by_name(op_name=op_name, graph_id=graph_id)
        print(op_name, graph_id, ops)

        data = {"op_name": op_name, "graph_id": graph_id, "ops": ops}

        return web.json_response(
            data,
            text=None,
            body=None,
            status=200,
            reason=None,
            headers=None,
            content_type="application/json",
            dumps=json.dumps,
        )
    except Exception as e:

        print("\nGRAPH OP NAME GET ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid op_name or graph id"},
            content_type="text/html",
            status=400,
        )
