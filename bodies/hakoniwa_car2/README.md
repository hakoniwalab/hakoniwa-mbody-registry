# Hakoniwa Car 2

An original, manufacturer-neutral five-door compact hatchback for highway simulations.

- length 4.380 m, width 1.780 m, height 1.520 m
- wheelbase 2.600 m, track 1.520 m, tire radius 0.310 m
- nominal mass 1,200 kg
- right-hand driver's eye: `[0.45, -0.38, 0.84]` in the vehicle frame, or 1.15 m above ground

Generate all configured colours and Forge the body:

```bash
python bodies/hakoniwa_car2/config/build_model.py
python tools/ackermann/forge.py hakoniwa_car2
python tools/ackermann/forge.py hakoniwa_car2 --verify
python tools/ackermann/validate.py hakoniwa_car2
```

Add a colour by adding one entry to `COLORS` in `config/build_model.py` and the same name/path under `variants` in `config/ackermann-forge.yaml`.
