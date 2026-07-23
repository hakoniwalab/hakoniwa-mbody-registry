#!/usr/bin/env python3

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

try:
    import yaml
except ModuleNotFoundError:
    print("Error: 'PyYAML' package not found.", file=sys.stderr)
    print("Please install it using: pip install PyYAML", file=sys.stderr)
    sys.exit(1)


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def run_git(args: list[str], cwd: Path, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        fail(f"Git command failed ({' '.join(args)}): {stderr}")


def normalize_fetch_path(raw_path: object) -> str:
    if not isinstance(raw_path, str):
        fail("Every entry in 'files' must be a string.")

    normalized = raw_path.strip().strip("/")
    if not normalized:
        fail("Entries in 'files' must not be empty.")

    path_obj = PurePosixPath(normalized)
    if path_obj.is_absolute() or ".." in path_obj.parts:
        fail(f"Invalid fetch path '{raw_path}': absolute paths and '..' are not allowed.")

    return path_obj.as_posix()


def load_config(
    yaml_file: Path,
) -> tuple[str, str, str, str | None, list[str]]:
    with yaml_file.open("r", encoding="utf-8") as file_obj:
        config = yaml.safe_load(file_obj)

    if not isinstance(config, dict):
        fail("YAML root must be a mapping.")

    name = config.get("name")
    repo = config.get("repo")
    branch = config.get("branch")
    revision = config.get("revision")
    files = config.get("files")

    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        fail("'name' must be a non-empty slug containing only letters, digits, '.', '_' or '-'.")
    if not isinstance(repo, str) or not repo.strip():
        fail("'repo' must be a non-empty string.")
    if not isinstance(branch, str) or not branch.strip():
        fail("'branch' must be a non-empty string.")
    if revision is not None:
        if not isinstance(revision, str) or not revision.strip():
            fail(
                "'revision' must be a non-empty string when specified."
            )
        revision = revision.strip()
    if not isinstance(files, list) or not files:
        fail("'files' must be a non-empty list.")

    normalized_files: list[str] = []
    seen: set[str] = set()
    for item in files:
        normalized = normalize_fetch_path(item)
        if normalized not in seen:
            normalized_files.append(normalized)
            seen.add(normalized)

    return (
        name,
        repo.strip(),
        branch.strip(),
        revision,
        normalized_files,
    )


def copy_fetched_path(source_root: Path, destination_root: Path, relative_path: str) -> None:
    source = source_root / relative_path
    destination = destination_root / relative_path

    if not source.exists():
        fail(f"Requested path '{relative_path}' was not found in the fetched branch.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)


def fetch_robot_sources(yaml_file: Path, output_dir: Path | None = None) -> Path:
    name, repo, branch, revision, files_to_fetch = load_config(yaml_file)

    if output_dir is not None:
        dest_dir = output_dir.resolve()
    else:
        # Default materialization path for committed generated artifacts.
        repo_root = Path(__file__).resolve().parent.parent
        robot_root = repo_root / "bodies" / name
        dest_dir = robot_root / "source"

    print(f"Fetching robot source for: {name}")
    print(f"  - Repo:        {repo}")
    print(f"  - Branch:      {branch}")
    if revision:
        print(f"  - Revision:    {revision}")
    print(f"  - Destination: {dest_dir}")
    print(f"  - Paths:       {', '.join(files_to_fetch)}")

    if dest_dir.exists():
        print(f"  - Cleaning up existing directory: {dest_dir}")
        shutil.rmtree(dest_dir)

    dest_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        print(f"  - Using temporary directory: {tmp_path}")
        run_git(["init", "-q"], cwd=tmp_path)
        run_git(["remote", "add", "origin", repo], cwd=tmp_path)
        run_git(["config", "core.sparseCheckout", "true"], cwd=tmp_path)
        run_git(["sparse-checkout", "init", "--cone"], cwd=tmp_path)
        run_git(["sparse-checkout", "set", *files_to_fetch], cwd=tmp_path)

        if revision:
            print(
                f"  - Fetching revision '{revision}'..."
            )

            run_git(
                [
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    revision,
                ],
                cwd=tmp_path,
                capture_output=True,
            )

            run_git(
                [
                    "checkout",
                    "--detach",
                    "FETCH_HEAD",
                ],
                cwd=tmp_path,
                capture_output=True,
            )

        else:
            print(
                f"  - Pulling files from branch '{branch}'..."
            )

            run_git(
                [
                    "pull",
                    "--depth",
                    "1",
                    "origin",
                    branch,
                ],
                cwd=tmp_path,
                capture_output=True,
            )

        print("  - Copying fetched files to destination...")
        for relative_path in files_to_fetch:
            copy_fetched_path(tmp_path, dest_dir, relative_path)

    print(f"Fetch complete. Files are in {dest_dir}")
    if output_dir is None:
        print("Local source materialization is ready for committed generated artifacts.")
        print("The source directory is intentionally not committed; upstream licensing still applies.")

    return dest_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sparse-fetch upstream robot source files. By default this materializes "
            "user-local source assets under bodies/{name}/source so committed generated "
            "artifacts can resolve external meshes without vendoring them."
        )
    )
    parser.add_argument(
        "yaml_file",
        type=Path,
        help="Path to the robot fetch definition YAML.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Destination directory. Defaults to bodies/{name}/source for local source "
            "materialization and backward compatibility."
        ),
    )

    args = parser.parse_args()

    if not args.yaml_file.is_file():
        fail(f"YAML file not found at '{args.yaml_file}'")

    fetch_robot_sources(args.yaml_file, args.output_dir)


if __name__ == "__main__":
    main()
