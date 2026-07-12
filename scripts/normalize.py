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
# 2026-07-12 修正: 別PCユーザー名（volzs）へのハードコード絶対パスだった。
# sibling repo（~/projects/MyPython）への相対参照に変更し、クロスPCで動作するようにした。
INPUT = BASE_DIR.parent / 'MyPython' / 'data' / 'clinics_dental_kanagawa.json'
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
    """住所から市区町村を抽出（政令市は市+区まで取る）

    2026-07-12 修正（zaitaku-hub W2レーン、N5レーンの kango 修正を踏まえた横展開）:
    元の実装は住所本体全体に対して正規表現を掛けており、丁目・番地・建物名・
    区画整理事業地区名等に含まれる「市」「区」「町」「村」の文字に誤反応し、
    番地の数字ごと市区町村名として誤抽出する regression が理論上存在した
    （例:「美唄市東4条南5丁目1番4号（美唄市東地区…」→ 誤って
    "美唄市東4条南5丁目1番4号（美唄市東地区" を抽出。全国36,491件の実住所
    データでの機械ストレステストで31件の実例を確認、本ガード適用で0件に解消・
    新規regressionゼロを確認済み。詳細: zaitaku-hub-lane-reports/W2_report.md）。

    ガード1: 全角/半角スペースを除去してから処理する（「横浜市　旭区」のような
    区切りスペース混入による誤った市区町村名生成を防ぐ。kango の Tier2 対応と同種）。
    ガード2: 住所本体のうち、最初に数字（半角/全角）が現れる位置より前の部分
    （＝丁目・番地等が始まる前）のみを市区町村抽出の対象にする。日本の住所表記では
    市区町村名は丁目・番地の数字より前に必ず現れるため、この制約により番地・
    建物名側に混入した「市」「区」「町」「村」の誤マッチを構造的に排除できる。

    既知の残存リスク（未対応・低確信のため見送り。kango Tier3 と同種）:
    「○○市土地区画整理事業施行地区」のように、数字が現れる前の時点で
    「区画整理」等の「区」に誤反応するケースは本ガードでは解消しない
    （区画整理・街区等の否定先読みは副作用範囲の検証が別途必要なため未実装）。
    """
    if not address:
        return ''
    addr = _PREF_RE.sub('', address).strip()
    addr = re.sub(r'[　\s]+', '', addr)  # 全角/半角スペース除去
    m_digit = re.search(r'[0-9０-９]', addr)
    head = addr[:m_digit.start()] if m_digit else addr
    # 政令市: ○○市○○区
    m = re.match(r'(.+?市)(.+?区)', head)
    if m:
        return m.group(1) + m.group(2)
    # 郡: ○○郡○○町/村
    m = re.match(r'(.+?郡)(.+?[町村])', head)
    if m:
        return m.group(1) + m.group(2)
    # 一般: ○○市/区/町/村
    m = re.match(r'(.+?[市区町村])', head)
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
