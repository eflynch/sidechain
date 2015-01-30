import itertools
import json

import chainclient
from chainclient import HALDoc
from websocket import create_connection
import coloredlogs
import logging
import numpy

from interpolate import Interpolator
from kbhit import KBHit

logger = logging.getLogger(__name__)
coloredlogs.install(level=logging.INFO)

SITE_URL = 'http://chain-api.media.mit.edu/sites/7'

METRIC_WHITELIST = []


def get_site(site_url=SITE_URL):
    return chainclient.get(site_url)


class Metric(object):
    def __init__(self, metric, sensors, sw, width, height):
        self.metric = metric
        self.sensors = sensors

    def get_sensor_hash(self):
        return {s.url: s for s in self.sensors}

    def get_array(self):
        return numpy.array(filter(lambda x: x != None, [s.value for s in self.sensors]))

    def get_mean(self):
        return numpy.mean(self.get_array())

    def get_std(self):
        return numpy.std(self.get_array())


class Sensor(object):
    def __init__(self, url, metric):
        self.url = url
        self.metric = metric
        self._value = None

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        return self.url == other.url

    @property
    def value(self):
        if self._value:
            return self._value
        else:
            return None
    @value.setter
    def value(self, value):
        self._value = value
    
    def __repr__(self):
        return "Sensor %s, (metric=%s)" % \
            (self.url, self.metric)

def get_devices(site):
    devices = list(site.rels['ch:devices'].rels['items'])
    return devices


def get_metrics(site):
    devices = get_devices(site)

    sensors_by_metric = {}

    for device in devices:
        if device.name == AGGREGATE_DEVICE_NAME:
            continue
        for chain_sensor in device.rels['ch:sensors'].rels['items']:
            url = chain_sensor.links.self.href
            sensor = Sensor(url=url, metric=chain_sensor.metric)
            if sensor.metric not in sensors_by_metric:
                sensors_by_metric[sensor.metric] = []
            sensors_by_metric[sensor.metric].append(sensor)

    metrics = {}
    for metric in sensors_by_metric:
        metric = Metric(metric, sensors_by_metric[metric])
        metrics[metric] = metric

    return metrics

def get_sensor_hash(metrics):
    return dict(list(itertools.chain(*[f.get_sensor_hash().items() for f in metrics.values()])))

def send_metric_stats(metric):
    if metric.metric not in METRIC_WHITELIST:
        return
    #timestamp

    mean = metric.get_mean()
    std = metric.get_std()

    #{'timestamp': timestamp, 'value': mean}
    #{'timestamp': timestamp, 'value': std}
    # POST these!!

def get_aggregate_device(site):
    devices = get_devices(site.rels['ch:devices'])
    return filter(lambda x: x.name == AGGREGATE_DEVICE_NAME, devices)[0]


def update_aggregate_virtual_devices(site, metrics, aggregate_statistics):
    agg_device = get_aggregate_device(site)

    sensors = agg_device.rels['ch:sensors'].rels['items']
    sensor_metrics = [s.metric for s in sensors]

    for metric in metrics:
        for statistic in aggregate_statistics:
            sensor_metric = '%_%' % metric, statistic
            if not in sensor_metric in sensor_metrics:
                #{'sensor-type': 'scalar', 'metric': sensor_metric, 'unit': unit}

def main():
    site = get_site()
    metrics = get_metrics(site)
    sensor_hash = get_sensor_hash(metrics)

    sensor_hash = get_sensor_hash(metrics)
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

        logger.info('Received value of %f from sensor %s' % (in_data.value, sensor))

        sensor.value = in_data.value
        metric = metrics[sensor.metric]
        send_metric_stats(metric)


if __name__ == "__main__":
    main()
