#!/usr/bin/env python
# Simple depth noise simulator
# Consider implementing model from https://ai2-s2-pdfs.s3.amazonaws.com/a8a6/18363b8dee8037df9133668ec8dcd532ee4e.pdf

import numpy as np
from PIL import Image


class DepthNoiseSim():
    def __init__(self, near, far, mean, sigma):
        self.mean = mean
        self.sigma = sigma
        self.near = near
        self.far = far

    '''Reads and simulate noise on inputpng and write output to outputpng'''
    def process_image(self, inputpng, outputpng):
        a = np.array(Image.open(inputpng)).astype(np.float32) / 1000.0
        self.simulate(a)
        Image.fromarray((a * 1000).astype(np.int32)).save(outputpng)


    '''Simulate noise over depth values in buffer and modifies it'''
    def simulate(self, buffer):
        gauss = np.random.normal(self.mean, self.sigma, buffer.shape)
        buffer += gauss
        noisy = buffer
        noisy[noisy > self.far] = 0
        noisy[noisy < self.near] = 0
        return noisy

