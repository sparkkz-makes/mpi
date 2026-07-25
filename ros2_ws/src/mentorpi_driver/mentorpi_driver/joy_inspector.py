#!/usr/bin/env python3
"""Live gamepad inspector — prints /joy axes & buttons in a fixed screen position.

Usage:
    ros2 run mentorpi_driver joy_inspector
or:
    python3 joy_inspector.py

Move sticks / press buttons and watch the bars update in place.
"""
import sys
import os

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy


# ANSI escape codes
CLEAR = '\033[2J'
HOME = '\033[H'
CLEAR_LINE = '\033[K'

# Bar drawing
BAR_WIDTH = 40


def axis_bar(value: float) -> str:
    """Render an axis value (-1..1) as a centered bar."""
    v = max(-1.0, min(1.0, value))
    half = BAR_WIDTH // 2
    pos = int(round(v * half))  # negative = left, positive = right
    cells = [' '] * BAR_WIDTH
    cells[half] = '|'
    if pos >= 0:
        for i in range(half + 1, half + 1 + pos):
            if 0 <= i < BAR_WIDTH:
                cells[i] = '█'
    else:
        for i in range(half + pos, half):
            if 0 <= i < BAR_WIDTH:
                cells[i] = '█'
    return f'[{''.join(cells)}]'


class JoyInspector(Node):
    def __init__(self):
        super().__init__('joy_inspector')
        self.sub = self.create_subscription(Joy, '/joy', self.cb, 10)
        self.axes = []
        self.buttons = []
        self.first = True

    def cb(self, msg: Joy):
        self.axes = list(msg.axes)
        self.buttons = list(msg.buttons)
        self.render()

    def render(self):
        out = [HOME]  # cursor to top-left
        out.append(CLEAR_LINE + '╔══ SHANWAN Gamepad — live /joy ══╗')
        out.append(CLEAR_LINE + '')
        out.append(CLEAR_LINE + '  AXES')
        names = ['X  (L-Stick H)', 'Y  (L-Stick V)', 'Z  (L-Trig?)',
                 'Rz (R-Stick H)', 'Gas(R-Trig?)', 'Brake',
                 'Hat0X (D-Pad H)', 'Hat0Y (D-Pad V)']
        for i, v in enumerate(self.axes):
            name = names[i] if i < len(names) else f'Axis{i}'
            out.append(f'{CLEAR_LINE}  [{i}] {name:18s} {v:+.3f} {axis_bar(v)}')
        out.append(CLEAR_LINE + '')
        out.append(CLEAR_LINE + '  BUTTONS')
        btn_names = ['A', 'B', 'C', 'X', 'Y', 'Z', 'TL(L1)', 'TR(R1)',
                     'TL2(L2)', 'TR2(R2)', 'Select', 'Start', 'Mode',
                     'ThumbL', 'ThumbR']
        # show in rows of 5
        for row_start in range(0, len(self.buttons), 5):
            cells = []
            for i in range(row_start, min(row_start + 5, len(self.buttons))):
                name = btn_names[i] if i < len(btn_names) else f'B{i}'
                state = '■' if self.buttons[i] else '·'
                cells.append(f'[{i}]{name}:{state}')
            out.append(CLEAR_LINE + '  ' + '  '.join(cells))
        out.append(CLEAR_LINE + '')
        out.append(CLEAR_LINE + '  ■ = pressed   · = released   | = centre')
        out.append(CLEAR_LINE + '')
        sys.stdout.write('\n'.join(out))
        sys.stdout.flush()


def main():
    rclpy.init()
    node = JoyInspector()
    # clear screen once at start
    sys.stdout.write(CLEAR + HOME)
    sys.stdout.flush()
    try:
        from .logging_utils import resilient_spin
        resilient_spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # restore terminal
        sys.stdout.write('\033[?25h\n')
        sys.stdout.flush()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
