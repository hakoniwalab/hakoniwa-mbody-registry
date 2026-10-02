# Hakoniwa Cart body

The Hakoniwa Cart is a four-seat cart authored for Hakoniwa from MuJoCo
primitives: a front in three layers just ahead of the front wheels (a black cowl, one thin softly rounded white face, a dark grey bumper with a slot); the round head lamps sit in black eye sockets that narrow inwards into the thin LED bar joining them, and the white sides flow down to the wheel arches in slants over dark grey flares and a white LED
bar between them over a dark bumper, two rows of seats facing forward (the
driver on the front left), a grab bar behind the rear row, round red tail
lamps, and a long white roof with orange lines on black pillars (the
windshield is an open frame). It is 3.1 m long, 1.4 m wide with the mirrors
and 2.5 m high, and has the same Ackermann structure as the Hakoniwa Car: two
independently steered front wheels and two driven rear wheels.

- `build_model.py`: writes `model.xml`; the panels (face, cowl, bumpers,
  pedestals, rear body, seats, roof) are rounded boxes, the eye sockets discs
  and flat ellipsoids, the side lines tilted boxes (three boxes and twelve edge
  capsules each), the wheel arches half circles of capsules, the steering
  wheel a ring of capsules. Change the model there and run it, then the Forge
- `model.xml`: the visual model (boxes, cylinders and capsules, no contact,
  no mass) and the joint structure; the vehicle frame is 0.45 m above the ground
- `collision_primitives.yaml`: the physical chassis (about 350 kg in all, low
  between the wheels), massless body and roof proxies, narrow tire treads
- `actuators.yaml`: steering (position) and rear-wheel (velocity) actuators
- `contact_excludes.yaml`: intentional assembly self-contact exclusions
- `mujoco_world.yaml`: the minimal test world
- `ackermann-forge.yaml`: the Forge input and the acceptance contract
  (wheelbase 2.10 m, track 1.04 m, wheel radius 0.27 m, maximum centre
  steering 0.60 rad, maximum wheel speed 11 rad/s = 3.0 m/s)
- `viewer.recipe.yaml`: viewer-neutral GLB assembly and movable joints
- `lights.yaml`: the lights (`tools/glb_add_lights.py`, run by the Forge on the parts GLB): the head lamps and the LED bar glow white, the tail lamps red, the markers and mirror signals amber, and two head lights (spot lights) light the way at night
- `provenance.yaml`: origin and license

Four 箱庭人間 (`bodies/hakoniwa_person`) ride it. Their hips go on these seat
points in the vehicle frame (the cushions' tops are at z 0.42; the hip sits a
little into the cushion, in front of the backrest), the legs bent over the
cushion's front edge:

| seat | x | y | z |
|---|---|---|---|
| driver (front left, behind the steering wheel) | 0.12 | 0.26 | 0.38 |
| passenger (front right) | 0.12 | -0.26 | 0.38 |
| rear_left | -1.08 | 0.26 | 0.38 |
| rear_right | -1.08 | -0.26 | 0.38 |

Seated adults' heads stay about 0.4 m under the roof.

Generate and check every derived file with:

```bash
python bodies/hakoniwa_cart/config/build_model.py
python tools/ackermann/forge.py hakoniwa_cart
python tools/ackermann/forge.py hakoniwa_cart --verify
python tools/ackermann/validate.py hakoniwa_cart
```

The generated runtime model is `generated/model.minimal_world.xml`; the
browser presentation is `generated/parts/*.glb` and `generated/view-model.json`.
Do not hand-edit generated files.
