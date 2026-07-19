# **Slice 5: Full Mecanum Motion Control**

## **Objective**

Implement inverse kinematics to support true omnidirectional movement (forward, lateral strafing, and rotation).

## **Development Steps**

1. **Kinematic Math:** Implement the matrix transformation for the ABAB wheel configuration.  
   * Wheel\_FL \= Vx \- Vy \- W(L \+ W)  
   * Wheel\_FR \= Vx \+ Vy \+ W(L \+ W)  
   * ... and so on for A/B type wheels.  
2. **Integration:** Update the driver.py or create a new kinematics node to perform the math before sending serial motor commands.

## **Technical Details**

* **Input:** geometry\_msgs/Twist (vx, vy, w)  
* **Output:** 4x individual wheel speeds.

## **Deliverables**

* The robot moves laterally (strafe) and rotates accurately based on commanded Twist vectors.