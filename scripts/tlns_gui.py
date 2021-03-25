import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
import random
import math


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


app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec_()