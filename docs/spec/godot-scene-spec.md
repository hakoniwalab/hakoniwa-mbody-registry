# Hakoniwa Godot Scene YAML v0.1 Specification

## 目的

本ドキュメントは、`hakoniwa-mbody-registry` における
**`godot_scene.yaml` の v0.1 仕様案**を整理する。

対象は以下である。

1. `godot_scene.yaml` の責務
2. `godot_sync.yaml` との責務分離
3. scene generator が生成すべきもの
4. `godot_scene.yaml` の YAML 仕様
5. v0.1 のデフォルト方針

本仕様の目的は、
**Godot scene 構成の責務を `godot_sync.yaml` から切り離し、
scene generator の入力を明示的にすること**
である。

---

## 背景

現在の生成フローでは、以下の層が混在しやすい。

```text
viewer model JSON
  ↓
Godot .tscn
  + runtime sync script
  + HakoniwaSimNode
  + HakoniwaCodecNode
  + material override
  + sample project layout
```

ここで混ざっている責務は大きく 3 つある。

- ロボット構造の scene 化
- Hakoniwa runtime へ接続するための node 配置
- sample / quickstart 向けの運用補助

一方、`godot_sync.yaml` は本来、
**PDU と可変部分の同期責務**
だけを持つべきであり、
scene 構成や camera などを混ぜたくない。

そこで、
**scene generator 用の入力として `godot_scene.yaml` を新設する**
方針を採る。

---

## 責務分離

### `viewer.recipe.yaml`

`viewer.recipe.yaml` は engine-independent のまま保つ。

持つ責務:

- MJCF と GLB の対応
- base body
- movable bodies
- fixed bodies

持たない責務:

- Godot runtime node
- PDU 同期設定
- sample project layout

### `godot_sync.yaml`

`godot_sync.yaml` は
**PDU と可変部分の同期設定**
だけを扱う。

持つ責務:

- base pose PDU 名
- joint_states PDU 名
- joint と body の対応
- axis / sign / offset
- coordinate_system rule
- endpoint 名
- comm / pdu_def など通信設定で必要な可変参照

持たない責務:

- scene root 名
- asset path 規約
- SimNode / CodecNode を scene に出すか
- camera rig
- material override

### `godot_scene.yaml`

`godot_scene.yaml` は
**Godot scene generator の出力方針**
を扱う。

持つ責務:

- scene root 名
- `res://` 配下の path 規約
- `HakoSync` script 生成
- `HakoniwaSimNode` を出すか
- `HakoniwaCodecNode` を出すか
- default material を付与するか

持たない責務:

- base / joint の PDU 名
- joint 軸や符号
- camera rig の実装
- ユーザ固有の UI や演出

---

## v0.1 の基本方針

### 1. `HakoSync` は必須生成

`HakoSync` はオプションではない。

scene generator は常に以下を生成する。

- `HakoSync` node
- `tb3_reference_sync.gd` のような薄い wrapper script

この script は placeholder ではなく、
`hakoniwa_robot_sync` addon の controller を継承する
薄い runtime 接続 script を自動生成する。

### 2. `HakoniwaSimNode` と `HakoniwaCodecNode` はオプション

これらは scene generator のオプションとする。

ただし、v0.1 の default は `true` とする。

理由:

- QuickStart の主対象は初心者である
- 初回体験では、生成直後に Hakoniwa runtime へ接続できる方がよい

### 3. camera rig は generator の責務に入れない

`camera_rig.gd` や Camera3D 配置は
sample / tutorial 側で扱う。

`docs/add-your-robot.md` には、
camera rig を Godot editor 上で D&D 追加する手順を追記する。

### 4. default material は generator が付与できるようにする

GLB に material が十分入っていない場合でも、
Godot 上で最低限視認できるようにする。

そのため、scene generator は
default material override を付与できるようにする。

v0.1 では:

- ON/OFF のみ持つ
- 色や roughness は generator 側の固定デフォルトでよい
- ユーザ好みの見た目調整は対象外とする

### 5. path 規約は現行の `godot/` テンプレートを正とする

scene generator は以下の配置規約を基準とする。

- `res://assets/parts/*.glb`
- `res://assets/<sync_script>.gd`
- `res://config/robot_sync.profile.json`
- `res://config/endpoint_shm_poll_with_pdu.json`
- `res://config/comm/*.json`

ツール側をこの規約へ寄せる。

### 6. scene の細部パラメータは当面テンプレート準拠とする

`WorldEnvironment`、`DirectionalLight3D`、ground、runtime node の property など、
scene の細かなパラメータは v0.1 では一般化しすぎない。

当面は、
**`hakoniwa-getting-started/godot/tb3-viewer-template/` の実値を正**
として generator を合わせる。

対象例:

- `Environment` の ambient / sky / SSAO 系設定
- `DirectionalLight3D` の transform や energy
- `RosToGodot` の transform
- `HakoniwaSimNode` の property 初期値
- `HakoniwaCodecNode` の property 初期値

理由:

- QuickStart の再現性を優先したい
- scene parameter の自由度を早期に YAML 化すると責務が過剰に広がる
- まずは TB3 の実テンプレートを再現できることが優先である

したがって v0.1 では、
これらの細部パラメータは `godot_scene.yaml` の自由設定項目には含めず、
generator 実装側で template-compatible に出力する。

---

## YAML 仕様案

```yaml
format: hako_godot_scene
version: 0.1

scene:
  root_name: turtlebot3_burger
  output_scene: TurtleBot3.generated.tscn
  sync_script_name: tb3_reference_sync.gd

paths:
  asset_root: res://assets
  parts_dir: res://assets/parts
  sync_script: res://assets/tb3_reference_sync.gd
  robot_sync_profile: res://config/robot_sync.profile.json
  endpoint_config: res://config/endpoint_shm_poll_with_pdu.json

nodes:
  generate_sim_node: true
  generate_codec_node: true

materials:
  apply_default_materials: true
```

---

## 各項目の意味

### `format`

固定値:

```yaml
format: hako_godot_scene
```

### `version`

初期値:

```yaml
version: 0.1
```

### `scene.root_name`

生成される Godot scene root node 名。

例:

```yaml
scene:
  root_name: turtlebot3_burger
```

### `scene.output_scene`

生成物の scene filename。

例:

```yaml
scene:
  output_scene: TurtleBot3.generated.tscn
```

### `scene.sync_script_name`

自動生成する `HakoSync` wrapper script のファイル名。

例:

```yaml
scene:
  sync_script_name: tb3_reference_sync.gd
```

### `paths.asset_root`

scene generator が asset 系を置く前提の root。

例:

```yaml
paths:
  asset_root: res://assets
```

### `paths.parts_dir`

GLB parts の参照先。

例:

```yaml
paths:
  parts_dir: res://assets/parts
```

### `paths.sync_script`

`HakoSync` script の参照先。

例:

```yaml
paths:
  sync_script: res://assets/tb3_reference_sync.gd
```

### `paths.robot_sync_profile`

`HakoSync` が読む profile path。

例:

```yaml
paths:
  robot_sync_profile: res://config/robot_sync.profile.json
```

### `paths.endpoint_config`

`HakoniwaSimNode` が読む endpoint config path。

例:

```yaml
paths:
  endpoint_config: res://config/endpoint_shm_poll_with_pdu.json
```

### `nodes.generate_sim_node`

`HakoniwaSimNode` を scene に出すか。

初期値:

```yaml
nodes:
  generate_sim_node: true
```

### `nodes.generate_codec_node`

`HakoniwaCodecNode` を scene に出すか。

初期値:

```yaml
nodes:
  generate_codec_node: true
```

### `materials.apply_default_materials`

scene generator が default material override を付与するか。

初期値:

```yaml
materials:
  apply_default_materials: true
```

---

## v0.1 で generator が生成すべきもの

### 必須

- root `Node3D`
- `WorldEnvironment`
- `DirectionalLight3D`
- `HakoSync`
- `RosToGodot`
- `Visuals`
- base / movable / fixed body node
- `HakoSync` 用 wrapper GDScript

### オプション

- `HakoniwaSimNode`
- `HakoniwaCodecNode`
- default material override

### 非対象

- `CameraRig`
- Camera3D
- UI
- user-specific interaction

---

## 生成される `HakoSync` script の方針

v0.1 では、generator は placeholder script ではなく、
以下に近い薄い wrapper を出力する。

```gdscript
extends "res://addons/hakoniwa_robot_sync/scripts/robot_sync_controller.gd"

func _ready() -> void:
	if sim_node_path.is_empty():
		sim_node_path = $"../HakoniwaSimNode".get_path()
	if target_root_path.is_empty():
		target_root_path = $"../RosToGodot".get_path()
	if profile_path.is_empty():
		profile_path = "res://config/robot_sync.profile.json"
	super._ready()
```

ここで `profile_path` は `godot_scene.yaml` の `paths.robot_sync_profile`
に従って埋め込む。

---

## 未使用 GLB の扱い

v0.1 では、
生成された `parts/*.glb` のすべてが scene に使われるとは限らない。

例:

- `caster_back_link.glb` は生成されても scene に参照されない場合がある

これは直ちに不整合とはみなさず、
**「生成 asset の superset が scene から部分利用されることはある」**
という仕様として扱う。

---

## TurtleBot3 例

```yaml
format: hako_godot_scene
version: 0.1

scene:
  root_name: turtlebot3_burger
  output_scene: TurtleBot3.generated.tscn
  sync_script_name: tb3_reference_sync.gd

paths:
  asset_root: res://assets
  parts_dir: res://assets/parts
  sync_script: res://assets/tb3_reference_sync.gd
  robot_sync_profile: res://config/robot_sync.profile.json
  endpoint_config: res://config/endpoint_shm_poll_with_pdu.json

nodes:
  generate_sim_node: true
  generate_codec_node: true

materials:
  apply_default_materials: true
```

---

## 今後の論点

### 1. endpoint path の責務

`endpoint_config` 自体は scene path なので `godot_scene.yaml` に置ける。
一方、endpoint JSON の生成責務は `godot_sync.yaml` 側に残る。

v0.1 では次の分離を採る。

- endpoint JSON の中身を作る: `godot_sync.yaml`
- scene からその配置先を参照する: `godot_scene.yaml`

### 2. material の色指定

v0.1 では ON/OFF のみで始める。

色・roughness・metallic などの細かい表現は、
必要になった時点で `materials.default_style` のような形で拡張する。

### 3. scene parameter の一般化範囲

v0.1 では、
`Environment` や `DirectionalLight3D` の細かな property を
YAML の公開設定項目にしない。

これらはまず TB3 template 準拠で固定生成し、
複数ロボットや複数サンプルで差分要求が出てから一般化を検討する。

### 4. QuickStart 以外の minimal mode

将来的には、
`generate_sim_node: false`
`generate_codec_node: false`
を標準とする truly minimal mode を
CLI preset で使い分けてもよい。

ただし v0.1 は QuickStart 優先のため、
default は `true` とする。
