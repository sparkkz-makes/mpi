# **Slice 1: Base System & Serial Communication**

## **Objective**

Establish a functional ROS2 environment on the Raspberry Pi and verify low-level communication with the RRC Lite board by triggering an audible buzzer response.

## **Development Steps**

1. **Repository Setup:** Initialize \~/dev/ros2\_ws and create a mentorpi\_driver package.  
2. **Serial Driver Implementation:** Create a Python node that initializes a pyserial connection to the RRC Lite board at 1,000,000 bps.  
3. **Protocol Testing:** Implement the RRCLiteProtocol class (from stash) to generate a valid buzzer command packet.  
4. **Verification:** Send the packet and confirm the buzzer sounds.

## **Technical Details**

### **ROS2 Setup**

* **Workspace:** \~/dev/ros2\_ws/src/mentorpi\_driver  
* **Package Structure:**  
  * mentorpi\_driver/  
    * driver.py (Main loop for serial communication)  
    * protocol.py (Contains the RRCLiteProtocol class)  
    * setup.py / package.xml

### **Hardware Interface (RRC Lite)**

* **Serial Port:** /dev/ttyUSB0 (or similar, requires verification via ls /dev/tty\*)  
* **Protocol Command (Buzzer):**  
  * **Function Code:** 0x02  
  * **Data Length:** 0x08 (8 bytes)  
  * **Example Packet:** AA 55 02 08 78 05 64 00 64 00 05 00 F0 (1400Hz, 100ms ON/OFF, 5 cycles).  
* **Checksum:** Calculated as (Function \+ Length \+ sum(Parameters)) & 0xFF.

## **Deliverables**

* A working ROS2 node capable of opening the serial port and sending formatted commands.  
* Audible buzzer confirmation upon node execution.