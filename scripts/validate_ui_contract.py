#!/usr/bin/env python3
"""Validate the generated public UI contract without modifying any file.

This is a deploy gate rather than a best-effort linter.  It checks every
generated HTML attribute and every city card, and it simulates hosting the
same artifact at both ``/`` and ``/shika/``.  Exit code 0 means all assertions
passed; any error is fail-closed.

The implementation intentionally uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urljoin, urlparse


EXPECTED_INPUT = 2507
EXPECTED_VISITING = 986
EXPECTED_UNKNOWN = 115
EXPECTED_HTML_WITH_NEARBY_DISABLED = 2550
EXPECTED_CITY = 35
EXPECTED_SITEMAP_WITH_NEARBY_DISABLED = 2548
MOUNTS = ("/", "/shika/")
URL_ATTRS = ("href", "src", "formaction")
FORBIDDEN_ROOT = re.compile(
    r"(?P<q>['\"`])/(?:shika/)?(?:clinic|data|pref|static)(?:/|(?P=q))"
    r"|(?P<q2>['\"`])/(?:shika/)?nearby(?:\.html)?(?=[?#'\"`])",
    re.IGNORECASE,
)


@dataclass
class Finding:
    code: str
    message: str


@dataclass
class Audit:
    checks: int = 0
    findings: list[Finding] = field(default_factory=list)

    def require(self, condition: bool, code: str, message: str) -> None:
        self.checks += 1
        if not condition:
            self.findings.append(Finding(code, message))


class DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.attrs: list[tuple[str, dict[str, str], int]] = []
        self.inputs: list[dict[str, str]] = []
        self.labels_for: set[str] = set()
        self.main_count = 0
        self.has_skip_link = False
        self.live_regions = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()
        self.attrs.append((tag, values, self.getpos()[0]))
        if tag == "input":
            self.inputs.append(values)
        if tag == "label" and values.get("for"):
            self.labels_for.add(values["for"])
        if tag == "main" or values.get("role") == "main":
            self.main_count += 1
        if tag == "a" and values.get("href") in ("#main", "#main-content"):
            self.has_skip_link = True
        if values.get("role") in ("status", "alert") or values.get("aria-live") in (
            "polite",
            "assertive",
        ):
            self.live_regions += 1


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def output_path_for_url(dist: Path, url_path: str) -> Path:
    clean = unquote(url_path).lstrip("/")
    if not clean or clean.endswith("/"):
        clean += "index.html"
    return dist.joinpath(*PurePosixPath(clean).parts)


def resolves_under_mount(dist: Path, page_rel: str, raw_url: str, mount: str) -> bool:
    page_url = "https://artifact.invalid" + mount + page_rel
    resolved = urlparse(urljoin(page_url, raw_url))
    mount_root = mount.rstrip("/")
    if mount_root:
        if resolved.path == mount_root:
            artifact_path = "/"
        elif resolved.path.startswith(mount_root + "/"):
            artifact_path = resolved.path[len(mount_root) :]
        else:
            return False
    else:
        artifact_path = resolved.path
    candidate = output_path_for_url(dist, artifact_path)
    return candidate.is_file()


def normalize_status(item: dict) -> str | None:
    value = None
    for key in ("visiting_status", "status", "s", "v"):
        if key in item:
            value = item[key]
            break
    if isinstance(value, str):
        value = value.strip().lower().replace("-", "_")
        aliases = {
            "yes": "confirmed_yes",
            "true": "confirmed_yes",
            "confirmed": "confirmed_yes",
            "confirmed_yes": "confirmed_yes",
            "no": "confirmed_no",
            "false": "confirmed_no",
            "confirmed_no": "confirmed_no",
            "unknown": "unknown",
            "unconfirmed": "unknown",
        }
        return aliases.get(value)
    # Booleans/0/1 are only two-state and therefore cannot satisfy the contract
    # for an unknown source record.
    if value is True or value == 1:
        return "confirmed_yes"
    if value is False or value == 0:
        return "confirmed_no"
    return None


def clinic_id_from_href(href: str) -> str | None:
    path = urlparse(href).path
    match = re.search(r"(?:^|/)clinic/([^/]+)\.html$", path)
    return unquote(match.group(1)) if match else None


def audit(repo: Path, dist: Path) -> Audit:
    out = Audit()
    data_file = repo / "data" / "normalized" / "clinics_dental.json"
    config_file = repo / "config" / "site_config.json"
    out.require(data_file.is_file(), "DATA_MISSING", f"missing {data_file}")
    out.require(config_file.is_file(), "CONFIG_MISSING", f"missing {config_file}")
    out.require(dist.is_dir(), "DIST_MISSING", f"missing {dist}")
    if out.findings:
        return out

    records_raw = read_json(data_file)
    config_raw = read_json(config_file)
    out.require(isinstance(records_raw, list), "DATA_SCHEMA", "normalized data must be a list")
    out.require(isinstance(config_raw, dict), "CONFIG_SCHEMA", "site config must be an object")
    if not isinstance(records_raw, list) or not isinstance(config_raw, dict):
        return out
    records = [r for r in records_raw if isinstance(r, dict)]
    config = config_raw
    ids = {str(r.get("clinic_id", "")): r for r in records}
    visiting_ids = {cid for cid, r in ids.items() if r.get("has_visiting_dental") is True}
    unknown_ids = {cid for cid, r in ids.items() if r.get("detail_status") == "unknown"}
    out.require(len(records) == EXPECTED_INPUT, "INPUT_COUNT", f"input={len(records)}, expected={EXPECTED_INPUT}")
    out.require(len(ids) == len(records), "INPUT_IDS", "clinic_id must be non-empty and unique")
    out.require(len(visiting_ids) == EXPECTED_VISITING, "VISITING_COUNT", f"visiting={len(visiting_ids)}, expected={EXPECTED_VISITING}")
    out.require(len(unknown_ids) == EXPECTED_UNKNOWN, "UNKNOWN_COUNT", f"unknown={len(unknown_ids)}, expected={EXPECTED_UNKNOWN}")

    detail_pages = sorted((dist / "clinic").glob("*.html")) if (dist / "clinic").is_dir() else []
    search_files = sorted((dist / "data" / "search").glob("*.json")) if (dist / "data" / "search").is_dir() else []
    city_pages = sorted((dist / "pref").glob("*/*.html")) if (dist / "pref").is_dir() else []
    html_pages = sorted(dist.rglob("*.html"))
    out.require(len(detail_pages) == EXPECTED_INPUT, "DETAIL_COUNT", f"detail={len(detail_pages)}, expected={EXPECTED_INPUT}")
    out.require(len(city_pages) == EXPECTED_CITY, "CITY_COUNT", f"city={len(city_pages)}, expected={EXPECTED_CITY}")

    search_items: list[dict] = []
    for path in search_files:
        value = read_json(path)
        if isinstance(value, list):
            search_items.extend(x for x in value if isinstance(x, dict))
        else:
            out.require(False, "SEARCH_SCHEMA", f"{path.relative_to(dist)} must contain a list")
    out.require(len(search_items) == EXPECTED_INPUT, "SEARCH_COUNT", f"search={len(search_items)}, expected={EXPECTED_INPUT}")
    search_by_id = {str(x.get("slug", x.get("clinic_id", ""))): x for x in search_items}
    out.require(len(search_by_id) == len(search_items), "SEARCH_IDS", "search ids must be non-empty and unique")
    status_counts = {"confirmed_yes": 0, "confirmed_no": 0, "unknown": 0, None: 0}
    status_mismatches = 0
    for cid, item in search_by_id.items():
        status = normalize_status(item)
        status_counts[status] = status_counts.get(status, 0) + 1
        source = ids.get(cid)
        if source is None:
            status_mismatches += 1
            continue
        expected = (
            "unknown"
            if source.get("detail_status") == "unknown"
            else "confirmed_yes"
            if source.get("has_visiting_dental") is True
            else "confirmed_no"
        )
        if status != expected:
            status_mismatches += 1
    out.require(status_counts.get("confirmed_yes") == EXPECTED_VISITING, "SEARCH_YES", f"search confirmed_yes={status_counts.get('confirmed_yes')}")
    out.require(status_counts.get("unknown") == EXPECTED_UNKNOWN, "SEARCH_UNKNOWN", f"search unknown={status_counts.get('unknown')}")
    out.require(status_counts.get("confirmed_no") == EXPECTED_INPUT - EXPECTED_VISITING - EXPECTED_UNKNOWN, "SEARCH_NO", f"search confirmed_no={status_counts.get('confirmed_no')}")
    out.require(status_mismatches == 0, "SEARCH_STATUS_MAP", f"search/source status mismatches={status_mismatches}")

    geo_file = dist / "data" / "clinics_geo.json"
    geo_count = 0
    if geo_file.is_file():
        geo = read_json(geo_file)
        geo_count = len(geo) if isinstance(geo, list) else 0
    threshold = float(config.get("nearby_min_coverage_ratio", 0.8))
    nearby_enabled = len(records) > 0 and geo_count / len(records) >= threshold
    out.require(
        not nearby_enabled,
        "NEARBY_COVERAGE_REVIEW_REQUIRED",
        "coverage reached the publication threshold; implement and re-review the interactive nearby flow before publishing",
    )
    if not nearby_enabled:
        out.require(len(html_pages) == EXPECTED_HTML_WITH_NEARBY_DISABLED, "HTML_COUNT", f"html={len(html_pages)}, expected={EXPECTED_HTML_WITH_NEARBY_DISABLED} when nearby disabled")
        out.require((dist / "nearby.html").is_file(), "NEARBY_PAGE", "nearby.html must remain as an honest unavailable page below the threshold")

    sitemap = dist / "sitemap.xml"
    sitemap_text = sitemap.read_text(encoding="utf-8") if sitemap.is_file() else ""
    sitemap_count = len(re.findall(r"<loc\b", sitemap_text))
    expected_sitemap = EXPECTED_SITEMAP_WITH_NEARBY_DISABLED if not nearby_enabled else EXPECTED_SITEMAP_WITH_NEARBY_DISABLED + 1
    out.require(sitemap_count == expected_sitemap, "SITEMAP_COUNT", f"locations={sitemap_count}, expected={expected_sitemap}")
    for name in ("privacy.html", "terms.html", "contact.html"):
        out.require((dist / name).is_file(), "TRUST_PAGE", f"missing {name}")
    not_found_text = (dist / "404.html").read_text(encoding="utf-8", errors="replace")
    out.require(not re.search(r'href=["\']\s*["\']', not_found_text, re.I), "EMPTY_404_HOME", "404 page has an empty home link")
    out.require('<meta name="robots" content="noindex,follow">' in not_found_text, "404_NOINDEX", "404 page must be noindex")
    out.require(bool(re.search(r'<base\s+href=["\']https://[^"\']+/["\']', not_found_text, re.I)), "404_BASE", "404 relative navigation lacks a canonical base URL")

    # Full rendered-attribute scan and mount simulation.
    all_city_ids: list[str] = []
    nearby_links = 0
    top_nearby_links = 0
    geolocation_mentions = 0
    scanned_urls = 0
    for page in html_pages:
        rel = page.relative_to(dist).as_posix()
        text = page.read_text(encoding="utf-8", errors="replace")
        parser = DocumentParser()
        parser.feed(text)
        body_attrs = next((attrs for tag, attrs, _ in parser.attrs if tag == "body"), {})
        expected_page_root = "../" * len(PurePosixPath(rel).parent.parts)
        out.require(
            body_attrs.get("data-page-root") == expected_page_root,
            "PAGE_ROOT",
            f"{rel}: data-page-root={body_attrs.get('data-page-root')!r}, expected={expected_page_root!r}",
        )
        out.require(parser.main_count == 1, "MAIN", f"{rel}: expected exactly one main landmark, got {parser.main_count}")
        out.require(parser.has_skip_link, "SKIP_LINK", f"{rel}: missing skip link")
        geolocation_mentions += text.count("navigator.geolocation")
        forbidden = FORBIDDEN_ROOT.search(text)
        out.require(forbidden is None, "ROOT_URL_LEAK", f"{rel}: forbidden root/fixed-base URL {forbidden.group(0) if forbidden else ''}")

        for tag, attrs, line in parser.attrs:
            if tag == "input" and attrs.get("type", "text").lower() not in ("hidden", "submit", "button"):
                input_id = attrs.get("id", "")
                named = bool(attrs.get("aria-label") or attrs.get("aria-labelledby") or input_id in parser.labels_for)
                out.require(named, "INPUT_LABEL", f"{rel}:{line}: input #{input_id or '<none>'} lacks a visible/ARIA label")
            for attr in URL_ATTRS:
                raw = attrs.get(attr)
                if raw is None or raw == "" or raw.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
                    continue
                parsed = urlparse(raw)
                if parsed.scheme or parsed.netloc or raw.startswith("//"):
                    # Canonical, JSON-LD and portal-network URLs are intentionally absolute.
                    continue
                scanned_urls += 1
                if "nearby" in parsed.path.lower():
                    nearby_links += 1
                    if rel == "index.html":
                        top_nearby_links += 1
                out.require(not parsed.path.startswith("/"), "ABSOLUTE_INTERNAL_URL", f"{rel}:{line}: {attr}={raw!r} is not document-relative")
                if parsed.path.startswith("/"):
                    continue
                for mount in MOUNTS:
                    out.require(resolves_under_mount(dist, rel, raw, mount), "BROKEN_INTERNAL_URL", f"{rel}:{line}: {attr}={raw!r} does not resolve when mounted at {mount}")
                if page in city_pages and attr == "href":
                    cid = clinic_id_from_href(raw)
                    if cid:
                        all_city_ids.append(cid)

        # Every page containing asynchronous search results must announce updates.
        if "search-results" in text or "nearby-results" in text:
            out.require(parser.live_regions > 0, "LIVE_REGION", f"{rel}: dynamic results lack role=status/aria-live")

    # JavaScript can create URLs which never appear in rendered attributes. Scan
    # every generated bundle rather than only the script linked by the top page.
    js_files = sorted(dist.rglob("*.js"))
    out.require(bool(js_files), "JS_SCAN_FIRED", "no generated JavaScript was found")
    fetch_calls = 0
    dynamic_clinic_urls = 0
    for script in js_files:
        rel = script.relative_to(dist).as_posix()
        text = script.read_text(encoding="utf-8", errors="replace")
        forbidden = FORBIDDEN_ROOT.search(text)
        out.require(forbidden is None, "JS_ROOT_URL_LEAK", f"{rel}: forbidden fixed/root URL {forbidden.group(0) if forbidden else ''}")
        for match in re.finditer(r"\bfetch\s*\(([^)]{1,240})\)", text):
            fetch_calls += 1
            expression = match.group(1).strip()
            safe = bool(re.search(r"\b(?:root|pageRoot)\b", expression))
            out.require(safe, "JS_FETCH_BASE", f"{rel}: fetch URL is not derived from page root: {expression[:120]}")
        dynamic_clinic_urls += len(re.findall(r"\broot\s*\+\s*['\"]clinic/", text))
    out.require(fetch_calls > 0, "FETCH_SCAN_FIRED", "no generated fetch call was inspected")
    out.require(dynamic_clinic_urls > 0, "DYNAMIC_HREF_SCAN_FIRED", "no page-root-derived dynamic clinic URL was inspected")

    out.require(scanned_urls > EXPECTED_INPUT, "URL_SCAN_FIRED", f"full URL scan unexpectedly saw only {scanned_urls} URLs")
    if not nearby_enabled:
        out.require(top_nearby_links == 0, "NEARBY_CTA", f"top nearby links remain below coverage threshold: {top_nearby_links}")
        out.require(geolocation_mentions == 0, "GEOLOCATION_EXECUTION", f"navigator.geolocation remains below coverage threshold: {geolocation_mentions}")

    city_id_set = set(all_city_ids)
    out.require(len(all_city_ids) == EXPECTED_INPUT, "CITY_CARD_COUNT", f"city detail cards={len(all_city_ids)}, expected all {EXPECTED_INPUT}")
    out.require(len(city_id_set) == EXPECTED_INPUT, "CITY_CARD_UNIQUE", f"unique city detail cards={len(city_id_set)}")
    out.require(city_id_set == set(ids), "CITY_CARD_SET", f"city card set differs: missing={len(set(ids)-city_id_set)}, extra={len(city_id_set-set(ids))}")

    top = dist / "index.html"
    top_text = top.read_text(encoding="utf-8", errors="replace") if top.is_file() else ""
    top_parser = DocumentParser()
    top_parser.feed(top_text)
    default_control = any(
        "checked" in attrs
        and any(word in " ".join(attrs.get(k, "") for k in ("id", "name", "value", "class")).lower() for word in ("visit", "confirmed"))
        for attrs in top_parser.inputs
    ) or bool(re.search(r"data-default-status=['\"]confirmed_yes['\"]", top_text, re.I)) or (
        any("all" in " ".join(attrs.get(k, "") for k in ("id", "name", "value", "class")).lower() and "checked" not in attrs for attrs in top_parser.inputs)
        and "confirmed_yes" in top_text
    )
    out.require(default_control, "TOP_DEFAULT", "top search must default to confirmed-only via a checked control or explicit data-default-status")
    city_default_missing = 0
    for page in city_pages:
        text = page.read_text(encoding="utf-8", errors="replace")
        parser = DocumentParser()
        parser.feed(text)
        has_default = any(
            "checked" in attrs
            and any(word in " ".join(attrs.get(k, "") for k in ("id", "name", "value", "class")).lower() for word in ("visit", "confirmed"))
            for attrs in parser.inputs
        ) or bool(re.search(r"data-default-status=['\"]confirmed_yes['\"]", text, re.I)) or (
            any("all" in " ".join(attrs.get(k, "") for k in ("id", "name", "value", "class")).lower() and "checked" not in attrs for attrs in parser.inputs)
            and "confirmed_yes" in text
        )
        if not has_default:
            city_default_missing += 1
    out.require(city_default_missing == 0, "CITY_DEFAULT", f"city pages without confirmed-only default marker={city_default_missing}")

    # Coarse but deterministic CSS contract checks. axe/browser review remains the
    # richer oracle; these markers prevent regression of the fixed shared styles.
    css_files = sorted(dist.rglob("*.css"))
    out.require(bool(css_files), "CSS_SCAN_FIRED", "no generated CSS was found")
    css = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in css_files).lower()
    out.require(":focus-visible" in css, "FOCUS_VISIBLE", "shared CSS lacks :focus-visible")
    out.require(bool(re.search(r"outline\s*:\s*(?:solid\s+)?2px|outline\s*:\s*2px", css)), "FOCUS_WIDTH", "shared CSS lacks a 2px focus outline")
    out.require(bool(re.search(r"min-(?:height|width)\s*:\s*44px", css)), "TARGET_SIZE", "shared CSS lacks a 44px target-size rule")
    out.require(not re.search(r"color\s*:\s*#(?:777|888)\b", css), "LOW_CONTRAST_COLOR", "shared CSS retains known sub-4.5:1 small-text color #777/#888")
    for label in ("プライバシー", "利用規約", "お問い合わせ"):
        out.require(label in top_text, "TRUST_LINK", f"top lacks visible {label} link")
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=default_repo)
    parser.add_argument("--dist-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo_root.resolve()
    dist = (args.dist_dir or repo / "dist").resolve()
    result = audit(repo, dist)
    for finding in result.findings:
        print(f"[FAIL] {finding.code}: {finding.message}")
    passed = result.checks - len(result.findings)
    print(f"SUMMARY checks={result.checks} PASS={passed} FAIL={len(result.findings)} UNKNOWN=0")
    return 1 if result.findings else 0


if __name__ == "__main__":
    sys.exit(main())
