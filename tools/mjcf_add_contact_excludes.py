#!/usr/bin/env python3

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from path_utils import infer_generated_dir


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def load_yaml_config(config_file: Path) -> list[dict]:
    with config_file.open("r", encoding="utf-8") as file_obj:
        config = yaml.safe_load(file_obj)

    if not isinstance(config, dict):
        fail("Contact exclude config root must be a mapping.")

    excludes = config.get("excludes")

    if not isinstance(excludes, list) or not excludes:
        fail(
            "Contact exclude config must contain "
            "a non-empty 'excludes' list."
        )

    normalized: list[dict] = []

    for index, exclude in enumerate(excludes):
        if not isinstance(exclude, dict):
            fail(
                f"Contact exclude entry #{index} "
                "must be a mapping."
            )

        body1 = exclude.get("body1")
        body2 = exclude.get("body2")

        if not isinstance(body1, str) or not body1.strip():
            fail(
                f"Contact exclude entry #{index} "
                "must define a non-empty 'body1'."
            )

        if not isinstance(body2, str) or not body2.strip():
            fail(
                f"Contact exclude entry #{index} "
                "must define a non-empty 'body2'."
            )

        body1 = body1.strip()
        body2 = body2.strip()

        if body1 == body2:
            fail(
                f"Contact exclude entry #{index} "
                f"references the same body twice: '{body1}'."
            )

        normalized.append(
            {
                "body1": body1,
                "body2": body2,
            }
        )

    return normalized


def build_output_path(
    input_file: Path,
    output_arg: str | None,
) -> Path:
    if output_arg:
        return Path(output_arg)

    generated_dir = infer_generated_dir(input_file)

    output_name = (
        f"{input_file.stem}.contact"
        f"{input_file.suffix}"
    )

    if generated_dir is None:
        return input_file.with_name(output_name)

    return generated_dir / output_name


def find_body_names(root: ET.Element) -> set[str]:
    return {
        body.get("name")
        for body in root.findall(".//body")
        if body.get("name")
    }


def normalize_pair(
    body1: str,
    body2: str,
) -> tuple[str, str]:
    """
    Normalize a body pair so that:

      (body1, body2)

    and:

      (body2, body1)

    are treated as the same exclusion.
    """

    return tuple(
        sorted(
            (
                body1,
                body2,
            )
        )
    )


def find_existing_excludes(
    contact_element: ET.Element,
) -> set[tuple[str, str]]:
    existing: set[tuple[str, str]] = set()

    for exclude in contact_element.findall("exclude"):
        body1 = exclude.get("body1")
        body2 = exclude.get("body2")

        if not body1 or not body2:
            continue

        existing.add(
            normalize_pair(
                body1,
                body2,
            )
        )

    return existing


def apply_contact_excludes(
    mjcf_file: Path,
    config_file: Path,
    output_file: Path,
) -> None:
    try:
        tree = ET.parse(mjcf_file)
    except ET.ParseError as exc:
        fail(
            f"Failed to parse MJCF file "
            f"'{mjcf_file}': {exc}"
        )

    root = tree.getroot()

    excludes_config = load_yaml_config(
        config_file
    )

    body_names = find_body_names(root)

    #
    # Validate that all configured body names exist.
    #
    missing_bodies: set[str] = set()

    for exclude in excludes_config:
        body1 = exclude["body1"]
        body2 = exclude["body2"]

        if body1 not in body_names:
            missing_bodies.add(body1)

        if body2 not in body_names:
            missing_bodies.add(body2)

    if missing_bodies:
        fail(
            "Contact exclude config references "
            "unknown bodies: "
            + ", ".join(
                sorted(missing_bodies)
            )
        )

    #
    # Reuse an existing <contact> element if present.
    #
    contact_element = root.find("contact")

    if contact_element is None:
        contact_element = ET.SubElement(
            root,
            "contact",
        )

    existing_excludes = find_existing_excludes(
        contact_element
    )

    added_count = 0
    skipped_count = 0

    for exclude_config in excludes_config:
        body1 = exclude_config["body1"]
        body2 = exclude_config["body2"]

        normalized_pair = normalize_pair(
            body1,
            body2,
        )

        if normalized_pair in existing_excludes:
            print(
                "Skipping existing contact exclude: "
                f"{body1} <-> {body2}"
            )

            skipped_count += 1
            continue

        exclude_element = ET.SubElement(
            contact_element,
            "exclude",
        )

        exclude_element.set(
            "body1",
            body1,
        )

        exclude_element.set(
            "body2",
            body2,
        )

        existing_excludes.add(
            normalized_pair
        )

        added_count += 1

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    ET.indent(tree)

    tree.write(
        output_file,
        encoding="utf-8",
        xml_declaration=False,
    )

    print(
        f"Applied {added_count} contact exclude(s) "
        f"from {config_file} -> {output_file}"
    )

    if skipped_count > 0:
        print(
            f"Skipped {skipped_count} "
            "existing contact exclude(s)."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Add MuJoCo contact exclude definitions "
            "to an MJCF XML model from a YAML configuration."
        )
    )

    parser.add_argument(
        "input",
        help="Path to the input MJCF XML file.",
    )

    parser.add_argument(
        "config",
        help=(
            "Path to the contact exclude "
            "YAML configuration file."
        ),
    )

    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Path to the output MJCF XML file. "
            "Defaults to "
            "bodies/{name}/generated/{stem}.contact.xml "
            "when the input is under bodies/{name}/."
        ),
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    config_file = Path(args.config)

    if not input_file.is_file():
        fail(
            f"Input file not found at "
            f"{input_file}"
        )

    if not config_file.is_file():
        fail(
            f"Config file not found at "
            f"{config_file}"
        )

    output_file = build_output_path(
        input_file,
        args.output,
    )

    apply_contact_excludes(
        input_file,
        config_file,
        output_file,
    )


if __name__ == "__main__":
    main()