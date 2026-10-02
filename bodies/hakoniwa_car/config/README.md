# Hakoniwa Car body

The Hakoniwa Car is a small autonomous delivery vehicle authored for Hakoniwa
from MuJoCo primitives: a cab in front (dark windshield with two "eye" lights,
a blue LED strip), a cargo box behind (two side panels, a rear door, red tail
lights), and a roof sensor pod with a LiDAR. It is about the golf cart's size
(1.2 m wide, 2.2 m long, 1.77 m high with the LiDAR) and has the same
Ackermann structure: two independently steered front wheels and two driven
rear wheels.

- `model.xml`: the visual model (boxes and cylinders, no contact, no mass) and
  the joint structure; the vehicle frame is 0.42 m above the ground
- `collision_primitives.yaml`: the physical chassis (about 300 kg in all, low
  between the wheels), massless cab/cargo and LiDAR proxies, narrow tire treads
- `actuators.yaml`: steering (position) and rear-wheel (velocity) actuators
- `contact_excludes.yaml`: intentional assembly self-contact exclusions
- `mujoco_world.yaml`: the minimal test world
- `ackermann-forge.yaml`: the Forge input and the acceptance contract
  (wheelbase 1.50 m, track 1.00 m, wheel radius 0.25 m, maximum centre
  steering 0.60 rad, maximum wheel speed 12 rad/s = 3.0 m/s)
- `viewer.recipe.yaml`: viewer-neutral GLB assembly and movable joints
- `provenance.yaml`: origin and license

Generate and check every derived file with:

```bash
python tools/ackermann/forge.py hakoniwa_car
python tools/ackermann/forge.py hakoniwa_car --verify
python tools/ackermann/validate.py hakoniwa_car
```

The generated runtime model is `generated/model.minimal_world.xml`; the
browser presentation is `generated/parts/*.glb` and `generated/view-model.json`.
Do not hand-edit generated files.

Carrying a load is not modelled yet: the cargo box is a closed shape with a
massless collision proxy.
