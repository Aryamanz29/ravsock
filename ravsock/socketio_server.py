import datetime
import json
import logging.handlers
import threading

import numpy as np
import socketio
from aiohttp import web
from ravop import OpStatus, ClientOpMapping, ClientOpMappingStatus, GraphStatus, RavQueue, QUEUE_HIGH_PRIORITY, \
    QUEUE_LOW_PRIORITY, QUEUE_COMPUTING, ravdb, Op as RavOp, Data as RavData
from sqlalchemy import or_

from .config import RAVSOCK_LOG_FILE, WAIT_INTERVAL_TIME

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
    logger.debug("Connected:{} {}".format(sid, environ))
    global num_clients
    print("Connected")
    client_type = None
    if 'ravop' in environ['QUERY_STRING']:
        client_type = "ravop"
    elif 'ravjs' in environ['QUERY_STRING']:
        client_type = "ravjs"
    else:
        if 'raven-federated' in environ['HTTP_CLIENT_NAME']:
            client_type = "raven-federated"
            print('Federated Learning Initialized for Client')
        elif 'analytics' in environ['HTTP_CLIENT_NAME']:
            client_type = "analytics"
            print('Analytics Initialized for Client')
            num_clients += 1

    # Create client
    if client_type == "raven-federated":
        obj = ravdb.create_client(client_id=sid, connected_at=datetime.datetime.now(), status="connected",
                                  reporting="READY", type=client_type)

    # Create client
    # ravdb.create_client(client_id=sid, connected_at=datetime.datetime.now(), status="connected",
    # type=client_type)

    print("Connected")


@sio.event
async def disconnect(sid):
    logger.debug("Disconnected:{}".format(sid))

    client = ravdb.get_client_by_sid(sid=sid)
    if client is not None:
        ravdb.update_client(client, status="disconnected", disconnected_at=datetime.datetime.now())

        if client.type == "ravjs":
            # Get ops which were assigned to this
            ops = ravdb.session.query(ClientOpMapping).filter(ClientOpMapping.client_id ==
                                                              sid).filter(or_(ClientOpMapping.status
                                                                              == ClientOpMappingStatus.SENT.value,
                                                                              ClientOpMapping.status ==
                                                                              ClientOpMappingStatus.ACKNOWLEDGED,
                                                                              ClientOpMapping.status ==
                                                                              ClientOpMappingStatus.COMPUTING.value)).all()

            print(ops)
            # Set those ops to pending
            for op in ops:
                ravdb.update_op(op, status=ClientOpMappingStatus.NOT_COMPUTED.value)


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
        update_client_op_mapping(op_id, sid, ClientOpMappingStatus.ACKNOWLEDGED.value)


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
        ravdb.update_op(op._op_db, outputs=json.dumps([data.id]), status=OpStatus.COMPUTED.value)

        # Update client op mapping
        update_client_op_mapping(op_id, sid=sid, status=ClientOpMappingStatus.COMPUTED.value)

        db_op = ravdb.get_op(op_id=op_id)
        if db_op.graph_id is not None:
            last_op = ravdb.get_last_graph_op(graph_id=db_op.graph_id)

            if last_op.id == op_id:
                ravdb.update(name="graph", id=db_op.graph_id, status=GraphStatus.COMPUTED.value)
    else:
        # Update op
        ravdb.update_op(op._op_db, outputs=None, status=OpStatus.FAILED.value, message=data['result'])

        # Update client op mapping
        update_client_op_mapping(op_id, sid=sid, status=ClientOpMappingStatus.FAILED.value)

        op_status = ravdb.get_op_status_final(op_id=op_id)

        if op_status == "failed":
            db_op = ravdb.get_op(op_id=op_id)
            ravdb.update(name="graph", id=db_op.graph_id, status=GraphStatus.FAILED.value)

            graph_ops = ravdb.get_graph_ops(graph_id=db_op.graph_id)
            for graph_op in graph_ops:
                ravdb.update_op(op=graph_op, status=OpStatus.FAILED.value)

                mappings = graph_op.mappings
                for mapping in mappings:
                    ravdb.update_client_op_mapping(mapping.id, status=ClientOpMappingStatus.FAILED.value)

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
        op = find_op()

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
    ravdb.update_op(ravop._op_db, status=OpStatus.COMPUTING.value)
    mapping = ravdb.create_client_op_mapping(client_id=client.id, op_id=op.id, sent_time=datetime.datetime.now(),
                                             status=ClientOpMappingStatus.SENT.value)
    logger.debug("Mapping created:{}".format(mapping))

    if op.graph_id is not None:
        # if db.get_first_graph_op(graph_id=op.graph_id).id == op.id:
        ravdb.update(name="graph", id=op.graph_id, status=GraphStatus.COMPUTING.value)

    timer = threading.Timer(2.0, abc, [mapping.id])
    timer.start()


def abc(args):
    print("Done:{}".format(args))


def find_op():
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
                            ravdb.update_op(op, status=OpStatus.FAILED.value)
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
                        ravdb.update_op(op, status=OpStatus.FAILED.value)

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


@sio.on("client_status", namespace="/raven-federated")
async def get_client_status(sid, client_status):
    print("client_status:{}".format(client_status))
    if client_status != {}:
        ravdb.update_federated_op(status=client_status['status'])
    op = find_op()
    logger.debug(op)
    if op is None:
        print("None")
        return None
    # Create payload
    payload = create_payload(op)
    # Updating client-op mapping
    client_op_mapping = ravdb.create_client_op_mapping(client_id=sid, op_id=op.id,
                                                       status=ClientOpMappingStatus.SENT.value)
    # update_client_op_mapping(op.id, sid, ClientOpMappingStatus.ACKNOWLEDGED.value)
    # Emit op
    logger.debug("Emitting op:{}, {}".format(sid, payload))
    return payload


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


@sio.on("fed_analytics", namespace="/analytics")
async def get_fed_analytics(sid, client_params):
    global global_mean, global_min, global_max, global_variance, global_standard_deviation, num_clients, n1, n2
    if num_clients == 1:
        n1 = client_params['size']
        global_mean = client_params['Average']
        global_variance = client_params['Variance']
    else:
        n2 = client_params['size']
        m1 = global_mean
        m2 = client_params['Average']
        global_variance = (n1 * global_variance + n2 * client_params['Variance']) / (n1 + n2) + (
                (n1 * n2 * (m1 - m2) ** 2) / (n1 + n2) ** 2)
        global_mean = global_mean * (n1) / (n1 + n2) + (client_params['Average'] * n2) / (n1 + n2)
    global_min = min(global_min, client_params['Minimum'])
    global_max = max(global_max, client_params['Maximum'])
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
                                                       status=ClientOpMappingStatus.SENT.value)
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
        ravdb.update_op(op._op_db, outputs=json.dumps([data.id]), status=OpStatus.COMPUTED.value)
        # Update client op mapping
        mapping = ravdb.find_client_op_mapping(client_id=sid, op_id=op_id)
        ravdb.update_client_op_mapping(mapping.id, sid=sid, status=ClientOpMappingStatus.COMPUTED.value)
