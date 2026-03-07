"""Static page serving routes (Solo Leveling only)."""

from __future__ import annotations

from flask import Blueprint, redirect, send_from_directory

from routes._shared import ROOT

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def home():
    return redirect("/study-journey")


@pages_bp.route("/study-journey")
@pages_bp.route("/study-journey/")
def study_journey_page():
    return send_from_directory(str(ROOT / "apps" / "study"), "index.html")


@pages_bp.route("/study")
@pages_bp.route("/study/")
def study_page():
    return send_from_directory(str(ROOT / "apps" / "study"), "study.html")


@pages_bp.route("/knowledge-feed")
@pages_bp.route("/knowledge-feed/")
def knowledge_feed_page():
    return send_from_directory(str(ROOT / "apps" / "study"), "knowledge_feed.html")


@pages_bp.route("/apps/study/knowledge_assets/<path:filename>")
def knowledge_assets(filename):
    return send_from_directory(str(ROOT / "apps" / "study" / "knowledge_assets"), filename)
