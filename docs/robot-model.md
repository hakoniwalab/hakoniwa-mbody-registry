# Hakoniwa Robot Viewer Model 構想

## 目的

`hakoniwa-mbody-registry` では、URDF / xacro など既存のロボット資産から、MuJoCo 用の MJCF、およびゲームエンジンで利用可能な GLB アセットを生成できる。

次の段階として、生成された MJCF と GLB をもとに、Godot / three.js / Unity / 将来的には OpenUSD などのビューア環境でロボットを自動構築できるようにする。

本ドキュメントでは、そのための軽量な中間モデルである **Hakoniwa Robot Viewer Model** と、それを生成するための recipe 定義、および最初の generator 実装方針を整理する。

---

## 背景

現在の流れは以下である。

```text
URDF / xacro
    ↓
MJCF
    ↓
GLB assets
```

この時点で、MuJoCo で物理シミュレーションを実行するための構造と、ゲームエンジン上で描画するための 3D アセットは得られる。

しかし、Godot などのゲームエンジン上でロボットを表示するには、以下の情報がさらに必要になる。

- どの body をロボットの base として扱うか
- どの joint / body を可動部として扱うか
- どの GLB をどの部品に対応させるか
- どの body / site をセンサーの取り付け位置として扱うか
- 箱庭 PDU と表示対象をどう対応づけるか
- Godot / three.js / Unity / OpenUSD などにどう変換するか

これらをゲームエンジンごとに個別実装すると、ビューア依存の情報が散らばる。

そこで、まずゲームエンジン非依存の軽量な中間モデルを定義し、その中間モデルから Godot scene などを生成する方針とする。

---

## 基本方針

### 1. 物理モデルの正は MJCF

ロボットの body / joint / transform / actuator など、物理シミュレーションに必要な情報は MJCF を正とする。

```text
MJCF:
  - body hierarchy
  - joint
  - geom / mesh
  - transform
  - actuator
```

### 2. 見た目の正は GLB

ゲームエンジン向けの visual asset は GLB を利用する。

```text
GLB:
  - base body mesh
  - wheel mesh
  - rotor mesh
  - sensor mesh
```

### 3. Viewer Model は表示・可動・センサー配置のための軽量モデル

Hakoniwa Robot Viewer Model は、物理モデルの代替ではない。

これは、ゲームエンジンや OpenUSD へ変換するための軽量な接続マニフェストである。

```text
Hakoniwa Robot Viewer Model:
  - base
  - movable parts
  - sensors
  - visual asset mapping
  - PDU binding
```

### 4. OpenUSD は将来的な接続先

OpenUSD は、将来的な重要な接続先として意識する。

ただし、Hakoniwa Robot Viewer Model は OpenUSD の代替ではない。

OpenUSD は高機能な scene / digital twin / robotics asset 表現基盤であり、Hakoniwa Robot Viewer Model はそこへも変換しやすい軽量な前段モデルと位置づける。

```text
hako_viewer_model.json
    ↓
Godot .tscn
three.js scene
Unity prefab
OpenUSD .usd / .usda
```

### 5. URDF よりも OpenUSD への接続性を意識する

URDF は既存ロボット資産の入口として重要である。

一方で、箱庭として将来的に接続したい先は、URDF そのものよりも OpenUSD / Isaac Sim / Omniverse などの広いデジタルツイン基盤である。

そのため、Viewer Model は URDF 互換性よりも、以下を重視する。

- 親子構造を失わない
- 部品単位の asset を保持する
- mount transform を明示する
- movable part / joint / sensor mount を明示する
- PDU binding を箱庭固有メタデータとして保持できる

---

## 責務分担

### MJCF

MJCF は物理シミュレーションの正である。

```text
MJCF が持つもの:
  - body / joint の親子関係
  - body の pos / quat / euler
  - joint の type / axis / range
  - geom / mesh
  - actuator
  - sensor mount 用 body / site
```

### actuators.yaml

`actuators.yaml` は、外部から MuJoCo を制御するための actuator を後付けする定義である。

actuator は、箱庭 PDU など外部入力から MuJoCo の joint を駆動するために必要である。

```yaml
actuators:
  - type: motor
    name: left_motor
    joint: wheel_left_joint
    ctrllimited: true
    ctrlrange: [-10, 10]
    gear: 1.0

  - type: motor
    name: right_motor
    joint: wheel_right_joint
    ctrllimited: true
    ctrlrange: [-10, 10]
    gear: 1.0
```

### sensors.yaml

`sensors.yaml` は、MJCF 上の body / site に対して、センサーとしての意味づけを後付けする定義である。

センサーの取り付け位置は MJCF の body / site から取得できる。

そのため、`sensors.yaml` では位置を直接書かず、以下のような意味づけのみを記述する。

```yaml
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

センサー仕様そのものは、必要に応じて別ファイルに分離する。

```yaml
format: hako_sensor_spec
version: 0.1

name: lds_01
type: lidar_2d

scan:
  angle_min: -3.1415926535
  angle_max: 3.1415926535
  angle_increment: 0.0174532925
  range_min: 0.12
  range_max: 3.5
  scan_time: 0.1

noise:
  type: gaussian
  stddev: 0.01

pdu:
  type: sensor_msgs/LaserScan
  name: tb3_scan
```

### viewer recipe

`viewer.recipe.yaml` は、MJCF から Viewer Model を生成するための薄い selector / hint 定義である。

ここには、MJCF から自動取得できる transform や joint axis は書かない。

```yaml
format: hako_viewer_model_recipe
version: 0.1

robot: turtlebot3_burger
mjcf: turtlebot3_burger.actuated.xml

assets:
  glb_dir: meshes
  map: mesh_name

base: base_link

movables:
  - wheel_left_joint
  - wheel_right_joint

sensors: sensors.yaml
```

### hako_viewer_model.json

`hako_viewer_model.json` は、viewer recipe と MJCF と sensors.yaml から生成される完全展開済みの中間モデルである。

Godot / three.js / Unity / OpenUSD exporter は、この JSON を入力として利用する。

---

## なぜ MJCF sensor を使わないのか

MJCF の `<sensor>` は、MuJoCo が `sensordata` に出力する観測量を定義するためのものである。

これは、MuJoCo 内部で joint position / joint velocity / frame position / gyro / accelerometer などを計算したい場合に有効である。

一方で、Viewer Model に必要なのは以下である。

```text
必要なもの:
  - センサーがどこに取り付けられているか
  - それが何のセンサーか
  - どの PDU と対応するか
  - どう可視化するか
```

センサーの取り付け位置は MJCF の body / site から取得できる。

そのため、Viewer Model のためには、MJCF の `<sensor>` は必須ではない。

```text
MJCF body / site:
  センサーの取り付け位置

sensors.yaml:
  センサーの意味づけ
  センサー仕様
  PDU 対応

MJCF <sensor>:
  MuJoCo に sensordata を計算させたい場合に使う
```

将来的に MuJoCo の `sensordata` を箱庭 PDU に流したくなった場合は、`sensors.yaml` から MJCF `<sensor>` を生成する方向で拡張できる。

---

## なぜ actuator は MJCF に入れるのか

actuator は、MuJoCo の物理シミュレーションを外部から駆動するために必要である。

たとえば TB3 では、左右の wheel joint を外部 PDU から制御するために actuator が必要になる。

```text
wheel_left_joint / wheel_right_joint
    ↓
actuator
    ↓
Hakoniwa PDU から制御入力
    ↓
MuJoCo 上でロボットが動く
```

一方で sensor は、観測値をどう扱うか、どう可視化するか、どの PDU に流すかという意味づけであり、必ずしも MJCF に埋め込む必要はない。

したがって、基本方針は以下とする。

```text
actuator:
  物理シミュレーションを外部から駆動する入口
  → MJCF に注入する

sensor:
  観測・可視化・PDU変換の意味づけ
  → sensors.yaml として後付けする
```

---

## Hakoniwa Robot Viewer Model v0.1 案

### 目的

ゲームエンジン上にロボットを再構築するための軽量な中間モデルを定義する。

### 対象

v0.1 では以下を対象とする。

```text
対象:
  - base
  - movable_parts
  - sensors
  - GLB visual assets
  - PDU binding

対象外:
  - inertia
  - collision
  - actuator dynamics
  - full physics
  - material system
  - lighting
  - full scene description
```

### 例

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
      "id": "burger_base",
      "type": "glb",
      "path": "meshes/burger_base.glb"
    },
    {
      "id": "left_tire",
      "type": "glb",
      "path": "meshes/left_tire.glb"
    },
    {
      "id": "right_tire",
      "type": "glb",
      "path": "meshes/right_tire.glb"
    },
    {
      "id": "lds",
      "type": "glb",
      "path": "meshes/lds.glb"
    }
  ],

  "base": {
    "name": "base_link",
    "asset": "burger_base",
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
      "asset": "left_tire",
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
      "asset": "right_tire",
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

  "sensors": [
    {
      "name": "lidar",
      "type": "lidar_2d",
      "body": "base_scan",
      "parent": "base_link",
      "asset": "lds",
      "mount": {
        "xyz": [-0.032, 0.0, 0.172],
        "rpy": [0.0, 0.0, 0.0]
      },
      "spec": "sensors/lds_01.yaml",
      "pdu": "tb3_scan"
    },
    {
      "name": "imu",
      "type": "imu",
      "body": "imu_link",
      "parent": "base_link",
      "mount": {
        "xyz": [-0.032, 0.0, 0.068],
        "rpy": [0.0, 0.0, 0.0]
      },
      "spec": "sensors/imu.yaml",
      "pdu": "tb3_imu"
    }
  ]
}
```

---

## Viewer Recipe v0.1 案

Viewer Recipe は、人間が編集する薄い YAML である。

これは Viewer Model そのものではなく、MJCF から Viewer Model を生成するための selector / hint である。

### 設計原則

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

### 例

```yaml
format: hako_viewer_model_recipe
version: 0.1

robot: turtlebot3_burger
mjcf: turtlebot3_burger.actuated.xml

assets:
  glb_dir: meshes
  map: mesh_name

base: base_link

movables:
  - wheel_left_joint
  - wheel_right_joint

sensors: sensors.yaml
```

### assets.map

`assets.map` は、MJCF の mesh 名または body 名と GLB ファイルの対応規則を指定する。

```yaml
assets:
  glb_dir: meshes
  map: mesh_name
```

必要に応じて override を許す。

```yaml
assets:
  glb_dir: meshes
  map: mesh_name
  overrides:
    burger_base: turtlebot3_burger_base.glb
    left_tire: wheel_left.glb
```

---

## sensors.yaml v0.1 案

`sensors.yaml` は、MJCF 上の body / site にセンサーとしての意味を与える。

位置姿勢は MJCF から取得するため、基本的にはここには書かない。

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

site を使う場合は以下とする。

```yaml
sensors:
  - name: front_camera
    type: camera
    site: front_camera_site
    spec: sensors/front_camera.yaml
    pdu: front_camera_image
```

---

## Generator 構想

### 全体フロー

```text
MJCF
actuators.yaml
sensors.yaml
viewer.recipe.yaml
GLB assets
        ↓
hako-viewer-model-gen
        ↓
hako_viewer_model.json
        ↓
hako-godot-scene-gen
        ↓
Godot .tscn
```

### hako-viewer-model-gen

`hako-viewer-model-gen` は、MJCF と recipe を入力として Viewer Model を生成する。

```bash
hako-viewer-model-gen \
  --recipe tb3.viewer.recipe.yaml \
  --out hako_viewer_model.json
```

または、

```bash
hako-viewer-model-gen tb3.viewer.recipe.yaml
```

#### 入力

```text
- viewer.recipe.yaml
- MJCF
- sensors.yaml
- GLB directory
```

#### 出力

```text
- hako_viewer_model.json
```

#### 生成器が MJCF から取得するもの

```text
- body hierarchy
- body pos / quat / euler
- joint type / axis / range
- geom / mesh name
- sensor body / site transform
```

#### recipe から取得するもの

```text
- robot name
- MJCF path
- base body name
- movable joint list
- sensors.yaml path
- asset mapping rule
- PDU names
```

---

## Godot Generator 構想

最初の backend は Godot とする。

### 入力

```text
hako_viewer_model.json
```

### 出力

```text
TB3.generated.tscn
tb3_sync.gd
```

### 生成される Godot scene の例

```text
TB3
  HakoSync
  Visuals
    base_link
      wheel_left_link
      wheel_right_link
      base_scan
      imu_link
```

### 変換方針

Godot generator は、Viewer Model の ROS 座標系を Godot 座標系へ変換する。

座標系差異は recipe に書かせない。

```text
hako_viewer_model:
  ROS coordinate

Godot generator:
  ROS → Godot 変換を担当
```

### 最初の実装範囲

v0.1 の Godot generator は、以下のみを対象とする。

```text
対応:
  - base Node3D
  - movable part Node3D
  - GLB instance
  - wheel / rotor の continuous rotation
  - base pose PDU binding
  - joint_state PDU binding

未対応:
  - collision
  - physics body
  - material tuning
  - sensor rendering
  - OpenUSD export
```

### 生成される scene の概念

```text
TB3
  HakoSync
    - pose PDU subscriber
    - joint_state PDU subscriber
  Visuals
    base_link
      burger_base.glb
      wheel_left_link
        left_tire.glb
      wheel_right_link
        right_tire.glb
      base_scan
        lds.glb
```

Godot 側では物理を行わない。

物理の正は MuJoCo とし、Godot は viewer / UI / interaction の役割を担う。

---

## OpenUSD への将来拡張

Hakoniwa Robot Viewer Model は、将来的に OpenUSD へ変換可能な構造を保つ。

### 対応イメージ

```text
hako_viewer_model.robot.root
  → USD root Prim

base
  → USD Xform / root link Prim

movable_parts
  → USD Xform + joint / articulation mapping

assets
  → USD asset reference / payload / converted mesh

sensors
  → sensor mount Prim / Isaac Sim sensor Prim

godot_sync.yaml / pdu-manifest.yaml
  → Hakoniwa runtime / communication metadata
```

### 方針

OpenUSD は高機能な scene description format である。

Hakoniwa Robot Viewer Model は、その完全な代替ではなく、OpenUSD へシームレスに変換できる軽量な前段モデルとする。

```text
hako_viewer_model.json
    ↓
OpenUSD exporter
    ↓
robot.usda
```

OpenUSD 変換を見据えて、以下の情報は Viewer Model に保持する。

```text
- parent-child hierarchy
- asset reference
- mount transform
- movable joint
- sensor mount
```

---

## v0.1 の実装ステップ

### Step 1: TB3 用 viewer.recipe.yaml を作成

```yaml
format: hako_viewer_model_recipe
version: 0.1

robot: turtlebot3_burger
mjcf: turtlebot3_burger.actuated.xml

assets:
  glb_dir: meshes
  map: mesh_name

base: base_link

movables:
  - wheel_left_joint
  - wheel_right_joint

sensors: sensors.yaml
```

### Step 2: sensors.yaml を作成

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

### Step 3: hako-viewer-model-gen を実装

まずは以下だけでよい。

```text
- MJCF XML parse
- body tree parse
- joint lookup
- geom mesh lookup
- body transform extraction
- sensor body lookup
- hako_viewer_model.json output
```

### Step 4: Godot .tscn generator を実装

```text
- hako_viewer_model.json を読む
- Godot Node3D tree を生成
- GLB を instance として参照
- movable_part に初期 transform を設定
- PDU sync 用 script を attach
```

### Step 5: TB3 で検証

```text
- base_link が表示される
- wheel_left_link / wheel_right_link が正しい位置に表示される
- wheel joint_state PDU で車輪が回る
- base pose PDU でロボット全体が移動する
- base_scan / imu_link が sensor mount として展開される
```

---

## まとめ

Hakoniwa Robot Viewer Model は、物理モデルでも、URDF の代替でも、OpenUSD の代替でもない。

これは、MJCF と GLB と箱庭 PDU を、ゲームエンジンや OpenUSD に接続するための軽量な viewer-oriented 中間モデルである。

```text
MJCF:
  物理の正

GLB:
  見た目の正

actuators.yaml:
  外部制御入力の意味づけ

sensors.yaml:
  観測・センサー・PDU出力の意味づけ

viewer.recipe.yaml:
  MJCFからViewer Modelを生成するための薄いselector

hako_viewer_model.json:
  Godot / three.js / Unity / OpenUSD へ渡す完全展開済み中間モデル
```

最初の実装対象は Godot と TB3 とし、将来的に three.js / Unity / OpenUSD へ展開する。

この構造により、箱庭は URDF 資産と MuJoCo 物理、GLB 可視化、PDU 通信、ゲームエンジンビューア、そして OpenUSD 系デジタルツイン基盤を接続するための軽量な橋渡しを提供できる。
