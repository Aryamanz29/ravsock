import os

from ravop.config import BASE_DIR

RAVSOCK_LOG_FILE = os.path.join(BASE_DIR, "ravsock.log")
WAIT_INTERVAL_TIME = 10


# FTP_SERVER_URL = "localhost"

CONTEXT_FOLDER = os.path.join(BASE_DIR, "contexts")
PARAMS_FOLDER = os.path.join(BASE_DIR, "params")

os.makedirs(CONTEXT_FOLDER, exist_ok=True)
os.makedirs(PARAMS_FOLDER, exist_ok=True)
