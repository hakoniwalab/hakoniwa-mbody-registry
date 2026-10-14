# Hakoniwa Truck

An original, manufacturer-neutral medium cab-over box truck for highway simulations.

- length 8.00 m, width 2.30 m, height 3.20 m
- wheelbase 4.30 m, front track 1.85 m, rear track 1.70 m, tire radius 0.45 m
- nominal simulation mass 6,000 kg, rear-wheel drive; suspension tuning uses
  the current empty-cargo-box model (5,950 kg sprung body plus unsprung wheels
  and steering carriers)
- suspension: 1.70 Hz, damping ratio 0.35, travel +/-0.10 m; front and rear
  rates are derived separately from the static axle loads at CG x=-0.60 m
- right-hand driver's eye: `[3.15, -0.42, 1.75]` in the vehicle frame, or 2.20 m above ground

Generate all configured cab colours and Forge the body:

```bash
python bodies/hakoniwa_truck/config/build_model.py
python tools/ackermann/forge.py hakoniwa_truck
python tools/ackermann/forge.py hakoniwa_truck --verify
python tools/ackermann/validate.py hakoniwa_truck
```

Add a cab colour by adding one entry to `CAB_COLORS` in `config/build_model.py` and the same name/path under `variants` in `config/ackermann-forge.yaml`.
