# Ackermann migration validation

The Ackermann toolchain turns the problems discovered while driving the
generic Golf Cart into repeatable acceptance tests for every vehicle port.
The validator is body-independent: names, dimensions, scenarios, and limits
come from `bodies/<body>/config/ackermann-forge.yaml`.

```bash
python tools/ackermann/validate.py generic_ackermann_golf_cart
python tools/ackermann/validate.py hunter_v2 --report /tmp/hunter-report.json
```

Business Pack Recipes run these commands with the managed Foundation Python.
Users do not need to create or reference an MBody-local virtual environment.

## Automatic scenarios

- idle: detects spontaneous motion and excessive contact settlement
- straight: checks forward authority, lateral drift, and yaw drift
- left/right turn: checks actual inner/outer steering angles, rear-wheel
  differential speed, forward authority, yaw response, turn direction, and
  left/right symmetry
- numerical health: rejects non-finite state and explosive single-step motion
- performance: measures headless RTF and enforces a conservative required
  minimum while retaining a separately configurable advisory target

The same dynamic validation runs as part of `forge.py <body> --verify`, after
the temporary model has been regenerated and loaded by MuJoCo.

## Boundary

This proves the generated body can respond to ideal actuator targets in
headless MuJoCo. It does not prove Hakoniwa PDU wiring, PS5 mappings, command
slew policy, Viewer mutex behavior, rendering smoothness, or real-vehicle
fidelity. Those remain downstream integration or manual acceptance tests.

This distinction is intentional. A bad body port should fail here; a runtime
stutter should be diagnosed in the runtime without weakening body validation.

## Optimization boundary

The user defines scenario inputs, hard tolerances, and simple relative score
weights in the body's `ackermann-forge.yaml`:

```yaml
validation:
  evaluation:
    score:
      method: weighted_tolerance_ratio
      weights:
        steering_tracking_rmse_rad: 2.0
        drive_tracking_rmse_rad_s: 1.0
        turn_yaw_asymmetry_ratio: 1.0
```

Each selected error is divided by its existing acceptance tolerance, then the
tool calculates the weighted mean. The displayed score is
`100 / (1 + normalized_loss)`: zero error is 100, while an average error equal
to the configured tolerances is 50. Weights are relative priorities and do not
need to total 100.

The JSON report contains raw error terms, normalized loss terms, one
`objective_loss` to minimize, and the display-oriented score. Hard pass/
fail checks remain authoritative; the score must not turn an unsafe candidate
into a pass.

This makes an optional optimizer such as Optuna a thin outer loop:

```text
candidate YAML in a temporary workspace
  -> Forge
  -> validate.py --report trial.json
  -> objective_loss
  -> next trial
```

An optimizer may propose actuator gains, force limits, or contact parameters.
It must not overwrite committed Recipe YAML. A person reviews the winning
candidate, records why it was selected, and then promotes it through the normal
Forge and verification flow. This preserves provenance and deterministic
regeneration while allowing automated search later.

The optional Optuna runner implements that boundary:

```bash
python tools/ackermann/optimize.py generic_ackermann_golf_cart \
  --output /tmp/golf-cart-tuning
```

The user controls the ranges, symmetric target assignments, trial count, and
seed in `ackermann-tuning.yaml`. Trial zero is always the accepted baseline.
Outputs include every trial report, `study.json`, `best-report.json`, a
loadable `best-model.xml`, and `best-candidate.yaml`. The latter explicitly
sets `promote_automatically: false`; promotion is a review action.

The optimizer minimizes the exact same user-weighted loss emitted by the
validator and adds a large penalty for every hard acceptance failure. It then
selects the winner only from passing trials, even if a future score definition
or penalty is configured poorly.
