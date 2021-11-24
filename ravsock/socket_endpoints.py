import json
import os

from aiohttp import web
from sqlalchemy.orm import class_mapper

from .config import BASE_DIR
from .db import ravdb
from .utils import (
    dump_data,
    copy_data,
    convert_to_ndarray,
    load_data_from_file,
    convert_ndarray_to_str,
    find_dtype,
    get_op_stats,
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
    params = id(op_id) : int
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
    params = op_name : str, id(graph_id) : int
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
        # print(type(ops), ops)
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
    params = id(op_id) : int
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


async def op_delete(request):
    # http://localhost:9999/op/delete/?id=1
    """
    params  = id(op_id) : int
    """
    try:
        op_id = request.rel_url.query["id"]
        op_obj = ravdb.get_op(op_id)
        ravdb.delete(op_obj)
        data = {
            "op_id": op_id,
            "message": "Op has been deleted successfully",
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

        print("\nOP DELETE ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid OP id"}, content_type="text/html", status=400
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
        value = convert_to_ndarray(data["value"])
        print(value)
        dtype = value.dtype
        print(dtype, type(dtype))
        data = ravdb.create_data(dtype=str(dtype))
        print(data)
        print("TYPE ===", type(data), "DATA == ", data)
        file_path = dump_data(data.id, value)

        # Update file path
        ravdb.update_data(data, file_path=file_path)
        data_dict = serialize(data)

        if data.file_path is not None:
            data_dict["value"] = load_data_from_file(data.file_path).tolist()

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
    params = id(data_id) : int
    """

    # try:
    data_id = request.rel_url.query["id"]
    print(data_id)

    if data_id is None:
        return web.json_response(
            {"message": "Data id parameter is required"},
            content_type="text/html",
            status=400,
        )

    data = ravdb.get_data(data_id=data_id)

    if data is None:
        return web.json_response(
            {"message": "Invalid Data id"}, content_type="text/html", status=400
        )

    data_dict = serialize(data)
    print(type(data_dict), data_dict)

    if data.file_path is not None:
        data_dict["value"] = load_data_from_file(data.file_path).tolist()

    # Remove datetime key
    del data_dict["created_at"]
    del data_dict["file_path"]

    print(data_dict)

    return web.json_response(data_dict, content_type="application/json", status=200)

    # except Exception as e:
    #
    #     print("\nDATA GET ENDPOINT ERROR : ", str(e))
    #
    #     return web.json_response(
    #         {"message": "Invalid Data id"}, content_type="text/html", status=400
    #     )


async def data_get_data(request):
    # http://localhost:9999/data/get/data/?id=1
    """
    params = id(data_id) : int
    returns = data
    """

    try:
        data_id = request.rel_url.query["id"]
        print(data_id)

        data = ravdb.get_data(data_id=data_id)

        value = load_data_from_file(data.file_path).tolist()

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
        data = await request.json()
        print(data)

        # Create a new graph
        graph_obj = ravdb.create_graph()
        ravdb.update("graph", id=graph_obj.id, **data)

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
    """
    params = id(graph_id) : int
    returns = graph_dict
    """

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


async def graph_get_all(request):
    # http://localhost:9999/graph/get/all
    """
    returns = list(graph_dicts)
    """

    try:
        graph_objs = ravdb.get_all_graphs()
        graph_dicts = []

        for graph in graph_objs:
            graph_dict = serialize(graph)
            # Remove datetime key
            del graph_dict["created_at"]
            graph_dicts.append(graph_dict)

        return web.json_response(
            graph_dicts, content_type="application/json", status=200
        )

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

        print("\nGRAPH GET ALL ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Unable to get all graphs"},
            content_type="text/html",
            status=400,
        )


async def graph_op_get(request):
    # http://localhost:9999/graph/op/get/?id=1
    """
    params  = id(graph_id) : int
    returns = list(ops associate with a graph)
    """

    try:
        graph_id = request.rel_url.query["id"]
        ops = ravdb.get_graph_ops(graph_id=graph_id)

        ops_dicts = []

        for op in ops:
            op_dict = serialize(op)
            # Remove datetime key
            del op_dict["created_at"]
            ops_dicts.append(op_dict)

        return web.json_response(
            ops_dicts,
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


async def graph_op_name_get(request):
    # http://localhost:9999/graph/op/name/get/?op_name=""&id=1

    try:
        op_name = request.rel_url.query["op_name"]
        graph_id = request.rel_url.query["id"]
        ops = ravdb.get_ops_by_name(op_name=op_name, graph_id=graph_id)

        ops_dicts = []

        for op in ops:
            op_dict = serialize(op)
            # Remove datetime key
            del op_dict["created_at"]
            ops_dicts.append(op_dict)

        return web.json_response(
            ops_dicts,
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


async def graph_op_get_stats(request):
    # http://localhost:9999/graph/op/get/stats/?id=4
    """
    Get stats of all ops
    params  = id(graph_id) : int
    """

    try:
        graph_id = request.rel_url.query["id"]
        ops = ravdb.get_graph_ops(graph_id=graph_id)
        stats = get_op_stats(ops)

        return web.json_response(
            stats,
            text=None,
            body=None,
            status=200,
            reason=None,
            headers=None,
            content_type="application/json",
            dumps=json.dumps,
        )

    except Exception as e:

        print("\nGRAPH STATS ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid Graph id"}, content_type="text/html", status=400
        )


async def graph_get_progress(request):
    # http://localhost:9999/graph/op/get/progress/?id=4

    """
    Get Graph Ops Progress
    params  = id(graph_id) : int
    """

    try:

        graph_id = request.rel_url.query["id"]
        ops = ravdb.get_graph_ops(graph_id=graph_id)
        stats = get_op_stats(ops)

        if stats["total_ops"] == 0:
            return 0
        progress = (
            (stats["computed_ops"] + stats["computing_ops"] + stats["failed_ops"])
            / stats["total_ops"]
        ) * 100

        return web.json_response(
            {"progress": progress},
            text=None,
            body=None,
            status=200,
            reason=None,
            headers=None,
            content_type="application/json",
            dumps=json.dumps,
        )

    except Exception as e:

        print("\nGRAPH STATS ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Invalid Graph id"}, content_type="text/html", status=400
        )

async def graph_op_delete(request):
    # http://localhost:9999/graph/op/delete/?id=1
    """
    It deletes Ops & data objects associated with the given graph
    params  = id(graph_id) : int
    """
    try :
        graph_id = request.rel_url.query["id"]
        graph_obj = ravdb.get_graph(graph_id=graph_id)
        
        if graph_obj is None :
            return web.json_response(
            {"message": "Invalid Graph id"}, content_type="text/html", status=400
            )

        else :
            if ravdb.delete_graph_ops(graph_id):
                data = {
                    "graph_id": graph_id,
                    "message": "Graph Ops has been deleted successfully",
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
            else :
                   return web.json_response({"message": "No ops accociate with this graph!"}, content_type="text/html", status=400)

    except Exception as e:

        print("\nGRAPH OP DELETE ENDPOINT ERROR : ", str(e))

        return web.json_response(
            {"message": "Graph Ops already been deleted"}, content_type="text/html", status=400
        )


async def graph_delete(request):
    # http://localhost:9999/graph/delete/?id=1
    """
    params  = id(graph_id) : int
    """

    try:
        graph_id = request.rel_url.query["id"]
        graph_obj = ravdb.get_graph(graph_id=graph_id)
        ravdb.delete(graph_obj)
        data = {
            "graph_id": graph_id,
            "message": "Graph has been deleted successfully",
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
