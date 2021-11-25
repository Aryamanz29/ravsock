from aiohttp import web
from ravsock.socketio_server import app #, cleanup, sio
from ravsock.utils import create_database, create_tables


# async def run_cleanup():
#     await cleanup()


if __name__ == "__main__":
    print("Starting server...")

    # Create database if not exists

    if create_database():
        create_tables()

    # sio.start_background_task(run_cleanup)
    web.run_app(app, port=9999)
