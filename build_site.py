"""
訪問歯科ナビ 静的サイト生成スクリプト

使用方法:
  python build_site.py              # サイト生成
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
GA4_ID = CFG.get('analytics', {}).get('ga4_id', '')
ATTRIBUTION = CFG.get('attribution', {}).get('source', '')
ATTRIBUTION_URL = CFG.get('attribution', {}).get('source_url', '')

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


# =============================================================
# CSS（歯科向けカラー: #0066a0 ティールブルー）
# =============================================================

COMMON_CSS = """\
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;color:#2c3e50;line-height:1.7;background:#f5f7fa}
a{color:#0066a0;text-decoration:none}a:hover{text-decoration:underline}
.container{max-width:1000px;margin:0 auto;padding:20px 16px}

/* Header */
header{background:linear-gradient(135deg,#0066a0 0%,#004d7a 100%);color:#fff;padding:14px 0;box-shadow:0 2px 4px rgba(0,0,0,0.1)}
header .header-inner{max-width:1000px;margin:0 auto;padding:0 16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.site-title{color:#fff;font-size:1.3em;font-weight:bold;text-decoration:none;display:block}
.site-title:hover{text-decoration:none}
.site-subtitle{color:rgba(255,255,255,0.85);font-size:0.8em;margin-top:2px}
header nav a{color:rgba(255,255,255,0.9);font-size:0.85em;margin-left:16px}

/* Breadcrumb */
.breadcrumb{font-size:0.85em;color:#666;margin:16px 0 8px;padding:0 16px;max-width:1000px;margin-left:auto;margin-right:auto}
.breadcrumb a{color:#0066a0}

/* Hero */
.hero{background:#fff;padding:28px 20px;border-radius:10px;margin-bottom:20px;border-left:4px solid #0066a0}
.hero h1{font-size:1.6em;margin-bottom:10px;color:#0066a0}
.hero p{color:#555;margin-bottom:8px}

/* Cards */
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;margin:16px 0}
.card{background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:16px;transition:box-shadow 0.2s;position:relative}
.card:hover{box-shadow:0 4px 12px rgba(0,102,160,0.1);border-color:#0066a0}
.card h3{font-size:1em;margin-bottom:8px;line-height:1.4}
.card h3 a{color:#0066a0}
.card .meta{font-size:0.85em;color:#666;line-height:1.6}
.card .meta .addr{display:block}
.card .meta .tel{display:block;margin-top:4px}
.card .specs{margin-top:6px;font-size:0.75em;color:#888}

/* Badges */
.badges{margin:8px 0 0;display:flex;flex-wrap:wrap;gap:6px}
.badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.72em;font-weight:bold;white-space:nowrap}
.badge-visit{background:#fff3cd;color:#856404;border:1px solid #ffeaa7}
.badge-hyg{background:#d1ecf1;color:#0c5460;border:1px solid #bee5eb}
.badge-specialty{background:#e9ecef;color:#495057;border:1px solid #dee2e6;font-weight:normal}

/* Filter */
.filter-bar{background:#fff;padding:14px 16px;border-radius:8px;margin:16px 0;border:1px solid #e0e0e0;display:flex;flex-wrap:wrap;gap:12px;align-items:center}
.filter-bar label{font-size:0.9em;cursor:pointer;user-select:none}
.filter-bar input[type=checkbox]{margin-right:4px;vertical-align:middle}
.filter-bar .count{margin-left:auto;font-size:0.85em;color:#666}

/* City grid */
.city-grid{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 20px}
.city-link{display:inline-block;padding:6px 12px;background:#fff;border:1px solid #ddd;border-radius:16px;font-size:0.88em;white-space:nowrap}
.city-link:hover{background:#e3f2fd;border-color:#0066a0;text-decoration:none}
.city-link .count{color:#888;font-size:0.85em;margin-left:4px}

/* Detail page */
.detail-header{background:#fff;padding:24px;border-radius:10px;margin-bottom:20px;border-left:4px solid #0066a0}
.detail-header h1{font-size:1.5em;margin-bottom:10px;color:#0066a0}
.info-table{width:100%;border-collapse:collapse;margin:16px 0;background:#fff}
.info-table th{text-align:left;padding:12px 14px;background:#f8f9fa;border:1px solid #e0e0e0;width:140px;font-size:0.9em;color:#555;vertical-align:top}
.info-table td{padding:12px 14px;border:1px solid #e0e0e0;font-size:0.95em}
.map-container{margin:16px 0;border-radius:8px;overflow:hidden;background:#fff;padding:4px}

/* Stats */
.stats-bar{display:flex;gap:14px;flex-wrap:wrap;margin:16px 0}
.stat-box{background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:14px 18px;text-align:center;min-width:130px;flex:1;max-width:200px}
.stat-box .num{font-size:1.8em;font-weight:bold;color:#0066a0}
.stat-box .label{font-size:0.8em;color:#888;margin-top:2px}

/* Footer */
footer{background:#2c3e50;color:#fff;padding:32px 0;margin-top:40px;font-size:0.85em}
footer .footer-inner{max-width:1000px;margin:0 auto;padding:0 16px}
footer a{color:#81d4fa}
footer .note{font-size:0.8em;color:#bbb;margin-top:12px;line-height:1.6}
.footer-bottom{margin-top:16px;padding-top:12px;border-top:1px solid #555;text-align:center;color:#999;font-size:0.8em}

/* Search box */
.search-box{margin:16px 0;padding:16px;background:#fff;border:1px solid #e0e0e0;border-radius:8px}
.search-box input[type=text]{width:100%;padding:10px 12px;border:1px solid #ccc;border-radius:4px;font-size:1em}
.search-box input[type=text]:focus{outline:none;border-color:#0066a0;box-shadow:0 0 0 2px rgba(0,102,160,0.1)}

/* Responsive */
@media(max-width:600px){
  .card-grid{grid-template-columns:1fr}
  header .header-inner{flex-direction:column;align-items:flex-start}
  .info-table th{width:100px;font-size:0.8em;padding:8px 10px}
  .info-table td{font-size:0.85em;padding:8px 10px}
  .hero h1{font-size:1.3em}
  .detail-header h1{font-size:1.2em}
}
"""

# =============================================================
# 検索・フィルタJS
# =============================================================

SEARCH_JS = """\
(function(){
  // フィルタ機能（ページ内のカードを非表示/表示）
  var cards = document.querySelectorAll('.clinic-card');
  var qInput = document.getElementById('q-input');
  var visitOnly = document.getElementById('filter-visit');
  var hygOnly = document.getElementById('filter-hyg');
  var countLabel = document.getElementById('count-label');
  var total = cards.length;

  function applyFilter(){
    var q = qInput ? qInput.value.trim().toLowerCase() : '';
    var v = visitOnly && visitOnly.checked;
    var hy = hygOnly && hygOnly.checked;
    var shown = 0;
    cards.forEach(function(c){
      var name = (c.dataset.name||'').toLowerCase();
      var addr = (c.dataset.addr||'').toLowerCase();
      var hasV = c.dataset.visit === '1';
      var hasH = c.dataset.hyg === '1';
      var ok = true;
      if(q && name.indexOf(q)<0 && addr.indexOf(q)<0) ok = false;
      if(v && !hasV) ok = false;
      if(hy && !hasH) ok = false;
      c.style.display = ok ? '' : 'none';
      if(ok) shown++;
    });
    if(countLabel){
      countLabel.textContent = shown + ' / ' + total + ' 件表示中';
    }
  }

  if(qInput) qInput.addEventListener('input', applyFilter);
  if(visitOnly) visitOnly.addEventListener('change', applyFilter);
  if(hygOnly) hygOnly.addEventListener('change', applyFilter);
  applyFilter();

  // 検索JSON（他ページへのジャンプ用、都道府県ページのみ）
  var input=document.getElementById('search-input');
  var results=document.getElementById('search-results');
  var data=[];
  var prefCode=document.body.dataset.prefCode||'';
  if(prefCode && input){
    fetch('/data/search/'+prefCode+'.json')
      .then(function(r){return r.json()})
      .then(function(d){data=d})
      .catch(function(){});
    var timer;
    input.addEventListener('input',function(){
      clearTimeout(timer);
      timer=setTimeout(function(){doSearch()},200);
    });
    function doSearch(){
      var q=input.value.trim().toLowerCase();
      if(q.length<2){results.innerHTML='';return;}
      var hits=data.filter(function(o){
        return(o.st||'').toLowerCase().indexOf(q)>=0;
      }).slice(0,30);
      if(!hits.length){results.innerHTML='<p style="color:#999;margin-top:8px">該当する歯科が見つかりません</p>';return;}
      var html=hits.map(function(o){
        var badges='';
        if(o.v) badges += '<span class="badge badge-visit">訪問歯科対応</span>';
        if(o.h) badges += '<span class="badge badge-hyg">歯科衛生士訪問</span>';
        return '<div class="card" style="margin-bottom:8px"><h3><a href="/clinic/'+esc(o.slug)+'.html">'+esc(o.n)+'</a></h3>'
          +'<div class="meta"><span class="addr">'+esc(o.a)+'</span>'
          +(o.tel?'<span class="tel">TEL: '+esc(o.tel)+'</span>':'')
          +'</div>'
          +(badges?'<div class="badges">'+badges+'</div>':'')
          +'</div>';
      }).join('');
      results.innerHTML=html;
    }
  }
  function esc(s){if(!s)return'';var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
})();
"""

# =============================================================
# HTML生成ヘルパー
# =============================================================

def make_head(title, desc, canonical, extra_head=''):
    """<head> タグを生成"""
    ga_tag = ''
    if GA4_ID:
        ga_tag = f'''<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA4_ID}');</script>'''
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{h(title)}</title>
  <meta name="description" content="{h(desc)}">
  <link rel="canonical" href="{h(canonical)}">
  <meta property="og:title" content="{h(title)}">
  <meta property="og:description" content="{h(desc)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{h(canonical)}">
  <meta property="og:site_name" content="{h(SITE_NAME)}">
  <meta property="og:locale" content="ja_JP">
  <link rel="stylesheet" href="/static/style.css">
  {ga_tag}
{extra_head}
</head>
"""


def make_header():
    return f"""<header>
  <div class="header-inner">
    <div>
      <a href="/" class="site-title">{h(SITE_NAME)}</a>
      <div class="site-subtitle">訪問歯科対応の歯科を探せるポータル</div>
    </div>
    <nav>
      <a href="/about.html">このサイトについて</a>
    </nav>
  </div>
</header>
"""


def make_breadcrumb(items):
    """パンくず生成。items = [(label, url), ...] 最後はリンクなし"""
    parts = []
    for i, (label, url) in enumerate(items):
        if i == len(items) - 1:
            parts.append(f'<span>{h(label)}</span>')
        else:
            parts.append(f'<a href="{h(url)}">{h(label)}</a>')
    # JSON-LD BreadcrumbList
    ld_items = []
    for i, (label, url) in enumerate(items):
        full_url = url if url.startswith('http') else f'{SITE_URL}{url}'
        ld_items.append(f'{{"@type":"ListItem","position":{i+1},"name":"{h(label)}","item":"{h(full_url)}"}}')
    json_ld = f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{",".join(ld_items)}]}}</script>'
    return f'<nav class="breadcrumb">{" &gt; ".join(parts)}</nav>\n{json_ld}'


def make_footer():
    parent_line = ''
    if PARENT_BRAND:
        parent_line = f'<p class="note">{h(SITE_NAME)}は{h(PARENT_BRAND)}群の訪問歯科版です。</p>'
    return f"""<footer>
  <div class="footer-inner">
    <p><strong>{h(SITE_NAME)}</strong> — 訪問歯科対応の歯科診療所を都道府県・市区町村から検索できるポータルサイト</p>
    {parent_line}
    <p class="note">
      情報は <a href="{h(ATTRIBUTION_URL)}" target="_blank" rel="noopener">{h(ATTRIBUTION)}</a> をもとに作成しています。<br>
      実際のサービス提供内容・料金・対応可否については各歯科診療所に直接ご確認ください。
    </p>
    <div class="footer-bottom">&copy; 2025 {h(SITE_NAME)} ({h(OPERATOR_NAME)})</div>
  </div>
</footer>
</body></html>
"""


def make_clinic_card(c):
    """歯科カード（一覧用）"""
    cid = clinic_slug(c['clinic_id'])
    name = c.get('name', '')
    addr = c.get('address', '')
    tel = c.get('tel', '')
    specs = c.get('specialties', [])
    has_v = c.get('has_visiting_dental', False)
    has_h = c.get('has_hygienist_visit', False)

    badges = ''
    if has_v:
        badges += '<span class="badge badge-visit">訪問歯科対応</span>'
    if has_h:
        badges += '<span class="badge badge-hyg">歯科衛生士訪問</span>'

    specs_html = ''
    if specs:
        specs_html = '<div class="specs">' + ' / '.join(h(s) for s in specs[:5]) + '</div>'

    tel_html = f'<span class="tel">TEL: {h(tel)}</span>' if tel else ''

    return f'''<div class="card clinic-card" data-name="{h(name)}" data-addr="{h(addr)}" data-visit="{1 if has_v else 0}" data-hyg="{1 if has_h else 0}">
  <h3><a href="/clinic/{cid}.html">{h(name)}</a></h3>
  <div class="meta">
    <span class="addr">{h(addr)}</span>
    {tel_html}
  </div>
  {specs_html}
  {f'<div class="badges">{badges}</div>' if badges else ''}
</div>
'''


# =============================================================
# ページ生成関数
# =============================================================

def build_index(clinics, pref_name, visiting_count):
    """神奈川県トップページ（MVPなので都道府県トップ = サイトトップ）"""
    total = len(clinics)
    title = f'{SITE_NAME}｜{pref_name}の訪問歯科対応の歯科{total:,}件'
    desc = f'{pref_name}の歯科診療所{total:,}件を掲載。うち訪問歯科対応{visiting_count:,}件。市区町村から検索できます。寝たきり・通院困難な方向け。'
    canonical = f'{SITE_URL}/'

    # 市区町村別
    cities = defaultdict(list)
    for c in clinics:
        cities[c['city']].append(c)
    city_items = sorted(cities.items(), key=lambda x: -len(x[1]))

    city_html = '<div class="city-grid">'
    for cname, clist in city_items:
        cslug = city_slug(cname)
        city_html += f'<a href="/pref/kanagawa/{cslug}.html" class="city-link">{h(cname)}<span class="count">({len(clist)})</span></a>'
    city_html += '</div>'

    body = f"""<body data-pref-code="14">
{make_header()}
<div class="container">
  <div class="hero">
    <h1>{h(pref_name)}の訪問歯科対応の歯科を探す</h1>
    <p>寝たきりや通院困難な方のための <strong>{CARE_TYPE}</strong> に対応している歯科診療所を市区町村から検索できます。</p>
    <p>ケアマネジャー・介護施設スタッフ・ご家族の方の歯科探しをサポートします。</p>
  </div>

  <div class="stats-bar">
    <div class="stat-box"><div class="num">{total:,}</div><div class="label">掲載歯科数</div></div>
    <div class="stat-box"><div class="num">{visiting_count:,}</div><div class="label">訪問歯科対応</div></div>
    <div class="stat-box"><div class="num">{len(cities)}</div><div class="label">市区町村</div></div>
  </div>

  <div class="search-box">
    <input type="text" id="search-input" placeholder="{h(pref_name)}の歯科を検索（名称・住所）">
    <div id="search-results"></div>
  </div>

  <h2 style="margin-top:28px;font-size:1.15em">市区町村から探す</h2>
  {city_html}

  <p style="margin-top:20px;font-size:0.9em;color:#666">
    ※ 訪問歯科対応の判定は医療情報ネット（厚生労働省）に登録されている情報に基づきます。
    実際の対応可否・料金については各歯科診療所に直接お問い合わせください。
  </p>
</div>
{make_footer()}"""

    extra = '<script src="/static/search.js" defer></script>'
    return make_head(title, desc, canonical, extra) + body


def build_pref_page(clinics, pref_name, visiting_count):
    """都道府県ページ（神奈川県）— indexと同じ内容だが別URLで配信"""
    return build_index(clinics, pref_name, visiting_count)


def build_city_page(city_name, clinics_in_city, pref_name):
    """市区町村ページ"""
    cslug = city_slug(city_name)
    n = len(clinics_in_city)
    visiting_n = sum(1 for c in clinics_in_city if c.get('has_visiting_dental'))
    title = f'{city_name}（{pref_name}）の訪問歯科対応の歯科一覧（{n}件）| {SITE_NAME}'
    desc = f'{pref_name}{city_name}の歯科診療所{n}件を掲載。うち訪問歯科対応{visiting_n}件。住所・電話番号・対応サービスを掲載。'
    canonical = f'{SITE_URL}/pref/kanagawa/{cslug}.html'

    bc = make_breadcrumb([
        ('トップ', '/'),
        (pref_name, '/pref/kanagawa.html'),
        (city_name, ''),
    ])

    # 訪問歯科対応を優先表示（ソート）
    sorted_clinics = sorted(
        clinics_in_city,
        key=lambda c: (
            not c.get('has_visiting_dental'),  # Trueを先に
            not c.get('has_hygienist_visit'),
            c.get('name', ''),
        ),
    )
    cards = ''.join(make_clinic_card(c) for c in sorted_clinics)

    body = f"""<body>
{make_header()}
{bc}
<div class="container">
  <div class="hero">
    <h1>{h(city_name)}（{h(pref_name)}）の歯科診療所</h1>
    <p>{h(city_name)}には歯科診療所が<strong>{n}件</strong>あり、うち<strong>{visiting_n}件</strong>が訪問歯科に対応しています。</p>
  </div>

  <div class="filter-bar">
    <input type="text" id="q-input" placeholder="名前・住所で絞り込み" style="flex:1;min-width:200px;padding:6px 10px;border:1px solid #ccc;border-radius:4px">
    <label><input type="checkbox" id="filter-visit">訪問歯科対応のみ</label>
    <label><input type="checkbox" id="filter-hyg">歯科衛生士訪問あり</label>
    <span class="count" id="count-label">{n} 件表示中</span>
  </div>

  <div class="card-grid">
    {cards}
  </div>

  <p style="margin-top:24px"><a href="/pref/kanagawa.html">&larr; {h(pref_name)}の歯科一覧に戻る</a></p>
</div>
{make_footer()}"""

    extra = '<script src="/static/search.js" defer></script>'
    # JSON-LD: ItemList
    items_ld = []
    for i, c in enumerate(sorted_clinics[:20], 1):
        items_ld.append(f'{{"@type":"ListItem","position":{i},"url":"{SITE_URL}/clinic/{clinic_slug(c["clinic_id"])}.html","name":"{h(c.get("name",""))}"}}')
    collection_ld = f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"ItemList","numberOfItems":{n},"itemListElement":[{",".join(items_ld)}]}}</script>'
    extra += '\n  ' + collection_ld
    return make_head(title, desc, canonical, extra) + body


def build_clinic_page(c, pref_name):
    """歯科詳細ページ"""
    cid = clinic_slug(c['clinic_id'])
    name = c.get('name', '')
    city = c.get('city', '')
    cslug = city_slug(city)
    addr = c.get('address', '')
    postal = c.get('postal', '')
    tel = c.get('tel', '')
    url = c.get('url', '')
    specs = c.get('specialties', [])
    has_v = c.get('has_visiting_dental', False)
    has_h = c.get('has_hygienist_visit', False)
    source_url = c.get('source_url', '')
    lat = c.get('latitude')
    lng = c.get('longitude')

    title_parts = [name, f'{city}（{pref_name}）']
    if has_v:
        title_parts.append(CARE_TYPE + '対応')
    title = '｜'.join(title_parts) + f' | {SITE_NAME}'

    desc_parts = [f'{name}は{pref_name}{city}の歯科診療所です']
    if addr:
        desc_parts.append(addr)
    if tel:
        desc_parts.append(f'電話{tel}')
    if has_v:
        desc_parts.append('訪問歯科対応')
    desc = '。'.join(desc_parts) + '。'

    canonical = f'{SITE_URL}/clinic/{cid}.html'

    bc = make_breadcrumb([
        ('トップ', '/'),
        (pref_name, '/pref/kanagawa.html'),
        (city, f'/pref/kanagawa/{cslug}.html'),
        (name, ''),
    ])

    # バッジ
    badges_html = ''
    if has_v:
        badges_html += '<span class="badge badge-visit">訪問歯科対応</span> '
    if has_h:
        badges_html += '<span class="badge badge-hyg">歯科衛生士訪問</span> '
    if badges_html:
        badges_html = f'<div class="badges">{badges_html}</div>'

    # 情報テーブル
    rows = []

    def add_row(label, val):
        if val:
            rows.append(f'<tr><th>{h(label)}</th><td>{val}</td></tr>')

    add_row('歯科名', h(name))
    if postal:
        add_row('郵便番号', f'〒{h(postal)}')
    add_row('住所', h(addr))
    if tel:
        add_row('電話番号', f'<a href="tel:{h(tel)}">{h(tel)}</a>')
    if url:
        add_row('公式サイト', f'<a href="{h(url)}" target="_blank" rel="noopener">{h(url)}</a>')
    if specs:
        specs_html = ' '.join(f'<span class="badge badge-specialty">{h(s)}</span>' for s in specs)
        add_row('診療科目', specs_html)

    visit_status = []
    if has_v:
        visit_status.append('歯科訪問診療に対応')
    if has_h:
        visit_status.append('訪問歯科衛生指導に対応')
    if visit_status:
        add_row('訪問対応', '<br>'.join(visit_status))

    if source_url:
        add_row('情報出典', f'<a href="{h(source_url)}" target="_blank" rel="noopener">医療情報ネットで見る</a>')

    table_html = f'<table class="info-table">{"".join(rows)}</table>'

    # 地図
    map_html = ''
    if lat and lng:
        map_html = f'''<div class="map-container">
  <iframe width="100%" height="320" frameborder="0" style="border:0"
    src="https://www.openstreetmap.org/export/embed.html?bbox={lng - 0.005},{lat - 0.003},{lng + 0.005},{lat + 0.003}&layer=mapnik&marker={lat},{lng}"
    loading="lazy" title="{h(name)}の地図"></iframe>
  <p style="font-size:0.8em;color:#888;margin-top:4px;padding:0 8px 8px">
    <a href="https://www.google.com/maps?q={lat},{lng}" target="_blank" rel="noopener">Google Mapsで見る</a>
  </p>
</div>'''

    # JSON-LD (Dentist)
    json_ld_data = {
        "@context": "https://schema.org",
        "@type": "Dentist",
        "name": name,
        "address": {
            "@type": "PostalAddress",
            "addressRegion": pref_name,
            "addressLocality": city,
            "streetAddress": addr,
            "postalCode": postal,
            "addressCountry": "JP",
        },
    }
    if tel:
        json_ld_data["telephone"] = tel
    if url:
        json_ld_data["url"] = url
    if lat and lng:
        json_ld_data["geo"] = {"@type": "GeoCoordinates", "latitude": lat, "longitude": lng}
    if specs:
        json_ld_data["medicalSpecialty"] = specs
    if has_v:
        json_ld_data["availableService"] = [{"@type": "MedicalProcedure", "name": "歯科訪問診療"}]

    json_ld_tag = f'<script type="application/ld+json">{json.dumps(json_ld_data, ensure_ascii=False)}</script>'

    body = f"""<body>
{make_header()}
{bc}
<div class="container">
  <div class="detail-header">
    <h1>{h(name)}</h1>
    <p style="color:#666;font-size:0.95em">{h(pref_name)} {h(city)}</p>
    {badges_html}
  </div>

  {table_html}
  {map_html}

  <div style="margin-top:24px;display:flex;gap:16px;flex-wrap:wrap">
    <a href="/pref/kanagawa/{cslug}.html">&larr; {h(city)}の歯科一覧</a>
    <a href="/pref/kanagawa.html">&larr; {h(pref_name)}の歯科一覧</a>
  </div>

  <p style="margin-top:20px;font-size:0.85em;color:#888;padding:12px;background:#f8f9fa;border-radius:6px">
    ※ 掲載情報は医療情報ネット（厚生労働省）をもとに作成しています。
    実際の診療内容・対応可否・料金については必ず {h(name)} に直接お問い合わせください。
    情報が古い場合がありますのでご了承ください。
  </p>
</div>
{make_footer()}"""

    return make_head(title, desc, canonical, json_ld_tag) + body


def build_about_page(total, visiting):
    """運営者情報・サイトについて"""
    title = f'このサイトについて | {SITE_NAME}'
    desc = f'{SITE_NAME}の運営者情報とデータ出典について。'
    canonical = f'{SITE_URL}/about.html'
    bc = make_breadcrumb([('トップ', '/'), ('このサイトについて', '')])

    body = f"""<body>
{make_header()}
{bc}
<div class="container">
  <h1>このサイトについて</h1>

  <h2 style="margin-top:24px;font-size:1.15em;color:#0066a0">{h(SITE_NAME)}とは</h2>
  <p style="margin-top:8px">
    {h(SITE_NAME)}は、訪問歯科に対応している歯科診療所を都道府県・市区町村から探せるポータルサイトです。
    寝たきり、通院困難な高齢者、介護施設入居者向けの歯科訪問診療を行っている歯科を掲載しています。
  </p>

  <h2 style="margin-top:24px;font-size:1.15em;color:#0066a0">掲載情報</h2>
  <table class="info-table">
    <tr><th>サイト名</th><td>{h(SITE_NAME)}</td></tr>
    <tr><th>運営者</th><td>{h(OPERATOR_NAME)}</td></tr>
    <tr><th>掲載地域</th><td>神奈川県（パイロット版）</td></tr>
    <tr><th>掲載件数</th><td>{total:,}件</td></tr>
    <tr><th>訪問歯科対応</th><td>{visiting:,}件</td></tr>
    <tr><th>データ出典</th><td><a href="{h(ATTRIBUTION_URL)}" target="_blank" rel="noopener">{h(ATTRIBUTION)}</a></td></tr>
  </table>

  <h2 style="margin-top:24px;font-size:1.15em;color:#0066a0">ご利用にあたって</h2>
  <p style="margin-top:8px">
    掲載されている情報は医療情報ネット（厚生労働省）に登録されている内容をもとに作成しています。
    情報は随時更新されますが、実際のサービス内容・対応可否・料金については各歯科診療所に直接ご確認ください。
    情報の正確性については万全を期していますが、ご利用の際は各歯科に最新情報をお問い合わせください。
  </p>

  <h2 style="margin-top:24px;font-size:1.15em;color:#0066a0">訪問歯科対応の判定</h2>
  <p style="margin-top:8px">
    「訪問歯科対応」バッジは、医療情報ネットの詳細ページで <strong>歯科訪問診療</strong> の情報が掲載されている歯科に付与しています。
    「歯科衛生士訪問」バッジは、同じく <strong>訪問歯科衛生指導</strong> の情報が掲載されている歯科に付与しています。
  </p>

  <p style="margin-top:24px"><a href="/">&larr; トップに戻る</a></p>
</div>
{make_footer()}"""
    return make_head(title, desc, canonical) + body


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
            })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(geo, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8')
    return len(geo)


def generate_sitemap(clinics, cities, dist_dir):
    """sitemap.xml"""
    today = date.today().isoformat()
    urls = []
    urls.append((f'{SITE_URL}/', '1.0', 'weekly'))
    urls.append((f'{SITE_URL}/pref/kanagawa.html', '0.9', 'weekly'))
    urls.append((f'{SITE_URL}/about.html', '0.3', 'yearly'))

    for cname in cities:
        if len(cities[cname]) >= 2:
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
    with_coords = sum(1 for c in clinics if c.get('latitude'))
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
    idx = build_index(clinics, pref_name, visiting)
    (DIST_DIR / 'index.html').write_text(idx, encoding='utf-8')
    (DIST_DIR / 'pref' / 'kanagawa.html').write_text(idx, encoding='utf-8')
    print('index.html / pref/kanagawa.html 生成完了')

    # 市区町村ページ
    for cname, clinics_in_city in cities.items():
        html = build_city_page(cname, clinics_in_city, pref_name)
        cslug = city_slug(cname)
        (DIST_DIR / 'pref' / 'kanagawa' / f'{cslug}.html').write_text(html, encoding='utf-8')
    print(f'市区町村ページ {len(cities)}枚生成完了')

    # 歯科詳細ページ
    for c in clinics:
        cid = clinic_slug(c['clinic_id'])
        html = build_clinic_page(c, pref_name)
        (DIST_DIR / 'clinic' / f'{cid}.html').write_text(html, encoding='utf-8')
    print(f'歯科詳細ページ {len(clinics):,}枚生成完了')

    # About ページ
    about = build_about_page(total, visiting)
    (DIST_DIR / 'about.html').write_text(about, encoding='utf-8')
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
    sitemap_count = generate_sitemap(clinics, cities, DIST_DIR)
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
    page_404 = make_head(f'ページが見つかりません | {SITE_NAME}',
                         'お探しのページは存在しません。',
                         f'{SITE_URL}/404.html')
    page_404 += f"""<body>
{make_header()}
<div class="container" style="text-align:center;padding:60px 20px">
  <h1 style="font-size:2.5em;color:#0066a0">404</h1>
  <p style="margin:16px 0">お探しのページが見つかりませんでした。</p>
  <a href="/">トップページへ</a>
</div>
{make_footer()}"""
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
