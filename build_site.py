"""
訪問歯科ナビ 静的サイト生成スクリプト

使用方法:
  python build_site.py              # サイト生成
  python build_site.py --build-only # サイト生成（heartbeatを記録しない）
  python build_site.py --preview    # 生成後にローカルサーバー起動

入力: data/normalized/clinics_dental.json
生成物:
  dist/
  ├── index.html                     # 神奈川県トップ
  ├── pref/kanagawa.html             # 都道府県ページ
  ├── pref/kanagawa/{city}.html      # 市区町村ページ
  ├── clinic/{clinic_id}.html        # 歯科詳細ページ
  ├── about.html                     # 運営者情報
  ├── data/
  │   ├── search/14.json             # 神奈川県検索JSON
  │   └── clinics_geo.json           # 地図用軽量JSON
  ├── static/
  │   ├── style.css
  │   └── search.js
  ├── sitemap.xml
  ├── robots.txt
  └── .nojekyll

設計: kyotaku-navi/build_site.py をベースに歯科向けカスタマイズ
"""
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from html import escape as _html_escape
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding='utf-8')

# =============================================================
# 設定読み込み
# =============================================================

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / 'config' / 'site_config.json'

with open(CONFIG_PATH, encoding='utf-8') as f:
    CFG = json.load(f)

SITE_NAME = CFG['site_name']
SITE_DESC = CFG['site_description']
SITE_URL = CFG.get('site_url', '').rstrip('/')
CNAME_DOMAIN = CFG.get('cname_domain', '')
PARENT_BRAND = CFG.get('parent_brand', '')
PARENT_BRAND_URL = CFG.get('parent_brand_url', '').rstrip('/')
ENTITY_NAME = CFG.get('entity_name', '歯科')
ENTITY_TYPE = CFG.get('entity_type', '訪問歯科対応の歯科診療所')
CARE_TYPE = CFG.get('care_type', '訪問歯科診療')
OPERATOR_NAME = CFG.get('operator_name', 'MDX株式会社')
OPERATOR_URL = CFG.get('operator_url', '')
OPERATOR_PRIVACY_URL = CFG.get('operator_privacy_url', '')
OPERATOR_CONTACT_URL = CFG.get('operator_contact_url', '')
DATA_RECORDED_DATE = CFG.get('data_recorded_date', '')
NEARBY_MIN_COVERAGE_RATIO = float(CFG.get('nearby_min_coverage_ratio', 0.8))
GA4_ID = CFG.get('analytics', {}).get('ga4_id', '')
ATTRIBUTION = CFG.get('attribution', {}).get('source', '')
ATTRIBUTION_URL = CFG.get('attribution', {}).get('source_url', '')
PORTAL_NETWORK_LINKS = CFG.get('portal_network_links', [])

DATA_FILE = BASE_DIR / 'data' / 'normalized' / 'clinics_dental.json'
DIST_DIR = BASE_DIR / CFG.get('build', {}).get('output_dir', 'dist')

# =============================================================
# 都道府県マスタ
# =============================================================

PREF_SLUG = {
    '01': 'hokkaido', '02': 'aomori', '03': 'iwate', '04': 'miyagi', '05': 'akita',
    '06': 'yamagata', '07': 'fukushima', '08': 'ibaraki', '09': 'tochigi', '10': 'gunma',
    '11': 'saitama', '12': 'chiba', '13': 'tokyo', '14': 'kanagawa', '15': 'niigata',
    '16': 'toyama', '17': 'ishikawa', '18': 'fukui', '19': 'yamanashi', '20': 'nagano',
    '21': 'gifu', '22': 'shizuoka', '23': 'aichi', '24': 'mie', '25': 'shiga',
    '26': 'kyoto', '27': 'osaka', '28': 'hyogo', '29': 'nara', '30': 'wakayama',
    '31': 'tottori', '32': 'shimane', '33': 'okayama', '34': 'hiroshima', '35': 'yamaguchi',
    '36': 'tokushima', '37': 'kagawa', '38': 'ehime', '39': 'kochi', '40': 'fukuoka',
    '41': 'saga', '42': 'nagasaki', '43': 'kumamoto', '44': 'oita', '45': 'miyazaki',
    '46': 'kagoshima', '47': 'okinawa',
}

PREF_CODE_TO_NAME = {
    '01': '北海道', '02': '青森県', '03': '岩手県', '04': '宮城県', '05': '秋田県',
    '06': '山形県', '07': '福島県', '08': '茨城県', '09': '栃木県', '10': '群馬県',
    '11': '埼玉県', '12': '千葉県', '13': '東京都', '14': '神奈川県', '15': '新潟県',
    '16': '富山県', '17': '石川県', '18': '福井県', '19': '山梨県', '20': '長野県',
    '21': '岐阜県', '22': '静岡県', '23': '愛知県', '24': '三重県', '25': '滋賀県',
    '26': '京都府', '27': '大阪府', '28': '兵庫県', '29': '奈良県', '30': '和歌山県',
    '31': '鳥取県', '32': '島根県', '33': '岡山県', '34': '広島県', '35': '山口県',
    '36': '徳島県', '37': '香川県', '38': '愛媛県', '39': '高知県', '40': '福岡県',
    '41': '佐賀県', '42': '長崎県', '43': '熊本県', '44': '大分県', '45': '宮崎県',
    '46': '鹿児島県', '47': '沖縄県',
}

# =============================================================
# ユーティリティ
# =============================================================

def h(s):
    """HTMLエスケープ"""
    if s is None:
        return ''
    return _html_escape(str(s))


def city_slug(city_name: str) -> str:
    """市区町村名からURL安全な slug を生成"""
    return quote(city_name, safe='')


def clinic_slug(clinic_id: str) -> str:
    """歯科IDからファイル名安全な slug を生成"""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', clinic_id)


def page_root(depth: int) -> str:
    """生成ページから成果物ルートへのdocument-relative prefix。"""
    return '../' * depth


def internal_url(depth: int, path: str = '') -> str:
    """同じ成果物をドメイン直下と /shika/ 配下の両方で使える相対URL。"""
    normalized = path.lstrip('/')
    return page_root(depth) + (normalized or 'index.html')


def visiting_status(c) -> str:
    """公開UIで使う訪問歯科情報の3状態。"""
    if c.get('detail_status') == 'unknown':
        return 'unknown'
    if c.get('has_visiting_dental'):
        return 'confirmed_yes'
    return 'confirmed_no'


# =============================================================
# CSS（歯科向けカラー: #0066a0 ティールブルー）
# =============================================================

COMMON_CSS = """\
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;color:#263746;line-height:1.7;background:#f5f7fa}
a{color:#005f96;text-decoration:underline;text-underline-offset:2px}.city-link,.site-title{text-decoration:none}a:hover{text-decoration-thickness:2px}
a:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid #b45309;outline-offset:3px}
.skip-link{position:absolute;left:8px;top:-80px;background:#fff;color:#003b5c;padding:10px 14px;z-index:1000}.skip-link:focus{top:8px}
.container{max-width:1000px;margin:0 auto;padding:20px 16px}
header{background:linear-gradient(135deg,#0066a0 0%,#004d7a 100%);color:#fff;padding:14px 0;box-shadow:0 2px 4px rgba(0,0,0,.1)}
header .header-inner{max-width:1000px;margin:0 auto;padding:0 16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.site-title{color:#fff;font-size:1.3em;font-weight:bold;display:flex;align-items:center;min-height:44px}.site-subtitle{color:#fff;font-size:.85em;margin-top:2px}
header nav a{color:#fff;font-size:.9em;margin-left:12px;display:inline-flex;align-items:center;min-height:44px}
.breadcrumb{font-size:.9em;color:#4b5965;margin:16px auto 8px;padding:0 16px;max-width:1000px}.breadcrumb a{color:#005f96}
.hero{background:#fff;padding:28px 20px;border-radius:10px;margin-bottom:20px;border-left:4px solid #0066a0}.hero h1{font-size:1.6em;margin-bottom:10px;color:#005f96}.hero p{color:#394b59;margin-bottom:8px}
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;margin:16px 0}.card{background:#fff;border:1px solid #d6dce1;border-radius:8px;padding:16px;position:relative}.card:hover{box-shadow:0 4px 12px rgba(0,102,160,.1);border-color:#0066a0}.card h3{font-size:1em;margin-bottom:8px;line-height:1.4}.card .meta{font-size:.9em;color:#4b5965;line-height:1.6}.card .meta span{display:block}.card .specs{margin-top:6px;font-size:.8em;color:#4b5965}
.badges{margin:8px 0 0;display:flex;flex-wrap:wrap;gap:6px}.badge{display:inline-block;padding:4px 10px;border-radius:12px;font-size:.78em;font-weight:bold;white-space:nowrap}.badge-visit{background:#fff3cd;color:#664d03;border:1px solid #e6c96b}.badge-hyg{background:#d1ecf1;color:#0c5460;border:1px solid #8fc3cf}.badge-no{background:#eef1f3;color:#3e4b55;border:1px solid #b8c0c7}.badge-unknown{background:#f3e8ff;color:#5b247a;border:1px solid #caa8df}.badge-specialty{background:#e9ecef;color:#3f4a54;border:1px solid #cbd1d6;font-weight:normal}
.filter-bar{background:#fff;padding:14px 16px;border-radius:8px;margin:16px 0;border:1px solid #d6dce1;display:flex;flex-wrap:wrap;gap:12px;align-items:center}.filter-bar label,.check-label{font-size:.95em;cursor:pointer;user-select:none;display:inline-flex;align-items:center;min-height:44px;padding:0 6px}.filter-bar input[type=checkbox],.check-label input{width:20px;height:20px;margin-right:7px}.filter-bar .count{margin-left:auto;font-size:.9em;color:#4b5965}
.text-input{width:100%;min-height:44px;padding:9px 12px;border:1px solid #7b8791;border-radius:4px;font-size:1em}.field-label{display:block;font-weight:bold;margin-bottom:4px}.help,.status-note{font-size:.9em;color:#4b5965;margin-top:4px}
.city-grid{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 20px}.city-link{display:inline-flex;align-items:center;min-height:44px;padding:7px 12px;background:#fff;border:1px solid #cbd1d6;border-radius:18px;font-size:.9em;white-space:nowrap}.city-link:hover{background:#e3f2fd;border-color:#0066a0}.city-link .count{color:#46535e;font-size:.9em;margin-left:4px}
.detail-header{background:#fff;padding:24px;border-radius:10px;margin-bottom:20px;border-left:4px solid #0066a0}.detail-header h1{font-size:1.5em;margin-bottom:10px;color:#005f96}.info-table{width:100%;border-collapse:collapse;margin:16px 0;background:#fff}.info-table th{text-align:left;padding:12px 14px;background:#f8f9fa;border:1px solid #d6dce1;width:150px;font-size:.9em;color:#394b59;vertical-align:top}.info-table td{padding:12px 14px;border:1px solid #d6dce1;font-size:.95em}.map-container{margin:16px 0;border-radius:8px;overflow:hidden;background:#fff;padding:4px}
.stats-bar{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:16px 0}.stat-box{background:#fff;border:1px solid #d6dce1;border-radius:8px;padding:14px 10px;text-align:center}.stat-box .num{font-size:1.8em;font-weight:bold;color:#005f96}.stat-box .label{font-size:.85em;color:#46535e;margin-top:2px}
.search-box{margin:16px 0;padding:16px;background:#fff;border:1px solid #d6dce1;border-radius:8px}.search-controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.button{border:0;border-radius:6px;background:#0066a0;color:#fff;min-height:44px;padding:9px 16px;font-weight:bold;cursor:pointer}.button-secondary{background:#fff;color:#005f96;border:2px solid #0066a0}.error{color:#a61b1b;font-weight:bold}.notice{padding:16px;border-left:4px solid #8a5a00;background:#fff8e6;margin:16px 0}.status-region{min-height:28px;margin-top:8px}
main a{display:inline-flex;align-items:center;min-height:44px}
footer{background:#263746;color:#fff;padding:32px 0;margin-top:40px;font-size:.9em}footer .footer-inner{max-width:1000px;margin:0 auto;padding:0 16px}footer a{color:#9bddff}footer .note{font-size:.9em;color:#e1e7eb;margin-top:12px;line-height:1.6}.footer-links{display:flex;flex-wrap:wrap;gap:4px 18px;margin-top:14px}.footer-links a{display:inline-flex;align-items:center;min-height:44px}.footer-bottom{margin-top:16px;padding-top:12px;border-top:1px solid #71808d;text-align:center;color:#e1e7eb;font-size:.85em}.portal-network{margin-top:20px;padding-top:16px;border-top:1px solid #71808d}.portal-network h3{font-size:.95em;color:#fff;margin-bottom:8px;font-weight:normal}.portal-network ul{list-style:none}.portal-network li{font-size:.9em;color:#e1e7eb;width:100%;margin:3px 0}
@media(max-width:600px){.card-grid{grid-template-columns:1fr}header .header-inner{flex-direction:column;align-items:flex-start}.info-table th{width:105px;font-size:.85em;padding:8px}.info-table td{font-size:.9em;padding:8px}.hero h1{font-size:1.3em}.detail-header h1{font-size:1.2em}.stats-bar{gap:7px}.stat-box{padding:10px 4px}.stat-box .num{font-size:1.35em}.stat-box .label{font-size:.72em}.filter-bar{align-items:stretch}.filter-bar .count{width:100%;margin-left:0}}
"""

# =============================================================
# 検索・フィルタJS
# =============================================================

SEARCH_JS = """\
(function(){
  var cards=document.querySelectorAll('.clinic-card'),qInput=document.getElementById('q-input'),includeAll=document.getElementById('filter-all'),hygOnly=document.getElementById('filter-hyg'),countLabel=document.getElementById('count-label'),total=cards.length;
  function applyFilter(){var q=qInput?qInput.value.trim().toLowerCase():'',all=includeAll&&includeAll.checked,hy=hygOnly&&hygOnly.checked,shown=0;cards.forEach(function(c){var ok=(!q||(c.dataset.name||'').toLowerCase().indexOf(q)>=0||(c.dataset.addr||'').toLowerCase().indexOf(q)>=0)&&(all||c.dataset.status==='confirmed_yes')&&(!hy||c.dataset.hyg==='1');c.hidden=!ok;if(ok)shown++;});if(countLabel)countLabel.textContent=shown+' / '+total+' 件表示中'+(all?'（全掲載）':'（訪問歯科対応確認済み）');}
  if(qInput)qInput.addEventListener('input',applyFilter);if(includeAll)includeAll.addEventListener('change',applyFilter);if(hygOnly)hygOnly.addEventListener('change',applyFilter);applyFilter();
  var input=document.getElementById('search-input'),results=document.getElementById('search-results'),searchStatus=document.getElementById('search-status'),searchAll=document.getElementById('search-all'),retry=document.getElementById('search-retry'),data=[],loadState='idle',prefCode=document.body.dataset.prefCode||'',root=document.body.dataset.pageRoot||'';
  function esc(s){if(!s)return'';var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
  function status(msg,isError){if(!searchStatus)return;searchStatus.textContent=msg;searchStatus.className='status-region'+(isError?' error':'');}
  function load(){loadState='loading';data=[];if(retry)retry.hidden=true;status('検索データを読み込んでいます…');return fetch(root+'data/search/'+prefCode+'.json').then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}).then(function(d){if(!Array.isArray(d))throw new Error('invalid');data=d;loadState='ready';status('2文字以上入力すると検索します。');if(input.value.trim().length>=2)doSearch();}).catch(function(){loadState='error';status('検索データを読み込めませんでした。再試行するか、市区町村から探してください。',true);if(retry)retry.hidden=false;});}
  if(prefCode&&input){load();if(retry)retry.addEventListener('click',load);if(searchAll)searchAll.addEventListener('change',function(){if(input.value.trim().length>=2)doSearch();});var timer;input.addEventListener('input',function(){clearTimeout(timer);timer=setTimeout(doSearch,200);});
    function doSearch(){var q=input.value.trim().toLowerCase();if(q.length<2){results.innerHTML='';status('2文字以上入力すると検索します。');return;}if(loadState==='loading'){status('検索データを読み込んでいます…');return;}if(loadState==='error'){status('検索データを読み込めませんでした。再試行してください。',true);return;}var all=searchAll&&searchAll.checked;var hits=data.filter(function(o){return(all||o.s==='confirmed_yes')&&(o.st||'').toLowerCase().indexOf(q)>=0;}).slice(0,30);if(!hits.length){results.innerHTML='';status('条件に一致する歯科は見つかりませんでした。');return;}results.innerHTML=hits.map(function(o){var badges=o.s==='confirmed_yes'?'<span class="badge badge-visit">訪問歯科対応確認済み</span>':(o.s==='unknown'?'<span class="badge badge-unknown">訪問対応情報 未確認</span>':'<span class="badge badge-no">訪問歯科情報の掲載なし</span>');if(o.h)badges+='<span class="badge badge-hyg">歯科衛生士訪問</span>';return '<div class="card" style="margin-bottom:8px"><h3><a href="'+root+'clinic/'+encodeURIComponent(o.slug)+'.html">'+esc(o.n)+'</a></h3><div class="meta"><span class="addr">'+esc(o.a)+'</span>'+(o.tel?'<span class="tel">TEL: '+esc(o.tel)+'</span>':'')+'</div><div class="badges">'+badges+'</div></div>';}).join('');status(hits.length+'件を表示しています。');}
  }
})();
"""

# =============================================================
# HTML生成ヘルパー
# =============================================================

def make_head(title, desc, canonical, depth=0, extra_head='', noindex=False):
    ga_tag = ''
    if GA4_ID:
        ga_tag = f'''<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA4_ID}');</script>'''
    robots = '<meta name="robots" content="noindex,follow">' if noindex else ''
    return f'''<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{h(title)}</title><meta name="description" content="{h(desc)}"><link rel="canonical" href="{h(canonical)}">{robots}
<meta property="og:title" content="{h(title)}"><meta property="og:description" content="{h(desc)}"><meta property="og:type" content="website"><meta property="og:url" content="{h(canonical)}"><meta property="og:site_name" content="{h(SITE_NAME)}"><meta property="og:locale" content="ja_JP">
<link rel="stylesheet" href="{h(internal_url(depth, 'static/style.css'))}">{ga_tag}{extra_head}</head>'''


def make_header(depth=0):
    return f'''<a class="skip-link" href="#main-content">本文へ移動</a><header><div class="header-inner"><div><a href="{h(internal_url(depth))}" class="site-title">{h(SITE_NAME)}</a><div class="site-subtitle">訪問歯科対応を確認できる歯科検索ポータル</div></div><nav aria-label="主要メニュー"><a href="{h(internal_url(depth, 'about.html'))}">このサイトについて</a></nav></div></header>'''


def make_breadcrumb(items, depth=0):
    parts=[]; ld_items=[]
    for i,(label,path) in enumerate(items):
        if i==len(items)-1: parts.append(f'<span aria-current="page">{h(label)}</span>')
        else: parts.append(f'<a href="{h(internal_url(depth,path))}">{h(label)}</a>')
        absolute = path if str(path).startswith('http') else f'{SITE_URL}/{str(path).lstrip("/")}'
        ld_items.append({'@type':'ListItem','position':i+1,'name':label,'item':absolute})
    ld={'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':ld_items}
    return f'<nav class="breadcrumb" aria-label="パンくず">{" &gt; ".join(parts)}</nav><script type="application/ld+json">{json.dumps(ld,ensure_ascii=False)}</script>'


def make_footer(depth=0):
    network=''
    if PORTAL_NETWORK_LINKS:
        items=''.join(f'<li><a href="{h(x["href"])}">{h(x["anchor"])}</a> — {h(x["description"])}</li>' for x in PORTAL_NETWORK_LINKS)
        network=f'<section class="portal-network" aria-labelledby="network-title"><h3 id="network-title">在宅ナビシリーズ</h3><ul>{items}</ul></section>'
    operator = f'<a href="{h(OPERATOR_URL)}" target="_blank" rel="noopener">{h(OPERATOR_NAME)}</a>' if OPERATOR_URL else h(OPERATOR_NAME)
    return f'''<footer><div class="footer-inner"><p><strong>{h(SITE_NAME)}</strong> — 神奈川県の歯科情報と訪問歯科対応の確認状況を探せるポータルサイト</p>
<p class="note">情報は <a href="{h(ATTRIBUTION_URL)}" target="_blank" rel="noopener">{h(ATTRIBUTION)}</a> をもとに作成しています。データ取得基準日は確認中です。データファイル初回収録日: {h(DATA_RECORDED_DATE)}。実際の対応可否・料金は各歯科へ直接ご確認ください。</p>
<nav class="footer-links" aria-label="サイト情報"><a href="{h(internal_url(depth,'about.html'))}">このサイトについて</a><a href="{h(internal_url(depth,'privacy.html'))}">プライバシー</a><a href="{h(internal_url(depth,'terms.html'))}">利用規約</a><a href="{h(internal_url(depth,'contact.html'))}">お問い合わせ</a></nav>{network}
<div class="footer-bottom">&copy; 2026 {h(SITE_NAME)}（運営: {operator}）</div></div></footer></body></html>'''


def status_badge(c):
    status=visiting_status(c)
    if status=='confirmed_yes': return '<span class="badge badge-visit">訪問歯科対応確認済み</span>'
    if status=='unknown': return '<span class="badge badge-unknown">訪問対応情報 未確認</span>'
    return '<span class="badge badge-no">訪問歯科情報の掲載なし</span>'


def make_clinic_card(c, depth):
    cid=clinic_slug(c['clinic_id']);name=c.get('name','');addr=c.get('address','');tel=c.get('tel','');specs=c.get('specialties',[]);has_h=c.get('has_hygienist_visit',False);status=visiting_status(c)
    specs_html='<div class="specs">'+' / '.join(h(s) for s in specs[:5])+'</div>' if specs else ''
    tel_html=f'<span class="tel">TEL: {h(tel)}</span>' if tel else ''
    hyg='<span class="badge badge-hyg">歯科衛生士訪問</span>' if has_h else ''
    return f'''<article class="card clinic-card" data-name="{h(name)}" data-addr="{h(addr)}" data-status="{status}" data-hyg="{1 if has_h else 0}"><h3><a href="{h(internal_url(depth,f'clinic/{cid}.html'))}">{h(name)}</a></h3><div class="meta"><span class="addr">{h(addr)}</span>{tel_html}</div>{specs_html}<div class="badges">{status_badge(c)}{hyg}</div></article>'''

# =============================================================
# ページ生成関数
# =============================================================

def build_index(clinics, pref_name, visiting_count, depth=0, canonical_path=''):
    total=len(clinics);unknown=sum(1 for c in clinics if visiting_status(c)=='unknown');cities=defaultdict(list)
    for c in clinics:cities[c['city']].append(c)
    title=f'{SITE_NAME}｜{pref_name}の訪問歯科対応確認済み{visiting_count:,}件'
    desc=f'{pref_name}の歯科{total:,}件を掲載。訪問歯科対応確認済み{visiting_count:,}件、訪問対応情報未確認{unknown:,}件。市区町村・名称・住所から検索できます。'
    canonical=f'{SITE_URL}/{canonical_path}'
    city_html='<div class="city-grid">'
    for cname,clist in sorted(cities.items(),key=lambda x:-sum(1 for c in x[1] if visiting_status(c)=='confirmed_yes')):
        yes=sum(1 for c in clist if visiting_status(c)=='confirmed_yes');city_html+=f'<a href="{h(internal_url(depth,f"pref/kanagawa/{city_slug(cname)}.html"))}" class="city-link">{h(cname)}<span class="count">対応確認済み {yes}</span></a>'
    city_html+='</div>'
    body=f'''<body data-pref-code="14" data-page-root="{h(page_root(depth))}" data-default-status="confirmed_yes">{make_header(depth)}<main id="main-content" class="container"><div class="hero"><h1>{h(pref_name)}の訪問歯科対応を確認できる歯科を探す</h1><p>初期表示は、医療情報ネットで歯科訪問診療の情報を確認できた<strong>{visiting_count:,}件</strong>です。全掲載<strong>{total:,}件</strong>も明示的に切り替えて検索できます。</p></div>
<div class="stats-bar"><div class="stat-box"><div class="num">{total:,}</div><div class="label">全掲載歯科</div></div><div class="stat-box"><div class="num">{visiting_count:,}</div><div class="label">訪問対応確認済み</div></div><div class="stat-box"><div class="num">{unknown:,}</div><div class="label">訪問対応情報 未確認</div></div></div>
<section class="search-box" aria-labelledby="search-heading"><h2 id="search-heading" style="font-size:1.15em">名称・住所から探す</h2><label class="field-label" for="search-input">歯科名または住所</label><input class="text-input" type="search" id="search-input" autocomplete="off"><p class="help">2文字以上入力してください。初期設定では訪問歯科対応確認済みのみ検索します。</p><label class="check-label"><input type="checkbox" id="search-all" aria-label="全掲載歯科から検索">対応情報未確認・訪問歯科情報の掲載なしを含む全歯科から検索</label><div id="search-status" class="status-region" role="status" aria-live="polite">検索データを読み込んでいます…</div><button id="search-retry" class="button button-secondary" type="button" hidden>再試行</button><div id="search-results" aria-live="polite"></div></section>
<h2 style="margin-top:28px;font-size:1.15em">市区町村から探す</h2><p class="help">件数は訪問歯科対応を確認できた歯科です。市区町村ページで全掲載への切替ができます。</p>{city_html}
<p class="notice">「対応確認済み」は情報掲載を示すもので、現在の訪問可否・訪問範囲を保証しません。実際の対応可否・料金は各歯科に直接ご確認ください。</p></main>{make_footer(depth)}'''
    extra=f'<script src="{h(internal_url(depth,"static/search.js"))}" defer></script>'
    return make_head(title,desc,canonical,depth,extra)+body


def build_city_page(city_name, clinics_in_city, pref_name):
    depth=2;n=len(clinics_in_city);visiting_n=sum(1 for c in clinics_in_city if visiting_status(c)=='confirmed_yes');unknown_n=sum(1 for c in clinics_in_city if visiting_status(c)=='unknown');cslug=city_slug(city_name)
    title=f'{city_name}（{pref_name}）の訪問歯科対応確認済み{visiting_n}件 | {SITE_NAME}';desc=f'{pref_name}{city_name}の歯科{n}件。訪問歯科対応確認済み{visiting_n}件、訪問対応情報未確認{unknown_n}件。'
    sorted_clinics=sorted(clinics_in_city,key=lambda c:({'confirmed_yes':0,'unknown':1,'confirmed_no':2}[visiting_status(c)],not c.get('has_hygienist_visit'),c.get('name','')));cards=''.join(make_clinic_card(c,depth) for c in sorted_clinics)
    bc=make_breadcrumb([('トップ',''),(pref_name,'pref/kanagawa.html'),(city_name,'')],depth)
    body=f'''<body data-page-root="{page_root(depth)}" data-default-status="confirmed_yes">{make_header(depth)}{bc}<main id="main-content" class="container"><div class="hero"><h1>{h(city_name)}の訪問歯科対応を確認できる歯科</h1><p>全掲載<strong>{n}件</strong>、訪問歯科対応確認済み<strong>{visiting_n}件</strong>、訪問対応情報未確認<strong>{unknown_n}件</strong>です。初期表示は対応確認済みのみです。</p></div>
<div class="filter-bar"><div style="flex:1;min-width:220px"><label class="field-label" for="q-input">名前・住所で絞り込み</label><input class="text-input" type="search" id="q-input"></div><label><input type="checkbox" id="filter-all" aria-label="全掲載を表示">全掲載を表示</label><label><input type="checkbox" id="filter-hyg" aria-label="歯科衛生士訪問あり">歯科衛生士訪問あり</label><span class="count" id="count-label" role="status" aria-live="polite"></span></div><div class="card-grid">{cards}</div><p><a href="{h(internal_url(depth,'pref/kanagawa.html'))}">&larr; {h(pref_name)}の一覧に戻る</a></p></main>{make_footer(depth)}'''
    items=[{'@type':'ListItem','position':i,'url':f'{SITE_URL}/clinic/{clinic_slug(c["clinic_id"])}.html','name':c.get('name','')} for i,c in enumerate(sorted_clinics[:20],1)]
    extra=f'<script src="{h(internal_url(depth,"static/search.js"))}" defer></script><script type="application/ld+json">{json.dumps({"@context":"https://schema.org","@type":"ItemList","numberOfItems":n,"itemListElement":items},ensure_ascii=False)}</script>'
    return make_head(title,desc,f'{SITE_URL}/pref/kanagawa/{cslug}.html',depth,extra)+body


def build_clinic_page(c,pref_name):
    depth=1;cid=clinic_slug(c['clinic_id']);name=c.get('name','');city=c.get('city','');addr=c.get('address','');postal=c.get('postal','');tel=c.get('tel','');url=c.get('url','');specs=c.get('specialties',[]);source_url=c.get('source_url','');lat=c.get('latitude');lng=c.get('longitude');status=visiting_status(c);has_h=c.get('has_hygienist_visit',False)
    title=f'{name}｜{city}（{pref_name}） | {SITE_NAME}';desc=f'{name}は{pref_name}{city}の歯科診療所です。訪問歯科情報の確認状態、住所、電話番号を掲載。';canonical=f'{SITE_URL}/clinic/{cid}.html';bc=make_breadcrumb([('トップ',''),(pref_name,'pref/kanagawa.html'),(city,f'pref/kanagawa/{city_slug(city)}.html'),(name,'')],depth)
    rows=[]
    def add(label,val):
        if val:rows.append(f'<tr><th>{h(label)}</th><td>{val}</td></tr>')
    add('歯科名',h(name));add('郵便番号',f'〒{h(postal)}' if postal else '');add('住所',h(addr));add('電話番号',f'<a href="tel:{h(tel)}">{h(tel)}</a>' if tel else '');add('公式サイト',f'<a href="{h(url)}" target="_blank" rel="noopener">公式サイトを見る</a>' if url else '');add('診療科目',' '.join(f'<span class="badge badge-specialty">{h(s)}</span>' for s in specs));status_text={'confirmed_yes':'医療情報ネットで歯科訪問診療の情報を確認','confirmed_no':'医療情報ネットの取得情報に歯科訪問診療の掲載なし','unknown':'詳細情報を取得できず、訪問対応情報は未確認'}[status];add('訪問歯科情報',status_text);add('歯科衛生士訪問','医療情報ネットで訪問歯科衛生指導の情報を確認' if has_h else '');add('情報出典',f'<a href="{h(source_url)}" target="_blank" rel="noopener">医療情報ネットで見る</a>' if source_url else '')
    badges=status_badge(c)+(('<span class="badge badge-hyg">歯科衛生士訪問</span>') if has_h else '')
    map_html=''
    if lat and lng:map_html=f'<div class="map-container"><iframe width="100%" height="320" style="border:0" src="https://www.openstreetmap.org/export/embed.html?bbox={lng-0.005},{lat-0.003},{lng+0.005},{lat+0.003}&amp;layer=mapnik&amp;marker={lat},{lng}" loading="lazy" title="{h(name)}の地図"></iframe><p><a href="https://www.google.com/maps?q={lat},{lng}" target="_blank" rel="noopener">Google Mapsで見る</a></p></div>'
    ld={'@context':'https://schema.org','@type':'Dentist','name':name,'address':{'@type':'PostalAddress','addressRegion':pref_name,'addressLocality':city,'streetAddress':addr,'postalCode':postal,'addressCountry':'JP'}}
    if tel:ld['telephone']=tel
    if url:ld['url']=url
    body=f'''<body data-page-root="{page_root(depth)}" data-default-status="confirmed_yes">{make_header(depth)}{bc}<main id="main-content" class="container"><div class="detail-header"><h1>{h(name)}</h1><p>{h(pref_name)} {h(city)}</p><div class="badges">{badges}</div></div><table class="info-table">{"".join(rows)}</table>{map_html}<p><a href="{h(internal_url(depth,f'pref/kanagawa/{city_slug(city)}.html'))}">&larr; {h(city)}の一覧</a></p><p class="notice">掲載情報は医療情報ネットをもとに作成しています。データ取得基準日は確認中です。データファイル初回収録日: {h(DATA_RECORDED_DATE)}。現在の診療内容・訪問可否・料金は必ず歯科へ直接お問い合わせください。</p></main>{make_footer(depth)}'''
    return make_head(title,desc,canonical,depth,f'<script type="application/ld+json">{json.dumps(ld,ensure_ascii=False)}</script>')+body


def build_about_page(total,visiting,unknown):
    depth=0;bc=make_breadcrumb([('トップ',''),('このサイトについて','')],depth)
    body=f'''<body data-page-root="">{make_header(depth)}{bc}<main id="main-content" class="container"><h1>このサイトについて</h1><p>{h(SITE_NAME)}は、神奈川県の歯科情報から訪問歯科対応の確認状況を探せるポータルサイトです。</p><h2>掲載情報</h2><table class="info-table"><tr><th>運営者</th><td><a href="{h(OPERATOR_URL)}" target="_blank" rel="noopener">{h(OPERATOR_NAME)}</a></td></tr><tr><th>全掲載</th><td>{total:,}件</td></tr><tr><th>訪問歯科対応確認済み</th><td>{visiting:,}件</td></tr><tr><th>訪問対応情報 未確認</th><td>{unknown:,}件</td></tr><tr><th>データ出典</th><td><a href="{h(ATTRIBUTION_URL)}" target="_blank" rel="noopener">{h(ATTRIBUTION)}</a></td></tr><tr><th>データ取得基準日</th><td>確認中</td></tr><tr><th>データファイル初回収録日</th><td>{h(DATA_RECORDED_DATE)}</td></tr></table><h2>表示の意味</h2><p>「対応確認済み」は医療情報ネットに歯科訪問診療の情報が掲載されている状態です。「情報の掲載なし」と「詳細情報を取得できず未確認」は区別して表示します。いずれも現在の訪問可否を保証しません。</p><h2>訂正のご連絡</h2><p>掲載情報の訂正は<a href="{h(internal_url(depth,'contact.html'))}">お問い合わせ案内</a>から運営者へご連絡ください。</p></main>{make_footer(depth)}'''
    return make_head(f'このサイトについて | {SITE_NAME}',f'{SITE_NAME}の運営者、掲載件数、データ出典、表示の意味。',f'{SITE_URL}/about.html',depth)+body


def build_nearby_page(total,geo_count,coverage_enabled):
    depth=0
    if coverage_enabled:
        raise RuntimeError('位置情報カバレッジが公開閾値に達しました。現在地検索を実装・再レビューしてから公開してください。')
    body=f'''<body data-page-root="">{make_header(depth)}<main id="main-content" class="container"><div class="hero"><h1>現在地から探す機能は現在ご利用いただけません</h1><p>全掲載{total:,}件のうち、距離検索に必要な位置情報を確認できているのは{geo_count:,}件のみです。検索結果を十分に案内できないため、現在地の取得は行いません。</p></div><p class="notice">現在地はブラウザから取得せず、本サイトのサーバーにも送信しません。市区町村からお探しください。</p><a class="city-link" href="{h(internal_url(depth))}">市区町村から探す</a></main>{make_footer(depth)}'''
    return make_head(f'現在地検索は利用できません | {SITE_NAME}','現在地検索は現在利用できません。市区町村からお探しください。',f'{SITE_URL}/nearby.html',depth,noindex=True)+body


def build_trust_page(kind):
    depth=0
    data={
      'privacy':('プライバシーについて','当サイトはGoogle Analytics 4（GA4）を利用し、閲覧状況を計測します。Googleによるデータの取扱いはGoogleの規約・ポリシーをご確認ください。現在地検索は停止中で、ブラウザの正確な位置情報を当サイトのサーバーへ送信しません。運営者のプライバシーポリシーもご確認ください。',f'<a href="{h(OPERATOR_PRIVACY_URL)}" target="_blank" rel="noopener">運営者のプライバシーポリシー</a>'),
      'terms':('ご利用にあたって','掲載情報は医療情報ネットをもとに作成していますが、現在の診療内容、訪問可否、訪問範囲、料金を保証するものではありません。利用前に各歯科へ直接ご確認ください。',f'<a href="{h(internal_url(depth,"about.html"))}">掲載情報と表示の意味</a>'),
      'contact':('お問い合わせ','掲載情報の訂正や当サイトへのお問い合わせは、運営者MDX株式会社の公式お問い合わせ窓口をご利用ください。',f'<a href="{h(OPERATOR_CONTACT_URL)}" target="_blank" rel="noopener">MDX株式会社のお問い合わせ窓口</a>')}
    title,text,link=data[kind];body=f'''<body data-page-root="">{make_header(depth)}{make_breadcrumb([('トップ',''),(title,'')],depth)}<main id="main-content" class="container"><h1>{title}</h1><p>{text}</p><p style="margin-top:20px">{link}</p></main>{make_footer(depth)}'''
    return make_head(f'{title} | {SITE_NAME}',text,f'{SITE_URL}/{kind}.html',depth)+body

# =============================================================
# JSON生成
# =============================================================

def generate_search_json(clinics, path):
    """検索用JSON（神奈川県版）"""
    entries = []
    for c in clinics:
        search_text = ' '.join(filter(None, [
            c.get('name', ''),
            c.get('city', ''),
            c.get('address', ''),
        ]))
        entries.append({
            'slug': clinic_slug(c['clinic_id']),
            'n': c.get('name', ''),
            'c': c.get('city', ''),
            'a': c.get('address', ''),
            'tel': c.get('tel', ''),
            'v': 1 if c.get('has_visiting_dental') else 0,
            's': visiting_status(c),
            'h': 1 if c.get('has_hygienist_visit') else 0,
            'st': search_text,
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8')
    return len(entries)


def generate_geo_json(clinics, path):
    """地図用軽量JSON"""
    geo = []
    for c in clinics:
        lat = c.get('latitude')
        lng = c.get('longitude')
        if lat and lng:
            geo.append({
                'id': clinic_slug(c['clinic_id']),
                'n': c.get('name', ''),
                'c': c.get('city', ''),
                'a': c.get('address', ''),
                'lt': round(lat, 5),
                'lg': round(lng, 5),
                'v': 1 if c.get('has_visiting_dental') else 0,
                's': visiting_status(c),
            })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(geo, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8')
    return len(geo)


def generate_sitemap(clinics, cities, dist_dir, nearby_enabled=False):
    """sitemap.xml"""
    today = date.today().isoformat()
    urls = []
    urls.append((f'{SITE_URL}/', '1.0', 'weekly'))
    urls.append((f'{SITE_URL}/pref/kanagawa.html', '0.9', 'weekly'))
    urls.append((f'{SITE_URL}/about.html', '0.3', 'yearly'))
    urls.extend((f'{SITE_URL}/{name}.html', '0.2', 'yearly') for name in ('privacy', 'terms', 'contact'))
    if nearby_enabled:
        urls.append((f'{SITE_URL}/nearby.html', '0.5', 'monthly'))

    for cname in cities:
        cslug = city_slug(cname)
        urls.append((f'{SITE_URL}/pref/kanagawa/{cslug}.html', '0.8', 'weekly'))

    for c in clinics:
        cid = clinic_slug(c['clinic_id'])
        urls.append((f'{SITE_URL}/clinic/{cid}.html', '0.5', 'monthly'))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, pri, freq in urls:
        lines.append(f'  <url><loc>{h(url)}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{pri}</priority></url>')
    lines.append('</urlset>')
    (dist_dir / 'sitemap.xml').write_text('\n'.join(lines), encoding='utf-8')
    return len(urls)


def generate_robots(dist_dir):
    """robots.txt"""
    txt = f"""User-agent: *
Disallow: /data/
Allow: /

User-agent: GPTBot
Disallow: /

User-agent: ChatGPT-User
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: anthropic-ai
Disallow: /

User-agent: Claude-Web
Disallow: /

User-agent: Google-Extended
Disallow: /

Sitemap: {SITE_URL}/sitemap.xml
"""
    (dist_dir / 'robots.txt').write_text(txt, encoding='utf-8')


# =============================================================
# メインビルド
# =============================================================

def build_site():
    print(f'=== {SITE_NAME} サイト生成 ===')

    if not DATA_FILE.exists():
        print(f'ERROR: {DATA_FILE} が見つかりません')
        print('先に scripts/normalize.py を実行してください')
        sys.exit(1)

    with open(DATA_FILE, encoding='utf-8') as f:
        clinics = json.load(f)

    total = len(clinics)
    visiting = sum(1 for c in clinics if c.get('has_visiting_dental'))
    hygienist = sum(1 for c in clinics if c.get('has_hygienist_visit'))
    with_coords = sum(1 for c in clinics if c.get('latitude') and c.get('longitude'))
    unknown = sum(1 for c in clinics if c.get('detail_status') == 'unknown')
    print(f'データ: {total:,}件')
    print(f'  訪問歯科対応: {visiting} ({visiting/total*100:.1f}%)')
    print(f'  衛生指導対応: {hygienist} ({hygienist/total*100:.1f}%)')
    print(f'  座標あり: {with_coords} ({with_coords/total*100:.1f}%)')
    print(f'  unknown: {unknown}')

    # 神奈川県のみ対象（MVP）
    pref_code = '14'
    pref_name = '神奈川県'

    # 市区町村別
    cities = defaultdict(list)
    for c in clinics:
        cities[c['city']].append(c)
    print(f'市区町村数: {len(cities)}')

    # 出力ディレクトリ作成
    for d in [DIST_DIR, DIST_DIR / 'pref', DIST_DIR / 'pref' / 'kanagawa',
              DIST_DIR / 'clinic', DIST_DIR / 'static',
              DIST_DIR / 'data', DIST_DIR / 'data' / 'search']:
        d.mkdir(parents=True, exist_ok=True)

    # CSS/JS
    (DIST_DIR / 'static' / 'style.css').write_text(COMMON_CSS, encoding='utf-8')
    (DIST_DIR / 'static' / 'search.js').write_text(SEARCH_JS, encoding='utf-8')
    print('CSS/JS 生成完了')

    # トップページ = 神奈川県ページ（MVPは神奈川県のみ）
    idx = build_index(clinics, pref_name, visiting, depth=0, canonical_path='')
    pref_idx = build_index(clinics, pref_name, visiting, depth=1, canonical_path='pref/kanagawa.html')
    (DIST_DIR / 'index.html').write_text(idx, encoding='utf-8')
    (DIST_DIR / 'pref' / 'kanagawa.html').write_text(pref_idx, encoding='utf-8')
    print('index.html / pref/kanagawa.html 生成完了')

    # 市区町村ページ
    # 注: ファイル名は生日本語（UTF-8）で保存する。
    # ブラウザは URL エンコード済みパス（city_slug）でリクエストするが、
    # GitHub Pages 側が URL デコードして実ファイル（生日本語名）にマッチする。
    # ファイル名自体を URL エンコード済みにすると、リテラル % が含まれて 404 になる。
    for cname, clinics_in_city in cities.items():
        html = build_city_page(cname, clinics_in_city, pref_name)
        (DIST_DIR / 'pref' / 'kanagawa' / f'{cname}.html').write_text(html, encoding='utf-8')
    print(f'市区町村ページ {len(cities)}枚生成完了')

    # 歯科詳細ページ
    for c in clinics:
        cid = clinic_slug(c['clinic_id'])
        html = build_clinic_page(c, pref_name)
        (DIST_DIR / 'clinic' / f'{cid}.html').write_text(html, encoding='utf-8')
    print(f'歯科詳細ページ {len(clinics):,}枚生成完了')

    # 現在地から探すページ
    nearby_enabled = total > 0 and (with_coords / total) >= NEARBY_MIN_COVERAGE_RATIO
    (DIST_DIR / 'nearby.html').write_text(build_nearby_page(total, with_coords, nearby_enabled), encoding='utf-8')
    print('nearby.html 生成完了')

    # About ページ
    about = build_about_page(total, visiting, unknown)
    (DIST_DIR / 'about.html').write_text(about, encoding='utf-8')
    for kind in ('privacy', 'terms', 'contact'):
        (DIST_DIR / f'{kind}.html').write_text(build_trust_page(kind), encoding='utf-8')
    print('about.html 生成完了')

    # 検索JSON
    search_count = generate_search_json(
        clinics, DIST_DIR / 'data' / 'search' / f'{pref_code}.json')
    search_size = (DIST_DIR / 'data' / 'search' / f'{pref_code}.json').stat().st_size
    print(f'検索JSON: {search_count}件 ({search_size/1024:.0f}KB)')

    # 地図用JSON
    geo_count = generate_geo_json(clinics, DIST_DIR / 'data' / 'clinics_geo.json')
    print(f'地図用JSON: {geo_count}件')

    # sitemap
    sitemap_count = generate_sitemap(clinics, cities, DIST_DIR, nearby_enabled)
    print(f'sitemap.xml: {sitemap_count} URL')

    # robots.txt
    generate_robots(DIST_DIR)
    print('robots.txt 生成完了')

    # .nojekyll
    (DIST_DIR / '.nojekyll').write_text('', encoding='utf-8')

    # CNAME（GitHub Pages カスタムドメイン）
    if CNAME_DOMAIN:
        (DIST_DIR / 'CNAME').write_text(f'{CNAME_DOMAIN}\n', encoding='utf-8')

    # 404ページ
    page_404 = make_head(
        f'ページが見つかりません | {SITE_NAME}',
        'お探しのページは存在しません。',
        f'{SITE_URL}/404.html',
        extra_head=f'<base href="{h(SITE_URL)}/">',
        noindex=True,
    )
    page_404 += f"""<body data-page-root="">
{make_header(0)}
<main id="main-content" class="container" style="text-align:center;padding:60px 20px">
  <h1 style="font-size:2.5em;color:#0066a0">404</h1>
  <p style="margin:16px 0">お探しのページが見つかりませんでした。</p>
  <a href="{h(SITE_URL)}/">トップページへ</a>
</main>
{make_footer(0)}"""
    (DIST_DIR / '404.html').write_text(page_404, encoding='utf-8')

    # === 品質チェック ===
    print(f'\n{"=" * 60}')
    print(f'  ビルド完了 品質チェック')
    print(f'{"=" * 60}')
    city_pages = len(list((DIST_DIR / 'pref' / 'kanagawa').glob('*.html')))
    clinic_pages = len(list((DIST_DIR / 'clinic').glob('*.html')))
    print(f'  掲載歯科数: {total:,}')
    print(f'  うち訪問歯科対応: {visiting} ({visiting/total*100:.1f}%)')
    print(f'  市区町村ページ: {city_pages}')
    print(f'  歯科詳細ページ: {clinic_pages:,}')
    print(f'  検索JSON: {search_count}件 ({search_size/1024:.0f}KB)')
    print(f'  座標付き歯科: {geo_count} ({geo_count/total*100:.1f}%)')
    print(f'  sitemap URL: {sitemap_count:,}')

    ok = True
    if clinic_pages != len(clinics):
        print(f'  [WARN] 詳細ページ数不一致: {clinic_pages} vs {len(clinics)}')
        ok = False
    if city_pages != len(cities):
        print(f'  [WARN] 市区町村ページ数不一致: {city_pages} vs {len(cities)}')
        ok = False

    if ok:
        print(f'  [OK] 全チェック通過')
    print(f'{"=" * 60}')

    # heartbeat: record last run (fail-safe, never raises)
    if '--preview' not in sys.argv and '--build-only' not in sys.argv:
        try:
            import subprocess as _hb_subprocess
            import sys as _hb_sys
            from pathlib import Path as _hb_Path
            _hb_subprocess.run(
                [_hb_sys.executable, str(_hb_Path.home() / "central-registry" / "scripts" / "heartbeat.py"), "SHIKA-BUILD-01"],
                capture_output=True,
            )
        except Exception:
            pass

    # プレビューサーバー
    if '--preview' in sys.argv:
        import http.server
        import functools
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST_DIR))
        server = http.server.HTTPServer(('localhost', 8000), handler)
        print(f'\nプレビュー: http://localhost:8000/')
        server.serve_forever()


if __name__ == '__main__':
    build_site()
