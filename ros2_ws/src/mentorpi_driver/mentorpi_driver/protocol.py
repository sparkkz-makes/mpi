"""
RRC Lite Communication Protocol

Implements the serial communication protocol for the RRC Lite controller board
(STM32F407VET6). The board communicates over UART at 1 Mbps.

Frame format:
    [0xAA][0x55][Function Code][Data Length][Parameters...][Checksum]

The checksum is a CRC8 value computed over Function Code + Data Length + Parameters.
"""

import struct


# CRC8 lookup table (polynomial 0x07, used by the RRC Lite firmware)
CRC8_TABLE = [
    0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
    157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
    35, 125, 159, 193, 66, 28, 254, 160, 225, 191, 93, 3, 128, 222, 60, 98,
    190, 224, 2, 92, 223, 129, 99, 61, 124, 34, 192, 158, 29, 67, 161, 255,
    70, 24, 250, 164, 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7,
    219, 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196, 154,
    101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69, 198, 152, 122, 36,
    248, 166, 68, 26, 153, 199, 37, 123, 58, 100, 134, 216, 91, 5, 231, 185,
    140, 210, 48, 110, 237, 179, 81, 15, 78, 16, 242, 172, 47, 113, 147, 205,
    17, 79, 173, 243, 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80,
    175, 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82, 176, 238,
    50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76, 18, 145, 207, 45, 115,
    202, 148, 118, 40, 171, 245, 23, 73, 8, 86, 180, 234, 105, 55, 213, 139,
    87, 9, 235, 181, 54, 104, 138, 212, 149, 203, 41, 119, 244, 170, 72, 22,
    233, 183, 85, 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
    116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215, 137, 107, 53,
]


class RRCLiteProtocol:
    """Builds and parses serial frames for the RRC Lite controller board."""

    FRAME_HEADER = bytes([0xAA, 0x55])

    # Function codes (from the official protocol document)
    FUNC_SYS = 0
    FUNC_LED = 1
    FUNC_BUZZER = 2
    FUNC_MOTOR = 3
    FUNC_PWM_SERVO = 4
    FUNC_BUS_SERVO = 5
    FUNC_KEY = 6
    FUNC_IMU = 7
    FUNC_GAMEPAD = 8
    FUNC_SBUS = 9
    FUNC_OLED = 10
    FUNC_RGB = 11

    # Motor subcommands
    MOTOR_CMD_SINGLE = 0x00
    MOTOR_CMD_MULTIPLE = 0x01
    MOTOR_CMD_STOP_SINGLE = 0x02
    MOTOR_CMD_STOP_SEVERAL = 0x03

    # PWM servo subcommands
    PWM_SERVO_CMD_SEVERAL = 0x01
    PWM_SERVO_CMD_SINGLE = 0x03
    PWM_SERVO_CMD_READ_POS = 0x05
    PWM_SERVO_CMD_SET_DEV = 0x07
    PWM_SERVO_CMD_READ_DEV = 0x09

    @staticmethod
    def calc_crc8(data: bytes) -> int:
        """Compute CRC8 checksum using the RRC Lite lookup table."""
        check = 0
        for b in data:
            check = CRC8_TABLE[check ^ b]
        return check & 0xFF

    @classmethod
    def pack_frame(cls, function_code: int, parameters: bytes) -> bytes:
        """
        Build a complete serial frame.

        Args:
            function_code: One of the FUNC_* constants.
            parameters: Pre-packed parameter bytes (little-endian).

        Returns:
            Complete frame: [0xAA][0x55][Func][Len][Params][CRC8]
        """
        data_length = len(parameters)
        # CRC8 is computed over [Func][Len][Params]
        crc_data = bytes([function_code, data_length]) + parameters
        checksum = cls.calc_crc8(crc_data)

        frame = bytearray(cls.FRAME_HEADER)
        frame.append(function_code)
        frame.append(data_length)
        frame.extend(parameters)
        frame.append(checksum)

        return bytes(frame)

    # ── LED commands ──────────────────────────────────────────────

    @classmethod
    def cmd_led(cls, led_id: int, on_time_ms: int, off_time_ms: int,
                cycles: int) -> bytes:
        """
        Build an LED blink command.

        Args:
            led_id: LED ID (1-based).
            on_time_ms: Light-on duration in milliseconds.
            off_time_ms: Light-off duration in milliseconds.
            cycles: Number of blink cycles.

        Returns:
            Serial frame bytes.
        """
        params = struct.pack('<BHHH', led_id, on_time_ms, off_time_ms, cycles)
        return cls.pack_frame(cls.FUNC_LED, params)

    # ── Buzzer commands ────────────────────────────────────────────

    @classmethod
    def cmd_buzzer(cls, frequency_hz: int, on_time_ms: int,
                   off_time_ms: int, cycles: int) -> bytes:
        """
        Build a buzzer command.

        Args:
            frequency_hz: Sound frequency in Hz (e.g. 1400).
            on_time_ms: Beep duration in milliseconds.
            off_time_ms: Pause duration in milliseconds.
            cycles: Number of beep cycles.

        Returns:
            Serial frame bytes.
        """
        params = struct.pack('<HHHH', frequency_hz, on_time_ms,
                             off_time_ms, cycles)
        return cls.pack_frame(cls.FUNC_BUZZER, params)

    # ── Motor commands ─────────────────────────────────────────────

    @classmethod
    def cmd_motor_single(cls, motor_id: int, speed: float) -> bytes:
        """
        Build a single-motor speed command.

        Args:
            motor_id: Motor ID (1-4).
            speed: Target speed in r/s (positive or negative).

        Returns:
            Serial frame bytes.
        """
        params = struct.pack('<BBf', cls.MOTOR_CMD_SINGLE, motor_id, speed)
        return cls.pack_frame(cls.FUNC_MOTOR, params)

    @classmethod
    def cmd_motor_multiple(cls, motor_data: list) -> bytes:
        """
        Build a multi-motor speed command.

        Args:
            motor_data: List of (motor_id, speed) tuples.

        Returns:
            Serial frame bytes.
        """
        count = len(motor_data)
        params = bytearray([cls.MOTOR_CMD_MULTIPLE, count])
        for motor_id, speed in motor_data:
            params.append(motor_id)
            params.extend(struct.pack('<f', speed))
        return cls.pack_frame(cls.FUNC_MOTOR, bytes(params))

    @classmethod
    def cmd_motor_stop_single(cls, motor_id: int) -> bytes:
        """Build a stop-single-motor command."""
        params = struct.pack('<BB', cls.MOTOR_CMD_STOP_SINGLE, motor_id)
        return cls.pack_frame(cls.FUNC_MOTOR, params)

    @classmethod
    def cmd_motor_stop_several(cls, motor_mask: int) -> bytes:
        """
        Build a stop-multiple-motors command.

        Args:
            motor_mask: Bitmask of motors to stop (bit 0 = motor 1, etc.).
        """
        params = struct.pack('<BB', cls.MOTOR_CMD_STOP_SEVERAL, motor_mask)
        return cls.pack_frame(cls.FUNC_MOTOR, params)

    # ── PWM Servo commands ─────────────────────────────────────────

    @classmethod
    def cmd_pwm_servo_single(cls, servo_id: int, pulse_width: int,
                             motion_time_ms: int) -> bytes:
        """
        Build a single PWM servo command.

        Args:
            servo_id: Servo ID (1-4).
            pulse_width: Pulse width in microseconds (500-2500 = 0°-180°).
            motion_time_ms: Time to reach target position in milliseconds.
        """
        params = struct.pack('<BHB', cls.PWM_SERVO_CMD_SINGLE,
                             motion_time_ms, servo_id)
        params += struct.pack('<H', pulse_width)
        return cls.pack_frame(cls.FUNC_PWM_SERVO, params)

    @classmethod
    def cmd_pwm_servo_several(cls, servo_data: list,
                              motion_time_ms: int) -> bytes:
        """
        Build a multi PWM servo command.

        Args:
            servo_data: List of (servo_id, pulse_width) tuples.
            motion_time_ms: Time to reach target positions in milliseconds.
        """
        count = len(servo_data)
        # Frame layout (per RRC Lite protocol doc, Data Length = 3N+4):
        #   subcommand (0x01) | motion_time (uint16) | count (uint8)
        #   | [servo_id (uint8), pulse_width (uint16)] * count
        params = bytearray(struct.pack('<BHB',
                                        cls.PWM_SERVO_CMD_SEVERAL,
                                        motion_time_ms, count))
        for servo_id, pulse_width in servo_data:
            params.append(servo_id)
            params.extend(struct.pack('<H', pulse_width))
        return cls.pack_frame(cls.FUNC_PWM_SERVO, bytes(params))