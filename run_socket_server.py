from aiohttp import web
from ravsock.socketio_server import app, cleanup, sio


async def run_cleanup():
    await cleanup()


if __name__ == "__main__":
    print("Starting server...")
    sio.start_background_task(run_cleanup)
    web.run_app(app, port=9999)
