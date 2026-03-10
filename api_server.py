#!/usr/bin/env python3
"""Mega Dashboard API Server

Thin shell that registers Flask Blueprint modules from routes/.
All route logic lives in routes/*.py; shared utilities in routes/_shared.py.
"""

from __future__ import annotations

import logging
import os as _os

_os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")  # Fix OpenMP conflict (torch + faiss)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/api_server.log"),
        logging.StreamHandler(),
    ],
)

from pathlib import Path

from flask import Flask, jsonify as _jsonify, send_from_directory
from flask_cors import CORS

# Optional: load local .env (TMDB key, etc.)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

from routes._shared import ROOT

# --- Import all blueprints ---
from routes.pages import pages_bp
from routes.finance import finance_bp
from routes.spotify import spotify_bp
from routes.trip import trip_bp
from routes.knowledge import knowledge_bp
from routes.study import study_bp
from routes.tv import tv_bp
from routes.movies import movies_bp
from routes.mega import mega_bp
from routes.recommendations import recommendations_bp
from routes.misc import misc_bp
from routes.knowledge_tree import knowledge_tree_bp

# Re-export for backwards compatibility (scripts/tusk_knowledge_refresh.py imports this)
from routes.knowledge import build_knowledge_feed  # noqa: F401

# Re-export shared utilities used by external scripts
from routes._shared import load_json, save_json  # noqa: F401

# --- Create app ---
app = Flask(__name__, static_folder=str(ROOT))
CORS(app)


@app.after_request
def _set_security_headers(resp):
    try:
        resp.headers.setdefault("Permissions-Policy", "microphone=*")
    except Exception:
        pass
    return resp


# --- Register blueprints ---
app.register_blueprint(pages_bp)
app.register_blueprint(finance_bp)
app.register_blueprint(spotify_bp)
app.register_blueprint(trip_bp)
app.register_blueprint(knowledge_bp)
app.register_blueprint(study_bp)
app.register_blueprint(tv_bp)
app.register_blueprint(movies_bp)
app.register_blueprint(mega_bp)
app.register_blueprint(recommendations_bp)
app.register_blueprint(misc_bp)
app.register_blueprint(knowledge_tree_bp)


# --- Global error handler (JSON 500 instead of HTML traceback) ---
@app.errorhandler(Exception)
def _handle_unhandled(e):
    logging.getLogger("mega").exception("Unhandled error: %s", e)
    return _jsonify({"error": str(e)}), 500


# --- Catch-all static file route (MUST be registered LAST) ---
@app.route("/<path:path>")
def static_files(path: str):
    return send_from_directory(str(ROOT), path)


if __name__ == "__main__":
    print("Mega Dashboard API Server")
    print("=" * 40)
    print("Starting server on http://localhost:8081")
    print()

    # Start Ashborn autonomous loop (daemon thread)
    try:
        from scripts.ashborn_loop import start_loop as _start_ashborn_loop
        _start_ashborn_loop()
        print("Ashborn autonomous loop started")
    except Exception as _e:
        print(f"Ashborn loop failed to start: {_e}")

    app.run(host="0.0.0.0", port=8081, debug=False, threaded=True)
