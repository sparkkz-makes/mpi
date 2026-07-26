# PWM servo pulse-width command for the RRC Lite board (gimbal).
# Published by chassis_driver, consumed by serial_driver.
#
# servo_ids[i] is the RRC PWM servo ID (1-4),
# pulses_us[i] is the target pulse width in microseconds
# (500-2500 = 0-180 deg, 1500 = center). Arrays must be same length.
# motion_time_ms applies to all servos in this message: the time the
# servo should take to reach the target (0 = as fast as possible).
uint8[] servo_ids
uint16[] pulses_us
uint16 motion_time_ms
