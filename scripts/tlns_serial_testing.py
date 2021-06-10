import toml
from tlns.tlns import *
import tinyproto
import argparse
import serial


class Figure():

    def in_fig(self, x, y):
        return False


class Origin():
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Rectangle(Figure):
    def __init__(self, widht, height, thickness, filled, origin_x=0, origin_y=0):
        super(Rectangle, self).__init__()
        self.w = widht
        self.h = height
        self.t = thickness
        self.filled = filled
        self.origin = Origin(origin_x, origin_y)


    def in_fig(self, x, y):
        if not self.filled:
            in_x = self.origin.x <= x < (self.origin.x + self.t) \
                   or (self.origin.x + self.w - self.t) <= x < (self.origin.x + self.w)
            in_y = self.origin.y <= y < (self.origin.y + self.t) \
                   or (self.origin.y + self.h - self.t) <= y < (self.origin.y + self.h)
        else:
            in_x = self.origin.x <= x < (self.origin.x + self.w)
            in_y = self.origin.y <= y < (self.origin.y + self.h)
        return (in_x or in_y) \
               and ((x < self.origin.x + self.w) and (x >= self.origin.x)) \
               and ((y < self.origin.y + self.h) and (y >= self.origin.y))


def render(board:Board, figure:Figure):
    if isinstance(figure, Rectangle):
        for x in range(board.w):
            for y in range(board.h):
                board.set(x, y, figure.in_fig(x, y))


def main():
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@', description='')
    parser.add_argument('TOML_CONFIG', type=str, help='TOML config file', default='data/serial_test.toml')
    parser.add_argument('-d', '--device', help='Serial device path', dest='device', type=str)
    parser.add_argument('-B', '--baud', help='Serial device baudrate', dest='baud', type=int, default=9600)

    args = parser.parse_args()

    board = Board()

    toml_config_path = args.TOML_CONFIG

    with open(args.TOML_CONFIG, "r") as toml_config_file:
        toml_config_str = toml_config_file.read()
        config: dict = toml.loads(toml_config_str)

    config_figures: dict = config['BOARD']['figure']

    figures = []

    for config_figure in config_figures.values():
        if config_figure['type'] == 'rect':
            figure = Rectangle(config_figure['widht'], config_figure['height'],
                               config_figure['thickness'], config_figure['filled'],
                               config_figure['center']['x'], config_figure['center']['y'])
        figures.append(figure)

    for figure in figures:
        render(board, figure)

    print(board)
    board_bytes = board.__bytes__()
    print("Hex: " + ''.join(board_bytes.hex()))

    p = tinyproto.Hdlc()

    def on_send(a):
        print("Sent bytes: " + ','.join( [ "{:#x}".format(x) for x in a ] ) )

    p.on_send = on_send
    p.begin()

    p.put(bytearray(board_bytes))

    result = p.tx()

    print("Putting this to {}: ".format(args.device), ','.join(["{:#x}".format(x) for x in result]))

    print()

    try:
        ser = serial.Serial(args.device, baudrate=args.baud, bytesize=8, parity='N', stopbits=1, timeout=0.5)
        ser.write(board_bytes)
        time.sleep(0.5)
        ser.close()
    except Exception as e:
        raise e


if __name__ == '__main__':
    main()