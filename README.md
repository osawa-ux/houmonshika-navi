# 訪問歯科ナビ（houmonshika-navi）

訪問歯科に対応している歯科診療所を都道府県・市区町村から検索できるポータルサイト。
**在宅ナビ** 群（`zaitaku-navi.com`）の訪問歯科版。

- 公開URL: `https://shika.zaitaku-navi.com`（未公開）
- 親ブランド: `https://zaitaku-navi.com`（未取得）
- 姉妹サイト: `clinic.zaitaku-navi.com`（訪問診療）、`kango.zaitaku-navi.com`（訪問看護）、`care.zaitaku-navi.com`（居宅介護支援）、`welfare.zaitaku-navi.com`（福祉系）

---

## 現在のステータス（2026-04-12 時点）

### 完了済み

- **P0**: 医療情報ネットからの歯科データ取得経路確認（`kkn=3` + `kikanKbn=3`）
- **P1**: `scrape_dental.py` 作成、神奈川県 2,507件の一覧+詳細取得
- **P2**: エラー926件の再取得（811件リカバリ）、訪問歯科対応986件（39.3%）確定
- **P3**: 神奈川県MVPサイト生成完了（トップ + 35市区町村 + 2,507歯科詳細 + sitemap）
- **サブドメイン方針切替**: 全URLを `https://shika.zaitaku-navi.com` に統一
- **Namecheap API認証情報**: `~/.secrets/MyPython/.env` に保存済み（Vaultにも同期）

### 次回再開時の開始ポイント

**公開作業（人手 + 自動化）:**

1. ✅ Namecheap API認証情報保存（完了）
2. ✅ Namecheap IP Whitelist 登録（完了）
3. ⏳ **親ドメイン `zaitaku-navi.com` の取得** — Namecheap で取得
4. ⏳ **Namecheap DNS ラッパースクリプト作成** — `scripts/namecheap_dns.py`
5. ⏳ **GitHub リポジトリ作成** — `osawa-ux/houmonshika-navi`
6. ⏳ **GitHub Pages 設定** — `dist/` を `gh-pages` ブランチにデプロイ or `docs/` にリネーム
7. ⏳ **DNS設定** — `shika → osawa-ux.github.io` の CNAME（Namecheap または Cloudflare）
8. ⏳ **HTTPS 有効化** — GitHub Pages 側で自動発行
9. ⏳ **GA4 ID 取得** → `config/site_config.json` の `analytics.ga4_id` に設定 → 再ビルド

**P4（品質強化）:**

- Google Maps API で Geocoding 一括付与（Nominatimは日本語住所35%で断念、P4でGoogle Maps APIに差し替え）
- 厚生局歯科届出データとの突合（在宅療養支援歯科診療所バッジ）
- Google Search Console 登録 + sitemap送信
- unknown 115件の「未確認」ラベル表示検討

**P5（全国展開）:**

- `scrape_dental.py` を47都道府県で実行（約2〜3時間）
- `retry_dental_errors.py` で全国エラー再取得
- `build_site.py` は既に47都道府県対応済み（PREF_SLUG等定数完備）

### 未解決の課題

- 検索JSON 749KB は許容範囲だが、全国展開時は都道府県別分割で問題なし
- 地図機能なし（P4でGoogle Maps APIを導入するまで詳細ページはOpenStreetMap iframeが空になる）
- 親ドメイン `zaitaku-navi.com` 未取得のため、姉妹サイトへのリンクはフッターに入れていない

### 関連リポジトリ

- データ収集・スクレイピング: `~/projects/MyPython/` (`scrape_dental.py`, `retry_dental_errors.py`)
- 元データ: `~/projects/MyPython/data/clinics_dental_kanagawa.json` (2,507件)
- 参考実装（ビルドシステム）: `~/projects/kyotaku-navi/build_site.py`

---

## MVP（神奈川県パイロット版）

- 掲載件数: 2,507件（神奈川県のみ）
- 訪問歯科対応: 986件（39.3%）
- 歯科衛生士訪問対応: 669件（26.7%）
- データ出典: [医療情報ネット（厚生労働省）](https://www.iryou.teikyouseido.mhlw.go.jp/)

## ディレクトリ構成

```
houmonshika-navi/
├── build_site.py              # 静的サイト生成スクリプト
├── config/
│   └── site_config.json       # サイト設定
├── data/
│   ├── normalized/
│   │   └── clinics_dental.json # ビルド用正規化データ
│   └── geocode_cache.json     # Geocoding キャッシュ（P4で使用）
├── scripts/
│   ├── normalize.py           # 元データを正規化
│   └── geocode.py             # 住所→緯度経度変換（Nominatim）
└── dist/                      # ビルド出力（GitHub Pages用）
```

## ビルド手順

```bash
# 1. 元データを正規化（MyPython/data/clinics_dental_kanagawa.json を入力）
python scripts/normalize.py

# 2. サイト生成
python build_site.py

# 3. ローカルプレビュー
python build_site.py --preview
# → http://localhost:8000/
```

## 生成物

| ファイル | 数 | 説明 |
|---|---|---|
| `dist/index.html` | 1 | トップ（神奈川県ページと同内容） |
| `dist/pref/kanagawa.html` | 1 | 神奈川県トップ |
| `dist/pref/kanagawa/{city}.html` | 35 | 市区町村ページ |
| `dist/clinic/{id}.html` | 2,507 | 歯科詳細ページ |
| `dist/about.html` | 1 | このサイトについて |
| `dist/data/search/14.json` | 1 | 検索用JSON（749KB） |
| `dist/sitemap.xml` | 1 | サイトマップ（2,545 URL） |
| `dist/robots.txt` | 1 | クローラ制御 |

## データ仕様

### 各歯科レコード

```json
{
  "clinic_id": "1404111100",
  "name": "さいとう歯科",
  "pref_code": "14",
  "pref": "神奈川県",
  "city": "横浜市中区",
  "postal": "231-0005",
  "address": "神奈川県横浜市中区本町1-3 綜通横浜ビル2階",
  "tel": "045-224-8011",
  "url": "http://www.saito-web.com",
  "specialties": ["歯科", "矯正歯科"],
  "has_visiting_dental": false,
  "has_hygienist_visit": false,
  "has_zaitaku_section": false,
  "detail_status": "ok",
  "source_url": "https://www.iryou.teikyouseido.mhlw.go.jp/...",
  "kikan_kbn": "3",
  "latitude": null,
  "longitude": null
}
```

### バッジ表示ロジック

| バッジ | 条件 |
|---|---|
| 訪問歯科対応 | `has_visiting_dental = true` |
| 歯科衛生士訪問 | `has_hygienist_visit = true` |

### unknown の扱い

`detail_status = 'unknown'` は医療情報ネットで詳細ページが取得できなかったレコード（115件）。UIではバッジなしで通常表示（false と同じ扱い）。内部的にはフラグを保持し、定期再取得の対象にする。

## 今後の拡張（P4以降）

- [ ] Geocoding（Google Maps API）で緯度経度付与
- [ ] 全国展開（47都道府県）
- [ ] 厚生局届出データとの突合（在宅療養支援歯科診療所バッジ）
- [ ] Google Places API（評価・写真）
- [ ] 有料プラン（月額33,000円）
- [ ] ケアマネ向けUI改善
- [ ] 対応施設種別（居宅/老健/特養）の自己申告項目

## デプロイ

GitHub Pages + Cloudflare DNS（親ドメイン `zaitaku-navi.com` 配下）での公開を想定。

```bash
# 1. dist/ を GitHub リポジトリに push
# 2. GitHub Pages settings で source = main / dist または gh-pages
# 3. Cloudflare DNS で CNAME レコード追加:
#    shika → osawa-ux.github.io (DNS only)
# 4. GitHub Pages settings で custom domain に shika.zaitaku-navi.com を設定
# 5. Enforce HTTPS を有効化（数分〜30分で証明書発行）
```

CNAME ファイルは `build_site.py` が `config/site_config.json` の `cname_domain` から自動生成します。

## 運営

- 運営者: MDX株式会社
- 在宅クリニックナビ（zaitakuclinic-navi.com）の姉妹サイト
