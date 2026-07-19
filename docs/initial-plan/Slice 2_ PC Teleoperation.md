# **Slice 2: PC Teleoperation**

## **Objective**

Enable manual control of the robot by bridging keyboard input from the PC to the Raspberry Pi.

## **Development Steps**

1. **ROS2 Setup:** Install teleop\_twist\_keyboard on the Pi or setup a custom node to capture Windows keyboard events via SSH.  
2. **Topic Mapping:** Ensure the teleop node publishes to /cmd\_vel using geometry\_msgs/Twist.  
3. **Verification:** Echo the /cmd\_vel topic on the Pi to verify inputs arrive from the PC.

## **Technical Details**

* **Message Type:** geometry\_msgs/Twist  
* **Linear X:** Forward/Backward  
* **Angular Z:** Rotation  
* **Topic Name:** /cmd\_vel

## **Deliverables**

* Successfully publishing velocity commands from the PC to the Raspberry Pi via ROS2 topics.