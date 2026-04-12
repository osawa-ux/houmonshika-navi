# 訪問歯科ナビ（houmonshika-navi）

訪問歯科に対応している歯科診療所を都道府県・市区町村から検索できるポータルサイト。

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

GitHub Pages での公開を想定。

```bash
# dist/ を main ブランチにコミットして push
# GitHub Pages 設定で source = main / root (dist ではなく dist 配下)
# もしくは gh-pages ブランチに dist/ をデプロイ
```

## 運営

- 運営者: MDX株式会社
- 在宅クリニックナビ（zaitakuclinic-navi.com）の姉妹サイト
