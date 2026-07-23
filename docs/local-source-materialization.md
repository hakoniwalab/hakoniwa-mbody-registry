# Local source materialization for committed generated artifacts

`hakoniwa-mbody-registry` commits generated URDF, MJCF, GLB, and related registry outputs, but it does **not** vendor third-party upstream robot source trees.

That means a committed generated file is not always self-contained. In particular, a MuJoCo XML file may keep relative references such as:

```text
../source/turtlebot3_description/meshes/bases/burger_base.stl
```

The supported runtime preparation step is to materialize the upstream source locally with `tools/fetch.py`.

## Responsibility boundary

```text
sources/<name>.yaml
  -> declares upstream repository / branch or revision / paths

          tools/fetch.py
               |
               v
bodies/<name>/source/
  -> user-local upstream source material
  -> gitignored by hakoniwa-mbody-registry
  -> governed by the upstream license

bodies/<name>/generated/
  -> committed Hakoniwa registry artifacts
  -> may reference files under ../source/
```

The registry therefore keeps third-party assets outside its committed MIT-licensed tree while still providing a repository-defined way to obtain exactly the source paths required by generated artifacts.

## TurtleBot3 Burger

The committed TurtleBot3 Burger MJCF references mesh files under:

```text
bodies/turtlebot3_burger/source/turtlebot3_description/meshes/
```

From the `hakoniwa-mbody-registry` repository root, materialize those files with:

```bash
python3 tools/fetch.py sources/turtlebot3_burger.yaml
```

This sparse-fetches the paths declared by `sources/turtlebot3_burger.yaml` into:

```text
bodies/turtlebot3_burger/source/
```

After that, the relative mesh references in the committed generated MJCF resolve locally. You do **not** need to run the full `tools/forge.sh` conversion pipeline merely to satisfy those runtime mesh references.

## Windows

The same materialization step is intended to work on native Windows because `tools/fetch.py` is Python-based and invokes Git directly.

For example, from PowerShell with a repository-local virtual environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\fetch.py sources\turtlebot3_burger.yaml
```

The expected local result is:

```text
bodies\turtlebot3_burger\source\turtlebot3_description\meshes\...
```

## Re-fetch behavior

When `tools/fetch.py` materializes the default `bodies/<name>/source/` destination, it replaces the existing local source directory before copying the newly fetched upstream paths.

Do not keep user-authored files under `bodies/<name>/source/`.

## Licensing

Materialized source files are fetched directly from the upstream repository and are not committed into `hakoniwa-mbody-registry`.

Their use and redistribution remain subject to the upstream license. For TurtleBot3, `ROBOTIS-GIT/turtlebot3` and its `turtlebot3_description` package declare Apache License 2.0.

`hakoniwa-mbody-registry` itself remains MIT licensed; materializing third-party source locally does not relicense those upstream files as MIT.
