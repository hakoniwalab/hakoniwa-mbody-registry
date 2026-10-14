#!/usr/bin/env python3
"""Run deterministic truck highway profiles and write Hakoniwa-time CSV evidence."""

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

BODY = ROOT / "bodies/hakoniwa_truck"
CONTRACT = yaml.safe_load((BODY / "config/ackermann-forge.yaml").read_text(encoding="utf-8"))["validation"]
MODEL = BODY / "generated/model.minimal_world.xml"
OUT = BODY / "validation/results"
SAMPLE_SEC = 0.02


def forward_speed(data, dof, yaw):
    return math.cos(yaw) * float(data.qvel[dof]) + math.sin(yaw) * float(data.qvel[dof + 1])


def run(name, controller, duration):
    harness = Harness(MODEL, CONTRACT)
    data = mujoco.MjData(harness.model)
    mujoco.mj_forward(harness.model, data)
    for _ in range(math.ceil(1.0 / harness.model.opt.timestep)):
        mujoco.mj_step(harness.model, data)
    dof = int(harness.model.jnt_dofadr[harness.freejoint])
    rows, next_sample = [], 0.0
    commanded_speed = commanded_steer = previous_speed = previous_world_vy = 0.0
    while data.time < duration + 1.0:
        elapsed = data.time - 1.0
        state = harness.state(data)
        yaw = float(state["yaw_rad"])
        speed = forward_speed(data, dof, yaw)
        commanded_speed, target_steer = controller(max(0.0, elapsed), data, speed, commanded_speed, commanded_steer)
        max_step = 0.3 * harness.model.opt.timestep
        commanded_steer += max(-max_step, min(max_step, target_steer - commanded_steer))
        for key, value in ackermann_targets(commanded_speed, commanded_steer, harness.geometry).items():
            data.ctrl[harness.actuator_ids[key]] = value
        mujoco.mj_step(harness.model, data)
        if elapsed + 1e-9 >= next_sample:
            position = state["position_m"]
            world_vy = float(data.qvel[dof + 1])
            rows.append({
                "hako_time_sec": round(max(0.0, elapsed), 6),
                "x_m": position[0], "y_m": position[1], "speed_m_s": speed,
                "acceleration_m_s2": (speed - previous_speed) / SAMPLE_SEC if rows else 0.0,
                "lateral_acceleration_m_s2": (world_vy - previous_world_vy) / SAMPLE_SEC if rows else 0.0,
                "steering_rad": commanded_steer, "commanded_speed_m_s": commanded_speed,
            })
            previous_speed, previous_world_vy = speed, world_vy
            next_sample += SAMPLE_SEC
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def first_time(rows, speed):
    return next(row["hako_time_sec"] for row in rows if row["speed_m_s"] >= speed)


def main():
    # Step targets deliberately exceed the required speed. This measures the
    # truck/actuator response rather than reproducing a command ramp.
    acceleration = run("acceleration", lambda _t, _d, _v, _c, _s: (30.0, 0.0), 38.0)

    def brake(t, _data, _speed, _commanded, _steer):
        return (22.222 if t < 28.0 else 0.0), 0.0

    braking = run("braking", brake, 36.0)
    hold = run("hold-80", lambda _t, _d, _v, _c, _s: (22.222, 0.0), 34.0)

    def lane_controller(t, data, speed, _commanded, _steer):
        target_speed = 22.222
        if t < 26.0:
            return target_speed, 0.0
        horizon = 4.0
        tau = min(horizon, t - 26.0)
        desired_y = 1.75 * (1.0 - math.cos(math.pi * tau / horizon))
        desired_vy = 1.75 * math.pi / horizon * math.sin(math.pi * tau / horizon)
        desired_ay = 1.75 * (math.pi / horizon) ** 2 * math.cos(math.pi * tau / horizon)
        y, vy = float(data.qpos[1]), float(data.qvel[1])
        lateral = desired_ay + 1.2 * (desired_y - y) + 1.6 * (desired_vy - vy)
        delta = math.atan2(4.3 * lateral, max(speed * speed, 25.0))
        return target_speed, max(-0.018, min(0.018, delta))

    lane = run("lane-change", lane_controller, 31.2)
    t80 = first_time(acceleration, 80 / 3.6)
    max_speed = max(row["speed_m_s"] for row in acceleration)
    peak = max(row["speed_m_s"] for row in braking)
    stopped = next(row["hako_time_sec"] for row in braking if row["hako_time_sec"] > 28 and row["speed_m_s"] <= 0.5)
    mean_decel = peak / (stopped - 28.0)
    hold_values = [row["speed_m_s"] for row in hold if row["hako_time_sec"] >= 28.0]
    lane_values = [row for row in lane if 26.0 <= row["hako_time_sec"] <= 31.0]
    # The primitive tire contact has millisecond stick/slip impulses. Report
    # the vehicle-body lateral acceleration over a 0.4 s engineering window,
    # rather than treating those solver impulses as chassis acceleration.
    half_window = round(0.4 / SAMPLE_SEC)
    smoothed_lateral_accel = []
    for index in range(half_window, len(lane) - half_window):
        if 26.0 <= lane[index]["hako_time_sec"] <= 31.0:
            before = lane[index - half_window]["y_m"]
            center = lane[index]["y_m"]
            after = lane[index + half_window]["y_m"]
            smoothed_lateral_accel.append(abs((after - 2 * center + before) / (0.4 ** 2)))
    summary = {
        "zero_to_80_kmh_sec": t80,
        "maximum_speed_kmh": max_speed * 3.6,
        "braking_mean_deceleration_m_s2": mean_decel,
        "braking_stop_time_sec": stopped - 28.0,
        "post_stop_max_commanded_speed_m_s": max(
            abs(row["commanded_speed_m_s"]) for row in braking if row["hako_time_sec"] >= stopped
        ),
        "post_stop_max_vehicle_speed_m_s": max(
            abs(row["speed_m_s"]) for row in braking if row["hako_time_sec"] >= stopped + 0.5
        ),
        "hold_80_spread_kmh": (max(hold_values) - min(hold_values)) * 3.6,
        "lane_change_lateral_m": lane_values[-1]["y_m"] - lane_values[0]["y_m"],
        "lane_change_peak_lateral_acceleration_m_s2": max(smoothed_lateral_accel),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    failures = []
    if not 17.5 <= t80 <= 32.5: failures.append("0-80 km/h")
    if summary["maximum_speed_kmh"] < 100: failures.append("maximum speed")
    if not 5 <= mean_decel <= 6: failures.append("braking")
    if summary["post_stop_max_commanded_speed_m_s"] > 1e-9: failures.append("post-stop command")
    if summary["post_stop_max_vehicle_speed_m_s"] > 0.5: failures.append("post-stop vehicle speed")
    if summary["hold_80_spread_kmh"] > 2: failures.append("80 km/h hold")
    if not 3.0 <= abs(summary["lane_change_lateral_m"]) <= 4.0: failures.append("lane displacement")
    if summary["lane_change_peak_lateral_acceleration_m_s2"] > 2: failures.append("lane lateral acceleration")
    if failures:
        print("FAILED: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
