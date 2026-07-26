# One raw telemetry frame received from the RRC Lite board.
# Published by serial_driver for every well-formed board-to-host frame
# (button events, IMU uploads, servo position responses, etc).
#
# This is the generic/raw channel for a future telemetry UI: function
# codes match docs/rrc-lite-protocol.md (FUNC_KEY=6, FUNC_IMU=7, ...).
# params is the raw parameter payload (already CRC-verified).
# Decoded convenience topics (e.g. /rrc_imu) are also published by
# serial_driver for known frame types.
std_msgs/Header header
uint8 function_code
uint8[] params
