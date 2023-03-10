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