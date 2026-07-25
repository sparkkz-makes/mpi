# MentorPi Project Overview

> This is the main index for the MentorPi robotics project documentation. Start here.

## What Is This Project?

The **MentorPi** is an educational robotics platform built on a Raspberry Pi with a four-wheel Mecanum drive chassis. The goal is to build a complete ROS2 software control system from scratch, learning robotics, control theory, and AI integration along the way.

The robot is controlled by an **RRC Lite** board (STM32F407VET6 microcontroller) that handles low-level motor driving, encoder reading, and sensor interfacing. The Raspberry Pi runs ROS2 and communicates with the RRC Lite over a serial UART connection.

## Hardware

| Component | Details |
|-----------|---------|
| **Chassis** | MentorPi 4-wheel Mecanum drive |
| **Controller** | Raspberry Pi running Ubuntu 26.04 LTS + ROS2 Lyrical |
| **Driver Board** | RRC Lite (STM32F407VET6), UART serial interface |
| **Motors** | 4x high-speed DC motors with AB-phase quadrature encoders |
| **Power** | 7.4V 2200mAh 10C LiPo battery |
| **Camera** | USB camera (monocular or depth) |
| **LIDAR** | STL-19P TOF LIDAR (360°) |
| **IMU** | Integrated on RRC Lite board |
| **Servos** | 2x LFD-01 for 2DOF gimbal (pitch/yaw) |

## Communication Protocol

The RRC Lite communicates with the Pi over UART at **1,000,000 bps** (1 Mbps). Every message uses a frame format:

```
[0xAA][0x55][Function Code][Data Length][Parameters...][Checksum]
```

The checksum is a **CRC8** value (not a simple sum) computed over the function code, length, and parameters. See [[RRC-Lite-Protocol]] for full details.

## Development Slices

The project is broken into 6 incremental slices. Each slice builds on the previous one and has a clear verification step.

| Slice | Goal | Status | Docs |
|-------|------|--------|------|
| **1** | Base system & serial communication (buzzer proof-of-life) | ✅ Complete | [[Slice-1-Overview]] |
| **2** | PC teleoperation (keyboard → `/cmd_vel`) | ✅ Complete | [[Slice-2-Overview]] |
| **3** | Motor control with encoder feedback | ✅ Complete | [[Slice-3-Overview]] |
| **4** | Wireless game controller integration | ✅ Complete | [[Slice-4-Overview]] |
| **5** | Full Mecanum omnidirectional motion control | ✅ Complete | [[Slice-5-Overview]] |
| **6** | Vision & gimbal integration | Not started | — |

## Design Philosophy

- **Modular (driver-centric):** Each hardware function gets its own node. Nodes communicate via standard ROS2 topics.
- **Extensible:** Kinematics are decoupled from the driver. Higher-level motion primitives (arc paths, spirals) can be added later without touching the driver.
- **Standardized messaging:** Using `geometry_msgs/Twist`, `sensor_msgs/JointState`, etc. means hardware can be swapped without changing the control logic.

## Workspace

The ROS2 workspace lives at `~/dev/mpi/ros2_ws/`:

```
ros2_ws/
├── src/
│   └── mentorpi_driver/          # The main (and currently only) package
│       ├── package.xml
│       ├── setup.py
│       └── mentorpi_driver/
│           ├── protocol.py       # RRC Lite serial protocol
│           ├── serial_driver.py  # Serial driver node
│           └── buzzer_node.py    # Buzzer proof-of-life node
├── build/                        # Build artifacts (auto-generated)
├── install/                      # Installed packages (auto-generated)
└── log/                          # Build logs
```

## ROS2 How-To Guides

General ROS2 knowledge docs (not project-specific):

- [[ROS2-Workspace-Setup]] — creating, building, and sourcing workspaces
- [[ROS2-Nodes-and-Topics]] — the core communication model
- [[ROS2-Parameters]] — making nodes configurable
- [[ROS2-Python-Packages]] — package structure, `setup.py`, `package.xml`
- [[ROS2-Running-Nodes]] — running nodes from the command line

## Slice Documentation

Each slice has its own folder with detailed walkthroughs:

- **[[Slice-1-Overview]]** — Base System & Serial Communication
  - [[Serial-Communication]] — pyserial and the RRC Lite connection
  - [[RRC-Lite-Protocol]] — frame format and CRC8 checksum
  - [[Protocol-Implementation]] — `protocol.py` code walkthrough
  - [[Buzzer-Node-Walkthrough]] — `buzzer_node.py` code walkthrough
  - [[Serial-Driver-Node-Walkthrough]] — `serial_driver.py` code walkthrough
  - [[Building-and-Testing]] — building and verifying the buzzer
