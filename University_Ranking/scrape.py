#!/usr/bin/env python3
"""
QS World University Rankings scraper (Crawl4AI 0.9+, async).

Strategy (in order):
  1. Load https://www.topuniversities.com/world-university-rankings in a stealth
     Chromium session, clear Cloudflare (with retries).
  2. Find the ranking node id ("nid") embedded in the page and call QS's own
     JSON endpoint  /rankings/endpoint?nid=...&page=N  *from inside the browser*
     (same origin + Cloudflare cookies) until every page is fetched.
     This is what the page itself does for infinite scroll, so it is far more
     reliable than guessing CSS selectors.
  3. If step 2 fails, fall back to DOM scraping: scroll / click "Load More"
     repeatedly, then parse rows with a flexible selector list
     (data-testid first, class-name fallbacks). Edit ROW_SELECTORS /
     FIELD_SELECTORS below after inspecting the live page.

Outputs: qs_rankings.csv, qs_rankings.json (+ qs_rankings_debug.html on failure)

Install:
    pip install "crawl4ai>=0.9" beautifulsoup4 nest_asyncio
    crawl4ai-setup            # installs Playwright's Chromium

Works from a normal terminal AND from Jupyter / Colab (see run() at the bottom).
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import random
import re
import sys
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
URL = "https://www.topuniversities.com/world-university-rankings"
API_PATH = "/rankings/endpoint"          # QS's internal JSON endpoint (same origin)
ITEMS_PER_PAGE = 100                     # rows per API page (QS accepts 15–~500)
MAX_API_PAGES = 200                      # hard stop safety net
MAX_RECORDS: Optional[int] = None        # e.g. 50 for a quick test run

EDITIONS_BACK = 3                        # also scrape the N previous editions (e.g. 2026, 2025, 2024 for a
                                         # 2027 page). Each edition is saved to its own CSV/JSON and its rank
                                         # is joined into the main file as RANK_<year>. 0 = current only.
FETCH_PROFILES = True                    # visit each /universities/<slug> page for SIZE/FOCUS/RES/STATUS.
                                         # These badges exist ONLY on profile pages, not in the endpoint.
                                         # ~1500 page loads at PROFILE_DELAY_S pacing => roughly 45-60 min.
PROFILE_DELAY_S = (1.0, 2.5)             # random pause between profile pages
PROFILE_ABORT_AFTER = 10                 # stop the pass if the first N profiles yield no badges at all
                                         # (means the selectors need updating - see qs_profile_debug.html)

HEADLESS = False                         # headed Chromium passes Cloudflare far more often;
                                         # switch to True once the profile below holds a clearance cookie
BROWSER_TYPE = "undetected"              # Crawl4AI >= 0.7.3 undetected adapter; falls back to "chromium"
USER_DATA_DIR = "./.qs_browser_profile"  # persistent profile -> Cloudflare clearance survives restarts
CHALLENGE_WAIT_S = 20                    # how long to let the challenge JS run before re-checking
MAX_ATTEMPTS = 3                         # Cloudflare retry attempts
BASE_TIMEOUT_MS = 60_000                 # grows on each retry
SESSION_ID = "qs-rankings-session"

# Column names. RANK_CURRENT / RANK_PREVIOUS are renamed to RANK_<year> once
# the edition year is detected from the page (falls back to 2025 / 2024).
DEFAULT_EDITION_YEAR = 2025

INDICATORS = [
    "Academic_Reputation",
    "Employer_Reputation",
    "Faculty_Student",
    "Citations_per_Faculty",
    "International_Faculty",
    "International_Students",
    "International_Research_Network",
    "Employment_Outcomes",
    "Sustainability",
]

# Known ranking node ids, used ONLY if auto-detection fails. May go stale.
KNOWN_NIDS = {2024: "3897789", 2025: "3990755"}

# Realistic desktop Chrome fingerprint
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
EXTRA_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,*/*;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-CH-UA-Platform": '"macOS"',
}

# ---- DOM fallback selectors -------------------------------------------------
# Verified against the live 2027 page (card layout, not a <table>). Each field
# lists selectors tried in order; data-testid variants first in case QS adds
# them, then the current class names. Adjust here if the markup changes.
ROW_SELECTORS = [
    '[data-testid="ranking-row"]',
    'div.ind[class*="ranking-row-js-"]',     # <- current QS markup
    "div.ind.main",
]
FIELD_SELECTORS: Dict[str, List[str]] = {
    "RANK_CURRENT":     ['[data-testid="rank"]', ".rank-no", "._univ-rank"],
    "Institution_Name": ['[data-testid="university-name"]', "a.uni-link", ".univ-names-text a"],
    "Location":         ['[data-testid="location"]', ".location"],
    "Overall_Score":    ['[data-testid="overall-score"]', ".rank-score", ".overall-score-span"],
    # Each indicator sits in a container: <h2 class="new-rankings-ind">Name</h2>
    # ... <div class="new-rankings-ind-val">Score</div>
    "_indicator_box":   ['[data-testid="indicator"]', ".new-rankings-indicator-container"],
    "_indicator_name":  ['[data-testid="indicator-name"]', "h2.new-rankings-ind", ".new-rankings-ind"],
    "_indicator_value": ['[data-testid="indicator-score"]', ".new-rankings-ind-val"],
    # Not rendered in the list view (only via the JSON endpoint): previous-year
    # rank, region, indicator ranks and the SIZE/FOCUS/RES/STATUS badges. Left
    # here so they're picked up if QS ever adds them to the cards.
    "RANK_PREVIOUS":    ['[data-testid="rank-previous"]', ".rank-prev", ".prev-rank"],
    "Region":           ['[data-testid="region"]', ".region"],
    "_badges":          ['[data-testid="badge"]', ".badge", ".classification span"],
}
# Pagination controls (bottom of the list)
PER_PAGE_DROPDOWN = ".perpage_dropdown_js"
PER_PAGE_OPTION = '.perpage_dropdown_js .item[data-value="{n}"]'
DOM_PER_PAGE = 150                        # largest option QS offers
NEXT_PAGE_LINK = "#alt-style-pagination a.page-link.next"
RANGE_LABEL = "#_outoftotalcounts"        # e.g. "1 - 30"
TOTAL_LABEL = "#_totalcountresults"       # e.g. "1504"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("qs")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def columns(edition_year: int, prev_years: Optional[List[int]] = None) -> List[str]:
    """Column order. prev_years -> extra RANK_<year> columns after the current rank."""
    if prev_years is None:
        prev_years = [edition_year - 1]
    cols = [f"RANK_{edition_year}"] + [f"RANK_{y}" for y in prev_years] + \
           ["Institution_Name", "Location", "Region", "SIZE", "FOCUS", "RES", "STATUS"]
    for ind in INDICATORS:
        cols += [f"{ind}_Score", f"{ind}_Rank"]
    cols.append("Overall_Score")
    return cols


def norm(s: Any) -> str:
    """lowercase + strip everything but letters/digits, for fuzzy key matching."""
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


# normalized indicator-name -> our column prefix
INDICATOR_LOOKUP = {
    "academicreputation": "Academic_Reputation",
    "employerreputation": "Employer_Reputation",
    "facultystudent": "Faculty_Student",
    "facultystudentratio": "Faculty_Student",
    "citationsperfaculty": "Citations_per_Faculty",
    "internationalfaculty": "International_Faculty",
    "internationalfacultyratio": "International_Faculty",
    "internationalstudents": "International_Students",
    "internationalstudentratio": "International_Students",
    "internationalstudentdiversity": "International_Students",
    "internationalresearchnetwork": "International_Research_Network",
    "employmentoutcomes": "Employment_Outcomes",
    "sustainability": "Sustainability",
    "sustainabilityscore": "Sustainability",
}


def clean(v: Any) -> Optional[str]:
    """Strip HTML/whitespace; empty -> None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return str(v)
    text = BeautifulSoup(str(v), "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def is_cloudflare_challenge(html: str, status: Optional[int]) -> bool:
    h = (html or "").lower()
    markers = ["just a moment", "cf-chl", "challenge-platform", "checking your browser",
               "cf-browser-verification", "attention required! | cloudflare"]
    return status in (403, 503) or any(m in h for m in markers)


def detect_edition_year(html: str) -> int:
    m = re.search(r"World University Rankings\s*(?:</[^>]+>\s*)?(20\d{2})", html or "")
    if m:
        return int(m.group(1))
    m = re.search(r"rankings\D{0,40}(20\d{2})", html or "", re.I)
    return int(m.group(1)) if m else DEFAULT_EDITION_YEAR


def extract_nid(html: str, edition_year: int) -> Optional[str]:
    """Find the ranking node id the page uses for its JSON endpoint."""
    patterns = [
        r"qs_rankings_rest_api[^}]{0,40}?nid\\?[\"']\s*:\s*\\?[\"'](\d{5,})",  # drupalSettings (current)
        r"rankings/endpoint\?[^\"']*?nid=(\d{5,})",
        r"data-nid=[\"'](\d{5,})[\"']",
    ]
    for p in patterns:
        m = re.search(p, html or "")
        if m:
            return m.group(1)
    return KNOWN_NIDS.get(edition_year)


# ----------------------------------------------------------------------------
# JavaScript snippets executed inside the browser
# ----------------------------------------------------------------------------
WARMUP_JS = """
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  await sleep(1500 + Math.random() * 1500);
  window.scrollBy(0, 300 + Math.random() * 400);
  await sleep(800 + Math.random() * 800);
  window.scrollBy(0, -150);
  await sleep(600);
})();
"""

# DOM fallback helpers. Each waits until the range label ("1 - 30") changes,
# which is how we know the new page of cards has been rendered.
ROW_CSS = 'div.ind[class*="ranking-row-js-"]'       # keep in sync with ROW_SELECTORS


def _wait_for_change_js(action_js: str, timeout_ms: int = 30000) -> str:
    """Run action_js, then wait until the page shows a *different* set of cards."""
    return f"""
(async () => {{
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const label = () => (document.querySelector("{RANGE_LABEL}") || {{}}).textContent || "";
  const rows  = () => document.querySelectorAll('{ROW_CSS}');
  const sig   = () => label() + "|" + rows().length + "|" + (rows()[0]?.className || "");
  const before = sig();
  {action_js}
  const t0 = Date.now();
  while (Date.now() - t0 < {timeout_ms}) {{
    await sleep(400);
    if (rows().length > 0 && sig() !== before) break;
  }}
  await sleep(1500);   // let the last cards finish rendering
  window.scrollTo(0, 0);
}})();
"""


SET_PER_PAGE_JS = _wait_for_change_js(f"""
  const dd = document.querySelector("{PER_PAGE_DROPDOWN}");
  if (dd) {{ dd.click(); await sleep(400); }}
  const opt = document.querySelector('{PER_PAGE_OPTION.format(n=DOM_PER_PAGE)}');
  if (opt) opt.click(); else return;
""")

NEXT_PAGE_JS = _wait_for_change_js(f"""
  const nxt = document.querySelector("{NEXT_PAGE_LINK}");
  if (!nxt || nxt.closest("li")?.classList.contains("disabled")) return;
  nxt.scrollIntoView({{block: "center"}});
  await sleep(300);
  nxt.click();
""")


# ----------------------------------------------------------------------------
# Record normalisation
# ----------------------------------------------------------------------------
def empty_record(cols: List[str]) -> Dict[str, Optional[str]]:
    return {c: None for c in cols}


def first_key(d: Dict[str, Any], candidates: List[str]) -> Any:
    """Case/format-insensitive lookup of the first present candidate key."""
    nd = {norm(k): v for k, v in d.items()}
    for c in candidates:
        if norm(c) in nd and nd[norm(c)] not in (None, "", []):
            return nd[norm(c)]
    return None


def flatten_indicators(obj: Any) -> List[Dict[str, Any]]:
    """Recursively collect indicator dicts ({indicator_name, score, rank}) from any nesting.

    QS currently returns  scores = {"research_discovery": [ {...}, {...} ],
                                    "sustainability":     [ {...} ], ...}
    but older editions returned a flat list; both are handled here.
    """
    out: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        if any(norm(k) in ("indicatorname", "name", "label") for k in obj) and \
           any(norm(k) in ("score", "value", "rank") for k in obj):
            out.append(obj)
        else:
            for v in obj.values():
                out.extend(flatten_indicators(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(flatten_indicators(v))
    return out


def deep_find(obj: Any, pred, depth: int = 0) -> Any:
    """Depth-first search for the first (key, value) whose key satisfies pred(norm(key))."""
    if depth > 4:
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if pred(norm(k)) and v not in (None, "", [], {}):
                return v
        for v in obj.values():
            r = deep_find(v, pred, depth + 1)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = deep_find(v, pred, depth + 1)
            if r is not None:
                return r
    return None


def node_to_record(n: Dict[str, Any], cols: List[str], year: int) -> Dict[str, Optional[str]]:
    rec = empty_record(cols)
    prev_y = str(year - 1)

    rec[f"RANK_{year}"] = clean(first_key(n, ["rank_display", "rank", "overall_rank", "current_rank"]))

    # previous-year rank: common names first, then any nested key mentioning prev/last or the year
    prev = first_key(n, ["rank_display_prev", "prev_rank", "previous_rank", "rank_prev",
                         f"rank_display_{prev_y}", f"rank_{prev_y}", "last_year_rank"])
    if prev is None:
        prev = deep_find(n, lambda k: "rank" in k and ("prev" in k or "last" in k or prev_y in k))
    if f"RANK_{year - 1}" in rec:
        rec[f"RANK_{year - 1}"] = clean(prev) if not isinstance(prev, (dict, list)) else None

    rec["Institution_Name"] = clean(first_key(n, ["title", "name", "institution", "university"]))
    city = clean(first_key(n, ["city"]))
    country = clean(first_key(n, ["country", "country_name"]))
    rec["Location"] = ", ".join(x for x in (city, country) if x) or clean(first_key(n, ["location"]))
    rec["Region"] = clean(first_key(n, ["region", "region_name"]))

    # Classification badges (Size / Focus / Research intensity / Status) – may be nested
    def badge(pred):
        v = deep_find(n, pred)
        return clean(v) if v is not None and not isinstance(v, (dict, list)) else None
    rec["SIZE"] = badge(lambda k: k in ("size", "sizeclass", "classificationsize"))
    rec["FOCUS"] = badge(lambda k: k in ("focus", "subjectfocus", "classificationfocus"))
    rec["RES"] = badge(lambda k: k in ("res", "research", "researchintensity", "researchintensityclass"))
    rec["STATUS"] = badge(lambda k: k in ("status", "institutionstatus", "publicprivate"))

    rec["Overall_Score"] = clean(first_key(n, ["overall_score", "score", "overall"]))
    # private join keys – dropped by save()
    rec["_nid"] = clean(first_key(n, ["nid", "core_id"]))
    rec["_path"] = clean(first_key(n, ["path", "url"]))

    # Indicator scores/ranks – flatten whatever nesting QS uses this year
    for s in flatten_indicators(n.get("scores") or n.get("indicators") or n):
        name = norm(first_key(s, ["indicator_name", "name", "label", "title"]))
        col = INDICATOR_LOOKUP.get(name)
        if not col:
            if name in ("overall", "overallscore"):
                rec["Overall_Score"] = rec["Overall_Score"] or clean(first_key(s, ["score", "value"]))
            else:
                log.debug("Unmapped indicator %r", name)
            continue
        rec[f"{col}_Score"] = clean(first_key(s, ["score", "value"]))
        rec[f"{col}_Rank"] = clean(first_key(s, ["rank", "rank_display"]))   # e.g. "=43" kept verbatim
    return rec


# ----------------------------------------------------------------------------
# DOM fallback parsing
# ----------------------------------------------------------------------------
def sel_text(row, selectors: List[str]) -> Optional[str]:
    for s in selectors:
        el = row.select_one(s)
        if el:
            return clean(el.get_text(" ", strip=True))
    return None


def select_rows(soup: BeautifulSoup):
    for rs in ROW_SELECTORS:
        rows = soup.select(rs)
        if rows:
            return rows, rs
    return [], None


def parse_dom(html: str, cols: List[str], year: int) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    rows, used = select_rows(soup)
    if not rows:
        log.warning("No rows matched ROW_SELECTORS – inspect the page and update them.")
        return []

    records = []
    for row in rows:
        rec = empty_record(cols)
        rank = sel_text(row, FIELD_SELECTORS["RANK_CURRENT"])
        rec[f"RANK_{year}"] = re.sub(r"[†*]", "", rank).strip() if rank else None
        rec[f"RANK_{year - 1}"] = sel_text(row, FIELD_SELECTORS["RANK_PREVIOUS"])
        rec["Institution_Name"] = sel_text(row, FIELD_SELECTORS["Institution_Name"])
        loc = sel_text(row, FIELD_SELECTORS["Location"])
        rec["Location"] = re.sub(r"\s*,\s*", ", ", loc) if loc else None   # "Cambridge,  United States"
        rec["Region"] = sel_text(row, FIELD_SELECTORS["Region"])
        rec["Overall_Score"] = sel_text(row, FIELD_SELECTORS["Overall_Score"])

        badges = []
        for s in FIELD_SELECTORS["_badges"]:
            badges = [b for b in (clean(x.get_text()) for x in row.select(s)) if b]
            if badges:
                break
        for key, val in zip(["SIZE", "FOCUS", "RES", "STATUS"], badges):
            rec[key] = val

        # Indicator cards: name -> score (ranks aren't shown in the list view)
        boxes = []
        for s in FIELD_SELECTORS["_indicator_box"]:
            boxes = row.select(s)
            if boxes:
                break
        for box in boxes:
            name = norm(sel_text(box, FIELD_SELECTORS["_indicator_name"]))
            val = sel_text(box, FIELD_SELECTORS["_indicator_value"])
            col = INDICATOR_LOOKUP.get(name) or INDICATOR_LOOKUP.get(name.replace("score", ""))
            if col:
                rec[f"{col}_Score"] = val
            elif name in ("overall", "overallscore"):
                rec["Overall_Score"] = rec["Overall_Score"] or val
            # "International Fees", "Scholarship", ... are login-gated extras – ignored

        if rec["Institution_Name"]:
            records.append(rec)
    return records


# ----------------------------------------------------------------------------
# Crawl4AI plumbing
# ----------------------------------------------------------------------------
def make_browser_config() -> BrowserConfig:
    kwargs: Dict[str, Any] = dict(
        browser_type=BROWSER_TYPE,        # "undetected" = patched Chromium that hides CDP/automation traces
        headless=HEADLESS,
        viewport_width=1366,
        viewport_height=768,
        user_agent=USER_AGENT,
        headers=EXTRA_HEADERS,
        use_persistent_context=True,      # keep cookies (incl. cf_clearance) between runs
        user_data_dir=USER_DATA_DIR,
        extra_args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        verbose=False,
        enable_stealth=True,              # Crawl4AI >= 0.7; removed below if unsupported
    )
    # Degrade gracefully on older Crawl4AI versions that lack some kwargs
    for attempt in range(4):
        try:
            return BrowserConfig(**kwargs)
        except (TypeError, ValueError) as exc:
            msg = str(exc)
            if "enable_stealth" in msg and "enable_stealth" in kwargs:
                log.warning("enable_stealth unsupported – dropping it"); kwargs.pop("enable_stealth")
            elif ("browser_type" in msg or "undetected" in msg) and kwargs["browser_type"] != "chromium":
                log.warning("undetected browser unsupported – using chromium"); kwargs["browser_type"] = "chromium"
            elif "persistent" in msg or "user_data_dir" in msg:
                log.warning("persistent context unsupported – dropping it")
                kwargs.pop("use_persistent_context", None); kwargs.pop("user_data_dir", None)
            else:
                raise
    return BrowserConfig(**kwargs)


def initial_run_config(timeout_ms: int, delay: float = 4.0) -> CrawlerRunConfig:
    # Deliberately minimal: no js_code / overlay removal / magic during the first
    # navigation, because Cloudflare's challenge page reloads itself and destroys
    # the JS execution context (that's the "Execution context was destroyed" error).
    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        session_id=SESSION_ID,
        page_timeout=timeout_ms,
        wait_until="domcontentloaded",
        delay_before_return_html=delay,   # give the challenge time to auto-resolve
        simulate_user=True,
        override_navigator=True,
    )


def recheck_config(timeout_ms: int, delay: float) -> CrawlerRunConfig:
    """Re-read the current tab after waiting; no navigation, no scripts."""
    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        session_id=SESSION_ID,
        js_only=True,
        js_code="window.scrollBy(0, 200);",   # trivial, sync -> can't hang if context resets
        page_timeout=timeout_ms,
        delay_before_return_html=delay,
    )


def looks_like_real_page(html: str) -> bool:
    return bool(html) and "<body" in html.lower() and len(html) > 50_000


def js_run_config(js: str, timeout_ms: int, wait_for: Optional[str] = None,
                  delay: float = 1.0) -> CrawlerRunConfig:
    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        session_id=SESSION_ID,
        js_only=True,                 # reuse the open page, don't navigate again
        js_code=js,
        wait_for=wait_for,
        page_timeout=timeout_ms,
        delay_before_return_html=delay,
    )


async def load_page(crawler: AsyncWebCrawler) -> Optional[str]:
    """Open the rankings page, retrying on Cloudflare challenge. Returns HTML."""
    def ok(res) -> bool:
        # Crawl4AI's own anti-bot detector marks the Cloudflare interstitial as
        # success=False; we also accept a "failed" result if the HTML is clearly
        # the real page (its structural check occasionally false-positives).
        if not res:
            return False
        html = res.html or ""
        if is_cloudflare_challenge(html, getattr(res, "status_code", None)):
            return False
        return res.success or looks_like_real_page(html)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        timeout = BASE_TIMEOUT_MS * attempt
        log.info("Loading page (attempt %d/%d, timeout %ds) ...", attempt, MAX_ATTEMPTS, timeout // 1000)
        try:
            res = await crawler.arun(url=URL, config=initial_run_config(timeout, delay=4.0 * attempt))
        except Exception as exc:          # network / browser errors
            log.warning("arun failed: %s", exc)
            res = None
        if ok(res):
            return res.html

        # Challenge shown. Don't navigate again (that restarts the challenge);
        # wait in the same tab and re-read it a few times.
        log.warning("Cloudflare challenge detected (error=%s). Waiting %ds for it to resolve%s ...",
                    getattr(res, "error_message", None), CHALLENGE_WAIT_S,
                    "" if HEADLESS else " – if a checkbox appears in the browser window, click it")
        for _ in range(3):
            await asyncio.sleep(CHALLENGE_WAIT_S)
            try:
                res = await crawler.arun(url=URL, config=recheck_config(timeout, delay=2.0))
            except Exception as exc:
                log.debug("recheck failed: %s", exc)
                res = None
            if ok(res):
                log.info("Challenge cleared.")
                return res.html
        await asyncio.sleep(random.uniform(3, 8))

    log.error("Could not get past Cloudflare after %d attempts.", MAX_ATTEMPTS)
    log.error("Options: keep HEADLESS=False and solve the checkbox manually once (the profile in %s "
              "stores the clearance cookie); or run from a residential IP / VPN.", USER_DATA_DIR)
    return None


def api_url(nid: str, page: int) -> str:
    return (f"https://www.topuniversities.com{API_PATH}?nid={nid}&page={page}&items_per_page={ITEMS_PER_PAGE}"
            f"&tab=indicators&region=&countries=&cities=&search=&star=&sort=&order=&isSearch=false")


async def fetch_api_page(crawler: AsyncWebCrawler, nid: str, page: int) -> Dict[str, Any]:
    """Open the JSON endpoint in the same browser tab (keeps Cloudflare cookies).

    Chromium renders a JSON response as <pre>...</pre>; we pull the text back out.
    """
    cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        session_id=SESSION_ID,
        page_timeout=BASE_TIMEOUT_MS,
        wait_until="domcontentloaded",
        delay_before_return_html=0.5,
    )
    try:
        res = await crawler.arun(url=api_url(nid, page), config=cfg)
    except Exception as exc:
        return {"error": f"navigation failed: {exc}"}
    html = (res.html if res else "") or ""
    status = getattr(res, "status_code", None)
    if not html:
        return {"error": f"empty response (status={status}, {getattr(res, 'error_message', '')})"}
    soup = BeautifulSoup(html, "html.parser")
    pre = soup.find("pre")
    text = (pre.get_text() if pre else soup.get_text()).strip()
    try:
        return {"status": status, "json": json.loads(text)}
    except json.JSONDecodeError:
        return {"status": status, "json": None, "text": text[:600]}


def pick_nodes(j: Any) -> List[Dict[str, Any]]:
    """Locate the list of university rows inside the endpoint's JSON."""
    if isinstance(j, list):
        return [x for x in j if isinstance(x, dict)]
    if not isinstance(j, dict):
        return []
    for k in ("score_nodes", "nodes", "data", "results", "items", "rows"):
        v = j.get(k)
        if isinstance(v, list) and v:
            return [x for x in v if isinstance(x, dict)]
        if isinstance(v, dict):
            inner = pick_nodes(v)
            if inner:
                return inner
    # last resort: the largest list of dicts anywhere at top level
    lists = [v for v in j.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
    return max(lists, key=len) if lists else []


async def fetch_via_api(crawler: AsyncWebCrawler, nid: str) -> Optional[List[Dict[str, Any]]]:
    all_nodes: List[Dict[str, Any]] = []
    seen_keys: set = set()
    total: Optional[int] = None

    for page in range(MAX_API_PAGES):
        out = await fetch_api_page(crawler, nid, page)
        if out.get("error"):
            log.warning("API page %d: %s", page, out["error"])
            break
        j = out.get("json")
        if j is None:
            log.warning("API page %d returned non-JSON (HTTP %s). First bytes: %r",
                        page, out.get("status"), (out.get("text") or "")[:300])
            break
        if page == 0:
            # Diagnostics so the user can adapt key names if QS changed the schema
            top_keys = list(j.keys())[:20] if isinstance(j, dict) else f"<list len={len(j)}>"
            log.info("API page 0 -> HTTP %s, top-level keys: %s", out.get("status"), top_keys)
            if isinstance(j, dict):
                total = next((int(j[k]) for k in ("total_record", "total_count", "total", "count")
                              if str(j.get(k, "")).isdigit()), None)
        nodes = pick_nodes(j)
        if page == 0 and nodes:
            log.info("Sample node keys: %s", list(nodes[0].keys())[:30])
        if not nodes:
            log.info("API page %d: no rows – stopping.", page)
            break

        new = 0
        for n in nodes:
            key = (str(n.get("nid") or n.get("core_id") or n.get("path") or n.get("title")), str(n.get("rank_display")))
            if key not in seen_keys:
                seen_keys.add(key)
                all_nodes.append(n)
                new += 1
        log.info("API page %d: %d rows (%d new, %d total%s)", page, len(nodes), new, len(all_nodes),
                 f" of {total}" if total else "")
        if new == 0:                      # server is repeating the last page
            break
        if total and len(all_nodes) >= total:
            break
        if MAX_RECORDS and len(all_nodes) >= MAX_RECORDS:
            break
        await asyncio.sleep(random.uniform(0.6, 1.5))

    return all_nodes or None


def dom_nav_config() -> CrawlerRunConfig:
    """(Re)open the rankings page and wait until the JS has rendered the cards."""
    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        session_id=SESSION_ID,
        page_timeout=BASE_TIMEOUT_MS,
        wait_until="domcontentloaded",
        wait_for=f"css:{ROW_CSS}",
        delay_before_return_html=2.0,
    )


async def fetch_via_dom(crawler: AsyncWebCrawler, cols: List[str], year: int) -> List[Dict[str, Optional[str]]]:
    """Walk the numbered pagination, parsing each page of cards."""
    records: List[Dict[str, Optional[str]]] = []
    seen: set = set()

    # 0) make sure we're on the rankings page with cards rendered
    res = await crawler.arun(url=URL, config=dom_nav_config())
    if not res or not res.html:
        log.error("Could not (re)open rankings page: %s", getattr(res, "error_message", ""))
        return []

    # 1) bump results-per-page to the maximum (fewer page loads)
    res = await crawler.arun(url=URL, config=js_run_config(SET_PER_PAGE_JS, BASE_TIMEOUT_MS,
                                                          wait_for=f"css:{ROW_CSS}", delay=1.0))
    html = res.html if res and res.html else ""
    soup = BeautifulSoup(html, "html.parser")
    total_el = soup.select_one(TOTAL_LABEL)
    total = int(total_el.get_text(strip=True)) if total_el and total_el.get_text(strip=True).isdigit() else None
    rng = soup.select_one(RANGE_LABEL)
    log.info("DOM: showing %s of %s", rng.get_text(strip=True) if rng else "?", total or "?")

    # 2) parse current page, click "next", repeat
    for page in range(1, 400):
        page_recs = parse_dom(html, cols, year)
        new = 0
        for r in page_recs:
            key = (r.get(f"RANK_{year}"), r.get("Institution_Name"))
            if key not in seen:
                seen.add(key)
                records.append(r)
                new += 1
        log.info("DOM page %d: %d cards (%d new, %d total%s)", page, len(page_recs), new, len(records),
                 f" of {total}" if total else "")
        if not page_recs or new == 0:
            break
        if total and len(records) >= total:
            break
        if MAX_RECORDS and len(records) >= MAX_RECORDS:
            break
        # Is there a next page?
        nxt = soup.select_one(NEXT_PAGE_LINK)
        if not nxt or (nxt.find_parent("li") and "disabled" in (nxt.find_parent("li").get("class") or [])):
            break
        res = await crawler.arun(url=URL, config=js_run_config(NEXT_PAGE_JS, BASE_TIMEOUT_MS,
                                                              wait_for=f"css:{ROW_CSS}", delay=1.0))
        if not res or not res.html:
            log.warning("Next-page navigation failed: %s", getattr(res, "error_message", ""))
            break
        html = res.html
        soup = BeautifulSoup(html, "html.parser")
        await asyncio.sleep(random.uniform(0.5, 1.5))
    return records


# ----------------------------------------------------------------------------
# Enrichment: previous edition rank + profile-page badges
# ----------------------------------------------------------------------------
def find_previous_edition_url(html: str, prev_year: int) -> Optional[str]:
    """The rankings page links to earlier editions (year switcher). Find last year's."""
    for m in re.finditer(r'href=["\']([^"\']*world-university-rankings[^"\']*)["\']', html or ""):
        href = m.group(1)
        if str(prev_year) in href and "subject" not in href and "region" not in href:
            return href if href.startswith("http") else "https://www.topuniversities.com" + href
    # Common historical pattern as a fallback
    return f"https://www.topuniversities.com/world-university-rankings/{prev_year}"


async def fetch_edition_nodes(crawler: AsyncWebCrawler, current_html: str, edition_year: int
                              ) -> Optional[List[Dict[str, Any]]]:
    """Load the page of an earlier edition, read its nid and pull its endpoint rows."""
    url = find_previous_edition_url(current_html, edition_year)
    log.info("Edition %d: loading %s", edition_year, url)
    cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, session_id=SESSION_ID, page_timeout=BASE_TIMEOUT_MS,
                           wait_until="domcontentloaded", delay_before_return_html=3.0)
    res = await crawler.arun(url=url, config=cfg)
    if not res or not res.html or is_cloudflare_challenge(res.html, getattr(res, "status_code", None)):
        log.warning("Edition %d: page did not load – skipped", edition_year)
        return None
    found = detect_edition_year(res.html)
    if found != edition_year:
        log.warning("Edition %d: page at %s reports edition %s – check find_previous_edition_url()",
                    edition_year, url, found)
    nid = extract_nid(res.html, edition_year)
    if not nid:
        log.warning("Edition %d: no nid found – skipped", edition_year)
        return None
    log.info("Edition %d: nid=%s", edition_year, nid)
    return await fetch_via_api(crawler, nid)


def save_edition(records: List[Dict[str, Optional[str]]], cols: List[str], year: int) -> None:
    public = [{k: v for k, v in r.items() if not k.startswith("_")} for r in records]
    with open(f"qs_rankings_{year}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(public)
    with open(f"qs_rankings_{year}.json", "w", encoding="utf-8") as f:
        json.dump(public, f, ensure_ascii=False, indent=2)
    log.info("Edition %d: saved %d records -> qs_rankings_%d.csv/.json", year, len(records), year)


async def add_previous_editions(crawler: AsyncWebCrawler, records: List[Dict[str, Optional[str]]],
                                current_html: str, year: int, prev_years: List[int]
                                ) -> Dict[int, List[Dict[str, Optional[str]]]]:
    """For each previous edition: scrape it fully, save it, and join its rank into `records`."""
    by_nid_cur = {r.get("_nid"): r for r in records if r.get("_nid")}
    by_title_cur = {norm(r.get("Institution_Name")): r for r in records}
    editions: Dict[int, List[Dict[str, Optional[str]]]] = {}
    for py in prev_years:
        try:
            nodes = await fetch_edition_nodes(crawler, current_html, py)
        except Exception as exc:
            log.warning("Edition %d failed: %s", py, exc)
            nodes = None
        if not nodes:
            continue
        ecols = columns(py, prev_years=[])
        erecs = [node_to_record(n, ecols, py) for n in nodes]
        editions[py] = erecs
        save_edition(erecs, ecols, py)
        hit = 0
        for r in erecs:
            tgt = by_nid_cur.get(r.get("_nid")) or by_title_cur.get(norm(r.get("Institution_Name")))
            if tgt is not None and r.get(f"RANK_{py}"):
                tgt[f"RANK_{py}"] = r[f"RANK_{py}"]
                hit += 1
        log.info("Edition %d: rank joined for %d/%d current institutions", py, hit, len(records))
    return editions


def save_all_editions(current: List[Dict[str, Optional[str]]], year: int,
                      editions: Dict[int, List[Dict[str, Optional[str]]]]) -> None:
    """Long-format file: one row per (edition, institution) with an Edition column."""
    base = ["Edition", "Rank", "Institution_Name", "Location", "Region", "SIZE", "FOCUS", "RES", "STATUS"]
    base += [c for c in columns(year, []) if c.endswith("_Score") or c.endswith("_Rank")]
    rows = []
    for ey, recs in sorted([(year, current)] + list(editions.items())):
        for r in recs:
            row = {"Edition": ey, "Rank": r.get(f"RANK_{ey}")}
            row.update({k: v for k, v in r.items() if k in base and k not in ("Edition", "Rank")})
            rows.append(row)
    with open("qs_rankings_all_editions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=base, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    log.info("Saved %d rows across %d editions -> qs_rankings_all_editions.csv", len(rows), len(editions) + 1)


# Profile-page badge extraction. QS shows the classification (Size / Focus /
# Research intensity / Status) on each university page. Selectors first, then
# a label-text fallback that finds e.g. "Size" and takes the adjacent value.
PROFILE_BADGE_SELECTORS: Dict[str, List[str]] = {
    "SIZE":   ['[data-testid="size"]', ".size .value", ".univ-size", "[class*='size'] .value"],
    "FOCUS":  ['[data-testid="focus"]', ".focus .value", ".univ-focus", "[class*='focus'] .value"],
    "RES":    ['[data-testid="research"]', ".research .value", ".univ-research", "[class*='research'] .value"],
    "STATUS": ['[data-testid="status"]', ".status .value", ".univ-status", "[class*='status'] .value"],
}
PROFILE_LABELS = {"SIZE": ("size",), "FOCUS": ("focus",),
                  "RES": ("research intensity", "research output", "research"), "STATUS": ("status",)}


def parse_profile_badges(html: str) -> Dict[str, Optional[str]]:
    soup = BeautifulSoup(html, "html.parser")
    out: Dict[str, Optional[str]] = {k: None for k in PROFILE_BADGE_SELECTORS}
    for key, sels in PROFILE_BADGE_SELECTORS.items():
        for s in sels:
            el = soup.select_one(s)
            if el and clean(el.get_text()):
                out[key] = clean(el.get_text())
                break
    # label-text fallback
    for key, labels in PROFILE_LABELS.items():
        if out[key]:
            continue
        for lab in labels:
            # Case A: "Status: Private" in one text node
            node = soup.find(string=lambda t: t and re.match(rf"^\s*{re.escape(lab)}\s*[:\-–]\s*\S", t, re.I))
            if node:
                val = clean(re.sub(rf"^\s*{re.escape(lab)}\s*[:\-–]\s*", "", str(node), flags=re.I))
                if val and len(val) <= 40:
                    out[key] = val
                    break
            # Case B: label in its own element, value in the next one
            node = soup.find(string=lambda t: t and norm(t) in (norm(lab), norm(lab + ":")))
            if not node:
                continue
            el = node.parent
            # value is usually the next element/sibling, or the rest of the parent's text
            cand = el.find_next_sibling()
            val = clean(cand.get_text()) if cand else None
            if not val and el.parent:
                txt = clean(el.parent.get_text(" ", strip=True)) or ""
                val = clean(re.sub(re.escape(lab), "", txt, flags=re.I).strip(" :-")) or None
            if val and len(val) <= 40:
                out[key] = val
                break
    return out


async def add_profile_badges(crawler: AsyncWebCrawler, records: List[Dict[str, Optional[str]]]) -> None:
    done = 0
    for i, r in enumerate(records, 1):
        path = r.get("_path")
        if not path:
            continue
        url = path if path.startswith("http") else "https://www.topuniversities.com" + path
        cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, session_id=SESSION_ID, page_timeout=BASE_TIMEOUT_MS,
                               wait_until="domcontentloaded", delay_before_return_html=1.5)
        try:
            res = await crawler.arun(url=url, config=cfg)
        except Exception as exc:
            log.warning("Profile %s failed: %s", url, exc)
            continue
        if not res or not res.html:
            continue
        if i == 1:   # keep one page for selector tuning
            with open("qs_profile_debug.html", "w", encoding="utf-8") as f:
                f.write(res.html)
        badges = parse_profile_badges(res.html)
        r.update({k: v for k, v in badges.items() if v})
        done += any(badges.values())
        if i <= 3:
            log.info("Profile %d (%s): %s", i, r.get("Institution_Name"), badges)
        if i == PROFILE_ABORT_AFTER and done == 0:
            log.error("First %d profile pages yielded no badges - aborting the profile pass. "
                      "Upload qs_profile_debug.html so the selectors can be fixed.", PROFILE_ABORT_AFTER)
            return
        if i % 25 == 0 or i == len(records):
            log.info("Profiles: %d/%d visited, %d with badges (~%d min left)", i, len(records), done,
                     int((len(records) - i) * (sum(PROFILE_DELAY_S) / 2 + 2.5) / 60))
        await asyncio.sleep(random.uniform(*PROFILE_DELAY_S))
    if done == 0:
        log.warning("No badges found on profile pages – inspect qs_profile_debug.html and adjust "
                    "PROFILE_BADGE_SELECTORS / PROFILE_LABELS")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def save(records: List[Dict[str, Optional[str]]], cols: List[str]) -> None:
    public = [{k: v for k, v in r.items() if not k.startswith("_")} for r in records]
    with open("qs_rankings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(public)
    with open("qs_rankings.json", "w", encoding="utf-8") as f:
        json.dump(public, f, ensure_ascii=False, indent=2)
    log.info("Saved %d records -> qs_rankings.csv, qs_rankings.json", len(records))


async def main() -> List[Dict[str, Optional[str]]]:
    records: List[Dict[str, Optional[str]]] = []
    html = ""
    async with AsyncWebCrawler(config=make_browser_config()) as crawler:
        html = await load_page(crawler) or ""
        year = detect_edition_year(html)
        prev_years = [year - i for i in range(1, EDITIONS_BACK + 1)]
        cols = columns(year, prev_years)
        log.info("Detected edition year: %s (previous editions to fetch: %s)", year, prev_years or "none")

        if html:
            # --- 1. API route --------------------------------------------------
            nid = extract_nid(html, year)
            if nid:
                log.info("Using ranking nid=%s", nid)
                try:
                    nodes = await fetch_via_api(crawler, nid)
                except Exception as exc:
                    log.warning("API route raised: %s", exc)
                    nodes = None
                if nodes:
                    with open("qs_rankings_raw_api.json", "w", encoding="utf-8") as f:
                        json.dump(nodes, f, ensure_ascii=False, indent=1)
                    log.info("Raw endpoint rows saved -> qs_rankings_raw_api.json")
                    records = [node_to_record(n, cols, year) for n in nodes]
            else:
                log.warning("Could not detect nid in page – skipping API route")

            # --- 2. DOM fallback -----------------------------------------------
            if not records:
                log.info("Falling back to DOM scraping ...")
                try:
                    records = await fetch_via_dom(crawler, cols, year)
                except Exception as exc:
                    log.error("DOM scraping failed: %s", exc)

        if records and MAX_RECORDS:
            records = records[:MAX_RECORDS]
        editions: Dict[int, List[Dict[str, Optional[str]]]] = {}
        if records and prev_years:
            try:
                editions = await add_previous_editions(crawler, records, html, year, prev_years)
            except Exception as exc:
                log.warning("Previous-edition scrape failed: %s", exc)
        if records and FETCH_PROFILES:
            try:
                await add_profile_badges(crawler, records)
            except Exception as exc:
                log.warning("Profile pass failed: %s", exc)

        # dedupe by (rank, name) and apply MAX_RECORDS
        seen, unique = set(), []
        for r in records:
            key = (r.get(f"RANK_{year}"), r.get("Institution_Name"))
            if key not in seen:
                seen.add(key)
                unique.append(r)
        records = unique[:MAX_RECORDS] if MAX_RECORDS else unique

        if not records:
            with open("qs_rankings_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            log.warning("0 records parsed. Raw HTML written to qs_rankings_debug.html")
        save(records, cols)
        if editions:
            save_all_editions(records, year, editions)
    return records


def run() -> List[Dict[str, Optional[str]]]:
    """Entry point that works in a plain interpreter AND inside Jupyter/Colab."""
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # Playwright needs Proactor
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Jupyter / Colab: an event loop is already running -> allow nesting
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(main())
    return asyncio.run(main())


if __name__ == "__main__":
    data = run()
    print(f"Scraped {len(data)} universities.")
    if data:
        print(json.dumps({k: v for k, v in data[0].items() if not k.startswith("_")}, indent=2, ensure_ascii=False))