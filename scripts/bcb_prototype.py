import copy

from PyQt5 import QtCore, QtGui, QtWidgets
import random
import asyncio
from PyQt5.QtWidgets import QApplication
from asyncqt import QEventLoop
import qtawesome
import sys
from itertools import count
import tinyproto
import serial
import argparse

from tlns.tlns import *

from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QMessageBox, \
    QComboBox, QDialog, QLabel
from PyQt5.QtCore import Qt, QTimer, QSize, QPoint, QRectF, QSizeF
from PyQt5.QtGui import QFontInfo, QFont, QPen, QBrush, QColor

WINDOW_MUL_COEF = 40

WINDOW_WIDTH = Board.WIDTH * WINDOW_MUL_COEF
WINDOW_HEIGHT = Board.HEIGHT * WINDOW_MUL_COEF

BRIGHTNESS_ARROW = 0x01
BRIGHTNESS_TARGET = PIXEL_MAX_BRIGHTNESS


class ColumnIndicator:
    class Cell:
        def __init__(self, number, brightness):
            self.number = number
            self.brightness = brightness

    def __init__(self, height = 10, percent: float = 100): # percent: from 0. to 100.
        self._percent = percent
        self._height = height
        self._perc_max = 100.
        self._br_max = 100.
        self._cell_weight = self._perc_max / self._height

        self._cells = [self.Cell(idx, 0) for idx in range(0, self._height)]

        self.fill(self._percent)

    def fill(self, percent):
        if percent > 100.:
            percent = 100.
        if percent < 0.:
            percent = 0.
        self._percent = percent
        for cell_idx in range(0, self._height):
            cell_br = self._cell_br(cell_idx, self._percent)
            self._cells[cell_idx] = self.Cell(cell_idx, cell_br)

    def _cell_br(self, cell_idx, percent):
        full_cells_num = percent // self._cell_weight

        if cell_idx < full_cells_num:
            return self._br_max
        elif cell_idx == full_cells_num:
            return (percent % self._cell_weight) * (self._br_max / self._cell_weight)
        else:
            return 0

    def cells(self):
        return copy.copy(self._cells)

    def cell_br(self, cell_idx):
        return self._cells[cell_idx].brightness

    def brightnesses(self):
        for cell in self._cells:
            yield cell.brightness

    def height(self):
        return self._height

    def percent(self):
        return self._percent


class RectangleSumm:
    def __init__(self, width=17, height=17):
        self.w = width
        self._w = width
        self.h = height
        self._h = height

        self._map = [[0 for x in range(self._w)] for y in range(self._h)]

        self._target_point = Point(round(self._w/2), self._h - 1)
        self._arrow_point = Point(round(self._w/2), 0)

        self._tick_counter = 0
        self._tick_counter_max = 2

    def move(self, inc_x, inc_y):
        self._map[self._arrow_point.x][self._arrow_point.y] = 0

        self._arrow_point.x += inc_x
        if self._arrow_point.x < 0: self._arrow_point.x = 0
        if self._arrow_point.x >= self._w: self._arrow_point.x = self._w - 1

        self._arrow_point.y += inc_y
        if self._arrow_point.y < 0: self._arrow_point.y = 0
        if self._arrow_point.y >= self._h: self._arrow_point.y = self._h - 1

        self._map[self._arrow_point.x][self._arrow_point.y] = 1

    def tick(self):
        self._tick_counter += 1
        self._tick_counter = self._tick_counter % self._tick_counter_max

        self._map[self._target_point.x][self._target_point.y] = 1

        mul = 2

        if self._target_point.x == self._arrow_point.x and \
                self._target_point.y == self._arrow_point.y:
            if self._tick_counter % 2:
                self._map[self._target_point.x][self._target_point.y] = 1
            else:
                self._map[self._target_point.x][self._target_point.y] = 0
            return

        if self._tick_counter*mul < self._tick_counter_max:
            self._map[self._target_point.x][self._target_point.y] = 1
        else:
            self._map[self._target_point.x][self._target_point.y] = 0

    def __getitem__(self, i):
        return self._map[i]


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


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, iface, no_path: bool = False, no_target: bool = False):
        super().__init__()

        self.no_path = no_path
        self.no_target = no_target
        self.label = QtWidgets.QLabel()
        canvas = QtGui.QPixmap(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.label.setPixmap(canvas)
        self.setCentralWidget(self.label)
        self.setMouseTracking(True)
        self.centralWidget().setMouseTracking(True)
        self._lines = [1]
        self.line = []
        self.shots = []
        self.board = Board()
        self.p = tinyproto.Hdlc()
        self.p.begin()
        self.ser = serial.Serial(iface, baudrate=115200, bytesize=8, parity='N', stopbits=1, timeout=None)

        self._health_indicator_left = ColumnIndicator(10, 45)
        self._health_indicator_right = ColumnIndicator(10, 45)
        self._rsumm = RectangleSumm()

        self.draw_board()

        timer = QTimer(self)
        timer.setSingleShot(False)
        timer.timeout.connect(self._tick)
        timer.start(500)

        timer_board = QTimer(self)
        timer_board.setSingleShot(False)
        timer_board.timeout.connect(self._write)
        timer_board.start(500)

    def _tick(self):
        self._rsumm.tick()
        self.draw_board(True)

    def _write(self):
        self.write_board_to_uart()

    def draw_picture(self):
        painter = QtGui.QPainter(self.label.pixmap())
        for y_idx in range(self.board.HEIGHT):
            for x_idx in range(self.board.WIDTH):
                br = self.board.get(y_idx, x_idx)
                max_br = PIXEL_MAX_BRIGHTNESS
                col = QColor(int(br * 255 / max_br), int(br * 255 / max_br), int(br * 255 / max_br))

                rect_h = WINDOW_MUL_COEF
                rect_w = WINDOW_MUL_COEF

                rect_y = WINDOW_HEIGHT - int(rect_h * y_idx)
                rect_x = int(rect_w * x_idx)
                rect = QRectF(QPoint(rect_x, rect_y), QSizeF(rect_w, -rect_h))

                painter.setPen(col)
                painter.setBrush(col)
                painter.drawRect(rect)

        painter.end()

    def draw_board(self, write_to_uart=False):
        self.draw_health()
        self.draw_rsumm()
        self.draw_picture()
        if write_to_uart:
            self.write_board_to_uart()
        self.update()

    def draw_health(self, color=Qt.white):
        for idx, br in enumerate(self._health_indicator_left.brightnesses()):
            for x_idx in range(0, 2):
                self.board.set(x_idx, idx*2, int(br/100*0xFF))
                self.board.set(x_idx, idx*2+1, int(br/100*0xFF))
        for idx, br in enumerate(self._health_indicator_right.brightnesses()):
            for x_idx in range(int(self.board.WIDTH - 2), self.board.WIDTH):
                self.board.set(x_idx, idx*2, int(br/100*0xFF))
                self.board.set(x_idx, idx*2+1, int(br/100*0xFF))

    def draw_rsumm(self, color=Qt.white):
        for idx_x in range(self._rsumm.w):
            for idx_y in range(self._rsumm.h):
                br = self._rsumm[idx_x][idx_y] * 100
                self.board.set(2 + idx_x, 2 + idx_y,  int(br/100*0xFF))

    def write_board_to_uart(self):
        self.p.put(self.board.__bytes__())
        #print(str(self.board))
        result = self.p.tx()
        self.ser.write(result)

    def clear_all(self):
        painter = QtGui.QPainter(self.label.pixmap())
        painter.setBrush(QBrush(Qt.black, Qt.SolidPattern))
        painter.drawRect(0, 0, self.label.pixmap().width(), self.label.pixmap().height())
        self.board = Board()
        self.write_board_to_uart()

    def mouseMoveEvent(self, e):
        point = Point(e.x(), e.y())

        self.line.append(point)

        self.update()

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.buttons() == QtCore.Qt.LeftButton:
            pass
        elif e.buttons() == QtCore.Qt.RightButton:
            pass

        self.update()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Down:
            self._health_indicator_left.fill(self._health_indicator_left.percent() - 2)
            self._rsumm.move(0, -1)
        elif event.key() == QtCore.Qt.Key.Key_Up:
            self._health_indicator_left.fill(self._health_indicator_left.percent() + 2)
            self._rsumm.move(0, 1)
        if event.key() == QtCore.Qt.Key.Key_Left:
            self._health_indicator_right.fill(self._health_indicator_right.percent() - 2)
            self._rsumm.move(-1, 0)
        elif event.key() == QtCore.Qt.Key.Key_Right:
            self._health_indicator_right.fill(self._health_indicator_right.percent() + 2)
            self._rsumm.move(1, 0)

        self.draw_board()



def main():
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@', description='')
    parser.add_argument('-d', '--device', help='Serial device path', dest='device', type=str, default='-')
    parser.add_argument('--no-path', help='No path on device', dest='no_path', type=bool, default=False)
    parser.add_argument('--no-target', help='No target', dest='no_target', type=bool, default=False)

    args = parser.parse_args()

    app = QApplication(sys.argv)
    loop = QEventLoop(app)

    font = QFont("Courier New", 7)

    app.setFont(font)

    asyncio.set_event_loop(loop)  # NEW must set the event loop

    if True:
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
    else:
        iface = '/dev/ttyS4'

    print("iface: " + iface)
    window = MainWindow(iface, args.no_path, args.no_target)
    window.show()
    app.exec_()


if __name__ == '__main__':
    main()
