"""Launch file for gamepad teleop: joy_node + teleop_twist_joy + chassis_driver.

NOTE: this legacy launch uses teleop_twist_joy (no mode toggle, no
gimbal, no e-stop button handling). Prefer teleop_camera.launch.py for
the full stack; this one is kept for minimal drive-only testing.

Usage:
    ros2 launch mentorpi_driver gamepad_teleop.launch.py
"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import os


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('mentorpi_driver'),
        'config',
        'teleop_joy_params.yaml',
    )

    return LaunchDescription([
        # 1. joy_node — reads /dev/input/js0, publishes /joy
        #    autorepeat_rate=50.0 keeps /joy (and therefore /cmd_vel) flowing
        #    at 50 Hz even when the stick is held still.
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

        # 2. teleop_twist_joy — converts /joy → /cmd_vel
        Node(
            package='teleop_twist_joy',
            executable='teleop_node',
            name='teleop_twist_joy_node',
            parameters=[config],
            remappings=[('cmd_vel', 'cmd_vel')],
            output='screen',
        ),

        # 3. chassis_driver — converts /cmd_vel → /motor_cmd (and holds
        #    the gimbal at center via /gimbal_cmd)
        Node(
            package='mentorpi_driver',
            executable='chassis_driver',
            name='chassis_driver',
            output='screen',
        ),
    ])
