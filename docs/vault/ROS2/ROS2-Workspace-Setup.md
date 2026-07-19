# ROS2 Workspace Setup

> Part of the [[ROS2-How-To]] series. See also: [[Project-Overview]], [[Building-and-Testing]]

## What is a ROS2 Workspace?

A **workspace** is a directory where you develop, build, and install ROS2 packages. The standard layout is:

```
ros2_ws/
├── build/        # Intermediate build artifacts (auto-generated)
├── install/      # Installed packages — you source this
├── build_logs/   # Build logs (redirected from log/)
├── runtime_logs/ # Runtime logs from our nodes
└── src/          # Your source code lives here
    └── my_package/
```

You write code in `src/`, build it with `colcon`, and the results land in `install/`. To use your packages, you **source** the install setup file, which adds your packages to ROS2's search paths.

## Creating a Workspace

```bash
mkdir -p ~/dev/mpi/ros2_ws/src
cd ~/dev/mpi/ros2_ws
```

That's it — an empty workspace. The magic happens when you add packages to `src/` and build.

## Sourcing ROS2

Before building or running anything, you need the base ROS2 environment loaded. The easiest way is to source the workspace activation script:

```bash
source ~/dev/mpi/ros2_ws/activate.sh
```

This activates the workspace venv, then sources `/opt/ros/jazzy/setup.bash`, then sources the workspace install. It sets environment variables like `ROS_DISTRO`, `AMENT_PREFIX_PATH`, and `COLCON_PREFIX_PATH` so that tools like `colcon`, `ros2`, and `rclpy` are findable.

> [!tip] Add this to your `~/.bashrc`
> ```bash
> echo 'source ~/dev/mpi/ros2_ws/activate.sh' >> ~/.bashrc
> ```
> This way every new terminal has the workspace ready. We also add colcon autocompletion:
> ```bash
> echo 'source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash' >> ~/.bashrc
> ```

## Building Packages

Use the workspace build script, which activates the venv, redirects colcon logs to `build_logs`, and patches console script shebangs:

```bash
cd ~/dev/mpi/ros2_ws
./build.sh
```

This builds **all** packages in `src/`. To build just one:

```bash
./build.sh --packages-select mentorpi_driver
```

To build and activate the workspace in the current shell:

```bash
source build.sh
```

### Common build flags

| Flag | Purpose |
|------|---------|
| `--packages-select <pkg>` | Build only the named package(s) |
| `--packages-up-to <pkg>` | Build the named package and its dependencies |
| `--symlink-install` | Symlink instead of copy — useful during development so edits take effect without rebuilding Python files |
| `--event-handlers console_direct+` | Print build output directly to console |

### What `build.sh` produces

After a successful build, you'll see:

- **`build/`** — intermediate files (compiled Python, C++ objects, etc.)
- **`install/`** — the "installed" version of your packages. This is what ROS2 actually uses.
- **`build_logs/`** — build logs. If a build fails, check `build_logs/latest_build/<package>/stderr.log`.

## Sourcing Your Workspace

After building, source the workspace activation script to make your packages available and activate the venv:

```bash
source ~/dev/mpi/ros2_ws/activate.sh
```

This **extends** the base ROS2 environment — it doesn't replace it. After sourcing, your packages appear in:

```bash
ros2 pkg list    # Should show your package
```

> [!important] Source order matters
> `activate.sh` handles this for you, but the underlying order is:
> ```bash
> source /home/stu/dev/mpi/.venv/bin/activate
> source /opt/ros/jazzy/setup.bash  # base ROS2
> source /home/stu/dev/mpi/ros2_ws/install/setup.bash
> ```
> If you source manually in the wrong order, your packages may not be found.

> [!tip] Add workspace sourcing to `.bashrc`
> ```bash
> echo 'source ~/dev/mpi/ros2_ws/activate.sh' >> ~/.bashrc
> ```
> Now every new terminal automatically has your workspace loaded. Just remember to re-source (or open a new terminal) after building.

## The Development Loop

The typical workflow is:

1. **Edit** code in `src/<package>/`
2. **Build** with `./build.sh --packages-select <package>`
3. **Source** the workspace (or open a new terminal if it's in `.bashrc`)
4. **Run** with `ros2 run <package> <node>`
5. **Repeat**

> [!note] Python packages and rebuilding
> For Python (ament_python) packages, you generally need to rebuild after changing `setup.py` (e.g., adding new entry points). Changes to existing `.py` files sometimes work without rebuilding if you use `--symlink-install`, but it's safest to rebuild after any change.

## Verifying Your Setup

```bash
# Check ROS2 is loaded
echo $ROS_DISTRO          # Should print: jazzy

# Check your workspace is sourced
ros2 pkg list | grep mentorpi_driver   # Should show your package

# Check colcon is available
colcon --version
```

## Troubleshooting

### "ros2: command not found"
You haven't sourced the base ROS2 setup. Run `source ~/dev/mpi/ros2_ws/activate.sh` (which sources `/opt/ros/jazzy/setup.bash` for you).

### "Package not found" after building
You haven't sourced your workspace. Run `source ~/dev/mpi/ros2_ws/activate.sh`.

### Stale paths from a deleted workspace
If you delete a workspace but its path is still in environment variables, you'll see warnings like:
```
WARNING: The path '/home/stu/dev/old_ws/install' in COLCON_PREFIX_PATH doesn't exist
```
Fix: update your `.bashrc` to source the new workspace, then open a fresh terminal.

## Next Steps

- [[ROS2-Python-Packages]] — how to structure a Python ROS2 package
- [[ROS2-Nodes-and-Topics]] — the core concepts you'll build on
- [[Building-and-Testing]] — building and testing the mentorpi_driver package
