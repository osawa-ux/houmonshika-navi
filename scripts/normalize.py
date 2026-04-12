"""
訪問歯科ナビ データ正規化スクリプト

入力: MyPython/data/clinics_dental_kanagawa.json (P2出力)
出力: data/normalized/clinics_dental.json (build_site.py 用)

処理内容:
- 市区町村抽出
- ビルド用フィールド追加（slug, city_code 等）
- detail_status='unknown' はそのまま保持
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent.parent
INPUT = Path('C:/Users/volzs/projects/MyPython/data/clinics_dental_kanagawa.json')
OUTPUT = BASE_DIR / 'data' / 'normalized' / 'clinics_dental.json'

# 都道府県名除去パターン
_PREF_RE = re.compile(
    r'^(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|'
    r'埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|'
    r'岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|'
    r'鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|'
    r'佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県)'
)


def extract_city(address: str) -> str:
    """住所から市区町村を抽出（政令市は市+区まで取る）"""
    if not address:
        return ''
    addr = _PREF_RE.sub('', address).strip()
    # 政令市: ○○市○○区
    m = re.match(r'(.+?市)(.+?区)', addr)
    if m:
        return m.group(1) + m.group(2)
    # 郡: ○○郡○○町/村
    m = re.match(r'(.+?郡)(.+?[町村])', addr)
    if m:
        return m.group(1) + m.group(2)
    # 一般: ○○市/区/町/村
    m = re.match(r'(.+?[市区町村])', addr)
    if m:
        return m.group(1)
    return ''


def normalize(raw: dict) -> dict:
    """P2出力を build_site.py 用フォーマットに変換"""
    address = raw.get('address', '')
    city = extract_city(address)

    return {
        'clinic_id': raw.get('kikan_cd', ''),
        'name': raw.get('name', ''),
        'pref_code': raw.get('pref_code', ''),
        'pref': raw.get('pref', ''),
        'city': city,
        'postal': raw.get('postal', ''),
        'address': address,
        'tel': raw.get('tel', ''),
        'url': raw.get('url', ''),
        'specialties': raw.get('specialties', []),
        'has_visiting_dental': raw.get('has_visiting_dental', False),
        'has_hygienist_visit': raw.get('has_hygienist_visit', False),
        'has_zaitaku_section': raw.get('has_zaitaku_section', False),
        'detail_status': raw.get('detail_status', 'ok'),
        'source_url': raw.get('source_url', ''),
        'kikan_kbn': raw.get('kikan_kbn', '3'),
        # Geocoding で後から埋める
        'latitude': raw.get('latitude'),
        'longitude': raw.get('longitude'),
    }


def main():
    print(f'入力: {INPUT}')
    if not INPUT.exists():
        print(f'ERROR: 入力ファイルが見つかりません')
        sys.exit(1)

    with open(INPUT, encoding='utf-8') as f:
        raw_data = json.load(f)
    print(f'読み込み: {len(raw_data)}件')

    normalized = [normalize(r) for r in raw_data]

    # 空の city を除外（住所不正）
    no_city = [c for c in normalized if not c['city']]
    if no_city:
        print(f'WARN: 市区町村抽出失敗 {len(no_city)}件')
    normalized = [c for c in normalized if c['city']]

    # 集計
    total = len(normalized)
    visiting = sum(1 for c in normalized if c['has_visiting_dental'])
    hygienist = sum(1 for c in normalized if c['has_hygienist_visit'])
    unknown = sum(1 for c in normalized if c['detail_status'] == 'unknown')
    print(f'正規化後: {total}件')
    print(f'  訪問歯科対応: {visiting} ({visiting/total*100:.1f}%)')
    print(f'  衛生指導対応: {hygienist} ({hygienist/total*100:.1f}%)')
    print(f'  unknown: {unknown}')

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
    print(f'出力: {OUTPUT}')


if __name__ == '__main__':
    main()
