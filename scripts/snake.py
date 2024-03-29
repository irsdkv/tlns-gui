# Source code based on https://github.com/RahulShagri/OG-Snake-Game

# MIT License
#
# Copyright (c) 2021 RahulShagri
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import dearpygui.dearpygui as dpg
import threading
import time
import random
import webbrowser
from theme_settings import *
import argparse

import tinyproto
from tlns.tlns import Board, PIXEL_MAX_BRIGHTNESS, PIXEL_HALF_BRIGHTNESS
import serial

dpg.setup_registries()  # Registries for mouse and keyboard press events

slither_data = []  # List of points and their respective direction. [[x_coordinate, y_coordinate], direction]
slither_change_data = []  # List of change of directions. [[x_coordinate, y_coordinate], direction]
snake_burrow = None  # the plot item of the main display of the game
snake = None  # the polyline item which acts as the snake
snake_moving_flag = 0  # flag to check if snake is moving or not
snake_length_flag = 1  # Flag to check if the snake should grow or not. 1=grow 0=fixed
fix_snake_length = None

pause = False

apple = None  # Apple item in DPG
apple_points = []   # Every unit coordinate of the apple rectangle. If the snake passes through any of these
# coordinate, then the apple changes location

snake_speed = None
snake_color = [0, 255, 0]
apple_color = [255, 0, 0]
burrow_color = [33, 33, 33]
burrow = None  # Burrow (background) item in DPG

score = None  # Score item in DPG
score_count = 0
highest_score = None  # Highest score item in DPG
highest_score_count = 0

BOARD_HEIGHT = 21
BOARD_WIDTH = 21
board = Board()
serial_iface = None
manual = False


def write_board_to_uart(board):
    global serial_iface
    p = tinyproto.Hdlc()
    p.begin()
    p.put(board.tobytes(mirror_y=True))
    print(str(board))
    result = p.tx()
    if serial_iface is not None:
        serial_iface.write(result)
    else:
        print("serial_iface is None. Skip sending.")


def initial_slither_points():
    # Function sets all the points required to draw the snake initially
    global slither_data, snake

    slither_data = []

    head_point = [int(BOARD_WIDTH/2), int(BOARD_HEIGHT/2)]
    tail_point = [int(BOARD_WIDTH/2), int(BOARD_HEIGHT/2)-4]
    snake_length = head_point[1] - tail_point[1]

    for point in range(snake_length):
        slither_data.append([[head_point[0], (head_point[1] - point)], 2])

    slither_data.append([tail_point, 2])


def restart_snake():
    global slither_data, slither_change_data, snake, snake_moving_flag, score, score_count, apple_points

    slither_data = []
    slither_change_data = []
    apple_points = []
    snake_moving_flag = 0
    score_count = 0
    dpg.set_value(item=score, value=score_count)

    initial_slither_points()
    place_apple()

    body_points = get_points_from_data(slither_data)
    body_points.pop(0)  # List of all points of the snake except the head
    board_local = Board()
    for body_point in body_points:
        board_local.set_quietly(body_point[0], body_point[1], PIXEL_HALF_BRIGHTNESS)
    for apple_point in apple_points:
        board_local.set_quietly(apple_point[0], apple_point[1], PIXEL_MAX_BRIGHTNESS)

    write_board_to_uart(board_local)

    dpg.configure_item(item=snake, points=get_points_from_data(slither_data), color=dpg.get_value(item=snake_color))


def move_snakeDispatcher():
    # Function creates a new thread that controls the continuous movement of the snake while the main code is listening
    # for any keyboard or mouse events to occur
    move_snake_thread = threading.Thread(name="move snake", target=move_snake, args=(), daemon=True)
    move_snake_thread.start()

def step():
    global slither_data, slither_change_data, snake, snake_moving_flag, apple_points, snake_speed, snake_color, \
        snake_length_flag, score, score_count, highest_score, highest_score_count, manual
    if pause:
        return 0
    snake_moving_flag = 1
    body_points = get_points_from_data(slither_data)
    body_points.pop(0)  # List of all points of the snake except the head

    board_local = Board()
    for body_point in body_points:
        board_local.set_quietly(body_point[0], body_point[1], PIXEL_HALF_BRIGHTNESS)
    for apple_point in apple_points:
        board_local.set_quietly(apple_point[0], apple_point[1], PIXEL_MAX_BRIGHTNESS)

    write_board_to_uart(board_local)

    if slither_data[0][0][1] == BOARD_WIDTH or slither_data[0][0][0] == BOARD_HEIGHT or \
            slither_data[0][0][1] == 0 or slither_data[0][0][0] == 0 or \
            slither_data[0][0] in body_points:  # Check if the snake touches the walls or itself

        for i in range(2):
            dpg.configure_item(item=snake, color=[255, 0, 0])
            time.sleep(0.15)
            dpg.configure_item(item=snake, color=dpg.get_value(item=snake_color))
            time.sleep(0.15)

        dpg.configure_item(item=snake, color=[255, 0, 0, 255])

        snake_moving_flag = 0
        return -1

    if slither_data[0][0] in apple_points:
        # If the head of the snake passes through any of the apple coordinates, then the apple changes location
        # and the snake's tail gets longer
        apple_points = []
        place_apple()

        score_count += 1
        dpg.set_value(item=score, value=score_count)

        if score_count > highest_score_count:
            highest_score_count = score_count
            dpg.set_value(item=score, value=score_count)
            dpg.set_value(item=highest_score, value=highest_score_count)

        if snake_length_flag == 1:  # Only if user wants to grow the snake
            add_length = 3  # Add additional 3 points to the tail
            tail_direction = slither_data[-1][1]  # Direction the tail is moving in
            tail_point = slither_data[-1][0][:]

            if tail_direction == 1:
                for n in range(add_length):
                    new_tail_point = [tail_point[0] + n + 1, tail_point[1]]
                    slither_data.append([new_tail_point, tail_direction])

            elif tail_direction == 2:
                for n in range(add_length):
                    new_tail_point = [tail_point[0], tail_point[1] - 1 - n]
                    slither_data.append([new_tail_point, tail_direction])

            elif tail_direction == 3:
                for n in range(add_length):
                    new_tail_point = [tail_point[0] - 1 - n, tail_point[1]]
                    slither_data.append([new_tail_point, tail_direction])

            else:
                for n in range(add_length):
                    new_tail_point = [tail_point[0], tail_point[1] + 1 + n]
                    slither_data.append([new_tail_point, tail_direction])

    else:
        for index in range(len(slither_data)):
            # This loop controls the continuous motion of the snake
            if slither_data[index][1] == 1:
                # Move West. Subtract X
                slither_data[index][0][0] -= 1

            elif slither_data[index][1] == 2:
                # Move North. Add Y
                slither_data[index][0][1] += 1

            elif slither_data[index][1] == 3:
                # Move East. Add X
                slither_data[index][0][0] += 1

            elif slither_data[index][1] == 4:
                # Move South. Subtract Y
                slither_data[index][0][1] -= 1

            if slither_data[index][0] in get_points_from_data(slither_change_data):
                # If the point of the snake is found in the list of direction of changes, then get the direction
                # of that point gets updated
                slither_data[index][1] = get_direction_from_data(slither_data[index][0], slither_change_data)

        for index in range(len(slither_change_data)):
            if not slither_change_data[index][0] in get_points_from_data(slither_data):
                slither_change_data.pop(index)
                break

    dpg.configure_item(item=snake, points=get_points_from_data(slither_data))

    time_pause = (-0.1*dpg.get_value(item=snake_speed)) + 1.1
    time.sleep(time_pause)  # Sets the speed of the snake depending on the value

    return 0

def move_snake():
    while not manual:
        if step() < 0:
            break

def get_points_from_data(data):
    # Functions takes entire data of slither and returns only the points
    slither_points = []
    for index in range(len(data)):
        slither_points.append(data[index][0])

    return slither_points


def get_direction_from_data(point, data):
    # Functions takes the entire data and extracts a particular direction for a given point
    for index in range(len(data)):
        if point == data[index][0]:
            return data[index][1]


def place_apple():
    global slither_data, apple

    pos_flag = 0

    while True:
        # Keeps looping until it finds a location (all points of the rectangle) that is not on the snake
        x_pos = random.randint(0, BOARD_WIDTH - 3)
        y_pos = random.randint(0, BOARD_HEIGHT - 3)

        for x in range(x_pos, x_pos+3):
            for y in range(y_pos, y_pos+3):
                if [x, y] in get_points_from_data(slither_data):
                    pos_flag = 1  # Signal that a point was found and continue finding a random point
                    break
            else:
                continue
            break

        if pos_flag == 1:
            # If a point is found inside the snake, then reset the pos_flag and continue iterating until
            # a new point outside the snake is found
            pos_flag = 0
            continue

        if pos_flag == 0:  # If pos_flag is not 1, continue placing the apple, otherwise reiterate
            dpg.configure_item(item=apple, pmin=[x_pos, y_pos], pmax=[x_pos+2, y_pos+2])
            for x in range(x_pos, x_pos + 3):
                for y in range(y_pos, y_pos + 3):
                    apple_points.append([x, y])
            return


def change_colors():
    global snake_color, apple_color, burrow_color, snake, apple, burrow

    dpg.configure_item(item=snake, color=dpg.get_value(item=snake_color))
    dpg.configure_item(item=apple, color=dpg.get_value(item=apple_color), fill=dpg.get_value(item=apple_color))
    dpg.configure_item(item=burrow, color=dpg.get_value(item=burrow_color), fill=dpg.get_value(item=burrow_color))


def check_snake_length():
    global snake_length_flag
    if dpg.get_value(item=fix_snake_length):
        snake_length_flag = 0

    else:
        snake_length_flag = 1


def reset_stats():
    global score, score_count, highest_score, highest_score_count

    score_count = 0
    highest_score_count = 0
    dpg.set_value(item=score, value=score_count)
    dpg.set_value(item=highest_score, value=highest_score_count)


def reset_settings():
    global snake, snake_color, apple, apple_color, burrow, burrow_color, snake_speed, fix_snake_length
    global snake_length_flag

    dpg.configure_item(item=snake, color=[0, 255, 0])
    dpg.configure_item(item=apple, color=[255, 0, 0], fill=[255, 0, 0])
    dpg.configure_item(item=burrow, color=[33, 33, 33], fill=[33, 33, 33])

    dpg.configure_item(item=snake_color, default_value=[0, 255, 0])
    dpg.configure_item(item=apple_color, default_value=[255, 0, 0])
    dpg.configure_item(item=burrow_color, default_value=[33, 33, 33])

    dpg.configure_item(item=snake_speed, default_value=5)
    dpg.set_value(item=fix_snake_length, value=False)
    snake_length_flag = 1


def open_help():
    webbrowser.open("https://github.com/RahulShagri/OG-Snake-Game")


def key_release_handler(sender, app_data):
    global snake_moving_flag, pause
    # Function listening to key release events. Arrow keys change snake direction and keeps a track of the point when
    # the key event occurs

    if app_data == 81:
        # TODO
        restart_snake()

    if not manual and app_data == 32:
        pause = False if pause else True

    if pause:
        return

    if snake_moving_flag == 0:  # If snake not moving then exit
        if app_data == 69:
            move_snakeDispatcher()
        if not manual:
            return

    global slither_data, slither_change_data
    head_point = slither_data[0][0][:]
    head_direction = slither_data[0][1]

    if head_direction == 1:
        # West
        head_point[0] -= 1

    if head_direction == 2:
        # North
        head_point[1] += 1

    if head_direction == 3:
        # East
        head_point[0] += 1

    if head_direction == 4:
        # South
        head_point[1] -= 1

    if app_data == 37 or app_data == 65:
        # West
        if head_direction != 3 and head_direction != 1:
            snake_direction = 1
            slither_change_data.append([head_point, snake_direction])

    if app_data == 38 or app_data == 87:
        # North
        if head_direction != 4 and head_direction != 2:
            snake_direction = 2
            slither_change_data.append([head_point, snake_direction])

    if app_data == 39 or app_data == 68:
        # East
        if head_direction != 1 and head_direction != 3:
            snake_direction = 3
            slither_change_data.append([head_point, snake_direction])

    if app_data == 40 or app_data == 83:
        # South
        if head_direction != 2 and head_direction != 4:
            snake_direction = 4
            slither_change_data.append([head_point, snake_direction])

    if manual and app_data == 32:
        step()


def main_window_setup():
    global snake, snake_burrow, apple, snake_speed, snake_color, apple_color, burrow_color, burrow
    global fix_snake_length, score, highest_score

    dpg.setup_viewport()
    dpg.set_viewport_title("Snake Game")
    dpg.configure_viewport(0, x_pos=0, y_pos=0, width=750, height=645)
    dpg.set_viewport_max_height(645)
    dpg.set_viewport_max_width(750)

    with dpg.window(pos=[0, 0], autosize=True, no_collapse=True, no_resize=True, no_close=True, no_move=True,
                    no_title_bar=True) as main_window:

        with dpg.child(height=90, autosize_x=True):
            score_text = dpg.add_text(default_value=" Score : ")
            dpg.add_same_line()
            score = dpg.add_text(default_value="0")
            dpg.set_item_font(item=score_text, font=score_font)
            dpg.set_item_font(item=score, font=score_font)

            highest_score_text = dpg.add_text(default_value=" Highest score : ")
            dpg.add_same_line()
            highest_score = dpg.add_text(default_value="0")
            dpg.set_item_font(item=highest_score_text, font=score_font)
            dpg.set_item_font(item=highest_score, font=score_font)

        with dpg.group(horizontal=True):
            with dpg.group():
                with dpg.plot(no_menus=False, no_title=True, no_box_select=True, no_mouse_pos=True, width=500,
                              height=500, equal_aspects=True) as snake_burrow:
                    default_x = dpg.add_plot_axis(axis=0, no_gridlines=True, no_tick_marks=True, no_tick_labels=True,
                                                  label="", lock_min=True)
                    dpg.set_axis_limits(axis=default_x, ymin=0, ymax=BOARD_WIDTH)
                    default_y = dpg.add_plot_axis(axis=1, no_gridlines=True, no_tick_marks=True, no_tick_labels=True,
                                                  label="", lock_min=True)
                    dpg.set_axis_limits(axis=default_y, ymin=0, ymax=BOARD_HEIGHT)

                    burrow = dpg.draw_rectangle(pmin=[0, 0], pmax=[BOARD_WIDTH, BOARD_HEIGHT], color=[33, 33, 33], fill=[33, 33, 33])
                    snake = dpg.draw_polyline(points=get_points_from_data(slither_data), thickness=1, color=[0, 255, 0])
                    apple = dpg.draw_rectangle(pmin=[0, 0], pmax=[2, 2], thickness=0, color=[255, 0, 0],
                                               fill=[255, 0, 0])

            with dpg.child(autosize_x=True, autosize_y=True):
                with dpg.group():
                    with dpg.child(height=340):
                        dpg.add_dummy(height=5)
                        settings_text = dpg.add_text(default_value=" Settings")
                        dpg.set_item_font(item=settings_text, font=bold_font)
                        dpg.add_dummy(height=5)
                        dpg.add_separator()
                        dpg.add_dummy(height=5)
                        snake_speed = dpg.add_drag_int(label="Snake speed", width=130, clamped=True, min_value=1,
                                                       max_value=10, default_value=5)
                        dpg.add_dummy(height=15)
                        snake_color = dpg.add_color_edit(label="Snake color", default_value=[0, 255, 0], no_alpha=True,
                                                         width=130, callback=change_colors)
                        dpg.add_dummy(height=5)
                        apple_color = dpg.add_color_edit(label="Apple color", default_value=[255, 0, 0], no_alpha=True,
                                                         width=130, callback=change_colors)
                        dpg.add_dummy(height=5)
                        burrow_color = dpg.add_color_edit(label="Burrow color", default_value=[33, 33, 33],
                                                          no_alpha=True, width=130, callback=change_colors)
                        dpg.add_dummy(height=15)
                        fix_snake_length = dpg.add_checkbox(label="Fix snake length", default_value=False,
                                                            callback=check_snake_length)
                        dpg.add_dummy(height=15)
                        dpg.add_button(label="Reset Settings", width=-1, height=30, callback=reset_settings)

                    dpg.add_separator()
                    dpg.add_dummy()
                    dpg.add_button(label="Start", callback=move_snakeDispatcher, width=-1, height=30)
                    dpg.add_button(label="Restart", callback=restart_snake, width=-1, height=30)
                    dpg.add_button(label="Reset Stats", width=-1, height=30, callback=reset_stats)
                    dpg.add_dummy()
                    dpg.add_separator()
                    dpg.add_dummy()
                    dpg.add_button(label="Help", width=-1, height=30, callback=open_help)

    dpg.add_key_release_handler(callback=key_release_handler)

    place_apple()

    dpg.set_primary_window(window=main_window, value=True)
    dpg.start_dearpygui()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@', description='')
    parser.add_argument('-d', '--device', help='Serial device path', dest='device', type=str, default='/dev/ttyUSB0')
    parser.add_argument('-m', '--manual', help='Stem on Space', dest='manual', type=bool, default=False)

    args = parser.parse_args()

    manual = args.manual

    if manual:
        snake_moving_flag = 1
        print("Manual mode ON")
    else:
        print("Manual mode OFF")

    try:
        serial_iface = serial.Serial(args.device, baudrate=115200, bytesize=8, parity='N', stopbits=1, timeout=None)
        print("Serial device opened!")
    except Exception as e:
        print("No Serial Device. Run without it.")
        print("e: " + str(e))

    initial_slither_points()
    main_window_setup()
