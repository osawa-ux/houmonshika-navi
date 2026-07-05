# CLAUDE.md — houmonshika-navi

訪問歯科ポータル（`shika.zaitaku-navi.com`）。在宅ナビ群の訪問歯科版。
医療情報ネットからスクレイピングした歯科データを正規化・静的サイト生成する。

- repo: `houmonshika-navi`
- project: `shika`
- domain: `shika.zaitaku-navi.com`（未公開・準備中）
- sister sites: clinic, kango, care, welfare（zaitaku-navi.com 群）

---

## 上位原則

本repoは Obsidian の `30_Areas/開発運用原則.md` を上位原則として参照する。
共通ルール・保存判断基準は `~/.claude/CLAUDE.md`（グローバル）。
データ整合性チェック（Pre-Build / Pre-Deploy Validation）は **必須**。

---

## このrepoの位置づけ

- データ収集（スクレイピング）は `~/projects/MyPython/` 側で実施（`scrape_dental.py` 等）
- 本 repo はビルド系（正規化 → 静的サイト生成）に集中
- ビルドシステムの参考実装: `~/projects/kyotaku-navi/build_site.py`
- MVP: 神奈川県 2,507件（訪問歯科対応 986件）

---

## 主要ファイル

- `build_site.py` — 静的サイト生成
- `config/site_config.json` — サイト設定（GA4 ID, cname_domain 等）
- `data/normalized/clinics_dental.json` — ビルド入力（正規化済み）
- `scripts/normalize.py` — MyPython 側の生データを正規化
- `scripts/geocode.py` — Nominatim Geocoding（P4で Google Maps API に差し替え予定）
- `dist/` — ビルド出力（GitHub Pages 公開対象）

---

## Pre-Build / Pre-Deploy Validation（必須）

`build_site.py` 実行前:
- 入力 JSON 件数（神奈川MVPなら 2,507件）
- 前回ビルド時との差分
- detail_status の分布（ok / unknown / error）

`build_site.py` 実行後・デプロイ前:
- 個別ページ数 ≒ 総件数 + 都道府県/市区町村ページ + sitemap
- 検索JSON `dist/data/search/14.json` の件数一致
- 代表的な市区町村（横浜市中区など）の件数 spot check

異常があれば push / デプロイを中止し、原因調査を優先。

---

## 能力カタログ連携

source of truth: Obsidian `30_Areas/能力カタログ.md`（索引兼台帳）。

### この repo に該当する能力 ID（既存登録分）

- `SHIKA-BUILD-01` — 訪問歯科ポータル 神奈川MVP 2,507件（active_unverified, write_with_confirmation）

### 更新義務

- 全国展開（47都道府県）が完了したら状態を `active` に昇格
- 厚生局歯科届出データ突合・Geocoding 一括付与など機能追加時は catalog 追記
- データ収集側の能力（医療情報ネットからの歯科データ取得）を独立 ID 化する場合は `DATA-SHIKA-ACQ-01` 等で MyPython 側に登録（本 repo ではビルド系に絞る）

---

## Obsidian 連携の最小ルール

vault path は動的解決:

```bash
python ~/.claude/skills/_shared/resolve_vault.py
python ~/.claude/skills/_shared/resolve_vault.py --join "20_Projects/shika/index.md"
```

### 読む候補ノート

- `20_Projects/shika/index.md` — この repo の現在地・重要論点
- `30_Areas/開発運用原則.md` — 上位原則
- `30_Areas/能力カタログ.md` — 横断能力索引
- 必要なら当日の `10_Daily/YYYY-MM-DD.md`

---

## 保存優先度（この repo 特有）

1. 訪問歯科データソースの統合判断（医療情報ネット / 厚生局届出の突合）
2. clinic / kango / care / welfare との横断 SEO 設計・内部リンク
3. detail_status `unknown` の扱い・再取得ロジック
4. Geocoding コスト・精度判断（Nominatim → Google Maps API）
5. P4以降の有料プラン導線設計

### 保存しないもの

- ビルド成功/失敗ログ全文
- 軽微な template / CSS 修正
- 個別歯科レコードの内容修正

---

## 作業完了時の報告形式

`SAVE_DECISION: yes / no` / `SAVE_REASON:` / `SAVE_CATEGORY:` / `SAVE_TITLE:` / `SAVE_SUMMARY:` / `NEXT_ACTIONS:` をグローバル CLAUDE.md に準拠して出力。

---

## docs 構成（decisions / design / runbooks）

決定の正本は `docs/decisions/`（連番 MADR・不変・supersede 更新）。設計 living doc は `docs/design/`。運用手順は `docs/runbooks/`。

運用ルール正本: vault `70_SOP/product-docs-adr.md`
