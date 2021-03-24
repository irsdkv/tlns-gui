import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
import random


class Board():
    WIDTH = 21
    HEIGHT = 21

    def __init__(self, w_=None, h_=None):
        self.w = w_ if w_ else self.WIDTH
        self.h = h_ if h_ else self.HEIGHT


WINDOW_MUL_COEF = 20

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


class Point:
    def __init__(self, x_=0, y_=0):
        self.x = x_
        self.y = y_

    def __iter__(self):
        return iter((self.x, self.y))

    def __str__(self):
        return str(self.x) + "," + str(self.y)


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
        self.draw_rect()
        self.line = []

    def draw_rect(self, color=Qt.white, point:Point=None):
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

    def hit(self, point:Point, target_pos:Point=None) -> bool:
        compare_pos = target_pos if target_pos else self.target_pos
        hit_x = (compare_pos.x - WINDOW_MUL_COEF/2) < point.x < (compare_pos.x + WINDOW_MUL_COEF/2)
        hit_y = (compare_pos.y - WINDOW_MUL_COEF/2) < point.y < (compare_pos.y + WINDOW_MUL_COEF/2)
        return hit_x and hit_y

    def redraw_rect(self):
        self.draw_rect(Qt.black)
        self.target_pos = get_random_target_point(self.target_pos)
        self.draw_rect()

    def draw_shot(self, point:Point, target_pos:Point=None):
        print("draw_shot: ", str(point.x) + ", " + str(point.y) + ", hit: " + str(self.hit(point)))
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

    def mouseMoveEvent(self, e):
        if e.buttons() == QtCore.Qt.NoButton:
            point = Point(e.x(), e.y())
            self.draw_point(point)

            self.line.append(point)

        self.update()

    def clear_all(self):
        painter = QtGui.QPainter(self.label.pixmap())
        painter.setBrush(QBrush(Qt.black, Qt.SolidPattern))
        painter.drawRect(0, 0, self.label.pixmap().width(), self.label.pixmap().height())
        self.line = []

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.buttons() == QtCore.Qt.LeftButton:
            old_target_pos = self.target_pos
            point = Point(e.x(), e.y())
            print("target: " + str(self.target_pos) + ", mouse: " + str(point))
            if self.hit(point):
                self.redraw_rect()
                self.redraw_line()
            self.draw_shot(point, old_target_pos)
        elif e.buttons() == QtCore.Qt.RightButton:
            self.clear_all()
            self.draw_rect(point=self.target_pos)
        self.update()


app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec_()