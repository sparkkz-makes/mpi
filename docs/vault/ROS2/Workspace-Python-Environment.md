# Workspace Python Environment

> How Python dependencies are managed for the MentorPi ROS2 workspace.

## Overview

The robot runs ROS2 Jazzy on Ubuntu, which uses the system Python at `/usr/bin/python3`. To keep the workspace isolated and make it easy to install extra packages (loguru, numpy, opencv-python, etc.) without touching system packages, we use a workspace-local virtual environment created with `uv`.

## The Venv

Location: `/home/stu/dev/mpi/.venv`

Created with system-site-packages so ROS2 packages installed under `/opt/ros/jazzy/lib/python3.12/site-packages` remain importable:

```bash
cd /home/stu/dev/mpi
uv venv --system-site-packages .venv
```

## Installing Packages

Always install into the workspace venv, never the system Python:

```bash
source /home/stu/dev/mpi/.venv/bin/activate
uv pip install <package>
```

Or use the convenience script:

```bash
source /home/stu/dev/mpi/ros2_ws/activate.sh
uv pip install <package>
```

## Building the Workspace

Use the provided build script so colcon logs go to `ros2_ws/build_logs`:

```bash
cd /home/stu/dev/mpi/ros2_ws
./build.sh
```

With package selection:

```bash
./build.sh --packages-select mentorpi_driver
```

To build *and* activate the workspace in the current shell:

```bash
source build.sh
```

## Running Nodes

Source the workspace activation script before running anything:

```bash
source /home/stu/dev/mpi/ros2_ws/activate.sh
ros2 launch mentorpi_driver gamepad_teleop.launch.py
```

This activates the venv and sources the ROS2 install in one step.

## Why Not System Python?

- Avoids `sudo pip install` which can break Ubuntu/ROS2 system packages.
- Makes dependency versions reproducible (can commit `uv pip freeze` output later).
- Keeps ML/vision packages isolated from the base OS.

## Notes

- The venv uses the same Python interpreter as ROS2 (`/usr/bin/python3`), so binary ROS2 packages are compatible.
- `build.sh` patches the shebang of installed console scripts to use the venv Python. This is required for packages installed only in the venv (e.g. `loguru`) to be importable at runtime.
- If you ever delete `.venv`, recreate it with `uv venv --system-site-packages .venv` and reinstall packages.
