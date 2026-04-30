# Hakoniwa Godot Sync YAML v0.1 Specification

## 目的

本ドキュメントは、`hakoniwa-mbody-registry` における
**`godot_sync.yaml` の v0.1 仕様案**を整理する。

対象は以下である。

1. `godot_sync.yaml` の役割
2. `viewer.recipe.yaml` との責務分離
3. `godot_sync.yaml` の YAML 仕様
4. `godot_sync.yaml` から生成される Godot 用 profile の位置づけ
5. 現在想定している generator の変換責務

本仕様の目的は、Godot 固有の runtime 反映設定を
`hakoniwa-godot` 側へ分散させず、
`hakoniwa-mbody-registry` を入口として完結させることである。

---

## 背景

`hakoniwa-mbody-registry` では、既に以下の生成パイプラインを持つ。

```text
URDF / xacro
  ↓
MJCF
  ↓
GLB assets
  ↓
hako_viewer_model.json
  ↓
Godot .tscn
```

ここで Godot scene の自動生成まではできるが、
Hakoniwa / ROS 系 PDU を用いて
robot state を scene node に反映するためには、
追加で以下の情報が必要になる。

- base pose に使う PDU 名
- joint_states に使う PDU 名
- 同期対象 joint 名
- body と joint の意味対応
- joint 回転軸
- 符号
- 初期オフセット
- 利用する座標変換 rule
- sensor 出力に使う PDU 名

これらは engine 固有であり、
`viewer.recipe.yaml` に混ぜると recipe の中立性が崩れる。

一方で、これらを `hakoniwa-godot` 側で手書きさせると、
robot 定義の入口が 2 つに分かれ、利用者負担が増える。

そこで、
**`hakoniwa-mbody-registry` 側に Godot 用 overlay 入力として `godot_sync.yaml` を置き、
そこから最終的な runtime profile を生成する**
方針を採る。

---

## 同期対象の原則

Godot sync v0.1 では、runtime で PDU 同期する対象を
**変化点だけ**に限定する。

対象:

- base pose
- joint_states
- sensor outputs
  - scan
  - imu
  - odometry

対象外:

- 固定 body の個別 pose
- wheel link など可動部 body の個別 pose
- sensor mount の固定 transform

理由:

- 固定構造は URDF / MJCF / generated scene hierarchy に既に含まれている
- runtime で毎 step 送るべきなのは、robot の状態変化だけでよい
- PDU を body ごとに増やすと設定も通信量も不要に増える

したがって、Godot sync 用の初期生成対象は原則として

- `base_link_pos` のような base 用 PDU
- `joint_states` のような joint 用 PDU

の 2 系統に絞る。

一方、robot 全体の canonical PDU 定義としては、
MuJoCo などの runtime が必要とする sensor 出力も含みうる。

つまり:

- Godot sync が consume する最小 subset
  - base pose
  - joint_states
- canonical robot PDU set
  - base pose
  - joint_states
  - sensor outputs

を区別する。

---

## 基本方針

### 1. `viewer.recipe.yaml` は engine-independent のまま保つ

`viewer.recipe.yaml` は Viewer Model のための中立 recipe である。

したがって以下のような engine 固有事項は原則として持たせない。

- Godot の NodePath
- Godot scene root 名
- Godot script 名
- Godot runtime 固有の同期設定

### 2. `godot_sync.yaml` は Godot 用 overlay とする

`godot_sync.yaml` は、Godot runtime 反映に必要な
最小限の意味づけだけを持つ。

```text
viewer.recipe.yaml
  engine-independent

godot_sync.yaml
  Godot runtime sync 用の overlay
```

この v0.1 仕様では、同期対象 PDU も

- base pose
- joint_states

に限定する。

### 3. 利用者には NodePath を書かせない

Godot scene generator は現在、`RosToGodot/Visuals/...` のような
命名規則で node を生成する。

このような generator 都合の path を
利用者が直接書くのは避けたい。

したがって、`godot_sync.yaml` では原則として

- `joint_name`
- `body_name`

を書かせ、最終的な `node_path` は generator が scene 生成規則から確定する。

### 4. `hakoniwa-godot` は generated profile consumer に徹する

`hakoniwa-godot` 側では robot 固有設定を持たない。

責務は以下に限定する。

- 生成済み profile JSON を読む
- `HakoniwaSimNode` / endpoint / codec を使って受信する
- scene node に反映する

---

## ファイル配置

想定する配置:

```text
bodies/<robot>/
  config/
    viewer.recipe.yaml
    godot_sync.yaml
  generated/
    <robot>.urdf
    <robot>.xml
    parts/*.glb
    godot/
      robot_sync.profile.json
```

ここで:

- `viewer.recipe.yaml`
  - Viewer Model / scene 生成の入口
- `godot_sync.yaml`
  - Godot runtime sync 情報の入口
- `robot_sync.profile.json`
  - `hakoniwa-godot` が読む最終生成物

---

## 全体フロー

```text
viewer.recipe.yaml
godot_sync.yaml
MJCF
GLB assets

    ↓ generator

hako_viewer_model.json
Godot .tscn
robot_sync.profile.json
```

整理すると:

- scene 構造は Viewer Model / scene generator が決める
- runtime sync 情報は `godot_sync.yaml` が与える
- 両者を結合して最終 profile JSON を作る

---

# 1. `godot_sync.yaml` v0.1 仕様

## 1.1 目的

`godot_sync.yaml` は、Godot scene 上で robot state を反映するための
薄い overlay 定義である。

役割は以下に限定する。

- PDU 名の指定
- 同期対象 joint の指定
- joint 回転ルールの指定
- 利用する座標変換 rule の指定
- endpoint 生成に必要な可変部分の指定

ここで扱う PDU は v0.1 では

- base pose 用
- joint_states 用

に限定する。

## 1.2 設計原則

```text
MJCF にある情報:
  書かない

scene generator が決められる情報:
  書かない

利用者しか決められない意味づけ:
  書く
```

具体的には:

- body hierarchy
- mount transform
- parent-child structure
- GLB path
- 最終 NodePath

は `godot_sync.yaml` に書かない。

また、個別 body pose を同期対象として列挙する用途にも使わない。
sensor 出力そのものの定義にも使わない。

## 1.3 最小例

```yaml
format: hako_godot_sync
version: 0.1

robot_name: TB3

pdu:
  base: base_link_pos
  joints: joint_states

coordinate_system:
  position_rule: hakoniwa_to_godot
  rotation_rule: hakoniwa_to_godot

endpoint:
  comm_path: ../comm/shm_poll_comm.json
  endpoint_name: tb3_godot_endpoint

joints:
  - joint_name: wheel_left_joint
    body_name: wheel_left_link
    axis: z
    sign: 1.0
    offset_rad: 0.0

  - joint_name: wheel_right_joint
    body_name: wheel_right_link
    axis: z
    sign: 1.0
    offset_rad: 0.0
```

## 1.4 フィールド仕様

### `format`

```yaml
format: hako_godot_sync
```

設定ファイル種別を示す文字列。

v0.1 では `hako_godot_sync` を指定する。

### `version`

```yaml
version: 0.1
```

仕様バージョン。

### `robot_name`

```yaml
robot_name: TB3
```

Hakoniwa / PDU 側で使う robot 名。

これは `HakoniwaTypedEndpoint` を bind する際の
`robot` 引数に相当する。

### `pdu`

```yaml
pdu:
  base: base_link_pos
  joints: joint_states
```

runtime 同期で使う PDU 名を指定する。

#### `pdu.base`

base body pose に使う PDU 名。

例:

- `base_link_pos`
- `pose`
- `odom_pose`

#### `pdu.joints`

joint 状態に使う PDU 名。

例:

- `joint_states`
- `actuator_state`

### `coordinate_system`

```yaml
coordinate_system:
  position_rule: hakoniwa_to_godot
  rotation_rule: hakoniwa_to_godot
```

利用する座標変換 rule 名。

自由な行列や式は書かせず、generator / runtime が知っている rule 名だけを許可する。

#### `coordinate_system.position_rule`

position 変換 rule。

候補例:

- `identity`
- `hakoniwa_to_godot`
- `ros_to_godot`

#### `coordinate_system.rotation_rule`

rotation 変換 rule。

候補例:

- `identity`
- `hakoniwa_to_godot`
- `ros_to_godot`

### `joints`

```yaml
joints:
  - joint_name: wheel_left_joint
    body_name: wheel_left_link
    axis: z
    sign: 1.0
    offset_rad: 0.0
```

joint 同期対象の配列。

各要素の意味は以下。

#### `joint_name`

`sensor_msgs/JointState.name[]` に現れる joint 名。

#### `body_name`

scene generator が作る body node の元になる body 名。

利用者には final NodePath を書かせず、
scene 生成規則から `body_name -> node_path` を解決する。

#### `axis`

回転軸。

許容値:

- `x`
- `y`
- `z`

#### `sign`

符号。

通常は:

- `1.0`
- `-1.0`

#### `offset_rad`

joint angle に加算する初期オフセット値。

式:

```text
applied_angle = sign * joint_position + offset_rad
```

### `endpoint`

```yaml
endpoint:
  comm_path: ../comm/shm_poll_comm.json
  endpoint_name: tb3_godot_endpoint
```

Godot 用 internal endpoint 生成に必要な可変部分だけを指定する。

v0.1 では endpoint JSON 全体を利用者に書かせず、
generator が固定骨格を持ち、ここに与えられた値を埋め込む。

#### `endpoint.comm_path`

Godot internal SHM poll endpoint が参照する comm 設定 JSON のパス。

相対パスの場合は、`godot_sync.yaml` のあるディレクトリから解釈する。

初期前提:

- SHM
- poll

そのため v0.1 では事実上 `shm_poll_comm.json` を指す運用を想定する。

#### `endpoint.endpoint_name`

生成される endpoint JSON に埋め込む endpoint 名。

用途:

- runtime 識別
- log / debug 表示

これは省略可能としてもよいが、v0.1 の仕様書では明示項目として置く。

## 1.5 必須項目

v0.1 で必須とするのは以下。

- `format`
- `version`
- `robot_name`
- `pdu`
- `pdu.base`
- `pdu.joints`
- `coordinate_system`
- `coordinate_system.position_rule`
- `coordinate_system.rotation_rule`
- `endpoint`
- `endpoint.comm_path`
- `endpoint.endpoint_name`
- `joints`

また `joints` は空配列を許可しない。

## 1.6 v0.1 で持たせないもの

以下は v0.1 では持たせない。

- Godot の final `node_path`
- scene root 名
- `RosToGodot` のような generator 内部 node 名
- 任意スクリプト
- 任意式
- 直接的な transform 行列

理由:

- scene generator の内部都合を利用者へ露出させたくない
- runtime が任意式を評価する設計を避けたい
- engine 固有構造の変更耐性を保ちたい

---

# 2. `robot_sync.profile.json` との対応

## 2.1 位置づけ

`robot_sync.profile.json` は、`godot_sync.yaml` と scene 生成規則から得られる
**最終生成物**である。

これは利用者が手編集する一次設定ではない。

`hakoniwa-godot` の `HakoniwaRobotSyncController` は
この JSON を読んで動作する。

## 2.2 生成時に解決されるもの

`godot_sync.yaml` からそのまま渡るもの:

- `robot_name`
- `base_link_pdu_name`
- `joint_states_pdu_name`
- `coordinate_system`
- `endpoint.comm_path`
- `endpoint.endpoint_name`
- `joint_name`
- `axis`
- `sign`
- `offset_rad`

generator が補完するもの:

- `base_node_path`
- `joint_mappings[].node_path`
- scene 生成規則に依存する root-relative path
- Godot internal SHM poll endpoint JSON の固定骨格

## 2.3 生成例

```json
{
  "version": 1,
  "robot_name": "TB3",
  "base_link_pdu_name": "base_link_pos",
  "joint_states_pdu_name": "joint_states",
  "base_node_path": "Visuals/base_link",
  "coordinate_system": {
    "position_rule": "hakoniwa_to_godot",
    "rotation_rule": "hakoniwa_to_godot"
  },
  "joint_mappings": [
    {
      "joint_name": "wheel_left_joint",
      "node_path": "Visuals/base_link/wheel_left_link",
      "axis": "z",
      "sign": 1.0,
      "offset_rad": 0.0,
      "apply_mode": "basis_delta"
    },
    {
      "joint_name": "wheel_right_joint",
      "node_path": "Visuals/base_link/wheel_right_link",
      "axis": "z",
      "sign": 1.0,
      "offset_rad": 0.0,
      "apply_mode": "basis_delta"
    }
  ]
}
```

ここで `Visuals/...` のような path は、
controller の `target_root_path` 基準の相対 path として扱う。

---

# 3. Generator の責務

`godot_sync.yaml` を読む generator は、少なくとも以下を担う。

## 3.1 YAML validation

- 必須項目の存在確認
- 型確認
- `axis` の許容値確認
- `sign` の型確認
- `joints` 非空確認
- `endpoint.comm_path` の存在確認
- `endpoint.endpoint_name` の型確認

## 3.2 body 解決

- `body_name` が Viewer Model / scene 生成対象に存在するか確認する
- 見つからない場合は generation failure とする

## 3.3 path 解決

- `body_name` から final `node_path` を求める
- scene generator と同じ命名規則を使う

## 3.4 endpoint JSON 生成

generator は Godot 用 internal endpoint JSON も生成する。

v0.1 では以下を固定前提とする。

- internal endpoint
- SHM
- poll

したがって、利用者に全文を設定させず、
固定骨格 + 可変部分の差し込みで生成する。

可変部分:

- `robot_name`
- `pdu_def_path`
- `endpoint.comm_path`
- `endpoint.endpoint_name`

Godot sync 用としては、ここで生成する endpoint の対象 PDU も
原則として以下に絞る。

- base pose
- joint_states

## 3.5 profile JSON 出力

- `hakoniwa-godot` が直接読める JSON を出力する

---

# 4. `pdu_bodies.yaml` テンプレ生成方針

## 4.1 位置づけ

`pdu_bodies.yaml` は、Godot sync v0.1 では
**利用者が必ず最初から手書きする一次入力**とはみなさない。

代わりに、generator が以下から
**初期テンプレ**を生成できるようにする。

- `viewer.recipe.yaml`
- `godot_sync.yaml`
- MJCF

ただし生成後は、必要に応じて利用者が編集してよい。

したがって v0.1 での `pdu_bodies.yaml` の立場は以下である。

```text
default-generated template
  + user-overridable config
```

## 4.2 生成対象

Godot sync 用の初期テンプレでは、
PDU 対象を変化点だけに絞る。

生成対象:

- base pose 用 PDU
- joint_states 用 PDU

生成しないもの:

- fixed body ごとの pose PDU
- wheel_link ごとの pose PDU
- sensor mount ごとの pose PDU

## 4.3 初期テンプレの考え方

generator はまず、以下の最小構成を出せればよい。

```text
1. base
2. joints
```

base は robot 全体の位置姿勢同期に使う。

joints は `sensor_msgs/JointState` などの
joint 状態同期に使う。

この段階では、
body 一覧全部を `*_pos` PDU に展開する必要はない。

なお、canonical な `pdutypes.json` / `pdu_def.json` は、
この `pdu_bodies.yaml` だけで完結するとは限らない。

sensor 系 PDU は `sensors.yaml` 側から追加されうる。

## 4.4 手編集との関係

利用者は必要なら `pdu_bodies.yaml` に項目を追加できる。

例:

- 特定 sensor の pose を別 PDU にしたい
- base 以外の body pose も明示同期したい
- 既定の型や命名規則を変えたい

ただし、Godot sync v0.1 の標準運用では
それらは必須ではない。

## 4.5 運用ルール案

初期案:

1. `pdu_bodies.yaml` が存在しない場合
   - generator が初期テンプレを生成する
2. `pdu_bodies.yaml` が存在する場合
   - generator はそれを優先して利用する
3. 明示的な再生成オプションが指定された場合
   - generator はテンプレを再生成できる

この運用により、

- 初期導入は自動化できる
- 高度なケースでは利用者が手修正できる

という両立が可能になる。

## 4.6 テンプレ生成に必要な入力

base 用 PDU は主に以下から決まる。

- `godot_sync.yaml` の `robot_name`
- `godot_sync.yaml` の `pdu.base`

joint_states 用 PDU は主に以下から決まる。

- `godot_sync.yaml` の `pdu.joints`
- `godot_sync.yaml` の `joints[]`

テンプレ生成時には、少なくとも

- base pose PDU 名
- joint_states PDU 名
- 利用する message type

を確定できればよい。

sensor 系 PDU はここでは扱わず、別途 `sensors.yaml` から導出する。

## 4.7 v0.1 での割り切り

v0.1 では `pdu_bodies.yaml` の完全一般化は目指さない。

まずは:

- Godot sync が成立する最小テンプレ
- base + joint_states

だけを正しく出せればよい。

canonical PDU 全体の生成では、
これに `sensors.yaml` 由来の PDU を追加する。

---

# 5. `pdu_bodies.yaml` 最小形式

## 5.1 目的

Godot sync v0.1 に必要な `pdu_bodies.yaml` は、
robot の変化点を PDU として定義するための最小テンプレである。

ここで定義したいのは以下の 2 系統だけである。

- base pose
- joint_states

sensor 系は `sensors.yaml` から別途定義する。

## 5.2 設計原則

```text
最初から全 body を列挙しない。
固定 body は PDU 化しない。
変化点だけを PDU 化する。
```

したがって v0.1 の `pdu_bodies.yaml` では、

- `base`
- `joints`

の 2 セクションを持てばよい。

## 5.3 最小例

```yaml
format: hako_pdu_bodies
version: 0.1

robot_name: TB3

base:
  channel_id: 0
  name: base_link_pos
  type: geometry_msgs/Twist
  pdu_size: 72
  body_name: base_link

joints:
  channel_id: 1
  name: joint_states
  type: sensor_msgs/JointState
  pdu_size: auto
  joint_names:
    - wheel_left_joint
    - wheel_right_joint
```

## 5.4 フィールド仕様

### `format`

```yaml
format: hako_pdu_bodies
```

ファイル種別を示す文字列。

v0.1 では `hako_pdu_bodies` を指定する。

### `version`

```yaml
version: 0.1
```

仕様バージョン。

### `robot_name`

```yaml
robot_name: TB3
```

PDU 定義の対象 robot 名。

### `base`

```yaml
base:
  channel_id: 0
  name: base_link_pos
  type: geometry_msgs/Twist
  pdu_size: 72
  body_name: base_link
```

robot 全体の位置姿勢を表す base 用 PDU 定義。

#### `base.channel_id`

base 用 channel ID。

#### `base.name`

base 用 PDU 名。

#### `base.type`

base 用 message type。

v0.1 の既定例では `geometry_msgs/Twist` を使う。

#### `base.pdu_size`

base 用 PDU サイズ。

固定長型であれば数値を持つ。

v0.1 では、利用者に毎回 size を手計算させない方針を採る。

generator は、既知の標準 type については
`hakoniwa-pdu` の size registry を参照して補完してよい。

参照例:

```text
hakoniwa_pdu.pdu_msgs.pdu_size.PDU_SIZE
```

例えば `geometry_msgs/Twist` や `sensor_msgs/JointState` など、
registry に既知の型はそこから解決する。

registry に存在しない型は、

- `null`
- `auto`

のいずれかで一旦保持し、
downstream tool または別 generator 段階で解決する方針を許容する。

#### `base.body_name`

この base pose が表す body 名。

通常は `base_link`。

### `joints`

```yaml
joints:
  channel_id: 1
  name: joint_states
  type: sensor_msgs/JointState
  pdu_size: auto
  joint_names:
    - wheel_left_joint
    - wheel_right_joint
```

joint 状態をまとめて送る PDU 定義。

#### `joints.channel_id`

joint_states 用 channel ID。

#### `joints.name`

joint_states 用 PDU 名。

#### `joints.type`

joint 状態の message type。

v0.1 では `sensor_msgs/JointState` を想定する。

#### `joints.pdu_size`

joint_states 用 PDU サイズ。

可変長 message を扱うため、v0.1 では `auto` を許容する。

generator または downstream tool が実サイズ解決できない場合は、
別途既定値または codec 側 metadata から確定する。

#### `joints.joint_names`

この PDU に含める joint 名配列。

`godot_sync.yaml` に書かれた `joints[].joint_name` と整合する必要がある。

## 5.5 必須項目

v0.1 で必須とするのは以下。

- `format`
- `version`
- `robot_name`
- `base`
- `base.channel_id`
- `base.name`
- `base.type`
- `base.body_name`
- `joints`
- `joints.channel_id`
- `joints.name`
- `joints.type`
- `joints.joint_names`

また `joints.joint_names` は空配列を許可しない。

`pdu_size` は v0.1 では

- 明示指定
- registry 補完
- `auto` / `null`

のいずれかを許容するため、入力上の必須項目からは外す。

## 5.6 generator の初期値

`godot_sync.yaml` から初期テンプレを作る場合、generator は以下の既定を持ってよい。

- `base.channel_id = 0`
- `joints.channel_id = 1`
- `base.name = godot_sync.yaml.pdu.base`
- `joints.name = godot_sync.yaml.pdu.joints`
- `base.body_name = base_link`
- `joints.joint_names = godot_sync.yaml.joints[].joint_name`

message type の初期値:

- `base.type = geometry_msgs/Twist`
- `joints.type = sensor_msgs/JointState`

`pdu_size` の初期値解決順:

1. `pdu_bodies.yaml` に明示値があるならそれを使う
2. type が `hakoniwa-pdu` size registry に存在するならその値を使う
3. 可変長または未知型なら `auto` または `null` を入れる

## 5.7 編集可能テンプレとしての扱い

このファイルは generator が初期作成するが、
利用者は必要に応じて編集してよい。

想定される編集例:

- channel_id の変更
- PDU 名の変更
- message type の変更
- `pdu_size` の明示指定
- joint_names の追加 / 削除

ただし Godot sync v0.1 の標準 generator は、
この最小形式を前提に `pdutypes.json` / `pdu_def.json` / endpoint JSON を生成する。

---

# 6. `sensors.yaml` との関係

## 6.1 位置づけ

MuJoCo 側では、robot state だけでなく sensor 出力も publish する制約がある。

例:

- `scan`
- `imu`
- `odometry`

これらは body そのものではなく、
sensor としての意味づけを持つため、
`pdu_bodies.yaml` ではなく `sensors.yaml` 側で定義するのが自然である。

## 6.2 canonical PDU 定義との関係

canonical な `pdutypes.json` / `pdu_def.json` は、
少なくとも以下の 2 つの入力から作る。

- `pdu_bodies.yaml`
  - base pose
  - joint_states
- `sensors.yaml`
  - scan
  - imu
  - odometry

つまり:

```text
pdu_bodies.yaml
  -> state / joints

sensors.yaml
  -> sensor outputs

both
  -> canonical pdutypes.json / pdu_def.json
```

## 6.3 v0.1 での役割分担

Godot sync runtime が直接 consume するのは、原則として

- base pose
- joint_states

である。

一方 MuJoCo などの runtime は、
追加で sensor 系 PDU も publish / consume しうる。

そのため canonical PDU 定義は Godot subset より広くてよい。

---

# 7. TB3 例

TurtleBot3 での最小例:

```yaml
format: hako_godot_sync
version: 0.1

robot_name: TB3

pdu:
  base: base_link_pos
  joints: joint_states

coordinate_system:
  position_rule: hakoniwa_to_godot
  rotation_rule: hakoniwa_to_godot

endpoint:
  comm_path: ../comm/shm_poll_comm.json
  endpoint_name: tb3_godot_endpoint

joints:
  - joint_name: wheel_left_joint
    body_name: wheel_left_link
    axis: z
    sign: 1.0
    offset_rad: 0.0

  - joint_name: wheel_right_joint
    body_name: wheel_right_link
    axis: z
    sign: 1.0
    offset_rad: 0.0
```

これにより、scene generator が生成した

- `base_link`
- `wheel_left_link`
- `wheel_right_link`

へ runtime で反映できる profile JSON を出力する。

---

# 8. 将来拡張

将来追加したい候補:

- `apply_mode`
- velocity / effort 利用
- 複数 joint group
- fixed sensor mount の明示同期
- quaternion / euler の細分化 rule
- generator 依存 path 規則の schema 化

ただし v0.1 では、まず

- base pose
- joint_states
- wheel / arm / rotor のような単純 joint 反映
- Godot 用 internal SHM poll endpoint の自動生成

を成立させることを優先する。

---

# 9. まとめ

`godot_sync.yaml` は、

- `viewer.recipe.yaml` の中立性を壊さず
- `hakoniwa-mbody-registry` を利用者入口に保ち
- `hakoniwa-godot` を profile consumer に徹させる

ための薄い Godot overlay 入力である。

重要な方針は以下である。

```text
利用者には body_name / joint_name / PDU 名だけを書かせる。
NodePath は generator が決める。
endpoint JSON の骨格は generator が決める。
hakoniwa-godot は生成済み profile を読むだけにする。
runtime 同期対象は base pose と joint_states に絞る。
```
