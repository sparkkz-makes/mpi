## Page 1

1
RRCLite Communication Protocol with
the Host Computer Analysis
1. Description
This chapter mainly analyzes the communication protocol between the
RRCLitedevelopmentboardandthehostcomputer(ROSpackage),layingthe
foundationforsubsequentlearningaboutthehostcomputer.
2. Communication Protocol
Commoninstructionexamplescanbefoundin:CommonCommunication
InstructionExamples
Instructionsarewritteninhexadecimal.Ifyouarenotfamiliarwiththe
calculationmethod,youcanreferto:Usingacalculatortoolforhexadecimal
conversion.Forconvertingnegativenumbersandfloating-pointnumbersto
hexadecimal,pleasesearchforonlinetutorials.
Instruction format:

| Field | Size | Meaning |
| --- | --- | --- |
| Frame Header | 2 bytes | Continuous reception of 0xAA, 0x55 indicates the arrival of a data packet |
| Function Code | 1 byte | Used to indicate the purpose of an information frame |
| Data Length | 1 byte | Number of parameters |
| Parameters | Variable | Additional control information other than function instructions |
| Checksum | 1 byte | Verifies correctness using a CRC checksum of Function, Length, and Data values (lower 8 bits) |


## Page 2

2
2.1 User-Initiated Data Transmission to the Control Board
Section
ThedevelopmentboardalreadyhasadedicatedUARTtoUSBcircuit,so
communicationonlyrequiresconnectingtheUART1porttothehostcomputer
usingadatacable.
1. LED control: Instruction name PACKET_FUNC_LED, value 1

| Field | Value / format | Description |
| --- | --- | --- |
| Frame Header | 0xAA 0x55 | Start of frame |
| Function Code | PACKET_FUNC_LED | LED control instruction |
| Data Length | 7 | Number of bytes in the parameter block |
| Parameter 1 | uint8_t led_id | LED ID |
| Parameter 2 | uint16_t light-on duration (ms) | On time |
| Parameter 3 | uint16_t light-off duration (ms) | Off time |
| Parameter 4 | uint16_t number of cycles | Repeat count |
| Checksum | CRC | Frame integrity check |

Example:
1. Control the LED to blink 5 times, with each cycle having the light on for 100 ms and off for 100 ms:

| Field | Value |
| --- | --- |
| Frame Header | 0xAA 0x55 |
| Function Code | PACKET_FUNC_LED |
| Data Length | 7 |
| Parameter 1 | 0x01 (1) |
| Parameter 2 | 0x64 0x00 (100) |
| Parameter 3 | 0x64 0x00 (100) |
| Parameter 4 | 0x05 0x00 (5) |
| Checksum | CRC |

Note:Thisislittle-endianmode.Forexample,theuint32_tvalue5(decimal)is

## Page 3

3
writtenas0x000x05.Inlittle-endianmode,theleastsignificantbytecomes
first,sowhensendingdata,itshouldbewrittenas0x050x00.
2 Control the LED to blink 10 times, with each cycle having the light on
for 500ms and off for 300ms
Frame
Header
Function Code
Data
Length
Parameter Checksum
0xAA 0x55 PACKET_FUNC_LED 7
Parameter1：0x01（1）
Parameter 2：0xF4 0x01
（500）
Parameter 3：0x2C 0x01
（300）
Parameter 4：0x0A0x00
（10）
CRC
2. Buzzer control: Instruction name PACKET_FUNC_BUZZER, value 2

| Field | Value / format | Description |
| --- | --- | --- |
| Frame Header | 0xAA 0x55 | Start of frame |
| Function Code | PACKET_FUNC_BUZZER | Buzzer control instruction |
| Data Length | 8 | Number of bytes in the parameter block |
| Parameter 1 | uint16_t frequency (Hz) | Sound frequency |
| Parameter 2 | uint16_t beeping duration (ms) | Beep duration |
| Parameter 3 | uint16_t no-beeping duration (ms) | Pause duration |
| Parameter 4 | uint16_t number of cycles | Repeat count |
| Checksum | CRC | Frame integrity check |

Example:
1. Control the buzzer to sound 5 times, with a frequency of 1400 Hz, each lasting 100 ms followed by a 100 ms pause.

| Field | Value |
| --- | --- |
| Frame Header | 0xAA 0x55 |
| Function Code | PACKET_FUNC_BUZZER |
| Data Length | 8 |
| Parameter 1 | 0x78 0x05 (1400) |
| Parameter 2 | 0x64 0x00 (100) |
| Parameter 3 | 0x64 0x00 (100) |
| Parameter 4 | 0x05 0x00 (5) |
| Checksum | CRC |

## Page 4

4
Header Length
0xAA 0x55 PACKET_FUNC_BUZZER 8
Parameter 1 ： 0x78
0x05（1400）
Parameter 2 ： 0x64
0x00（100）
Parameter 3 ： 0x64
0x00（100）
Parameter 4 ： 0x05
0x00（5）
CRC
②Controlthebuzzertosound10times,withafrequencyof1000Hz,each
lastingfor500msfollowedbya300mspause.
Frame
Header
Function Code
Data
Length
Parameter Checksum
0xAA 0x55 PACKET_FUNC_BUZZER 8
Parameter 1 ： 0xE8
0x03（1000）
Parameter 2 ： 0xF4
0x01（500）
Parameter 3 ： 0x2C
0x01（300）
Parameter 4 ： 0x0A
0x00（10）
CRC
3. Encoder motor control: Instruction name PACKET_FUNC_MOTOR,
value 3

| Subcommand | Meaning |
| --- | --- |
| 0x00 | Control a single motor |
| 0x01 | Control multiple motors |
| 0x02 | Stop a single motor |
| 0x03 | Stop several motors |

| Field | Format | Description |
| --- | --- | --- |
| Frame Header | 0xAA 0x55 | Start of frame |
| Function Code | PACKET_FUNC_MOTOR | Motor control instruction |
| Data Length | 6 / 5N+2 / 2 | Depends on the command type |
| Parameter 1 | uint8_t subcommand | Selects single, multi, stop, or stop-all behavior |
| Parameter 2+ | Variable | Motor ID(s) and speed/value data |
| Checksum | CRC | Frame integrity check |

(1) Control Single Motor
Frame
Header
Function Code
Data
Length
Parameter Checksum

## Page 5

5
0xAA
0x55
PACKET_FUNC_MOTOR 6
Parameter 1：（uint8_t）0x00
（subcommand）
Parameter2：（uint8_t）motor_id
Parameter 3 ： （float ）speed
value（positiveandnegative）
CRC
(Note:floattypeis4bytes)
Example:Controlmotor1torotateat-1r/sspeed:
Frame
Header
Function Code
Data
Length
Parameter Checksum
0xAA 0x55 PACKET_FUNC_MOTOR 6
Parameter1：0x00
Parameter2：0x01
Parameter 3 ： 0x00
0x000x80 0xBF（-1）
CRC
(2) Control Multiple Motors
Frame
Header
Function Code
Data
Length
Parameter Checksum
0xAA
0x55
PACKET_FUNC_MOTOR 5N+2
Parameter1：（uint8_t）0x01
（subcommand）
Parameter2：（uint8_t）motor
quantity
Parameter 3 ： （ uint8_t ）
motor_id_1
Parameter4：（float）speed_1
······
Parameter 2N+1：（uint8_t）
motor_id_N
Parameter2N+2：（float）speed
_N
CRC

## Page 6

6
（ Format reference
parameters3,4）
(Note:floattypeis4bytes)
Example:
Controlmotor1andmotor2torotateatspeedsof-1r/sand2r/srespectively:
Frame
Header
Function Code
Data
Length
Parameter Checksum
0xAA 0x55 PACKET_FUNC_MOTOR 12
Parameter 1 ： 0x01
（subcommand）
Parameter2：0x02
Parameter3：0x01
Parameter 4 ： 0x00
0x000x80 0xBF（-1）
Parameter5：0x02
Parameter 6 ： 0x00
0x000x00 0x40（+2）
CRC
（3）Control Single Motor to Stop
Frame
Header
Function Code
Data
Length
Parameter Checksum
0xAA
0x55
PACKET_FUNC_MOTOR 2
Parameter1：（uint8_t）0x02
（subcommand）
Parameter 2 ： （ uint8_t ）
motor_id
CRC
Example:
Controlmotor1tostop:
Frame
Header
FunctionCode
Data
Length
Parameter Checksum
0xAA PACKET_FUNC_MOTOR 2 Parameter 1 ： 0x02 CRC

## Page 7

7
0x55 （subcommand）
Parameter2：0x01
（4）Controlseveralmotorstostop:
Frame
Header
Function Code
Data
Length
Parameter Checksum
0xAA
0x55
PACKET_FUNC_MOTOR 2
Parameter 1 ：(uint8_t) 0x03
（subcommand）
Parameter 2：(uint8_t) motor
mask
CRC
Example:
Controlmotor1andmotor3tostop:
Frame
Header
Function Code
Data
Lengt
h
Parameter
Chec
ksum
0xAA 0x55 PACKET_FUNC_MOTOR 2
Parameter1：0x03 (mode)
Parameter 2 ： 0x05 (Binary
00000101)
CRC
4. PWM servo control: instruction name PACKET_FUNC_PWM_SERVO,
value 4

| Subcommand | Meaning |
| --- | --- |
| 0x01 | Control several PWM servos |
| 0x03 | Control a single PWM servo |
| 0x05 | Read PWM servo position |
| 0x07 | Set PWM servo deviation |
| 0x09 | Read PWM servo deviation |

| Field | Format | Description |
| --- | --- | --- |
| Frame Header | 0xAA 0x55 | Start of frame |
| Function Code | PACKET_FUNC_PWM_SERVO | PWM servo instruction |
| Data Length | 3N+4 / 6 / 2 / 3 | Depends on the command type |
| Parameter 1 | uint8_t subcommand | Selects the operation to perform |
| Parameter 2+ | Variable | Motion time, servo IDs, pulse widths, or deviation |
| Checksum | CRC | Frame integrity check |

（1）Control several PWM servos
Frame
Header
FunctionCode
Data
Length
Parameter Checksum
0xAA
0x55
PACKET_FUNC_PWM_SERVO 3N+4
Parameter 1 ： (uint8_t) 0x01
(subcommand)
Parameter 2：(uint16_t) motion
time(ms)
Parameter 3 ：(uint8_t) number
CRC

## Page 8

8
ofservo
Parameter4：(uint8_t)
servo_id_1
Parameter5:(unit16_t)pulse
width
······
Parameter2N+2：(uint8_t)
servo_id_N
Parameter2N+3：(uint16_t)
pulse width
Example:Controlservo1andservo2torotateto90°and180°respectively,
correspondingtopulsewidthsof1500and2500,within2seconds:
Frame
Header
Function Code
Data
Length
Parameter Checksum
0xAA
0x55
PACKET_FUNC_PWM_SERVO 10
Parameter1：0x01
(subcommand)
Parameter2：0xD0 0x07
(2000)
Parameter3：0x02(the
numberofservos to be
controlled)
Parameter4:0x01(1)
Parameter5：0xDC0x05
(1500)
Parameter6：0x02(2)
Parameter7：0xC4 0x09
(2500)
CRC
（2）Control single PWM servo

## Page 9

9
Frame
Header
Function Code
Data
Length
Parameter Checksum
0xAA
0x55
PACKET_FUNC_PWM_SERVO 6
Parameter1：（uint8_t）0x03
（subcommand）
Parameter 2：（uint16_t）
motion time(ms)
Parameter 3 ： （uint8_t ）
servo_id
Parameter 4：（uint16_t）
pulsewidth
CRC
Thepulsewidthrangesfrom[500,2500],correspondingto[0°,180°].
Example:
Controlservo1torotatetothe90°positionwithin1second,withapulsewidth
of1500:
Frame
Header
Function Code
Data
Length
Parameter
Check
sum
0xAA 0x55
PACKET_FUNC_PWM_SERV
O
6
Parameter 1 ： 0x03
（subcommand）
Parameter 2：0xE8 0x03
（1000）
Parameter3：0x01（1）
Parameter4：0xDC0x05
（1500）
CRC
（3）Read PWM servo position
Frame
Header
Function Code
Data
Length
Parameter
Checks
um
0xAA PACKET_FUNC_PWM_SERVO 2 Parameter 1 ： （uint8_t ）0x05 CRC

## Page 10

10
0x55 （subcommand）
Parameter2：（uint8_t）servo_id
Aftersendingthecommandtoreadtheposition,thecontrolboardwillsendthe
positiondataofthecorrespondingPWMservo withtheIDtothehost
computer."
（4）Set PWM Servo Deviation
Frame
Header
Function Code
Data
Length
Parameter
Checks
um
0xAA
0x55
PACKET_FUNC_PWM_SERVO 3
Parameter 1 ： （uint8_t ）0x07
（subcommand）
Parameter2：（uint8_t）servo_id
Parameter3：（uint8_t）deviation
parameter
（ Convert to int8_t type, valid
rangeis -100to +100）
CRC
Example:
Settheoffsetofservo2to+10
Frame
Header
Function Code
Data
Length
Parameter
Check
sum
0xAA
0x55
PACKET_FUNC_PWM_SERVO 3
Parameter 1 ： 0x07
（subcommand）
Parameter2：0x02（2）
Parameter3：0x0A（10）
CRC
（5）Read PWM Servo Deviation
Frame
Header
Function Code
Data
Length
Parameter
Checks
um
0xAA PACKET_FUNC_PWM_SERVO 2 Parameter 1 ： （uint8_t ）0x09 CRC

## Page 11

11
0x55 （subcommand）
Parameter2：（uint8_t）servo_id
Aftersendingthecommandtoreadtheposition,thecontrolboardwillsendthe
offsetdataofthecorrespondingPWMservowiththeIDtothehostcomputer.
5. Serial bus servo control: Instruction name
PACKET_FUNC_BUS_SERVO，value 5

| Subcommand | Meaning |
| --- | --- |
| 0x01 | Control serial bus servo to move |
| 0x05 | Read position |
| 0x07 | Read input voltage |
| 0x09 | Read temperature |
| 0x0B | Motor power-off |
| 0x0C | Motor power-on |
| 0x10 | ID writing |
| 0x12 | ID reading |
| 0x20 | Deviation adjusting |
| 0x22 | Deviation reading |
| 0x24 | Deviation saving |
| 0x30 | Position limit setting |
| 0x32 | Position limit reading |
| 0x34 | Voltage limit setting |
| 0x36 | Voltage limit reading |
| 0x38 | Temperature limit setting |
| 0x3A | Temperature limit reading |

| Field | Format | Description |
| --- | --- | --- |
| Frame Header | 0xAA 0x55 | Start of frame |
| Function Code | PACKET_FUNC_BUS_SERVO | Bus servo instruction |
| Data Length | 3N+4 / 2 / 3 / 6 | Depends on the command type |
| Parameter 1 | uint8_t subcommand | Selects the operation to perform |
| Parameter 2+ | Variable | Servo IDs, motion time, pulse widths, or limits |
| Checksum | CRC | Frame integrity check |

（1）Control serial bus servo to move
Frame
Header
FunctionCode
Data
Length
Parameter Checksum
0xAA
0x55
PACKET_FUNC_BUS_SERVO 3N+4
Parameter1：（uint8_t）0x01
（subcommand）
Parameter 2 ： （uint16_t ）
motion time(ms)
Parameter3：（uint8_t）servo
quantity
Parameter 4 ： （uint8_t ）
servo_id_1
Parameter 5 ： （uint16_t ）
Pulsewidth
······
Parameter2N+1：（uint8_t）
servo_id_N
Parameter2N+2：（uint16_t）
Pulsewidth
CRC
Example:
Controlbusservo1andservo 2torotateto200°and240°respectively,
correspondingtopulsewidthsof833and1000,within1second:

## Page 12

12
Frame
Header
FunctionCode
Data
Length
Parameter Checksum
0xAA
0x55
PACKET_FUNC_BUS_SERVO 10
Parameter 1 ： 0x01
（subcommand）
Parameter2：0xE80x03
（1000）
Parameter3：0x02（2）
Parameter4：0x01（1）
Parameter5：0x410x03
（833）
Parameter4：0x02（2）
Parameter5：0xE80x03
（1000）
CRC
（2）Read position command
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERV
O
2
Parameter 1 ： （ uint8_t ） 0x05
（subcommand）
Parameter2：（uint8_t）servo_id
CRC
Aftersendingthecommandtoreadtheposition,thecontrolboardwillsendthe
positiondataofthecorrespondingbusservowiththeIDtothehostcomputer.
（3）Read the input voltage command
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERV
O
2
Parameter 1 ： （ uint8_t ） 0x07
（subcommand）
CRC

## Page 13

13
Parameter2：（uint8_t）servo_id
Aftersendingthecommandtoreadtheinputvoltage,thecontrolboardwill
sendtheinputvoltagedataofthecorrespondingbusservowiththeIDtothe
hostcomputer.
（4）Read temperature command
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Checks
um
0xAA
0x55
PACKET_FUNC_BUS_SERV
O
2
Parameter 1 ： （ uint8_t ） 0x09
（subcommand）
Parameter2：（uint8_t）servo_id
CRC
Aftersendingthecommandtoreadthetemperature,thecontrolboardwill
sendthetemperaturedataofthecorrespondingbusservowiththeIDtothe
hostcomputer.
（5）Motor power-off command
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERV
O
2
Parameter 1 ： （ uint8_t ） 0x0B
（subcommand）
Parameter2：（uint8_t）servo_id
CRC
Aftersendingthecommandtounloadpower,thecontrolboardwillunloadthe
powerofthecorrespondingbusservo withtheID.
（6）Motor power-on command
Frame
Header
Function Code
Data
Length
Parameter
Chec
ksum

## Page 14

14
0xAA
0x55
PACKET_FUNC_BUS_SERVO 2
Parameter 1 ： （uint8_t ）0x0C
（subcommand）
Parameter2：（uint8_t）servo_id
CRC
Aftersendingthecommandtoloadpower,thecontrolboardwillloadpowerto
thecorrespondingbusservo withtheID.
（7）ID writing command
Frame
Header
Function Code
Data
Length
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERVO 3
Parameter1:（uint8_t）0x10
（subcommand）
Parameter 2:（uint8_t）servo_id
Parameter3:（uint8_t）save_id
CRC
AftersendingtheIDwritecommand,thecontrolboardwilloverwritetheID
numberofthecorrespondingbusservo.
（8）ID reading command
Frame
Header
Function Code
Data
Length
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERVO 2
Parameter1 ： （ uint8_t ） 0x12
（subcommand）
Parameter2 ： （ uint8_t ） 0xFE
（BroadcastQuery）
CRC
AftersendingtheIDreadcommand,thecontrolboardwilluploadtheID
numberofthebusservotothehostcomputer.
Note: There can only be one bus servo here. Otherwise, multiple bus servos
returning data simultaneously will cause bus conflicts.

## Page 15

15
（9）Deviation adjusting command
Frame
Header
Function Code
Data
Length
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERVO 3
Parameter 1 ： （ uint8_t ） 0x20
（subcommand）
Parameter2：（uint8_t）servo_id
Parameter3：（uint8_t）deviation
adjustmentvalue
CRC
Aftersendingtheoffsetadjustmentcommand,thecontrolboardwillsetthe
offsetvalueofthecorrespondingbusservowiththevalueofparameter3.
（10）Deviation reading command
Frame
Header
FunctionCode
Data
Length
Parameter
Check
sum
0xAA
0x55
PACKET_FUNC_BUS_SERVO 2
Parameter 1 ： （uint8_t ）0x22
（subcommand）
Parameter2：（uint8_t）servo_id
CRC
Aftersendingtheoffsetreadcommand,thecontrolboardwillreadtheoffset
valueofthecorrespondingbusservoanduploadittothehostcomputer.
（11）Deviation saving command
Frame
Header
Function Code
Data
Length
Parameter
Check
sum
0xAA
0x55
PACKET_FUNC_BUS_SERVO 2
Parameter 1 ： （uint8_t ）0x24
（subcommand）
Parameter2：（uint8_t）servo_id
CRC
Aftersendingtheoffsetsavecommand,thecontrolboardwillenablethe

## Page 16

16
correspondingbusservowiththeIDtosaveitscurrentoffsetvalue.
（12）Position limit setting command
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERV
O
6
Parameter 1 ： （ uint8_t ） 0x30
（subcommand）
Parameter2：（uint8_t）servo_id
Parameter3：（uint16_t）lowerlimit
Parameter4：（uint16_t）higherlimit
CRC
Thenumericalrangeofthelimitis[0,1000].
Aftersendingthepositionlimitsettingcommand,thecontrolboardwillsetthe
limitparametersforthecorrespondingIDofthebusservo.
（13）Position limit reading command
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERV
O
2
Parameter 1 ： （ uint8_t ） 0x32
（subcommand）
Parameter2：（uint8_t）servo_id
CRC
Aftersendingthepositionlimitreadcommand,thecontrolboardwillupload
thelimitparametersofthecorrespondingbusservo tothehostcomputer.
（14）Voltage Limit Setting Command
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Chec
ksum

## Page 17

17
0xAA
0x55
PACKET_FUNC_BUS_SERV
O
6
Parameter 1 ： （ uint8_t ） 0x34
（subcommand）
Parameter 2：（uint8_t）servo_id
Parameter3：（uint16_t）lowerlimit
Parameter4：（uint16_t）higherlimit
CRC
Thelowvoltagelimitvalueshouldbegreaterthan4500,andthehighvoltage
limitvalueshouldbelessthan14000.
Aftersendingthevoltagelimitsettingcommand,thecontrolboardwillsetthe
voltagelimitparametersforthecorrespondingIDofthebusservo.
（15）Voltage limit reading command
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERV
O
2
Parameter 1 ： （ uint8_t ） 0x36
（subcommand）
Parameter2：（uint8_t）servo_id
CRC
Aftersendingthevoltagelimitreadcommand,thecontrolboardwilluploadthe
voltagelimitparametersofthecorrespondingbusservo tothehostcomputer.
（16）Temperature limit setting command
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERV
O
3
Parameter 1 ： （ uint8_t ） 0x38
（subcommand）
Parameter2：（uint8_t）servo_id
Parameter 3 ： （ uint8_t ） high
CRC

## Page 18

18
temperaturethreshold
Theparametervalueforthehigh-temperaturethresholdshouldbelessthan
100.
Aftersendingthetemperaturelimitsettingcommand,thecontrolboardwillset
thehigh-temperaturethresholdparameterforthecorrespondingIDofthebus
servo.
（17）Temperature limit reading command
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Chec
ksum
0xAA
0x55
PACKET_FUNC_BUS_SERV
O
2
Parameter 1 ： （ uint8_t ） 0x3A
（subcommand）
Parameter2：（uint8_t）servo_id
CRC
Aftersendingthetemperaturelimitsettingcommand,thecontrolboardwill
uploadthehigh-temperaturethresholdparameterofthecorrespondingbus
servotothehostcomputer.
2.2 Data sent by the control board to the user
1. Bus Servo Data Upload: Command name
PACKET_FUNC_BUS_SERVO, value 5

| Upload type | Command | Data fields |
| --- | --- | --- |
| Position upload | 0x05 | servo_id, success flag, servo position |
| Voltage upload | 0x07 | servo_id, success flag, servo voltage |
| Temperature upload | 0x09 | servo_id, success flag, servo temperature |
| ID upload | 0x12 | broadcast command, success flag, read servo_id |
| Deviation upload | 0x22 | broadcast command, success flag, servo deviation |
| Position limit upload | 0x32 | servo_id, success flag, lower/upper limit |
| Voltage limit upload | 0x36 | servo_id, success flag, lower/upper limit |
| Temperature limit upload | 0x3A | servo_id, success flag, temperature limit |

（1）Serial bus servo position upload
Frame
Header
FunctionCode
Data
Leng
th
Parameter
Che
cksu
m
0xAA 0x55
PACKET_FUNC_BUS_SERV
O
5
Parameter1：（uint8_t）servo_id
Parameter 2 ： （ uint8_t ） 0x05
（subcommand）
CRC

## Page 19

19
Parameter3：（int8_t）Wastheread
successful?
（0：success；-1：fail）
Parameter 4 ： （int16_t ）servo
position
Whenareadcommandisreceived,thecorrespondingservo'sposition
parameterisreadanduploadedtothehostcomputer.
Example:
Theangleofservo 5isuploadedas30°,correspondingtoapulsewidthof
833:
Frame
Header
FunctionCode
Data
Lengt
h
Parameter
Checks
um
0xAA 0x55
PACKET_FUNC_BUS_SERV
O
5
Parameter1：0x05（5）
Parameter 2 ： 0x05
（subcommand）
Parameter3：0x00（0）
Parameter 4 ：0x41 0x03
（833）
CRC
（2）Bus Servo Voltage Upload
Frame
Header
FunctionCode
Data
Leng
th
Parameter
Che
cksu
m
0xAA 0x55
PACKET_FUNC_BUS_SERV
O
5
Parameter1：（uint8_t）servo_id
Parameter 2 ： （ uint8_t ） 0x07
（subcommand）
Parameter3：（int8_t）Wastheread
CRC

## Page 20

20
successful?
（0：success；-1：fail）
Parameter 4：（uint16_t） servo
voltage
Whenareadcommandisreceived,thevoltageparameterofthe
correspondingservo isreadanduploadedtothehostcomputer.
（3）Bus Servo Temperature Upload
Frame
Header
FunctionCode
Data
Leng
th
Parameter
Che
cksu
m
0xAA 0x55
PACKET_FUNC_BUS_SERV
O
4
Parameter1：（uint8_t）servo_id
Parameter 2 ： （ uint8_t ） 0x09
（subcommand）
Parameter 3 ： （int8_t ）Was the
readingsuccessful
（0：success；-1：fail）
Parameter 4 ： （uint8_t ）servo
temperature
CRC
Whenareadcommandisreceived,thetemperatureparameterofthe
correspondingservo isreadanduploadedtothehostcomputer.
（4）Serial Bus Servo ID Upload
Frame
Header
FunctionCode
Data
Leng
th
Parameter
Che
cksu
m
0xAA 0x55
PACKET_FUNC_BUS_SERV
O
4
Parameter 1 ： （ uint8_t ）0xFE
（broadcastcommand）
CRC

## Page 21

21
Parameter 2 ： （ uint8_t ） 0x12
（subcommand）
Parameter 3 ： （int8_t ）Was the
readingsuccessful
（0：success；-1：fail）
Parameter 4 ： （ uint8_t ） read
servo_id
Whenareadcommandisreceived,theIDnumberoftheservoisreadand
uploadedtothehostcomputer.
（5）Serial Bus Servo Deviation Parameter Upload
Frame
Header
FunctionCode
Data
Leng
th
Parameter
Che
cksu
m
0xAA 0x55
PACKET_FUNC_BUS_SERV
O
4
Parameter 1 ： （ uint8_t ）0xFE
（previous broadcastcommand）
Parameter 2 ： （ uint8_t ） 0x22
（subcommand）
Parameter 3 ： （int8_t ）Was the
readingsuccessful
（0：success；-1：fail）
Parameter 4 ： （uint8_t ）servo
deviation
CRC
Whenareadcommandisreceived,thedeviationparameterofthe
correspondingservo isreadanduploadedtothehostcomputer.
（6）Bus Servo Position Limit Parameter Upload
Frame FunctionCode Data Parameter Che

## Page 22

22
Header Leng
th
cksu
m
0xAA 0x55
PACKET_FUNC_BUS_SERV
O
7
Parameter1：（uint8_t）servo_id
Parameter 2 ： （ uint8_t ） 0x32
（subcommand）
Parameter 3 ： （int8_t ）Was the
readingsuccessful
（0：success；-1：fail）
Parameter4：（uint16_t）lowerlimit
Parameter5：（uint16_t）higherlimit
CRC
Whenareadcommandisreceived,thepositionlimitparametersofthe
correspondingservo arereadanduploadedtothehostcomputer.
（7）Serial Bus Servo Voltage Limit Parameter Upload
Frame
Header
FunctionCode
Data
Leng
th
Parameter
Che
cksu
m
0xAA 0x55
PACKET_FUNC_BUS_SERV
O
7
Parameter1：（uint8_t）servo_id
Parameter 2 ： （ uint8_t ） 0x36
（subcommand）
Parameter 3 ： （int8_t ）Was the
readingsuccessful
（0：success；-1：fail）
Parameter4：（uint16_t）lowerlimit
Parameter5：（uint16_t）higherlimit
CRC
Whenareadcommandisreceived,thevoltagelimitparametersofthe
correspondingservo arereadanduploadedtothehostcomputer.

## Page 23

23
（8）Bus Servo Temperature Limit Parameter Upload
Frame
Header
FunctionCode
Data
Leng
th
Parameter
Che
cksu
m
0xAA 0x55
PACKET_FUNC_BUS_SERV
O
4
Parameter1：（uint8_t）servo_id
Parameter 2 ： （ uint8_t ） 0x3A
（subcommand）
Parameter 3 ： （int8_t ）Was the
readingsuccessful
（0：success；-1：fail）
Parameter4：（uint8_t）temperature
limit
CRC
Whenareadcommandisreceived,thetemperaturelimitparametersofthe
correspondingservo arereadanduploadedtothehostcomputer.
2. Upload Button Message: Instruction Name PACKET_FUNC_KEY,
Value 6
Frame
Header
FunctionCode
Data
Length
Parameter Checksum
0xAA 0x55 PACKET_FUNC_KEY 2
Parameter 1 ：(uint8_t)
button_id
Parameter 2 ：(uint8_t)
button event
CRC
Partialbuttoneventcallbackvaluesareasfollows:
BUTTON_EVENT_PRESSED=0x01,/*Buttonpressed/
BUTTON_EVENT_LONGPRESS=0x02,/Buttonlongpressed/
BUTTON_EVENT_CLICK=0x20,/Buttonclicked/
BUTTON_EVENT_DOUBLE_CLICK=0x40,/Buttondouble-clicked*/
Example:

## Page 24

24
Sendamessageindicatingthatbutton1ispressed:
Frame
Header
FunctionCode
Data
Length
Parameter Checksum
0xAA 0x55 PACKET_FUNC_KEY 2
Parameter1：0x01
Parameter2：0x01
CRC
3. Upload IMU Data: Command Name PACKET_FUNC_IMU, Value 7
Frame
Header
FunctionCode
Data
Length
Parameter Checksum
0xAA 0x55 PACKET_FUNC_IMU 24
Parameter 1 ： (float)
accel_x data
Parameter 2 ： (float)
accel_y data
Parameter 3 ： (float)
accel_z data
Parameter 4 ： (float)
gyro_x data
Parameter 5 ： (float)
gyro_y data
Parameter 6 ： (float)
gyro_z data
CRC
4. PWM servo control: Command name PACKET_FUNC_PWM_SERVO,
value 4
（1）PWM servo position upload
Frame
Header
Function Code
Data
Length
Parameter
Checks
um
0xAA PACKET_FUNC_PWM_SERVO 4 Parameter1：(uint8_t)servo_id CRC

## Page 25

25
0x55 Parameter 2 ： (uint8_t)0x05
（subcommand）
Parameter 3 ： (uint16_t)pulse
width
Uponreceivingthereadcommand,readthepulsewidthofthecorresponding
servoanduploadittothehostcomputer.
（2）PWM servo deviation upload
Frame
Header
FunctionCode
Data
Length
Parameter
Checks
um
0xAA
0x55
PACKET_FUNC_PWM_SERVO 3
Parameter1：(uint8_t)servo_id
Parameter 2 ： (uint8_t)0x05
（subcommand）
Parameter 3 ： (int8_t)servo
deviation
CRC
Uponreceivingthereadcommand,readthepulsewidthofthecorresponding
servoanduploadittothehostcomputer.
Common Communication Protocol Examples
Preparation:
Opentheserialportassistant,connectviatype-CtoUART1,setthebaudrate
to1000000,andselectHEX(hexadecimaltransmission).
Examples:
1. Controlthebuzzertosound5times,atafrequencyof1400Hz,eachtime
for100msandstopfor100ms:
AA5502087805640064000500F0
2. Controlthebuzzertosound10times,atafrequencyof1000Hz,eachtime
for500msandstopfor300ms:
AA550208E803F4012C010A008B

## Page 26

26
3. ControltheLEDlighttoflash10times,eachtimeonfor500msandofffor
300ms:
AA55010701F4012C010A0004
4. ControltheLEDlighttoflash5times,eachtimeonfor100msandofffor
100ms:
AA5501070164006400050037
5. Singlemotorcontrolmovement:Controlmotor1torotateat-1r/sspeed:
AA5503060001000080BFDA
6. Controlmotor1tostop:
AA550302020108
7. Controlmotor1andmotor2torotateat-1r/sand2r/srespectively:
AA55030C010201000080BF0200000040FB
8. Controlmotors1and3tostop:
AA5503020305AD
9. Controlservo1andservo2torotateto90°and180°respectively,
correspondingtopulsewidthsof1500,2500,2s:
AA55040A01D0070201DC0502C409C8
10. ControlPWMservo1tomoveto1000:
AA55040603e80301e803e4
11. SetPWMservodeviation:Setthedeviationofservo2to+10:
AA55030307020A53
12. Controlbusservo rotation:ControlbusservoNo.1andNo.2to200°and
240°respectively,thecorrespondingpulsewidthsare833and1000,andit
takes1s:
AA55050A01E8030201410302E8039F
13. Controlthebusservotorotate:ControlbusservoNo.1andNo.2torotate
to0°,thecorrespondingpulsewidthis0,andthetimeis1s:
AA55050A01E80302010000020000D2
14. ControlthebusservowithID1topoweroff:

## Page 27

27
AA5505020B01B3
15. ControlthebusservowithID1topoweron:
AA5505020C01DD
16. ChangetheIDofthebusservowithID1to2:
AA55050310010268
Expansion—Using the Calculator Tool for Base Conversion
UsingtheWindowsCalculatorforBaseConversion:
①：OpentheStartmenu,searchforCalculator,andopenit.
②：ClickontheOpenNavigationbuttoninthetopleftcorner,andselect
Programmer.

## Page 28

28
③：Fourbasesareavailableforselection.Chooseonebase,inputavalue,
andtheequivalentvaluesintheotherthreebaseswillbedisplayed.

## Page 29

29