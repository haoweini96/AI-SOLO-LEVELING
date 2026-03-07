#!/usr/bin/env python3
"""
YouTube Video Study Analyzer
Extracts keyframes + transcript from YouTube videos, sends to Claude for multimodal analysis.

Usage:
    python3 analyze_video.py "https://www.youtube.com/watch?v=VIDEO_ID"
    python3 analyze_video.py "https://www.youtube.com/watch?v=VIDEO_ID" --model claude-sonnet-4-20250514 --max-frames 20
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent  # projects/mega/
DATA = ROOT / "data"
VIDEOS_INDEX = DATA / "study_videos.json"
ANALYSES_DIR = DATA / "study_analyses"
FRAMES_DIR = DATA / "study_frames"

# Ensure dirs exist
ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

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


def extract_video_id(url):
    """Extract YouTube video ID from various URL formats."""
    m = re.search(
        r'(?:youtube\.com/(?:watch\?.*v=|embed/|shorts/|live/)|youtu\.be/)([a-zA-Z0-9_-]{11})',
        url,
    )
    return m.group(1) if m else None


def format_ts(seconds):
    """Format seconds as H:MM:SS or M:SS."""
    s = int(seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def update_index(video_id, **fields):
    """Update a video entry in the index file."""
    data = load_json(VIDEOS_INDEX, {"videos": []})
    found = False
    for v in data["videos"]:
        if v["video_id"] == video_id:
            v.update(fields)
            found = True
            break
    if not found:
        entry = {"video_id": video_id, **fields}
        data["videos"].insert(0, entry)
    save_json(VIDEOS_INDEX, data)


# ── Stage 1: Metadata ───────────────────────────────────────────────────────

def get_metadata(url, video_id):
    """Get video metadata via yt-dlp."""
    print(f"[1/5] Fetching metadata for {video_id}...")
    result = subprocess.run(
        ["yt-dlp", "--no-download", "-j", url],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {result.stderr[:500]}")

    info = json.loads(result.stdout)
    return {
        "title": info.get("title", "Unknown"),
        "channel": info.get("channel") or info.get("uploader", "Unknown"),
        "duration": info.get("duration", 0),
        "thumbnail": info.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "upload_date": info.get("upload_date", ""),
    }


# ── Stage 2: Transcript ─────────────────────────────────────────────────────

def get_transcript(video_id):
    """Get transcript with timestamps. Returns list of {text, start, duration}."""
    print(f"[2/5] Extracting transcript...")

    # Try youtube-transcript-api first
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=["en", "zh-Hans", "zh-Hant", "zh", "ja"])
        segments = []
        for snippet in transcript.snippets:
            segments.append({
                "text": snippet.text,
                "start": snippet.start,
                "duration": snippet.duration,
            })
        print(f"  Got {len(segments)} transcript segments")
        return segments
    except Exception as e:
        print(f"  youtube-transcript-api failed: {e}")

    # Fallback: yt-dlp auto-subs
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [
                    "yt-dlp", "--skip-download",
                    "--write-auto-sub", "--sub-lang", "en",
                    "--sub-format", "json3",
                    "-o", f"{tmpdir}/subs",
                    f"https://www.youtube.com/watch?v={video_id}",
                ],
                capture_output=True, timeout=60,
            )
            sub_file = Path(tmpdir) / "subs.en.json3"
            if sub_file.exists():
                sub_data = json.loads(sub_file.read_text())
                events = sub_data.get("events", [])
                segments = []
                for ev in events:
                    segs = ev.get("segs", [])
                    text = "".join(s.get("utf8", "") for s in segs).strip()
                    if text and text != "\n":
                        segments.append({
                            "text": text,
                            "start": ev.get("tStartMs", 0) / 1000.0,
                            "duration": ev.get("dDurationMs", 0) / 1000.0,
                        })
                if segments:
                    print(f"  Got {len(segments)} transcript segments (yt-dlp fallback)")
                    return segments
    except Exception as e:
        print(f"  yt-dlp subtitle fallback failed: {e}")

    print("  No transcript available — will do visual-only analysis")
    return []


# ── Stage 3: Keyframe Extraction ────────────────────────────────────────────

def download_video(url, video_id):
    """Download video to a temp file via yt-dlp. Returns path to downloaded file."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="study_"))
    output_template = str(tmp_dir / f"{video_id}.%(ext)s")
    result = subprocess.run(
        [
            "yt-dlp",
            "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "--merge-output-format", "mp4",
            "-o", output_template,
            url,
        ],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp download failed: {result.stderr[:500]}")

    # Find the downloaded file
    files = list(tmp_dir.glob(f"{video_id}.*"))
    if not files:
        raise RuntimeError("yt-dlp produced no output file")
    print(f"  Downloaded: {files[0].name} ({files[0].stat().st_size // 1024 // 1024}MB)")
    return files[0], tmp_dir


def extract_keyframes(url, video_id, max_frames=20, scene_threshold=0.3):
    """
    Hybrid keyframe extraction:
    1. Download video locally via yt-dlp
    2. Scene-change detection (ffmpeg select filter)
    3. If < 5 frames → fallback to fixed 30s interval
    Returns list of (filepath, timestamp_seconds, method)
    """
    print(f"[3/5] Downloading video & extracting keyframes...")
    frames_dir = FRAMES_DIR / video_id
    frames_dir.mkdir(parents=True, exist_ok=True)

    video_path, tmp_dir = download_video(url, video_id)

    try:
        # ── Scene-change detection ───────────────────────────────────────
        frames = _extract_scene_change(str(video_path), frames_dir, max_frames, scene_threshold)

        if len(frames) >= 5:
            print(f"  Scene detection: {len(frames)} keyframes")
            return frames

        print(f"  Scene detection got only {len(frames)} frames, falling back to interval...")
        for f, _, _ in frames:
            Path(f).unlink(missing_ok=True)

        # ── Fixed interval fallback ──────────────────────────────────────
        frames = _extract_interval(str(video_path), frames_dir, max_frames)
        print(f"  Interval extraction: {len(frames)} keyframes")
        return frames
    finally:
        # Clean up downloaded video
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _extract_scene_change(video_path, output_dir, max_frames, threshold):
    """Extract frames at scene changes using ffmpeg on a local file."""
    pattern = str(output_dir / "scene_%04d.jpg")
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"select='gt(scene,{threshold})',showinfo,scale='min(1280,iw)':-1",
            "-vsync", "vfr",
            "-q:v", "2",
            "-frames:v", str(max_frames),
            pattern,
        ],
        capture_output=True, text=True, timeout=600,
    )

    # Parse timestamps from showinfo output in stderr
    timestamps = []
    for line in result.stderr.split("\n"):
        m = re.search(r"pts_time:\s*([0-9.]+)", line)
        if m:
            timestamps.append(float(m.group(1)))

    frames = []
    for i, ts in enumerate(timestamps[:max_frames]):
        fpath = output_dir / f"scene_{i+1:04d}.jpg"
        if fpath.exists():
            final = output_dir / f"frame_{len(frames)+1:03d}.jpg"
            fpath.rename(final)
            frames.append((str(final), ts, "scene_change"))
    return frames


def _extract_interval(video_path, output_dir, max_frames):
    """Extract frames at fixed intervals from a local file."""
    # Get duration
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, timeout=30,
    )
    duration = float(probe.stdout.strip()) if probe.returncode == 0 else 600
    interval = max(30, duration / max_frames)

    pattern = str(output_dir / "interval_%04d.jpg")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps=1/{interval},scale='min(1280,iw)':-1",
            "-q:v", "2",
            "-frames:v", str(max_frames),
            pattern,
        ],
        capture_output=True, timeout=600,
    )

    frames = []
    for i in range(1, max_frames + 1):
        fpath = output_dir / f"interval_{i:04d}.jpg"
        if fpath.exists():
            final = output_dir / f"frame_{len(frames)+1:03d}.jpg"
            fpath.rename(final)
            ts = (i - 1) * interval
            frames.append((str(final), ts, "interval"))
    return frames


# ── Stage 4: Claude Multimodal Analysis ─────────────────────────────────────

def pair_frames_with_transcript(frames, transcript):
    """Group transcript segments with their nearest keyframe."""
    if not transcript:
        return [{"frame_path": f, "timestamp": ts, "transcript_text": ""} for f, ts, _ in frames]

    groups = []
    for i, (fpath, fts, _) in enumerate(frames):
        next_ts = frames[i + 1][1] if i + 1 < len(frames) else float("inf")
        text_parts = []
        for seg in transcript:
            seg_mid = seg["start"] + seg["duration"] / 2
            if fts - 5 <= seg_mid < next_ts:
                text_parts.append(seg["text"])
        groups.append({
            "frame_path": fpath,
            "timestamp": fts,
            "transcript_text": " ".join(text_parts),
        })
    return groups


def analyze_with_claude(frames, transcript, metadata, model="claude-sonnet-4-20250514"):
    """Send keyframes + transcript to Claude for multimodal analysis."""
    print(f"[4/5] Analyzing with Claude ({model})...")

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")

    groups = pair_frames_with_transcript(frames, transcript)

    # Build interleaved content
    content = [
        {"type": "text", "text": (
            f"Analyze this YouTube video: \"{metadata['title']}\" by {metadata['channel']} "
            f"(duration: {format_ts(metadata['duration'])})\n\n"
            "I've extracted keyframes and their corresponding transcript segments. "
            "Analyze each section and provide an overall summary.\n\n"
            "---\n"
        )},
    ]

    for group in groups:
        # Add image
        with open(group["frame_path"], "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64},
        })
        # Add transcript
        ts_str = format_ts(group["timestamp"])
        if group["transcript_text"]:
            content.append({
                "type": "text",
                "text": f"[{ts_str}] Transcript: {group['transcript_text'][:2000]}",
            })
        else:
            content.append({
                "type": "text",
                "text": f"[{ts_str}] (no transcript for this segment)",
            })

    content.append({
        "type": "text",
        "text": "\nPlease provide your analysis as JSON.",
    })

    system_prompt = (
        "You are a study assistant analyzing a YouTube video about AI/technology. "
        "You receive keyframes (screenshots) paired with transcript segments.\n\n"
        "For each keyframe section, identify:\n"
        "1. The key concept being discussed\n"
        "2. Important details visible on screen (diagrams, code, architecture, formulas, slides)\n"
        "3. A concise summary of that section\n\n"
        "Then provide an overall summary AND assign a category.\n\n"
        "Output as JSON with this exact structure:\n"
        "{\n"
        '  "category": "one of: AI Agents, RAG, Fine-tuning, LLM Infra, Prompt Engineering, '
        'AI Coding, AI Products, ML Research, AI News, General Tech, Other",\n'
        '  "sections": [\n'
        '    {"frame_index": 0, "timestamp": "0:15", "title": "Section title", '
        '"key_points": ["point 1", "point 2"], "screen_content": "Description of what is shown on screen"}\n'
        "  ],\n"
        '  "summary": {\n'
        '    "title": "Descriptive title for this video analysis",\n'
        '    "takeaways": ["Main takeaway 1", "Main takeaway 2", ...],\n'
        '    "concepts": ["Key concept 1", "Key concept 2", ...],\n'
        '    "actionable": ["Action item 1", "Action item 2", ...]\n'
        "  }\n"
        "}\n\n"
        "Be specific about what you see in the images. If a diagram or code is shown, describe it. "
        "Focus on practical, useful insights. "
        "If the video is in Chinese, still output the analysis in English."
    )

    body = {
        "model": model,
        "max_tokens": 4096,
        "temperature": 0.2,
        "system": system_prompt,
        "messages": [{"role": "user", "content": content}],
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

    with urllib.request.urlopen(req, timeout=300) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))

    # Extract text from response
    text = ""
    for block in resp_data.get("content", []):
        if block.get("type") == "text":
            text += block["text"]

    # Parse JSON from response (handle markdown fences)
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    analysis = json.loads(text)

    # Extract token usage from response
    usage = resp_data.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    # Pricing: Sonnet 4 = $3/M input, $15/M output
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


# ── Stage 5: Persist ────────────────────────────────────────────────────────

def save_results(video_id, url, metadata, transcript, frames, analysis, token_info, model):
    """Save analysis results and update index."""
    print(f"[5/5] Saving results...")

    frame_entries = []
    for i, (fpath, ts, method) in enumerate(frames):
        frame_entries.append({
            "index": i,
            "filename": Path(fpath).name,
            "timestamp": ts,
            "method": method,
        })

    category = analysis.get("category", "Other")

    result = {
        "video_id": video_id,
        "url": url,
        "title": metadata["title"],
        "channel": metadata["channel"],
        "duration": metadata["duration"],
        "upload_date": metadata.get("upload_date", ""),
        "analyzed_at": datetime.now().isoformat(),
        "model_used": model,
        "category": category,
        "token_usage": token_info,
        "transcript_available": len(transcript) > 0,
        "transcript": transcript,
        "frames": frame_entries,
        "analysis": analysis,
    }

    save_json(ANALYSES_DIR / f"{video_id}.json", result)

    update_index(
        video_id,
        url=url,
        title=metadata["title"],
        channel=metadata["channel"],
        duration=metadata["duration"],
        thumbnail=metadata["thumbnail"],
        status="done",
        completed_at=datetime.now().isoformat(),
        frame_count=len(frames),
        section_count=len(analysis.get("sections", [])),
        category=category,
        token_usage=token_info,
        model_used=model,
        error=None,
    )

    print(f"  Saved to data/study_analyses/{video_id}.json")


# ── Main Pipeline ────────────────────────────────────────────────────────────

def analyze_video(url, model="claude-sonnet-4-20250514", max_frames=20, scene_threshold=0.3):
    """Full analysis pipeline."""
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from: {url}")

    # Check tools
    for tool in ("yt-dlp", "ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise RuntimeError(f"{tool} not found. Install it first.")

    print(f"\n{'='*60}")
    print(f"Analyzing: {url}")
    print(f"Video ID:  {video_id}")
    print(f"Model:     {model}")
    print(f"{'='*60}\n")

    update_index(video_id, url=url, status="processing", started_at=datetime.now().isoformat(),
                 thumbnail=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")

    try:
        metadata = get_metadata(url, video_id)
        update_index(video_id, title=metadata["title"], channel=metadata["channel"],
                     duration=metadata["duration"], thumbnail=metadata["thumbnail"])

        transcript = get_transcript(video_id)
        frames = extract_keyframes(url, video_id, max_frames, scene_threshold)

        if not frames:
            raise RuntimeError("No keyframes extracted")

        analysis, token_info = analyze_with_claude(frames, transcript, metadata, model)
        save_results(video_id, url, metadata, transcript, frames, analysis, token_info, model)

        print(f"\nDone! {len(frames)} frames, {len(analysis.get('sections', []))} sections analyzed.")
        return {"ok": True, "video_id": video_id}

    except Exception as e:
        error_msg = str(e)[:500]
        print(f"\nError: {error_msg}", file=sys.stderr)
        update_index(video_id, status="error", error=error_msg)
        return {"ok": False, "video_id": video_id, "error": error_msg}


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a YouTube video")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--model", default="claude-sonnet-4-20250514")
    parser.add_argument("--max-frames", type=int, default=20)
    parser.add_argument("--scene-threshold", type=float, default=0.3)
    args = parser.parse_args()

    result = analyze_video(args.url, args.model, args.max_frames, args.scene_threshold)
    if not result["ok"]:
        sys.exit(1)
