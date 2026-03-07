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

log = logging.getLogger("solo-leveling")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- Data file paths ---
KNOWLEDGE_FEED_FILE = DATA_DIR / "knowledge_feed.json"
X_FEED_CACHE_FILE = DATA_DIR / "x_feed_cache.json"
MEDIUM_FORYOU_CACHE_FILE = DATA_DIR / "medium_for_you_cache.json"
KNOWLEDGE_SAVED_FILE = DATA_DIR / "knowledge_saved.json"

KNOWLEDGE_TREE_FILE = DATA_DIR / "knowledge_tree.json"
KNOWLEDGE_REVIEWS_FILE = DATA_DIR / "knowledge_reviews.json"
HUNTER_PROFILE_FILE = DATA_DIR / "hunter_profile.json"
TECH_TREE_TEMPLATE_FILE = DATA_DIR / "tech_tree_template.json"


# --- Shared utilities ---

def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text("utf-8"))
    except Exception:
        return default
    return default


# --- Generic JSON cache (for medium-size files) ---
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
    """Write to a temp file, then atomically replace the target."""
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
