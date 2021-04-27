from PyQt5 import QtCore, QtGui, QtWidgets
import random
import math
import asyncio
from PyQt5.QtWidgets import QApplication
from asyncqt import QEventLoop
import qtawesome
import sys
import glob
import time
import copy
import threading
from itertools import count

from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QMessageBox, \
    QComboBox, QDialog, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFontInfo, QFont, QPen, QBrush
from logging import getLogger
from collections import OrderedDict

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


def get_monospace_font():
    preferred = ['Consolas', 'DejaVu Sans Mono', 'Monospace', 'Lucida Console', 'Monaco']
    for name in preferred:
        font = QFont(name)
        if QFontInfo(font).fixedPitch():
            return font

    font = QFont()
    font.setStyleHint(QFont().Monospace)
    font.setFamily('monospace')
    return font


def get_icon(name):
    return qtawesome.icon('fa.' + name)


def show_error(title, text, informative_text, parent=None, blocking=False):
    mbox = QMessageBox(parent)

    mbox.setWindowTitle(str(title))
    mbox.setText(str(text))
    if informative_text:
        mbox.setInformativeText(str(informative_text))

    mbox.setIcon(QMessageBox.Critical)
    mbox.setStandardButtons(QMessageBox.Ok)
    mbox.setMinimumWidth(1000)
    mbox.setMinimumHeight(800)

    if blocking:
        mbox.exec()
    else:
        mbox.show()     # Not exec() because we don't want it to block!


def run_setup_window():

    dialog = QDialog()

    icon = get_icon("plane")

    dialog.setWindowTitle('Interface Setup')
    dialog.setWindowIcon(icon)
    dialog.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
    dialog.setAttribute(Qt.WA_DeleteOnClose)              # This is required to stop background timers!
    ifaces = None

    combo = QComboBox(dialog)
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
    combo.setFont(get_monospace_font())

    result = None

    def on_ok():
        nonlocal result
        result_key = str(combo.currentText()).strip()
        if not result_key:
            show_error('Invalid parameters', 'Interface name cannot be empty', 'Please select a valid interface',
                       parent=dialog)
            return
        try:
            result = ifaces[result_key]
        except KeyError:
            result = result_key
        dialog.close()


    ok_button = QPushButton("Connect")
    ok_button.clicked.connect(on_ok)

    layout = QVBoxLayout()

    layout.addWidget(QLabel("Select interface:"))
    layout.addWidget(combo)

    layout.addWidget(ok_button)

    dialog.setLayout(layout)

    def update_iface_list():
        nonlocal ifaces
        ifaces = iface_lister.get_list()
        known_keys = set()
        remove_indices = []
        was_empty = combo.count() == 0
        # Marking known and scheduling for removal
        for idx in count():
            tx = combo.itemText(idx)
            if not tx:
                break
            known_keys.add(tx)
            if tx not in ifaces:
                remove_indices.append(idx)
        # Removing - starting from the last item in order to retain indexes
        for idx in remove_indices[::-1]:
            combo.removeItem(idx)
        # Adding new items - starting from the last item in order to retain the final order
        for key in list(ifaces.keys())[::-1]:
            if key not in known_keys:
                combo.insertItem(0, key)

        # Updating selection
        if was_empty:
            combo.setCurrentIndex(0)

    with BackgroundIfaceListUpdater('/dev/tty*', lambda s: not ('px4_fmu' in s.lower())) as iface_lister:
        update_iface_list()
        timer = QTimer(dialog)
        timer.setSingleShot(False)
        timer.timeout.connect(update_iface_list)
        timer.start(int(BackgroundIfaceListUpdater.UPDATE_INTERVAL / 2 * 1000))
        dialog.exec()


    return result


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


WINDOW_MUL_COEF = 20

class Board():
    WIDTH = 21
    HEIGHT = 21

    def __init__(self, w_=None, h_=None):
        self.w = w_ if w_ else self.WIDTH
        self.h = h_ if h_ else self.HEIGHT

    @staticmethod
    def get_pos(point:Point, mul:int=WINDOW_MUL_COEF) -> Point:
        x = math.floor(point.x / mul)
        y = math.floor(point.y / mul)

        return Point(x*mul, y*mul)



WINDOW_WIDTH = Board.WIDTH * WINDOW_MUL_COEF
WINDOW_HEIGHT = Board.HEIGHT * WINDOW_MUL_COEF


def get_x(point_x: int) -> int:
    assert point_x < Board.WIDTH
    assert point_x >= 0
    return int(point_x * WINDOW_MUL_COEF + WINDOW_MUL_COEF/2)


def get_y(point_y: int) -> int:
    assert point_y < Board.HEIGHT
    assert point_y >= 0
    return int(point_y * WINDOW_MUL_COEF + WINDOW_MUL_COEF/2)


def get_xy(w,h) -> (int, int):
    return get_x(w), get_y(h)


def get_random_target_pos(current_pos_x:int = None, current_pos_y:int = None) -> (int, int):
    random.seed()
    w = random.randint(0, Board.WIDTH - 1)
    h = random.randint(0, Board.HEIGHT - 1)

    if current_pos_x:
        while current_pos_x == w:
            w = random.randint(0, Board.WIDTH - 1)

    if current_pos_y:
        while current_pos_y == h:
            w = random.randint(0, Board.HEIGHT - 1)

    return get_x(w), get_y(h)


def get_random_target_point(point_: Point = None) -> Point:
    if point_:
        point = point_
    else:
        point = Point(None, None)
    return Point(*get_random_target_pos(*point))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.label = QtWidgets.QLabel()
        canvas = QtGui.QPixmap(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.label.setPixmap(canvas)
        self.setCentralWidget(self.label)
        self.setMouseTracking(True)
        self.centralWidget().setMouseTracking(True)
        self.target_pos = get_random_target_point()
        self.draw_target()
        self.line = []
        self.path_rects = []
        self.shots = []

    def draw_target(self, color=Qt.white, point:Point=None):
        print("target_pos: ", str(self.target_pos.x) + ", " + str(self.target_pos.y))
        if not point:
            point = self.target_pos
        painter = QtGui.QPainter(self.label.pixmap())
        pen = QtGui.QPen()
        pen.setWidth(WINDOW_MUL_COEF)
        pen.setColor(color)
        painter.setPen(pen)
        painter.drawPoint(*point)
        painter.end()

    def redraw_path_rects(self):
        for point in self.path_rects:
            self.draw_path_rect(point)

    def draw_path_rect(self, point:Point, color=Qt.gray):
        if self.hit(point):
            return

        rect_pos = Board.get_pos(point)

        if rect_pos in self.path_rects:
            return

        print("rect_pos: ", str(rect_pos))

        painter = QtGui.QPainter(self.label.pixmap())
        painter.setPen(QPen(Qt.magenta, 2, Qt.SolidLine))
        painter.setBrush(QBrush(color, Qt.SolidPattern))
        painter.drawRect(rect_pos.x, rect_pos.y, WINDOW_MUL_COEF, WINDOW_MUL_COEF)

        if False and self.path_rects:
            painter.setPen(QPen(color, 2, Qt.SolidLine))
            if self.path_rects[-1].x == rect_pos.x:
                x = rect_pos.x + 2
                if rect_pos.y > self.path_rects[-1].y:
                    y = rect_pos.y - 2
                else:
                    y = self.path_rects[-1].y - 2
                painter.drawRect(x, y, WINDOW_MUL_COEF-4, 4)
            if self.path_rects[-1].y == rect_pos.y:
                y = rect_pos.y + 2
                if rect_pos.x > self.path_rects[-1].x:
                    x = rect_pos.x - 2
                else:
                    x = self.path_rects[-1].x - 2
                    print("rect_pos.x < self.path_rects[-1].x")
                painter.drawRect(x, y, 4, WINDOW_MUL_COEF-4)

        painter.end()

        self.redraw_line()
        self.redraw_shots()
        self.draw_target()
        if rect_pos not in self.path_rects:
            self.path_rects.append(rect_pos)

    def redraw_path(self):
        self.redraw_path_rects()
        self.redraw_line()
        self.redraw_shots()

    def hit(self, point:Point, target_pos:Point=None) -> bool:
        compare_pos = target_pos if target_pos else self.target_pos
        hit_x = (compare_pos.x - WINDOW_MUL_COEF/2) < point.x < (compare_pos.x + WINDOW_MUL_COEF/2)
        hit_y = (compare_pos.y - WINDOW_MUL_COEF/2) < point.y < (compare_pos.y + WINDOW_MUL_COEF/2)
        return hit_x and hit_y

    def redraw_target(self):
        self.draw_target(Qt.black)
        self.target_pos = get_random_target_point(self.target_pos)
        self.draw_target()

    def redraw_shots(self):
        for point, target_pos in self.shots:
            self.draw_shot(point, target_pos)

    def draw_shot(self, point:Point, target_pos:Point=None):
        painter = QtGui.QPainter(self.label.pixmap())
        painter.setPen(QPen(Qt.green, 2, Qt.SolidLine))
        color = Qt.red if self.hit(point, target_pos) else Qt.white
        painter.setBrush(QBrush(color, Qt.SolidPattern))
        painter.drawEllipse(point.x - 7, point.y - 7, 14, 14)

    def draw_point(self, point:Point):
        painter = QtGui.QPainter(self.label.pixmap())
        pen = QtGui.QPen()
        pen.setWidth(2)
        pen.setColor(Qt.cyan)
        painter.setPen(pen)
        painter.drawPoint(*point)
        painter.end()

    def redraw_line(self):
        for point in self.line:
            self.draw_point(point)

    def clear_all(self):
        painter = QtGui.QPainter(self.label.pixmap())
        painter.setBrush(QBrush(Qt.black, Qt.SolidPattern))
        painter.drawRect(0, 0, self.label.pixmap().width(), self.label.pixmap().height())
        self.line = []
        self.path_rects = []
        self.shots = []

    def mouseMoveEvent(self, e):
        point = Point(e.x(), e.y())
        self.draw_point(point)
        self.draw_path_rect(point)

        self.line.append(point)

        self.update()

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.buttons() == QtCore.Qt.LeftButton:
            old_target_pos = self.target_pos
            point = Point(e.x(), e.y())
            self.shots.append((point, old_target_pos))
            print("target: " + str(self.target_pos) + ", mouse: " + str(point))
            if self.hit(point):
                self.path_rects = []
                self.clear_all()
                self.redraw_line()
                self.redraw_target()
            else:
                self.redraw_path()
        elif e.buttons() == QtCore.Qt.RightButton:
            self.clear_all()
            self.draw_target(point=self.target_pos)
        self.update()


def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)

    font = QFont("Courier New", 7)

    app.setFont(font)

    asyncio.set_event_loop(loop)  # NEW must set the event loop
    while True:
        # Asking the user to specify which interface to work with
        try:
            iface = run_setup_window()
            if not iface:
                sys.exit(0)
        except Exception as ex:
            show_error('Fatal error', 'Could not list available interfaces', ex, blocking=True)
            sys.exit(1)

        break

    print("iface: " + iface)
    window = MainWindow()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()