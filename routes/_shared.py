"""Shared constants and utility functions used by all blueprint modules."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

log = logging.getLogger("mega")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- Data file paths ---
RECS_FILE = DATA_DIR / "daily_recommendations.json"
FEEDBACK_FILE = DATA_DIR / "feedback.json"
PROFILE_FILE = DATA_DIR / "profile.json"

KNOWLEDGE_FEED_FILE = DATA_DIR / "knowledge_feed.json"
X_FEED_CACHE_FILE = DATA_DIR / "x_feed_cache.json"
MEDIUM_FORYOU_CACHE_FILE = DATA_DIR / "medium_for_you_cache.json"
KNOWLEDGE_SAVED_FILE = DATA_DIR / "knowledge_saved.json"

TV_CATALOG_FILE = DATA_DIR / "tv_catalog.json"
TV_FEEDBACK_FILE = DATA_DIR / "tv_feedback.json"
MOVIES_CATALOG_FILE = DATA_DIR / "movies_catalog.json"
MOVIES_FEEDBACK_FILE = DATA_DIR / "movies_feedback.json"
USAGE_FILE = DATA_DIR / "usage_tracking.json"
TMDB_CACHE_FILE = DATA_DIR / "tmdb_cache.json"
TMDB_MOVIE_CACHE_FILE = DATA_DIR / "tmdb_movie_cache.json"
TV_EMBED_FILE = DATA_DIR / "tv_embeddings.json"
TV_TMDB_META_FILE = DATA_DIR / "tv_tmdb_meta.json"
MOVIES_EMBED_FILE = DATA_DIR / "movies_embeddings.json"
MOVIES_TMDB_META_FILE = DATA_DIR / "movies_tmdb_meta.json"
COMING_SOON_CACHE_FILE = DATA_DIR / "coming_soon_cache.json"
CONTINUE_TRACK_FILE = DATA_DIR / "continue_tracking.json"

KNOWLEDGE_TREE_FILE = DATA_DIR / "knowledge_tree.json"
KNOWLEDGE_REVIEWS_FILE = DATA_DIR / "knowledge_reviews.json"
HUNTER_PROFILE_FILE = DATA_DIR / "hunter_profile.json"
TECH_TREE_TEMPLATE_FILE = DATA_DIR / "tech_tree_template.json"

FINANCE_CATEGORY_COLORS_FILE = ROOT / "apps" / "finance" / "data" / "category_colors.json"
FINANCE_CATEGORY_RULES_FILE = ROOT / "apps" / "finance" / "data" / "category_rules.json"
FINANCE_CATEGORY_META_FILE = ROOT / "apps" / "finance" / "data" / "category_meta.json"


# --- Shared utilities ---

def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text("utf-8"))
    except Exception:
        return default
    return default


# --- Embeddings cache (shared by movies.py and tv.py) ---
# Avoids re-parsing large JSON files (315 MB movies, 58 MB TV) on every request.
# Keyed by file path; uses os.path.getmtime() for invalidation.
# Write order invariant: _embed_cache[key] is set BEFORE _embed_mtime[key]
# so fast-path readers under CPython's GIL see either (old, old) or (new, new).
_embed_cache: dict[str, dict | None] = {}
_embed_mtime: dict[str, float] = {}
_embed_lock = threading.Lock()


def load_embeddings(path: Any) -> dict | None:
    """Load embedding vectors from a JSON file with mtime-based caching."""
    key = str(path)
    try:
        mtime = os.path.getmtime(key)
    except OSError:
        return None
    cached_mtime = _embed_mtime.get(key)
    if cached_mtime is not None and cached_mtime == mtime and key in _embed_cache:
        return _embed_cache[key]
    with _embed_lock:
        if _embed_mtime.get(key) == mtime and key in _embed_cache:
            return _embed_cache[key]
        try:
            data = load_json(path, {})
            vectors = data.get("vectors") if isinstance(data, dict) else None
            if not isinstance(vectors, dict) or not vectors:
                _embed_cache[key] = None
                _embed_mtime[key] = mtime
                return None
            _embed_cache[key] = vectors
            _embed_mtime[key] = mtime
            return vectors
        except Exception:
            return None


# --- Generic JSON cache (for medium-size files: catalogs, tmdb_meta, feedback) ---
# Same pattern as embeddings but returns the full parsed object.
_json_cache: dict[str, Any] = {}
_json_mtime: dict[str, float] = {}
_json_lock = threading.Lock()


def load_json_cached(path: Path, default: Any = None) -> Any:
    """Load a JSON file with mtime-based caching. Thread-safe."""
    key = str(path)
    try:
        mtime = os.path.getmtime(key)
    except OSError:
        return default
    cached_mtime = _json_mtime.get(key)
    if cached_mtime is not None and cached_mtime == mtime and key in _json_cache:
        return _json_cache[key]
    with _json_lock:
        if _json_mtime.get(key) == mtime and key in _json_cache:
            return _json_cache[key]
        data = load_json(path, default)
        _json_cache[key] = data
        _json_mtime[key] = mtime
        return data


def invalidate_json_cache(path: Path) -> None:
    """Drop a file from the JSON cache (call after save_json on that path)."""
    key = str(path)
    with _json_lock:
        _json_cache.pop(key, None)
        _json_mtime.pop(key, None)


def evict_stale_cache(cache: dict, max_age_sec: int = 30 * 86400) -> dict:
    """Remove entries older than max_age_sec from a TMDB-style cache dict.

    Entries must have a 'fetchedAt' epoch timestamp. Returns the pruned dict.
    """
    import time as _time

    cutoff = int(_time.time()) - max_age_sec
    return {
        k: v for k, v in cache.items()
        if isinstance(v, dict) and int(v.get("fetchedAt", 0) or 0) >= cutoff
    }


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".tmp.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except Exception:
            pass


@contextmanager
def atomic_write(path: Path, mode: str = "w", encoding: str = "utf-8", newline: str | None = None):
    """Write to a temp file, then atomically replace the target.

    Use for CSV or other non-JSON writes that can't use save_json().
    Pass newline="" for CSV files (required by the csv module).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".tmp.", dir=str(path.parent))
    try:
        kw: dict = {"mode": mode}
        if "b" not in mode:
            kw["encoding"] = encoding
            kw["newline"] = newline
        with os.fdopen(fd, **kw) as f:
            yield f
        os.replace(tmp_name, path)
    except BaseException:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except Exception:
            pass
        raise


def make_meta(generated_at: str | float | None, stale_after_hours: float) -> dict:
    """Build a _meta envelope with age and staleness flag."""
    from datetime import datetime as _dt

    if generated_at is None:
        return {"generated_at": None, "age_hours": None, "stale": True}
    try:
        if isinstance(generated_at, (int, float)):
            gen_dt = _dt.fromtimestamp(generated_at)
        else:
            gen_dt = _dt.fromisoformat(str(generated_at).replace("Z", ""))
        age_sec = (_dt.now() - gen_dt).total_seconds()
        age_h = round(max(age_sec, 0) / 3600, 1)
        return {
            "generated_at": gen_dt.isoformat(),
            "age_hours": age_h,
            "stale": age_h > stale_after_hours,
        }
    except Exception:
        return {"generated_at": str(generated_at), "age_hours": None, "stale": True}
