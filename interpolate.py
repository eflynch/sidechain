import numpy
from scipy.spatial import Delaunay
from scipy.interpolate import griddata
from matplotlib import pyplot as plt

class Interpolator(object):
    def __init__(self, sensors, precision, length_transform=None):
        self.sensors = sensors
        self.precision = precision

        if length_transform is None:
            self.length_transform = lambda p: p
        else:
            self.length_transform = length_transform

    def floor(self, x):
        return round(x, self.precision)

    def grid_size(self):
        return (0.1)**self.precision

    def generate_cache(self, minX, maxX, minY, maxY):
        points = numpy.array([self.length_transform([s.x, s.y]) for s in self.sensors])
        tri = Delaunay(points)
        minX = self.floor(minX)
        maxX = self.floor(maxX)
        minY = self.floor(minY)
        maxY = self.floor(maxY)

        self.simplex_lookup = {}
        for x in numpy.mgrid[minX:maxX:self.grid_size()]:
            for y in numpy.mgrid[minY:maxY:self.grid_size()]:
                x = self.floor(x)
                y = self.floor(y)
                self.simplex_lookup[(x,y)] = tri.vertices[tri.find_simplex([x, y])]

    def cache_point(self, x, y):
        points = numpy.array([self.length_transform([s.x, s.y]) for s in self.sensors])
        tri = Delaunay(points)
        self.simplex_lookup[(x, y)] = tri.vertices[tri.find_simplex([x, y])]

    def get_simplex(self, x, y):
        if (self.floor(x), self.floor(y)) not in self.simplex_lookup:
            self.cache_point(self.floor(x), self.floor(y))
        vs = self.simplex_lookup[(self.floor(x), self.floor(y))]
        return [self.sensors[v] for v in vs]

    def interpolate(self, x, y):
        point = self.length_transform([x, y])
        sensors = self.get_simplex(*point)
        points = numpy.array([self.length_transform([s.x, s.y]) for s in sensors])
        values = numpy.array([s.value for s in sensors])
        fill_value = float('inf')
        return griddata(points, values, [point], fill_value=fill_value)[0]

    def interpolate_slow(self, eval_points):
        points = numpy.array([self.length_transform([s.x, s.y]) for s in self.sensors])
        values = numpy.array([s.value for s in self.sensors])
        fill_value = float('inf')
        return griddata(points, values, eval_points, fill_value=fill_value)

    def plot_heat_map(self, minX, maxX, minY, maxY):
        eval_points_x, eval_points_y = numpy.mgrid[minX:maxX:self.grid_size(), minY:maxY:self.grid_size()]

        heatmap = self.interpolate_slow((eval_points_x, eval_points_y))
        plt.imshow(heatmap.T, extent=(minX, maxX, minY, maxY), origin='lower')
        plt.colorbar()

