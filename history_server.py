from Queue import PriorityQueue, Empty
from threading import Thread
from gevent import sleep
import datetime
import json

from flask import Flask, request
from flask_sockets import Sockets

import chainclient

import coloredlogs
import logging

from models import get_models

app = Flask(__name__)
sockets = Sockets(app)

logger = logging.getLogger(__name__)
coloredlogs.install(level=logging.INFO)


#absurd numper of time related imports that hopefully can be paired down
import dateutil.parser; import pytz; import calendar

# Time functions
def to_unix_time(t):
    return calendar.timegm(t.utctimetuple())
def from_string(s):
    return dateutil.parser.parse(s)
def from_unix_time(u):
    return datetime.datetime.fromtimestamp(u).replace(tzinfo=pytz.utc)


LOOK_AHEAD_TIME = datetime.timedelta(seconds=1000)
CHUNK_LENGTH = datetime.timedelta(seconds=2000)
SITE_URL= 'http://chain-api.media.mit.edu/sites/7'


class Event:
    def __init__(self, sensor, time, value):
        self.sensor = sensor
        self.time = time
        self.value = value

    def __repr__(self):
        return '<event time=%s value=%s>' % (str(self.time), self.value)

    def to_dict(self):
        return {
            'timestamp': str(self.time),
            '_links': {
                'self': {
                    'href': 'http://chain-api.media.mit.edu/scalar_data/'
                },
                'ch:sensor': {
                    'href': self.sensor.url
                }
            },
            'value': self.value
        }

def get_data(sensor, start_time, end_time):
    start_stamp = to_unix_time(start_time)
    end_stamp = to_unix_time(end_time)
    c = chainclient.get(sensor.data_url +'&timestamp__gte=%s&timestamp__lt=%s' % (start_stamp, end_stamp))
    return c.data


site = chainclient.get(SITE_URL)
_, _, sensor_hash = get_models(site)
sensors = sensor_hash.values()
logger.info("Initialized")


class PseudoClock:
    def start(self, start_time=1415491200, time_scale=1):
        self.time_scale = time_scale
        self.local_start_time = self.local_now()
        self.pseudo_start_time = from_unix_time(start_time)

    def local_now(self):
        return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

    def pseudo_now(self):
        pseudo_elapsed_time = (self.local_now() - self.local_start_time) * self.time_scale
        return self.pseudo_start_time + pseudo_elapsed_time


@sockets.route('/')
def send_socket(ws):
    clock = PseudoClock()
    clock.start(start_time=1415491200, time_scale=1)
    logger.info("Connected to client for time %s" % clock.pseudo_start_time)

    # shared memory
    q = PriorityQueue()

    def look_ahead_loop():
        highest_time_checked = clock.pseudo_start_time
        while True:
            if clock.pseudo_now() >= clock.local_now():
                break
            if clock.pseudo_now() < highest_time_checked - LOOK_AHEAD_TIME:
                sleep(0.1)
                continue
            start = highest_time_checked
            end = highest_time_checked + CHUNK_LENGTH
            logger.info('Queueing Chunk: %s to %s' % (start, end))
            for sensor in sensors:
                data = get_data(sensor, start, end)
                for d in data:
                    t = dateutil.parser.parse(d['timestamp'])
                    v = d['value']
                    q.put((t.utctimetuple(), Event(sensor, t, v)))
            highest_time_checked = end

    t = Thread(target=look_ahead_loop)
    t.daemon = True
    t.start()

    def read_seek():
        new_start_time = ws.receive()
        while True:
            try:
                q.get(False)
            except Empty:
                clock.start(start_time=new_start_time, time_scale=1)

    t2 = Thread(target=read_seek)
    t2.daemon = True
    t2.start()

    while True:
        key, event = q.get()
        if clock.pseudo_now() < event.time:
            q.put((key, event))
            sleep(0.05)
        else:
            logger.info('Sending: %s' % json.dumps(event.to_dict()))
            ws.send(json.dumps(event.to_dict()))
            q.task_done()
