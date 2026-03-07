"""Knowledge Feed Blueprint.

Provides the build_knowledge_feed() function and all /api/knowledge/* routes.

Extracted from api_server.py. The function build_knowledge_feed is also
importable directly for use by scripts/tusk_knowledge_refresh.py:

    from routes.knowledge import build_knowledge_feed
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import requests as _requests

from flask import Blueprint, jsonify, request

from routes._shared import (
    DATA_DIR,
    KNOWLEDGE_FEED_FILE,
    KNOWLEDGE_SAVED_FILE,
    MEDIUM_FORYOU_CACHE_FILE,
    ROOT,
    X_FEED_CACHE_FILE,
    load_json,
    log,
    make_meta,
    save_json,
)

knowledge_bp = Blueprint("knowledge", __name__)


# ---------------------------------------------------------------------------
# Core: build_knowledge_feed
# ---------------------------------------------------------------------------


def build_knowledge_feed(force: bool = False) -> dict[str, Any]:
    """Build a knowledge feed JSON (preload-oriented).

    Sources:
      - Towards Data Science (publication RSS) -> filtered into ML / Stats / LLMs
      - 机器之心 (jiqizhixin) RSS
      - 量子位 (qbitai) RSS
      - PingWest / 36kr best-effort HTML scrape (if accessible)
      - X cache (data/x_feed_cache.json) as a small "Social" section

    The page should NOT recompute on every visit. This function is only used on
    cache-miss or /refresh.

    Output schema matches knowledge_feed/index.html:
      { generated: <iso>, sections: [{title, subtitle, items:[{title,url,source,cover}]}] }
    """

    now_iso = datetime.now().isoformat(timespec="seconds")

    # --- de-dupe across days ---
    SEEN_FILE = DATA_DIR / "knowledge_seen_urls.json"
    seen_data = load_json(SEEN_FILE, {"seen": {}})
    seen: dict[str, float] = seen_data.get("seen", {}) or {}

    # Drop old seen (>7 days)
    cutoff = time.time() - 7 * 24 * 3600
    seen = {
        u: ts
        for (u, ts) in seen.items()
        if isinstance(ts, (int, float)) and ts >= cutoff
    }

    def mark_seen(url: str) -> None:
        if url:
            seen[url] = time.time()

    def allow(url: str) -> bool:
        return bool(url) and url not in seen

    def allow_if_older(url: str, min_age_sec: float) -> bool:
        """Allow url if not seen recently (or never seen)."""
        if not url:
            return False
        ts = seen.get(url)
        if ts is None:
            return True
        try:
            return (time.time() - float(ts)) >= float(min_age_sec)
        except Exception:
            return True

    def fetch_text(url: str) -> str | None:
        try:
            r = _requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (MegaDashboard/1.0)"},
                timeout=25,
            )
            if r.status_code >= 400:
                return None
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception as e:
            log.warning("RSS fetch failed: %s", e)
            return None

    def parse_rss(url: str) -> list[dict[str, Any]]:
        """Parse RSS2 or Atom feeds into a common item shape.

        Returns list of: {title, url, categories, cover}
        """
        text = fetch_text(url)
        if not text:
            return []
        try:
            root = ET.fromstring(text)
        except Exception:
            return []

        out: list[dict[str, Any]] = []

        # --- RSS2 ---
        rss_items = root.findall(".//item")
        if rss_items:
            for item in rss_items:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if not link:
                    # some feeds use guid
                    link = (item.findtext("guid") or "").strip()
                cats = [c.text.strip() for c in item.findall("category") if c.text]

                cover = ""
                # media:content
                for el in item.findall("{http://search.yahoo.com/mrss/}content"):
                    cover = el.attrib.get("url", "") or cover
                # media:thumbnail
                if not cover:
                    thumb = item.find("{http://search.yahoo.com/mrss/}thumbnail")
                    if thumb is not None:
                        cover = thumb.attrib.get("url", "") or cover
                # enclosure
                if not cover:
                    enc_el = item.find("enclosure")
                    if enc_el is not None:
                        cover = enc_el.attrib.get("url", "") or cover
                # content:encoded (fallback)
                if not cover:
                    enc = (
                        item.findtext(
                            "{http://purl.org/rss/1.0/modules/content/}encoded"
                        )
                        or ""
                    )
                    m = re.search(r'<img[^>]+src="([^"]+)"', enc)
                    if m:
                        cover = m.group(1)

                out.append(
                    {"title": title, "url": link, "categories": cats, "cover": cover}
                )
            return out

        # --- Atom (e.g., YouTube feeds) ---
        atom_ns = "{http://www.w3.org/2005/Atom}"
        media_ns = "{http://search.yahoo.com/mrss/}"
        for entry in root.findall(f".//{atom_ns}entry"):
            title = (entry.findtext(f"{atom_ns}title") or "").strip()

            link = ""
            for lnk in entry.findall(f"{atom_ns}link"):
                rel = lnk.attrib.get("rel", "")
                href = lnk.attrib.get("href", "")
                if href and (rel == "alternate" or rel == ""):
                    link = href
                    break
            cats = [
                c.attrib.get("term", "")
                for c in entry.findall(f"{atom_ns}category")
                if c.attrib.get("term")
            ]

            cover = ""
            thumb = entry.find(f"{media_ns}group/{media_ns}thumbnail")
            if thumb is not None:
                cover = thumb.attrib.get("url", "") or cover

            out.append(
                {"title": title, "url": link, "categories": cats, "cover": cover}
            )

        return out

    def scrape_links(
        url: str, host_label: str, max_items: int = 25
    ) -> list[dict[str, Any]]:
        """Best-effort HTML scrape: extract reasonable-looking article links."""
        html = fetch_text(url)
        if not html:
            return []
        # Grab hrefs that look like articles; keep absolute urls only
        hrefs = re.findall(r'href="(https?://[^"]+)"', html)
        out: list[dict[str, Any]] = []
        for h in hrefs:
            if any(bad in h for bad in ["/login", "/signup", "javascript:"]):
                continue
            if h.startswith(url.rstrip("/")):
                pass
            # Light filters per site
            if "pingwest.com" in h and "/" not in h.replace(
                "https://www.pingwest.com/", ""
            ):
                continue
            if len(out) >= max_items:
                break
            out.append({"title": "", "url": h, "source": host_label, "cover": ""})
        # Dedupe
        dedup: dict[str, dict[str, Any]] = {}
        for it in out:
            dedup[it["url"]] = it
        return list(dedup.values())

    # ------------------------------------------------------------
    # Build sections to match Haowei's desired layout:
    # 1) Social: X (3) + YouTube (2)
    # 2) Blogs: Medium (3) + TowardsDataScience (2)
    # 3) Chinese: 5 hottest across 36kr / 机器之心 / 量子位 / 品玩
    # ------------------------------------------------------------

    def normalize_item(
        title: str, url: str, source: str, cover: str = ""
    ) -> dict[str, Any]:
        return {
            "title": title or "",
            "url": url or "",
            "source": source or "",
            "cover": cover or "",
        }

    def looks_ai_related(title: str, url: str = "") -> bool:
        t = (title or "").lower()
        u = (url or "").lower()
        keywords = [
            "ai",
            "llm",
            "gpt",
            "chatgpt",
            "claude",
            "gemini",
            "openai",
            "anthropic",
            "transformer",
            "language model",
            "rag",
            "agent",
            "diffusion",
            "machine learning",
        ]
        return any(k in t or k in u for k in keywords)

    def pick_unique(
        pool: list[dict[str, Any]],
        limit: int,
        min_age_sec_fallback: float | None = None,
    ) -> list[dict[str, Any]]:
        """Pick up to limit unique items.

        If min_age_sec_fallback is set and we can't fill the quota with unseen URLs,
        allow URLs that were seen but older than that threshold.
        """
        out: list[dict[str, Any]] = []
        used: set[str] = set()

        def ok(url: str) -> bool:
            if url in used:
                return False
            if allow(url):
                return True
            if min_age_sec_fallback is not None and allow_if_older(
                url, min_age_sec_fallback
            ):
                return True
            return False

        for it in pool:
            url = str(it.get("url") or "")
            if not ok(url):
                continue
            out.append(it)
            used.add(url)
            mark_seen(url)
            if len(out) >= limit:
                break
        return out

    # --- Social: replace low-quality X cache with higher-signal sources (HN/Reddit) ---
    # (No manual login; uses public RSS + simple heuristics)

    def fill_cover_best_effort(it: dict[str, Any]) -> None:
        """Try to ensure a cover image exists. Falls back to a site favicon."""
        if it.get("cover"):
            return
        url = str(it.get("url") or "")
        if not url:
            return
        html = fetch_text(url) or ""
        cover = ""
        if html:
            for pat in [
                r'property="og:image" content="([^"]+)"',
                r'name="twitter:image" content="([^"]+)"',
                r'property="og:image:url" content="([^"]+)"',
                r'property="og:image:secure_url" content="([^"]+)"',
            ]:
                m = re.search(pat, html)
                if m:
                    cover = m.group(1)
                    break
        if not cover and html:
            m = re.search(
                r'<img[^>]+src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"',
                html,
                flags=re.I,
            )
            if m:
                cover = m.group(1)
        if not cover:
            # favicon fallback (always present-ish)
            cover = (
                "https://www.google.com/s2/favicons?sz=256&domain_url="
                + urllib.parse.quote(url, safe="")
            )
        it["cover"] = cover

    # ── Parallel RSS/scrape prefetch ─────────────────────────
    # Fire all independent HTTP fetches at once to cut cold-start
    # from ~120s (serial) to ~25s (one timeout window).
    from concurrent.futures import ThreadPoolExecutor, as_completed

    _rss_jobs: list[tuple[str, str]] = [
        # Social / HN
        ("https://hnrss.org/newest?q=llm+OR+rag+OR+anthropic+OR+openai+OR+gpt+OR+gemini+OR+transformer", "hn"),
        # AI news
        ("https://blog.google/technology/ai/rss/", "ai:Google AI"),
        ("https://www.deeplearning.ai/the-batch/feed/", "ai:deeplearning.ai · The Batch"),
        ("https://www.theverge.com/rss/index.xml", "ai:The Verge"),
        # Blogs
        ("https://towardsdatascience.com/feed", "tds"),
        ("https://medium.com/feed/tag/machine-learning", "med"),
        ("https://medium.com/feed/tag/statistics", "med"),
        ("https://medium.com/feed/tag/large-language-models", "med"),
        ("https://medium.com/feed/tag/llm", "med"),
        # Chinese RSS
        ("https://www.jiqizhixin.com/rss.xml", "cn:机器之心"),
        ("https://www.qbitai.com/feed", "cn:量子位"),
    ]

    # YouTube feeds (from config)
    YT_FEEDS_FILE = DATA_DIR / "youtube_feeds.json"
    yt_cfg = load_json(YT_FEEDS_FILE, {"feeds": []})
    yt_feeds = yt_cfg.get("feeds", []) or []
    for feed_url in yt_feeds[:10]:
        _rss_jobs.append((str(feed_url), "yt"))

    _scrape_jobs: list[tuple[str, str, int]] = [
        ("https://www.pingwest.com/", "品玩", 60),
        ("https://36kr.com/", "36kr", 80),
    ]

    _prefetch: dict[str, list[dict[str, Any]]] = {}

    with ThreadPoolExecutor(max_workers=8) as pool:
        rss_futures = {
            pool.submit(parse_rss, url): (url, tag)
            for url, tag in _rss_jobs
        }
        scrape_futures = {
            pool.submit(scrape_links, url, label, max_items): (url, f"cn_scrape:{label}")
            for url, label, max_items in _scrape_jobs
        }
        for fut in as_completed({**rss_futures, **scrape_futures}):
            key_info = rss_futures.get(fut) or scrape_futures.get(fut)
            tag = key_info[1] if key_info else "?"
            try:
                _prefetch.setdefault(tag, []).extend(fut.result())
            except Exception as e:
                log.warning("Prefetch gather failed: %s", e)

    # ── Process prefetched results ────────────────────────────

    social_pool: list[dict[str, Any]] = []

    # Hacker News
    for it in _prefetch.get("hn", []):
        title = it.get("title") or ""
        url = it.get("url") or ""
        if not looks_ai_related(title, url):
            continue
        social_pool.append(normalize_item(title, url, "Hacker News", it.get("cover") or ""))

    # AI news RSS feeds
    _ai_labels = {"Google AI", "deeplearning.ai · The Batch", "The Verge"}
    for tag, items in _prefetch.items():
        if not tag.startswith("ai:"):
            continue
        label = tag[3:]
        for it in items:
            title = it.get("title") or ""
            url = it.get("url") or ""
            if not looks_ai_related(title, url):
                continue
            social_pool.append(normalize_item(title, url, label, it.get("cover") or ""))

    random.shuffle(social_pool)

    # Inject curated X posts (2 slots) — picked randomly from x_curated_posts.json
    X_CURATED_FILE = DATA_DIR / "x_curated_posts.json"
    picked_x: list[dict[str, Any]] = []
    try:
        xcurated = load_json(X_CURATED_FILE, {}).get("posts", [])
        random.shuffle(xcurated)
        for xp in xcurated:
            if len(picked_x) >= 2:
                break
            url = f"https://x.com/{xp.get('handle', '')}/status/{xp.get('tweet_id', '')}"
            title = xp.get("title", "")
            cover = xp.get("cover", "")
            author = xp.get("author_name", xp.get("handle", "X"))
            views = xp.get("views", 0)
            views_label = (
                f"{views / 1_000_000:.1f}M views"
                if views >= 1_000_000
                else (
                    f"{views // 1000}K views" if views >= 1000 else f"{views} views"
                )
            )
            if title and cover:
                picked_x.append(
                    {
                        "title": f"{title}",
                        "url": url,
                        "source": f"X · @{xp.get('handle', author)}",
                        "cover": cover,
                        "subtitle": views_label,
                    }
                )
    except Exception as e:
        log.warning("X feed scrape failed: %s", e)
        picked_x = []

    # Pick 1 from RSS (not 3) — X posts take 2 slots
    picked_social: list[dict[str, Any]] = []
    for it in social_pool:
        if len(picked_social) >= 1:
            break
        url = str(it.get("url") or "")
        if not url:
            continue
        if not (allow(url) or allow_if_older(url, 0)):
            continue
        fill_cover_best_effort(it)
        if not it.get("cover"):
            continue
        picked_social.append(it)
        mark_seen(url)

    picked_social = picked_x + picked_social

    # --- Social: YouTube (2) — from prefetch ---
    youtube_pool: list[dict[str, Any]] = []
    for it in _prefetch.get("yt", []):
        title = it.get("title") or ""
        url = it.get("url") or ""
        if not looks_ai_related(title, url):
            continue
        cover = it.get("cover") or ""
        if not cover:
            continue
        youtube_pool.append(normalize_item(title, url, "YouTube", cover))

    random.shuffle(youtube_pool)
    picked_yt = pick_unique(youtube_pool, 2, min_age_sec_fallback=0)

    social_items = picked_social + picked_yt

    # --- Blogs: Medium (3) ---
    # Prefer "For You" cache (scraped from authenticated browser) because Medium blocks server-side fetch.
    picked_medium: list[dict[str, Any]] = []
    try:
        mcache = load_json(MEDIUM_FORYOU_CACHE_FILE, {})
        cached_items = mcache.get("items") or []
        # sort by claps/comments if present
        cached_items = sorted(
            cached_items,
            key=lambda x: (int(x.get("claps") or 0), int(x.get("comments") or 0)),
            reverse=True,
        )
        for it in cached_items:
            title = str(it.get("title") or "")
            url = str(it.get("url") or "")
            cover = str(it.get("cover") or "")
            if not looks_ai_related(title, url):
                continue
            picked_medium.append(normalize_item(title, url, "Medium", cover))
            mark_seen(url)
            if len(picked_medium) >= 3:
                break
    except Exception as e:
        log.warning("Medium feed scrape failed: %s", e)
        picked_medium = []

    # Fallback to tag RSS if cache unavailable — from prefetch
    if len(picked_medium) < 3:
        medium_pool: list[dict[str, Any]] = []
        for it in _prefetch.get("med", []):
            title = it.get("title") or ""
            url = it.get("url") or ""
            if not looks_ai_related(title, url):
                continue
            medium_pool.append(
                normalize_item(title, url, "Medium", it.get("cover") or "")
            )
        random.shuffle(medium_pool)
        # don't reuse URLs already picked
        for it in medium_pool:
            if len(picked_medium) >= 3:
                break
            if it.get("url") in [x.get("url") for x in picked_medium]:
                continue
            picked_medium.extend(pick_unique([it], 1, min_age_sec_fallback=0))

    # --- Blogs: Towards Data Science (2) — from prefetch ---
    tds_pool: list[dict[str, Any]] = []
    for it in _prefetch.get("tds", []):
        title = it.get("title") or ""
        url = it.get("url") or ""
        cats = " ".join((it.get("categories") or [])).lower()
        if not looks_ai_related(title, url) and not any(
            k in cats
            for k in [
                "machine learning",
                "deep learning",
                "artificial intelligence",
                "nlp",
                "statistics",
                "data science",
            ]
        ):
            continue
        tds_pool.append(
            normalize_item(title, url, "Towards Data Science", it.get("cover") or "")
        )

    picked_tds = pick_unique(tds_pool, 2, min_age_sec_fallback=0)

    blogs_items = picked_medium + picked_tds

    # --- Chinese (5 hottest-ish) — from prefetch ---
    cn_pool: list[dict[str, Any]] = []

    # RSS sources
    for tag, source in [("cn:机器之心", "机器之心"), ("cn:量子位", "量子位")]:
        for it in _prefetch.get(tag, []):
            cn_pool.append(
                normalize_item(
                    it.get("title") or "",
                    it.get("url") or "",
                    source,
                    it.get("cover") or "",
                )
            )

    # Best-effort scrapes
    for tag, source in [("cn_scrape:品玩", "品玩"), ("cn_scrape:36kr", "36kr")]:
        for it in _prefetch.get(tag, []):
            cn_pool.append(
                normalize_item(
                    it.get("title") or "",
                    it.get("url") or "",
                    source,
                    it.get("cover") or "",
                )
            )

    # De-dupe by URL
    dedup: dict[str, dict[str, Any]] = {}
    for it in cn_pool:
        u = str(it.get("url") or "")
        if u:
            dedup[u] = it
    cn_pool = list(dedup.values())
    random.shuffle(cn_pool)

    def fill_title_cover_inline(it: dict[str, Any]) -> None:
        """Try to fill missing title/cover by fetching HTML and reading <title> + og:image."""
        url = str(it.get("url") or "")
        if not url:
            return
        if it.get("title") and it.get("cover"):
            return
        html = fetch_text(url) or ""
        if not html:
            return
        if not it.get("title"):
            m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
            if m:
                it["title"] = re.sub(r"\s+", " ", m.group(1)).strip()
        if not it.get("cover"):
            # Try OpenGraph / Twitter cards
            for pattern in [
                r'property="og:image" content="([^"]+)"',
                r'name="twitter:image" content="([^"]+)"',
                r'property="og:image:url" content="([^"]+)"',
                r'property="og:image:secure_url" content="([^"]+)"',
            ]:
                m = re.search(pattern, html)
                if m:
                    it["cover"] = m.group(1)
                    break

        if not it.get("cover"):
            # Common lazyload patterns (qbitai / some CN sites)
            for pattern in [
                r'data-src="([^"]+\.(?:jpg|jpeg|png|webp))"',
                r'data-original="([^"]+\.(?:jpg|jpeg|png|webp))"',
            ]:
                m = re.search(pattern, html, flags=re.I)
                if m:
                    it["cover"] = m.group(1)
                    break

        if not it.get("cover"):
            # Fallback: first reasonable <img src>
            m = re.search(
                r'<img[^>]+src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"',
                html,
                flags=re.I,
            )
            if m:
                it["cover"] = m.group(1)

        # Avoid site logos / headers as "covers"
        c = str(it.get("cover") or "")
        if c and any(
            bad in c.lower() for bad in ["logo", "head.jpg", "favicon", "avatar"]
        ):
            it["cover"] = ""

    # Pick 5 Chinese items with diversity across sources.
    # Goal: include multiple sources (36kr / 机器之心 / 量子位 / 品玩).
    quotas = {"机器之心": 2, "量子位": 1, "36kr": 1, "品玩": 1}

    pools: dict[str, list[dict[str, Any]]] = {k: [] for k in quotas}
    other_pool: list[dict[str, Any]] = []

    for it in cn_pool:
        src = str(it.get("source") or "")
        if src in pools:
            pools[src].append(it)
        else:
            other_pool.append(it)

    picked_cn: list[dict[str, Any]] = []

    def try_pick_from(pool: list[dict[str, Any]], want: int) -> None:
        nonlocal picked_cn
        for it in pool:
            if want <= 0 or len(picked_cn) >= 5:
                break
            url = str(it.get("url") or "")
            if not url:
                continue
            if not (allow(url) or allow_if_older(url, 0)):
                continue
            fill_title_cover_inline(it)
            if not it.get("title") or not it.get("cover"):
                continue
            picked_cn.append(it)
            mark_seen(url)
            want -= 1

    # First satisfy per-source quotas
    for src, want in quotas.items():
        try_pick_from(pools.get(src, []), want)

    # Backfill remaining slots from any Chinese pool
    if len(picked_cn) < 5:
        merged: list[dict[str, Any]] = []
        for src in ["机器之心", "量子位", "36kr", "品玩"]:
            merged.extend(pools.get(src, []))
        merged.extend(other_pool)
        random.shuffle(merged)
        try_pick_from(merged, 5 - len(picked_cn))

    def extract_og_image(url: str) -> str:
        html = fetch_text(url)
        if not html:
            return ""
        # Try OpenGraph / Twitter cards
        for pattern in [
            r'property="og:image" content="([^"]+)"',
            r'name="twitter:image" content="([^"]+)"',
            r'property="og:image:url" content="([^"]+)"',
        ]:
            m = re.search(pattern, html)
            if m:
                return m.group(1)
        return ""

    def extract_html_title(url: str) -> str:
        html = fetch_text(url)
        if not html:
            return ""
        m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
        if not m:
            return ""
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        return t

    def ensure_cover(item: dict[str, Any]) -> bool:
        """Ensure item has a non-empty cover URL; try og:image if missing."""
        if item.get("cover"):
            return True
        url = str(item.get("url") or "")
        if not url:
            return False
        img = extract_og_image(url)
        if img:
            item["cover"] = img
            return True
        return False

    # Fill missing covers for Blogs (Medium/TDS) via og:image (only 5 items)
    for it in blogs_items:
        ensure_cover(it)

    # Download and locally cache hotlink-protected Chinese cover images
    _PROXY_REFERERS: dict[str, str] = {
        "image.jiqizhixin.com": "https://www.jiqizhixin.com/",
        "i.qbitai.com": "https://www.qbitai.com/",
    }
    THUMB_DIR = DATA_DIR / "thumbnails"

    def cache_cn_cover(item: dict[str, Any]) -> None:
        """Download hotlink-protected image with correct Referer and store locally."""
        cover = str(item.get("cover") or "")
        if not cover or cover.startswith("/data/") or cover.startswith(
            "http://localhost"
        ):
            return
        host = urllib.parse.urlparse(cover).netloc
        referer = _PROXY_REFERERS.get(host)
        if not referer:
            return
        url_hash = hashlib.md5(cover.encode()).hexdigest()[:12]
        ext = cover.rsplit(".", 1)[-1].split("?")[0].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            ext = "jpg"
        local_path = THUMB_DIR / f"cn_{url_hash}.{ext}"
        if local_path.exists():
            item["cover"] = f"/data/thumbnails/cn_{url_hash}.{ext}"
            return
        try:
            hdrs = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "image/*,*/*;q=0.8",
                "Referer": referer,
            }
            r = _requests.get(cover, headers=hdrs, timeout=20)
            if r.status_code == 200 and len(r.content) > 1000:
                local_path.write_bytes(r.content)
                item["cover"] = f"/data/thumbnails/cn_{url_hash}.{ext}"
        except Exception as e:
            log.warning("Thumbnail download failed: %s", e)
            # Clear cover so item gets filtered out, letting another source fill the slot
            item["cover"] = ""

    for it in picked_cn:
        cache_cn_cover(it)

    # --- Assemble final sections ---
    sections: list[dict[str, Any]] = []
    # Ensure we output 5 items per section and all have covers.
    social_items = [it for it in social_items if it.get("cover")]
    blogs_items = [it for it in blogs_items if it.get("cover")]
    picked_cn = [it for it in picked_cn if it.get("cover")]

    if social_items:
        sections.append(
            {
                "title": "Social",
                "subtitle": "HN/AI News + YouTube",
                "items": social_items[:5],
            }
        )
    if blogs_items:
        sections.append(
            {
                "title": "Blogs",
                "subtitle": "Medium + TDS",
                "items": blogs_items[:5],
            }
        )
    if picked_cn:
        sections.append(
            {
                "title": "中文热点",
                "subtitle": "36kr / 机器之心 / 量子位 / 品玩",
                "items": picked_cn[:5],
            }
        )

    # persist seen
    save_json(SEEN_FILE, {"seen": seen})

    return {"generated": now_iso, "sections": sections}


# ---------------------------------------------------------------------------
# Helper: metadata scraping used by saved-link routes
# ---------------------------------------------------------------------------


def _extract_meta_content(raw: str, keys: list[str]) -> str:
    """Extract meta tag content from raw HTML for the given property/name keys."""
    for k in keys:
        pats = [
            rf"<meta[^>]*property=[\"']{re.escape(k)}[\"'][^>]*content=[\"'](.*?)[\"'][^>]*>",
            rf"<meta[^>]*content=[\"'](.*?)[\"'][^>]*property=[\"']{re.escape(k)}[\"'][^>]*>",
            rf"<meta[^>]*name=[\"']{re.escape(k)}[\"'][^>]*content=[\"'](.*?)[\"'][^>]*>",
            rf"<meta[^>]*content=[\"'](.*?)[\"'][^>]*name=[\"']{re.escape(k)}[\"'][^>]*>",
        ]
        for p in pats:
            m = re.search(p, raw, re.IGNORECASE | re.DOTALL)
            if m:
                v = re.sub(r"\s+", " ", m.group(1)).strip()
                if v:
                    return v
    return ""


def _scrape_link_meta(url: str) -> dict[str, str]:
    """Fetch a URL and extract its Open Graph / Twitter card metadata."""
    out: dict[str, str] = {
        "title": url,
        "cover": "",
        "description": "",
        "source": "",
        "favicon": "",
    }

    raw = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        log.warning("Metadata fetch failed: %s", e)
        raw = ""

    if raw:
        title = _extract_meta_content(raw, ["og:title", "twitter:title"]) or (
            re.search(
                r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL
            ).group(1)
            if re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
            else ""
        )
        if title:
            out["title"] = re.sub(r"\s+", " ", title).strip()[:220]

        cover = _extract_meta_content(
            raw,
            ["og:image", "og:image:url", "twitter:image", "twitter:image:src"],
        )
        if cover:
            out["cover"] = urllib.parse.urljoin(url, cover)

        desc = _extract_meta_content(
            raw, ["description", "og:description", "twitter:description"]
        )
        if desc:
            out["description"] = desc[:280]

        source = _extract_meta_content(raw, ["og:site_name", "application-name"])
        if source:
            out["source"] = source[:80]

        m_icon = re.search(
            r"<link[^>]+rel=[\"'][^\"']*icon[^\"']*[\"'][^>]+href=[\"'](.*?)[\"'][^>]*>",
            raw,
            re.IGNORECASE,
        )
        if m_icon:
            out["favicon"] = urllib.parse.urljoin(url, m_icon.group(1).strip())

    # Fallback: noembed / medium oembed (works for blocked sites)
    if (out["title"] == url) or (not out["cover"]):
        for oe in [
            "https://noembed.com/embed?url=" + urllib.parse.quote(url, safe=""),
            "https://medium.com/oembed?url=" + urllib.parse.quote(url, safe=""),
        ]:
            try:
                with urllib.request.urlopen(oe, timeout=12) as resp:
                    j = json.loads(resp.read().decode("utf-8") or "{}")
                if j.get("title") and out["title"] == url:
                    out["title"] = str(j.get("title"))[:220]
                if j.get("thumbnail_url") and not out["cover"]:
                    out["cover"] = str(j.get("thumbnail_url"))
                if j.get("provider_name") and not out["source"]:
                    out["source"] = str(j.get("provider_name"))[:80]
                if out["title"] != url and out["cover"]:
                    break
            except Exception as e:
                log.warning("Metadata scrape failed: %s", e)
                continue

    if not out["source"]:
        try:
            out["source"] = (
                urllib.parse.urlparse(url).netloc.replace("www.", "")[:80]
            )
        except Exception:
            out["source"] = ""

    if not out["favicon"]:
        try:
            base = "{uri.scheme}://{uri.netloc}".format(
                uri=urllib.parse.urlparse(url)
            )
            out["favicon"] = (
                base.rstrip("/") + "/favicon.ico"
                if base and base != "://"
                else ""
            )
        except Exception:
            out["favicon"] = ""

    # Fallback title from URL slug when blocked pages hide metadata
    if out["title"] == url:
        try:
            path = urllib.parse.urlparse(url).path.strip("/").split("/")[-1]
            slug = re.sub(r"-[0-9a-f]{8,}$", "", path, flags=re.IGNORECASE)
            slug = slug.replace("-", " ").strip()
            if slug:
                out["title"] = slug.title()[:220]
        except Exception:
            pass

    # Fallback cover: webpage screenshot first, then favicon
    if not out["cover"]:
        out["cover"] = f"https://image.thum.io/get/width/600/noanimate/{url}"
    if (not out["cover"]) and out["favicon"]:
        out["cover"] = out["favicon"]

    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@knowledge_bp.route("/api/knowledge")
def api_knowledge():
    """Return the precomputed knowledge feed.

    This should be FAST and not recompute anything on page load.
    Use POST /api/knowledge/refresh to force a rebuild.
    """
    data = load_json(KNOWLEDGE_FEED_FILE, None)
    if data is None:
        data = build_knowledge_feed()
        save_json(KNOWLEDGE_FEED_FILE, data)
    data["_meta"] = make_meta(data.get("generated"), stale_after_hours=12)
    return jsonify(data)


@knowledge_bp.route("/api/knowledge/refresh", methods=["POST"])
def api_knowledge_refresh():
    """Force a rebuild of the knowledge feed cache."""
    from cron_logger import CronLogger  # type: ignore

    _log = CronLogger("knowledge-feed-refresh-daily", "Tusk", "Knowledge feed rebuild")
    _log.start()
    try:
        data = build_knowledge_feed(force=True)
        save_json(KNOWLEDGE_FEED_FILE, data)
        secs = len(data.get("sections") or [])
        links = sum(len(s.get("items") or []) for s in (data.get("sections") or []))
        _log.finish("success", summary=f"{secs} sections, {links} links")
        return jsonify({"success": True, **data})
    except Exception as e:
        _log.finish("failed", error=str(e))
        raise


@knowledge_bp.route("/api/knowledge/saved", methods=["GET"])
def api_knowledge_saved_get():
    """Return the user's saved knowledge items."""
    data = load_json(KNOWLEDGE_SAVED_FILE, {"items": []})
    return jsonify(data)


@knowledge_bp.route("/api/knowledge/saved/add", methods=["POST"])
def api_knowledge_saved_add():
    """Add a URL to the saved knowledge list, enriching metadata via scraping."""
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url") or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "invalid_url"}), 400

    data = load_json(KNOWLEDGE_SAVED_FILE, {"items": []})
    items = data.get("items", []) or []
    if any(str(it.get("url") or "").strip() == url for it in items):
        return jsonify({"ok": True, "duplicate": True})

    title = str(payload.get("title") or "").strip() or url
    image = ""
    description = ""
    source = ""
    favicon = ""

    try:
        meta = _scrape_link_meta(url)
        title = meta.get("title") or title
        image = meta.get("cover") or ""
        description = meta.get("description") or ""
        source = meta.get("source") or ""
        favicon = meta.get("favicon") or ""
    except Exception as e:
        log.warning("Knowledge item meta read failed: %s", e)

    item = {
        "url": url,
        "title": title,
        "cover": image,
        "description": description,
        "source": source,
        "favicon": favicon,
        "summary": "",
        "saved_at": datetime.now().isoformat(),
    }
    items.insert(0, item)
    data["items"] = items
    save_json(KNOWLEDGE_SAVED_FILE, data)
    return jsonify({"ok": True, "item": item})


@knowledge_bp.route("/api/knowledge/saved/delete", methods=["POST"])
def api_knowledge_saved_delete():
    """Remove a URL from the saved knowledge list."""
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url") or "").strip()
    data = load_json(KNOWLEDGE_SAVED_FILE, {"items": []})
    items = data.get("items", []) or []
    items = [it for it in items if str(it.get("url") or "").strip() != url]
    data["items"] = items
    save_json(KNOWLEDGE_SAVED_FILE, data)
    return jsonify({"ok": True})


@knowledge_bp.route("/api/knowledge/saved/enrich", methods=["POST"])
def api_knowledge_saved_enrich():
    """Re-scrape metadata for an existing saved item (or add it if missing)."""
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url") or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "invalid_url"}), 400
    try:
        meta = _scrape_link_meta(url)
    except Exception as e:
        return (
            jsonify(
                {"ok": False, "error": "scrape_failed", "detail": str(e)[:300]}
            ),
            500,
        )

    data = load_json(KNOWLEDGE_SAVED_FILE, {"items": []})
    items = data.get("items", []) or []
    found = None
    for it in items:
        if str(it.get("url") or "").strip() == url:
            if meta.get("title"):
                it["title"] = meta["title"]
            if meta.get("cover"):
                it["cover"] = meta["cover"]
            if meta.get("description"):
                it["description"] = meta["description"]
            if meta.get("source"):
                it["source"] = meta["source"]
            if meta.get("favicon"):
                it["favicon"] = meta["favicon"]
            found = it
            break
    if found is None:
        found = {
            "url": url,
            "title": meta.get("title") or url,
            "cover": meta.get("cover") or "",
            "description": meta.get("description") or "",
            "source": meta.get("source") or "",
            "favicon": meta.get("favicon") or "",
            "summary": "",
            "saved_at": datetime.now().isoformat(),
        }
        items.insert(0, found)
    data["items"] = items
    save_json(KNOWLEDGE_SAVED_FILE, data)
    return jsonify({"ok": True, "item": found})


@knowledge_bp.route("/api/knowledge/summarize", methods=["POST"])
def api_knowledge_summarize():
    """Fetch a URL's content and generate an AI summary via the Anthropic API."""
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url") or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "invalid_url"}), 400

    # Fetch page (best-effort). If blocked, fall back to metadata-only summary.
    raw = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        log.warning("Tusk HTTP fetch failed: %s", e)
        raw = ""

    meta = _scrape_link_meta(url)
    title = meta.get("title") or url
    cover = meta.get("cover") or ""
    text = ""
    if raw:
        text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()[:20000]
    if not text:
        text = (meta.get("description") or "")[:1200]

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return jsonify({"ok": False, "error": "missing_ANTHROPIC_API_KEY"}), 500

    body = {
        "model": "claude-opus-4-6",
        "max_tokens": 900,
        "temperature": 0.2,
        "system": "你是一个阅读助手。请用中文做精炼总结，输出：1) 三句话摘要 2) 关键观点(3-6条) 3) 可执行启发(2-4条)",
        "messages": [
            {
                "role": "user",
                "content": f"URL: {url}\n标题: {title}\n\n正文:\n{text}",
            }
        ],
    }

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception as e:
        return jsonify({"ok": False, "error": "ai_failed", "detail": str(e)[:300]}), 500

    parts = out.get("content") or []
    summary = "".join(
        (p.get("text") or "") for p in parts if p.get("type") == "text"
    ).strip()

    # Persist to saved list (upsert)
    data = load_json(KNOWLEDGE_SAVED_FILE, {"items": []})
    items = data.get("items", []) or []
    found = False
    for it in items:
        if str(it.get("url") or "").strip() == url:
            it["title"] = title
            it["summary"] = summary
            if cover and not it.get("cover"):
                it["cover"] = cover
            it["summarized_at"] = datetime.now().isoformat()
            found = True
            break
    if not found:
        items.insert(
            0,
            {
                "url": url,
                "title": title,
                "cover": cover,
                "summary": summary,
                "saved_at": datetime.now().isoformat(),
                "summarized_at": datetime.now().isoformat(),
            },
        )
    data["items"] = items
    save_json(KNOWLEDGE_SAVED_FILE, data)

    return jsonify({"ok": True, "title": title, "summary": summary})
