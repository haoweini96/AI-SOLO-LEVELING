#!/usr/bin/env python3
"""
Article Study Analyzer
Fetches article content (including Medium paywalled articles via Puppeteer),
sends to Claude for structured analysis.

Usage:
    python3 analyze_article.py "https://example.com/article"
    python3 analyze_article.py "https://medium.com/@user/article-slug"
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent  # projects/mega/
DATA = ROOT / "data"
VIDEOS_INDEX = DATA / "study_videos.json"
ANALYSES_DIR = DATA / "study_analyses"

ANALYSES_DIR.mkdir(parents=True, exist_ok=True)

# ── Env ──────────────────────────────────────────────────────────────────────

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_json(path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text("utf-8"))
    except Exception:
        pass
    return default if default is not None else {}


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def article_id_from_url(url):
    """Generate a stable short ID from URL."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def is_medium_url(url):
    """Check if URL is a Medium article."""
    return bool(re.search(r"medium\.com|towardsdatascience\.com|betterprogramming\.pub|levelup\.gitconnected\.com", url))


def update_index(aid, **fields):
    """Update an entry in the study index file."""
    data = load_json(VIDEOS_INDEX, {"videos": []})
    found = False
    for v in data["videos"]:
        if v["video_id"] == aid:
            v.update(fields)
            found = True
            break
    if not found:
        entry = {"video_id": aid, **fields}
        data["videos"].insert(0, entry)
    save_json(VIDEOS_INDEX, data)


# ── Stage 1: Fetch Article Content ──────────────────────────────────────────

def _is_bot_blocked(text):
    """Check if fetched content is a Cloudflare/bot-check page instead of real article."""
    if not text or len(text) < 200:
        return True
    lower = text.lower()
    markers = ["security verification", "checking if the site connection is secure",
               "ray id:", "cloudflare", "just a moment", "enable javascript"]
    hits = sum(1 for m in markers if m in lower)
    return hits >= 2


def _is_error_page(text):
    """Check if fetched content is a 404/error page rather than a real article."""
    if not text:
        return True
    lower = text.lower()
    error_markers = [
        "404 not found", "page not found", "page doesn't exist",
        "page does not exist", "this page could not be found",
        "the page you're looking for", "the page you are looking for",
        "error 404", "error 403", "error 500", "410 gone",
        "this content is no longer available", "has been removed",
        "has been deleted", "no longer exists",
    ]
    return any(m in lower for m in error_markers)


def _is_error_analysis(analysis):
    """Check if Claude's analysis result describes an error page rather than real content."""
    title = (analysis.get("summary", {}).get("title", "") or "").lower()
    category = (analysis.get("category", "") or "").lower()
    takeaways = " ".join(analysis.get("summary", {}).get("takeaways", [])).lower()
    error_signals = ["404", "not found", "error page", "page not found", "missing page"]
    hits = sum(1 for s in error_signals if s in title or s in takeaways)
    return hits >= 2 or (category == "other" and hits >= 1)


def fetch_via_jina(url):
    """Fetch article content via Jina Reader API (free, no auth needed)."""
    print(f"  Fetching via Jina Reader...")
    jina_url = f"https://r.jina.ai/{url}"
    req = urllib.request.Request(jina_url, headers={
        "Accept": "text/plain",
        "User-Agent": "Mozilla/5.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        if _is_bot_blocked(raw):
            print(f"  Jina Reader got bot-blocked content")
            return None, None
        # Parse Jina's markdown response: Title:, URL Source:, Markdown Content:
        title = ""
        m = re.search(r"^Title:\s*(.+)$", raw, re.M)
        if m:
            title = m.group(1).strip()
        # Extract text after "Markdown Content:" header
        parts = raw.split("Markdown Content:", 1)
        text = parts[1].strip() if len(parts) > 1 else raw
        if text and len(text) > 200 and not _is_bot_blocked(text):
            meta_html = f'<title>{title}</title><meta property="og:title" content="{title}">'
            return text, meta_html
    except Exception as e:
        print(f"  Jina Reader failed: {e}")
    return None, None


def fetch_via_http(url):
    """Standard HTTP fetch + HTML strip. Raises on 4xx/5xx status codes."""
    print(f"  Fetching via HTTP...")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.getcode()
            if status and status >= 400:
                raise RuntimeError(f"HTTP {status}: server returned error status")
            raw = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.reason}")
    return raw


def fetch_via_puppeteer(url):
    """Fetch article via Puppeteer with persistent Chrome profile.
    Returns (text, metadata_dict) or (None, None)."""
    print(f"  Fetching via Puppeteer (authenticated)...")
    script = Path(__file__).parent / "fetch_medium.mjs"
    if not script.exists():
        print(f"  fetch_medium.mjs not found")
        return None, None

    try:
        result = subprocess.run(
            ["node", str(script), url],
            capture_output=True, text=True, timeout=90,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired:
        print(f"  Puppeteer timed out")
        return None, None

    if result.returncode != 0:
        print(f"  Puppeteer failed: {result.stderr[:300]}")
        return None, None

    try:
        data = json.loads(result.stdout)
        text = data.get("text") or ""
        if text and not _is_bot_blocked(text):
            meta = {
                "title": data.get("title", ""),
                "author": data.get("author", ""),
                "cover": data.get("cover", ""),
                "site": "",
            }
            return text, meta
        print(f"  Puppeteer got bot-blocked content")
    except json.JSONDecodeError:
        print(f"  Puppeteer returned invalid JSON")

    return None, None


def extract_text_from_html(raw):
    """Strip HTML to plain text."""
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_generic_og_image(cover_url):
    """Check if a cover URL is a generic/default OG image (not content-specific)."""
    if not cover_url:
        return True
    generic_patterns = [
        "abs.twimg.com/rweb/ssr/default",  # X/Twitter generic OG
        "abs.twimg.com/responsive-web",
        "pbs.twimg.com/profile_images/",   # X/Twitter user profile pic (not post-specific)
        "pbs.twimg.com/profile_banners/",  # X/Twitter user banner
        "static.xx.fbcdn.net",  # Facebook generic
    ]
    return any(p in cover_url for p in generic_patterns)


def _fetch_x_tweet_image(url):
    """Extract the actual media/OG image from an X/Twitter tweet via fxtwitter API.
    Priority: photos > videos > external card > article cover > author avatar."""
    tweet_match = re.search(r'(?:x\.com|twitter\.com)/([^/]+)/status/(\d+)', url)
    if not tweet_match:
        return ""
    tweet_id = tweet_match.group(2)

    try:
        api_url = f"https://api.fxtwitter.com/status/{tweet_id}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tweet = data.get("tweet", {})

        # 1. Attached media (photos/videos)
        media = tweet.get("media", {})
        photos = media.get("photos", [])
        if photos:
            img = photos[0].get("url", "")
            if img:
                print(f"  fxtwitter: got photo: {img[:100]}")
                return img
        videos = media.get("videos", [])
        if videos:
            img = videos[0].get("thumbnail_url", "")
            if img:
                print(f"  fxtwitter: got video thumbnail: {img[:100]}")
                return img
        # External link card thumbnail
        external = media.get("external", {})
        if external.get("thumbnail_url"):
            print(f"  fxtwitter: got external card thumbnail")
            return external["thumbnail_url"]
        # Mosaic preview (multi-image)
        mosaic = media.get("mosaic", {})
        if mosaic.get("formats", {}).get("jpeg"):
            print(f"  fxtwitter: got mosaic image")
            return mosaic["formats"]["jpeg"]

        # 2. Article cover media (X articles / long-form posts)
        article = tweet.get("article", {})
        cover_media = article.get("cover_media", {})
        cover_url = cover_media.get("media_info", {}).get("original_img_url", "")
        if cover_url:
            print(f"  fxtwitter: got article cover: {cover_url[:100]}")
            return cover_url

        # 3. Author avatar as last resort before placeholder
        avatar = tweet.get("author", {}).get("avatar_url", "")
        if avatar:
            # Use higher-res version (replace _200x200 with _400x400)
            avatar = avatar.replace("_200x200", "_400x400")
            print(f"  fxtwitter: using author avatar: {avatar[:100]}")
            return avatar

    except Exception as e:
        print(f"  fxtwitter API failed: {e}")

    return ""


FRAMES_DIR = DATA / "study_frames"


def _generate_placeholder_thumbnail(article_id, url, dest_dir, title=""):
    """Generate a unique gradient+title placeholder image when no real thumbnail is available."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import colorsys
    except ImportError:
        print("  Pillow not available for placeholder generation")
        return ""

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "thumbnail.png"
    local_path = f"/api/study/frame/{article_id}/thumbnail.png"
    if dest.exists() and dest.stat().st_size > 1000:
        return local_path

    # Derive unique colors from article_id hash
    h = int(hashlib.md5(article_id.encode()).hexdigest(), 16)
    hue1 = (h % 360)
    hue2 = (hue1 + 40 + (h >> 12) % 60) % 360

    def hsl_to_rgb(hue, sat, lum):
        r, g, b = colorsys.hls_to_rgb(hue / 360, lum, sat)
        return int(r * 255), int(g * 255), int(b * 255)

    c1 = hsl_to_rgb(hue1, 0.65, 0.18)
    c2 = hsl_to_rgb(hue2, 0.55, 0.30)

    W, H = 600, 340
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # Draw gradient
    for y in range(H):
        t = y / H
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Load fonts — prefer CJK-capable font, fallback to Helvetica
    def _load_font(size):
        for path in [
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
        ]:
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    font_sm = _load_font(16)
    font_md = _load_font(20)
    font_lg = _load_font(26)

    # Extract domain for platform label
    is_x = bool(re.search(r'x\.com|twitter\.com', url))
    platform = "X / TWITTER" if is_x else ""
    if not platform:
        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        platform = domain_match.group(1).upper() if domain_match else ""

    # Accent line
    accent = hsl_to_rgb(hue1, 0.85, 0.55)
    draw.rectangle([(30, 30), (90, 33)], fill=accent)

    # Platform label
    draw.text((30, 42), platform, fill=(255, 255, 255, 160), font=font_sm)

    # Title text — word-wrap to fit
    if title:
        # Clean title: remove "on X:" prefix patterns
        title_clean = re.sub(r'^.*?\s+on X:\s*["\u201c]?', '', title)
        title_clean = re.sub(r'["\u201d]?\s*/\s*X\s*$', '', title_clean)
        title_clean = title_clean.strip() or title

        # Word wrap — character-level for CJK, word-level for Latin
        lines = []
        current = ""
        max_w = W - 60
        for ch in title_clean:
            test = current + ch
            bbox = draw.textbbox((0, 0), test, font=font_lg)
            if bbox[2] - bbox[0] > max_w and current:
                lines.append(current)
                current = ch
            else:
                current = test
        if current:
            lines.append(current)

        # Limit to 5 lines
        if len(lines) > 5:
            lines = lines[:5]
            lines[-1] = lines[-1][:40] + "..."

        y_start = 75
        for i, line in enumerate(lines):
            alpha = 230 - i * 15
            draw.text((30, y_start + i * 36), line,
                       fill=(255, 255, 255, max(alpha, 140)), font=font_lg)

    # Article ID as subtle identifier at bottom-right
    draw.text((W - 130, H - 35), f"#{article_id}", fill=(255, 255, 255, 80), font=font_sm)

    img.save(str(dest), "PNG")
    print(f"  Generated placeholder thumbnail: {dest}")
    return local_path


def _capture_screenshot_local(url, article_id, title=""):
    """Capture a thumbnail for an article and save locally.
    For X/Twitter: uses fxtwitter OG image.
    For other sites: uses microlink.io screenshot API.
    Returns the local API path like /api/study/frame/{id}/thumbnail.png"""
    dest_dir = FRAMES_DIR / article_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "thumbnail.png"
    local_path = f"/api/study/frame/{article_id}/thumbnail.png"
    if dest.exists() and dest.stat().st_size > 1000:
        return local_path

    img_url = ""

    is_x = bool(re.search(r'x\.com|twitter\.com', url))

    # For X/Twitter, try fxtwitter media (microlink hits X's login wall)
    if is_x:
        img_url = _fetch_x_tweet_image(url)

    # For non-X sites, use microlink screenshot API
    if not img_url and not is_x:
        try:
            encoded = urllib.request.quote(url, safe="")
            api = f"https://api.microlink.io/?url={encoded}&screenshot=true&meta=false"
            req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            img_url = data.get("data", {}).get("screenshot", {}).get("url", "")
        except Exception as e:
            print(f"  Microlink screenshot failed: {e}")

    if img_url:
        try:
            urllib.request.urlretrieve(img_url, str(dest))
            print(f"  Thumbnail saved: {dest} ({dest.stat().st_size} bytes)")
            return local_path
        except Exception as e:
            print(f"  Thumbnail download failed: {e}")

    # Fallback: generate a unique gradient placeholder with title text
    return _generate_placeholder_thumbnail(article_id, url, dest_dir, title=title)


def extract_metadata(url, raw_html):
    """Extract title, author, cover from OG tags."""
    meta = {"title": "", "author": "", "cover": "", "site": ""}

    def og(prop):
        m = re.search(rf'<meta[^>]*property=["\']og:{prop}["\'][^>]*content=["\'](.*?)["\']', raw_html, re.I)
        if not m:
            m = re.search(rf'<meta[^>]*content=["\'](.*?)["\'][^>]*property=["\']og:{prop}["\']', raw_html, re.I)
        return m.group(1) if m else ""

    meta["title"] = og("title") or ""
    if not meta["title"]:
        m = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.I | re.S)
        if m:
            meta["title"] = re.sub(r"\s+", " ", m.group(1)).strip()

    meta["cover"] = og("image") or ""
    meta["site"] = og("site_name") or ""

    # Author from meta tags
    m = re.search(r'<meta[^>]*name=["\']author["\'][^>]*content=["\'](.*?)["\']', raw_html, re.I)
    if m:
        meta["author"] = m.group(1)
    if not meta["author"]:
        # Try JSON-LD
        m = re.search(r'"author"[^}]*"name"\s*:\s*"([^"]+)"', raw_html)
        if m:
            meta["author"] = m.group(1)

    # For X/Twitter: replace generic OG image with actual tweet media
    is_x = bool(re.search(r'x\.com|twitter\.com', url))
    if is_x and _is_generic_og_image(meta["cover"]):
        print(f"  X/Twitter detected with generic OG image, fetching real media...")
        real_img = _fetch_x_tweet_image(url)
        if real_img:
            meta["cover"] = real_img
            print(f"  Got tweet media: {real_img[:100]}")
        else:
            # Clear generic image so screenshot/placeholder fallback is used
            meta["cover"] = ""

    return meta


# ── Stage 2: Claude Analysis ────────────────────────────────────────────────

def analyze_with_claude(text, metadata, model="claude-sonnet-4-20250514"):
    """Send article text to Claude for structured analysis."""
    print(f"[3/4] Analyzing with Claude ({model})...")

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")

    # Truncate to stay within budget
    text = text[:25000]

    system_prompt = (
        "You are a study assistant analyzing a web article about AI/technology.\n\n"
        "Break the article into logical sections and for each section identify:\n"
        "1. The key concept being discussed\n"
        "2. Important details (data, examples, techniques mentioned)\n"
        "3. A concise summary\n\n"
        "Then provide an overall summary AND assign a category.\n\n"
        "Output as JSON with this exact structure:\n"
        "{\n"
        '  "category": "one of: AI Agents, RAG, Fine-tuning, LLM Infra, Prompt Engineering, '
        'AI Coding, AI Products, ML Research, AI News, General Tech, Other",\n'
        '  "sections": [\n'
        '    {"frame_index": null, "timestamp": null, "title": "Section title", '
        '"key_points": ["point 1", "point 2"], "screen_content": null}\n'
        "  ],\n"
        '  "summary": {\n'
        '    "title": "Descriptive title for this article analysis",\n'
        '    "takeaways": ["Main takeaway 1", "Main takeaway 2", ...],\n'
        '    "concepts": ["Key concept 1", "Key concept 2", ...],\n'
        '    "actionable": ["Action item 1", "Action item 2", ...]\n'
        "  }\n"
        "}\n\n"
        "Focus on practical, useful insights. "
        "If the article is in Chinese, still output the analysis in English."
    )

    body = {
        "model": model,
        "max_tokens": 4096,
        "temperature": 0.2,
        "system": system_prompt,
        "messages": [{
            "role": "user",
            "content": (
                f"Analyze this article: \"{metadata['title']}\" by {metadata['author'] or 'Unknown'}\n"
                f"Source: {metadata['site'] or 'Web'}\n\n"
                f"---\n\n{text}\n\n---\n\n"
                "Please provide your analysis as JSON."
            ),
        }],
    }

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))

    # Extract text
    text_out = ""
    for block in resp_data.get("content", []):
        if block.get("type") == "text":
            text_out += block["text"]

    # Parse JSON
    text_out = text_out.strip()
    if text_out.startswith("```"):
        text_out = re.sub(r"^```(?:json)?\s*", "", text_out)
        text_out = re.sub(r"\s*```$", "", text_out)

    analysis = json.loads(text_out)

    # Token usage
    usage = resp_data.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    model_pricing = {
        "claude-sonnet-4-20250514": (3.0, 15.0),
        "claude-opus-4-6": (15.0, 75.0),
        "claude-haiku-4-5-20251001": (0.80, 4.0),
    }
    in_rate, out_rate = model_pricing.get(model, (3.0, 15.0))
    cost = (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000
    token_info = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": round(cost, 4),
        "model": model,
    }
    print(f"  Got {len(analysis.get('sections', []))} sections from Claude")
    print(f"  Tokens: {input_tokens:,} in + {output_tokens:,} out = ${cost:.4f}")
    return analysis, token_info


# ── Stage 3: Persist ────────────────────────────────────────────────────────

def save_results(aid, url, metadata, article_text, analysis, token_info, model):
    """Save analysis results and update index."""
    print(f"[4/4] Saving results...")

    category = analysis.get("category", "Other")

    result = {
        "video_id": aid,
        "type": "article",
        "url": url,
        "title": metadata["title"],
        "channel": metadata["author"] or metadata["site"] or "",
        "duration": 0,
        "upload_date": "",
        "analyzed_at": datetime.now().isoformat(),
        "model_used": model,
        "category": category,
        "token_usage": token_info,
        "transcript_available": True,
        "transcript": [],
        "frames": [],
        "analysis": analysis,
        "article_text_length": len(article_text),
        "cover": metadata.get("cover", ""),
    }

    save_json(ANALYSES_DIR / f"{aid}.json", result)

    update_index(
        aid,
        type="article",
        url=url,
        title=metadata["title"],
        channel=metadata["author"] or metadata["site"] or "",
        duration=0,
        thumbnail=metadata.get("cover") or _capture_screenshot_local(url, aid, title=metadata.get("title", "")),
        status="done",
        completed_at=datetime.now().isoformat(),
        frame_count=0,
        section_count=len(analysis.get("sections", [])),
        category=category,
        token_usage=token_info,
        model_used=model,
        error=None,
    )

    print(f"  Saved to data/study_analyses/{aid}.json")


# ── Main Pipeline ────────────────────────────────────────────────────────────

def analyze_article(url, model="claude-sonnet-4-20250514"):
    """Full article analysis pipeline."""
    aid = article_id_from_url(url)

    print(f"\n{'='*60}")
    print(f"Analyzing article: {url}")
    print(f"Article ID: {aid}")
    print(f"Model:      {model}")
    print(f"{'='*60}\n")

    # Capture screenshot early for the card thumbnail (skip for X — needs title for placeholder)
    is_x_url = bool(re.search(r'x\.com|twitter\.com', url))
    screenshot_thumb = "" if is_x_url else _capture_screenshot_local(url, aid)
    update_index(aid, type="article", url=url, status="processing",
                 started_at=datetime.now().isoformat(),
                 thumbnail=screenshot_thumb)

    try:
        # Stage 1: Fetch — try multiple methods in order
        print(f"[1/4] Fetching article content...")
        text = None
        metadata = None
        raw_html = None

        # Method 1: Puppeteer (best for Medium and paywalled sites)
        puppeteer_text, puppeteer_meta = fetch_via_puppeteer(url)
        if puppeteer_text and len(puppeteer_text) > 200:
            text = puppeteer_text
            metadata = puppeteer_meta
            print(f"  Got content via Puppeteer ({len(text)} chars)")

        # Method 2: Jina Reader
        if not text:
            print(f"  Puppeteer failed, trying Jina Reader...")
            jina_text, jina_meta_html = fetch_via_jina(url)
            if jina_text and len(jina_text) > 200:
                text = jina_text
                metadata = extract_metadata(url, jina_meta_html)
                print(f"  Got content via Jina Reader ({len(text)} chars)")

        # Method 3: Direct HTTP (last resort)
        if not text:
            print(f"  Jina Reader failed, trying direct HTTP...")
            try:
                raw_html = fetch_via_http(url)
                if raw_html and len(raw_html) > 100:
                    metadata = extract_metadata(url, raw_html)
                    text = extract_text_from_html(raw_html)
                    if _is_bot_blocked(text):
                        text = None
                    else:
                        print(f"  Got content via HTTP ({len(text)} chars)")
            except Exception as e:
                print(f"  HTTP failed: {e}")

        if not text:
            raise RuntimeError("All fetch methods failed. For Medium, try: node study/fetch_medium.mjs --setup")

        # Check for error pages (404, etc.) in fetched content
        if _is_error_page(text):
            raise RuntimeError("URL returned an error page (404/not found). Skipping analysis.")

        # Stage 2: Extract
        print(f"[2/4] Extracting metadata...")

        # For X/Twitter: filter out generic OG images (profile pics, default cards)
        # regardless of which fetch method provided the metadata
        is_x = bool(re.search(r'x\.com|twitter\.com', url))
        if is_x and _is_generic_og_image(metadata.get("cover", "")):
            print(f"  X/Twitter generic cover detected, trying fxtwitter...")
            real_img = _fetch_x_tweet_image(url)
            if real_img:
                metadata["cover"] = real_img
                print(f"  Got tweet media: {real_img[:100]}")
            else:
                metadata["cover"] = ""
                print(f"  No tweet media found, will use screenshot/placeholder")

        print(f"  Title: {metadata['title'][:80]}")
        print(f"  Author: {metadata['author'] or 'Unknown'}")
        print(f"  Text length: {len(text)} chars")

        update_index(aid, title=metadata["title"],
                     channel=metadata["author"] or metadata["site"] or "",
                     thumbnail=metadata.get("cover") or screenshot_thumb)

        # Stage 3: Analyze
        analysis, token_info = analyze_with_claude(text, metadata, model)

        # Post-analysis check: reject if Claude analyzed an error page
        if _is_error_analysis(analysis):
            raise RuntimeError("Content appears to be an error page (404/not found). Skipping.")

        # Stage 4: Save
        save_results(aid, url, metadata, text, analysis, token_info, model)

        print(f"\nDone! {len(analysis.get('sections', []))} sections analyzed.")
        return {"ok": True, "video_id": aid}

    except Exception as e:
        error_msg = str(e)[:500]
        print(f"\nError: {error_msg}", file=sys.stderr)
        update_index(aid, status="error", error=error_msg)
        return {"ok": False, "video_id": aid, "error": error_msg}


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a web article")
    parser.add_argument("url", help="Article URL")
    parser.add_argument("--model", default="claude-sonnet-4-20250514")
    args = parser.parse_args()

    result = analyze_article(args.url, args.model)
    if not result["ok"]:
        sys.exit(1)
