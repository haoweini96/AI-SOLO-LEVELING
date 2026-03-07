#!/usr/bin/env python3
"""AI Solo Leveling — API Server

Gamified AI/ML learning platform inspired by Solo Leveling.
"""

from __future__ import annotations

import logging
import os as _os

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

# Optional: load local .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

from routes._shared import ROOT

# --- Import blueprints ---
from routes.pages import pages_bp
from routes.knowledge_tree import knowledge_tree_bp
from routes.study import study_bp
from routes.knowledge import knowledge_bp

# Re-export for scripts
from routes._shared import load_json, save_json  # noqa: F401

# --- Create app ---
app = Flask(__name__, static_folder=str(ROOT))
CORS(app)

# --- Register blueprints ---
app.register_blueprint(pages_bp)
app.register_blueprint(knowledge_tree_bp)
app.register_blueprint(study_bp)
app.register_blueprint(knowledge_bp)


# --- Global error handler ---
@app.errorhandler(Exception)
def _handle_unhandled(e):
    logging.getLogger("solo-leveling").exception("Unhandled error: %s", e)
    return _jsonify({"error": str(e)}), 500


# --- Catch-all static file route (MUST be last) ---
@app.route("/<path:path>")
def static_files(path: str):
    return send_from_directory(str(ROOT), path)


if __name__ == "__main__":
    print()
    print("  ⚔️  AI Solo Leveling")
    print("  " + "=" * 36)
    print("  Starting server on http://localhost:8081")
    print()
    print("  Arise, Shadow Monarch!")
    print()

    app.run(host="0.0.0.0", port=8081, debug=False, threaded=True)
