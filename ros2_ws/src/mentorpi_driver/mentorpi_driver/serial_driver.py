"""
Serial Driver Node for RRC Lite

This ROS2 node manages the serial connection to the RRC Lite controller board.
It provides the low-level send interface that other nodes use to communicate
with the hardware.

For Slice 1, it also subscribes to a 'test_led' topic (std_msgs/String) so you
can trigger an LED blink from the command line for proof-of-life testing.
"""

import serial
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .protocol import RRCLiteProtocol


class SerialDriverNode(Node):
    """ROS2 node that manages serial communication with the RRC Lite board."""

    def __init__(self):
        super().__init__('serial_driver')

        # Declare ROS2 parameters — these can be overridden from the CLI:
        #   ros2 run mentorpi_driver serial_driver --ros-args -p port:=/dev/ttyACM0
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 1000000)

        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value

        self.get_logger().info(f'Opening serial port {port} at {baudrate} baud...')

        try:
            self.serial_conn = serial.Serial(
                port,
                baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.02,  # 20ms read timeout for non-blocking reads
            )
            self.get_logger().info('Serial port opened successfully.')
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to open serial port: {e}')
            self.serial_conn = None

        # Slice 1 test: subscribe to 'test_led' to trigger an LED blink
        self.sub_test = self.create_subscription(
            String, 'test_led', self.test_led_callback, 10
        )

    def send_command(self, frame: bytes) -> None:
        """Send a raw frame to the RRC Lite board."""
        if not self.serial_conn:
            self.get_logger().warning('Serial connection not active. Cannot send.')
            return
        self.serial_conn.write(frame)

    def test_led_callback(self, msg: String) -> None:
        """
        Called when a message arrives on 'test_led'.
        Blinks LED 1 for 5 cycles (100ms on, 100ms off).
        """
        self.get_logger().info(f'Received test command: "{msg.data}". Blinking LED...')
        cmd = RRCLiteProtocol.cmd_led(1, 100, 100, 5)
        self.send_command(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = SerialDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()