# **Slice 4: Wireless Game Controller**

## **Objective**

Replace keyboard teleoperation with a physical USB wireless game controller.

## **Development Steps**

1. **Input Detection:** Verify joy\_node can read the USB dongle at /dev/input/js0.  
2. **Mapping:** Use teleop\_twist\_joy to map joystick axes to cmd\_vel linear/angular components.  
3. **Safety:** Implement an "Enable" button (Deadman switch) on the controller to prevent accidental motion.

## **Technical Details**

* **Package:** joy and teleop\_twist\_joy.  
* **Parameter File:** Create a .yaml config to map specific joystick buttons/axes to move/strafe/rotate commands.

## **Deliverables**

* Fluid manual control using the physical game controller.