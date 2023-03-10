import math
from logging import getLogger
import sys


PIXEL_MAX_BRIGHTNESS = 0xFF
PIXEL_HALF_BRIGHTNESS = 0x80

class Point:
    def __init__(self, x_=0, y_=0):
        self.x = x_
        self.y = y_

    def __iter__(self):
        return iter((self.x, self.y))

    def __str__(self):
        return str(self.x) + "," + str(self.y)

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


class Board():
    WIDTH = 21
    HEIGHT = 21

    def __init__(self, w_=None, h_=None):
        self.w = w_ if w_ else self.WIDTH
        self.h = h_ if h_ else self.HEIGHT
        self.pix = []
        for _ in range(self.h):
            row = []
            for _ in range(self.w):
                row.append(0)
            self.pix.append(row)

    def set(self, x, y, val=PIXEL_MAX_BRIGHTNESS):
        assert x < self.w
        assert y < self.h
        self.set_quietly(x, y, val)

    def set_quietly(self, x, y, val=PIXEL_MAX_BRIGHTNESS):
        if x >= self.w or y >= self.h:
            return
        if isinstance(val, float) and val <= 1.:
            val = int(val * PIXEL_MAX_BRIGHTNESS)
        self.pix[x][y] = val

    def unset(self,  x, y):
        self.set(x, y, 0)

    def get(self, x, y):
        assert x < self.w
        assert y < self.h
        return self.pix[y][x]

    def get_quietly(self, x, y):
        if x >= self.w or y >= self.h:
            return 0
        return self.pix[y][x]

    @staticmethod
    def get_pos(point:Point, mul:int=1) -> Point:
        x = math.floor(point.x / mul)
        y = math.floor(point.y / mul)

        return Point(x*mul, y*mul)

    def __str__(self):
        string = ""
        for x in reversed(range(self.w)):
            string = string + str(x) + ':\t'
            for y in range(self.h):
                brightness = self.get(x, y)
                if brightness == 0:
                    c = '-'
                elif brightness <= 0x80:
                     c = '+'
                else:
                    c = 'o'
                string = string + c
            string = string + '\n'
        return string

    def __bytes__(self):
        bytes_ = b''
        pixels = []
        for x in range(self.w):
            for y in range(self.h):
                pixels.append(self.get(y, x))

        return bytearray(pixels)

    def tobytes(self, inverse=False, mirror_y=False, mirror_x=False):
        bytes_ = b''
        pixels = []
        for x in range(self.w):
            for y in range(self.h):
                y_final = y if not mirror_y else (self.h - y - 1)
                x_final = x if not mirror_x else (self.w - x - 1)
                if not inverse:
                    pixels.append(self.get(y_final, x_final))
                else:
                    pixels.append(self.get(x_final, y_final))

        return bytearray(pixels)

