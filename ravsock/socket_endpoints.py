import json

import numpy as np
from aiohttp import web

from .db import ravdb
from .utils import dump_data


# from ravop.core import t

# We can define aiohttp endpoints just as we normally would with no change
async def index(request):
    with open("index.html") as f:
        return web.Response(text=f.read(), content_type="text/html")


async def op_get(request):
    # http://localhost:9999/ravdb/op/get/?id=3
    op_id = request.rel_url.query["id"]
    print(op_id)

    op = ravdb.get_op(op_id)

    if op is None:
        return web.json_response({"message": "Invalid op id"}, content_type="text/html", status=400
                                 )
    else:
        op_dict = db_model_to_dict(op)
        return web.json_response(op_dict, content_type="text/html", status=200
                                 )


def db_model_to_dict(obj):
    obj1 = obj.__dict__
    del obj1['_sa_instance_state']
    del obj1['created_at']
    return obj1


async def op_status(request):
    # http://localhost:9999/ravdb/op/status/?id=3
    op_id = request.rel_url.query["id"]
    print(op_id)

    op = ravdb.get_op(op_id)

    if op is None:
        return web.json_response({"message": "Invalid op id"}, content_type="text/html", status=400
                                 )
    else:
        return web.json_response({"status": op.status}, content_type="text/html", status=200
                                 )


async def op_get_data(request):
    # http://localhost:9999/ravdb/op/get/data/?id=3
    op_id = request.rel_url.query["id"]
    print(op_id)

    op = ravdb.get_op(op_id)

    if op is None:
        return web.json_response({"message": "Invalid op id"}, content_type="text/html", status=400
                                 )
    else:
        data = ravdb.get_data(op_id)
        return web.json_response({"data": data},
                                 content_type="text/html",
                                 status=200,
                                 )


# async def op_add(request):
# http://localhost:9999/ravdb/op/add/?value1=12354&value2=346
#     a = t(ast.literal_eval(request.rel_url.query['value1']))
#     b = t(ast.literal_eval(request.rel_url.query['value2']))
#     c = a + b
#     return web.Response(text=str(c.id), content_type='text/html', status=200)


async def op_create(request):
    # http://localhost:9999/ravdb/op/create/?name=None&graph_id=None&node_type=input&inputs=null&outputs=[1]&op_type=other&operator=linear&status=computed&params={}
    data = await request.post()
    data = dict(data)

    if len(data.keys()) == 0:
        return web.Response(
            text=str({"message": "Invalid parameters"}),
            content_type="text/html",
            status=400,
        )

    # name = request.rel_url.query["name"]
    # graph_id = request.rel_url.query["graph_id"]
    # node_type = request.rel_url.query["node_type"]
    # inputs = request.rel_url.query["inputs"]
    # outputs = request.rel_url.query["outputs"]
    # op_type = request.rel_url.query["op_type"]
    # operator = request.rel_url.query["operator"]
    # status = request.rel_url.query["status"]
    # params = request.rel_url.query["params"]

    # op = ravdb.create_op(
    #     name=name,
    #     graph_id=graph_id,
    #     node_type=node_type,
    #     inputs=inputs,
    #     outputs=outputs,
    #     op_type=op_type,
    #     operator=operator,
    #     status=status,
    #     params=params,
    # )

    op = ravdb.create_op(**data)

    return web.Response(text=str({"op_id": op.id}), content_type="text/html", status=200)


async def db_create_data(request):
    # http://localhost:9999/ravdb/create/data/?dtype=ndarray&value=12700
    dtype = request.rel_url.query["dtype"]  #
    value = request.rel_url.query["value"]
    value = np.fromstring(value, dtype=np.uint8)
    data = ravdb.create_data(type=dtype)
    print(dtype, "DATA == ", data)

    if dtype == "ndarray":
        file_path = dump_data(data.id, value)
        # Update file path
        ravdb.update_data(data, file_path=file_path)
    elif dtype in ["int", "float"]:
        ravdb.update_data(data, value=value)

    data_dict = db_model_to_dict(data)

    return web.json_response()

    return web.Response(
        text=data_dict,
        content_type="text/html",
        status=200,
    )


async def graph_create(request):
    # http://localhost:9999/ravdb/graph/create/
    # Create a new graph
    graph_obj = ravdb.create_graph()
    graph_id = graph_obj.id
    print(graph_obj, graph_id)

    data = {"graph_obj": str(graph_obj), "graph_id": graph_id}

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


async def graph_get(request):
    # http://localhost:9999/ravdb/graph/get/?graph_id=1
    graph_id = request.rel_url.query["graph_id"]
    graph_obj = ravdb.get_graph(graph_id=graph_id)
    print(graph_id, graph_obj)

    data = {"graph_obj": str(graph_obj), "graph_id": graph_id}

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


async def graph_op_get(request):
    # http://localhost:9999/ravdb/graph/op/get/?graph_id=1
    graph_id = request.rel_url.query["graph_id"]
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


async def graph_op_delete(request):
    # http://localhost:9999/ravdb/graph/op/delete/?graph_db_id=1
    graph_db_id = request.rel_url.query["graph_db_id"]
    data = {
        "graph_obj": ravdb.delete_graph_ops(graph_db_id),
        "message": "Graph Object has been deleted",
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


async def graph_op_name_get(request):
    # http://localhost:9999/ravdb/graph/op/name/get/?op_name=""&graph_id=1
    op_name = request.rel_url.query["op_name"]
    graph_id = request.rel_url.query["graph_id"]
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
