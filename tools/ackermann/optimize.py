#!/usr/bin/env python3

"""Search Ackermann MJCF parameters with Optuna and the shared validator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

import optuna
import yaml

import validate as ackermann_validate


REPO_ROOT = Path(__file__).resolve().parents[2]


class OptimizationError(RuntimeError):
    pass


def mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise OptimizationError(f"{label} must be a mapping")
    return value


def sequence(value: object, label: str) -> list:
    if not isinstance(value, list) or not value:
        raise OptimizationError(f"{label} must be a non-empty list")
    return value


def load_yaml(path: Path, label: str) -> dict:
    if not path.is_file():
        raise OptimizationError(f"{label} not found: {path}")
    return mapping(yaml.safe_load(path.read_text(encoding="utf-8")), label)


def suggest(trial: optuna.Trial, name: str, spec: dict) -> float | int:
    distribution = str(spec.get("distribution", "float"))
    low = spec.get("low")
    high = spec.get("high")
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        raise OptimizationError(f"parameters.{name} requires numeric low/high")
    if float(low) >= float(high):
        raise OptimizationError(f"parameters.{name}.low must be below high")
    log = bool(spec.get("log", False))
    step = spec.get("step")
    if distribution == "float":
        if step is not None and log:
            raise OptimizationError(f"parameters.{name} cannot combine step and log")
        return trial.suggest_float(
            name,
            float(low),
            float(high),
            step=float(step) if step is not None else None,
            log=log,
        )
    if distribution == "int":
        return trial.suggest_int(
            name,
            int(low),
            int(high),
            step=int(step) if step is not None else 1,
            log=log,
        )
    raise OptimizationError(f"parameters.{name}.distribution must be float or int")


def apply_candidate(source_model: Path, output_model: Path, config: dict, values: dict) -> list[dict]:
    tree = ET.parse(source_model)
    root = tree.getroot()
    applied: list[dict] = []
    parameters = mapping(config.get("parameters"), "parameters")
    for parameter_name, raw_spec in parameters.items():
        spec = mapping(raw_spec, f"parameters.{parameter_name}")
        targets = sequence(spec.get("targets"), f"parameters.{parameter_name}.targets")
        for index, raw_target in enumerate(targets):
            target = mapping(raw_target, f"parameters.{parameter_name}.targets[{index}]")
            kind = str(target.get("kind", ""))
            names = sequence(target.get("names"), f"parameters.{parameter_name}.targets[{index}].names")
            attribute = str(target.get("attribute", ""))
            if kind not in {"actuator", "joint"} or not attribute:
                raise OptimizationError("candidate targets require kind=actuator|joint and attribute")
            if kind == "actuator":
                container = root.find("actuator")
                candidates = list(container) if container is not None else []
            else:
                candidates = root.findall(".//joint")
            by_name = {element.get("name"): element for element in candidates if element.get("name")}
            missing = sorted(str(name) for name in names if str(name) not in by_name)
            if missing:
                raise OptimizationError(
                    f"{parameter_name} references missing {kind}(s): " + ", ".join(missing)
                )
            for raw_name in names:
                element_name = str(raw_name)
                element = by_name[element_name]
                previous = element.get(attribute)
                element.set(attribute, str(values[parameter_name]))
                applied.append(
                    {
                        "parameter": parameter_name,
                        "kind": kind,
                        "name": element_name,
                        "attribute": attribute,
                        "before": previous,
                        "after": values[parameter_name],
                    }
                )
    # Trial files live outside the canonical generated directory. Resolve only
    # their existing relative resources so MuJoCo loads the evidence model
    # without copying or modifying third-party source meshes.
    for element in root.iter():
        resource = element.get("file")
        if resource and not Path(resource).is_absolute():
            element.set("file", str((source_model.parent / resource).resolve()))
    output_model.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree)
    tree.write(output_model, encoding="utf-8", xml_declaration=False)
    return applied


def validate_config(config: dict) -> None:
    if config.get("version") != 1:
        raise OptimizationError("Only tuning Recipe version 1 is supported")
    parameters = mapping(config.get("parameters"), "parameters")
    baseline = mapping(config.get("baseline"), "baseline")
    if set(parameters) != set(baseline):
        raise OptimizationError("baseline must define exactly every search parameter")
    # Exercise schema and ranges before starting a study.
    for name, raw_spec in parameters.items():
        spec = mapping(raw_spec, f"parameters.{name}")
        sequence(spec.get("targets"), f"parameters.{name}.targets")
        value = baseline[name]
        low, high = spec.get("low"), spec.get("high")
        if not isinstance(value, (int, float)) or not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
            raise OptimizationError(f"baseline/range for {name} must be numeric")
        if not float(low) <= float(value) <= float(high):
            raise OptimizationError(f"baseline.{name} is outside its search range")


def optimize(body: str, model_path: Path, config_path: Path, output_dir: Path, trials_override: int | None) -> dict:
    tuning = load_yaml(config_path, "tuning Recipe")
    validate_config(tuning)
    _, validation_contract = ackermann_validate.load_contract(body)
    study_config = mapping(tuning.get("study"), "study")
    trials = trials_override or int(study_config.get("trials", 20))
    seed = int(study_config.get("seed", 20260830))
    penalty = float(study_config.get("hard_failure_penalty", 100.0))
    if trials < 1 or penalty <= 0.0:
        raise OptimizationError("study trials and hard_failure_penalty must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = output_dir / "trials"
    reports_dir.mkdir(parents=True, exist_ok=True)
    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    baseline = mapping(tuning.get("baseline"), "baseline")
    study.enqueue_trial(baseline, user_attrs={"candidate_kind": "baseline"})
    trial_records: list[dict] = []

    with tempfile.TemporaryDirectory(prefix=f"hakoniwa-ackermann-optuna-{body}-") as temporary:
        temporary_root = Path(temporary)

        def objective(trial: optuna.Trial) -> float:
            values = {
                name: suggest(trial, name, mapping(spec, f"parameters.{name}"))
                for name, spec in mapping(tuning.get("parameters"), "parameters").items()
            }
            candidate_model = temporary_root / f"trial-{trial.number:04d}.xml"
            applied = apply_candidate(model_path, candidate_model, tuning, values)
            try:
                report = ackermann_validate.validate(candidate_model, validation_contract)
                loss = float(report["evaluation"]["objective_loss"])
                hard_failures = len(report["failures"])
                objective_value = loss + penalty * hard_failures
            except Exception as error:  # MuJoCo-invalid candidates are valid failed trials.
                report = {
                    "schema_version": 1,
                    "status": "error",
                    "failures": [f"{type(error).__name__}: {error}"],
                    "evaluation": {"objective_loss": penalty},
                }
                hard_failures = 1
                objective_value = penalty * 2.0
            trial.set_user_attr("hard_failure_count", hard_failures)
            trial.set_user_attr("quality_score_0_100", report.get("evaluation", {}).get("quality_score_0_100"))
            record = {
                "trial": trial.number,
                "objective": objective_value,
                "parameters": values,
                "applied": applied,
                "report": report,
            }
            (reports_dir / f"trial-{trial.number:04d}.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8"
            )
            trial_records.append(record)
            return objective_value

        study.optimize(objective, n_trials=trials, show_progress_bar=False)

    passing = [record for record in trial_records if not record["report"].get("failures")]
    if not passing:
        raise OptimizationError("no candidate passed the hard acceptance checks")
    best = min(passing, key=lambda record: record["objective"])
    # The study best should also be passing because each hard failure carries a large penalty,
    # but select explicitly from passing records so the safety boundary is unambiguous.
    best_model = output_dir / "best-model.xml"
    applied = apply_candidate(model_path, best_model, tuning, best["parameters"])
    best_candidate = {
        "schema_version": 1,
        "body": body,
        "source_model": str(model_path),
        "source_tuning_recipe": str(config_path),
        "promote_automatically": False,
        "objective": best["objective"],
        "quality_score_0_100": best["report"]["evaluation"]["quality_score_0_100"],
        "parameters": best["parameters"],
        "applied": applied,
        "instruction": "Review this candidate, then manually copy accepted values to the source-of-truth YAML and rerun Forge verification.",
    }
    (output_dir / "best-candidate.yaml").write_text(
        yaml.safe_dump(best_candidate, sort_keys=False), encoding="utf-8"
    )
    shutil.copy2(reports_dir / f"trial-{best['trial']:04d}.json", output_dir / "best-report.json")
    summary = {
        "schema_version": 1,
        "body": body,
        "seed": seed,
        "trials": trials,
        "passing_trials": len(passing),
        "baseline": trial_records[0],
        "best": best,
        "all_trials": [
            {
                "trial": record["trial"],
                "objective": record["objective"],
                "parameters": record["parameters"],
                "status": record["report"].get("status"),
                "hard_failure_count": len(record["report"].get("failures", [])),
            }
            for record in trial_records
        ],
    }
    (output_dir / "study.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("body", help="Body name under bodies/")
    parser.add_argument("--model", type=Path, help="Override generated minimal-world MJCF")
    parser.add_argument("--config", type=Path, help="Override tuning Recipe")
    parser.add_argument("--output", type=Path, required=True, help="Evidence directory (not source-of-truth config)")
    parser.add_argument("--trials", type=int, help="Override Recipe trial count")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    recipe_path, _ = ackermann_validate.load_contract(args.body)
    model = args.model or ackermann_validate.default_model_path(args.body, recipe_path)
    config = args.config or recipe_path.parent / "ackermann-tuning.yaml"
    summary = optimize(args.body, model.resolve(), config.resolve(), args.output.resolve(), args.trials)
    print(
        f"Ackermann optimization complete: {args.body} "
        f"passing={summary['passing_trials']}/{summary['trials']} "
        f"baseline={summary['baseline']['objective']:.6f} "
        f"best={summary['best']['objective']:.6f}"
    )
    print(f"Review candidate: {args.output.resolve() / 'best-candidate.yaml'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OptimizationError, ackermann_validate.ValidationError, OSError, ValueError, ET.ParseError, yaml.YAMLError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
