import ast
from aiohttp import web
from .db import ravdb

# from ravop.core import t

# We can define aiohttp endpoints just as we normally would with no change


async def index(request):
    with open("ravclient/index.html") as f:
        return web.Response(text=f.read(), content_type="text/html")


async def op_get(request):
    op_id = request.rel_url.query["id"]
    print(op_id)
    return web.Response(
        text=str(ravdb.get_op(op_id)), content_type="text/html", status=200
    )


async def op_status(request):
    op_id = request.rel_url.query["id"]
    print(op_id)
    return web.Response(
        text=str(ravdb.get_op_status(op_id)), content_type="text/html", status=200
    )


async def op_refresh(request):
    op_id = request.rel_url.query["id"]
    print(op_id)
    return web.Response(
        text=str(ravdb.refresh(ravdb.get_op(op_id))),
        content_type="text/html",
        status=200,
    )


async def op_get_data(request):
    op_id = request.rel_url.query["id"]
    print(op_id)
    return web.Response(
        text=str(ravdb.refresh(ravdb.get_data(op_id))),
        content_type="text/html",
        status=200,
    )


# async def op_add(request):
#     a = t(ast.literal_eval(request.rel_url.query['value1']))
#     b = t(ast.literal_eval(request.rel_url.query['value2']))
#     c = a + b
#     return web.Response(text=str(c.id), content_type='text/html', status=200)
