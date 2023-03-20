from PyQt5 import QtCore, QtGui, QtWidgets
import random
import asyncio
from PyQt5.QtWidgets import QApplication
from asyncqt import QEventLoop
import qtawesome
import sys
from itertools import count
import tinyproto
from tlns.tlns import Board, PIXEL_MAX_BRIGHTNESS
import serial
import argparse

from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QMessageBox, \
    QComboBox, QDialog, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFontInfo, QFont, QPen, QBrush

from tlns.tlns import *
from util.util import *

WINDOW_MUL_COEF = 40

WINDOW_WIDTH = Board.WIDTH * WINDOW_MUL_COEF
WINDOW_HEIGHT = Board.HEIGHT * WINDOW_MUL_COEF

BRIGHTNESS_ARROW = 0x01
BRIGHTNESS_TARGET = PIXEL_MAX_BRIGHTNESS

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



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, iface, no_path: bool = False, no_target: bool = False, screen=None):
        super().__init__()


        self.showFullScreen()

        self._screen = screen
        size = screen.size()
        rect = screen.availableGeometry()
        self._w, self._h = rect.width(), rect.height()

        min_axis = self._w if self._w < self._h else self._h
        self._mul_coef = min_axis / Board.WIDTH

        self._mul_coef_x = self._w / Board.WIDTH
        self._mul_coef_y = self._h / Board.HEIGHT

        self.no_path = no_path
        self.no_target = no_target
        self.label = QtWidgets.QLabel()
        canvas = QtGui.QPixmap(self._w, self._h)
        self.label.setPixmap(canvas)
        self.setCentralWidget(self.label)
        self.setMouseTracking(True)
        self.centralWidget().setMouseTracking(True)
        self.target_pos = self.get_random_target_point()
        self.draw_target()
        self.line = []
        self.path_rects = []
        self.shots = []
        self.board = Board()
        self.p = tinyproto.Hdlc()
        self.p.begin()
        self.ser = serial.Serial(iface, baudrate=115200, bytesize=8, parity='N', stopbits=1, timeout=None)
        self.update_board_target(None, self.target_pos)
        self.write_board_to_uart()
        self.prev_pos = None

    def get_x(self, point_x: int) -> int:
        assert point_x < Board.WIDTH
        assert point_x >= 0
        return int(point_x * self._mul_coef_x + self._mul_coef_x / 2)

    def get_y(self, point_y: int) -> int:
        assert point_y < Board.HEIGHT
        assert point_y >= 0
        return int(point_y * self._mul_coef_y + self._mul_coef_y / 2)

    def get_xy(self, w, h) -> (int, int):
        return self.get_x(w), self.get_y(h)

    def get_random_target_pos(self, current_pos_x: int = None, current_pos_y: int = None) -> (int, int):
        random.seed()
        w = random.randint(1, Board.WIDTH - 2)
        h = random.randint(1, Board.HEIGHT - 2)

        if current_pos_x:
            while current_pos_x == w:
                w = random.randint(1, Board.WIDTH - 2)

        if current_pos_y:
            while current_pos_y == h:
                w = random.randint(1, Board.HEIGHT - 2)

        return self.get_x(w), self.get_y(h)

    def get_random_target_point(self, point_: Point = None) -> Point:
        if point_:
            point = point_
        else:
            point = Point(None, None)
        return Point(*self.get_random_target_pos(*point))

    def draw_target(self, color=Qt.white, point:Point=None):
        if self.no_target:
            return
        print("target_pos: ", str(self.target_pos.x) + ", " + str(self.target_pos.y))
        if not point:
            point = self.target_pos
        points = list()
        points.append(point)
        points.append(Point(point.x - self._mul_coef_x, point.y))
        points.append(Point(point.x - self._mul_coef_x, point.y - self._mul_coef_y/2))
        points.append(Point(point.x - self._mul_coef_x, point.y + self._mul_coef_y/2))
        points.append(Point(point.x + self._mul_coef_x, point.y - self._mul_coef_y/2))
        points.append(Point(point.x + self._mul_coef_x, point.y))
        points.append(Point(point.x + self._mul_coef_x, point.y + self._mul_coef_y/2))
        points.append(Point(point.x + self._mul_coef_x, point.y + self._mul_coef_y/2))
        points.append(Point(point.x, point.y + self._mul_coef_y/2))
        points.append(Point(point.x, point.y - self._mul_coef_y/2))
        painter = QtGui.QPainter(self.label.pixmap())
        pen = QtGui.QPen()
        pen.setWidth(self._mul_coef_x)
        pen.setColor(color)
        painter.setPen(pen)
        for point_ in points:
            painter.drawPoint(*point_)
        painter.end()

    def redraw_path_rects(self):
        for point in self.path_rects:
            self.draw_path_rect(point)

    def draw_path_rect(self, point:Point, color=Qt.gray):
        if self.hit(point):
            return

        rect_pos = Board.get_pos(point, self._mul_coef_x, self._mul_coef_y)

        if self.no_path and self.prev_pos:
            x_prev = int(self.prev_pos.x / self._mul_coef_x)
            y_prev = int(self.prev_pos.y / self._mul_coef_y)
            x_rect = int(rect_pos.x / self._mul_coef_x)
            y_rect = int(rect_pos.y / self._mul_coef_y)
            if x_prev != x_rect or y_prev != y_rect:
                self.board.unset(x_prev, y_prev)
                self.board.set(x_rect, y_rect, BRIGHTNESS_ARROW)
                self.prev_pos = rect_pos
                self.write_board_to_uart()

        if rect_pos in self.path_rects:
            return

        print("rect_pos: ", str(rect_pos))

        painter = QtGui.QPainter(self.label.pixmap())
        painter.setPen(QPen(Qt.magenta, 2, Qt.SolidLine))
        painter.setBrush(QBrush(color, Qt.SolidPattern))
        painter.drawRect(rect_pos.x, rect_pos.y, self._mul_coef_x, self._mul_coef_y)

        if False and self.path_rects:
            painter.setPen(QPen(color, 2, Qt.SolidLine))
            if self.path_rects[-1].x == rect_pos.x:
                x = rect_pos.x + 2
                if rect_pos.y > self.path_rects[-1].y:
                    y = rect_pos.y - 2
                else:
                    y = self.path_rects[-1].y - 2
                painter.drawRect(x, y, self._mul_coef_x-4, 4)
            if self.path_rects[-1].y == rect_pos.y:
                y = rect_pos.y + 2
                if rect_pos.x > self.path_rects[-1].x:
                    x = rect_pos.x - 2
                else:
                    x = self.path_rects[-1].x - 2
                    print("rect_pos.x < self.path_rects[-1].x")
                painter.drawRect(x, y, 4, self._mul_coef_x-4)

        painter.end()

        self.redraw_line()
        self.redraw_shots()
        self.draw_target()
        if rect_pos not in self.path_rects:
            #for old_rect in self.path_rects:
            #    self.board.set(int(old_rect.x/self._mul_coef), int(old_rect.y/self._mul_coef), 0)
            if not self.no_path:
                self.board.set(int(rect_pos.x/self._mul_coef_x), int(rect_pos.y/self._mul_coef_y), BRIGHTNESS_ARROW)
                self.write_board_to_uart()
            self.path_rects.append(rect_pos)
            self.prev_pos = rect_pos

        if not self.no_target:
            self.board.set(int(self.target_pos.x/self._mul_coef_x), int(self.target_pos.y/self._mul_coef_y), BRIGHTNESS_TARGET)

    def write_board_to_uart(self):
        self.p.put(self.board.__bytes__())
        print(str(self.board))
        result = self.p.tx()
        self.ser.write(result)

    def redraw_path(self):
        self.redraw_path_rects()
        self.redraw_line()
        self.redraw_shots()

    def hit(self, point:Point, target_pos:Point=None) -> bool:
        compare_pos = target_pos if target_pos else self.target_pos
        hit_x = (compare_pos.x - self._mul_coef_x/2) - self._mul_coef_x < point.x < (compare_pos.x + self._mul_coef_x/2) + self._mul_coef_x
        hit_y = (compare_pos.y - self._mul_coef_y/2) - self._mul_coef_y < point.y < (compare_pos.y + self._mul_coef_y/2) + self._mul_coef_y
        return hit_x and hit_y

    def update_board_target(self, old_pos, new_pos):
        def big_point(point, val):
            self.board.set(int(point.x / self._mul_coef_x), int(point.y / self._mul_coef_y), val)
#            return
            x = int(point.x / self._mul_coef_x)
            y = int(point.y / self._mul_coef_y)
            if y > 0:
                self.board.set_quietly(x, y - 1, val)
            self.board.set_quietly(x, y + 1, val)
            if x > 0 and y > 1:
                self.board.set_quietly(x - 1, y - 1, val)
            if x > 0:
                self.board.set_quietly(x - 1, y + 1, val)
            if y > 0:
                self.board.set_quietly(x + 1, y - 1, val)
            self.board.set_quietly(x + 1, y + 1, val)
            if x > 0:
                self.board.set_quietly(x - 1, y, val)
            self.board.set_quietly(x + 1, y, val)
        if self.no_target:
            return
        if old_pos:
            big_point(old_pos, 0)
        big_point(new_pos, BRIGHTNESS_TARGET)

    def redraw_target(self, new_tg=True):
        old_pos = copy.copy(self.target_pos)
        self.board.set(int(self.target_pos.x/self._mul_coef_x), int(self.target_pos.y/self._mul_coef_y), 0)
        self.draw_target(Qt.black)
        if new_tg:
            self.target_pos = self.get_random_target_point(self.target_pos)
        self.draw_target()
        self.update_board_target(old_pos, self.target_pos)

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
        self.board = Board()
        self.write_board_to_uart()

    def mouseMoveEvent(self, e):
        point = Point(e.x(), e.y())
        self.draw_point(point)
        self.draw_path_rect(point)

        if self.hit(point):
            self.clear_all()
            self.redraw_target(False)
        else:
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
                self.write_board_to_uart()
            else:
                self.redraw_path()
        elif e.buttons() == QtCore.Qt.RightButton:
            self.clear_all()
            self.draw_target(point=self.target_pos)
        self.update()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.showNormal()
        if event.key() == QtCore.Qt.Key.Key_F11:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

        self.update()


def main():
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@', description='')
    parser.add_argument('-d', '--device', help='Serial device path', dest='device', type=str, default='-')
    parser.add_argument('--no-path', help='No path on device', dest='no_path', type=bool, default=False)
    parser.add_argument('--no-target', help='No target', dest='no_target', type=bool, default=False)

    args = parser.parse_args()

    app = QApplication(sys.argv)
    loop = QEventLoop(app)

    screen = app.primaryScreen()

    font = QFont("Courier New", 7)

    app.setFont(font)

    asyncio.set_event_loop(loop)  # NEW must set the event loop

    if args.device == '-':
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
    else:
        iface = args.device

    print("iface: " + iface)
    window = MainWindow(iface, args.no_path, args.no_target, screen=screen)
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()
