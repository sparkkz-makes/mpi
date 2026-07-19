# **MentorPi Project Master Document**

## **1\. Project Overview & Philosophy**

* **Purpose:** Educational/Hobbyist platform to learn robotics, control, and AI.  
* **Goal:** Build a software control system from scratch.  
* **Philosophy:** Modular design (driver-centric), extensible for future kinematics and AI integration.

## **2\. Hardware Specifications**

* **Chassis:** MentorPi platform (Four-wheel Mecanum drive).  
* **Controller:** Raspberry Pi (Ubuntu LTS, ROS2).  
* **Driver Board:** RRC Lite (STM32F407VET6, Serial interface).  
* **Motors:** 4x High-speed closed-loop DC motors with AB-phase quadrature encoders.  
* **Power System:** 7.4V 2200mAh 10C LiPo Battery.  
* **Sensors:** \* Camera: USB interface (monocular or depth).  
  * LIDAR: STL-19P TOF LIDAR (360°).  
  * IMU: Integrated on RRC Lite.  
* **Servos:** 2x LFD-01 for 2DOF gimbal.

## **3\. Communication Protocols (RRC Lite)**

* **UART:** 1 Mbps (1,000,000 bps), 8 Data Bits, 1 Stop Bit, No Parity.  
* **Frame:** \[AA\]\[55\]\[Func\]\[Len\]\[Payload\]\[Checksum\].  
* **Checksum Calculation:** (Func \+ Len \+ sum(Payload)) & 0xFF.  
* **Byte Order:** Little-Endian (LSB first).

## **4\. Development Slices**

* **Slice 1: Base System & Serial Communication**  
  * *Objective:* Establish ROS2 env \+ Proof-of-life (buzzer).  
* **Slice 2: PC Teleoperation**  
  * *Objective:* Bridge PC keyboard to /cmd\_vel (geometry\_msgs/Twist).  
* **Slice 3: Motor Control with Encoders**  
  * *Objective:* Implement motor driver node \+ Encoder feedback (/joint\_states).  
* **Slice 4: Wireless Game Controller**  
  * *Objective:* Integrate USB joystick using joy and teleop\_twist\_joy.  
* **Slice 5: Full Mecanum Motion Control**  
  * *Objective:* Implement inverse kinematics for omnidirectional movement.  
* **Slice 6: Vision & Gimbal Integration**  
  * *Objective:* Enable camera streaming (MJPG/web\_video\_server) \+ PWM servo gimbal control.

## **5\. Kinematics & Motion Control**

* **Configuration:** ABAB setup of Type A and Type B Mecanum wheels.  
* **Principle:** Force vectors from 45° rollers allow omnidirectional movement.

## **6\. Extensibility Principles**

* **Kinematics:** Decouple Inverse Kinematics (IK) from driver nodes; plan for higher-level motion primitives (e.g., arc-path following, spiral patterns).  
* **Modularity:** Use standardized ROS2 messaging (e.g., sensor\_msgs/JointState, geometry\_msgs/Twist) to ensure hardware controllers can be swapped/upgraded without changing logic.