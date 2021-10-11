import datetime
import json
import logging.handlers
import threading
from random import Random

import numpy as np
import socketio
import tenseal as ts
from aiohttp import web
from paramiko import SSHClient
from ravop import OpStatus, ClientOpMapping, MappingStatus, GraphStatus, RavQueue, QUEUE_HIGH_PRIORITY, \
    QUEUE_LOW_PRIORITY, QUEUE_COMPUTING, ravdb, Op as RavOp, Data as RavData
from ravop.db.models import ObjectiveClientMapping
from sqlalchemy import or_

from .config import RAVSOCK_LOG_FILE, WAIT_INTERVAL_TIME
from .encryption import secret_key, context
from .ftp import get_client, check_credentials
from .ftp.utils import add_user
from .helpers import get_random_string

print(context)

# Set up a specific logger with our desired output level
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add the log message handler to the logger
handler = logging.handlers.RotatingFileHandler(RAVSOCK_LOG_FILE)

logger.addHandler(handler)

sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode='aiohttp', async_handlers=True)

# Creates a new Aiohttp Web Application
app = web.Application()

# Binds our Socket.IO server to our Web App instance
sio.attach(app)

# Instantiate queues
queue_high_priority = RavQueue(name=QUEUE_HIGH_PRIORITY)
queue_low_priority = RavQueue(name=QUEUE_LOW_PRIORITY)
queue_computing = RavQueue(name=QUEUE_COMPUTING)


async def distribute_ops():
    clients = ravdb.get_available_clients()
    logger.debug("Available client;{}".format(str(clients)))
    for client in clients:
        await sio.emit("ping", data=None, namespace="/ravjs", room=client.client_id)


async def wait_interval():
    await distribute_ops()
    threading.Timer(WAIT_INTERVAL_TIME, await wait_interval).start()


# wait_interval()

"""
Connect and disconnect events
"""

num_clients = 0


@sio.event
async def connect(sid, environ):
    from urllib import parse
    ps = parse.parse_qs(environ['QUERY_STRING'])

    client_type = ps['type'][0]
    cid = ps["cid"][0]

    if client_type is None or cid is None:
        return None

    print("Connected:{} {}".format(sid, environ))

    # Create client
    client = ravdb.get_client_by_cid(cid)
    if client is None:
        client = ravdb.create_client(cid=cid, sid=sid, type=client_type, status="connected")
    else:
        client = ravdb.update_client(client, sid=sid, connected_at=datetime.datetime.now(), status="connected")

    # Create FTP credentials
    if client_type == "analytics":

        ftp_credentials = client.ftp_credentials

        args = (cid, ftp_credentials, client)

        download_thread = threading.Thread(target=create_credentials, name="create_credentials", args=args)
        download_thread.start()

        # if ftp_credentials is None:
        #     credentials = add_user(cid)
        #
        #     ravdb.update_client(client,
        #                         ftp_credentials=json.dumps(credentials))
        # else:
        #     ftp_credentials = json.loads(ftp_credentials)
        #     if not check_credentials(ftp_credentials['username'], ftp_credentials['password']):
        #         credentials = add_user(cid)
        #
        #         ravdb.update_client(client,
        #                             ftp_credentials=json.dumps(credentials))


def create_credentials(cid, ftp_credentials, client):
    if ftp_credentials is None:
        credentials = add_user(cid)

        ravdb.update_client(client,
                            ftp_credentials=json.dumps(credentials))
    else:
        ftp_credentials = json.loads(ftp_credentials)
        print("FTP credentials:", ftp_credentials)
        if not check_credentials(ftp_credentials['username'], ftp_credentials['password']):
            credentials = add_user(cid)

            ravdb.update_client(client,
                                ftp_credentials=json.dumps(credentials))


@sio.event
async def disconnect(sid):
    print("Disconnected:{}".format(sid))

    client = ravdb.get_client_by_sid(sid=sid)
    if client is not None:
        ravdb.update_client(client, status="disconnected", sid=None,
                            disconnected_at=datetime.datetime.now())

        if client.type == "ravjs":
            # Get ops which were assigned to this
            ops = ravdb.session.query(ClientOpMapping).filter(ClientOpMapping.client_id ==
                                                              client.id).filter(or_(ClientOpMapping.status
                                                                                    == MappingStatus.SENT,
                                                                                    ClientOpMapping.status ==
                                                                                    MappingStatus.ACKNOWLEDGED,
                                                                                    ClientOpMapping.status ==
                                                                                    MappingStatus.COMPUTING)).all()

            print(ops)
            # Set those ops to pending
            for op in ops:
                ravdb.update_op(op, status=MappingStatus.NOT_COMPUTED)
        elif client.type == "analytics":
            ops = ravdb.session.query(ObjectiveClientMapping).filter(ObjectiveClientMapping.client_id ==
                                                                     client.id).filter(or_(ObjectiveClientMapping.status
                                                                                           == MappingStatus.SENT,
                                                                                           ObjectiveClientMapping.status ==
                                                                                           MappingStatus.ACKNOWLEDGED,
                                                                                           ObjectiveClientMapping.status ==
                                                                                           MappingStatus.COMPUTING)).all()

            print(ops)
            # Set those ops to pending
            for op in ops:
                ravdb.update_op(op, status=MappingStatus.NOT_COMPUTED)


"""
Ping and pong events
"""


@sio.on("ping", namespace="/ravjs")
async def ping(sid):
    await sio.emit("pong", {}, namespace="/ravjs", room=sid)


@sio.on("pong", namespace="/ravjs")
async def pong(sid, data):
    """
    Client is available
    Send an op to the client
    """
    print("Pong: {} {}".format(sid, data))

    # Find, create payload and emit op
    await emit_op(sid)


@sio.on('inform_server', namespace="/ravop")
async def inform_server(sid, data):
    print("Inform server")
    data_type = data['type']
    if data_type == "op":
        data_id = data['op_id']

        # Emit op to the client
        clients = ravdb.get_available_clients()
        for client in clients:
            await sio.emit("ping", data=None, namespace="/ravjs", room=client.client_id)
    else:
        # Emit op to the client
        clients = ravdb.get_available_clients()
        print(clients)
        for client in clients:
            await sio.emit("ping", data=None, namespace="/ravjs", room=client.client_id)


@sio.on('remind_server', namespace="/ravop")
async def remind_server(sid, data):
    data = json.load(data)
    data_type = data['type']
    if data_type == "op":
        data_id = data['op_id']
    else:
        data_id = data['graph_id']


"""
When clients asks for an op
1. Op Computed or failed
"""


@sio.on('get_op', namespace="/ravjs")
async def get_op(sid, message):
    """
    Send an op to the client
    """
    print("get_op", message)

    # Find, create payload and emit op
    await emit_op(sid)


@sio.on('acknowledge_op', namespace="/ravjs")
async def acknowledge_op(sid, message):
    print("Op received", sid)

    data = json.loads(message)
    op_id = data['op_id']
    print("Op id", op_id)
    op_found = ravdb.get_op(op_id=op_id)

    if op_found is not None:
        # Update client op mapping - Status to acknowledged
        update_client_op_mapping(op_id, sid, MappingStatus.ACKNOWLEDGED)


@sio.on('op_completed', namespace="/ravjs")
async def op_completed(sid, data):
    # Save the results
    logger.debug("\nResult received {}".format(data))
    data = json.loads(data)
    print(data)

    op_id = data['op_id']

    logger.debug("{} {} {} {}".format(op_id, type(data['result']), data['operator'], data['result']))

    op = RavOp(id=op_id)

    if data["status"] == "success":
        data = RavData(value=np.array(data['result']), dtype="ndarray")

        # Update op
        ravdb.update_op(op._op_db, outputs=json.dumps([data.id]), status=OpStatus.COMPUTED)

        # Update client op mapping
        update_client_op_mapping(op_id, sid=sid, status=MappingStatus.COMPUTED)

        db_op = ravdb.get_op(op_id=op_id)
        if db_op.graph_id is not None:
            last_op = ravdb.get_last_graph_op(graph_id=db_op.graph_id)

            if last_op.id == op_id:
                ravdb.update(name="graph", id=db_op.graph_id, status=GraphStatus.COMPUTED)
    else:
        # Update op
        ravdb.update_op(op._op_db, outputs=None, status=OpStatus.FAILED, message=data['result'])

        # Update client op mapping
        update_client_op_mapping(op_id, sid=sid, status=MappingStatus.FAILED)

        op_status = ravdb.get_op_status_final(op_id=op_id)

        if op_status == "failed":
            db_op = ravdb.get_op(op_id=op_id)
            ravdb.update(name="graph", id=db_op.graph_id, status=GraphStatus.FAILED)

            graph_ops = ravdb.get_graph_ops(graph_id=db_op.graph_id)
            for graph_op in graph_ops:
                ravdb.update_op(op=graph_op, status=OpStatus.FAILED)

                mappings = graph_op.mappings
                for mapping in mappings:
                    ravdb.update_client_op_mapping(mapping.id, status=MappingStatus.FAILED)

    # Emit another op to this client
    await emit_op(sid)


"""
1. Find Op
2. Create Payload
3. Emit Op
"""


async def emit_op(sid, op=None):
    """
    1. Find an op
    2. Create payload
    3. Emit Op
    """
    # Find an op
    if op is None:
        op = find_op(name=ravdb.get_client_by_sid(sid).type)

    logger.debug(op)

    if op is None:
        print("None")
        return

    # Create payload
    payload = create_payload(op)

    # Emit op
    logger.debug("Emitting op:{}, {}".format(sid, payload))
    await sio.emit("op", payload, namespace="/ravjs", room=sid)

    # Store the mapping in database
    client = ravdb.get_client_by_sid(sid)
    ravop = RavOp(id=op.id)
    ravdb.update_op(ravop._op_db, status=OpStatus.COMPUTING)
    mapping = ravdb.create_client_op_mapping(client_id=client.id, op_id=op.id, sent_time=datetime.datetime.now(),
                                             status=MappingStatus.SENT)
    logger.debug("Mapping created:{}".format(mapping))

    if op.graph_id is not None:
        # if db.get_first_graph_op(graph_id=op.graph_id).id == op.id:
        ravdb.update(name="graph", id=op.graph_id, status=GraphStatus.COMPUTING)


def find_op(name=None):
    if name == "analytics":
        queue_analytics = RavQueue(name="queue:analytics")
        op_id = queue_analytics.get(0)

        if op_id is None:
            return None

        op = ravdb.get_op(op_id=op_id)

        r = ravdb.get_op_readiness(op)
        if r == "ready":
            queue_analytics.pop()
            return op
        elif r == "parent_op_failed":
            queue_analytics.pop()

            # Change this op's status to failed
            if op.status != "failed":
                ravdb.update_op(op, status=OpStatus.FAILED)
            return None

    elif name == "federated":
        pass
    elif name == "ravjs":
        op = ravdb.get_incomplete_op()

        if op is not None:
            return op
        else:
            q1 = RavQueue(name=QUEUE_HIGH_PRIORITY)
            q2 = RavQueue(name=QUEUE_LOW_PRIORITY)

            while True:
                op_id1 = None
                op_id2 = None

                if q1.__len__() > 0:
                    op_id1 = q1.get(0)
                elif q2.__len__() > 0:
                    op_id2 = q2.get(0)

                if op_id1 is None and op_id2 is None:
                    return None

                ops = [op_id1, op_id2]

                for index, op_id in enumerate(ops):
                    if op_id is None:
                        continue

                    op = ravdb.get_op(op_id=op_id)

                    if op.graph_id is not None:
                        if ravdb.get_graph(op.graph_id).status == "failed":
                            # Change this op's status to failed
                            if op.status != "failed":
                                ravdb.update_op(op, status=OpStatus.FAILED)
                                continue

                        elif ravdb.get_graph(op.graph_id).status == "computed":
                            if index == 0:
                                q1.pop()
                            elif index == 1:
                                q2.pop()
                            continue

                    r = ravdb.get_op_readiness(op)
                    if r == "ready":
                        if index == 0:
                            q1.pop()
                        elif index == 1:
                            q2.pop()

                        return op
                    elif r == "parent_op_failed":
                        if index == 0:
                            q1.pop()
                        elif index == 1:
                            q2.pop()

                        # Change this op's status to failed
                        if op.status != "failed":
                            ravdb.update_op(op, status=OpStatus.FAILED)

                return None

                # if q1.__len__() > 0 or q2.__len__() > 0:
                #     if
                #     op_id = q1.get(0)
                #     op = db.get_op(op_id=op_id)
                #
                #     if db.get_op_readiness(op) == "ready":
                #         q1.pop()
                #         return op
                #     elif db.get_op_readiness(op) == "parent_op_not_ready":
                #         continue
                #
                # elif q2.__len__() > 0:
                #     op_id = q2.get(0)
                #     op = db.get_op(op_id=int(op_id))
                #
                #     if db.get_op_readiness(op) == "ready":
                #         q2.pop()
                #         return op
                #     elif db.get_op_readiness(op) == "parent_op_not_ready":
                #         continue
                # else:
                #     op = None
                #     print("There is no op")
                #     return op


def create_payload(op):
    """
    Create payload for the operation
    params:
    op: database op
    """
    values = []
    inputs = json.loads(op.inputs)
    for op_id in inputs:
        ravop = RavOp(id=op_id)
        if ravop.output_dtype == "ndarray":
            values.append(ravop.output.tolist())
        else:
            values.append(ravop.output)

    payload = dict()
    payload['op_id'] = op.id
    payload['values'] = values
    payload['op_type'] = op.op_type
    payload['operator'] = op.operator

    params = dict()
    for key, value in json.loads(op.params).items():
        if type(value).__name__ == 'int':
            op1 = RavOp(id=value)
            if op1.output_dtype == "ndarray":
                params[key] = op1.output.tolist()
            else:
                params[key] = op1.output
        elif type(value).__name__ == 'str':
            params[key] = value

    payload['params'] = params

    return payload


def update_client_op_mapping(op_id, sid, status):
    client = ravdb.get_client_by_sid(sid)
    mapping = ravdb.find_client_op_mapping(client.id, op_id)
    ravdb.update_client_op_mapping(mapping.id, status=status,
                                   response_time=datetime.datetime.now())


@sio.on('op_completed', namespace="/raven-federated")
async def op_completed(sid, data):
    # Save the results
    logger.debug("\nResult received {}".format(data))
    # data = json.loads(data)
    print(data)
    op_id = data['op_id']
    logger.debug("{} {} {} {}".format(op_id, type(data['result']), data['operator'], data['result']))


"""
Federated Analytics
"""

global_mean = 0
global_min = float('inf')
global_max = float('-inf')
global_variance = 0
global_standard_deviation = 0
n1 = 0
n2 = 0
params = dict()


@sio.on("handshake", namespace="/analytics")
async def get_handshake(sid, data):
    # Get objective
    client = ravdb.get_client_by_sid(sid)
    objective = ravdb.find_active_objective(client.id)
    print(objective)
    if objective is not None:
        # Create objective client mapping
        ravdb.create_objective_client_mapping(objective_id=objective.id, client_id=client.id)
        return row2dict(objective)


@sio.on("context_vector", namespace="/analytics")
async def get_context_vector(sid, data):
    # Setup TenSEAL context
    global context
    print(context)

    client = ravdb.get_client_by_sid(sid=sid)
    if client.ftp_credentials is not None:
        ftp_credentials = json.loads(client.ftp_credentials)
        ftp = get_client(username=ftp_credentials['username'], password=ftp_credentials['password'])

        with open("context.txt", "wb") as f:
            f.write(context.serialize())

        ftp.upload("context.txt", "context.txt")

    return True


def row2dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = str(getattr(row, column.name))

    return d


@sio.on("receive_params", namespace="/analytics")
async def receive_params(sid, client_params):
    global context
    params.update(client_params)

    if client_params.get("objective_id", None) is not None:
        client = ravdb.get_client_by_sid(sid)
        objective = ravdb.get_objective(objective_id=client_params['objective_id'])
        objective_client_mapping = ravdb.find_objective_client_mapping(objective_id=client_params['objective_id'],
                                                                       client_id=client.id)

        ravdb.update_objective_client_mapping(objective_client_mapping.id, status="computed",
                                              result=str(client_params[objective.operator]))

        objective = ravdb.get_objective(objective_id=client_params['objective_id'])
        mappings = ravdb.get_objective_mappings(client_params['objective_id'], status=MappingStatus.COMPUTED)
        rules = json.loads(objective.rules)

        # Calculate
        if objective.result is None:
            ravdb.update_objective(objective_id=objective.id, result=json.dumps(client_params))
        else:
            result = json.loads(objective.result)

            current_mean = client_params.get('mean', None)
            previous_mean = result.get('mean', None)
            n1 = result['size']
            n2 = client_params['size']
            final_mean = None
            global_variance = None
            global_standard_deviation = None
            global_min = min(result['minimum'], client_params.get('minimum', float('inf')))
            global_max = max(result['maximum'], client_params.get('maximum', float("-inf")))

            if objective.operator == "mean":
                final_mean = (previous_mean * n1) / (n1 + n2) + (current_mean * n2) / (n1 + n2)
            elif objective.operator == "variance":
                final_mean = (previous_mean * n1) / (n1 + n2) + (current_mean * n2) / (n1 + n2)
                global_variance = (n1 * result.get('variance', None) + n2 * client_params.get('variance', None)) / \
                                  (n1 + n2) + ((n1 * n2 * (previous_mean - current_mean) ** 2) / (n1 + n2) ** 2)
            elif objective.operator == "standard_deviation":
                final_mean = (previous_mean * n1) / (n1 + n2) + (current_mean * n2) / (n1 + n2)
                global_variance = (n1 * result.get('variance', None) + n2 * client_params.get('variance', None)) / (
                        n1 + n2) + (
                                          (n1 * n2 * (previous_mean - current_mean) ** 2) / (n1 + n2) ** 2)
                global_standard_deviation = np.sqrt(global_variance)

            ravdb.update_objective(objective_id=objective.id, result=json.dumps({"mean": final_mean,
                                                                                 "size": n1 + n2,
                                                                                 "variance": global_variance,
                                                                                 "minimum": global_min,
                                                                                 "maximum": global_max,
                                                                                 "standard_deviation": global_standard_deviation
                                                                                 }))

        if mappings.count() >= rules['participants']:
            ravdb.update_objective(objective_id=client_params['objective_id'], status="computed")


@sio.on("fed_analytics", namespace="/analytics")
async def get_fed_analytics(sid, client_params):
    # op = find_op(name="analytics")
    #
    # payload = create_payload(op)
    #
    # clients = ravdb.
    #
    # sio.emit()

    print(client_params)
    global global_mean, global_min, global_max, global_variance, global_standard_deviation, num_clients, n1, n2
    if num_clients == 1:
        n1 = ts.ckks_tensor_from(context, client_params['size']).decrypt(secret_key).tolist()[0]
        global_mean = ts.ckks_tensor_from(context, client_params['Average']).decrypt(secret_key).tolist()[0]
        global_variance = ts.ckks_tensor_from(context, client_params['Variance']).decrypt(secret_key).tolist()[0]
    else:
        n2 = ts.ckks_tensor_from(context, client_params['size']).decrypt(secret_key).tolist()[0]
        m1 = global_mean
        m2 = ts.ckks_tensor_from(context, client_params['Average']).decrypt(secret_key).tolist()[0]
        global_variance = (n1 * global_variance + n2 *
                           ts.ckks_tensor_from(context, client_params['Variance']).decrypt(secret_key).tolist()[0]) / (
                                  n1 + n2) + ((n1 * n2 * (m1 - m2) ** 2) / (n1 + n2) ** 2)
        global_mean = global_mean * (n1) / (n1 + n2) + (
                ts.ckks_tensor_from(context, client_params['Average']).decrypt(secret_key).tolist()[0] * n2) / (
                              n1 + n2)
    global_min = min(global_min, ts.ckks_tensor_from(context, client_params['Minimum']).decrypt(secret_key).tolist()[0])
    global_max = max(global_max, ts.ckks_tensor_from(context, client_params['Maximum']).decrypt(secret_key).tolist()[0])
    global_standard_deviation = np.sqrt(global_variance)
    print("Global Mean: {}".format(global_mean))
    print("Global Min: {}".format(global_min))
    print("Global Max: {}".format(global_max))
    print("Global Variance: {}".format(global_variance))
    print("Global Standard Deviation: {}".format(global_standard_deviation))
    print('----------------------------------')
    n1 += n2


"""
Federated Learning
"""


@sio.on("client_status", namespace="/raven-federated")
async def get_client_status(sid, client_status):
    print("client_status:{}".format(client_status))
    if client_status != {}:
        ravdb.update_federated_op(status=client_status['status'])
    op = find_op()
    logger.debug("Op:{}".format(op))
    if op is None:
        print("None")
        return None
    # Create payload
    payload = create_payload(op)
    # Updating client-op mapping
    client_op_mapping = ravdb.create_client_op_mapping(client_id=sid, op_id=op.id,
                                                       status=MappingStatus.SENT)
    # Emit op
    logger.debug("Emitting op:{}, {}".format(sid, payload))
    return payload


@sio.on('op_completed', namespace="/raven-federated")
async def op_completed(sid, data):
    # Save the results
    logger.debug("\nResult received {}".format(data))
    print(data)
    op_id = data['op_id']
    logger.debug("{} {} {} {}".format(op_id, type(data['result']), data['operator'], data['result']))
    op = RavOp(id=op_id)
    if data["status"] == "success":
        data = RavData(value=np.array(data['result']), dtype="ndarray")
        # Update op
        ravdb.update_op(op._op_db, outputs=json.dumps([data.id]), status=OpStatus.COMPUTED)
        # Update client op mapping
        mapping = ravdb.find_client_op_mapping(client_id=sid, op_id=op_id)
        ravdb.update_client_op_mapping(mapping.id, sid=sid, status=MappingStatus.COMPUTED)
