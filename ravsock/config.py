import os
from os.path import expanduser

WAIT_INTERVAL_TIME = 10

BASE_DIR = os.path.join(expanduser("~"), "rdf")
DATA_FILES_PATH = os.path.join(BASE_DIR, "files")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(DATA_FILES_PATH, exist_ok=True)

RAVSOCK_LOG_FILE = os.path.join(BASE_DIR, "ravsock.log")

CONTEXT_FOLDER = os.path.join(BASE_DIR, "contexts")
PARAMS_FOLDER = os.path.join(BASE_DIR, "params")

os.makedirs(CONTEXT_FOLDER, exist_ok=True)
os.makedirs(PARAMS_FOLDER, exist_ok=True)

QUEUE_HIGH_PRIORITY = "queue:high_priority"
QUEUE_LOW_PRIORITY = "queue:low_priority"
QUEUE_COMPUTING = "queue:computing"

RDF_REDIS_HOST = os.environ.get("RDF_REDIS_HOST", "localhost")
RDF_REDIS_PORT = os.environ.get("RDF_REDIS_PORT", "6379")
RDF_REDIS_DB = os.environ.get("RDF_REDIS_DB", "0")

RDF_DATABASE_URI = "sqlite:///{}/rdf.db?check_same_thread=False".format(BASE_DIR)

FTP_SERVER_URL = "54.201.212.222"
# FTP_SERVER_URL = "localhost"
FTP_SERVER_USERNAME = "ubuntu"
FTP_SERVER_PASSWORD = "******"
