"""
訪問歯科ナビ Geocoding スクリプト

住所 → 緯度経度を取得し、clinics_dental.json に書き戻す。
キャッシュを必ず使う（一度取得した住所は再取得しない）。

データソース:
- Nominatim (OpenStreetMap, 無料、1 req/sec 制限)

使い方:
  python scripts/geocode.py          # 未取得のみ
  python scripts/geocode.py --all    # 全件再取得（通常は不要）
  python scripts/geocode.py --limit 50  # 最大50件のみ処理
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent.parent
DATA_FILE = BASE_DIR / 'data' / 'normalized' / 'clinics_dental.json'
CACHE_FILE = BASE_DIR / 'data' / 'geocode_cache.json'

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'houmonshika-navi/1.0 (https://shika.zaitaku-navi.com)'
RATE_LIMIT_SEC = 1.1  # Nominatim の利用規約（1req/sec以下）


def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def normalize_address(address: str) -> str:
    """Geocoding用に住所を整形"""
    if not address:
        return ''
    # 建物名・階数を除去（○階、○F、ビル名など）
    addr = re.sub(r'[0-9０-９]+\s*(階|F|Ｆ)', '', address)
    addr = re.sub(r'　.*$', '', addr)  # 全角スペース以降（建物名）
    # 丁目・番・号の正規化
    addr = addr.replace('－', '-').replace('ー', '-')
    return addr.strip()


def geocode_one(address: str, cache: dict) -> tuple:
    """1件の住所をジオコーディング。(lat, lng, from_cache) を返す"""
    key = normalize_address(address)
    if not key:
        return None, None, False

    if key in cache:
        entry = cache[key]
        if entry and entry.get('lat'):
            return entry['lat'], entry['lng'], True
        else:
            return None, None, True  # キャッシュに失敗記録あり

    # API 呼び出し
    params = {
        'q': key + ', Japan',
        'format': 'json',
        'limit': 1,
        'countrycodes': 'jp',
    }
    headers = {'User-Agent': USER_AGENT}
    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data:
            lat = float(data[0]['lat'])
            lng = float(data[0]['lon'])
            cache[key] = {'lat': lat, 'lng': lng}
            return lat, lng, False
        else:
            cache[key] = None  # 失敗も記録して再試行しない
            return None, None, False
    except Exception as e:
        print(f'  ERROR geocoding "{key}": {e}')
        # エラー時はキャッシュに記録しない（次回再試行可）
        return None, None, False


def main():
    all_mode = '--all' in sys.argv
    limit = None
    if '--limit' in sys.argv:
        i = sys.argv.index('--limit')
        if i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    if not DATA_FILE.exists():
        print(f'ERROR: {DATA_FILE} が見つかりません')
        sys.exit(1)

    with open(DATA_FILE, encoding='utf-8') as f:
        clinics = json.load(f)

    cache = load_cache()
    print(f'データ: {len(clinics)}件')
    print(f'キャッシュ: {len(cache)}件')

    # 対象抽出
    if all_mode:
        targets = clinics
    else:
        targets = [c for c in clinics if not c.get('latitude')]

    if limit:
        targets = targets[:limit]

    print(f'処理対象: {len(targets)}件')

    updated = 0
    cache_hits = 0
    api_calls = 0
    fails = 0
    start = time.time()
    last_api_call = 0

    for i, clinic in enumerate(targets):
        address = clinic.get('address', '')
        lat, lng, from_cache = geocode_one(address, cache)

        if lat and lng:
            clinic['latitude'] = lat
            clinic['longitude'] = lng
            updated += 1
            if from_cache:
                cache_hits += 1
        else:
            fails += 1

        if not from_cache:
            api_calls += 1
            # レート制限
            elapsed_since_last = time.time() - last_api_call
            if elapsed_since_last < RATE_LIMIT_SEC:
                time.sleep(RATE_LIMIT_SEC - elapsed_since_last)
            last_api_call = time.time()

        # 進捗表示と中間保存
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start
            print(f'  {i+1}/{len(targets)} updated={updated} cache={cache_hits} api={api_calls} fails={fails} ({elapsed:.0f}s)')
            save_cache(cache)
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(clinics, f, ensure_ascii=False, indent=2)

    # 最終保存
    save_cache(cache)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(clinics, f, ensure_ascii=False, indent=2)

    # 集計
    total_with_coords = sum(1 for c in clinics if c.get('latitude'))
    print(f'\n=== 完了 ===')
    print(f'  更新: {updated}件')
    print(f'  キャッシュヒット: {cache_hits}件')
    print(f'  API呼び出し: {api_calls}件')
    print(f'  失敗: {fails}件')
    print(f'  座標付与済み合計: {total_with_coords}/{len(clinics)} ({total_with_coords/len(clinics)*100:.1f}%)')


if __name__ == '__main__':
    main()
