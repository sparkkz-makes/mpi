# ROS2 Python Packages

> Part of the [[ROS2-How-To]] series. See also: [[ROS2-Workspace-Setup]], [[Building-and-Testing]]

## What Is a Package?

A **package** is the smallest unit of ROS2 code that can be built and installed. It contains nodes, libraries, config files, and metadata. In ROS2, Python packages use the **ament_python** build type.

## Package Structure

Our `mentorpi_driver` package is a typical Python ROS2 package:

```
mentorpi_driver/                    # Package root (lives in src/)
├── package.xml                     # Package metadata and dependencies
├── setup.cfg                       # Python packaging config
├── setup.py                        # Entry points and install rules
├── resource/
│   └── mentorpi_driver             # Marker file for ament indexing (empty)
└── mentorpi_driver/                 # The actual Python package
    ├── __init__.py                  # Makes it a Python package (empty)
    ├── protocol.py                 # RRC Lite protocol implementation
    ├── serial_driver.py            # Serial driver ROS2 node
    └── buzzer_node.py              # Buzzer proof-of-life node
```

### Why the double `mentorpi_driver/`?

This confuses everyone at first. There are **two** directories with the same name:

1. **Outer `mentorpi_driver/`** — the ROS2 package root. Contains `package.xml`, `setup.py`, etc.
2. **Inner `mentorpi_driver/`** — the Python package (where `__init__.py` lives). This is what you `import` in Python.

The outer directory is the "ROS2 package" and the inner is the "Python module". They can have different names, but it's conventional to keep them the same.

## `package.xml` — Package Metadata

This tells ROS2 what the package is and what it depends on:

```xml
<?xml version="1.0"?>
<package format="3">
  <name>mentorpi_driver</name>
  <version>0.1.0</version>
  <description>ROS2 driver package for the MentorPi RRC Lite controller board.</description>
  <maintainer email="stuart.parkinson.nz@gmail.com">stu</maintainer>
  <license>MIT</license>

  <!-- Build dependencies -->
  <buildtool_depend>ament_python</buildtool_depend>

  <!-- Runtime dependencies -->
  <depend>rclpy</depend>
  <depend>std_msgs</depend>
  <depend>geometry_msgs</depend>
  <depend>sensor_msgs</depend>

  <!-- Test dependencies -->
  <test_depend>ament_copyright</test_depend>
  <test_depend>ament_flake8</test_depend>
  <test_depend>ament_pep257</test_depend>
  <test_depend>python3-pytest</test_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

Key elements:
- **`<buildtool_depend>ament_python</buildtool_depend>`** — tells colcon to use the Python build system
- **`<depend>`** — declares a dependency. If you `import rclpy` in your code, you need `<depend>rclpy</depend>`
- **`<build_type>ament_python</build_type>`** — confirms this is a Python package
- **`<test_depend>`** — dependencies only needed for testing

> [!important] If you import it, declare it
> Every Python package you `import` in your code must be listed in `package.xml`. If you add `import numpy` and numpy isn't declared, the build may succeed but the node will fail at runtime on a clean system.

## `setup.py` — Entry Points and Install Rules

This is a standard Python `setup.py` with ROS2-specific additions:

```python
from setuptools import find_packages, setup

package_name = 'mentorpi_driver'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='stu',
    maintainer_email='stuart.parkinson.nz@gmail.com',
    description='ROS2 driver for MentorPi RRC Lite controller board',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'buzzer_node = mentorpi_driver.buzzer_node:main',
            'serial_driver = mentorpi_driver.serial_driver:main',
        ],
    },
)
```

### Entry Points — The Most Important Part

The `entry_points` section maps **command names** to **Python functions**:

```python
'buzzer_node = mentorpi_driver.buzzer_node:main',
#  ^command name    ^module path              ^function
```

This is what makes `ros2 run mentorpi_driver buzzer_node` work. When you run that command, ROS2:
1. Finds the `mentorpi_driver` package
2. Looks up the `buzzer_node` entry point
3. Calls `mentorpi_driver.buzzer_node.main()`

> [!tip] Adding a new node
> 1. Write the node file (e.g., `motor_driver.py`) with a `main()` function
> 2. Add an entry point in `setup.py`:
>    ```python
>    'motor_driver = mentorpi_driver.motor_driver:main',
>    ```
> 3. Add any new dependencies to `package.xml` and `setup.py` `install_requires`
> 4. Rebuild with `./build.sh`

### `data_files` — What Gets Installed Where

```python
data_files=[
    ('share/ament_index/resource_index/packages',
        ['resource/' + package_name]),     # Registers the package with ament
    ('share/' + package_name, ['package.xml']),  # Installs package.xml
],
```

- The `resource/mentorpi_driver` file (even though it's empty) registers the package so `ros2 pkg list` can find it
- `package.xml` must be installed so other packages can find this one's metadata

## `setup.cfg`

```ini
[develop]
script_dir=$base/lib/mentorpi_driver
[install]
install_scripts=$base/lib/mentorpi_driver
```

This tells setuptools where to install the executable scripts (the entry points). They end up in `install/mentorpi_driver/lib/mentorpi_driver/`.

## `resource/` Directory

Contains a single empty file named after the package (`resource/mentorpi_driver`). This is a marker file — its presence tells the ament build system "this package exists". Without it, `ros2 pkg list` won't show your package.

## Creating a New Package from Scratch

If you want to create a new package (not using our existing one):

```bash
cd ~/dev/mpi/ros2_ws/src
ros2 pkg create --build-type ament_python my_package \
    --dependencies rclpy std_msgs
```

This generates the boilerplate structure automatically. Then you add your nodes and entry points.

## Next Steps

- [[ROS2-Running-Nodes]] — how to run the nodes you've defined
- [[Building-and-Testing]] — building and testing our package
- [[Protocol-Implementation]] — walkthrough of `protocol.py`
