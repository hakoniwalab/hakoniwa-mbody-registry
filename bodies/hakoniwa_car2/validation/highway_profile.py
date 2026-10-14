#!/usr/bin/env python3
"""Run deterministic highway profiles and write Hakoniwa-time CSV evidence."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys

import mujoco
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/ackermann"))
from validate import Harness, ackermann_targets  # noqa: E402

BODY = ROOT / "bodies/hakoniwa_car2"
CONTRACT = yaml.safe_load((BODY / "config/ackermann-forge.yaml").read_text(encoding="utf-8"))["validation"]
MODEL = BODY / "generated/model.minimal_world.xml"
OUT = BODY / "validation/results"
SAMPLE_SEC = 0.02


def forward_speed(data, base_qvel: int, yaw: float) -> float:
    return math.cos(yaw) * float(data.qvel[base_qvel]) + math.sin(yaw) * float(data.qvel[base_qvel + 1])


def run(name: str, controller, duration: float) -> list[dict]:
    harness = Harness(MODEL, CONTRACT)
    data = mujoco.MjData(harness.model)
    mujoco.mj_forward(harness.model, data)
    for _ in range(math.ceil(1.0 / harness.model.opt.timestep)):
        mujoco.mj_step(harness.model, data)
    base_qvel = int(harness.model.jnt_dofadr[harness.freejoint])
    rows = []
    next_sample = 0.0
    commanded_speed = 0.0
    commanded_steer = 0.0
    previous_speed = 0.0
    previous_world_vy = 0.0
    while data.time < duration + 1.0:
        elapsed = data.time - 1.0
        state = harness.state(data)
        yaw = float(state["yaw_rad"])
        speed = forward_speed(data, base_qvel, yaw)
        command = controller(max(0.0, elapsed), data, speed, commanded_speed, commanded_steer)
        commanded_speed, target_steer = command
        max_step = 0.5 * harness.model.opt.timestep
        commanded_steer += max(-max_step, min(max_step, target_steer - commanded_steer))
        targets = ackermann_targets(commanded_speed, commanded_steer, harness.geometry)
        for key, value in targets.items():
            data.ctrl[harness.actuator_ids[key]] = value
        mujoco.mj_step(harness.model, data)
        if elapsed + 1e-9 >= next_sample:
            position = state["position_m"]
            world_vx = float(data.qvel[base_qvel])
            world_vy = float(data.qvel[base_qvel + 1])
            rows.append({
                "hako_time_sec": round(max(0.0, elapsed), 6),
                "x_m": position[0], "y_m": position[1],
                "speed_m_s": speed,
                "acceleration_m_s2": (speed - previous_speed) / SAMPLE_SEC if rows else 0.0,
                "lateral_acceleration_m_s2": (world_vy - previous_world_vy) / SAMPLE_SEC if rows else 0.0,
                "steering_rad": commanded_steer,
                "commanded_speed_m_s": commanded_speed,
            })
            previous_speed = speed
            previous_world_vy = world_vy
            next_sample += SAMPLE_SEC
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def first_time(rows, speed):
    return next(row["hako_time_sec"] for row in rows if row["speed_m_s"] >= speed)


def main() -> int:
    # Saturated acceleration mode: one large positive command takes the
    # integrated speed target directly to the vehicle limit.  The measured
    # rise time is therefore the model/actuator response, not a command ramp.
    acceleration = run("acceleration", lambda _t, _d, _v, _c, _s: (46.5, 0.0), 18.0)

    def brake_controller(t, _data, speed, _commanded, _steer):
        # One large negative acceleration command clamps the integrated speed
        # target to zero at 10 s. Reverse is disabled, matching the public API.
        return (46.5 if t < 10.0 else 0.0), 0.0

    braking = run("braking", brake_controller, 16.0)
    hold = run("hold-80", lambda _t, _d, _v, _c, _s: (22.222, 0.0), 14.0)

    def lane_controller(t, data, speed, _commanded, _steer):
        target_speed = 33.333
        if t < 15.0:
            return target_speed, 0.0
        horizon = 4.0
        tau = min(horizon, t - 15.0)
        desired_y = 1.75 * (1.0 - math.cos(math.pi * tau / horizon))
        desired_vy = 1.75 * math.pi / horizon * math.sin(math.pi * tau / horizon)
        desired_ay = 1.75 * (math.pi / horizon) ** 2 * math.cos(math.pi * tau / horizon)
        y = float(data.qpos[1])
        vy = float(data.qvel[1])
        lateral = desired_ay + 4.81 * (desired_y - y) + 3.1 * (desired_vy - vy)
        delta = math.atan2(2.6 * lateral, max(speed * speed, 25.0))
        return target_speed, max(-0.025, min(0.025, delta))

    lane = run("lane-change", lane_controller, 20.0)
    t100 = first_time(acceleration, 100 / 3.6)
    max_speed = max(row["speed_m_s"] for row in acceleration)
    peak = max(row["speed_m_s"] for row in braking)
    stopped = next(row["hako_time_sec"] for row in braking if row["hako_time_sec"] > 10.0 and row["speed_m_s"] <= 0.5)
    brake_start = 10.0
    mean_decel = peak / (stopped - brake_start)
    hold_values = [row["speed_m_s"] for row in hold if row["hako_time_sec"] >= 10.0]
    lane_values = [row for row in lane if 15.0 <= row["hako_time_sec"] <= 19.2]
    max_lateral_accel = max(abs(row["lateral_acceleration_m_s2"]) for row in lane_values)
    summary = {
        "zero_to_100_kmh_sec": t100,
        "maximum_speed_kmh": max_speed * 3.6,
        "braking_mean_deceleration_m_s2": mean_decel,
        "hold_80_spread_kmh": (max(hold_values) - min(hold_values)) * 3.6,
        "lane_change_lateral_m": lane_values[-1]["y_m"] - lane_values[0]["y_m"],
        "lane_change_peak_lateral_acceleration_m_s2": max_lateral_accel,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    failures = []
    if not 7.7 <= t100 <= 14.3: failures.append("0-100 km/h")
    if summary["maximum_speed_kmh"] < 150: failures.append("maximum speed")
    if not 7 <= mean_decel <= 8.5: failures.append("braking")
    if summary["hold_80_spread_kmh"] > 2: failures.append("80 km/h hold")
    if not 3.0 <= abs(summary["lane_change_lateral_m"]) <= 4.0: failures.append("lane displacement")
    if max_lateral_accel > 3: failures.append("lane lateral acceleration")
    if failures:
        print("FAILED: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
