import math
import glob
import time
import copy
import threading
from logging import getLogger
from collections import OrderedDict
import sys
from bitarray import bitarray

logger = getLogger(__name__)
RUNNING_ON_LINUX = 'linux' in sys.platform.lower()

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
        self.pix[x][y] = val

    def set_quietly(self, x, y, val=PIXEL_MAX_BRIGHTNESS):
        if x >= self.w or y >= self.h:
            return
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




def _linux_parse_proc_net_dev(out_ifaces):
    with open('/proc/net/dev') as f:
        for line in f:
            if ':' in line:
                name = line.split(':')[0].strip()
                out_ifaces.insert(0 if 'can' in name else len(out_ifaces), name)
    return out_ifaces


def _linux_parse_ip_link_show(out_ifaces):
    import re
    import subprocess
    import tempfile

    with tempfile.TemporaryFile() as f:
        proc = subprocess.Popen('ip link show', shell=True, stdout=f)
        if 0 != proc.wait(10):
            raise RuntimeError('Process failed')
        f.seek(0)
        out = f.read().decode()

    return re.findall(r'\d+?: ([a-z0-9]+?): <[^>]*UP[^>]*>.*\n *link/can', out) + out_ifaces


def list_ifaces(linux_path, key):
    """Returns dictionary, where key is description, value is the OS assigned name of the port
    linux_path example:
        '/dev/serial/by-id/*'
    Key example:
        lambda s: not ('zubax' in s.lower() and 'babel' in s.lower())"""
    logger.debug('Updating iface list...')
    if RUNNING_ON_LINUX:
        # Linux system
        ifaces = glob.glob(linux_path)
        try:
            ifaces = list(sorted(ifaces, key=key))
        except Exception:
            logger.warning('Sorting failed', exc_info=True)

        # noinspection PyBroadException
        try:
            ifaces = _linux_parse_ip_link_show(ifaces)       # Primary
        except Exception as ex:
            logger.warning('Could not parse "ip link show": %s', ex, exc_info=True)
            ifaces = _linux_parse_proc_net_dev(ifaces)       # Fallback

        out = OrderedDict()
        for x in ifaces:
            out[x] = x

        return out
    else:
        # Windows, Mac, whatever
        from PyQt5 import QtSerialPort

        out = OrderedDict()
        for port in QtSerialPort.QSerialPortInfo.availablePorts():
            out[port.description()] = port.systemLocation()

        return out


class BackgroundIfaceListUpdater:
    UPDATE_INTERVAL = 0.5

    def __init__(self, linux_path, key):
        self.linux_path = linux_path
        self.key = key
        self._ifaces = list_ifaces(linux_path, key)
        self._thread = threading.Thread(target=self._run, name='iface_lister', daemon=True)
        self._keep_going = True
        self._lock = threading.Lock()

    def __enter__(self):
        logger.debug('Starting iface list updater')
        self._thread.start()
        return self

    def __exit__(self, *_):
        logger.debug('Stopping iface list updater...')
        self._keep_going = False
        self._thread.join()
        logger.debug('Stopped iface list updater')

    def _run(self):
        while self._keep_going:
            time.sleep(self.UPDATE_INTERVAL)
            new_list = list_ifaces(self.linux_path, self.key)
            with self._lock:
                self._ifaces = new_list

    def get_list(self):
        with self._lock:
            return copy.copy(self._ifaces)
