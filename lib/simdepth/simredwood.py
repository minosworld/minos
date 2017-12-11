#!/usr/bin/env python
# Depth noise simulator from http://redwood-data.org/indoor/dataset.html
# Simulates Kinect noise with distortion model that is loaded from file
# This noise simulator has the following issues:
# - It is not very robust (resolution was hard coded)
# - It is also extremely slow!  Takes about 1sec frame with noise enabled for 320x320


import numpy as np
import glob
import os
from PIL import Image
from sys import argv
from multiprocessing import Pool


class RedwoodDepthNoiseSim:
    def __init__(self, model_filename=None):
        self.distmodel = None
        if model_filename is not None:
            self.loaddistmodel(model_filename)

    '''Loads distortion model'''
    def loaddistmodel(self, fname):
        data = np.loadtxt(fname, comments='%', skiprows=5)
        dist = np.empty([80, 80, 5])

        for y in range(0, 80):
            for x in range(0, 80):
                idx = (y * 80 + x) * 23 + 3
                if (data[idx:idx + 5] < 8000).all():
                    dist[y, x, :] = 0
                else:
                    dist[y, x, :] = data[idx + 15: idx + 20]
        self.distmodel = dist

    def distort(self, x, y, z):
        i2 = int((z + 1) / 2)
        i1 = i2 - 1
        a = (z - (i1 * 2 + 1)) / 2
        x = int(x / 8)
        y = int(y / 6)
        f = (1 - a) * self.distmodel[y, x, min(max(i1, 0), 4)] + a * self.distmodel[y, x, min(i2, 4)]

        if f == 0:
            return 0
        else:
            return z / f

    '''Reads and simulate noise on inputpng and write output to outputpng'''
    def process_image(self, inputpng, outputpng):
        # convert from grayscale uint8 to float32
        a = np.array(Image.open(inputpng)).astype(np.float32) / 1000.0
        self.simulate(a)
        Image.fromarray((a * 1000).astype(np.int32)).save(outputpng)

    '''Simulate noise over depth values in buffer and modifies it'''
    def simulate(self, buffer):
        a = buffer
        b = np.copy(a)
        it = np.nditer(a, flags=['multi_index'], op_flags=['writeonly'])

        ymax = buffer.shape[0] - 1
        xmax = buffer.shape[1] - 1
        while not it.finished:
            # pixel shuffle
            x = min(max(round(it.multi_index[1] + np.random.normal(0, 0.25)), 0), xmax)
            y = min(max(round(it.multi_index[0] + np.random.normal(0, 0.25)), 0), ymax)

            # downsample
            d = b[y - y % 2, x - x % 2]

            # distortion
            d = self.distort(x, y, d)

            # quantization and high freq noise
            if d == 0:
                it[0] = 0
            else:
                denom = round((35.130 / d + np.random.normal(0, 0.027778)) * 8)
                if denom != 0:
                    it[0] = 35.130 * 8 / denom
                else:
                    it[0] = d

            it.iternext()
        return a


if __name__ == "__main__":
    if (len(argv) < 4):
        print('Usage: {0} <input png dir> <output png dir> <distortion model>'.format(argv[0]))
        exit(0)

    s = RedwoodDepthNoiseSim()
    s.loaddistmodel(argv[3])

    ifiles = glob.glob(argv[1] + '/*.png')
    ofiles = [argv[2] + '/' + os.path.basename(f) for f in ifiles]
    print('Processing %d files' % len(ifiles))
    param = zip(ifiles, ofiles)

    p = Pool(8)
    p.starmap(s.process_image, param)
