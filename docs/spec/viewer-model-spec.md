# Hakoniwa Viewer Model Recipe / JSON / Generator v0.1 Specification

## 目的

本ドキュメントは、`hakoniwa-mbody-registry` における **Hakoniwa Viewer Model** の v0.1 仕様案を整理する。

対象は以下である。

1. Viewer Model を生成するための recipe YAML 仕様
2. 生成される `hako_viewer_model.json` 仕様
3. recipe + MJCF から Viewer Model JSON を生成する変換ルール
4. 現在の Python 実装で対応できている範囲
5. 今後スキーマ化する際の論点

本仕様は、まず TurtleBot3 Burger を対象にした最小実装から始める。

---

## 背景

`hakoniwa-mbody-registry` では、URDF / xacro から MJCF と GLB を生成するパイプラインを構築している。

次の段階として、生成された MJCF と GLB から、Godot / three.js / Unity / OpenUSD などのビューア環境でロボットを自動構築したい。

そのために、以下の2段階モデルを導入する。

```text
viewer.recipe.yaml
  人間が書く薄い selector / hint

MJCF
  body / joint / transform / mesh の正

        ↓ generator

hako_viewer_model.json
  ビューアが読む完全展開済み中間モデル
```

重要な方針は以下である。

```text
MJCF にある情報は recipe に書かない。
generator が解決できる情報は recipe に書かない。
recipe には、人間しか知らない意味づけだけを書く。
```

---

## 用語

### Viewer Recipe

MJCF から Viewer Model を生成するための入力 YAML。

人間が編集することを前提とする。

主な役割は、MJCF 内のどの body / joint を viewer に出すかを指定することである。

### Viewer Model

ゲームエンジン非依存の軽量中間モデル。

Godot / three.js / Unity / OpenUSD exporter などの入力となる。

JSON として生成される。

### MJCF

MuJoCo 用の物理モデル。

Viewer Model の生成においては、以下の正とする。

```text
- body hierarchy
- body transform
- joint
- joint axis
- geom / mesh
```

### GLB

ゲームエンジンで利用する visual asset。

v0.1 では、body 名と GLB ファイル名を対応させる。

---

## 全体フロー

```text
viewer.recipe.yaml
turtlebot3_burger.actuated.xml
parts/*.glb

        ↓

hako_viewer_model_gen.py

        ↓

turtlebot3.json
```

実行例。

```bash
python3 hako_viewer_model_gen.py viewer.recipe.yaml -o turtlebot3.json --pretty
```

---

# 1. Viewer Recipe v0.1 仕様

## 1.1 目的

Viewer Recipe は、MJCF から Viewer Model を生成するための最小入力である。

これは Viewer Model そのものではなく、MJCF から何を抽出するかを指定する selector / hint である。

## 1.2 設計原則

```text
MJCFにあるもの:
  書かない

名前規則で決まるもの:
  書かない

generatorが解決できるもの:
  書かない

人間しか知らない意味:
  書く
```

## 1.3 最小例

```yaml
format: hako_viewer_model_recipe
version: 0.1

robot: turtlebot3_burger
mjcf: turtlebot3_burger.actuated.xml

assets:
  glb_dir: parts
  map: body_name

base: base_link

movables:
  - wheel_left_joint
  - wheel_right_joint

pdu:
  pose: tb3_pose
  joint_state: tb3_joint_state
```

## 1.4 フィールド仕様

### `format`

```yaml
format: hako_viewer_model_recipe
```

recipe の種類を示す文字列。

v0.1 では `hako_viewer_model_recipe` を指定する。

### `version`

```yaml
version: 0.1
```

recipe の仕様バージョン。

v0.1 では `0.1`。

### `robot`

```yaml
robot: turtlebot3_burger
```

生成される Viewer Model の robot name。

出力 JSON の `robot.name` に使われる。

### `mjcf`

```yaml
mjcf: turtlebot3_burger.actuated.xml
```

入力 MJCF ファイル。

相対パスの場合は、recipe ファイルのあるディレクトリからの相対パスとして解釈する。

### `assets`

```yaml
assets:
  glb_dir: parts
  map: body_name
```

GLB asset の解決ルール。

#### `assets.glb_dir`

GLB ファイルが配置されているディレクトリ。

出力 JSON では、以下のような path に展開される。

```json
{
  "id": "base_link",
  "type": "glb",
  "path": "parts/base_link.glb"
}
```

#### `assets.map`

GLB と MJCF 要素の対応規則。

v0.1 では以下のみ対応する。

```yaml
map: body_name
```

これは、MJCF body 名と GLB ファイル名を対応させることを意味する。

```text
body name: wheel_left_link
GLB path : parts/wheel_left_link.glb
asset id : wheel_left_link
```

### `base`

```yaml
base: base_link
```

Viewer Model における base body。

この body が viewer 上の robot root となる。

MJCF 上の body 名を指定する。

### `movables`

```yaml
movables:
  - wheel_left_joint
  - wheel_right_joint
```

可動表示対象とする joint 名のリスト。

v0.1 では、中身は **body 名ではなく joint 名** である。

理由は、可動性の正体が body ではなく joint だからである。

generator は joint 名から以下を解決する。

```text
joint name
  ↓
joint が属する body
  ↓
parent body
  ↓
body の mount transform
  ↓
joint axis
  ↓
movable_part
```

将来的には、キー名を `movable_joints` に変更または併用してもよい。

```yaml
movable_joints:
  - wheel_left_joint
  - wheel_right_joint
```

v0.1 実装では、`movable_joints` があればそれを優先し、なければ `movables` を読む方針が望ましい。

### `pdu`

```yaml
pdu:
  pose: tb3_pose
  joint_state: tb3_joint_state
```

Viewer Model に埋め込む PDU binding 名。

v0.1 では、変換器は値を解釈せず、出力 JSON の `pdu_bindings` にそのまま転記する。

---

## 1.5 recipe に書かないもの

以下は MJCF から取得できるため、recipe には書かない。

```text
- body の xyz
- body の quat / rpy
- joint axis
- parent body
- mesh 名
- movable body 名
```

以下は generator / backend 側の責務であり、recipe には書かない。

```text
- ROS → Godot 座標変換
- ROS → OpenUSD 座標変換
- GLB instance の具体的な engine 表現
- Godot NodePath
```

---

# 2. hako_viewer_model.json v0.1 仕様

## 2.1 目的

`hako_viewer_model.json` は、Viewer Recipe と MJCF から生成される完全展開済みの中間モデルである。

Godot / three.js / Unity / OpenUSD exporter は、この JSON を入力として利用する。

## 2.2 最小例

```json
{
  "format": "hako_viewer_model",
  "version": "0.1",
  "coordinate_system": "ros",
  "robot": {
    "name": "turtlebot3_burger",
    "root": "base_link"
  },
  "assets": [
    {
      "id": "base_link",
      "type": "glb",
      "path": "parts/base_link.glb"
    },
    {
      "id": "wheel_left_link",
      "type": "glb",
      "path": "parts/wheel_left_link.glb"
    },
    {
      "id": "wheel_right_link",
      "type": "glb",
      "path": "parts/wheel_right_link.glb"
    },
    {
      "id": "base_scan",
      "type": "glb",
      "path": "parts/base_scan.glb"
    }
  ],
  "base": {
    "name": "base_link",
    "asset": "base_link",
    "mount": {
      "xyz": [0.0, 0.0, 0.0],
      "rpy": [0.0, 0.0, 0.0]
    }
  },
  "movable_parts": [
    {
      "name": "wheel_left_link",
      "joint": "wheel_left_joint",
      "parent": "base_link",
      "asset": "wheel_left_link",
      "mount": {
        "xyz": [0.0, 0.08, 0.023],
        "rpy": [-1.5708, 0.0, 0.0]
      },
      "motion": {
        "type": "continuous",
        "axis": [0.0, 0.0, 1.0]
      }
    },
    {
      "name": "wheel_right_link",
      "joint": "wheel_right_joint",
      "parent": "base_link",
      "asset": "wheel_right_link",
      "mount": {
        "xyz": [0.0, -0.08, 0.023],
        "rpy": [-1.5708, 0.0, 0.0]
      },
      "motion": {
        "type": "continuous",
        "axis": [0.0, 0.0, 1.0]
      }
    }
  ],
  "pdu_bindings": {
    "pose": "tb3_pose",
    "joint_state": "tb3_joint_state"
  }
}
```

## 2.3 フィールド仕様

### `format`

```json
"format": "hako_viewer_model"
```

Viewer Model の種類。

### `version`

```json
"version": "0.1"
```

Viewer Model 仕様バージョン。

### `coordinate_system`

```json
"coordinate_system": "ros"
```

Viewer Model が採用する座標系。

v0.1 では `ros` を基本とする。

ゲームエンジン固有の座標系変換は、各 backend generator が担当する。

```text
hako_viewer_model.json:
  ROS coordinate

Godot generator:
  ROS → Godot 変換

OpenUSD exporter:
  ROS → USD 変換
```

### `robot`

```json
"robot": {
  "name": "turtlebot3_burger",
  "root": "base_link"
}
```

#### `robot.name`

ロボット名。

recipe の `robot` から生成される。

#### `robot.root`

viewer 上の root body。

recipe の `base` から生成される。

### `assets`

```json
"assets": [
  {
    "id": "base_link",
    "type": "glb",
    "path": "parts/base_link.glb"
  }
]
```

Viewer Model が参照する visual asset の一覧。

v0.1 では `type: glb` のみ対象。

#### `assets[].id`

asset ID。

v0.1 では body 名と同一。

#### `assets[].type`

asset 種別。

v0.1 では `glb`。

#### `assets[].path`

GLB ファイルへのパス。

recipe の `assets.glb_dir` と MJCF body 名から生成される。

### `base`

```json
"base": {
  "name": "base_link",
  "asset": "base_link",
  "mount": {
    "xyz": [0.0, 0.0, 0.0],
    "rpy": [0.0, 0.0, 0.0]
  }
}
```

Viewer 上の base body。

v0.1 では、base の mount は identity とする。

これは、Viewer Model の root を base として扱うためである。

### `movable_parts`

```json
"movable_parts": [
  {
    "name": "wheel_left_link",
    "joint": "wheel_left_joint",
    "parent": "base_link",
    "asset": "wheel_left_link",
    "mount": {
      "xyz": [0.0, 0.08, 0.023],
      "rpy": [-1.5708, 0.0, 0.0]
    },
    "motion": {
      "type": "continuous",
      "axis": [0.0, 0.0, 1.0]
    }
  }
]
```

可動表示対象。

recipe の `movables` / `movable_joints` に指定された joint から生成する。

#### `movable_parts[].name`

可動部 body 名。

MJCF で joint が属している body 名。

#### `movable_parts[].joint`

可動部に対応する MJCF joint 名。

#### `movable_parts[].parent`

可動部 body の parent body 名。

#### `movable_parts[].asset`

可動部 body に対応する visual asset ID。

#### `movable_parts[].mount`

parent body から見た可動部 body の初期 transform。

v0.1 では `xyz` と `rpy` を出力する。

内部的には MJCF の `pos` と `quat` から生成する。

#### `movable_parts[].motion`

joint の可動情報。

##### `motion.type`

v0.1 では以下の変換を行う。

```text
MJCF joint type = hinge
  → continuous

MJCF joint type = slide
  → prismatic

その他
  → MJCF joint type をそのまま出力
```

##### `motion.axis`

MJCF joint の `axis` を出力する。

v0.1 では、MJCF/ROS座標系の値をそのまま出力する。

### `pdu_bindings`

```json
"pdu_bindings": {
  "pose": "tb3_pose",
  "joint_state": "tb3_joint_state"
}
```

PDU 名の対応。

v0.1 では recipe の `pdu` をそのまま転記する。

---

# 3. 変換ルール v0.1

## 3.1 入力

```text
- viewer.recipe.yaml
- MJCF XML
- GLB directory
```

## 3.2 出力

```text
- hako_viewer_model.json
```

## 3.3 MJCF index 作成

generator は MJCF を parse し、以下の index を作成する。

```text
body index:
  body name → BodyInfo

joint index:
  joint name → JointInfo
```

### BodyInfo

```text
BodyInfo:
  name
  parent
  pos
  quat
  mesh_names
```

### JointInfo

```text
JointInfo:
  name
  body
  joint_type
  axis
  pos
```

## 3.4 body index ルール

MJCF の `<worldbody>` から body tree を再帰的に走査する。

各 body について以下を取得する。

```text
name:
  body の name 属性

parent:
  親 body 名

pos:
  body の pos 属性
  未指定なら [0, 0, 0]

quat:
  body の quat 属性
  未指定なら [1, 0, 0, 0]

mesh_names:
  body 直下の geom mesh 属性
```

## 3.5 joint index ルール

各 body 直下の `<joint>` を取得する。

```text
name:
  joint の name 属性

body:
  joint が属する body 名

joint_type:
  joint の type 属性
  未指定なら hinge

axis:
  joint の axis 属性
  未指定なら [0, 0, 1]

pos:
  joint の pos 属性
  未指定なら [0, 0, 0]
```

## 3.6 assets 生成ルール

v0.1 では、mesh geom を持つ body から asset を生成する。

```text
if body has geom mesh:
  asset id = body.name
  asset type = glb
  asset path = {glb_dir}/{body.name}.glb
```

例。

```text
body: wheel_left_link
glb_dir: parts

→
{
  "id": "wheel_left_link",
  "type": "glb",
  "path": "parts/wheel_left_link.glb"
}
```

## 3.7 base 生成ルール

recipe の `base` に指定された body を Viewer Model の base とする。

```text
base.name = recipe.base
base.asset = recipe.base
base.mount = identity
```

v0.1 では、base body 自身の MJCF transform は出力しない。

理由は、Viewer Model 上では base を root として扱うためである。

## 3.8 movable_parts 生成ルール

recipe の `movables` / `movable_joints` に指定された joint 名ごとに、以下を行う。

```text
1. joint name から JointInfo を取得
2. JointInfo.body から可動部 body を取得
3. body.parent を parent とする
4. body.pos / body.quat から mount を生成
5. joint.axis から motion.axis を生成
6. joint.type から motion.type を生成
7. body.name から asset を解決
```

疑似コード。

```text
for joint_name in recipe.movables:
    joint = joint_index[joint_name]
    body = body_index[joint.body]

    movable_part.name = body.name
    movable_part.joint = joint.name
    movable_part.parent = body.parent
    movable_part.asset = body.name
    movable_part.mount.xyz = body.pos
    movable_part.mount.rpy = quat_to_rpy(body.quat)
    movable_part.motion.axis = joint.axis
    movable_part.motion.type = motion_type_from_joint(joint)
```

## 3.9 pdu_bindings 生成ルール

recipe の `pdu` が存在する場合、出力 JSON の `pdu_bindings` にそのまま転記する。

```yaml
pdu:
  pose: tb3_pose
  joint_state: tb3_joint_state
```

↓

```json
"pdu_bindings": {
  "pose": "tb3_pose",
  "joint_state": "tb3_joint_state"
}
```

---

# 4. 現在の Python 実装仕様

## 4.1 ツール名

現時点の試作実装。

```text
hako_viewer_model_gen.py
```

## 4.2 実行方法

```bash
python3 hako_viewer_model_gen.py viewer.recipe.yaml -o turtlebot3.json --pretty
```

## 4.3 依存

```text
Python 3
PyYAML
```

## 4.4 対応済み

現在の実装で対応している範囲。

```text
- recipe YAML 読み込み
- MJCF XML parse
- worldbody 以下の body tree 走査
- body index 作成
- joint index 作成
- base 生成
- movable_parts 生成
- GLB assets 生成
- pdu_bindings 転記
- body quat → rpy 変換
- pretty JSON 出力
```

## 4.5 対応している recipe key

```text
format
version
robot
mjcf
coordinate / coordinate_system
assets.glb_dir
assets.map
base
movables
movable_joints
pdu
```

## 4.6 対応している assets.map

```text
body_name
```

それ以外の map 方式は未対応。

## 4.7 対応している joint type

```text
hinge:
  continuous として出力

slide:
  prismatic として出力

その他:
  そのまま出力
```

## 4.8 現在未対応

```text
- sensors.yaml
- fixed_parts
- body transform の base-relative 合成
- body 階層の全展開
- geom 単位の visual origin
- 複数 mesh を持つ body の扱い
- assets.overrides
- material
- collision
- inertia
- actuator 情報の viewer model への反映
- OpenUSD export
- Godot .tscn generation
- JSON Schema validation
- YAML Schema validation
```

---

# 5. 現在の実装上の注意点

## 5.1 base 直下でない movable body

現在の実装では、movable part の `mount` は、MJCF上の parent body から見た body local transform をそのまま出力する。

これは以下の構造では問題ない。

```text
base_link
  wheel_left_link
```

しかし、将来的に以下のような階層がある場合、

```text
base_link
  sub_frame
    wheel_left_link
```

`wheel_left_link` を `base_link` 直下に配置したいなら、base-relative transform の合成が必要になる。

v0.1 では、MJCF の parent をそのまま出力し、backend 側が同じ階層を構築する前提とする。

## 5.2 rpy の丸め

現在の実装では、MJCF の quat を rpy に変換して出力する。

MJCF の quat が近似値の場合、出力 rpy は以下のように微小にずれることがある。

```text
expected: -1.5708
actual  : -1.569999
```

これは数値変換の結果であり、実用上は問題ない。

将来的には、以下の方針が考えられる。

```text
- rpy の丸め桁を調整する
- mount に quat を出力する
- rpy と quat の両方を出力する
```

OpenUSD / Godot 変換を考えると、将来的には quat を保持する方が安全である。

## 5.3 assets の生成対象

現在の実装では、mesh geom を持つ body のみ assets に追加する。

そのため、mesh を持たない frame body は assets に出ない。

これは v0.1 として妥当である。

## 5.4 pdu 名の一致

Viewer Model の `pdu_bindings.joint_state` と、実行時の joint_state sensor config の `pdu_name` は一致している必要がある。

例。

```json
{
  "pdu_name": "joint_states"
}
```

で joint_state sensor が publish する場合、Viewer Model 側も以下に合わせる必要がある。

```json
"pdu_bindings": {
  "joint_state": "joint_states"
}
```

---

# 6. 今後のスキーマ化方針

## 6.1 recipe schema

将来的に以下を JSON Schema または YAML 向け schema として定義する。

```text
hako_viewer_model_recipe.schema.json
```

検証項目。

```text
- format が hako_viewer_model_recipe である
- version が存在する
- robot が存在する
- mjcf が存在する
- base が存在する
- assets.glb_dir が存在する
- assets.map が body_name である
- movables または movable_joints が配列である
- pdu が optional object である
```

## 6.2 viewer model schema

将来的に以下を JSON Schema として定義する。

```text
hako_viewer_model.schema.json
```

検証項目。

```text
- format が hako_viewer_model である
- version が存在する
- coordinate_system が存在する
- robot.name が存在する
- robot.root が存在する
- assets が配列である
- base が存在する
- movable_parts が配列である
- movable_parts[].joint が存在する
- movable_parts[].motion.axis が vec3 である
- pdu_bindings が optional object である
```

---

# 7. sensors.yaml との将来統合

v0.1 の最小実装では sensors は未対応である。

ただし、構想上は以下の形を想定する。

```yaml
format: hako_sensors
version: 0.1

sensors:
  - name: lidar
    type: lidar_2d
    body: base_scan
    spec: sensors/lds_01.yaml
    pdu: tb3_scan

  - name: imu
    type: imu
    body: imu_link
    spec: sensors/imu.yaml
    pdu: tb3_imu
```

generator は MJCF から `body` または `site` の transform を取得し、Viewer Model に展開する。

```json
"sensors": [
  {
    "name": "lidar",
    "type": "lidar_2d",
    "body": "base_scan",
    "parent": "base_link",
    "asset": "base_scan",
    "mount": {
      "xyz": [-0.032, 0.0, 0.172],
      "rpy": [0.0, 0.0, 0.0]
    },
    "spec": "sensors/lds_01.yaml",
    "pdu": "tb3_scan"
  }
]
```

---

# 8. Godot Generator との接続

`hako_viewer_model.json` から Godot scene を生成する。

想定ツール。

```text
hako-godot-scene-gen
```

入力。

```text
hako_viewer_model.json
```

出力。

```text
TurtleBot3.generated.tscn
```

Godot 上の構造例。

```text
TurtleBot3
  HakoSync
  Visuals
    base_link
      wheel_left_link
      wheel_right_link
      base_scan
```

Godot generator の責務。

```text
- hako_viewer_model.json を読む
- ROS座標系からGodot座標系へ変換する
- GLB asset を instance 化する
- movable_parts の mount を Node3D transform に変換する
- joint_state PDU と joint 名を対応させる
- base pose PDU で root を動かす
```

重要な方針。

```text
座標系差異は recipe に書かせない。
座標系差異は backend generator が吸収する。
```

---

# 9. OpenUSD Exporter との将来接続

Hakoniwa Viewer Model は、将来的に OpenUSD へ変換することを意識する。

ただし、OpenUSD の代替ではない。

```text
hako_viewer_model.json
    ↓
OpenUSD exporter
    ↓
robot.usda
```

対応イメージ。

```text
robot.root
  → USD root Prim

base
  → USD Xform / root link Prim

movable_parts
  → USD Xform + joint / articulation mapping

assets
  → USD reference / payload / converted mesh

sensors
  → sensor mount Prim / Isaac Sim sensor Prim

pdu_bindings
  → Hakoniwa custom metadata
```

OpenUSD 変換を見据えて、Viewer Model は以下を保持する。

```text
- parent-child hierarchy
- asset reference
- mount transform
- movable joint
- sensor mount
- Hakoniwa PDU metadata
```

---

# 10. v0.1 の到達点

今回の v0.1 で確認できたこと。

```text
- recipe は最小限で十分
- movables は joint 名指定でよい
- generator は joint → body → parent / transform / axis を解決できる
- MJCF から viewer model に必要な静的情報を抽出できる
- runtime の joint_state sensor と viewer model は joint 名で接続できる
```

この段階で、次のパイプラインが成立する。

```text
viewer.recipe.yaml
MJCF
        ↓
hako_viewer_model_gen.py
        ↓
hako_viewer_model.json
        ↓
Godot generator
        ↓
Godot viewer

MuJoCo runtime
        ↓
joint_state sensor
        ↓
joint_state PDU
        ↓
Godot viewer
```

---

## まとめ

v0.1 の基本思想は以下である。

```text
recipe:
  人間が書く薄い selector

MJCF:
  構造・配置・joint・mesh の正

generator:
  MJCF から viewer model を展開する変換器

hako_viewer_model.json:
  Godot / three.js / Unity / OpenUSD へ渡す軽量中間モデル
```

この構造により、箱庭は URDF / MJCF / GLB / PDU / Game Engine / OpenUSD を接続するための軽量な橋渡し層を持つことができる。
