#!/usr/bin/env bash
# Source this file to activate the MentorPi workspace environment:
#   source activate.sh

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${WS_DIR}/../.venv"

if [ -f "${VENV_DIR}/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "${VENV_DIR}/bin/activate"
else
    echo "Workspace venv not found at ${VENV_DIR}" >&2
    echo "Run: uv venv --system-site-packages ${VENV_DIR}" >&2
    return 1 2>/dev/null || exit 1
fi

if [ -f "${WS_DIR}/install/setup.bash" ]; then
    # shellcheck source=/dev/null
    source "${WS_DIR}/install/setup.bash"
else
    echo "Workspace not built yet. Run: colcon build" >&2
fi

echo "MentorPi workspace activated."
echo "  Python: $(which python3)"
echo "  ROS distro: ${ROS_DISTRO:-unknown}"
echo "  Custom runtime logs: ${WS_DIR}/runtime_logs"
