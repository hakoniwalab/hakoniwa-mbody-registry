# TurtleBot3 Godot Reference Scene ROS->Godot v2

This version separates the coordinate conversion node and the robot pose node:

```text
TurtleBot3
  HakoSync
  RosToGodot        # fixed ROS -> Godot conversion
    Visuals         # robot pose target
      base_link
        wheel_left_link
        wheel_right_link
        base_scan
```

The conversion is:

```text
godot_x = -ros_y
godot_y =  ros_z
godot_z = -ros_x
```

If v1 still looked sideways, use this v2. The Transform3D component order is adjusted for Godot's `.tscn` serialization.
