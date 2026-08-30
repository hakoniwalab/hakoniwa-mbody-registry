#!/usr/bin/env python3

"""Run model-independent, headless acceptance tests for an Ackermann body."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time

import mujoco
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


class ValidationError(RuntimeError):
    pass


def mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a mapping")
    return value


def number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError(f"{label} must be finite")
    return result


def name_id(model: mujoco.MjModel, object_type: mujoco.mjtObj, name: str) -> int:
    result = mujoco.mj_name2id(model, object_type, name)
    if result < 0:
        raise ValidationError(f"model has no {object_type.name}: {name}")
    return result


def load_contract(body: str) -> tuple[Path, dict]:
    path = REPO_ROOT / "bodies" / body / "config" / "ackermann-forge.yaml"
    if not path.is_file():
        raise ValidationError(f"Ackermann Forge Recipe not found: {path}")
    recipe = mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "Recipe")
    contract = mapping(recipe.get("validation"), "validation")
    return path, contract


def default_model_path(body: str, recipe_path: Path) -> Path:
    recipe = mapping(yaml.safe_load(recipe_path.read_text(encoding="utf-8")), "Recipe")
    source = mapping(recipe.get("source"), "source")
    output = mapping(source.get("output"), "source.output")
    basename = str(output.get("basename", body))
    return recipe_path.parent.parent / "generated" / f"{basename}.minimal_world.xml"


def ackermann_targets(
    linear_velocity: float,
    center_steering: float,
    geometry: dict,
) -> dict[str, float]:
    wheelbase = number(geometry.get("wheelbase_m"), "geometry.wheelbase_m")
    track = number(geometry.get("track_width_m"), "geometry.track_width_m")
    radius = number(geometry.get("wheel_radius_m"), "geometry.wheel_radius_m")
    max_steer = number(
        geometry.get("max_center_steering_rad"),
        "geometry.max_center_steering_rad",
    )
    max_wheel = number(
        geometry.get("max_wheel_angular_velocity_rad_s"),
        "geometry.max_wheel_angular_velocity_rad_s",
    )
    if min(wheelbase, track, radius, max_steer, max_wheel) <= 0.0:
        raise ValidationError("all Ackermann geometry values must be positive")

    delta = max(-max_steer, min(max_steer, center_steering))
    base_wheel = max(-max_wheel, min(max_wheel, linear_velocity / radius))
    result = {
        "steering_left": 0.0,
        "steering_right": 0.0,
        "drive_left": base_wheel,
        "drive_right": base_wheel,
    }
    if abs(delta) < 1.0e-9:
        return result

    turn_radius = wheelbase / math.tan(delta)
    left = math.atan2(wheelbase, turn_radius - track / 2.0)
    right = math.atan2(wheelbase, turn_radius + track / 2.0)
    if delta < 0.0:
        if left > 0.0:
            left -= math.pi
        if right > 0.0:
            right -= math.pi
    result["steering_left"] = max(-max_steer, min(max_steer, left))
    result["steering_right"] = max(-max_steer, min(max_steer, right))
    result["drive_left"] = max(
        -max_wheel,
        min(max_wheel, base_wheel * (1.0 - track / (2.0 * turn_radius))),
    )
    result["drive_right"] = max(
        -max_wheel,
        min(max_wheel, base_wheel * (1.0 + track / (2.0 * turn_radius))),
    )
    return result


def yaw_from_qpos(qpos: list[float]) -> float:
    w, x, y, z = qpos
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


class Harness:
    def __init__(self, model_path: Path, contract: dict):
        if not model_path.is_file():
            raise ValidationError(f"MJCF not found: {model_path}")
        self.model_path = model_path
        self.model = mujoco.MjModel.from_xml_path(str(model_path))
        self.interface = mapping(contract.get("interface"), "validation.interface")
        self.geometry = mapping(contract.get("geometry"), "validation.geometry")
        self.scenarios = mapping(contract.get("scenarios"), "validation.scenarios")
        self.tolerances = mapping(contract.get("tolerances"), "validation.tolerances")

        freejoint_name = str(self.interface.get("base_freejoint", ""))
        self.freejoint = name_id(
            self.model, mujoco.mjtObj.mjOBJ_JOINT, freejoint_name
        )
        self.base_qpos = int(self.model.jnt_qposadr[self.freejoint])

        joint_names = mapping(self.interface.get("joints"), "validation.interface.joints")
        actuator_names = mapping(
            self.interface.get("actuators"), "validation.interface.actuators"
        )
        expected_keys = {"steering_left", "steering_right", "drive_left", "drive_right"}
        if set(joint_names) != expected_keys or set(actuator_names) != expected_keys:
            raise ValidationError(
                "interface joints and actuators must define exactly: "
                + ", ".join(sorted(expected_keys))
            )
        self.joint_ids = {
            key: name_id(self.model, mujoco.mjtObj.mjOBJ_JOINT, str(value))
            for key, value in joint_names.items()
        }
        self.actuator_ids = {
            key: name_id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, str(value))
            for key, value in actuator_names.items()
        }
        self.joint_qpos = {
            key: int(self.model.jnt_qposadr[joint_id])
            for key, joint_id in self.joint_ids.items()
        }
        self.joint_qvel = {
            key: int(self.model.jnt_dofadr[joint_id])
            for key, joint_id in self.joint_ids.items()
        }

    def state(self, data: mujoco.MjData) -> dict[str, float | list[float]]:
        position = [float(value) for value in data.qpos[self.base_qpos : self.base_qpos + 3]]
        quaternion = [
            float(value) for value in data.qpos[self.base_qpos + 3 : self.base_qpos + 7]
        ]
        return {
            "position_m": position,
            "yaw_rad": yaw_from_qpos(quaternion),
            "steering_rad": [
                float(data.qpos[self.joint_qpos["steering_left"]]),
                float(data.qpos[self.joint_qpos["steering_right"]]),
            ],
            "drive_velocity_rad_s": [
                float(data.qvel[self.joint_qvel["drive_left"]]),
                float(data.qvel[self.joint_qvel["drive_right"]]),
            ],
        }

    def run(self, duration_sec: float, targets: dict[str, float]) -> tuple[dict, float]:
        data = mujoco.MjData(self.model)
        mujoco.mj_forward(self.model, data)
        settle_sec = number(self.scenarios.get("settle_sec", 1.0), "scenarios.settle_sec")
        settle_steps = max(1, math.ceil(settle_sec / self.model.opt.timestep))
        for _ in range(settle_steps):
            mujoco.mj_step(self.model, data)
        initial = self.state(data)

        for key, value in targets.items():
            data.ctrl[self.actuator_ids[key]] = value
        steps = max(1, math.ceil(duration_sec / self.model.opt.timestep))
        previous_position = data.qpos[self.base_qpos : self.base_qpos + 3].copy()
        max_step_translation = 0.0
        finite = True
        started = time.perf_counter()
        for _ in range(steps):
            mujoco.mj_step(self.model, data)
            position = data.qpos[self.base_qpos : self.base_qpos + 3]
            max_step_translation = max(
                max_step_translation,
                math.sqrt(sum(float(position[i] - previous_position[i]) ** 2 for i in range(3))),
            )
            finite = finite and all(math.isfinite(float(value)) for value in data.qpos)
            previous_position[:] = position
        wall_sec = time.perf_counter() - started
        final = self.state(data)
        initial_position = initial["position_m"]
        final_position = final["position_m"]
        assert isinstance(initial_position, list) and isinstance(final_position, list)
        result = {
            "duration_sec": steps * self.model.opt.timestep,
            "wall_sec": wall_sec,
            "rtf": steps * self.model.opt.timestep / max(wall_sec, 1.0e-12),
            "max_step_translation_m": max_step_translation,
            "finite_state": finite,
            "initial": initial,
            "final": final,
            "delta": {
                "x_m": final_position[0] - initial_position[0],
                "y_m": final_position[1] - initial_position[1],
                "z_m": final_position[2] - initial_position[2],
                "yaw_rad": float(final["yaw_rad"]) - float(initial["yaw_rad"]),
            },
            "targets": targets,
        }
        return result, wall_sec


def assert_limit(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def rms(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values) / max(len(values), 1))


def weighted_score(
    raw_terms: dict[str, float],
    normalizers: dict[str, float],
    weights: dict,
) -> tuple[float, float, dict[str, float]]:
    unknown = sorted(set(weights) - set(raw_terms))
    if unknown:
        raise ValidationError("evaluation.score.weights has unknown metric(s): " + ", ".join(unknown))
    if not weights:
        raise ValidationError("evaluation.score.weights must not be empty")
    parsed_weights = {key: number(value, f"evaluation.score.weights.{key}") for key, value in weights.items()}
    if any(value < 0.0 for value in parsed_weights.values()) or sum(parsed_weights.values()) <= 0.0:
        raise ValidationError("score weights must be non-negative and have a positive sum")
    normalized = {
        key: raw_terms[key] / max(normalizers[key], 1.0e-12)
        for key in parsed_weights
    }
    loss = sum(normalized[key] * parsed_weights[key] for key in parsed_weights) / sum(parsed_weights.values())
    return loss, 100.0 / (1.0 + loss), normalized


def validate(model_path: Path, contract: dict) -> dict:
    harness = Harness(model_path, contract)
    failures: list[str] = []

    idle_duration = number(harness.scenarios.get("idle_sec", 3.0), "scenarios.idle_sec")
    idle, _ = harness.run(idle_duration, ackermann_targets(0.0, 0.0, harness.geometry))
    idle_delta = idle["delta"]
    assert_limit(
        math.hypot(idle_delta["x_m"], idle_delta["y_m"])
        <= number(harness.tolerances.get("idle_horizontal_drift_m"), "tolerances.idle_horizontal_drift_m"),
        "idle horizontal drift exceeded tolerance",
        failures,
    )
    assert_limit(
        abs(idle_delta["z_m"])
        <= number(harness.tolerances.get("idle_vertical_drift_m"), "tolerances.idle_vertical_drift_m"),
        "idle vertical drift exceeded tolerance",
        failures,
    )

    straight_cfg = mapping(harness.scenarios.get("straight"), "scenarios.straight")
    straight_speed = number(straight_cfg.get("speed_m_s"), "scenarios.straight.speed_m_s")
    straight_duration = number(straight_cfg.get("duration_sec"), "scenarios.straight.duration_sec")
    straight, _ = harness.run(
        straight_duration,
        ackermann_targets(straight_speed, 0.0, harness.geometry),
    )
    straight_delta = straight["delta"]
    assert_limit(
        straight_delta["x_m"] >= number(harness.tolerances.get("straight_min_forward_m"), "tolerances.straight_min_forward_m"),
        "straight-drive forward progress was too small",
        failures,
    )
    assert_limit(
        abs(straight_delta["y_m"]) <= number(harness.tolerances.get("straight_max_lateral_m"), "tolerances.straight_max_lateral_m"),
        "straight-drive lateral drift exceeded tolerance",
        failures,
    )
    assert_limit(
        abs(straight_delta["yaw_rad"]) <= number(harness.tolerances.get("straight_max_yaw_rad"), "tolerances.straight_max_yaw_rad"),
        "straight-drive yaw drift exceeded tolerance",
        failures,
    )

    turn_cfg = mapping(harness.scenarios.get("turn"), "scenarios.turn")
    turn_speed = number(turn_cfg.get("speed_m_s"), "scenarios.turn.speed_m_s")
    turn_steer = number(turn_cfg.get("center_steering_rad"), "scenarios.turn.center_steering_rad")
    turn_duration = number(turn_cfg.get("duration_sec"), "scenarios.turn.duration_sec")
    turns: dict[str, dict] = {}
    steering_error_limit = number(harness.tolerances.get("steering_tracking_error_rad"), "tolerances.steering_tracking_error_rad")
    drive_error_limit = number(harness.tolerances.get("drive_tracking_error_rad_s"), "tolerances.drive_tracking_error_rad_s")
    for label, sign in (("left", 1.0), ("right", -1.0)):
        targets = ackermann_targets(turn_speed, sign * turn_steer, harness.geometry)
        result, _ = harness.run(turn_duration, targets)
        turns[label] = result
        actual_steer = result["final"]["steering_rad"]
        actual_drive = result["final"]["drive_velocity_rad_s"]
        assert_limit(
            abs(actual_steer[0] - targets["steering_left"]) <= steering_error_limit
            and abs(actual_steer[1] - targets["steering_right"]) <= steering_error_limit,
            f"{label}-turn steering joints did not track Ackermann targets",
            failures,
        )
        assert_limit(
            abs(actual_drive[0] - targets["drive_left"]) <= drive_error_limit
            and abs(actual_drive[1] - targets["drive_right"]) <= drive_error_limit,
            f"{label}-turn rear wheel velocities did not track differential targets",
            failures,
        )
        assert_limit(
            result["delta"]["x_m"] >= number(harness.tolerances.get("turn_min_forward_m"), "tolerances.turn_min_forward_m"),
            f"{label}-turn forward progress was too small",
            failures,
        )
        assert_limit(
            abs(result["delta"]["yaw_rad"]) >= number(harness.tolerances.get("turn_min_abs_yaw_rad"), "tolerances.turn_min_abs_yaw_rad"),
            f"{label}-turn yaw response was too small",
            failures,
        )

    left_yaw = turns["left"]["delta"]["yaw_rad"]
    right_yaw = turns["right"]["delta"]["yaw_rad"]
    assert_limit(left_yaw * right_yaw < 0.0, "left and right turns did not have opposite yaw signs", failures)
    yaw_symmetry = abs(abs(left_yaw) - abs(right_yaw)) / max(abs(left_yaw), abs(right_yaw), 1.0e-12)
    assert_limit(
        yaw_symmetry <= number(harness.tolerances.get("turn_max_yaw_asymmetry_ratio"), "tolerances.turn_max_yaw_asymmetry_ratio"),
        "left/right turn yaw responses were too asymmetric",
        failures,
    )

    measured_rtfs = [idle["rtf"], straight["rtf"], turns["left"]["rtf"], turns["right"]["rtf"]]
    minimum_rtf = min(measured_rtfs)
    rtf_advisory = number(harness.tolerances.get("rtf_advisory_min", 1.0), "tolerances.rtf_advisory_min")
    required_rtf = number(harness.tolerances.get("rtf_required_min", 0.0), "tolerances.rtf_required_min")
    assert_limit(minimum_rtf >= required_rtf, "headless RTF was below the required minimum", failures)
    max_step_translation = max(
        scenario["max_step_translation_m"]
        for scenario in (idle, straight, turns["left"], turns["right"])
    )
    assert_limit(
        all(scenario["finite_state"] for scenario in (idle, straight, turns["left"], turns["right"])),
        "non-finite MuJoCo state detected",
        failures,
    )
    assert_limit(
        max_step_translation <= number(harness.tolerances.get("max_step_translation_m"), "tolerances.max_step_translation_m"),
        "single-step body displacement indicates an unstable or explosive model",
        failures,
    )

    steering_errors: list[float] = []
    drive_errors: list[float] = []
    for result in turns.values():
        steering_errors.extend(
            [
                result["final"]["steering_rad"][0] - result["targets"]["steering_left"],
                result["final"]["steering_rad"][1] - result["targets"]["steering_right"],
            ]
        )
        drive_errors.extend(
            [
                result["final"]["drive_velocity_rad_s"][0] - result["targets"]["drive_left"],
                result["final"]["drive_velocity_rad_s"][1] - result["targets"]["drive_right"],
            ]
        )
    objective_terms = {
        "idle_horizontal_drift_m": math.hypot(idle_delta["x_m"], idle_delta["y_m"]),
        "straight_lateral_drift_m": abs(straight_delta["y_m"]),
        "straight_yaw_drift_rad": abs(straight_delta["yaw_rad"]),
        "steering_tracking_rmse_rad": rms(steering_errors),
        "drive_tracking_rmse_rad_s": rms(drive_errors),
        "turn_yaw_asymmetry_ratio": yaw_symmetry,
    }
    normalizers = {
        "idle_horizontal_drift_m": number(harness.tolerances.get("idle_horizontal_drift_m"), "tolerances.idle_horizontal_drift_m"),
        "straight_lateral_drift_m": number(harness.tolerances.get("straight_max_lateral_m"), "tolerances.straight_max_lateral_m"),
        "straight_yaw_drift_rad": number(harness.tolerances.get("straight_max_yaw_rad"), "tolerances.straight_max_yaw_rad"),
        "steering_tracking_rmse_rad": steering_error_limit,
        "drive_tracking_rmse_rad_s": drive_error_limit,
        "turn_yaw_asymmetry_ratio": number(harness.tolerances.get("turn_max_yaw_asymmetry_ratio"), "tolerances.turn_max_yaw_asymmetry_ratio"),
    }
    evaluation = mapping(contract.get("evaluation"), "validation.evaluation")
    score_config = mapping(evaluation.get("score"), "validation.evaluation.score")
    if score_config.get("method") != "weighted_tolerance_ratio":
        raise ValidationError("evaluation.score.method must be 'weighted_tolerance_ratio'")
    objective_loss, quality_score, normalized_loss_terms = weighted_score(
        objective_terms,
        normalizers,
        mapping(score_config.get("weights"), "evaluation.score.weights"),
    )
    report = {
        "schema_version": 1,
        "model": str(model_path),
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "metrics": {
            "minimum_headless_rtf": minimum_rtf,
            "rtf_advisory_min": rtf_advisory,
            "rtf_advisory_passed": minimum_rtf >= rtf_advisory,
            "rtf_required_min": required_rtf,
            "max_step_translation_m": max_step_translation,
            "turn_yaw_asymmetry_ratio": yaw_symmetry,
        },
        "evaluation": {
            "method": "weighted_tolerance_ratio",
            "direction": "minimize",
            "objective_loss": objective_loss,
            "quality_score_0_100": quality_score,
            "raw_terms": objective_terms,
            "normalized_loss_terms": normalized_loss_terms,
            "note": "Ranking aid only; hard acceptance failures remain authoritative.",
        },
        "scenarios": {"idle": idle, "straight": straight, **turns},
        "scope": {
            "guarantees": "headless MuJoCo body dynamics and Ackermann actuator response",
            "does_not_guarantee": "Hakoniwa PDU wiring, gamepad mapping, Viewer mutex/render smoothness, or real-vehicle fidelity",
        },
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("body", help="Body name under bodies/")
    parser.add_argument("--model", type=Path, help="Override generated minimal-world MJCF")
    parser.add_argument("--report", type=Path, help="Write detailed JSON metrics")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    recipe_path, contract = load_contract(args.body)
    model_path = args.model or default_model_path(args.body, recipe_path)
    report = validate(model_path.resolve(), contract)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote report: {args.report}")
    metrics = report["metrics"]
    if report["failures"]:
        raise ValidationError(
            "\n  - ".join(
                ["Ackermann dynamic validation failed:", *report["failures"]]
            )
        )
    print(
        f"Ackermann dynamic validation passed: {args.body} "
        f"minimum_rtf={metrics['minimum_headless_rtf']:.2f} "
        f"turn_asymmetry={metrics['turn_yaw_asymmetry_ratio']:.3f} "
        f"quality_score={report['evaluation']['quality_score_0_100']:.1f}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValidationError, OSError, ValueError, yaml.YAMLError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
