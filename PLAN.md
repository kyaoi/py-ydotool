# PLAN.md

## 概要

次版リリースでは、`py-ydotool` のテキスト入力まわりを再設計し、以下を実現する。

- `wl-copy` 利用時の timeout バグ修正
- `type()` / `write()` を **高水準の文字列入力 API** として整理
- 日本語を含む Unicode 文字列を、可能な範囲で自然に入力できる設計へ拡張
- Wayland 環境で `ydotool` / `wtype` / `eitype` / clipboard paste を状況に応じて使い分ける仕組みの導入
- `type_delay_ms` などの timing 契約を明文化し、backend ごとの差異を README / docstring / テストで固定

本 PLAN は、今後この方向で実装を進めるための唯一の作業基準とする。

---

## 背景

現状の `py-ydotool` では、テキスト入力に関して次の課題がある。

- `copy()` / `paste_text()` 系で `wl-copy` が timeout する環境がある
- `type()` が事実上 `ydotool` 前提のため、日本語や一般的な Unicode 文字列を安定して扱えない
- Wayland 上では入力 backend の能力差が大きく、1 つの実装で全言語・全環境を自然に扱うのが難しい
- `type_delay_ms` の意味が backend ごとに変わり得るが、現状はその契約が明確でない

特に次の 2 点が重要である。

1. **`wl-copy` timeout はバグとして先に潰す必要がある**
2. **`type()` は「物理キーを1文字ずつ叩く API」ではなく「文字列を最適な方法で注入する API」へ再定義した方が自然である**

---

## 進捗サマリー

- [x] Task 1 現状契約の棚卸しと README / docstring 整理
- [x] Task 2 `wl-copy` timeout 修正
- [x] Task 3 text backend 抽象化の導入
- [x] Task 4 `type()` / `write()` の高水準 API 化
- [x] Task 5 Unicode / 日本語入力の自動 backend 選択
- [x] Task 6 paste fallback と timing 契約の明文化
- [x] Task 7 CLI / doctor / help の更新
- [x] Task 8 テスト整備
- [x] Task 9 README / 使用例 / 制約整理

---

## リリース判定ルール

**次版リリース可** としてよいのは、以下をすべて満たしたときのみとする。

- [x] Task 1〜Task 9 がすべて完了している
- [x] `wl-copy` timeout の回帰テストが存在する
- [x] `type()` の backend 自動選択ルールが README / docstring / テストで一致している
- [x] `type_delay_ms` が direct typing backend 専用であることが文書化されている
- [x] paste fallback 時の挙動が README / docstring / テストで明確化されている
- [x] 既存 API (`press`, `key_down`, `key_up`, `hotkey`, daemon 周り) の後方互換性が保たれている
- [x] 新しい CLI オプションや help が実装と一致している

---

## 今回の設計方針

## 1. `type()` の意味を再定義する

次版では `type()` を、単なる `ydotool type` の薄いラッパではなく、

> **与えられた文字列を、その環境で最も適切な方法で入力する高水準 API**

として扱う。

### 目的

- ASCII と Unicode の扱いを統一する
- backend 差を利用者に極力意識させない
- 日本語入力を含む多言語入力を「使える範囲で自動で吸収」する

### 契約

- [x] `type(text)` は backend を自動選択して文字列を入力する
- [x] `write(text)` は `type(text)` 相当として扱う
- [x] `press()` / `hotkey()` などの物理キー系 API とは役割を分ける
- [x] 「文字列入力」と「物理キー入力」を内部設計上も明確に分離する

---

## 2. 単一 backend で全言語対応は目標にしない

今回の設計では、**1 つの backend だけで全言語対応することは目標にしない**。

理由:

- `ydotool` は物理キー寄りであり、Unicode 文字列入力には本質的制約がある
- compositor / portal / virtual keyboard の対応状況が環境依存である
- paste fallback は強力だが、入力の意味が「逐次 typing」ではなく「一括注入」になる

### 方針

- [x] backend の能力差を前提にする
- [x] direct typing と paste fallback を同列に扱わず、契約を分ける
- [x] 「完全保証」ではなく「実用上広く入力できること」を目標にする

---

## 3. text backend を導入する

clipboard backend とは別に、**text input backend** を新設する。

### 想定 backend

- `ydotool`
  - ASCII / 既存資産 / 物理キー寄りの文字入力
- `wtype`
  - Wayland virtual keyboard 経由の Unicode 文字入力
- `eitype`
  - EI / portal 系の文字入力
- `paste`
  - clipboard 経由の一括注入 fallback

### 契約

- [x] backend ごとに「何ができるか」を能力として表現する
- [x] 少なくとも `supports_unicode` / `supports_direct_text` / `supports_timing_per_char` 相当の整理を行う
- [x] backend の存在確認・選択ロジックはクライアント内部に閉じ込める

---

## 4. backend 自動選択の基本ルール

初期実装では、概ね以下の順で評価する。

### 自動選択の考え方

1. ユーザーが `text_backend=...` を明示した場合はそれを優先する
2. direct Unicode 入力可能 backend が使えるならそれを優先する
3. ASCII かつ `ydotool` で十分な場合は `ydotool` を使う
4. direct typing が難しい場合は `paste` へフォールバックする

### 初期案

- [x] Wayland + `wtype` 利用可 → `wtype` を優先候補にする
- [x] Wayland + `eitype` 利用可 → `eitype` を候補にする
- [x] ASCII のみ + `ydotool` 利用可 → `ydotool` を候補にする
- [x] どれも厳しい場合 + clipboard backend 利用可 → `paste`
- [x] どの方式も使えない場合は分かりやすい例外を送出する

### 備考

厳密な優先順位は実装時に微調整してよいが、**README / docstring / テストの説明と一致させること** を必須とする。

---

## 5. `type_delay_ms` の契約

この論点は次版で必ず固定する。

### 採用方針

`type_delay_ms` は、

> **direct typing backend における文字ごとの遅延**

として扱う。

### したがって

- [x] `ydotool` / `wtype` / `eitype` など、逐次文字入力できる backend では `type_delay_ms` を適用してよい
- [x] `paste` fallback では `type_delay_ms` は適用しない
- [x] paste fallback では文字列は一括挿入として扱う

### 明文化すること

- [x] README に `type_delay_ms` は direct typing backend 専用と書く
- [x] docstring に同じ意味を書く
- [x] strict mode により timing を守れない fallback を失敗へ切り替えられるようにする

### 今回やらないこと

- `paste` なのに見た目だけ `len(text) * delay` で待って辻褄を合わせること
- clipboard 経由で1文字ずつ貼り付けること

---

## 6. paste fallback の契約

paste fallback は便利だが、逐次 typing とは意味が異なる。

### 契約

- [x] text backend が `paste` の場合、文字列は一括でクリップボードへ設定してから paste 操作を行う
- [x] `type_delay_ms` は無視される
- [x] 必要に応じて clipboard の保存・復元機能を導入する
- [x] clipboard 復元に失敗した場合の扱いを明確にする

### README に書くこと

- [x] paste fallback は「typed one by one」ではなく「atomic insertion」である
- [x] アプリによっては paste shortcut の差異がある
- [x] 端末 / Vim / 特殊 UI / パスワード欄では期待通りでない場合がある

---

## 7. `wl-copy` timeout 修正の方針

今回の最優先バグ修正として扱う。

### 背景認識

- `wl-copy` は利用形態によってはバックグラウンド化する
- `subprocess.run(..., capture_output=True, timeout=...)` との組み合わせで待ち続ける問題が起き得る

### 修正方針

- [x] copy 系コマンドでは stdout / stderr を不要に捕捉しない
- [x] `paste` 系コマンドのみ出力を読む
- [x] clipboard 操作の subprocess 実行経路を整理し、copy / paste で必要な I/O 契約を分ける

### 完了条件

- [x] `wl-copy` を使う copy 経路が timeout しない
- [x] `wl-paste` を使う paste 経路は従来どおり内容取得できる
- [x] 回帰テストがある

---

## 8. API 設計

## 想定追加設定

次版では少なくとも以下の設定導入を検討する。

- [x] `text_backend: Literal["auto", "ydotool", "wtype", "eitype", "paste"] = "auto"`
- [x] `restore_clipboard: bool = True`
- [x] `paste_shortcut` のカスタマイズ余地
- [x] `strict_text_timing` のような strict モード

### 設計原則

- [x] 既存利用者が何も指定しなくても自然に改善されること
- [x] 明示指定すれば backend 選択を固定できること
- [x] 例外文言で「何が足りないか」が分かること

---

## 9. CLI 方針

ライブラリ API と同じ思想で CLI も整理する。

### 目的

- Unicode 文字列入力の backend 選択を CLI でも使えるようにする
- doctor / help で実行環境の制約が分かるようにする

### 候補

- [x] `type` コマンドに `--text-backend` を追加する
- [x] `--restore-clipboard/--no-restore-clipboard` 相当を追加実装する
- [x] doctor / setup 系で `wtype` / `eitype` / clipboard backend の可用性を見せる
- [x] help / README で direct typing と paste fallback の違いを説明する

---

## タスク一覧

## Task 1. 現状契約の棚卸しと README / docstring 整理

### 目的

変更前に、現状 API と README のズレを潰し、今後の説明の土台を作る。

### 作業内容

- [x] `type()` / `write()` / `copy()` / `paste_text()` の現状挙動を棚卸しする
- [x] `type_delay_ms` の現状意味を確認する
- [x] README / docstring で、今回の変更対象になりそうな箇所を洗い出す
- [x] 「文字列入力 API」と「物理キー API」の役割差を文章で先に固定する

### 完了条件

- [x] 今回変える契約と変えない契約が明文化されている
- [x] 後続タスクで README / docstring の説明が迷子にならない

---

## Task 2. `wl-copy` timeout 修正

### 目的

clipboard copy 経路を安定化し、paste fallback 導入の土台を作る。

### 作業内容

- [x] subprocess 実行 helper の copy / paste 契約を分離する
- [x] copy 経路では不要な `capture_output=True` をやめる
- [x] `wl-copy` / `xclip` / `xsel` など既存 clipboard backend への影響を確認する
- [x] 失敗時例外が分かりやすいことを確認する

### 完了条件

- [x] `wl-copy` 経路で timeout しない
- [x] paste 経路の戻り値契約を壊していない
- [x] focused regression test がある

---

## Task 3. text backend 抽象化の導入

### 目的

Unicode 入力と backend 自動選択のための内部土台を作る。

### 作業内容

- [x] text input backend を表す内部構造を追加する
- [x] backend ごとのコマンド生成・能力定義を分離する
- [x] `auto` 選択ロジックの枠組みを導入する
- [x] clipboard backend との責務境界を明確にする

### 完了条件

- [x] `type()` が backend 実装詳細を直接抱え込まない構造になっている
- [x] backend の追加・差し替えがしやすい

---

## Task 4. `type()` / `write()` の高水準 API 化

### 目的

`type()` / `write()` を backend 自動選択の入口にする。

### 作業内容

- [x] `type()` を「文字列入力の高水準 API」として実装修正する
- [x] `write()` を `type()` と同じ契約へ寄せる
- [x] 既存引数との後方互換性を壊さないよう整理する
- [x] backend 明示指定時の分岐を作る

### 完了条件

- [x] Unicode 文字列を `type()` で扱う設計が API 上自然になっている
- [x] 既存 ASCII 利用例が極力そのまま動く

---

## Task 5. Unicode / 日本語入力の自動 backend 選択

### 目的

日本語を含む文字列で自然に入力方式を切り替えられるようにする。

### 作業内容

- [x] 非 ASCII / Unicode 文字列の扱い方針を固定する
- [x] `wtype` / `eitype` / `ydotool` / `paste` の優先順位を実装する
- [x] backend 明示指定時のエラー・フォールバック方針を決める
- [x] direct typing 不可時の fallback を `paste` へ接続する

### 完了条件

- [x] 日本語を含む文字列で `type()` が自動的に適切 backend を選べる
- [x] 失敗時の理由が利用者に分かる

---

## Task 6. paste fallback と timing 契約の明文化

### 目的

`type_delay_ms` と paste fallback の関係を曖昧にしない。

### 作業内容

- [x] `type_delay_ms` を direct typing backend 専用として実装・文書化する
- [x] paste fallback 時には適用しない仕様を固定する
- [x] strict mode で ignored fallback を失敗へ切り替える方針を採用する
- [x] `restore_clipboard` の仕様を整理する
- [x] strict mode を入れると判断し、`strict_text_timing` を導入する

### 完了条件

- [x] `type_delay_ms` の意味が README / docstring / テストで一致している
- [x] paste fallback の timing 挙動に surprise が少ない

---

## Task 7. CLI / doctor / help の更新

### 目的

ライブラリだけでなく CLI 利用者にも新しい仕様が分かるようにする。

### 作業内容

- [x] `type` コマンドのオプション追加を実装する
- [x] doctor / help に text backend の可用性情報を出す方針を決める
- [x] clipboard restore や backend 選択のヘルプ文面を整備する
- [x] 実装と help の不一致がないようにする

### 完了条件

- [x] CLI からも backend 制御が可能
- [x] help を読めば fallback の意味が分かる

---

## Task 8. テスト整備

### 目的

新しい契約を固定し、以後の変更で壊れにくくする。

### 作業内容

- [x] `wl-copy` timeout 回帰テストを追加する
- [x] backend 自動選択の単体テストを追加する
- [x] Unicode / 日本語文字列の routing テストを追加する
- [x] paste fallback 時に `type_delay_ms` が未適用であることを確認するテストを追加する
- [x] backend 明示指定エラーのテストを追加する
- [x] clipboard restore のテストを追加できる範囲で追加する

### 完了条件

- [x] 主要ルーティングと契約がテストで固定されている
- [x] 「今回保証しないこと」を曖昧な期待値として混ぜていない

---

## Task 9. README / 使用例 / 制約整理

### 目的

利用者が新仕様を README だけで理解できるようにする。

### 作業内容

- [x] `type()` の意味が高水準 API に変わったことを書く
- [x] `type_delay_ms` の適用条件を書く
- [x] paste fallback は atomic insertion であることを書く
- [x] `wtype` / `eitype` / `ydotool` / clipboard それぞれの役割を簡潔に説明する
- [x] 日本語入力例・ASCII 入力例・明示 backend 指定例を追加する
- [x] 制約事項をまとめる

### 完了条件

- [x] README を読むだけで、direct typing と paste fallback の違いが分かる
- [x] timing の挙動で誤解しにくい

---

## 非目標

今回のリリースでは、以下はやらない。

- 単一 backend のみで「全環境・全言語完全対応」を保証すること
- すべてのアプリ / 端末 / エディタ / パスワード欄で同一品質を保証すること
- paste fallback でも `type_delay_ms` を逐次 typing 的に再現すること
- clipboard 経由で1文字ずつ入力すること
- IME 状態そのものの完全制御
- compositor 依存挙動の完全吸収

---

## 実装優先順

1. Task 1 現状契約の棚卸し
2. Task 2 `wl-copy` timeout 修正
3. Task 3 text backend 抽象化
4. Task 4 `type()` / `write()` の高水準 API 化
5. Task 5 Unicode / 日本語入力 routing
6. Task 6 timing 契約と paste fallback 固定
7. Task 7 CLI / doctor / help 更新
8. Task 8 テスト整備
9. Task 9 README 最終整理

---

## 完了チェックリスト

### clipboard

- [x] `wl-copy` timeout が解消されている
- [x] copy / paste の subprocess 契約が分離されている
- [x] clipboard 回帰テストがある

### text backend

- [x] backend 抽象化が導入されている
- [x] `auto` 選択が実装されている
- [x] 明示 backend 指定ができる

### API

- [x] `type()` が高水準文字列入力 API になっている
- [x] `write()` が同契約に揃っている
- [x] `press()` / `hotkey()` など物理キー系 API への影響が限定されている

### timing / fallback

- [x] `type_delay_ms` が direct typing backend 専用として整理されている
- [x] paste fallback は atomic insertion として整理されている
- [x] surprise の少ない例外 / ログ / README になっている

### CLI / docs

- [x] CLI help が更新されている
- [x] README 使用例が更新されている
- [x] 制約事項が README に書かれている

### テスト

- [x] routing テストがある
- [x] Unicode / 日本語ケースのテストがある
- [x] timing 契約のテストがある
- [x] `wl-copy` timeout 回帰テストがある

### リリース可否

- [x] 上記すべてが完了したら次版リリース可
