# Direct MJCF materialization

Some upstream robot models already provide canonical MuJoCo XML and mesh assets. In those cases, `forge.sh` can materialize the upstream MJCF tree directly instead of converting from URDF.

Use `forge.mode: mjcf_passthrough` with a pinned upstream revision:

```yaml
name: shadow_hand
repo: https://github.com/google-deepmind/mujoco_menagerie.git
branch: main
revision: <pinned commit>
files:
  - shadow_hand/
forge:
  mode: mjcf_passthrough
  entry_mjcf: shadow_hand/scene_right.xml
```

Materialize Shadow Hand into the ignored local source directory:

```bash
PATH=$PWD/.venv/bin:$PATH \
  ./tools/forge.sh sources/shadow_hand.yaml bodies/shadow_hand/source
```

The passthrough flow performs:

1. sparse fetch from the pinned upstream revision;
2. local materialization under the requested directory;
3. entry MJCF existence validation;
4. recursive `<include file="...">` and `<mesh file="...">` reference validation.

External mesh assets such as OBJ/STL/DAE should normally remain in `bodies/{name}/source/`, which is intentionally not committed. The source YAML, pinned revision, and Hakoniwa-specific conversion/configuration rules remain versioned.
