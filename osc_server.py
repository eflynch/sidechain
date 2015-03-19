from multiprocessing import Process, Pipe, Manager
from threading import Thread
import itertools
import json

import chainclient
from chainclient import HALDoc
from websocket import create_connection
from matplotlib import pyplot as plt
import coloredlogs
import logging
import numpy
import liblo

from models import get_models

logger = logging.getLogger(__name__)
coloredlogs.install(level=logging.INFO)


# parameters
SITE_URL= 'http://chain-api.media.mit.edu/sites/7'
OSC_IN_PORT = 5553
OSC_OUT_PORT = 5555
OSC_UNITY_PORT = 5554

outgoing_addr = liblo.Address(OSC_OUT_PORT)

def main():
    # Set up Chain Objects
    site = chainclient.get(SITE_URL)
    metric_hash, device_hash, sensor_hash = get_models(site)


    # Pass through websocket events from chainAPI
    def get_ws_values_loop():
        if True:
            stream_url = 'ws://localhost:8000/'
        else:
            stream_url = site.links['ch:websocketStream'].href
        logger.info('Connecting to %s' % stream_url)
        ws = create_connection(stream_url)
        logger.info('Connected!')
        while True:
            resource_data = ws.recv()
            logger.debug(resource_data)
            in_data = HALDoc(json.loads(resource_data))
            try:
                sensor = sensor_hash[in_data.links['ch:sensor'].href]
            except KeyError:
                logger.warning('Hash miss: %s' % in_data.links['ch:sensor'].href)
                continue
            logger.debug('Received value of %f from sensor %s' % (in_data.value, sensor))
            sensor.value = in_data.value
            liblo.send(outgoing_addr, '/device/data', sensor.device.index, sensor.metric, in_data.value)
    t = Thread(target=get_ws_values_loop)
    t.daemon = True
    t.start()


    # OSC Server to pass through Unity player information
    # /player/location x y z
    # /player/angle yaw pitch roll
    # /time seconds
    def osc_pass_through_loop():
        server = liblo.Server(OSC_UNITY_PORT)

        def pass_through(path, args):
            logger.info("Received data from Unity: %s : %s" % (path, args))
            liblo.send(outgoing_addr, path, *args)

        server.add_method(None, None, pass_through)
        while True:
            server.recv(100)
    t2 = Thread(target=osc_pass_through_loop)
    t2.daemon = True
    t2.start()


    # OSC Server to communicated with Music client
    try:
        server = liblo.Server(OSC_IN_PORT)
    except liblo.ServerError, err:
        print str(err)

    def get_metric(path, args):
        metric_title, x, y = args
        logger.debug("Received request for %s at %s, %s" % (metric_title, x ,y))
        metric = metric_hash[metric_title]
        value = metric.get_value(x,y)
        if value != float('inf'):
            liblo.send(outgoing_addr, '/metric/data', metric_title, value)
        else:
            value = metric.get_mean()
            liblo.send(outgoing_addr, '/metric/data', metric_title, value)
            logger.warning("No data for %s at %s, %s. Sending mean instead" % (metric_title, x, y))

    def get_mean(path, args):
        (metric_title,) = args
        logger.debug("Received request for %s mean" % (metric_title))
        metric = metric_hash[metric_title]
        value = metric.get_mean()
        liblo.send(outgoing_addr, '/metric/mean/data', metric_title, value)

    def get_std(path, args):
        (metric_title,) = args
        logger.debug("Received request for %s std" % (metric_title))
        metric = metric_hash[metric_title]
        value = metric.get_std()
        liblo.send(outgoing_addr, '/metric/std/data', metric_title, value)
    
    def get_device(path, args):
        (index, ) = args
        logger.debug("Recevied request for device %s" % index)
        device = device_hash[index]
        liblo.send(outgoing_addr, '/device/location', device.index, device.x, device.y)

    def plot_heat(path, args):
        (metric_title, ) = args
        logger.debug("Received request to plot metric %s" % metric_title)
        metric = metric_hash[metric_title]
        plt.figure()
        metric.plot_sensors()
        metric.plot_heat_map()
        plt.show()

    def plot_scatter(path, args):
        (metric_title, ) = args
        logger.debug("Received request to plot metric %s" % metric_title)
        metric = metric_hash[metric_title]
        plt.figure()
        metric.plot_sensors()
        metric.plot_scatter()
        plt.show()

    def plot_sensors(path, args):
        (metric_title, ) = args
        logger.debug("Received request to plot metric %s" % metric_title)
        metric = metric_hash[metric_title]
        plt.figure()
        metric.plot_sensors()
        plt.show()

    server.add_method("/metric", 'sff', get_metric)
    server.add_method("/device", 'i', get_device)
    server.add_method("/metric/plot/heat", 's', plot_heat)
    server.add_method("/metric/plot/scatter", 's', plot_scatter)
    server.add_method("/metric/plot/sensors", 's', plot_sensors)
    server.add_method("/metric/mean", 's', get_mean)
    server.add_method("/metric/std", 's', get_std)

    while True:
        server.recv(100)

if __name__ == "__main__":
    main()
