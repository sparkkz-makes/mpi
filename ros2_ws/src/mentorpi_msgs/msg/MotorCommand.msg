# Per-wheel encoder-motor speed command for the RRC Lite board.
# Published by chassis_driver, consumed by serial_driver.
#
# motor_ids[i] is the RRC motor ID (0-3 on this firmware),
# speeds_rps[i] is the target speed in revolutions/second
# (sign = direction). Arrays must be the same length.
uint8[] motor_ids
float32[] speeds_rps
