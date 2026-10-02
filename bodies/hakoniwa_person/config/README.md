# Hakoniwa People body (箱庭人間)

Block-style people for the Hakoniwa town, made from MuJoCo primitives. Four
looks share one structure:

| variant | look |
|---|---|
| `visitor` | 立ち客: white shirt with an orange front, dark trousers |
| `staff` | 店員: white and orange cap, orange apron with the 箱庭 mark |
| `passerby` | 通行人: blue cap and vest, khaki trousers, backpack |
| `child` | 子ども: yellow hat, green shirt, shorts (0.7 scale) |

## Structure

A person is a stick that slides; the walk is an animation.

- `person` (root): `slide_x_joint`, `slide_y_joint` (world x, y) and
  `turn_joint` (about z). Its only collider is `person_collision`, a capsule
  of radius 0.22 m from 0.05 m to 1.58 m (an adult, 60 kg; a child is 0.7
  times as big). It floats above the ground, so it never rubs the floor; it
  stops at walls, cars and other people. Velocity actuators `move_x`,
  `move_y` (m/s) and `turn` (rad/s) drive it, with limited force.
- `torso` and its `head`: fixed to the root (the body does not bob).
- `arm_left` / `arm_right` on `shoulder_*_joint`, `leg_left` / `leg_right`
  on `hip_*_joint` (about y; the frames are at the shoulders and hips).
  Soft springs keep them straight; a runtime animates a walk by sending
  these joint angles to the viewer (legs and arms swinging opposite ways).
  The hips bend to 100° for a seated pose.
- `shadow`: a flat dark disc under the feet, the root's part in the viewer.

Visual geoms are in group 1 with no contact and no mass.

## Files

- `config/build_model.py`: writes `config/model.<variant>.xml`; with
  `--generate`, also `generated/<variant>/` (the model, its GLB parts split
  by body, the viewer recipe and `view-model.json`). Change the people there
  and run it again:

```bash
python bodies/hakoniwa_person/config/build_model.py --generate
```

The GLBs use `mjcf2glb.py --capsule-count 12`, because the rounded boxes are
made of many small capsules (about 330 KB per person instead of 3 MB).
