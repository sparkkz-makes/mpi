# Slice 6 — Camera Streaming over HTTP

## Status
**Camera streaming: WORKING (2026-07-25).** Gimbal control: not yet started.

## Objective
Stream the USB camera feed to a web browser (phone or PC) over HTTP, as the
first half of Slice 6 (Vision & Gimbal Integration).

## Hardware
- **Camera:** "icspring camera" USB webcam (`usb-xhci-hcd.1-1`)
- **Device:** `/dev/video0` (also exposes `/dev/video1` and `/dev/media3`)
- **Driver:** `uvcvideo` (kernel)
- **Supported format:** YUYV 4:2:2 **only** — no hardware MJPEG
- **Supported size:** 640x480 (discrete; the only size)
- **Supported framerates:** 5, 10, 15, 20, 25, 30 fps

Probed with:
```bash
sudo v4l2-ctl --device=/dev/video0 --list-formats-ext
```

## Software Stack
| Component | Package | Role |
|-----------|---------|------|
| Camera driver | `ros-lyrical-v4l2-camera` (v0.8.0) | Captures `/dev/video0`, publishes `/image_raw` |
| Image transport | `ros-lyrical-image-transport` + `ros-lyrical-compressed-image-transport` | Auto-publishes `/image_raw/compressed` (JPEG) |
| HTTP server | `ros-lyrical-web-video-server` (v3.1.1) | Serves `/image_raw` as MJPG over HTTP on :8080 |

Install command:
```bash
sudo apt install -y v4l-utils \
  ros-lyrical-v4l2-camera \
  ros-lyrical-web-video-server \
  ros-lyrical-compressed-image-transport \
  ros-lyrical-image-transport
```

## Permissions (important)
The `stu` user was **not** in the `video` group, so `v4l2_camera` failed with
`Permission denied (13)` opening `/dev/video0`. Fixed with:
```bash
sudo usermod -aG video stu
```
This requires a **new login session** to take effect. As a workaround in an
existing shell, run the launch via `sg`:
```bash
sg video -c "source /home/stu/dev/mpi/ros2_ws/activate.sh && \
  ros2 launch mentorpi_driver camera_stream.launch.py"
```

## Files Added
- `ros2_ws/src/mentorpi_driver/launch/camera_stream.launch.py` — launches
  `v4l2_camera` + `web_video_server`. CLI args: `video_device`,
  `image_width`, `image_height`, `port`.
- `ros2_ws/src/mentorpi_driver/config/camera_params.yaml` — v4l2_camera
  params (640x480 YUYV @ 30fps, `frame_id: camera_link`).
- `setup.py` — registered the new launch + config in `data_files`.
- `package.xml` — added `v4l2_camera`, `web_video_server`,
  `image_transport`, `compressed_image_transport` as exec deps.

## Running
```bash
source /home/stu/dev/mpi/ros2_ws/activate.sh
ros2 launch mentorpi_driver camera_stream.launch.py
```
(Use `sg video -c "..."` if not in a fresh login session after adding the
group.)

## Viewing the Stream
On any device on the same network, open a browser to:
```
http://192.168.1.26:8080/stream?topic=/image_raw&type=mjpeg&width=640
```
- Root URL `http://192.168.1.26:8080/` lists all available image topics.
- `type=mjpeg` is the most browser-friendly format.
- Other supported types: `h264`, `png`, `vp8`, `vp9`, `ros_compressed`.

## Verified Performance (2026-07-25)
- `/image_raw` publish rate: **~22-23 fps** (target 30; the YUYV→rgb8
  software conversion costs some throughput).
- HTTP stream: returns `HTTP 200`, ~14 MB of MJPEG data in 5 s (multiple
  frames). Confirmed via `curl`.
- `web_video_server` logs `Handling Request` + `Streaming topic /image_raw`
  on each browser connection.

## Known Warnings (non-fatal)
1. `Image encoding not the same as requested output, performing possibly
   slow conversion: yuv422_yuy2 => rgb8` — v4l2_camera converts YUYV to
   rgb8 in software. Could be optimized by setting `output_encoding` to
   `yuv422_yuy2` in the config, but `web_video_server` expects rgb8/bgr8
   for MJPEG encoding, so the conversion is necessary.
2. `Camera calibration file ... not found` — no camera intrinsics
   calibration. v4l2_camera publishes a default (identity) CameraInfo.
   Fine for streaming; needed for CV/AI later.
3. `Failed getting value for control 10092545: Permission denied` — a
   UVC control the camera exposes but won't let userspace read. Harmless.

## Topics Published
- `/image_raw` (`sensor_msgs/Image`, rgb8, 640x480)
- `/image_raw/compressed` (`sensor_msgs/CompressedImage`, JPEG)
- `/camera_info` (`sensor_msgs/CameraInfo`, default/uncalibrated)

## Next Steps (Slice 6 part 2 — Gimbal)
- Add `gimbal_driver` node: right-stick rate-control integrator for
  pan/tilt servos via `RRCLiteProtocol.cmd_pwm_servo_single`.
- A-button mode toggle (drive ↔ camera), published on a latched
  `/teleop_mode` topic so `motor_driver` can suppress `/cmd_vel` in
  camera mode.
- Discover servo IDs and pulse ranges (physical test, like Slice 3 motors).
- See the design discussion in this slice's session notes.
