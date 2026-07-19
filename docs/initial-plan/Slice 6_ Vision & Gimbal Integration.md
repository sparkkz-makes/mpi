# **Slice 6: Vision & Gimbal Integration**

## **Objective**

Enable camera streaming and remote gimbal control for the look-around functionality.

## **Development Steps**

1. **Gimbal Driver:** Add functionality to driver.py for FUNC\_PWM\_SERVO (Function Code 0x04) to control gimbal pitch/yaw servos.  
2. **Video Streaming:** Configure v4l2\_camera or usb\_cam ROS2 node to stream USB camera output.  
3. **Web Interface:** Set up a simple web\_video\_server node to broadcast the ROS2 topic as an MJPG stream (accessible via browser).

## **Technical Details**

### **Hardware Interface (Gimbal)**

* **Function Code:** 0x04 (FUNC\_PWM\_SERVO)  
* **Payload Structure:** \- ServoID (uint8)  
  * Angle (uint8 or uint16 depending on firmware scale)  
  * Duration (uint16, ms)

### **Vision Pipeline**

* **Stream Source:** /dev/video0  
* **ROS2 Topic:** /image\_raw  
* **Streaming Protocol:** MJPG (via web\_video\_server for mobile/PC browser support)

## **Extensibility**

* Future-proofing for Computer Vision (AI): The /image\_raw topic allows easy insertion of YOLO/OpenCV nodes between the stream and the UI.