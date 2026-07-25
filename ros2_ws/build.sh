#!/usr/bin/env bash
# Build the MentorPi workspace using the workspace venv.
#
# Usage:
#   ./build.sh [extra colcon args]   # build only
#   source build.sh [extra args]     # build and activate workspace in current shell

set -e

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${WS_DIR}/../.venv"

if [ ! -f "${VENV_DIR}/bin/activate" ]; then
    echo "Workspace venv not found. Creating it now..." >&2
    uv venv --system-site-packages "${VENV_DIR}"
fi

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

cd "${WS_DIR}"

# Use build_logs for colcon build logs instead of the default log/ directory.
# Pass any extra arguments through to colcon (e.g. --packages-select foo).
colcon --log-base build_logs build --symlink-install "$@"

# Rewrite console-script shebangs so installed nodes run with the workspace
# venv Python. This is required for packages installed only in the venv
# (e.g. loguru) to be importable at runtime.
VENV_PYTHON="$(cd "${VENV_DIR}/bin" && pwd)/python3"
find "${WS_DIR}/install" -type f -executable | while read -r script; do
    if head -1 "${script}" | grep -q '^#!/usr/bin/python3'; then
        sed -i "1s|.*|#!${VENV_PYTHON}|" "${script}"
    fi
done

# If this script was sourced, activate the workspace in the current shell.
# If it was executed normally, just print a reminder.
if [ -n "${BASH_SOURCE[0]:-}" ] && [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    echo "Build complete. Run 'source activate.sh' to use the workspace."
else
    # shellcheck source=/dev/null
    source "${WS_DIR}/activate.sh"
fi
