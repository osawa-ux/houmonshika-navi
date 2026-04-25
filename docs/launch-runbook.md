# houmonshika-navi ローンチ Runbook

`https://shika.zaitaku-navi.com/` を公開するための手順書。

## 前提状態（2026-04-24 確認）

| 項目 | 状態 |
|---|---|
| GitHub repo | `osawa-ux/houmonshika-navi`（**private**、master branch） |
| 対象コンテンツ | `dist/` 配下（index.html / clinic/ / pref/ / CNAME 等完成済み） |
| CNAME ファイル | `dist/CNAME = shika.zaitaku-navi.com` ✓ |
| GitHub Pages | **未有効化** |
| DNS (Cloudflare) | **shika サブドメイン未設定** |
| 既存パターン参照 | `houmonshinsatsu-navi`（public, gh-pages branch, `zaitakuclinic-navi.com`）/ `kyotaku-navi`（public, gh-pages branch, `care.zaitaku-navi.com`） |

## アーキテクチャ

```
GitHub repo (houmonshika-navi, gh-pages branch)
      ↓ GitHub Pages 配信 (osawa-ux.github.io)
      ↓
Cloudflare DNS (zaitaku-navi.com zone)
      CNAME: shika → osawa-ux.github.io (DNS only、Proxy オフ推奨)
      ↓
https://shika.zaitaku-navi.com/
      ↑ SSL: GitHub Pages 側で Let's Encrypt 自動発行
```

## ローンチ手順

### Step 1: repo を public にする（GitHub Free Plan 前提）

GitHub Pages で独自ドメインを使うには:
- **public repo** なら GitHub Free でも OK
- private repo のまま使うには GitHub Pro 以上が必要

既存の houmonshinsatsu-navi / kyotaku-navi は public。**パターン踏襲で public にする**のが無難。

```bash
gh repo edit osawa-ux/houmonshika-navi --visibility public --accept-visibility-change-consequences
```

**事前確認事項**:
- repo に秘密情報（.env 系、API keys、個人情報を含むデータ）が commit 履歴に含まれていないか
- データファイル（神奈川県 MVP 2,507 件）に個人情報が含まれていないか（医療情報ネット公開データなので基本 OK）

### Step 2: `gh-pages` branch を作成し、`dist/` 内容を配置

既存パターン（houmonshinsatsu-navi / kyotaku-navi）に合わせて、**`gh-pages` branch を配信元** にする。

```bash
cd ~/projects/houmonshika-navi

# gh-pages という新規 branch を dist/ の内容だけで作る
git checkout --orphan gh-pages
git rm -rf . 2>/dev/null
git checkout master -- dist
# dist の中身を root に移動
git mv dist/* .
rmdir dist

# 確認: CNAME が root にあるか
cat CNAME    # shika.zaitaku-navi.com が出るはず

# commit + push
git add -A
git commit -m "publish: initial gh-pages from dist/ (神奈川MVP 2,507件)"
git push -u origin gh-pages

# master に戻る
git checkout master
```

**別案**: `dist/` をそのまま master に残し、Pages source を `master branch / dist folder` に設定する方式も GitHub 最新 UI なら選べる。ただし houmonshinsatsu-navi / kyotaku-navi 方式に合わせるなら gh-pages が一貫。

### Step 3: GitHub Pages を有効化

```bash
# gh api で有効化
gh api -X POST repos/osawa-ux/houmonshika-navi/pages \
  -f 'source[branch]=gh-pages' \
  -f 'source[path]=/' \
  --header 'Accept: application/vnd.github+json'

# 確認
gh api repos/osawa-ux/houmonshika-navi/pages --jq '{url:.html_url, branch:.source.branch, path:.source.path, cname:.cname}'
```

期待値:
```json
{
  "url": "https://shika.zaitaku-navi.com/",
  "branch": "gh-pages",
  "path": "/",
  "cname": "shika.zaitaku-navi.com"
}
```

Pages build 完了まで 1〜5 分。

### Step 4: Cloudflare DNS に CNAME 追加

Cloudflare ダッシュボード（zaitaku-navi.com zone）で追加:

```
Type   : CNAME
Name   : shika
Target : osawa-ux.github.io
Proxy  : DNS only (グレー雲)  ← 重要: Proxy ONだと GitHub Pages の証明書発行に失敗する
TTL    : Auto
```

または API 経由（cloudflare-manager 拡張で可能）:

```bash
# 前提: CF_API_TOKEN を取得、zaitaku-navi.com の zone_id を取得
export CF_API_TOKEN='<token>'
ZONE_ID=$(curl -s "https://api.cloudflare.com/client/v4/zones?name=zaitaku-navi.com" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  | jq -r '.result[0].id')

curl -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type":"CNAME","name":"shika","content":"osawa-ux.github.io","ttl":1,"proxied":false}'
```

### Step 5: DNS 伝播確認 + HTTPS 強制化

```bash
# DNS 伝播確認（数分〜数時間）
nslookup shika.zaitaku-navi.com 8.8.8.8
# → osawa-ux.github.io に解決されれば OK

# HTTP 接続確認
curl -sI "http://shika.zaitaku-navi.com/" | head -3
# → 301 Permanent Redirect to HTTPS もしくは 200

# GitHub Pages で HTTPS を強制（Let's Encrypt 証明書発行完了後）
gh api -X PUT repos/osawa-ux/houmonshika-navi/pages \
  -f 'https_enforced=true' \
  --header 'Accept: application/vnd.github+json'

# 最終確認
curl -sI "https://shika.zaitaku-navi.com/" | head -5
# → 200 OK / Server: GitHub.com
```

### Step 6: Data Integrity Check（必須）

Pre-Deploy Validation のルールに従い:

```bash
# MVP データ件数確認
# data/ または build 出力で件数検証
python scripts/verify_build.py   # 存在すれば

# 代表ページの手動確認
curl -s "https://shika.zaitaku-navi.com/" | grep -o "2,507\|神奈川" | head -3
curl -s "https://shika.zaitaku-navi.com/pref/kanagawa.html" | head -20
```

期待値: 神奈川県 MVP 2,507 件が表示されること。

### Step 7: SEO 登録

- Google Search Console でプロパティ追加: `https://shika.zaitaku-navi.com`
- 親ハブ `zaitaku-navi.com` の関連サブドメインとして紐付け
- sitemap.xml 送信: `https://shika.zaitaku-navi.com/sitemap.xml`
- robots.txt 確認: `https://shika.zaitaku-navi.com/robots.txt`

### Step 8: alldomain-check の config 更新

ローンチ完了後:

```bash
# ~/.claude/skills/alldomain-check/config.json の shika エントリを更新
# { "host": "shika.zaitaku-navi.com", "expected": "not-launched" }
# ↓
# { "host": "shika.zaitaku-navi.com", "expected": "200" }
```

次回チェック時に healthy として表示されれば OK。

## ロールバック

**DNS** （Cloudflare）: CNAME を削除するだけで即座にロールバック（DNS 伝播待ちあり）
**Pages**: `gh api -X DELETE repos/osawa-ux/houmonshika-navi/pages` で無効化
**repo public/private**: `gh repo edit osawa-ux/houmonshika-navi --visibility private --accept-visibility-change-consequences`

## 判断ポイント（人間確認）

- [ ] repo を public にして問題ない（秘密情報漏洩リスクの最終確認）
- [ ] 神奈川 MVP 2,507 件で公開してよい（全国展開前に検索需要を観測する戦略でOK？）
- [ ] `dist/` を `gh-pages` branch に移す方式でよい（master に dist/ を残す運用継続？）
- [ ] Cloudflare Proxy: DNS only で OK（SEO / セキュリティ上、Proxy ON を検討しない？）

## 参考: 既存成功例の設定

| 項目 | houmonshinsatsu-navi | kyotaku-navi |
|---|---|---|
| visibility | public | public |
| Pages source | gh-pages branch, / | gh-pages branch, / |
| CNAME | zaitakuclinic-navi.com | care.zaitaku-navi.com |
| Cloudflare | Proxy ON (Bot Fight Mode 有効) | DNS only |
| Let's Encrypt | 自動発行済 | 自動発行済 |
