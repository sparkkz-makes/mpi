"""Launch file for USB camera streaming over HTTP (Slice 6).

Brings up:
  1. v4l2_camera  — captures /dev/video0, publishes /image_raw (+ compressed)
  2. web_video_server — serves /image_raw as MJPG over HTTP on :8080

View in a browser (phone or PC on the same network):
    http://<robot-ip>:8080/stream?topic=/image_raw&type=mjpeg&width=640

Usage:
    ros2 launch mentorpi_driver camera_stream.launch.py
    ros2 launch mentorpi_driver camera_stream.launch.py video_device:=/dev/video0
    ros2 launch mentorpi_driver camera_stream.launch.py image_width:=640 image_height:=480
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('mentorpi_driver'),
        'config',
        'camera_params.yaml',
    )

    # ── Launch arguments (override from CLI) ───────────────────────
    video_device_arg = DeclareLaunchArgument(
        'video_device',
        default_value='/dev/video0',
        description='V4L2 device path for the USB camera.',
    )
    image_width_arg = DeclareLaunchArgument(
        'image_width',
        default_value='640',
        description='Capture width in pixels.',
    )
    image_height_arg = DeclareLaunchArgument(
        'image_height',
        default_value='480',
        description='Capture height in pixels.',
    )
    port_arg = DeclareLaunchArgument(
        'port',
        default_value='8080',
        description='HTTP port for web_video_server.',
    )

    # ── 1. v4l2_camera — publishes /image_raw ─────────────────────
    #    The compressed_image_transport plugin (installed alongside)
    #    automatically also publishes /image_raw/compressed as JPEG,
    #    which web_video_server serves as MJPG to browsers.
    #    NOTE: the icspring USB camera only supports YUYV 4:2:2 at
    #    640x480 (no hardware MJPEG); see config/camera_params.yaml.
    v4l2_camera_node = Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name='v4l2_camera',
        parameters=[config, {
            'video_device': LaunchConfiguration('video_device'),
            'image_width': LaunchConfiguration('image_width'),
            'image_height': LaunchConfiguration('image_height'),
        }],
        output='screen',
    )

    # ── 2. web_video_server — HTTP MJPG stream ───────────────────
    #    Default port 8080. Streams any image topic on the network.
    #    Browse to http://<robot-ip>:8080/ for a topic list, or
    #    http://<robot-ip>:8080/stream?topic=/image_raw&type=mjpeg
    #    for the live feed.
    web_video_server_node = Node(
        package='web_video_server',
        executable='web_video_server',
        name='web_video_server',
        parameters=[{
            'port': LaunchConfiguration('port'),
        }],
        output='screen',
    )

    return LaunchDescription([
        video_device_arg,
        image_width_arg,
        image_height_arg,
        port_arg,
        v4l2_camera_node,
        web_video_server_node,
    ])
