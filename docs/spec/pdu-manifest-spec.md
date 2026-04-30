# Hakoniwa PDU Manifest YAML v0.1 Specification

## 目的

本ドキュメントは、`hakoniwa-mbody-registry` における
**`pdu-manifest.yaml` の v0.1 仕様案**を整理する。

対象は以下である。

1. `pdu-manifest.yaml` の役割
2. `bodies` / `sensors` / `extras` の責務分離
3. `pdutypes.json` / `pdu_def.json` / endpoint / profile 生成との関係
4. `pdu-manifest.yaml` の YAML 仕様
5. `channel_id` と `pdu_size` の基本方針

本仕様の目的は、robot ごとの PDU 契約を
1 つの正規入力で定義し、
そこから runtime ごとの生成物を一貫して得られるようにすることである。

---

## 背景

これまで議論に出てきた入力は、概念的に以下へ分かれていた。

- body / joint 系の状態出力
- sensor 系の出力
- Godot sync 用の runtime 反映設定

これらを個別ファイルに切りすぎると、

- 入口が増える
- channel_id の整合が崩れやすい
- `pdutypes.json` / `pdu_def.json` の canonical 性が弱くなる

という問題が出る。

一方で、全部を flat に 1 層で持つと、

- endpoint 生成で必要なもの
- canonical PDU に入るもの
- runtime 実装だけが気にするもの

の境界が曖昧になる。

そのため、`pdu-manifest.yaml` を
**1 つの正規入力**としつつ、
内部を階層で分ける方針を採る。
また、`bodies` / `sensors` に素直に入らない entry は
`extras` で受ける。

---

## 基本方針

### 1. `pdu-manifest.yaml` は PDU 契約の正とする

`pdu-manifest.yaml` は、
robot が外部とやり取りする PDU 契約の正規入力である。

ここから少なくとも以下を生成する。

- `pdutypes.json`
- `pdu_def.json`
- Godot 用 internal endpoint JSON
- Godot 用 runtime profile JSON

### 2. `bodies` と `sensors` を分ける

`pdu-manifest.yaml` は v0.1 では最低限、
次の 3 階層を持つ。

- `bodies`
- `sensors`
- `extras`

#### `bodies`

対象:

- base pose
- joint_states

用途:

- canonical PDU 定義に入る
- Godot sync が主に consume する
- Godot internal endpoint 生成に使う

#### `sensors`

対象:

- scan
- imu
- odometry
- 将来の各種 sensor output

用途:

- canonical PDU 定義に入る
- MuJoCo などの runtime が主に publish / consume する
- Godot internal endpoint 生成では通常使わない

#### `extras`

対象:

- command 系
- 補助 pose 系
- `tf` のような補助 publish 系
- その他、`bodies` / `sensors` に素直に収まらない entry

用途:

- canonical PDU 定義に入る
- 既存の動作済み `pdutypes.json` との互換維持に使う
- Godot internal endpoint 生成では通常使わない

### 3. endpoint 生成は `bodies` だけを見る

Godot 用 internal SHM poll endpoint の初期生成では、
通常 `bodies` セクションだけを使う。

理由:

- Godot sync v0.1 が必要とするのは base pose と joint_states だから
- sensor 出力は canonical 定義には入るが、
  Godot internal endpoint に必須ではないから

### 4. runtime 詳細設定はここへ入れすぎない

`pdu-manifest.yaml` は PDU 契約の正であり、
MuJoCo runtime のノイズモデルや update loop 実装詳細の正ではない。

したがって:

- sensor の意味
- PDU 名
- message type

は持つが、

- detailed sensor runtime behavior
- actuator control algorithm
- comm backend 実装詳細

までは持ちすぎない方針とする。

---

## 全体像

```text
viewer.recipe.yaml
godot_sync.yaml
pdu-manifest.yaml
MJCF
GLB assets

    ↓ generator

pdutypes.json
pdu_def.json
endpoint_shm_with_pdu.json
robot_sync.profile.json
Godot .tscn
```

責務分離:

- `viewer.recipe.yaml`
  - engine-independent viewer 構造
- `godot_sync.yaml`
  - Godot runtime 反映設定
- `pdu-manifest.yaml`
  - robot PDU 契約

---

# 1. `pdu-manifest.yaml` v0.1 仕様

## 1.1 最小例

```yaml
format: hako_pdu_manifest
version: 0.1

robot_name: TB3

bodies:
  base:
    pdu_name: base_link_pos
    pdu_type: geometry_msgs/Twist
    body_name: base_link
    channel_id: 1

  joints:
    pdu_name: joint_states
    pdu_type: sensor_msgs/JointState
    channel_id: 5
    joint_names:
      - wheel_left_joint
      - wheel_right_joint

sensors:
  - name: lidar
    pdu_name: laser_scan
    pdu_type: sensor_msgs/LaserScan
    channel_id: 3
    body_name: base_scan

  - name: imu
    pdu_name: imu
    pdu_type: sensor_msgs/Imu
    channel_id: 4
    body_name: imu_link

  - name: odometry
    pdu_name: odom
    pdu_type: nav_msgs/Odometry
    channel_id: 6
    body_name: base_link

extras:
  - name: game_controller_command
    pdu_name: hako_cmd_game
    pdu_type: hako_msgs/GameControllerOperation
    channel_id: 0

  - name: base_scan_pose
    pdu_name: base_scan_pos
    pdu_type: geometry_msgs/Twist
    channel_id: 2
    body_name: base_scan

  - name: tf
    pdu_name: tf
    pdu_type: tf2_msgs/TFMessage
    channel_id: 7
```

## 1.2 フィールド仕様

### `format`

```yaml
format: hako_pdu_manifest
```

ファイル種別を示す文字列。

v0.1 では `hako_pdu_manifest` を指定する。

### `version`

```yaml
version: 0.1
```

仕様バージョン。

### `robot_name`

```yaml
robot_name: TB3
```

対象 robot 名。

### `bodies`

body / joint 系の状態 PDU を定義する。

v0.1 では以下の 2 セクションを持つ。

- `base`
- `joints`

#### `bodies.base`

robot 全体の位置姿勢を表す base 系 PDU。

必須:

- `pdu_name`
- `pdu_type`
- `body_name`

任意:

- `channel_id`
- `pdu_size`

#### `bodies.joints`

joint 状態を表す PDU。

必須:

- `pdu_name`
- `pdu_type`
- `joint_names`

任意:

- `channel_id`
- `pdu_size`

### `sensors`

sensor 系 PDU の配列。

各要素の必須項目:

- `name`
- `pdu_name`
- `pdu_type`

また mount 対象として少なくとも 1 つ必要:

- `body_name`
  または
- `site_name`

任意:

- `channel_id`
- `pdu_size`

### `extras`

補助的な PDU entry の配列。

各要素の必須項目:

- `name`
- `pdu_name`
- `pdu_type`

任意:

- `body_name`
- `site_name`
- `channel_id`
- `pdu_size`

---

# 2. `bodies` セクション

## 2.1 役割

`bodies` は、変化点として同期する
body / joint 系の最小状態を定義する。

v0.1 では:

- base pose
- joint_states

を扱う。

## 2.2 endpoint 生成との関係

Godot 用 internal SHM poll endpoint の初期生成は、
通常この `bodies` セクションのみを見る。

したがって、

- `base_link_pos`
- `joint_states`

が Godot endpoint の標準入力になる。

## 2.3 NodePath は持たない

`bodies` は PDU 契約を定義するだけであり、
Godot の final NodePath は持たない。

NodePath 解決は:

- scene generator
- `godot_sync.yaml`
- generated profile

側の責務とする。

---

# 3. `sensors` セクション

## 3.1 役割

`sensors` は sensor 系 PDU を定義する。

対象例:

- `scan`
- `imu`
- `odometry`

## 3.2 `bodies` との違い

`bodies` は robot の状態変化そのものを扱う。

`sensors` は、sensor として意味づけられた観測出力を扱う。

そのため、

- canonical `pdutypes.json` / `pdu_def.json` には入る
- Godot internal endpoint には通常入れない

という運用が可能である。

## 3.3 runtime 詳細との関係

MuJoCo 側に既存の sensor schema / runtime 設定がある場合、
それを source of truth としてよい。

この `sensors` セクションでは、
少なくとも canonical PDU 契約に必要な最小事項だけを持てばよい。

例:

- `pdu_name`
- `pdu_type`
- `body_name` / `site_name`

---

# 4. `extras` セクション

## 4.1 役割

`extras` は、`bodies` と `sensors` へ直接分類しにくい
PDU entry を扱う。

代表例:

- `hako_cmd_game`
- `base_scan_pos`
- `tf`

## 4.2 使いどころ

`extras` は、既存 runtime と互換性を保ちながら
manifest を 1 本化したいときの逃げ道である。

そのため v0.1 では、
entry の意味を厳密に一般化するよりも、
canonical `pdutypes.json` と `pdu_def.json` を壊さずに
表現できることを優先する。

## 4.3 endpoint 生成との関係

Godot 用 internal endpoint の初期生成では、
通常 `extras` は使わない。

将来的に command 系 endpoint や補助 pose 系 endpoint が必要なら、
その時点で consumer ごとの生成規則を拡張する。

---

# 5. `pdu_size` 方針

## 5.1 基本方針

利用者に `pdu_size` の手計算を強制しない。

known な標準 message 型については、
generator が size registry から補完してよい。

参照例:

```text
hakoniwa_pdu.pdu_msgs.pdu_size.PDU_SIZE
```

## 5.2 解決順

各 entry の `pdu_size` は以下の順で決める。

1. manifest に明示値があるならそれを使う
2. `pdu_type` が registry に存在するならその値を使う
3. 存在しない場合は `null` または `auto` を許容する

## 5.3 既知型の例

- `geometry_msgs/Twist`
- `sensor_msgs/JointState`
- `sensor_msgs/LaserScan`
- `sensor_msgs/Imu`
- `nav_msgs/Odometry`

---

# 6. `channel_id` 方針

## 6.1 原則

`channel_id` は runtime ごとにズレてはならない。

したがって `pdu-manifest.yaml` から生成される canonical 定義では、
`channel_id` は以下を満たす必要がある。

- deterministic
- stable
- consumer 非依存

## 6.2 v0.1 の扱い

v0.1 では各 entry に `channel_id` を明示的に持たせてよい。

generator は明示値を優先する。

将来的には自動割り当て規則を別仕様として定義してよいが、
少なくとも既存の動作済み `pdutypes.json` / `pdu_def.json` と
一致することを優先する。

---

# 7. 生成物との対応

## 7.1 canonical 生成物

`pdu-manifest.yaml` から生成される canonical 生成物:

- `pdutypes.json`
- `pdu_def.json`

入力範囲:

- `bodies`
- `sensors`
- `extras`

## 7.2 Godot 用生成物

Godot 用生成物:

- `endpoint_shm_with_pdu.json`
- `robot_sync.profile.json`

入力範囲:

- endpoint JSON
  - 主に `bodies`
- runtime profile
  - `bodies`
  - `godot_sync.yaml`

## 7.3 MuJoCo 用 runtime

MuJoCo などは canonical 生成物全体を利用できる。

つまり:

- `bodies`
- `sensors`
- `extras`

の全てを含む PDU 定義を consume / publish できる。

---

# 8. 既存ファイルとの関係

v0.1 の整理としては以下を想定する。

- `pdu_bodies.yaml`
  - `pdu-manifest.yaml` の `bodies` へ統合される方向
- `sensors.yaml`
  - `pdu-manifest.yaml` の `sensors` へ統合される方向
- `godot_sync.yaml`
  - そのまま別責務として維持

つまり最終的な責務は:

- `viewer.recipe.yaml`
- `godot_sync.yaml`
- `pdu-manifest.yaml`

の 3 本へ寄せる。

---

# 9. TB3 例

TB3 の最小例:

```yaml
format: hako_pdu_manifest
version: 0.1

robot_name: TB3

bodies:
  base:
    pdu_name: base_link_pos
    pdu_type: geometry_msgs/Twist
    body_name: base_link
    channel_id: 1

  joints:
    pdu_name: joint_states
    pdu_type: sensor_msgs/JointState
    channel_id: 5
    joint_names:
      - wheel_left_joint
      - wheel_right_joint

sensors:
  - name: lidar
    pdu_name: laser_scan
    pdu_type: sensor_msgs/LaserScan
    channel_id: 3
    body_name: base_scan

  - name: imu
    pdu_name: imu
    pdu_type: sensor_msgs/Imu
    channel_id: 4
    body_name: imu_link

  - name: odometry
    pdu_name: odom
    pdu_type: nav_msgs/Odometry
    channel_id: 6
    body_name: base_link

extras:
  - name: game_controller_command
    pdu_name: hako_cmd_game
    pdu_type: hako_msgs/GameControllerOperation
    channel_id: 0

  - name: base_scan_pose
    pdu_name: base_scan_pos
    pdu_type: geometry_msgs/Twist
    channel_id: 2
    body_name: base_scan

  - name: tf
    pdu_name: tf
    pdu_type: tf2_msgs/TFMessage
    channel_id: 7
```

注記:

- 上記の `channel_id` と PDU 名は、既存の動作済み TB3 用
  `pdutypes.json` に合わせる
- `hako_cmd_game`, `base_scan_pos`, `tf` は `extras` で扱う
- `extras` は既存 config 互換を保つための補助 entry 置き場である

---

# 10. まとめ

`pdu-manifest.yaml` は、
robot の PDU 契約を 1 つの正規入力にまとめるための manifest である。

重要な方針は以下である。

```text
bodies と sensors を階層で分ける。
分類しにくい entry は extras で受ける。
canonical pdutypes / pdu_def は 3 つから作る。
Godot endpoint は主に bodies だけを見る。
pdu_size は known type なら registry から補完する。
channel_id は stable な canonical 値に固定する。
```
