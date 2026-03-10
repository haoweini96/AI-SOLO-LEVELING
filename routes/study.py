"""Study (YouTube Video Analysis) routes.

Blueprint: study_bp
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime

from flask import Blueprint, Response, jsonify, request, send_from_directory

from routes._shared import DATA_DIR, KNOWLEDGE_TREE_FILE, ROOT, load_json, log, save_json

study_bp = Blueprint("study", __name__)

# --- File paths ---
STUDY_VIDEOS_FILE = DATA_DIR / "study_videos.json"
STUDY_ANALYSES_DIR = DATA_DIR / "study_analyses"
STUDY_FRAMES_DIR = DATA_DIR / "study_frames"
STUDY_HIGHLIGHTS_FILE = DATA_DIR / "study_highlights.json"


# --- Helper ---

def _is_youtube_url(url: str) -> bool:
    return bool(re.search(
        r"(?:youtube\.com/(?:watch\?.*v=|embed/|shorts/|live/)|youtu\.be/)([a-zA-Z0-9_-]{11})", url
    ))


# --- Routes ---

@study_bp.route("/api/study/videos")
def api_study_videos():
    data = load_json(STUDY_VIDEOS_FILE, {"videos": []})
    return jsonify(data)


@study_bp.route("/api/study/analyze", methods=["POST"])
def api_study_analyze():
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url") or "").strip()
    force = payload.get("force", False)

    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "invalid_url"}), 400

    is_yt = _is_youtube_url(url)

    if is_yt:
        yt_match = re.search(
            r"(?:youtube\.com/(?:watch\?.*v=|embed/|shorts/|live/)|youtu\.be/)([a-zA-Z0-9_-]{11})", url
        )
        item_id = yt_match.group(1)
        script = ROOT / "apps" / "study" / "analyze_video.py"
        thumb = f"https://i.ytimg.com/vi/{item_id}/hqdefault.jpg"
        item_type = "video"
    else:
        import hashlib as _hl
        item_id = _hl.md5(url.encode()).hexdigest()[:12]
        script = ROOT / "apps" / "study" / "analyze_article.py"
        thumb = f"https://image.thum.io/get/width/600/noanimate/{url}"
        item_type = "article"

    data = load_json(STUDY_VIDEOS_FILE, {"videos": []})
    existing = [v for v in data["videos"] if v["video_id"] == item_id]
    if existing and existing[0].get("status") == "done" and not force:
        return jsonify({"ok": True, "video_id": item_id, "status": "already_done"})
    if existing and existing[0].get("status") == "processing":
        return jsonify({"ok": True, "video_id": item_id, "status": "processing"})

    # Mark as processing
    entry = {
        "video_id": item_id,
        "type": item_type,
        "url": url,
        "status": "processing",
        "started_at": datetime.now().isoformat(),
        "title": "",
        "channel": "",
        "thumbnail": thumb,
    }
    data["videos"] = [v for v in data["videos"] if v["video_id"] != item_id]
    data["videos"].insert(0, entry)
    save_json(STUDY_VIDEOS_FILE, data)

    subprocess.Popen(
        [sys.executable, str(script), url],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return jsonify({"ok": True, "video_id": item_id, "status": "processing", "type": item_type})


def _sync_to_knowledge_tree(item: dict, analysis: dict):
    """Auto-sync a completed study item to Knowledge Tree (tech tree). Safe to call multiple times (dedup)."""
    try:
        from routes.knowledge_tree import (
            _add_source_and_classify,
            _award_xp,
            _generate_node_summary,
            _id_lock,
            _load_template,
            _load_tree,
            _now_iso,
            _save_tree,
            _study_item_to_source,
        )

        tree_data = _load_tree()
        study_item_id = item.get("video_id") or analysis.get("video_id")

        # Dedup: check if already imported
        already = any(
            s.get("study_item_id") == study_item_id
            for s in tree_data.get("sources", [])
        )
        if already:
            return

        source_data = _study_item_to_source(item, analysis)
        template = _load_template()

        with _id_lock:
            tree_data = _load_tree()
            source, node_ids, any_newly_lit = _add_source_and_classify(source_data, tree_data, template)

            # Regenerate summaries for all affected nodes (incorporates new source)
            for nid in node_ids:
                node = tree_data.get("nodes", {}).get(nid)
                if node and node.get("status") not in (None, "locked"):
                    result = _generate_node_summary(nid, tree_data)
                    if result:
                        node["summary"] = result.get("summary", "")
                        node["key_takeaways"] = result.get("key_takeaways", [])
                        node["updated_at"] = _now_iso()

            _save_tree(tree_data)

        # Award XP
        xp = 30  # source XP
        if any_newly_lit:
            xp += 100  # first light bonus
        _award_xp(xp, f"study sync: {study_item_id}")

        log.info("Auto-synced study item %s to tech tree → nodes %s", study_item_id, node_ids)
    except Exception as e:
        log.warning("Failed to sync study item to knowledge tree: %s", e)


@study_bp.route("/api/study/status/<video_id>")
def api_study_status(video_id: str):
    data = load_json(STUDY_VIDEOS_FILE, {"videos": []})
    match = [v for v in data["videos"] if v["video_id"] == video_id]
    if not match:
        return jsonify({"ok": False, "error": "not_found"}), 404

    item = match[0]
    # Auto-sync to Knowledge Tree when analysis completes
    if item.get("status") == "done":
        analysis_path = STUDY_ANALYSES_DIR / f"{video_id}.json"
        if analysis_path.exists():
            try:
                analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
                _sync_to_knowledge_tree(item, analysis)
            except Exception:
                pass

    return jsonify({"ok": True, **item})


@study_bp.route("/api/study/analysis/<video_id>")
def api_study_analysis(video_id: str):
    path = STUDY_ANALYSES_DIR / f"{video_id}.json"
    if not path.exists():
        return jsonify({"ok": False, "error": "not_found"}), 404

    # Belt-and-suspenders: sync to Knowledge Tree when analysis is loaded
    data = load_json(STUDY_VIDEOS_FILE, {"videos": []})
    item = next((v for v in data["videos"] if v["video_id"] == video_id and v.get("status") == "done"), None)
    if item:
        try:
            analysis = json.loads(path.read_text(encoding="utf-8"))
            _sync_to_knowledge_tree(item, analysis)
        except Exception:
            pass

    return Response(path.read_text(encoding="utf-8"), mimetype="application/json")


@study_bp.route("/api/study/frame/<video_id>/<filename>")
def api_study_frame(video_id: str, filename: str):
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", video_id)
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "", filename)
    frames_dir = STUDY_FRAMES_DIR / safe_id
    if not (frames_dir / safe_name).exists():
        return ("not found", 404)
    return send_from_directory(str(frames_dir), safe_name)


@study_bp.route("/api/study/delete", methods=["POST"])
def api_study_delete():
    payload = request.get_json(silent=True) or {}
    video_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(payload.get("video_id") or ""))
    if not video_id:
        return jsonify({"ok": False, "error": "missing video_id"}), 400

    data = load_json(STUDY_VIDEOS_FILE, {"videos": []})
    data["videos"] = [v for v in data["videos"] if v["video_id"] != video_id]
    save_json(STUDY_VIDEOS_FILE, data)

    analysis_path = STUDY_ANALYSES_DIR / f"{video_id}.json"
    if analysis_path.exists():
        analysis_path.unlink()
    frames_dir = STUDY_FRAMES_DIR / video_id
    if frames_dir.exists():
        import shutil
        shutil.rmtree(frames_dir, ignore_errors=True)

    return jsonify({"ok": True})


@study_bp.route("/api/study/translate", methods=["POST"])
def api_study_translate():
    """Translate analysis to Chinese via Claude."""
    import urllib.request as urlreq

    payload = request.get_json(silent=True) or {}
    video_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(payload.get("video_id") or ""))
    if not video_id:
        return jsonify({"ok": False, "error": "missing video_id"}), 400

    path = STUDY_ANALYSES_DIR / f"{video_id}.json"
    if not path.exists():
        return jsonify({"ok": False, "error": "not_found"}), 404

    data = json.loads(path.read_text("utf-8"))
    if data.get("analysis_zh"):
        return jsonify({"ok": True, "analysis_zh": data["analysis_zh"]})

    analysis = data.get("analysis", {})
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"ok": False, "error": "no api key"}), 500

    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "temperature": 0.2,
        "system": (
            "Translate the following JSON video analysis into Chinese (简体中文). "
            "Keep the JSON structure and keys in English, only translate the values. "
            "Keep technical terms (like RAG, LLM, API, etc.) in English. "
            "Output valid JSON only."
        ),
        "messages": [{"role": "user", "content": json.dumps(analysis, ensure_ascii=False)}],
    }

    req = urlreq.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urlreq.urlopen(req, timeout=120) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
        text = ""
        for block in resp_data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        analysis_zh = json.loads(text)

        # Track translation tokens
        usage = resp_data.get("usage", {})
        translate_tokens = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": round(
                (usage.get("input_tokens", 0) * 3.0 + usage.get("output_tokens", 0) * 15.0)
                / 1_000_000, 4
            ),
        }

        # Save back
        data["analysis_zh"] = analysis_zh
        # Add translation cost to existing token usage
        if data.get("token_usage"):
            data["token_usage"]["translate_tokens"] = translate_tokens
            data["token_usage"]["cost_usd"] = round(
                data["token_usage"].get("cost_usd", 0) + translate_tokens["cost_usd"], 4
            )
        save_json(path, data)
        return jsonify({"ok": True, "analysis_zh": analysis_zh, "translate_tokens": translate_tokens})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 500


@study_bp.route("/api/study/category", methods=["POST"])
def api_study_category():
    """Update video category."""
    payload = request.get_json(silent=True) or {}
    video_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(payload.get("video_id") or ""))
    category = str(payload.get("category") or "").strip()
    if not video_id or not category:
        return jsonify({"ok": False, "error": "missing video_id or category"}), 400

    # Update analysis file
    path = STUDY_ANALYSES_DIR / f"{video_id}.json"
    if path.exists():
        data = json.loads(path.read_text("utf-8"))
        data["category"] = category
        if data.get("analysis"):
            data["analysis"]["category"] = category
        save_json(path, data)

    # Update index
    idx = load_json(STUDY_VIDEOS_FILE, {"videos": []})
    for v in idx["videos"]:
        if v["video_id"] == video_id:
            v["category"] = category
            break
    save_json(STUDY_VIDEOS_FILE, idx)
    return jsonify({"ok": True})


@study_bp.route("/api/study/highlights", methods=["GET"])
def api_study_highlights_get():
    """Return all highlights, optionally filtered by article_id."""
    article_id = request.args.get("article_id", "").strip()
    data = load_json(STUDY_HIGHLIGHTS_FILE, {"highlights": []})
    highlights = data.get("highlights") or []
    if article_id:
        highlights = [h for h in highlights if h.get("article_id") == article_id]
    return jsonify({"highlights": highlights})


@study_bp.route("/api/study/highlights", methods=["POST"])
def api_study_highlights_post():
    """Add a new highlight."""
    import uuid as _uuid

    payload = request.get_json(silent=True) or {}
    article_id = str(payload.get("article_id") or "").strip()
    text = str(payload.get("text") or "").strip()
    color = str(payload.get("color") or "yellow").strip()
    note = str(payload.get("note") or "").strip()
    if not article_id or not text:
        return jsonify({"ok": False, "error": "missing article_id or text"}), 400

    highlight = {
        "id": str(_uuid.uuid4()),
        "article_id": article_id,
        "text": text,
        "color": color,
        "note": note,
        "added_at": datetime.now().isoformat(),
    }
    data = load_json(STUDY_HIGHLIGHTS_FILE, {"highlights": []})
    data.setdefault("highlights", []).append(highlight)
    save_json(STUDY_HIGHLIGHTS_FILE, data)
    return jsonify({"ok": True, "highlight": highlight})


@study_bp.route("/api/study/highlights/<highlight_id>", methods=["DELETE"])
def api_study_highlights_delete(highlight_id: str):
    """Delete a highlight by ID."""
    data = load_json(STUDY_HIGHLIGHTS_FILE, {"highlights": []})
    before = len(data.get("highlights") or [])
    data["highlights"] = [h for h in (data.get("highlights") or []) if h.get("id") != highlight_id]
    if len(data["highlights"]) < before:
        save_json(STUDY_HIGHLIGHTS_FILE, data)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not found"}), 404


@study_bp.route("/api/study/highlights/<highlight_id>", methods=["PATCH"])
def api_study_highlights_patch(highlight_id: str):
    """Update a highlight's note."""
    payload = request.get_json(silent=True) or {}
    data = load_json(STUDY_HIGHLIGHTS_FILE, {"highlights": []})
    for h in (data.get("highlights") or []):
        if h.get("id") == highlight_id:
            if "note" in payload:
                h["note"] = str(payload["note"]).strip()
            if "color" in payload:
                h["color"] = str(payload["color"]).strip()
            save_json(STUDY_HIGHLIGHTS_FILE, data)
            return jsonify({"ok": True, "highlight": h})
    return jsonify({"ok": False, "error": "not found"}), 404
