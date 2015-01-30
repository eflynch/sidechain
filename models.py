import numpy
from matplotlib import pyplot as plt

from interpolate import Interpolator

def get_models(site):
    device_hash = {}
    sensor_hash = {}
    sensors_by_metric = {}
    for index, device_doc in enumerate(site.rels['ch:devices'].rels['items']):
        if 'geoLocation' in device_doc:
            latitude = device_doc['geoLocation']['latitude']
            longitude = device_doc['geoLocation']['longitude']
            elevation = device_doc['geoLocation']['elevation']
        else:
            latitude = longitude = elevation = None

        device = Device(latitude, longitude, elevation, index)
        device_hash[index] = device
        for chain_sensor in device_doc.rels['ch:sensors'].rels['items']:
            url = chain_sensor.links.self.href
            sensor = Sensor(url=url,
                            metric=chain_sensor.metric,
                            device=device)
            sensor_hash[url] = sensor
            if chain_sensor.metric not in sensors_by_metric:
                sensors_by_metric[chain_sensor.metric] = []
            sensors_by_metric[chain_sensor.metric].append(sensor)

    metric_hash = {metric_name: Metric(metric_name, sensors_by_metric[metric_name]) for metric_name in sensors_by_metric}

    return metric_hash, device_hash, sensor_hash

class Metric(object):
    def __init__(self, metric, sensors):
        self.metric = metric
        self.sensors = sensors
        self._norm_bounds = None
        self.interpolator = self.generate_interpolator(sensors)

    @property
    def norm_bounds(self):
        if self._norm_bounds is not None:
            return self._norm_bounds
        points = numpy.array([[s.x, s.y] for s in self.sensors])
        self._norm_bounds = (
            min(points[:,0]),                       # origin_x
            min(points[:,1]),                       # origin_y
            max(points[:,0]) - min(points[:,0]),    # width
            max(points[:,1]) - min(points[:,1])     # length
        )
        return self._norm_bounds

    def _norm_x(self, x):
        return (x - self.norm_bounds[0]) * 100. / self.norm_bounds[2]

    def _norm_y(self, y):
        return (y - self.norm_bounds[1]) * 100. / self.norm_bounds[3]

    def get_points(self, exclude_no_data=False):
        if exclude_no_data:
            return numpy.array([[s.x, s.y] for s in self.sensors if s.value < float('inf')])
        else:
            return numpy.array([[s.x, s.y] for s in self.sensors])

    def get_values(self, exclude_no_data=False):
        if exclude_no_data:
            return numpy.array([s.value for s in self.sensors if s.value < float('inf')])
        else:
            return numpy.array([s.value for s in self.sensors])

    def get_normalized_points(self, exclude_no_data=False):
        points = self.get_points(exclude_no_data)
        points[:,0] = self._norm_x(points[:,0])
        points[:,1] = self._norm_y(points[:,1])
        return points

    def generate_interpolator(self, sensors, precision=0):
        if len(sensors) < 4:
            return None
        length_transform = lambda p: [self._norm_x(p[0]), self._norm_y(p[1])]
        interpolator = Interpolator(sensors, precision, length_transform)
        interpolator.generate_cache(0, 100, 0, 100)
        return interpolator

    def get_value(self, x, y):
        if not self.interpolator:
            raise Exception('Cannot interpolate %s' % self.metric)
        return self.interpolator.interpolate(x, y)

    def get_mean(self):
        values = self.get_values(True)
        return numpy.mean(values)

    def get_std(self):
        values = self.get_values(True)
        return numpy.std(values)

    def plot_heat_map(self):
        if not self.interpolator:
            raise Exception('Cannot interpolate %s' % self.metric)
        self.interpolator.plot_heat_map(0, 100, 0, 100)

    def plot_sensors(self):
        points = self.get_normalized_points()
        indices = numpy.array([s.device.index for s in self.sensors])
        plt.plot(points[:,0], points[:,1], 'w.', ms=3)
        for i,j,index in zip(points[:,0], points[:,1], indices):
            plt.annotate(index, xy=(i,j))

    def plot_scatter(self):
        points = self.get_normalized_points(True)
        values = self.get_values(True)
        area = numpy.pi * 15 * (values - min(values)) / (max(values)-min(values))
        plt.scatter(points[:,0], points[:,1], s=area)

    def get_sensor_hash(self):
        return {s.url: s for s in self.sensors}


class Device(object):
    def __init__(self, latitude, longitude, elevation, index):
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
        self.index = index

    @property
    def x(self):
        if self.latitude is None:
            return 41.9034748
        if self.latitude == 0.0:
            return 41.9034748
        return self.latitude

    @property
    def y(self):
        if self.longitude is None:
            return -70.573021
        if self.longitude == 0.0:
            return -70.573021
        return self.longitude
    

class Sensor(object):
    def __init__(self, url, metric, device):
        self.url = url
        self.metric = metric
        self.device = device
        self._value = None

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        return self.url == other.url

    @property
    def x(self):
        return self.device.x
     
    @property
    def y(self):
        return self.device.y

    @property
    def value(self):
        if self._value:
            return self._value
        else:
            return float('inf')
    @value.setter
    def value(self, value):
        self._value = value

    @property
    def data_url(self):
        identifier = self.url.split('/')[-1]
        return 'http://chain-api.media.mit.edu/scalar_data/?sensor_id=%s' % identifier
    
    
    def __repr__(self):
        return "Sensor %s, (metric=%s)" % \
            (self.url, self.metric)
