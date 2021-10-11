import ast

import paramiko

from .config import FTP_SERVER_URL, FTP_SERVER_USERNAME, FTP_SERVER_PASSWORD
from ..helpers import get_random_string


def add_user(cid):
    username = cid
    password = get_random_string(10)
    print("Creating:", username, password)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(FTP_SERVER_URL, 22, FTP_SERVER_USERNAME, FTP_SERVER_PASSWORD)

    stdin, stdout, stderr = ssh.exec_command("sudo python3 ~/raven-ftp-server/add_user.py --username {} --password {}".format(username, password))

    ssh.exec_command("nohup sudo python3 ~/raven-ftp-server/run.py --action restart > output.log &")

    for line in iter(stderr.readline, ""):
        print(line, end="")

    final_output = ""

    for line in iter(stdout.readline, ""):
        print(line, end="")
        final_output += line

    print("Final:", final_output, type(final_output))

    ssh.close()

    return {"username": username, "password": password}

