# Sensor Placement

[Back to README](../../README.md)

---

## Camera

The camera is mounted 19 cm from the floor and angled downward.

**Why angled downward:**
Pointing the camera downward removes anything outside the game mat from the frame that would otherwise interfere with the HSV color detection. Without the downward tilt, the top portion of the frame picks up irrelevant colors that can trigger false detections.

**Why 19 cm:**
The height is a tradeoff between two things, the further up the camera is, the larger the field of view and the more of the track it can see ahead, which helps with early corner and pillar detection. However, a taller sensor tower takes longer to print and is more likely to tip or vibrate during sharp turns. 19 cm was chosen as a balance between a useful field of view and a practical, stable mount height.

## LiDAR
We were thinking about using a LiDAR but we scrapped that idea because we didn't have enough time and the robot was fine without it.

It was going to be placed in the front of our robot at a medium height so it could detect objects like the parking lot without covering up the camera.
