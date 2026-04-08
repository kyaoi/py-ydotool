# PLAN.md

## 概要

次版リリースでは、`py-ydotool` のマウス操作を **relative move** と **current-display local absolute move** の 2 系統として整理し、以下を実現する。

- ゆっくり移動できるマウス移動
- 移動時間 (`duration`) と分割数 (`steps`) の指定
- クリックだけ / 移動だけ / ドラッグだけを明確に使える API と CLI
- `position()` 未対応と multi-display 制約の README 明記
- 「この PLAN のタスクがすべて完了したら次版リリース」という判断ができる明確な完了条件

---

## 進捗サマリー

- [x] Task 1 README / docstring の契約整理
- [x] Task 2 補間ヘルパの実装
- [x] Task 3 `move_rel()` の duration 対応
- [x] Task 4 `move_to()` の契約整理と duration 対応
- [x] Task 5 drag 系 API の duration 対応
- [x] Task 6 click-at 系 API の契約整理
- [x] Task 7 CLI の拡張
- [x] Task 8 テスト整備

---

## リリース判定ルール

**次版リリース可** としてよいのは、以下をすべて満たしたときのみとする。

- [x] Task 1〜Task 8 がすべて完了している
- [x] API / CLI / README / テストの整合が取れている
- [x] `position()` 非対応と multi-display 非保証が README に明記されている
- [x] 新規挙動に対するテストが追加されている
- [x] 既存のマウス操作 API との後方互換性が保たれている

---

## 背景

現状の `py-ydotool` には、クリック・移動・ドラッグの基本機能がすでにある。

一方で、以下が未整理または未対応である。

- PyAutoGUI のような `duration` 付きの滑らかな移動
- relative move と absolute move の契約の切り分け
- Wayland / ydotool 由来の制約の README 明記
- multi-display 時の absolute 座標の扱いの明文化
- `position()` 未実装の理由と今後の扱い

---

## 今回の方針

### 採用する方向性

今回のマウス移動は、以下の 2 系統で扱う。

### 1. Relative move

現在位置からの相対移動。

- 例: `move_rel(dx, dy, ...)`
- 最も意味が明快で、安全に拡張しやすい
- duration 付き滑らか移動の中心機能とする

### 2. Current-display local absolute move

**現在ポインタが存在しているディスプレイの `(0, 0)` を起点** とする absolute move。

- 例: `move_to(x, y, ...)`
- 仮想デスクトップ全体の global absolute ではない
- multi-display 全域を一貫して扱う API にはしない
- 実装上は、必要に応じて **現在ディスプレイの `(0, 0)` へ寄せてから `move_rel(x, y)` する方式** を採ってよい
- この方式は **「現在ディスプレイ基準の absolute-like move」** として扱う

---

## 今回の API 契約

## 1. `position()`

今回のリリースでは **未実装のまま** とする。

### 契約

- [ ] `position()` は実装しない
- [ ] 推定値で埋めない
- [ ] README に未対応理由を書く

### README に書くこと

- `ydotool` 単体では現在の実カーソル位置取得が難しい
- 将来対応する場合も「真の現在位置」と「内部推定値」は分ける
- 今回は `position()` を提供しない

---

## 2. Relative move の契約

### 対象 API

- `move_rel(dx, dy, *, duration=0.0, steps=None)`
- `drag_rel(dx, dy, *, button=..., duration=0.0, steps=None)`

### 契約

- [ ] `duration=0` のときは従来どおり即時移動
- [ ] `duration>0` のときは linear 補間で複数ステップ移動
- [ ] `steps` は省略可能
- [ ] 最終的な合計移動量が一致する

---

## 3. Current-display local absolute move の契約

### 対象 API

- `move_to(x, y, *, duration=0.0, steps=None)`
- `click_at(x, y, *, ...)`
- `double_click_at(x, y, *, ...)`
- `drag_to(x, y, *, button=..., duration=0.0, steps=None)`

### 契約

- [ ] `(x, y)` は **仮想デスクトップ全体** ではなく **現在ディスプレイのローカル座標** として扱う
- [ ] multi-display 全域をまたぐ absolute move は保証しない
- [ ] `duration=0` の場合は従来の absolute move を利用してよい
- [ ] `duration>0` の場合は、必要に応じて **現在ディスプレイの `(0, 0)` まで寄せてから相対移動** する方式を採ってよい
- [ ] この挙動は README / docstring に明記する

### 注意

`duration>0` の `move_to()` は、**現在位置から目標まで一直線に滑らか移動することを保証しない**。
今回の契約はあくまで **現在ディスプレイ `(0, 0)` 基準の absolute-like move** である。

---

## 4. Multi-display の契約

今回のリリースでは、以下を **非目標** とする。

- [ ] すべてのディスプレイ範囲を一貫した absolute 座標で扱うこと
- [ ] 仮想デスクトップ全体の global `(0, 0)` を提供すること
- [ ] 画面をまたぐ正確な absolute click / drag を保証すること

### README に書くこと

- `move_to()` 系の absolute API は **現在ディスプレイ基準** とみなす
- multi-display 環境では全ディスプレイ範囲の absolute 制御は未保証
- absolute 系は環境依存であり、single-display または current-display 内利用を前提とする

---

## 5. 補間ロジックの契約

共通補間ヘルパを内部に追加する。

### 必須要件

- [ ] `duration >= 0`
- [ ] `steps is None or steps > 0`
- [ ] `duration == 0` では即時移動
- [ ] linear 補間のみを対象にする
- [ ] 丸め誤差があっても最終座標・合計移動量が一致する
- [ ] drag 系でもボタン解放安全性を壊さない

### 今回やらないこと

- [ ] easing / tween の複数実装
- [ ] PyAutoGUI 完全互換

---

## タスク一覧

## Task 1. README / docstring の契約整理

### 目的

利用者が `py-ydotool` のマウス API を誤解しないようにする。

### 作業内容

- [x] README に relative move と current-display local absolute move の違いを書く
- [x] `position()` 未対応を書く
- [x] multi-display absolute 非保証を書く
- [x] `move_to(duration>0)` は現在ディスプレイ `(0, 0)` 基準の absolute-like move であることを書く
- [x] 必要な docstring を更新する

### 完了条件

- [x] README だけ読んで、relative / absolute / multi-display 制約が分かる
- [x] `position()` の扱いが曖昧でない

---

## Task 2. 補間ヘルパの実装

### 目的

duration 付き移動の共通基盤を作る。

### 作業内容

- [x] `client.py` に共通補間ヘルパを追加する
- [x] linear 補間で複数ステップへ分割できるようにする
- [x] 丸め誤差込みで最終一致させる
- [x] invalid な `duration` / `steps` を弾く

### 完了条件

- [x] relative / absolute-like / drag が同じ補間基盤を再利用できる
- [x] 0 秒移動と duration 移動の両方が扱える

---

## Task 3. `move_rel()` の duration 対応

### 目的

安全で分かりやすい滑らか移動を提供する。

### 作業内容

- [x] `move_rel(dx, dy, *, duration=0.0, steps=None)` を実装する
- [x] `duration=0` の既存互換を保つ
- [x] `duration>0` で補間ヘルパを使う

### 完了条件

- [x] relative move に duration 指定ができる
- [x] 既存コードを壊さない

---

## Task 4. `move_to()` の契約整理と duration 対応

### 目的

`move_to()` を **current-display local absolute move** として明確化する。

### 作業内容

- [x] `move_to(x, y, *, duration=0.0, steps=None)` の API 契約を整理する
- [x] `duration=0` は従来の absolute move を利用する
- [x] `duration>0` は current-display `(0, 0)` 基準で動く方式を実装する
- [x] 必要であれば「まず `(0, 0)` に寄せてから `move_rel(x, y)`」方式で実装する
- [x] docstring / README と実装の意味を一致させる

### 完了条件

- [x] `move_to()` の意味が current-display local absolute として固定されている
- [x] multi-display global absolute と誤読されない
- [x] `duration>0` の動作方針が実装・文書で一致している

---

## Task 5. drag 系 API の duration 対応

### 目的

ドラッグでも滑らかな移動を可能にする。

### 作業内容

- [x] `drag_rel(..., duration=0.0, steps=None)` を実装する
- [x] `drag_to(..., duration=0.0, steps=None)` の方針を `move_to()` と揃える
- [x] `drag_between(...)` がある場合は補間ロジックを共通化する
- [x] `hold_button()` の安全性を維持する

### 完了条件

- [x] drag 系でも duration 指定ができる
- [x] 例外時でもボタン解放が保証される

---

## Task 6. click-at 系 API の契約整理

### 目的

absolute click 系の意味を `move_to()` と揃える。

### 作業内容

- [x] `click_at()` を current-display local absolute として文書化する
- [x] `double_click_at()` も同様に整理する
- [x] 必要なら内部的に `move_to()` 契約へ寄せる

### 完了条件

- [x] click-at 系の absolute 座標の意味が明確
- [x] README / docstring / 実装が一致している

---

## Task 7. CLI の拡張

### 目的

ライブラリ API と同じ考え方で CLI からも使えるようにする。

### 作業内容

- [x] `move` に `--duration` / `--steps` を追加する
- [x] `drag` に `--duration` / `--steps` を追加する
- [x] CLI の `move` が current-display local absolute なのか relative なのかを明確にする
- [x] 必要なら relative 指定オプションや help 文面を整理する

### 完了条件

- [x] CLI から duration 指定が可能
- [x] help / README で座標系の意味が分かる

---

## Task 8. テスト整備

### 目的

新しい API 契約と制約を固定する。

### 作業内容

- [x] `move_rel(duration=...)` のテスト追加
- [x] `move_to(duration=...)` の current-display local absolute 契約テスト追加
- [x] invalid `duration` / `steps` のテスト追加
- [x] drag 系 duration テスト追加
- [x] CLI 引数テスト追加
- [x] README で宣言した制約と矛盾しないか確認する

### 完了条件

- [x] relative / absolute-like / drag / CLI の主要ケースがテストされている
- [x] 「今回保証しないこと」をテスト期待値に混ぜていない

---

## 非目標

今回のリリースでは、以下はやらない。

- [ ] 真の `position()` 実装
- [ ] multi-display 全域の global absolute move
- [ ] 全ディスプレイ共通の `(0, 0)` 導入
- [ ] compositor-specific backend 導入
- [ ] easing / tween 追加
- [ ] PyAutoGUI 完全互換

---

## 実装優先順

1. Task 1 README / docstring
2. Task 2 補間ヘルパ
3. Task 3 `move_rel()`
4. Task 4 `move_to()`
5. Task 5 drag 系
6. Task 6 click-at 系
7. Task 7 CLI
8. Task 8 テスト最終調整

---

## 完了チェックリスト

### API

- [x] `move_rel()` に `duration` / `steps` がある
- [x] `move_to()` に `duration` / `steps` がある
- [x] drag 系が duration 対応している
- [x] click-at 系の契約が整理されている

### 制約明記

- [x] `position()` 未対応が README に書かれている
- [x] multi-display 非保証が README に書かれている
- [x] current-display local absolute の意味が README に書かれている

### CLI

- [x] `move` に duration 指定がある
- [x] `drag` に duration 指定がある
- [x] help 文面が更新されている

### テスト

- [x] API テスト追加済み
- [x] CLI テスト追加済み
- [x] invalid 値テスト追加済み
- [x] drag 安全性テスト追加済み

### リリース可否

- [x] 上記すべてが完了したら次版リリース可

