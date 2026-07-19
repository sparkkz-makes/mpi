# **Slice 3: Motor Control with Encoders**

## **Objective**

Implement a motor driver node that translates cmd\_vel into raw serial commands and reads encoder feedback.

## **Development Steps**

1. **Motor Driver Node:** Subscribe to /cmd\_vel. Calculate target velocities for 4 wheels.  
2. **Serial Integration:** Map velocities to FUNC\_MOTOR (Function Code 0x03).  
3. **Encoder Feedback:** Regularly poll FUNC\_IMU or dedicated encoder function codes to retrieve wheel speeds. Publish these as sensor\_msgs/JointState.

## **Technical Details**

* **Motor Command (Func 0x03):** Payload usually expects 4x Int16 or Int32 (speed/direction).  
* **Encoder Feedback:** Requires polling at 20-50Hz to ensure smooth odometry calculations.

## **Deliverables**

* Robot responds to /cmd\_vel with actual wheel motion.  
* /joint\_states topic provides real-time encoder feedback.