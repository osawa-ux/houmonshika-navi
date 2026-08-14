import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "ui_contract_for_test", ROOT / "scripts" / "validate_ui_contract.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V = load_validator()


def page(body: str, home: str = "index.html", page_root: str = "") -> str:
    return (
        f'<!doctype html><html lang="ja"><head><title>fixture</title></head><body data-page-root="{page_root}">'
        '<a class="skip-link" href="#main">本文へ</a>'
        f'<main id="main">{body}</main><footer><a href="{home}">home</a></footer>'
        "</body></html>"
    )


def make_fixture(root: Path) -> tuple[Path, Path]:
    repo, dist = root / "repo", root / "repo" / "dist"
    (repo / "data" / "normalized").mkdir(parents=True)
    (repo / "config").mkdir()
    (dist / "clinic").mkdir(parents=True)
    (dist / "data" / "search").mkdir(parents=True)
    (dist / "pref" / "kanagawa").mkdir(parents=True)
    (dist / "static").mkdir(parents=True)
    records = []
    search = []
    for index in range(V.EXPECTED_INPUT):
        cid = f"{index:010d}"
        yes = index < V.EXPECTED_VISITING
        unknown = V.EXPECTED_VISITING <= index < V.EXPECTED_VISITING + V.EXPECTED_UNKNOWN
        status = "confirmed_yes" if yes else "unknown" if unknown else "confirmed_no"
        records.append(
            {
                "clinic_id": cid,
                "name": f"Clinic {index}",
                "pref": "Kanagawa",
                "city": f"City {index % V.EXPECTED_CITY}",
                "address": f"Address {index}",
                "has_visiting_dental": yes,
                "detail_status": "unknown" if unknown else "ok",
            }
        )
        search.append({"slug": cid, "s": status, "n": f"Clinic {index}"})
        (dist / "clinic" / f"{cid}.html").write_text(
            page('<a href="../privacy.html">privacy</a>', "../index.html", "../"), encoding="utf-8"
        )
    (repo / "data" / "normalized" / "clinics_dental.json").write_text(
        json.dumps(records), encoding="utf-8"
    )
    (repo / "config" / "site_config.json").write_text(
        json.dumps({"nearby_min_coverage_ratio": 0.8}), encoding="utf-8"
    )
    (dist / "data" / "search" / "14.json").write_text(json.dumps(search), encoding="utf-8")
    (dist / "data" / "clinics_geo.json").write_text("[]", encoding="utf-8")

    buckets = [[] for _ in range(V.EXPECTED_CITY)]
    for index in range(V.EXPECTED_INPUT):
        buckets[index % V.EXPECTED_CITY].append(f"{index:010d}")
    for index, ids in enumerate(buckets):
        cards = "".join(f'<a href="../../clinic/{cid}.html">clinic</a>' for cid in ids)
        controls = (
            '<label for="filter-all">全掲載</label><input id="filter-all" type="checkbox">'
            '<div data-default-status="confirmed_yes"></div>'
        )
        (dist / "pref" / "kanagawa" / f"city{index}.html").write_text(
            page(controls + cards, "../../index.html", "../../"), encoding="utf-8"
        )
    (dist / "pref" / "kanagawa.html").write_text(page("pref", "../index.html", "../"), encoding="utf-8")

    css = (
        "<style>a:focus-visible{outline:2px solid #b45309}"
        ".button{min-height:44px;color:#666}</style>"
    )
    top = css + (
        '<label for="search-input">名称・住所</label><input id="search-input">'
        '<label for="search-all">全掲載</label><input id="search-all" type="checkbox">'
        '<div id="search-results" aria-live="polite"></div>'
        '<div data-default-status="confirmed_yes"></div>'
        '<a href="privacy.html">プライバシー</a><a href="terms.html">利用規約</a>'
        '<a href="contact.html">お問い合わせ</a>'
        '<script src="static/search.js"></script>'
    )
    (dist / "index.html").write_text(page(top), encoding="utf-8")
    for name in ("about.html", "privacy.html", "terms.html", "contact.html"):
        (dist / name).write_text(page(name), encoding="utf-8")
    not_found = page("404")
    not_found = not_found.replace(
        "<head>",
        '<head><meta name="robots" content="noindex,follow"><base href="https://example.invalid/">',
        1,
    )
    (dist / "404.html").write_text(not_found, encoding="utf-8")
    (dist / "nearby.html").write_text(
        page("現在地検索は座標データ整備中のため利用できません。"), encoding="utf-8"
    )
    (dist / "static" / "search.js").write_text(
        "fetch(root+'data/search/14.json');var href=root+'clinic/'+id+'.html';",
        encoding="utf-8",
    )
    (dist / "static" / "style.css").write_text(
        "a:focus-visible{outline:2px solid #b45309}.button{min-height:44px;color:#666}",
        encoding="utf-8",
    )
    locations = ["index", "about", "privacy", "terms", "contact", "pref"]
    locations += [f"city-{i}" for i in range(V.EXPECTED_CITY)]
    locations += [f"clinic-{i}" for i in range(V.EXPECTED_INPUT)]
    assert len(locations) == V.EXPECTED_SITEMAP_WITH_NEARBY_DISABLED
    (dist / "sitemap.xml").write_text(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>https://example.invalid/{x}</loc></url>" for x in locations)
        + "</urlset>",
        encoding="utf-8",
    )
    return repo, dist


class UiContractPositiveControlTests(unittest.TestCase):
    def test_full_gate_mutation_red_restore_then_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, dist = make_fixture(Path(tmp))
            first = V.audit(repo, dist)
            self.assertEqual([], first.findings, [f"{f.code}: {f.message}" for f in first.findings[:20]])

            target = dist / "pref" / "kanagawa" / "city0.html"
            original = target.read_bytes()
            original_hash = hashlib.sha256(original).hexdigest()
            mutated = original.replace(b'../../clinic/', b'/clinic/', 1)
            self.assertNotEqual(original, mutated, "mutation did not apply")
            target.write_bytes(mutated)
            red = V.audit(repo, dist)
            codes = {f.code for f in red.findings}
            self.assertTrue({"ROOT_URL_LEAK", "ABSOLUTE_INTERNAL_URL", "BROKEN_INTERNAL_URL"} & codes)

            target.write_bytes(original)
            self.assertEqual(original_hash, hashlib.sha256(target.read_bytes()).hexdigest())
            green = V.audit(repo, dist)
            self.assertEqual([], green.findings, [f"{f.code}: {f.message}" for f in green.findings[:20]])


if __name__ == "__main__":
    unittest.main()
