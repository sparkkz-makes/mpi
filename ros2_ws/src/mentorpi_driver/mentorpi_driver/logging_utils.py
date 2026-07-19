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
        self.rclpy_logger.warn(msg)
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
