# TurtleBot3 Burger generated assets

The files in this directory are committed registry outputs, but the MuJoCo XML files are not fully self-contained.

Some generated MJCF assets reference upstream TurtleBot3 mesh files through relative paths under:

```text
../source/turtlebot3_description/meshes/
```

Before loading those MJCF files, materialize the upstream source locally from the repository root:

```bash
python3 tools/fetch.py sources/turtlebot3_burger.yaml
```

On native Windows with a repository-local virtual environment:

```powershell
.\.venv\Scripts\python.exe tools\fetch.py sources\turtlebot3_burger.yaml
```

This populates the gitignored local directory:

```text
bodies/turtlebot3_burger/source/
```

You do not need to rerun the full forge pipeline just to satisfy these mesh references.

See [`docs/local-source-materialization.md`](../../../docs/local-source-materialization.md) for the ownership, licensing, and re-fetch rules.
