"""
Dual logging helper for MentorPi driver nodes.

Wraps the standard rclpy logger (so /rosout and ROS2 tooling still work) and
adds a developer-friendly file logger powered by loguru.

Features:
- Human-readable ISO-8601 timestamps in file logs.
- Per-run datestamped log files under ros2_ws/runtime_logs.
- Keeps the last 10 run log files by default.
- Optional log_level parameter that controls both rclpy and file verbosity.
- Convenience methods that mirror rclpy logger usage.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger as _file_logger
import rclpy
from rclpy.node import Node


# Default log retention for runtime logs
DEFAULT_RETENTION = 10


# Mapping from string level names to rclpy LoggingSeverity values.
# Imported lazily to avoid importing rclpy at module load time.
def _level_to_rclpy(level: str) -> int:
    from rclpy.logging import LoggingSeverity
    mapping = {
        'debug': LoggingSeverity.DEBUG,
        'info': LoggingSeverity.INFO,
        'warn': LoggingSeverity.WARN,
        'warning': LoggingSeverity.WARN,
        'error': LoggingSeverity.ERROR,
        'fatal': LoggingSeverity.FATAL,
    }
    return mapping.get(level.lower(), LoggingSeverity.INFO)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _remove_old_logs(log_dir: Path, retention: int) -> None:
    """Keep only the most recent `retention` log files in the directory."""
    files = sorted(
        (f for f in log_dir.iterdir() if f.is_file() and f.suffix == '.log'),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for old in files[retention:]:
        try:
            old.unlink()
        except OSError:
            pass


def setup_file_logging(
    node_name: str,
    log_dir: Optional[Path] = None,
    retention: int = DEFAULT_RETENTION,
) -> Path:
    """
    Configure loguru to write per-run logs to disk.

    Args:
        node_name: Name of the node (used in the filename).
        log_dir: Directory for log files. Defaults to ros2_ws/runtime_logs.
        retention: Number of run log files to keep.

    Returns:
        Path to the log file created for this run.
    """
    if log_dir is None:
        # Walk up from the package source to find the workspace root.
        candidate = Path(__file__).resolve().parents[3]
        log_dir = candidate / 'runtime_logs'

    _ensure_dir(log_dir)
    _remove_old_logs(log_dir, retention)

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_file = log_dir / f'{node_name}_{timestamp}.log'

    # Remove any previously added file sinks in this process (e.g. from tests).
    _file_logger.remove()

    _file_logger.add(
        str(log_file),
        level='DEBUG',
        format='{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}',
        rotation=None,
        retention=None,
        enqueue=True,
    )

    return log_file


class NodeLogger:
    """
    Convenience wrapper that forwards messages to both rclpy and loguru.

    Usage:
        self.log = NodeLogger(self)
        self.log.info('hello')
        self.log.debug('verbose thing')
    """

    def __init__(
        self,
        node: Node,
        level: str = 'info',
        log_dir: Optional[Path] = None,
        retention: int = DEFAULT_RETENTION,
    ):
        self.node = node
        self.rclpy_logger = node.get_logger()
        self.log_file = setup_file_logging(node.get_name(), log_dir, retention)

        self.set_level(level)

        self.info(f'File logging enabled: {self.log_file}')

    def set_level(self, level: str) -> None:
        """Set verbosity for both rclpy and file loggers."""
        self.rclpy_logger.set_level(_level_to_rclpy(level))
        # loguru sink is fixed at DEBUG; we filter by level in the wrapper.
        self._file_level = level.lower()

    def _should_log_to_file(self, level: str) -> bool:
        levels = ['debug', 'info', 'warn', 'warning', 'error', 'fatal']
        try:
            return levels.index(level.lower()) >= levels.index(self._file_level)
        except ValueError:
            return True

    def debug(self, msg: str) -> None:
        self.rclpy_logger.debug(msg)
        if self._should_log_to_file('debug'):
            _file_logger.debug(msg)

    def info(self, msg: str) -> None:
        self.rclpy_logger.info(msg)
        if self._should_log_to_file('info'):
            _file_logger.info(msg)

    def warn(self, msg: str) -> None:
        self.rclpy_logger.warning(msg)
        if self._should_log_to_file('warn'):
            _file_logger.warning(msg)

    def warning(self, msg: str) -> None:
        self.warn(msg)

    def error(self, msg: str) -> None:
        self.rclpy_logger.error(msg)
        if self._should_log_to_file('error'):
            _file_logger.error(msg)

    def fatal(self, msg: str) -> None:
        self.rclpy_logger.fatal(msg)
        if self._should_log_to_file('fatal'):
            _file_logger.critical(msg)


# ── Resilient spin helper ────────────────────────────────────────────
#
# rclpy 10.0.10 on Python 3.14 has an intermittent pybind11 bug in
# Subscription.handle.take_message(): it raises
#   RuntimeError: Unable to convert call argument '0' to Python object
# when converting certain message fields (notably the integer arrays in
# sensor_msgs/Joy.buttons) from the C++ ROS message to Python. The error
# is transient (most messages decode fine) but uncaught, so a single bad
# message kills the node and tears down the launch.
#
# `resilient_spin()` wraps rclpy.spin() and recovers from ONLY this
# specific error by logging it and continuing. Any other exception
# propagates and kills the node — earlier versions swallowed all
# exceptions, which could mask real bugs (e.g. a broken timer callback
# failing 10×/s forever, logged but never fixed).
#
# NOTE: If timers silently stop firing (no RuntimeError, but no timer
# callbacks execute), the likely cause is a BLOCKING I/O call in a
# callback starving the single-threaded executor — NOT an executor bug.
# Audit serial/bus reads and writes for missing timeouts.
#
# See: docs/vault/mpi/Slice-6/Teleop-Manager.md (rclpy crash workaround)


_PYBIND11_TAKE_MESSAGE_SIGNATURE = 'Unable to convert call argument'


def resilient_spin(node: Node) -> None:
    """
    Spin a node, recovering from the rclpy pybind11 take_message bug.

    Wraps rclpy.spin_once() in a loop. If a RuntimeError matching the
    known pybind11 conversion failure escapes from the executor's
    message-take path, it is logged and the loop continues rather than
    crashing the node. KeyboardInterrupt and ExternalShutdownException
    still propagate so normal shutdown works, and ALL other exceptions
    propagate too — unknown bugs should kill the node loudly, not be
    retried forever.

    Args:
        node: The rclpy Node to spin.
    """
    from rclpy.executors import ExternalShutdownException
    logger = node.get_logger()
    recover_count = 0

    while rclpy.ok():
        try:
            rclpy.spin_once(node, timeout_sec=0.1)
        except (KeyboardInterrupt, ExternalShutdownException):
            return
        except RuntimeError as e:
            if _PYBIND11_TAKE_MESSAGE_SIGNATURE not in str(e):
                # Unknown RuntimeError — not the pybind11 bug. Crash loudly.
                raise
            recover_count += 1
            logger.warn(
                f'Recovered from rclpy message-take RuntimeError '
                f'(#{recover_count}): {e}. Continuing.'
            )
