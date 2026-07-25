# MentorPi — Agent Context

> Auto-loaded by VS Code Copilot when this repo is the workspace.
> Machine-specific notes (paths, installed packages, group memberships) live
> here so they survive across sessions, PCs, and workspace folders.

## Project overview

ROS2 driver package for the MentorPi robot (4-wheel Mecanum drive, RRC Lite
controller board with STM32F407VET6, UART serial interface).

- **Repo:** `git@github.com:sparkkz-makes/mpi.git`
- **ROS2 workspace:** `ros2_ws/` (single package: `mentorpi_driver`, `ament_python`)
- **Docs:** `docs/vault/` (Obsidian vault with slice-by-slice development notes)

## Environment (this machine)

- **Hardware:** Raspberry Pi 5
- **OS:** Ubuntu 26.04 LTS (codename `resolute`), aarch64
- **ROS2 distro:** Lyrical (`ros-lyrical-*` packages)
- **Python:** 3.14 (system) — ROS2 site-packages at `/opt/ros/lyrical/lib/python3.14/site-packages`
- **ROS2 install variant:** `ros-lyrical-ros-base` + `ros-dev-tools` (headless/server)
- **Extra ROS2 packages:** `ros-lyrical-joy`, `ros-lyrical-teleop-twist-joy`

> **Note:** This repo was originally developed on Jazzy/Ubuntu 24.04. It was
> migrated to Lyrical/Ubuntu 26.04 on 2026-07-25. See "Migration notes" below.

## Build & run

```bash
# Activate workspace (sources venv + ROS2 install in one step)
source ~/dev/mpi/ros2_ws/activate.sh

# Build (creates venv if missing, runs colcon, patches shebangs)
cd ~/dev/mpi/ros2_ws && ./build.sh

# Build single package
./build.sh --packages-select mentorpi_driver

# Launch gamepad teleop
ros2 launch mentorpi_driver gamepad_teleop.launch.py
```

### Python environment

- Venv at `~/dev/mpi/.venv` (created with `uv venv --system-site-packages`)
- `uv` installed at `~/.local/bin/uv` (added to `~/.bashrc` via `source $HOME/.local/bin/env`)
- Venv packages: `loguru` (pyserial available system-wide)
- `build.sh` patches installed console-script shebangs to use the venv Python
  so venv-only packages (loguru) are importable at runtime.

## System permissions (required for hardware access)

The `stu` user is a member of these groups (set up 2026-07-25):

- **`dialout`** — for `/dev/ttyACM0` (RRC Lite serial). Device is `root:dialout`, `crw-rw----`.
- **`input`** — for `/dev/input/event*` (gamepad via evdev). Devices are `root:input`, `crw-rw----`.

> Group changes require **log out / log back in** (or reboot) to take effect.

## Migration notes (Jazzy → Lyrical)

Two breaking changes were found and fixed:

### 1. `RcutilsLogger.warn()` removed in Lyrical

Jazzy's rclpy logger had both `.warn()` and `.warning()`. **Lyrical dropped
`.warn()`** — only `.warning()` remains (standard Python logging name).

Fixed in commit `0a14c56`:
- `logging_utils.py`: `NodeLogger.warn()` now calls `rclpy_logger.warning()`
  (kept `.warn()` on the wrapper for backwards compat with callers)
- `motor_driver.py`: 3x `self.log.warn()` → `self.log.warning()`
- `serial_driver.py`: `get_logger().warn()` → `get_logger().warning()`

### 2. `joy` package switched to evdev interface

In Lyrical, `joy` v3.3.0 switched from the legacy `/dev/input/js*` joystick
API (world-readable `crw-rw-r--`) to the **evdev** interface
(`/dev/input/event*`, owned `root:input` with `crw-rw----`).

- **Symptom:** joy_node runs silently, no "Opened joystick" log, `/joy` topic
  has 0 Hz, no error printed. Only visible via `strace`: `EACCES` on
  `/dev/input/event*`.
- **Fix:** `sudo usermod -aG input stu` (see "System permissions" above).

### Other migration findings

- Jazzy references in docs (markdown only) were updated to Lyrical (commit `d5ab984`).
- No hardcoded `/opt/ros/jazzy` paths in code.
- All other rclpy API usage is stable (get_logger, create_timer, destroy_node,
  rclpy.shutdown, ExternalShutdownException).
- Launch file + joy config use standard ROS2 patterns, no version-specific issues.
- Cosmetic build warning: `Unknown distribution option: 'tests_require'`
  (setuptools on Python 3.14 deprecated it) — harmless.

## Git

- **Identity** (local to this repo): `sparkkz-makes` / `stuart.parkinson.nz@gmail.com`
- **Migration branch:** `lyrical-upgrades` (commits `d5ab984`, `0a14c56`)
- **SSH key:** `~/.ssh/id_ed25519` (ed25519, added to GitHub as `stu@rpi5`)

## Package structure

```
ros2_ws/src/mentorpi_driver/
├── package.xml          # ament_python, deps: rclpy, std_msgs, geometry_msgs, sensor_msgs, joy, teleop_twist_joy
├── setup.py             # entry points: buzzer_node, serial_driver, motor_driver, joy_inspector
├── setup.cfg
├── resource/
├── config/
│   └── teleop_joy_params.yaml   # SHANWAN Android Gamepad mapping, Mecanum kinematics
├── launch/
│   └── gamepad_teleop.launch.py # joy_node + teleop_twist_joy + motor_driver
└── mentorpi_driver/
    ├── __init__.py
    ├── buzzer_node.py
    ├── serial_driver.py
    ├── motor_driver.py
    ├── joy_inspector.py
    ├── logging_utils.py   # NodeLogger wrapper (rclpy + loguru file logging)
    └── protocol.py        # RRCLiteProtocol (serial frame encoding)
```

## Debugging tips

- **Timeouts:** Use `timeout -s KILL <secs>` (SIGKILL can't be caught; plain
  `timeout` sends SIGTERM which ROS2 nodes sometimes ignore).
- **joy_node silent failure:** If `/joy` has 0 Hz and no "Opened joystick" log,
  check `input` group membership and `/dev/input/event*` permissions.
- **Serial port:** If motor_driver gets `Permission denied: '/dev/ttyACM0'`,
  check `dialout` group membership.
