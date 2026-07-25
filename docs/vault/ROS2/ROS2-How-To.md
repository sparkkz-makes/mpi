# ROS2 How-To Guides

> See also: [[Project-Overview]] for the MentorPi project documentation

A collection of beginner-friendly guides for working with ROS2 (specifically ROS2 Lyrical on Ubuntu). These are general-purpose references — not specific to the MentorPi project — but they use examples from the project where helpful.

## Guides

### Getting Started
- [[ROS2-Workspace-Setup]] — creating, building, and sourcing colcon workspaces
- [[ROS2-Python-Packages]] — package structure, `setup.py`, `package.xml`, entry points

### Core Concepts
- [[ROS2-Nodes-and-Topics]] — the node/topic communication model, publishers, subscribers, timers
- [[ROS2-Parameters]] — making nodes configurable via parameters

### Running Things
- [[ROS2-Running-Nodes]] — `ros2 run`, passing parameters, remapping topics, inspecting the graph

## Suggested Reading Order

If you're new to ROS2, read in this order:

1. [[ROS2-Workspace-Setup]] — understand the workspace concept
2. [[ROS2-Python-Packages]] — see how a package is structured
3. [[ROS2-Nodes-and-Topics]] — the core mental model
4. [[ROS2-Parameters]] — configurable nodes
5. [[ROS2-Running-Nodes]] — actually running things

Then follow along with the project:

1. [[Project-Overview]] — what we're building
2. [[Slice-1-Overview]] — the first slice
3. [[Building-and-Testing]] — build and verify
