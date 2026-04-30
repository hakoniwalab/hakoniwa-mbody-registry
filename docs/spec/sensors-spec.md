# Hakoniwa Sensors YAML v0.1 Specification

## 目的

本ドキュメントは、`hakoniwa-mbody-registry` における
**`sensors.yaml` の v0.1 仕様案**を整理する。

対象は以下である。

1. `sensors.yaml` の役割
2. MJCF / viewer recipe / Godot sync との責務分離
3. `sensors.yaml` の YAML 仕様
4. `pdutypes.json` / `pdu_def.json` 生成時の扱い
5. `pdu_size` の補完方針

本仕様の目的は、MuJoCo などの runtime が publish する
sensor 系 PDU を、body / joint 系の state PDU と分離して定義することである。

---

## 背景

robot の canonical PDU 定義には、少なくとも以下の 2 系統がある。

- body / joint 系
  - `base_link_pos`
  - `joint_states`
- sensor 系
  - `scan`
  - `imu`
  - `odometry`

このうち body / joint 系は `pdu_bodies.yaml` で扱えるが、
sensor 系は body 名だけでは意味が足りない。

必要になるのは例えば以下である。

- sensor の論理名
- sensor 種別
- mount 対象 body / site
- publish する PDU 名
- message type
- 必要なら sensor spec file

そのため、sensor 系は `pdu_bodies.yaml` に混ぜず、
`sensors.yaml` として独立定義する。

---

## 基本方針

### 1. `sensors.yaml` は sensor の意味づけを持つ

`sensors.yaml` は、MJCF 上の body / site に対して
「これは lidar である」「これは imu である」といった
**sensor としての意味づけ**を与える。

### 2. transform は MJCF を正とする

sensor の位置姿勢は MJCF 側の body / site から取得する。

したがって `sensors.yaml` には、原則として
position / rotation を直接書かない。

### 3. canonical PDU 定義へ統合する

`sensors.yaml` は単体で終わる設定ではない。

最終的には:

- `pdu_bodies.yaml`
- `sensors.yaml`

の両方から canonical な

- `pdutypes.json`
- `pdu_def.json`

を生成する。

### 4. 利用者に `pdu_size` を強制しない

known な標準 message 型については、
generator が size registry から補完してよい。

unknown な型だけ `null` または `auto` を許容する。

---

## ファイル配置

想定する配置:

```text
bodies/<robot>/
  config/
    sensors.yaml
  generated/
    pdutypes.json
    pdu_def.json
```

必要なら sensor 個別 spec は別ディレクトリに置ける。

```text
bodies/<robot>/
  config/
    sensors.yaml
    sensors/
      lidar.yaml
      imu.yaml
```

---

# 1. `sensors.yaml` v0.1 仕様

## 1.1 目的

`sensors.yaml` は、robot に属する sensor 出力を定義するための最小入力である。

役割は以下に限定する。

- sensor 名の定義
- sensor 種別の定義
- mount 対象 body / site の定義
- publish する PDU 名の定義
- publish する message type の定義
- 必要なら sensor spec file の参照

## 1.2 設計原則

```text
MJCF にある transform は書かない。
body / site の意味づけだけを書く。
PDU の意味単位で列挙する。
```

## 1.3 最小例

```yaml
format: hako_sensors
version: 0.1

robot_name: TB3

sensors:
  - name: lidar
    type: lidar_2d
    body: base_scan
    pdu_name: scan
    pdu_type: sensor_msgs/LaserScan
    spec: sensors/lds_01.yaml

  - name: imu
    type: imu
    body: imu_link
    pdu_name: imu
    pdu_type: sensor_msgs/Imu
    spec: sensors/imu.yaml

  - name: odometry
    type: odometry
    body: base_link
    pdu_name: odometry
    pdu_type: nav_msgs/Odometry
```

site を使う場合:

```yaml
sensors:
  - name: front_camera
    type: camera
    site: front_camera_site
    pdu_name: front_camera_image
    pdu_type: sensor_msgs/Image
    spec: sensors/front_camera.yaml
```

## 1.4 フィールド仕様

### `format`

```yaml
format: hako_sensors
```

ファイル種別を示す文字列。

v0.1 では `hako_sensors` を指定する。

### `version`

```yaml
version: 0.1
```

仕様バージョン。

### `robot_name`

```yaml
robot_name: TB3
```

sensor 定義の対象 robot 名。

### `sensors`

sensor 定義の配列。

各要素は 1 つの sensor 出力定義を表す。

#### `name`

sensor の論理名。

例:

- `lidar`
- `imu`
- `odometry`

#### `type`

sensor の意味種別。

例:

- `lidar_2d`
- `imu`
- `odometry`
- `camera`

#### `body`

mount 対象 body 名。

`body` か `site` のどちらか一方を指定する。

#### `site`

mount 対象 site 名。

`body` か `site` のどちらか一方を指定する。

#### `pdu_name`

publish する PDU 名。

例:

- `scan`
- `imu`
- `odometry`

#### `pdu_type`

publish する message type。

例:

- `sensor_msgs/LaserScan`
- `sensor_msgs/Imu`
- `nav_msgs/Odometry`

#### `pdu_size`

省略可能。

既知型であれば generator が補完してよい。
未知型または可変長型では `null` または `auto` を許容する。

#### `spec`

省略可能。

sensor 個別仕様ファイルへの参照。

用途:

- lidar の角度分解能
- imu の noise model
- camera の画像仕様

## 1.5 必須項目

v0.1 で必須とするのは以下。

- `format`
- `version`
- `robot_name`
- `sensors`

各 sensor entry では以下を必須とする。

- `name`
- `type`
- `pdu_name`
- `pdu_type`
- `body` または `site` のどちらか一方

また `sensors` は空配列を許可しない。

## 1.6 `pdu_size` の扱い

利用者に `pdu_size` の手計算を強制しない。

generator は既知の標準型について、
以下の registry を参照してサイズを補完してよい。

```text
hakoniwa_pdu.pdu_msgs.pdu_size.PDU_SIZE
```

既知型の例:

- `sensor_msgs/LaserScan`
- `sensor_msgs/Imu`
- `nav_msgs/Odometry`

補完ルール:

1. `sensors.yaml` に明示値があればそれを使う
2. `pdu_type` が registry に存在すればその値を使う
3. 存在しなければ `null` または `auto` を入れる

## 1.7 v0.1 で持たせないもの

以下は `sensors.yaml` に直接持たせない。

- mount の position / rotation
- final NodePath
- runtime 実装依存の comm 設定
- generator 内部の channel_id 割り当て規則

---

# 2. canonical PDU 生成との関係

## 2.1 役割分担

canonical `pdutypes.json` / `pdu_def.json` は、
少なくとも以下から構成される。

- `pdu_bodies.yaml`
  - `base_link_pos`
  - `joint_states`
- `sensors.yaml`
  - `scan`
  - `imu`
  - `odometry`

つまり:

```text
pdu_bodies.yaml + sensors.yaml
  -> canonical pdutypes.json / pdu_def.json
```

## 2.2 Godot と MuJoCo の関係

Godot sync runtime が直接 consume するのは通常、

- `base_link_pos`
- `joint_states`

である。

一方、MuJoCo などの runtime は sensor 系 PDU も publish する。

そのため canonical PDU 定義は、
Godot が必要とする subset より広くてよい。

## 2.3 channel_id

`channel_id` は runtime ごとにズレてはならない。

したがって sensor 系 PDU も、
canonical 生成規則に従って一意に割り当てる必要がある。

v0.1 では具体的な割り当てアルゴリズムは別仕様とし、
少なくとも以下を要求する。

- deterministic
- stable
- consumer 非依存

---

# 3. TB3 例

TB3 の最小例:

```yaml
format: hako_sensors
version: 0.1

robot_name: TB3

sensors:
  - name: lidar
    type: lidar_2d
    body: base_scan
    pdu_name: scan
    pdu_type: sensor_msgs/LaserScan

  - name: imu
    type: imu
    body: imu_link
    pdu_name: imu
    pdu_type: sensor_msgs/Imu

  - name: odometry
    type: odometry
    body: base_link
    pdu_name: odometry
    pdu_type: nav_msgs/Odometry
```

この定義があれば、
canonical PDU 生成器は body / joint 系に加えて
TB3 の sensor 系 PDU を追加できる。

---

# 4. 将来拡張

将来追加したい候補:

- `frame_id`
- publish rate hint
- noise model 参照
- multi-topic / packet message 対応
- request/response 型 sensor service
- sensor category ごとの default type / default size

---

# 5. まとめ

`sensors.yaml` は、

- body / joint 系 PDU と sensor 系 PDU を分離し
- MuJoCo などの sensor 出力要件を canonical 定義へ取り込み
- `hakoniwa-godot` と `hakoniwa-mujoco` の共通 PDU 契約を支える

ための最小入力である。

重要な方針は以下である。

```text
transform は MJCF を正とする。
sensor の意味づけだけを書く。
pdu_size は known type なら registry から補完する。
canonical pdutypes は pdu_bodies.yaml と sensors.yaml の両方から作る。
```
