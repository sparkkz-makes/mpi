"""
Buzzer Node — Slice 1 Proof-of-Life

This ROS2 node sends a buzzer command to the RRC Lite board every 5 seconds.
It's the simplest possible test that the entire serial communication chain works:

    ROS2 node → protocol.py (CRC8 frame) → pyserial → RRC Lite → buzzer

Usage:
    ros2 run mentorpi_driver buzzer_node

Note: For Slice 1 testing, this node opens its own serial connection directly.
In later slices, nodes will communicate via ROS2 topics instead.
"""

import serial
import rclpy
from rclpy.node import Node

from .protocol import RRCLiteProtocol


class BuzzerNode(Node):
    """Beeps the buzzer every 5 seconds as a proof-of-life test."""

    def __init__(self):
        super().__init__('buzzer_node')

        # Declare parameters (same defaults as serial_driver)
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 1000000)

        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value

        self.get_logger().info(f'BuzzerNode starting. Port={port}, Baud={baudrate}')

        try:
            self.serial_conn = serial.Serial(
                port,
                baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.02,
            )
            self.get_logger().info('Serial port opened. Buzzer will beep every 5 seconds.')
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to open serial port: {e}')
            self.serial_conn = None
            return

        # Timer fires every 5 seconds
        self.counter = 0
        self.timer = self.create_timer(5.0, self.timer_callback)

    def timer_callback(self):
        """Send a buzzer command: 1400Hz, 100ms on, 100ms off, 2 cycles."""
        self.get_logger().info(f'Buzzer beep #{self.counter}')
        cmd = RRCLiteProtocol.cmd_buzzer(
            frequency_hz=1400,
            on_time_ms=100,
            off_time_ms=100,
            cycles=2,
        )
        self.serial_conn.write(cmd)
        self.counter += 1


def main(args=None):
    rclpy.init(args=args)
    node = BuzzerNode()
    try:
        from .logging_utils import resilient_spin
        resilient_spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Send a stop buzzer command (0 Hz, 0 cycles) to silence the buzzer
        if node.serial_conn:
            stop_cmd = RRCLiteProtocol.cmd_buzzer(0, 0, 0, 0)
            node.serial_conn.write(stop_cmd)
            node.get_logger().info('Sent buzzer stop command.')
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()