"""Launch file for full teleop + camera + gimbal (Slice 6).

Brings up the complete stack:
  1. joy_node           — reads /dev/input/js0, publishes /joy
  2. teleop_manager     — /joy → /cmd_vel + /gimbal_vel + /gimbal_recenter
                          (A button toggles drive ↔ camera mode)
  3. serial_driver      — gateway: /motor_cmd + /gimbal_cmd → RRC Lite serial
  4. motor_driver       — /cmd_vel → /motor_cmd (Mecanum kinematics)
  5. gimbal_driver      — /gimbal_vel + /gimbal_recenter → /gimbal_cmd
                          (rate-control integrator for pan/tilt servos)
  6. v4l2_camera        — /dev/video0 → /image_raw
  7. web_video_server   — HTTP MJPG stream on :8080

View the camera in a browser (phone or PC on the same network):
    http://<robot-ip>:8080/stream?topic=/image_raw&type=mjpeg&width=640

Controls (SHANWAN Android Gamepad):
    Left stick   → forward/back + turn (both modes)
    Right stick  → strafe (DRIVE) OR pan/tilt (CAMERA)
    A (btn 0)    → toggle drive ↔ camera mode
    R1 (btn 7)   → turbo (2× speed)
    R3 (btn 14)  → recenter gimbal
    X (btn 3)    → emergency stop (latched, in motor_driver)

Usage:
    ros2 launch mentorpi_driver teleop_camera.launch.py
    ros2 launch mentorpi_driver teleop_camera.launch.py camera:=false
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('mentorpi_driver')

    teleop_config = os.path.join(pkg_share, 'config', 'teleop_manager_params.yaml')
    gimbal_config = os.path.join(pkg_share, 'config', 'gimbal_params.yaml')
    camera_config = os.path.join(pkg_share, 'config', 'camera_params.yaml')

    # ── Launch arguments ────────────────────────────────────────────
    camera_arg = DeclareLaunchArgument(
        'camera', default_value='true',
        description='Whether to launch the camera + web_video_server nodes.',
    )
    port_arg = DeclareLaunchArgument(
        'serial_port', default_value='/dev/ttyACM0',
        description='Serial port for the RRC Lite board.',
    )
    web_port_arg = DeclareLaunchArgument(
        'web_port', default_value='8080',
        description='HTTP port for web_video_server.',
    )

    camera_enabled = LaunchConfiguration('camera')

    return LaunchDescription([
        camera_arg,
        port_arg,
        web_port_arg,

        # 1. joy_node — reads the gamepad, publishes /joy at 50 Hz
        Node(
            package='joy',
            executable='joy_node',
            name='joy_node',
            parameters=[{
                'device_id': 0,
                'deadzone': 0.05,
                'autorepeat_rate': 50.0,
            }],
            output='screen',
        ),

        # 2. teleop_manager — /joy → /cmd_vel + /gimbal_vel + /gimbal_recenter
        Node(
            package='mentorpi_driver',
            executable='teleop_manager',
            name='teleop_manager',
            parameters=[teleop_config],
            output='screen',
        ),

        # 3. serial_driver — the gateway (owns /dev/ttyACM0)
        Node(
            package='mentorpi_driver',
            executable='serial_driver',
            name='serial_driver',
            parameters=[{
                'port': LaunchConfiguration('serial_port'),
                'baudrate': 1000000,
            }],
            output='screen',
        ),

        # 4. motor_driver — /cmd_vel → /motor_cmd
        Node(
            package='mentorpi_driver',
            executable='motor_driver',
            name='motor_driver',
            output='screen',
        ),

        # 5. gimbal_driver — /gimbal_vel + /gimbal_recenter → /gimbal_cmd
        Node(
            package='mentorpi_driver',
            executable='gimbal_driver',
            name='gimbal_driver',
            parameters=[gimbal_config],
            output='screen',
        ),

        # 6. v4l2_camera — /dev/video0 → /image_raw (only if camera:=true)
        Node(
            package='v4l2_camera',
            executable='v4l2_camera_node',
            name='v4l2_camera',
            parameters=[camera_config],
            condition=IfCondition(camera_enabled),
            output='screen',
        ),

        # 7. web_video_server — HTTP MJPG on :8080 (only if camera:=true)
        Node(
            package='web_video_server',
            executable='web_video_server',
            name='web_video_server',
            parameters=[{'port': LaunchConfiguration('web_port')}],
            condition=IfCondition(camera_enabled),
            output='screen',
        ),
    ])
