"""Knowledge Tree routes — Tech Tree + Solo Leveling XP System.

Blueprint: knowledge_tree_bp
Prefix: /api/knowledge-tree/
"""

from __future__ import annotations

import io
import json
import os
import random
import re
import shutil
import threading
from datetime import datetime, timedelta, timezone

import numpy as np
from flask import Blueprint, jsonify, request, send_file

from routes._shared import (
    DATA_DIR,
    HUNTER_PROFILE_FILE,
    KNOWLEDGE_REVIEWS_FILE,
    KNOWLEDGE_TREE_FILE,
    TECH_TREE_TEMPLATE_FILE,
    load_json,
    log,
    make_meta,
    save_json,
)

knowledge_tree_bp = Blueprint("knowledge_tree", __name__)

_id_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACHIEVEMENTS = [
    {"id": "first_light", "title": "First Awakening", "desc": "Light up your first concept node", "icon": "⚡", "xp_bonus": 50},
    {"id": "five_lights", "title": "Rising Hunter", "desc": "Light up 5 concept nodes", "icon": "🌟", "xp_bonus": 100},
    {"id": "ten_lights", "title": "Illuminator", "desc": "Light up 10 concept nodes", "icon": "💡", "xp_bonus": 200},
    {"id": "half_tree", "title": "Half the World", "desc": "Light up 50% of the tech tree", "icon": "🌍", "xp_bonus": 500},
    {"id": "full_tree", "title": "Omniscient", "desc": "Light up the entire tech tree", "icon": "👁", "xp_bonus": 1000},
    {"id": "first_master", "title": "Shadow Extraction", "desc": "Master your first concept", "icon": "👤", "xp_bonus": 200},
    {"id": "five_masters", "title": "Shadow Army", "desc": "Master 5 concepts", "icon": "⚔️", "xp_bonus": 500},
    {"id": "first_review", "title": "Daily Quest", "desc": "Complete your first review", "icon": "📋", "xp_bonus": 30},
    {"id": "streak_7", "title": "Weekly Warrior", "desc": "7-day review streak", "icon": "🔥", "xp_bonus": 200},
    {"id": "streak_30", "title": "Monthly Monarch", "desc": "30-day review streak", "icon": "👑", "xp_bonus": 1000},
    {"id": "hundred_reviews", "title": "Centurion", "desc": "Complete 100 reviews", "icon": "💯", "xp_bonus": 500},
    {"id": "ten_sources", "title": "Knowledge Collector", "desc": "Collect 10 knowledge sources", "icon": "📚", "xp_bonus": 100},
    {"id": "multi_branch", "title": "Polymath", "desc": "Light up nodes in all 6 branches", "icon": "🎯", "xp_bonus": 300},
    {"id": "rank_e", "title": "觉醒", "desc": "成为猎人", "icon": "⚡", "xp_bonus": 0},
    {"id": "rank_d", "title": "D级突破", "desc": "达到 D-Rank", "icon": "🟢", "xp_bonus": 50},
    {"id": "rank_c", "title": "C级突破", "desc": "达到 C-Rank", "icon": "🔵", "xp_bonus": 100},
    {"id": "rank_b", "title": "B级突破", "desc": "达到 B-Rank", "icon": "🟣", "xp_bonus": 150},
    {"id": "rank_a", "title": "A级突破", "desc": "达到 A-Rank", "icon": "🟡", "xp_bonus": 200},
    {"id": "rank_s", "title": "S级觉醒", "desc": "达到 S-Rank", "icon": "🔴", "xp_bonus": 300},
    {"id": "national", "title": "国家权力级", "desc": "超越 S-Rank", "icon": "👑", "xp_bonus": 500},
    {"id": "shadow_monarch", "title": "暗影君王", "desc": "ARISE!", "icon": "🖤", "xp_bonus": 1000},
    # Sub-branch completion achievements
    {"id": "branch_math_stats", "title": "数学基础", "desc": "完成 Math & Statistics 全部概念", "icon": "📐", "xp_bonus": 150},
    {"id": "branch_classical_ml", "title": "经典ML大师", "desc": "完成 Classical ML 全部概念", "icon": "🎓", "xp_bonus": 150},
    {"id": "branch_nn_fundamentals", "title": "神经网络入门", "desc": "完成 Neural Network Fundamentals", "icon": "🧬", "xp_bonus": 150},
    {"id": "branch_computer_vision", "title": "计算机视觉", "desc": "完成 Computer Vision 全部概念", "icon": "👁", "xp_bonus": 150},
    {"id": "branch_nlp_lm", "title": "NLP 专家", "desc": "完成 NLP & Language Models", "icon": "📝", "xp_bonus": 150},
    {"id": "branch_llm_fundamentals", "title": "LLM 基础", "desc": "完成 LLM Fundamentals", "icon": "🤖", "xp_bonus": 150},
    {"id": "branch_rag", "title": "RAG 架构师", "desc": "完成 RAG 全部概念", "icon": "🔍", "xp_bonus": 150},
    {"id": "branch_agent_fundamentals", "title": "Agent 基础", "desc": "完成 Agent Fundamentals", "icon": "🕵️", "xp_bonus": 150},
    {"id": "branch_multi_agent", "title": "多Agent大师", "desc": "完成 Multi-Agent Systems", "icon": "👥", "xp_bonus": 150},
    {"id": "branch_agent_dev", "title": "Agent 开发者", "desc": "完成 Agent Development", "icon": "⚔️", "xp_bonus": 150},
    {"id": "branch_ml_systems", "title": "ML 系统工程师", "desc": "完成 ML Systems", "icon": "⚙️", "xp_bonus": 150},
    {"id": "branch_ai_dev", "title": "AI 开发专家", "desc": "完成 AI-Assisted Development", "icon": "💻", "xp_bonus": 150},
    {"id": "branch_api_integration", "title": "API 大师", "desc": "完成 API & Integration", "icon": "🔌", "xp_bonus": 150},
    {"id": "branch_gen_media", "title": "生成式创作者", "desc": "完成 Generative Media", "icon": "🎨", "xp_bonus": 150},
    {"id": "branch_ai_product", "title": "AI 产品设计师", "desc": "完成 AI Product Design", "icon": "🎯", "xp_bonus": 150},
    # Top-level domain completion achievements
    {"id": "domain_foundations", "title": "基础扎实", "desc": "完成 Foundations 全部概念", "icon": "📐", "xp_bonus": 500},
    {"id": "domain_deep_learning", "title": "深度学习大师", "desc": "完成 Deep Learning 全部概念", "icon": "🧬", "xp_bonus": 500},
    {"id": "domain_llm_apps", "title": "LLM 应用大师", "desc": "完成 LLM & Applications 全部概念", "icon": "🤖", "xp_bonus": 500},
    {"id": "domain_ai_agents", "title": "Agent 统帅", "desc": "完成 AI Agents 全部概念", "icon": "🕵️", "xp_bonus": 500},
    {"id": "domain_ai_engineering", "title": "AI 工程师", "desc": "完成 AI Engineering 全部概念", "icon": "🛠", "xp_bonus": 500},
    {"id": "domain_ai_products", "title": "AI 创造者", "desc": "完成 AI Products 全部概念", "icon": "🎨", "xp_bonus": 500},
]

# Branch ID → achievement ID mapping (sub-branch and top-level)
BRANCH_ACHIEVEMENT_MAP = {
    "math_stats": "branch_math_stats",
    "classical_ml": "branch_classical_ml",
    "nn_fundamentals": "branch_nn_fundamentals",
    "computer_vision": "branch_computer_vision",
    "nlp_lm": "branch_nlp_lm",
    "llm_fundamentals": "branch_llm_fundamentals",
    "rag": "branch_rag",
    "agent_fundamentals": "branch_agent_fundamentals",
    "multi_agent": "branch_multi_agent",
    "agent_dev": "branch_agent_dev",
    "ml_systems": "branch_ml_systems",
    "ai_dev": "branch_ai_dev",
    "api_integration": "branch_api_integration",
    "gen_media": "branch_gen_media",
    "ai_product": "branch_ai_product",
    "foundations": "domain_foundations",
    "deep_learning": "domain_deep_learning",
    "llm_apps": "domain_llm_apps",
    "ai_agents": "domain_ai_agents",
    "ai_engineering": "domain_ai_engineering",
    "ai_products": "domain_ai_products",
}

# Solo Leveling rank table: (min_level, max_level, rank, title_at_min, title_at_max)
RANK_TABLE = [
    # (min_level, max_level, rank, title_cn, subtitle_cn)
    (1,   5,   "E", "觉醒者",         "初入猎场"),
    (6,   10,  "E", "E级猎人",        "崭露头角"),
    (11,  15,  "D", "D级猎人",        "小有名气"),
    (16,  20,  "D", "D级精英",        "见习突破者"),
    (21,  27,  "C", "C级猎人",        "独当一面"),
    (28,  35,  "C", "C级精英",        "百战之将"),
    (36,  42,  "B", "B级猎人",        "公会中坚"),
    (43,  50,  "B", "B级精英",        "攻略组核心"),
    (51,  57,  "A", "A级猎人",        "名震四方"),
    (58,  65,  "A", "A级精英",        "顶级战力"),
    (66,  72,  "S", "S级猎人",        "人类巅峰"),
    (73,  80,  "S", "S级精英",        "传说猎人"),
    (81,  87,  "National", "国家权力级",  "超越人类"),
    (88,  95,  "National", "国家权力级精英", "世界守护者"),
    (96,  99,  "Monarch",  "君主候选",    "暗影觉醒"),
    (100, 100, "Shadow Monarch", "暗影君王", "统御万影"),
]


# ---------------------------------------------------------------------------
# Helpers — basics
# ---------------------------------------------------------------------------

def _is_chinese(text: str) -> bool:
    """Return True if >30% of non-whitespace chars are CJK."""
    if not text:
        return False
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    cjk = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    return cjk / len(chars) > 0.3


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _load_tree():
    return load_json(KNOWLEDGE_TREE_FILE, {"tech_tree_version": "1.0", "nodes": {}, "sources": [], "edges": []})


def _save_tree(data):
    save_json(KNOWLEDGE_TREE_FILE, data)


def _load_template():
    return load_json(TECH_TREE_TEMPLATE_FILE, {"version": "1.0", "tree": {"children": []}})


def _load_profile():
    return load_json(HUNTER_PROFILE_FILE, _default_profile())


def _save_profile(profile):
    save_json(HUNTER_PROFILE_FILE, profile)


def _default_profile():
    return {
        "hunter_name": "Shadow Monarch",
        "rank": "E",
        "level": 1,
        "total_xp": 0,
        "current_xp": 0,
        "xp_to_next_level": 100,
        "title": "Novice Hunter",
        "stats": {
            "foundations": 0, "deep_learning": 0, "llm_apps": 0,
            "ai_agents": 0, "ai_engineering": 0, "ai_products": 0,
        },
        "achievements": [],
        "daily_streak": 0,
        "longest_streak": 0,
        "last_active_date": None,
        "created_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Helpers — tech tree template traversal
# ---------------------------------------------------------------------------

def _get_all_leaves(template: dict) -> list[dict]:
    """Get all leaf nodes from the template tree."""
    leaves = []
    def _walk(node):
        children = node.get("children", [])
        if not children:
            leaves.append(node)
        else:
            for c in children:
                _walk(c)
    _walk(template.get("tree", {}))
    return leaves


def _get_top_level_branches(template: dict) -> list[dict]:
    """Get the 6 top-level branches."""
    return template.get("tree", {}).get("children", [])


def _get_leaves_under(branch: dict, template: dict = None) -> list[dict]:
    """Get all leaf nodes under a branch."""
    leaves = []
    def _walk(node):
        children = node.get("children", [])
        if not children:
            leaves.append(node)
        else:
            for c in children:
                _walk(c)
    _walk(branch)
    return leaves


def _get_branch_for_leaf(leaf_id: str, template: dict) -> str | None:
    """Get the top-level branch ID that contains a leaf node."""
    for branch in _get_top_level_branches(template):
        leaves = _get_leaves_under(branch)
        if any(l["id"] == leaf_id for l in leaves):
            return branch["id"]
    return None


def _get_all_intermediate_nodes(template: dict) -> list[dict]:
    """Get all intermediate (non-leaf, non-root) nodes."""
    intermediates = []
    def _walk(node, depth=0):
        children = node.get("children", [])
        if children:
            if depth > 0:  # skip root
                intermediates.append(node)
            for c in children:
                _walk(c, depth + 1)
    _walk(template.get("tree", {}))
    return intermediates


# ---------------------------------------------------------------------------
# Helpers — XP, rank, level system
# ---------------------------------------------------------------------------

def xp_for_level(level: int) -> int:
    """XP required to reach the next level. ~67.5K total for Lv.100, ~1 year at 200 XP/day."""
    return round(45 + 3 * level * (1.02 ** level))


def _rank_for_level(level: int) -> str:
    for min_l, max_l, rank, _, _ in RANK_TABLE:
        if min_l <= level <= max_l:
            return rank
    return "E"


def _title_for_level(level: int) -> str:
    for min_l, max_l, _, title_cn, _ in RANK_TABLE:
        if min_l <= level <= max_l:
            return title_cn
    return "觉醒者"


def _subtitle_for_level(level: int) -> str:
    for min_l, max_l, _, _, subtitle_cn in RANK_TABLE:
        if min_l <= level <= max_l:
            return subtitle_cn
    return "初入猎场"


def _update_streak(profile: dict):
    """Update daily streak based on last_active_date."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    last = profile.get("last_active_date")
    if last == today:
        return  # already active today
    if last:
        try:
            last_date = datetime.fromisoformat(last).date()
            today_date = datetime.now(timezone.utc).date()
            diff = (today_date - last_date).days
            if diff == 1:
                profile["daily_streak"] = profile.get("daily_streak", 0) + 1
            elif diff > 1:
                profile["daily_streak"] = 1
        except (ValueError, TypeError):
            profile["daily_streak"] = 1
    else:
        profile["daily_streak"] = 1
    profile["last_active_date"] = today
    profile["longest_streak"] = max(profile.get("longest_streak", 0), profile["daily_streak"])


def _check_achievements(profile: dict, tree_data: dict) -> list[dict]:
    """Check and award new achievements. Returns list of newly earned achievements."""
    earned_ids = {a["id"] for a in profile.get("achievements", [])}
    nodes = tree_data.get("nodes", {})
    sources = tree_data.get("sources", [])
    reviews_data = load_json(KNOWLEDGE_REVIEWS_FILE, {"reviews": []})
    total_reviews = len(reviews_data.get("reviews", []))

    lit = sum(1 for n in nodes.values() if n.get("status") in ("lit", "mastered"))
    mastered = sum(1 for n in nodes.values() if n.get("status") == "mastered")
    total_leaves = len(nodes)
    lit_ratio = lit / total_leaves if total_leaves > 0 else 0

    template = _load_template()
    branches = _get_top_level_branches(template)
    branches_lit = 0
    for branch in branches:
        leaves = _get_leaves_under(branch)
        leaf_ids = [l["id"] for l in leaves]
        if any(nodes.get(lid, {}).get("status") in ("lit", "mastered") for lid in leaf_ids):
            branches_lit += 1

    rank = profile.get("rank", "E")
    rank_order = {"E": 0, "D": 1, "C": 2, "B": 3, "A": 4, "S": 5, "National": 6, "Monarch": 7, "Shadow Monarch": 8}
    rank_num = rank_order.get(rank, 0)

    conditions = {
        "first_light": lit >= 1,
        "five_lights": lit >= 5,
        "ten_lights": lit >= 10,
        "half_tree": lit_ratio >= 0.5,
        "full_tree": lit_ratio >= 1.0,
        "first_master": mastered >= 1,
        "five_masters": mastered >= 5,
        "first_review": total_reviews >= 1,
        "streak_7": profile.get("daily_streak", 0) >= 7,
        "streak_30": profile.get("daily_streak", 0) >= 30,
        "hundred_reviews": total_reviews >= 100,
        "ten_sources": len(sources) >= 10,
        "multi_branch": branches_lit >= 6,
        "rank_e": rank_num >= 0,
        "rank_d": rank_num >= 1,
        "rank_c": rank_num >= 2,
        "rank_b": rank_num >= 3,
        "rank_a": rank_num >= 4,
        "rank_s": rank_num >= 5,
        "national": rank_num >= 6,
        "shadow_monarch": rank_num >= 8,
    }

    # Branch completion achievements — check each sub-branch and top-level branch
    def _all_leaves_lit(branch_node):
        leaves = _get_leaves_under(branch_node)
        leaf_ids = [l["id"] for l in leaves]
        return len(leaf_ids) > 0 and all(
            nodes.get(lid, {}).get("status") in ("lit", "mastered") for lid in leaf_ids
        )

    for branch in branches:
        # Top-level domain check
        ach_id = BRANCH_ACHIEVEMENT_MAP.get(branch.get("id"))
        if ach_id:
            conditions[ach_id] = _all_leaves_lit(branch)
        # Sub-branch checks
        for mid in branch.get("children", []):
            ach_id = BRANCH_ACHIEVEMENT_MAP.get(mid.get("id"))
            if ach_id:
                conditions[ach_id] = _all_leaves_lit(mid)

    new_achievements = []
    for ach in ACHIEVEMENTS:
        if ach["id"] not in earned_ids and conditions.get(ach["id"], False):
            earned = {
                "id": ach["id"],
                "title": ach["title"],
                "desc": ach["desc"],
                "icon": ach["icon"],
                "earned_at": _now_iso(),
            }
            profile.setdefault("achievements", []).append(earned)
            new_achievements.append({**earned, "xp_bonus": ach["xp_bonus"]})

    return new_achievements


def _calculate_stats(tree_data: dict, template: dict) -> dict:
    """Calculate 6-dimensional stats from tree node status."""
    branches = _get_top_level_branches(template)
    stats = {}
    nodes = tree_data.get("nodes", {})

    for branch in branches:
        branch_id = branch["id"]
        leaves = _get_leaves_under(branch)
        leaf_ids = [l["id"] for l in leaves]
        total = len(leaf_ids)

        if total == 0:
            stats[branch_id] = 0
            continue

        lit = sum(1 for lid in leaf_ids if nodes.get(lid, {}).get("status") in ("lit", "mastered"))
        mastered_count = sum(1 for lid in leaf_ids if nodes.get(lid, {}).get("status") == "mastered")
        avg_conf = sum(nodes.get(lid, {}).get("confidence", 0) for lid in leaf_ids) / total

        score = min(100, int(
            (lit / total) * 40 +
            (mastered_count / total) * 30 +
            avg_conf * 30
        ))
        stats[branch_id] = score

    return stats


def _award_xp(amount: int, reason: str, tree_data: dict | None = None) -> dict:
    """Award XP, check level-ups and achievements. Returns result dict."""
    profile = _load_profile()

    profile["total_xp"] = profile.get("total_xp", 0) + amount
    profile["current_xp"] = profile.get("current_xp", 0) + amount

    # Check level-ups
    level_ups = 0
    old_level = profile.get("level", 1)
    old_rank = profile.get("rank", "E")
    old_stats = dict(profile.get("stats", {}))

    while profile["current_xp"] >= profile.get("xp_to_next_level", 100) and profile["level"] < 100:
        profile["current_xp"] -= profile["xp_to_next_level"]
        profile["level"] += 1
        level_ups += 1
        profile["xp_to_next_level"] = xp_for_level(profile["level"])
        profile["rank"] = _rank_for_level(profile["level"])
        profile["title"] = _title_for_level(profile["level"])
        profile["subtitle"] = _subtitle_for_level(profile["level"])

    # Cap at level 100
    if profile["level"] >= 100:
        profile["level"] = 100
        profile["current_xp"] = 0
        profile["xp_to_next_level"] = 0

    # Always recalculate rank/title (handles migration from old rank system)
    profile["rank"] = _rank_for_level(profile["level"])
    profile["title"] = _title_for_level(profile["level"])
    profile["subtitle"] = _subtitle_for_level(profile["level"])

    # Update stats
    if tree_data is None:
        tree_data = _load_tree()
    template = _load_template()
    profile["stats"] = _calculate_stats(tree_data, template)

    # Check achievements
    new_achievements = _check_achievements(profile, tree_data)

    # Award achievement XP bonuses (recursive but achievements won't trigger more achievements)
    for ach in new_achievements:
        bonus = ach.get("xp_bonus", 0)
        if bonus > 0:
            profile["total_xp"] += bonus
            profile["current_xp"] += bonus
            # Re-check level-ups from bonus
            while profile["current_xp"] >= profile.get("xp_to_next_level", 100) and profile["level"] < 100:
                profile["current_xp"] -= profile["xp_to_next_level"]
                profile["level"] += 1
                level_ups += 1
                profile["xp_to_next_level"] = xp_for_level(profile["level"])
                profile["rank"] = _rank_for_level(profile["level"])
                profile["title"] = _title_for_level(profile["level"])
                profile["subtitle"] = _subtitle_for_level(profile["level"])

    # Append XP history entry
    xp_history = profile.setdefault("xp_history", [])
    xp_history.append({
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "amount": amount,
        "reason": reason,
        "total_after": profile.get("total_xp", 0),
    })

    _save_profile(profile)

    return {
        "xp_gained": amount,
        "reason": reason,
        "level_ups": level_ups,
        "old_level": old_level,
        "new_level": profile["level"],
        "old_rank": old_rank,
        "new_rank": profile["rank"],
        "old_stats": old_stats,
        "new_stats": profile["stats"],
        "new_achievements": new_achievements,
        "profile": profile,
    }


# ---------------------------------------------------------------------------
# Helpers — node status
# ---------------------------------------------------------------------------

def _update_node_status(node: dict):
    """Update a node's status based on quest progress (4 states: locked/in_progress/lit/mastered)."""
    has_sources = len(node.get("source_ids", [])) > 0

    if not has_sources:
        node["status"] = "locked"
        return

    quest = node.get("quest")
    if not quest:
        quest = _default_quest()
        node["quest"] = quest

    progress = quest.get("progress", {})

    # Learning: coverage-based (fallback to source count for nodes without dimensions)
    dimensions = quest.get("dimensions")
    if dimensions:
        coverage_met = progress.get("overall_coverage", 0) >= quest.get("coverage_threshold", 0.7)
    else:
        coverage_met = progress.get("sources_count", 0) >= quest.get("required_sources", 1)

    quiz_met = progress.get("quiz_passed", False)
    practice = quest.get("practice_task")
    practice_met = True
    if practice and isinstance(practice, dict) and practice.get("required", False):
        practice_met = progress.get("practice_completed", False)

    all_met = coverage_met and quiz_met and practice_met

    if all_met and node.get("confidence", 0) >= 0.8 and (node.get("review_status") or {}).get("review_count", 0) >= 5:
        node["status"] = "mastered"
    elif all_met:
        node["status"] = "lit"
    else:
        node["status"] = "in_progress"


def _update_coverage(node: dict):
    """Recalculate node's overall coverage from all source coverages."""
    quest = node.get("quest", {})
    dimensions = quest.get("dimensions", [])
    progress = quest.setdefault("progress", {})
    source_coverages = progress.get("source_coverages", {})

    if not dimensions or not source_coverages:
        progress["overall_coverage"] = 0
        progress["dimension_scores"] = {}
        return

    # Each dimension takes the max score across all sources
    dim_scores = {}
    for dim in dimensions:
        dim_id = dim["id"]
        max_score = 0
        for scores in source_coverages.values():
            max_score = max(max_score, scores.get(dim_id, 0))
        dim_scores[dim_id] = round(max_score, 2)

    progress["dimension_scores"] = dim_scores

    # Weighted average
    total_weight = sum(d["weight"] for d in dimensions)
    overall = sum(dim_scores.get(d["id"], 0) * d["weight"] for d in dimensions) / max(total_weight, 0.01)
    progress["overall_coverage"] = round(overall, 2)


def _evaluate_source_coverage(source: dict, node: dict) -> dict:
    """AI-evaluate a source's coverage of a node's knowledge dimensions. Returns {dim_id: score}."""
    dimensions = node.get("quest", {}).get("dimensions", [])
    if not dimensions:
        return {}

    dims_json = json.dumps([{"id": d["id"], "title": d["title"]} for d in dimensions], ensure_ascii=False)

    result = _call_claude(
        system_prompt="You are a knowledge assessment assistant. Return strict JSON.",
        user_prompt=f"""Evaluate how well the following learning material covers each knowledge dimension.

Learning material:
Title: {source.get('title', '')}
Summary: {source.get('summary', '')}
Key points: {source.get('key_takeaways', [])[:8]}

Knowledge dimensions to evaluate:
{dims_json}

Score each dimension 0-100:
- 0: Not covered at all
- 20-40: Briefly mentioned
- 50-70: Covered with some depth
- 80-100: Deep, comprehensive coverage

Return JSON:
{{"scores": {{"dim_id_1": 85, "dim_id_2": 30, ...}}}}""",
        max_tokens=500,
    )

    scores = {}
    for dim_id, score in result.get("scores", {}).items():
        scores[dim_id] = round(min(1.0, max(0, score / 100)), 2)

    return scores


def _update_quest_progress(node: dict, tree_data: dict = None):
    """Update quest progress counters, coverage, and recalculate node status."""
    quest = node.get("quest")
    if not quest:
        quest = _default_quest()
        node["quest"] = quest
    progress = quest.setdefault("progress", {})
    progress["sources_count"] = len(node.get("source_ids", []))
    _update_coverage(node)
    _update_node_status(node)


# ---------------------------------------------------------------------------
# Helpers — AI integration
# ---------------------------------------------------------------------------

def _call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> dict:
    """Call Claude Sonnet and return parsed JSON dict."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.3,
    )

    text = response.content[0].text.strip()
    # Strip markdown code fence
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?\s*```$", "", text)
    # Find the outermost JSON object
    start = text.find("{")
    if start >= 0:
        depth = 0
        end = start
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        text = text[start:end]

    return json.loads(text)


def _classify_source_to_tree(source: dict, template: dict) -> list[str]:
    """AI-classify a source to 1-3 tech tree leaf nodes."""
    leaves = _get_all_leaves(template)

    # Build rich leaf descriptions with guide + dimensions for better classification
    tree_data = _load_tree()
    leaf_entries = []
    for l in leaves:
        entry: dict = {"id": l["id"], "title": l["title"]}
        # Add guide description if available
        guide = l.get("guide")
        if isinstance(guide, dict) and guide.get("what"):
            entry["description"] = guide["what"]
        # Add dimension names from quest config
        node_data = tree_data.get("nodes", {}).get(l["id"], {})
        dims = node_data.get("quest", {}).get("dimensions", [])
        dim_names = [d.get("title") or d.get("name") or d.get("id") for d in dims if isinstance(d, dict)]
        dim_names = [n for n in dim_names if n]
        if dim_names:
            entry["dimensions"] = dim_names
        leaf_entries.append(entry)
    leaves_json = json.dumps(leaf_entries, ensure_ascii=False)

    prompt = (
        "Here is a new knowledge source:\n"
        f"Title: {source.get('title', '')}\n"
        f"Summary: {source.get('summary', '')}\n"
        f"Tags: {source.get('tags', [])}\n"
        f"Key takeaways: {source.get('key_takeaways', [])[:5]}\n\n"
        f"Here are all leaf concept nodes in the tech tree (with descriptions and dimensions):\n{leaves_json}\n\n"
        "Which concept nodes should this source be linked to? A source can link to 1-3 nodes.\n\n"
        'Return JSON:\n'
        '{"node_ids": ["node_id_1", "node_id_2"], "reasoning": "Brief explanation for the choices"}\n\n'
        "Rules:\n"
        "- Only select truly relevant nodes, don't over-select\n"
        "- Usually 1-2 is enough\n"
        "- Only select leaf node IDs\n"
        "- Reference each node's description and dimensions to judge relevance, don't rely solely on title"
    )

    result = _call_claude(
        system_prompt="You are a knowledge classification assistant.",
        user_prompt=prompt,
        max_tokens=500,
    )

    valid_leaf_ids = {l["id"] for l in leaves}
    node_ids = [nid for nid in result.get("node_ids", []) if nid in valid_leaf_ids]
    return node_ids[:3]


def _generate_node_summary(node_id: str, tree_data: dict) -> dict | None:
    """AI-generate a summary for a node based on its linked sources."""
    node = tree_data.get("nodes", {}).get(node_id)
    if not node:
        return None

    source_ids = node.get("source_ids", [])
    sources = [s for s in tree_data.get("sources", []) if s["id"] in source_ids]
    if not sources:
        return None

    sources_info = [
        {"title": s.get("title", ""), "summary": s.get("summary", ""), "key_takeaways": s.get("key_takeaways", [])[:5]}
        for s in sources
    ]

    try:
        result = _call_claude(
            system_prompt="You are a knowledge organizer. Synthesize source information into a concise concept summary. Always respond in English. Return strict JSON.",
            user_prompt=f"""Concept ID: {node_id}
Source information:
{json.dumps(sources_info, ensure_ascii=False, indent=2)}

Return JSON:
{{"summary": "2-3 sentence comprehensive summary in English", "key_takeaways": ["takeaway1", "takeaway2", ...], "tags": ["tag1", "tag2"]}}""",
            max_tokens=1000,
        )
        return result
    except Exception as e:
        log.warning("Failed to generate summary for node %s: %s", node_id, e)
        return None


MINDMAP_COLORS = ["#4fc3f7", "#81c784", "#ffb74d", "#f06292", "#ba68c8", "#4dd0e1"]


def _generate_mindmap(node: dict, takeaways: list[str], summaries: list[str], lang: str = "en") -> dict:
    """AI-generate a mind map structure for a node."""
    title = node.get("title", node.get("id", ""))
    # Guard: need at least some content to generate a meaningful mind map
    if not takeaways and not any(summaries):
        return {"center": title, "branches": [], "connections": []}

    if lang == "zh":
        lang_rule = "- 用简体中文，技术术语保留英文（如 RAG, Embedding, Fine-tuning, Agent, Pipeline）"
    else:
        lang_rule = "- Use English for all labels"

    result = _call_claude(
        system_prompt="You are a knowledge structuring expert. Organize scattered knowledge points into a clear mind map structure. Return strict JSON.",
        user_prompt=f"""Concept: {title}
Description: {node.get('summary', '')}

Source summaries for this concept:
{chr(10).join(s for s in summaries if s)}

Key takeaways:
{chr(10).join(f'• {t}' for t in takeaways)}

Organize this knowledge into a mind map structure. The center node is the concept name, then branch out into 3-6 thematic branches, each with 2-5 specific knowledge points.

Return JSON:
{{
  "center": "{title}",
  "branches": [
    {{
      "id": "branch_1",
      "label": "Branch theme name",
      "color": "#4fc3f7",
      "children": [
        {{"id": "b1_1", "label": "Specific knowledge point 1"}},
        {{"id": "b1_2", "label": "Specific knowledge point 2"}}
      ]
    }}
  ],
  "connections": [
    {{"from": "b1_2", "to": "b2_1", "label": "relates to"}}
  ]
}}

Rules:
- Center node is the concept name
- 3-6 main branches representing core themes/aspects
- Each branch has 2-5 leaf nodes with specific knowledge points
- Branch labels are short (2-5 words)
- Leaf node labels can be slightly longer but no more than 15 words
- color: assign a different color to each branch (pick from: #4fc3f7, #81c784, #ffb74d, #f06292, #ba68c8, #4dd0e1)
- connections: cross-branch relationships (optional, 0-3), showing related knowledge points across branches
{lang_rule}""",
        max_tokens=2000,
    )

    # Validate and sanitize response
    if "center" not in result:
        result["center"] = title
    if not isinstance(result.get("branches"), list) or not result["branches"]:
        raise ValueError("AI response missing branches array")
    for i, b in enumerate(result["branches"]):
        b.setdefault("id", f"branch_{i}")
        b.setdefault("label", f"Topic {i + 1}")
        b.setdefault("children", [])
        if not b.get("color"):
            b["color"] = MINDMAP_COLORS[i % len(MINDMAP_COLORS)]
    result.setdefault("connections", [])
    return result


def _extract_knowledge_with_ai(conversation_text: str, user_notes: str = "") -> dict:
    """Use Claude to extract structured knowledge points from conversation text."""
    system_prompt = (
        "You are a knowledge extraction assistant. Analyze the provided conversation content and extract valuable knowledge points.\n\n"
        "Rules:\n"
        "1. Only extract knowledge with learning value — ignore chit-chat, debugging processes, repetitive code edits\n"
        "2. Each knowledge point should be an independent, reviewable concept or fact\n"
        "3. If the conversation is mainly coding/debugging with no new knowledge, return an empty array\n"
        "4. tags: lowercase English, for search\n"
        "5. summary: write in English, 2-3 sentences\n"
        "6. key_takeaways: each item is an independent point that can be used directly for review\n\n"
        "Return strict JSON, no other text:"
    )

    notes_line = f"\n\nUser notes: {user_notes}" if user_notes else ""
    user_prompt = (
        f"Conversation content:\n{conversation_text}{notes_line}\n\n"
        "Extract knowledge points, return JSON:\n"
        '{\n'
        '  "knowledge_points": [\n'
        '    {\n'
        '      "title": "Short title",\n'
        '      "tags": ["tag1", "tag2"],\n'
        '      "summary": "2-3 sentence summary",\n'
        '      "key_takeaways": ["takeaway1", "takeaway2"],\n'
        '      "raw_excerpt": "Most relevant excerpt from the conversation"\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        'If the conversation has no valuable knowledge, return {"knowledge_points": []}'
    )

    try:
        result = _call_claude(system_prompt, user_prompt, max_tokens=2000)
        log.info("AI extracted %d knowledge points", len(result.get("knowledge_points", [])))
        return result
    except Exception as e:
        log.warning("AI extraction failed: %s", e)
        return {"knowledge_points": [{"title": f"Notes: {conversation_text[:50]}...", "tags": [], "summary": "AI extraction failed.", "key_takeaways": [], "raw_excerpt": conversation_text[:500]}]}


def _format_conversation(messages: list[dict]) -> str:
    """Format conversation messages into readable text."""
    lines = []
    for msg in messages:
        role = (msg.get("role") or "unknown").upper()
        content = msg.get("content") or ""
        if len(content) > 2000:
            content = content[:2000] + "... [truncated]"
        lines.append(f"[{role}]: {content}")
    full_text = "\n\n".join(lines)
    if len(full_text) > 8000:
        full_text = full_text[:8000] + "\n\n... [truncated]"
    return full_text


# ---------------------------------------------------------------------------
# Helpers — source management
# ---------------------------------------------------------------------------

def _next_source_id(sources: list[dict]) -> str:
    """Generate src_{3-digit seq}."""
    max_num = 0
    for s in sources:
        try:
            num = int(s["id"].split("_")[1])
            max_num = max(max_num, num)
        except (ValueError, IndexError):
            pass
    return f"src_{max_num + 1:03d}"


def _add_source_and_classify(source_data: dict, tree_data: dict, template: dict) -> tuple[dict, list[str], bool]:
    """Add a source and classify it to tree nodes. Returns (source, node_ids, any_newly_lit)."""
    source_id = _next_source_id(tree_data.get("sources", []))
    now = _now_iso()

    source = {
        "id": source_id,
        "title": source_data.get("title", "Untitled"),
        "type": source_data.get("type", "article"),
        "url": source_data.get("url", ""),
        "study_item_id": source_data.get("study_item_id"),
        "summary": source_data.get("summary", ""),
        "key_takeaways": source_data.get("key_takeaways", []),
        "tags": source_data.get("tags", []),
        "raw_excerpt": source_data.get("raw_excerpt", ""),
        "node_ids": [],
        "created_at": now,
        "captured_from": source_data.get("captured_from", "manual"),
    }

    # AI classify to tree nodes
    try:
        node_ids = _classify_source_to_tree(source, template)
    except Exception as e:
        log.warning("AI classification failed for source %s: %s", source_id, e)
        node_ids = []

    source["node_ids"] = node_ids
    tree_data.setdefault("sources", []).append(source)

    # Light up nodes
    any_newly_lit = False
    for nid in node_ids:
        node = tree_data.get("nodes", {}).get(nid)
        if not node:
            continue
        was_unlit = node.get("status") == "locked"
        if source_id not in node.get("source_ids", []):
            node.setdefault("source_ids", []).append(source_id)
        if was_unlit and not node.get("first_lit_at"):
            node["first_lit_at"] = now
            any_newly_lit = True
        node["updated_at"] = now

        # Merge tags
        existing_tags = set(node.get("tags", []))
        for tag in source.get("tags", []):
            existing_tags.add(tag)
        node["tags"] = sorted(existing_tags)

        # Evaluate source coverage against node dimensions
        try:
            coverage_scores = _evaluate_source_coverage(source, node)
            if coverage_scores:
                quest = node.setdefault("quest", _default_quest())
                progress = quest.setdefault("progress", {})
                sc = progress.setdefault("source_coverages", {})
                sc[source_id] = coverage_scores
        except Exception as e:
            log.warning("Coverage evaluation failed for source %s on node %s: %s", source_id, nid, e)

        _update_quest_progress(node, tree_data)

    return source, node_ids, any_newly_lit


# ---------------------------------------------------------------------------
# Helpers — SRS (Spaced Repetition)
# ---------------------------------------------------------------------------

def _update_srs(node: dict, result: str) -> dict:
    """Update a node's SRS review status. result: 'forgot'|'hard'|'remembered'|'easy'."""
    rs = node.setdefault("review_status", {})
    rs["review_count"] = rs.get("review_count", 0) + 1
    rs["last_reviewed"] = _now_iso()

    quality_map = {"forgot": 0, "hard": 3, "remembered": 4, "easy": 5}
    q = quality_map[result]

    ef = rs.get("ease_factor", 2.5)
    ef = max(1.3, ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    rs["ease_factor"] = round(ef, 2)

    if q < 3:
        rs["interval_days"] = 1
        node["confidence"] = round(max(0.0, node.get("confidence", 0) - 0.2), 2)
    else:
        count = rs["review_count"]
        if count == 1:
            rs["interval_days"] = 1
        elif count == 2:
            rs["interval_days"] = 3
        else:
            rs["interval_days"] = round(rs.get("interval_days", 1) * ef)
        node["confidence"] = round(min(1.0, node.get("confidence", 0) + 0.15), 2)

    rs["interval_days"] = min(rs["interval_days"], 180)
    rs["next_review"] = (datetime.now(timezone.utc) + timedelta(days=rs["interval_days"])).isoformat()

    _update_quest_progress(node)
    return node


def _get_due_nodes(tree_data: dict, limit: int | None = None) -> list[dict]:
    """Get in_progress/lit/mastered nodes due for review (excludes locked)."""
    now = _now_iso()
    due = []
    for nid, node in tree_data.get("nodes", {}).items():
        if node.get("status") == "locked":
            continue
        rs = node.get("review_status") or {}
        next_review = rs.get("next_review")
        if next_review and next_review <= now:
            due.append({**node, "id": nid})

    due.sort(key=lambda n: (n.get("confidence", 0), (n.get("review_status") or {}).get("next_review", "")))
    if limit:
        due = due[:limit]
    return due


def _get_next_due_time(tree_data: dict) -> str | None:
    """Get the next upcoming review time."""
    upcoming = []
    now = _now_iso()
    for node in tree_data.get("nodes", {}).values():
        nr = (node.get("review_status") or {}).get("next_review")
        if nr and nr > now:
            upcoming.append(nr)
    return min(upcoming) if upcoming else None


def _select_review_nodes(tree_data: dict, reviews_data: dict, count: int = 6) -> list[tuple]:
    """Select nodes for comprehensive review, ordered by priority.

    Returns list of (node_id, node_dict, reason) tuples where reason is
    'due', 'wrong', or 'random'.
    """
    nodes = tree_data.get("nodes", {})
    reviews = reviews_data.get("reviews", [])
    now = _now_iso()

    selected: list[tuple] = []
    selected_ids: set[str] = set()

    # Only nodes with source_ids that are not locked
    eligible = {
        nid: n for nid, n in nodes.items()
        if n.get("status") in ("in_progress", "lit", "mastered")
        and n.get("source_ids")
    }
    if not eligible:
        return []

    # Priority 1: SRS due nodes (next_review < now)
    due_nodes = []
    for nid, node in eligible.items():
        nr = (node.get("review_status") or {}).get("next_review", "")
        if nr and nr <= now:
            due_nodes.append((nid, node))
    due_nodes.sort(key=lambda x: (x[1].get("review_status") or {}).get("next_review", ""))

    for nid, node in due_nodes[:3]:
        if nid not in selected_ids:
            selected.append((nid, node, "due"))
            selected_ids.add(nid)

    # Priority 2: Recently wrong nodes (from last 50 reviews)
    wrong_nids: list[str] = []
    seen_wrong: set[str] = set()
    for r in reversed(reviews[-50:]):
        nid = r.get("node_id", "")
        if r.get("result") == "forgot" and nid in eligible and nid not in seen_wrong:
            wrong_nids.append(nid)
            seen_wrong.add(nid)

    for nid in wrong_nids[:2]:
        if nid not in selected_ids:
            selected.append((nid, eligible[nid], "wrong"))
            selected_ids.add(nid)

    # Priority 3: Fill remaining with random eligible nodes
    remaining = [nid for nid in eligible if nid not in selected_ids]
    random.shuffle(remaining)

    for nid in remaining[: count - len(selected)]:
        selected.append((nid, eligible[nid], "random"))
        selected_ids.add(nid)

    return selected


# ---------------------------------------------------------------------------
# Helpers — quiz generation
# ---------------------------------------------------------------------------

def _get_related_context(due_nodes: list[dict], tree_data: dict) -> list[dict]:
    """Get related node info for quiz connection questions."""
    edges = tree_data.get("edges", [])
    all_nodes = tree_data.get("nodes", {})
    due_ids = {n["id"] for n in due_nodes}
    context = []
    for node in due_nodes:
        related = []
        for edge in edges:
            other_id = None
            if edge.get("source_id") == node["id"]:
                other_id = edge.get("target_id")
            elif edge.get("target_id") == node["id"]:
                other_id = edge.get("source_id")
            if other_id and other_id in all_nodes and other_id not in due_ids:
                other = all_nodes[other_id]
                related.append({"title": other.get("title", other_id), "summary": (other.get("summary") or "")[:200]})
        if related:
            context.append({"node_id": node["id"], "related": related[:3]})
    return context


def _generate_quizzes_with_ai(nodes: list[dict], related_context: list[dict]) -> list[dict]:
    """Generate mixed-format quizzes in English: multiple_choice + open_ended, four quiz types."""
    # Collect source content for richer quiz generation
    tree_data = _load_tree()
    all_content = []
    for n in nodes:
        node_data = tree_data.get("nodes", {}).get(n["id"], {})
        sources = [s for s in tree_data.get("sources", []) if s["id"] in node_data.get("source_ids", [])]
        content = {
            "node_id": n["id"],
            "title": n.get("title", n["id"]),
            "summary": n.get("summary", node_data.get("summary", "")),
            "key_takeaways": n.get("key_takeaways", node_data.get("key_takeaways", [])),
            "dimensions": [d.get("title", d.get("name", "")) for d in node_data.get("quest", {}).get("dimensions", []) if isinstance(d, dict)],
            "source_summaries": [s.get("summary", "")[:200] for s in sources],
        }
        all_content.append(content)

    system_prompt = """You are an AI/ML technical interviewer and education expert. Generate high-quality quiz questions based on the student's learned knowledge.
Generate questions in English. Technical terms stay in English.

Quiz types:
1. concept_recall — Test understanding and recall of core concepts
2. application — Give a real-world work scenario, test how to apply knowledge
3. comparison — Test ability to distinguish and choose between similar concepts/tools/methods
4. system_design — Test architectural thinking and overall design ability

Answer formats:
- multiple_choice: 4 options, 1 correct answer
- open_ended: free-form answer, provide scoring rubric

Quality requirements (very important):
- Never ask pure data memorization questions (e.g., "how much did X grow?", "what year did Y happen?")
- Never ask questions that only require rote memorization
- All questions should test understanding, analysis, and application
- Concept Recall should ask "what is the core principle" not "what statistic"
- Application should give a real work scenario to reason through
- Comparison should test judgment on when to use A vs B
- System Design should have concrete constraints to test architectural thinking

Mix: approximately 60% multiple choice + 40% open-ended
Return strict JSON format."""

    user_prompt = f"""Generate 12 quiz questions (7 multiple choice + 5 open-ended) for the following topics, mixing all four quiz types.

Knowledge content:
{json.dumps(all_content, ensure_ascii=False, indent=2)}

Return JSON:
{{"quizzes": [
  {{
    "id": "q1",
    "node_id": "node_id_here",
    "quiz_type": "concept_recall",
    "format": "multiple_choice",
    "question": "Question text",
    "options": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"],
    "correct_answer": "A",
    "explanation": "Why this answer is correct (1-2 sentences)",
    "difficulty": "easy"
  }},
  {{
    "id": "q2",
    "node_id": "node_id_here",
    "quiz_type": "application",
    "format": "open_ended",
    "question": "Scenario description + question",
    "expected_points": ["Key point 1", "Key point 2", "Key point 3"],
    "hint": "Hint (optional)",
    "difficulty": "medium"
  }}
]}}

Rules:
- 12 questions: 7 multiple choice + 5 open-ended
- All four quiz types must appear, distribute as evenly as possible
- No duplicate or overly similar questions
- Multiple choice distractors should be plausible, not obviously wrong
- Open-ended expected_points are scoring rubric items (key info the user should mention)
- Application questions should have specific work scenarios (e.g., "You're responsible for a RAG system at your company...")
- System Design questions should have clear constraints (e.g., "100K documents, latency < 2s")
- Difficulty distribution: 3 easy + 6 medium + 3 hard
- Keep questions practical and work-oriented, not textbook-style

Good examples:
- "Your RAG system has high retrieval relevance but poor answer quality. What could be the cause?" (application)
- "RAG vs Fine-tuning: which would you choose when data updates frequently? Why?" (comparison)
- "Design an enterprise RAG system supporting 100K documents with latency < 3s. How would you architect it?" (system_design)

Bad examples (never generate these):
- "How much did AI security incidents grow from 2017-2023?" (pure memorization)
- "What year was MLflow released?" (meaningless trivia)
- "Which of the following is NOT an MLOps tool?" (too simple, no depth)"""

    try:
        result = _call_claude(system_prompt, user_prompt, max_tokens=6000)
        quizzes = result.get("quizzes", [])
        # Ensure each quiz has required fields
        for i, q in enumerate(quizzes):
            q.setdefault("id", f"q{i+1}")
            q.setdefault("format", "multiple_choice" if q.get("options") else "open_ended")
            q.setdefault("quiz_type", q.pop("type", "concept_recall"))
            # Normalize: if has options but no correct_answer, treat as open_ended
            if q["format"] == "multiple_choice" and not q.get("correct_answer"):
                q["format"] = "open_ended"
                q.setdefault("expected_points", q.pop("expected_answer_points", []))
        return quizzes
    except Exception as e:
        log.warning("Quiz generation failed: %s", e)
        return [
            {"id": f"q{i+1}", "node_id": n["id"], "quiz_type": "concept_recall",
             "format": "open_ended",
             "question": f"Recall the key concepts of '{n.get('title', n['id'])}'.",
             "hint": (n.get("summary") or "")[:100],
             "expected_points": n.get("key_takeaways", []),
             "difficulty": "medium"}
            for i, n in enumerate(nodes)
        ]


def _translate_quizzes_to_zh(quizzes: list[dict]) -> list[dict]:
    """Translate English quizzes to Chinese. Technical terms stay in English."""
    try:
        result = _call_claude(
            system_prompt="你是一个技术翻译专家。把英文 quiz 翻译成中文，技术名词保留英文。返回 JSON 对象。",
            user_prompt=f"""翻译以下 quiz 题目为中文。规则：
- 技术名词保留英文（Agent, RAG, Pipeline, Embedding, Fine-tuning 等）
- 风格像中国程序员日常讨论
- 选项也要翻译
- explanation 也要翻译
- expected_points 也要翻译
- hint 也要翻译
- 保持所有其他字段（id, node_id, quiz_type, format, difficulty, correct_answer）不变

{json.dumps(quizzes, ensure_ascii=False)}

返回 JSON 对象格式：{{"quizzes": [翻译后的题目数组]}}""",
            max_tokens=6000,
        )
        zh_quizzes = result.get("quizzes", [])
        if zh_quizzes:
            log.info("Quiz translation to zh succeeded: %d quizzes", len(zh_quizzes))
            return zh_quizzes
        log.warning("Quiz translation returned empty quizzes, keys: %s", list(result.keys()))
        return quizzes  # fallback to English
    except Exception as e:
        log.warning("Quiz translation to zh failed: %s", e)
        return quizzes  # fallback to English on error


def _evaluate_open_answer(question: str, user_answer: str, expected_points: list[str]) -> dict:
    """AI-evaluate an open-ended quiz answer against expected points."""
    try:
        result = _call_claude(
            system_prompt="You are a technical interview evaluator. Assess whether the candidate's answer covers the key points. Return strict JSON.",
            user_prompt=f"""Question: {question}

Candidate's answer: {user_answer}

Expected points (1 point each):
{json.dumps(expected_points, ensure_ascii=False)}

Evaluate whether the candidate mentioned each point. Return JSON:
{{
  "total_points": {len(expected_points)},
  "earned_points": 0,
  "point_results": [
    {{"point": "point text", "covered": true, "comment": "The candidate mentioned..."}}
  ],
  "overall_feedback": "Overall assessment (1-2 sentences, in Chinese with tech terms in English)",
  "score_percentage": 0.75
}}""",
            max_tokens=1500,
        )
        # Ensure numeric fields
        result.setdefault("total_points", len(expected_points))
        result.setdefault("earned_points", sum(1 for p in result.get("point_results", []) if p.get("covered")))
        result.setdefault("score_percentage", result["earned_points"] / max(result["total_points"], 1))
        return result
    except Exception as e:
        log.warning("Open answer evaluation failed: %s", e)
        return {
            "total_points": len(expected_points),
            "earned_points": 0,
            "point_results": [{"point": p, "covered": False, "comment": "评估失败"} for p in expected_points],
            "overall_feedback": f"AI 评估失败: {str(e)[:100]}",
            "score_percentage": 0,
        }


# ---------------------------------------------------------------------------
# Study-item conversion helper (used by auto-sync and study.py)
# ---------------------------------------------------------------------------

def _study_item_to_source(item: dict, analysis: dict) -> dict:
    """Convert a study item + analysis into source fields for the tech tree."""
    a = analysis.get("analysis", {})
    summary_block = a.get("summary", {})

    title = summary_block.get("title") or analysis.get("title") or item.get("title", "Untitled")
    concepts = summary_block.get("concepts", [])
    tags = sorted(set(c.strip().lower() for c in concepts if c.strip()))

    takeaways = summary_block.get("takeaways", [])
    actionable = summary_block.get("actionable", [])
    key_takeaways = takeaways + [f"[Action] {a_item}" for a_item in actionable]

    summary = ". ".join(takeaways[:3]) if takeaways else title

    sections = a.get("sections", [])
    raw_parts = []
    for sec in sections:
        sec_title = sec.get("title", "")
        sec_points = sec.get("key_points", [])
        if sec_title:
            raw_parts.append(f"## {sec_title}")
        raw_parts.extend(f"- {p}" for p in sec_points)
    raw_excerpt = "\n".join(raw_parts)

    return {
        "title": title,
        "type": item.get("type", "article"),
        "url": item.get("url", ""),
        "study_item_id": item.get("video_id") or analysis.get("video_id"),
        "summary": summary,
        "key_takeaways": key_takeaways,
        "tags": tags,
        "raw_excerpt": raw_excerpt,
        "captured_from": "study_sync",
    }


# ---------------------------------------------------------------------------
# Auto-sync study items
# ---------------------------------------------------------------------------

_auto_sync_done = False


def _auto_sync_study_items():
    """Silently check and import new study items."""
    global _auto_sync_done
    if _auto_sync_done:
        return
    _auto_sync_done = True

    try:
        study_videos_file = DATA_DIR / "study_videos.json"
        study_analyses_dir = DATA_DIR / "study_analyses"
        study_highlights_file = DATA_DIR / "study_highlights.json"

        study_data = load_json(study_videos_file, {"videos": []})
        done_items = [v for v in study_data.get("videos", []) if v.get("status") == "done"]
        if not done_items:
            return

        tree_data = _load_tree()
        existing_study_ids = {s.get("study_item_id") for s in tree_data.get("sources", []) if s.get("study_item_id")}

        to_import = [v for v in done_items if v.get("video_id", "") not in existing_study_ids]
        if not to_import:
            return

        highlights_data = load_json(study_highlights_file, {"highlights": []})
        highlights_by_article = {}
        for h in highlights_data.get("highlights", []):
            aid = h.get("article_id", "")
            if aid:
                highlights_by_article.setdefault(aid, []).append(h)

        template = _load_template()
        imported = 0
        total_xp = 0

        with _id_lock:
            for item in to_import:
                vid = item.get("video_id", "")
                analysis_path = study_analyses_dir / f"{vid}.json"
                if not analysis_path.exists():
                    continue
                try:
                    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
                except Exception:
                    continue

                source_data = _study_item_to_source(item, analysis)

                # Append highlights
                for h in highlights_by_article.get(vid, []):
                    line = f"\n\n📌 Highlight: {h.get('text', '')}"
                    if h.get("note"):
                        line += f"\n💬 Note: {h['note']}"
                    source_data["raw_excerpt"] += line

                source, node_ids, any_newly_lit = _add_source_and_classify(source_data, tree_data, template)
                imported += 1
                total_xp += 30  # source XP
                if any_newly_lit:
                    total_xp += 100 * sum(1 for nid in node_ids if tree_data["nodes"].get(nid, {}).get("status") != "locked")

            _save_tree(tree_data)

        if imported > 0:
            # Generate summaries for newly lit nodes
            for nid, node in tree_data.get("nodes", {}).items():
                if node.get("status") != "locked" and not node.get("summary"):
                    result = _generate_node_summary(nid, tree_data)
                    if result:
                        node["summary"] = result.get("summary", "")
                        node["key_takeaways"] = result.get("key_takeaways", [])
                        if result.get("tags"):
                            node["tags"] = sorted(set(node.get("tags", []) + result["tags"]))
                        node["updated_at"] = _now_iso()
            _save_tree(tree_data)

            if total_xp > 0:
                _award_xp(total_xp, f"auto-sync {imported} study items", tree_data)

            log.info("Auto-synced %d study items to tech tree", imported)
    except Exception as e:
        log.warning("Auto-sync study items failed: %s", e)


# ---------------------------------------------------------------------------
# Routes — Tech Tree & Hunter Profile
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/tech-tree")
def kt_tech_tree():
    """Return the full tech tree with node status, XP, confidence."""
    _auto_sync_study_items()
    template = _load_template()
    tree_data = _load_tree()
    nodes = tree_data.get("nodes", {})
    sources = tree_data.get("sources", [])

    # Build enriched tree structure
    def _enrich(tpl_node):
        node_data = nodes.get(tpl_node["id"])
        enriched = {
            "id": tpl_node["id"],
            "title": tpl_node.get("title", ""),
            "icon": tpl_node.get("icon"),
        }
        children = tpl_node.get("children", [])
        if children:
            enriched["children"] = [_enrich(c) for c in children]
            # Aggregate stats for intermediate nodes
            all_leaves = _get_leaves_under(tpl_node)
            leaf_ids = [l["id"] for l in all_leaves]
            lit_count = sum(1 for lid in leaf_ids if nodes.get(lid, {}).get("status") in ("lit", "mastered"))
            mastered_count = sum(1 for lid in leaf_ids if nodes.get(lid, {}).get("status") == "mastered")
            enriched["total_leaves"] = len(leaf_ids)
            enriched["lit_count"] = lit_count
            enriched["mastered_count"] = mastered_count
        else:
            # Leaf node — include full data
            if node_data:
                enriched.update({
                    "status": node_data.get("status", "locked"),
                    "confidence": node_data.get("confidence", 0),
                    "xp": node_data.get("xp", 0),
                    "source_count": len(node_data.get("source_ids", [])),
                    "summary": node_data.get("summary", ""),
                    "key_takeaways": node_data.get("key_takeaways", []),
                    "tags": node_data.get("tags", []),
                    "review_status": node_data.get("review_status"),
                    "first_lit_at": node_data.get("first_lit_at"),
                    "quest": node_data.get("quest"),
                })
            else:
                enriched.update({"status": "locked", "confidence": 0, "xp": 0, "source_count": 0})
            # Include guide from template for learning roadmap
            if tpl_node.get("guide"):
                enriched["guide"] = tpl_node["guide"]

        return enriched

    tree = _enrich(template.get("tree", {}))

    # Overall stats
    all_leaves = _get_all_leaves(template)
    total_leaves = len(all_leaves)
    lit_total = sum(1 for l in all_leaves if nodes.get(l["id"], {}).get("status") in ("lit", "mastered"))
    mastered_total = sum(1 for l in all_leaves if nodes.get(l["id"], {}).get("status") == "mastered")

    return jsonify({
        "ok": True,
        "tree": tree,
        "total_leaves": total_leaves,
        "lit_count": lit_total,
        "mastered_count": mastered_total,
        "total_sources": len(sources),
    })


@knowledge_tree_bp.route("/api/knowledge-tree/hunter-profile")
def kt_hunter_profile():
    """Return the hunter profile."""
    profile = _load_profile()
    return jsonify({"ok": True, "profile": profile})


@knowledge_tree_bp.route("/api/knowledge-tree/hunter-profile", methods=["PUT"])
def kt_update_hunter_profile():
    """Update hunter profile (e.g. hunter_name)."""
    body = request.get_json(silent=True) or {}
    profile = _load_profile()
    if "hunter_name" in body:
        profile["hunter_name"] = str(body["hunter_name"]).strip()[:50]
    _save_profile(profile)
    return jsonify({"ok": True, "profile": profile})


@knowledge_tree_bp.route("/api/knowledge-tree/award-xp", methods=["POST"])
def kt_award_xp():
    """Award XP (internal use). Body: {amount, reason}."""
    body = request.get_json(silent=True) or {}
    amount = int(body.get("amount", 0))
    reason = str(body.get("reason", "manual"))
    if amount <= 0:
        return jsonify({"ok": False, "error": "amount must be positive"}), 400
    result = _award_xp(amount, reason)
    return jsonify({"ok": True, **result})


# ---------------------------------------------------------------------------
# Routes — Node detail & sources
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/nodes/<node_id>")
def kt_get_node(node_id):
    """Get a single tech tree node with its linked sources."""
    tree_data = _load_tree()
    node = tree_data.get("nodes", {}).get(node_id)
    if not node:
        return jsonify({"ok": False, "error": "not found"}), 404

    # Get template info
    template = _load_template()
    title = node_id
    branch_path = ""
    branches = _get_top_level_branches(template)
    for branch in branches:
        for mid in branch.get("children", []):
            for leaf in mid.get("children", []):
                if leaf["id"] == node_id:
                    title = leaf["title"]
                    branch_path = f"{branch.get('icon', '')} {branch['title']} > {mid['title']}"
                    break

    # Get linked sources
    source_ids = node.get("source_ids", [])
    sources = [s for s in tree_data.get("sources", []) if s["id"] in source_ids]

    # Get related concepts (from edges)
    edges = tree_data.get("edges", [])
    related = []
    leaf_map = {l["id"]: l["title"] for l in _get_all_leaves(template)}
    nodes_dict = tree_data.get("nodes", {})
    for e in edges:
        if e.get("source_id") == node_id:
            tid = e["target_id"]
            related.append({"id": tid, "title": leaf_map.get(tid, tid), "status": nodes_dict.get(tid, {}).get("status", "locked"), "relation": e.get("relation")})
        elif e.get("target_id") == node_id:
            sid = e["source_id"]
            related.append({"id": sid, "title": leaf_map.get(sid, sid), "status": nodes_dict.get(sid, {}).get("status", "locked"), "relation": e.get("relation")})

    return jsonify({
        "ok": True,
        "node": {**node, "id": node_id, "title": title, "branch_path": branch_path},
        "sources": sources,
        "related": related,
    })


@knowledge_tree_bp.route("/api/knowledge-tree/nodes/<node_id>", methods=["PUT"])
def kt_update_node(node_id):
    """Update a tech tree node (confidence, review_status, summary, etc.)."""
    body = request.get_json(silent=True) or {}
    with _id_lock:
        tree_data = _load_tree()
        node = tree_data.get("nodes", {}).get(node_id)
        if not node:
            return jsonify({"ok": False, "error": "not found"}), 404

        for field in ("summary", "key_takeaways", "tags", "confidence"):
            if field in body:
                node[field] = body[field]

        if "review_status" in body:
            rs = body["review_status"]
            for k in ("ease_factor", "interval_days", "next_review", "review_count", "last_reviewed"):
                if k in rs:
                    node["review_status"][k] = rs[k]

        node["updated_at"] = _now_iso()
        _update_quest_progress(node, tree_data)
        _save_tree(tree_data)

    return jsonify({"ok": True, "node": {**node, "id": node_id}})


# ---------------------------------------------------------------------------
# Mind Map
# ---------------------------------------------------------------------------

def _find_node_in_template(node_id: str, template: dict) -> dict | None:
    """Find a node (branch, mid-level, or leaf) in the template tree by id."""
    def _walk(node):
        if node.get("id") == node_id:
            return node
        for child in node.get("children", []):
            found = _walk(child)
            if found:
                return found
        return None
    return _walk(template.get("tree", {}))


def _generate_branch_mindmap(branch_node: dict, tree_data: dict) -> dict:
    """Generate a mind map for a branch/mid-level node from its tree structure."""
    nodes_dict = tree_data.get("nodes", {})
    branches = []

    for child in branch_node.get("children", []):
        if child.get("children"):
            # Sub-branch with children (leaves)
            branch_data = {
                "id": child["id"],
                "label": child.get("title", child["id"]),
                "color": MINDMAP_COLORS[len(branches) % len(MINDMAP_COLORS)],
                "children": [],
            }
            for leaf in child.get("children", []):
                leaf_node = nodes_dict.get(leaf["id"], {})
                status = leaf_node.get("status", "locked")
                label = leaf.get("title", leaf["id"])
                if status != "locked" and leaf_node.get("key_takeaways"):
                    short = leaf_node["key_takeaways"][0][:30]
                    label = f"{label} — {short}..."
                branch_data["children"].append({
                    "id": leaf["id"], "label": label, "status": status,
                })
            branches.append(branch_data)
        else:
            # Direct leaf child
            leaf_node = nodes_dict.get(child["id"], {})
            status = leaf_node.get("status", "locked")
            children = []
            if leaf_node.get("key_takeaways"):
                children = [
                    {"id": f"{child['id']}_t{i}", "label": t[:50]}
                    for i, t in enumerate(leaf_node["key_takeaways"][:3])
                ]
            branches.append({
                "id": child["id"],
                "label": child.get("title", child["id"]),
                "color": MINDMAP_COLORS[len(branches) % len(MINDMAP_COLORS)],
                "status": status,
                "children": children,
            })

    return {
        "ok": True,
        "mindmap": {
            "center": branch_node.get("title", branch_node.get("id", "")),
            "branches": branches,
            "connections": [],
        },
        "cached": True,  # branch mindmaps are always derived from structure
    }


@knowledge_tree_bp.route("/api/knowledge-tree/mindmap/<node_id>")
def kt_get_mindmap(node_id):
    """Get or generate a mind map for any tech tree node (leaf or branch)."""
    lang = request.args.get("lang", "en")
    tree_data = _load_tree()
    template = _load_template()

    # Check if this is a branch/mid-level node in the template
    tpl_node = _find_node_in_template(node_id, template)
    if tpl_node and tpl_node.get("children"):
        # Branch or mid-level — generate from tree structure (no AI needed)
        return jsonify(_generate_branch_mindmap(tpl_node, tree_data))

    # Leaf node — need sources for AI generation
    node = tree_data.get("nodes", {}).get(node_id)
    if not node:
        return jsonify({"ok": False, "error": "not found"}), 404

    source_ids = node.get("source_ids", [])
    if not source_ids:
        return jsonify({"ok": False, "error": "no sources"}), 404

    # Check cache — zh has its own cache slot
    version_key = ",".join(sorted(source_ids))
    if lang == "zh":
        zh = node.get("zh", {})
        cached_zh = zh.get("mindmap")
        if cached_zh and zh.get("mindmap_version") == version_key:
            return jsonify({"ok": True, "mindmap": cached_zh, "cached": True})
    else:
        cached = node.get("mindmap")
        if cached and node.get("mindmap_version") == version_key:
            return jsonify({"ok": True, "mindmap": cached, "cached": True})

    # Collect source knowledge
    sources_by_id = {s["id"]: s for s in tree_data.get("sources", [])}
    sources = [sources_by_id[sid] for sid in source_ids if sid in sources_by_id]
    takeaways = []
    summaries = []
    for src in sources:
        takeaways.extend(src.get("key_takeaways", []))
        summaries.append(src.get("summary", ""))

    leaf_map = {l["id"]: l["title"] for l in _get_all_leaves(template)}
    node_with_title = {**node, "title": leaf_map.get(node_id, node_id)}

    try:
        mindmap = _generate_mindmap(node_with_title, takeaways, summaries, lang=lang)
    except Exception as e:
        log.warning("Failed to generate mindmap for %s: %s", node_id, e)
        return jsonify({"ok": False, "error": str(e)}), 500

    # Cache to node
    with _id_lock:
        tree_data = _load_tree()
        nd = tree_data.get("nodes", {}).get(node_id)
        if nd:
            if lang == "zh":
                zh = nd.setdefault("zh", {})
                zh["mindmap"] = mindmap
                zh["mindmap_version"] = version_key
            else:
                nd["mindmap"] = mindmap
                nd["mindmap_version"] = version_key
            _save_tree(tree_data)

    return jsonify({"ok": True, "mindmap": mindmap, "cached": False})


@knowledge_tree_bp.route("/api/knowledge-tree/generate-mindmaps", methods=["POST"])
def kt_generate_mindmaps():
    """Batch-generate mind maps for all nodes that have sources."""
    body = request.get_json(silent=True) or {}
    limit = min(body.get("limit", 5), 10)  # Cap at 10 per request to avoid timeout

    tree_data = _load_tree()
    template = _load_template()
    leaf_map = {l["id"]: l["title"] for l in _get_all_leaves(template)}
    nodes = tree_data.get("nodes", {})
    sources_by_id = {s["id"]: s for s in tree_data.get("sources", [])}
    generated_maps = {}  # nid -> {mindmap, mindmap_version}
    skipped = []
    count = 0

    for nid, node in nodes.items():
        if count >= limit:
            break
        source_ids = node.get("source_ids", [])
        if not source_ids:
            continue
        version_key = ",".join(sorted(source_ids))
        if node.get("mindmap") and node.get("mindmap_version") == version_key:
            skipped.append(nid)
            continue

        srcs = [sources_by_id[sid] for sid in source_ids if sid in sources_by_id]
        takeaways = []
        summaries = []
        for src in srcs:
            takeaways.extend(src.get("key_takeaways", []))
            summaries.append(src.get("summary", ""))

        node_with_title = {**node, "title": leaf_map.get(nid, nid)}
        try:
            mindmap = _generate_mindmap(node_with_title, takeaways, summaries)
            generated_maps[nid] = {"mindmap": mindmap, "mindmap_version": version_key}
            count += 1
            log.info("Generated mindmap for %s", nid)
        except Exception as e:
            log.warning("Failed to generate mindmap for %s: %s", nid, e)

    # Save under lock to avoid race with single-node endpoint
    if generated_maps:
        with _id_lock:
            fresh = _load_tree()
            for nid, data in generated_maps.items():
                nd = fresh.get("nodes", {}).get(nid)
                if nd:
                    nd["mindmap"] = data["mindmap"]
                    nd["mindmap_version"] = data["mindmap_version"]
            _save_tree(fresh)

    return jsonify({"ok": True, "generated": list(generated_maps.keys()), "skipped": skipped})


@knowledge_tree_bp.route("/api/knowledge-tree/sources")
def kt_list_sources():
    """List all sources, optionally filtered by node_id."""
    tree_data = _load_tree()
    sources = tree_data.get("sources", [])
    node_id = request.args.get("node_id", "").strip()
    if node_id:
        sources = [s for s in sources if node_id in s.get("node_ids", [])]
    return jsonify({"ok": True, "sources": sources})


@knowledge_tree_bp.route("/api/knowledge-tree/sources/<source_id>", methods=["DELETE"])
def kt_delete_source(source_id):
    """Delete a source and unlink it from nodes."""
    with _id_lock:
        tree_data = _load_tree()
        sources = tree_data.get("sources", [])
        source = next((s for s in sources if s["id"] == source_id), None)
        if not source:
            return jsonify({"ok": False, "error": "not found"}), 404

        # Unlink from nodes
        for nid in source.get("node_ids", []):
            node = tree_data.get("nodes", {}).get(nid)
            if node:
                node["source_ids"] = [sid for sid in node.get("source_ids", []) if sid != source_id]
                _update_quest_progress(node, tree_data)

        tree_data["sources"] = [s for s in sources if s["id"] != source_id]
        _save_tree(tree_data)

    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Routes — Stats
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/stats")
def kt_stats():
    """Summary statistics."""
    _auto_sync_study_items()
    tree_data = _load_tree()
    template = _load_template()
    nodes = tree_data.get("nodes", {})
    sources = tree_data.get("sources", [])

    all_leaves = _get_all_leaves(template)
    total_leaves = len(all_leaves)
    statuses = [nodes.get(l["id"], {}).get("status", "locked") for l in all_leaves]
    locked_count = sum(1 for s in statuses if s == "locked")
    in_progress_count = sum(1 for s in statuses if s == "in_progress")
    lit = sum(1 for s in statuses if s == "lit")
    mastered = sum(1 for s in statuses if s == "mastered")

    due_nodes = _get_due_nodes(tree_data)
    profile = _load_profile()

    return jsonify({
        "ok": True,
        "stats": {
            "total_leaves": total_leaves,
            "locked_count": locked_count,
            "in_progress_count": in_progress_count,
            "lit_count": lit,
            "mastered_count": mastered,
            "total_sources": len(sources),
            "due_for_review": len(due_nodes),
            "hunter_level": profile.get("level", 1),
            "hunter_rank": profile.get("rank", "E"),
            "total_xp": profile.get("total_xp", 0),
            "daily_streak": profile.get("daily_streak", 0),
        },
    })


@knowledge_tree_bp.route("/api/knowledge-tree/dashboard-stats")
def kt_dashboard_stats():
    """Comprehensive stats for the Stats dashboard tab."""
    tree_data = _load_tree()
    reviews_data = load_json(KNOWLEDGE_REVIEWS_FILE, {"reviews": []})
    profile = _load_profile()
    study_videos_raw = load_json(DATA_DIR / "study_videos.json", {})

    nodes = tree_data.get("nodes", {})
    reviews = reviews_data.get("reviews", [])
    videos = study_videos_raw if isinstance(study_videos_raw, list) else study_videos_raw.get("videos", [])
    titles = _build_title_map()

    # Helper: extract local date from ISO timestamp (handles UTC→local conversion)
    def _local_date(iso_str: str) -> str:
        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is not None:
                dt = dt.astimezone()  # convert to local timezone
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return iso_str[:10]  # fallback

    # === Daily activity (from reviews + videos timestamps) ===
    daily_activity = {}
    for r in reviews:
        date = _local_date(r.get("reviewed_at", ""))
        if date:
            daily_activity.setdefault(date, {"quizzes": 0, "articles": 0, "xp": 0})
            daily_activity[date]["quizzes"] += 1

    for v in videos:
        date = _local_date(v.get("started_at", ""))
        if date and v.get("status") == "done":
            daily_activity.setdefault(date, {"quizzes": 0, "articles": 0, "xp": 0})
            daily_activity[date]["articles"] += 1

    # Merge XP history into daily_activity
    for entry in profile.get("xp_history", []):
        date = entry.get("date", "")[:10]
        if date:
            daily_activity.setdefault(date, {"quizzes": 0, "articles": 0, "xp": 0})
            daily_activity[date]["xp"] += entry.get("amount", 0)

    # === Quiz stats ===
    total_quizzes = len(reviews)
    correct = sum(1 for r in reviews if r.get("result") in ("easy", "remembered"))
    wrong = sum(1 for r in reviews if r.get("result") == "forgot")
    accuracy = correct / total_quizzes if total_quizzes > 0 else 0

    # === Weekly quiz breakdown ===
    weekly_quiz = {}
    for r in reviews:
        date = _local_date(r.get("reviewed_at", ""))
        if date:
            try:
                dt = datetime.fromisoformat(date)
                week = dt.strftime("%Y-W%W")
                weekly_quiz.setdefault(week, {"total": 0, "correct": 0, "articles": 0})
                weekly_quiz[week]["total"] += 1
                if r.get("result") in ("easy", "remembered"):
                    weekly_quiz[week]["correct"] += 1
            except Exception:
                pass

    # Add articles to weekly breakdown
    for v in videos:
        date = _local_date(v.get("started_at", ""))
        if date and v.get("status") == "done":
            try:
                dt = datetime.fromisoformat(date)
                week = dt.strftime("%Y-W%W")
                weekly_quiz.setdefault(week, {"total": 0, "correct": 0, "articles": 0})
                weekly_quiz[week]["articles"] += 1
            except Exception:
                pass

    # === Branch stats (radar) ===
    stats_radar = profile.get("stats", {})

    # === Coverage ranking (closest to completion) ===
    coverage_ranking = []
    for nid, node in nodes.items():
        if node.get("status") == "in_progress":
            cov = node.get("quest", {}).get("progress", {}).get("overall_coverage", 0)
            threshold = node.get("quest", {}).get("coverage_threshold", 0.7)
            coverage_ranking.append({
                "node_id": nid,
                "title": titles.get(nid, node.get("title", nid)),
                "coverage": round(cov, 3),
                "threshold": threshold,
                "completion": round(min(cov / threshold, 1.0) if threshold > 0 else 0, 3),
            })
    coverage_ranking.sort(key=lambda x: x["completion"], reverse=True)

    # === Weakest areas (most wrong answers) ===
    wrong_by_node = {}
    for r in reviews:
        if r.get("result") == "forgot":
            nid = r.get("node_id", "")
            wrong_by_node[nid] = wrong_by_node.get(nid, 0) + 1
    wrong_ranking = sorted(wrong_by_node.items(), key=lambda x: x[1], reverse=True)[:5]
    wrong_ranking = [
        {"node_id": nid, "title": titles.get(nid, nid), "wrong_count": cnt}
        for nid, cnt in wrong_ranking
    ]

    return jsonify({
        "daily_activity": daily_activity,
        "weekly_quiz": weekly_quiz,
        "quiz_stats": {
            "total": total_quizzes,
            "correct": correct,
            "wrong": wrong,
            "accuracy": round(accuracy, 2),
        },
        "branch_stats": stats_radar,
        "coverage_ranking": coverage_ranking[:10],
        "wrong_ranking": wrong_ranking,
        "profile": {
            "level": profile.get("level", 1),
            "rank": profile.get("rank", "E"),
            "title": profile.get("title", ""),
            "xp": profile.get("total_xp", 0),
            "current_xp": profile.get("current_xp", 0),
            "xp_to_next": profile.get("xp_to_next_level", 100),
            "streak": profile.get("daily_streak", 0),
            "total_sources": len(tree_data.get("sources", [])),
            "nodes_in_progress": sum(1 for n in nodes.values() if n.get("status") == "in_progress"),
            "nodes_lit": sum(1 for n in nodes.values() if n.get("status") == "lit"),
            "nodes_mastered": sum(1 for n in nodes.values() if n.get("status") == "mastered"),
            "nodes_locked": sum(1 for n in nodes.values() if n.get("status") == "locked"),
        },
        "xp_history": profile.get("xp_history", []),
    })


# ---------------------------------------------------------------------------
# Routes — Recommended Tasks (Daily / Weekly Quests)
# ---------------------------------------------------------------------------

RECOMMENDED_TASKS_FILE = DATA_DIR / "recommended_tasks.json"
STUDY_VIDEOS_FILE = DATA_DIR / "study_videos.json"


def _get_leaves_from_branch(branch_node: dict) -> list[dict]:
    """Get all leaf nodes from a branch subtree."""
    leaves = []
    def _walk(node):
        children = node.get("children", [])
        if not children:
            leaves.append(node)
        else:
            for c in children:
                _walk(c)
    _walk(branch_node)
    return leaves


def _build_title_map() -> dict[str, str]:
    """Build node_id → title mapping from the template tree."""
    template = load_json(TECH_TREE_TEMPLATE_FILE, {"version": "1.0", "tree": {"children": []}})
    titles = {}
    def _walk(node):
        if "id" in node:
            titles[node["id"]] = node.get("title", node["id"])
        for c in node.get("children", []):
            _walk(c)
    _walk(template.get("tree", {}))
    return titles


def _generate_daily_quests(tree_data, reviews_data, profile, study_videos):
    """Generate up to 3 daily quests based on rules + data (no AI calls)."""
    quests = []
    now = datetime.utcnow()
    nodes = tree_data.get("nodes", {})
    titles = _build_title_map()
    reviews = reviews_data.get("reviews", [])

    # === Type 1: 📚 Read & Learn ===
    days_since = 99
    if study_videos:
        last_added = max((v.get("started_at", "") for v in study_videos), default="")
        try:
            last_time = datetime.fromisoformat(last_added.replace("Z", "+00:00"))
            days_since = (now - last_time.replace(tzinfo=None)).days
        except Exception:
            days_since = 99

    if days_since >= 1:
        quests.append({
            "id": "daily_read",
            "type": "read",
            "icon": "📚",
            "title": "Read & Learn",
            "short_desc": f"Add a new article to Study ({days_since}d since last)",
            "detail": f"You haven't added a new article in {days_since} days. Find an interesting AI/ML article, add it to Study, and let the system analyze it. This keeps your knowledge fresh and growing.",
            "actions": [
                "Browse your favorite AI blogs or newsletters",
                "Check Hacker News, Twitter, or arxiv for new content",
                "Paste a URL into the Study tab and click Analyze",
            ],
            "priority": "high" if days_since >= 3 else "medium",
            "xp_reward": 30,
            "node_id": None,
        })

    # === Type 2: 🧠 Review ===
    reviewed_nodes = {}
    for r in reviews:
        nid = r.get("node_id", "")
        reviewed_at = r.get("reviewed_at", "")
        if nid and reviewed_at > reviewed_nodes.get(nid, ""):
            reviewed_nodes[nid] = reviewed_at

    stale_nodes = []
    for nid, node in nodes.items():
        if node.get("status") in ("in_progress", "lit", "mastered") and node.get("source_ids"):
            last_review = reviewed_nodes.get(nid, "")
            if last_review:
                try:
                    lr_time = datetime.fromisoformat(last_review.replace("Z", "+00:00"))
                    days_stale = (now - lr_time.replace(tzinfo=None)).days
                except Exception:
                    days_stale = 99
            else:
                days_stale = 99
            if days_stale >= 3:
                stale_nodes.append((nid, node, days_stale))

    stale_nodes.sort(key=lambda x: x[2], reverse=True)

    if stale_nodes:
        nid, node, days = stale_nodes[0]
        quests.append({
            "id": f"daily_review_{nid}",
            "type": "review",
            "icon": "🧠",
            "title": "Review Knowledge",
            "short_desc": f'{titles.get(nid, nid)} — {days}d since last review',
            "detail": f'You haven\'t reviewed "{titles.get(nid, nid)}" in {days} days. Take a quick quiz to reinforce your knowledge before it fades.',
            "actions": [
                "Open the node and review the Mind Map",
                "Do a Knowledge Check quiz",
                "Re-read the Key Takeaways",
            ],
            "priority": "high" if days >= 7 else "medium",
            "xp_reward": 20,
            "node_id": nid,
        })

    # === Type 3: 🎯 Quiz ===
    unquizzed = []
    for nid, node in nodes.items():
        if node.get("status") == "in_progress" and node.get("source_ids"):
            progress = node.get("quest", {}).get("progress", {})
            if not progress.get("quiz_passed") and progress.get("quiz_attempts", 0) == 0:
                coverage = progress.get("overall_coverage", 0)
                unquizzed.append((nid, node, coverage))

    unquizzed.sort(key=lambda x: x[2], reverse=True)

    if unquizzed:
        nid, node, cov = unquizzed[0]
        quests.append({
            "id": f"daily_quiz_{nid}",
            "type": "quiz",
            "icon": "🎯",
            "title": "Knowledge Check",
            "short_desc": f'{titles.get(nid, nid)} — never quizzed',
            "detail": f'You\'ve been learning about "{titles.get(nid, nid)}" (coverage {cov * 100:.0f}%) but haven\'t tested yourself yet. Take a quiz to check your understanding.',
            "actions": [
                "Open the node",
                "Click Start Quiz",
                "Score 80%+ to pass",
            ],
            "priority": "medium",
            "xp_reward": 25,
            "node_id": nid,
        })

    # === Type 4: 📊 Fill Gaps ===
    weak_nodes = []
    for nid, node in nodes.items():
        if node.get("status") == "in_progress":
            dims = node.get("quest", {}).get("dimensions", [])
            dim_scores = node.get("quest", {}).get("progress", {}).get("dimension_scores", {})
            weak_dims = [d for d in dims if dim_scores.get(d["id"], 0) < 0.3]
            if weak_dims:
                weak_nodes.append((nid, node, weak_dims))

    if weak_nodes:
        nid, node, weak = weak_nodes[0]
        dim_names = ", ".join(d["title"] for d in weak[:2])
        quests.append({
            "id": f"daily_fill_{nid}",
            "type": "fill_gaps",
            "icon": "📊",
            "title": "Fill Knowledge Gaps",
            "short_desc": f'{titles.get(nid, nid)} — weak: {dim_names}',
            "detail": f'"{titles.get(nid, nid)}" has weak dimensions: {dim_names}. Find articles or resources that cover these areas to improve your coverage.',
            "actions": [
                f"Search for articles about {dim_names}",
                "Use Deep Research to find resources",
                "Add relevant articles to Study",
            ],
            "priority": "medium",
            "xp_reward": 30,
            "node_id": nid,
        })

    # === Type 5: 🔍 Explore ===
    locked_nodes = [(nid, n) for nid, n in nodes.items() if n.get("status") == "locked"]
    if locked_nodes:
        nid, node = random.choice(locked_nodes)
        quests.append({
            "id": f"daily_explore_{nid}",
            "type": "explore",
            "icon": "🔍",
            "title": "Explore New Concept",
            "short_desc": f'{titles.get(nid, nid)}',
            "detail": f'Expand your knowledge by exploring "{titles.get(nid, nid)}". Check the Deep Research report for recommended learning resources.',
            "actions": [
                "Open the node in the Tech Tree",
                "Read the learning guide",
                "Generate a Deep Research report",
            ],
            "priority": "low",
            "xp_reward": 10,
            "node_id": nid,
        })

    # === Type 6: 🔥 Streak ===
    streak = profile.get("daily_streak", 0)
    if streak >= 2:
        quests.append({
            "id": "daily_streak",
            "type": "streak",
            "icon": "🔥",
            "title": f"Keep the Streak! ({streak} days)",
            "short_desc": f"{streak} day learning streak — keep going!",
            "detail": f"You've been learning for {streak} consecutive days! Do any learning activity today to keep your streak alive and earn bonus XP.",
            "actions": [
                "Add an article to Study",
                "Do a quiz",
                "Review a node",
            ],
            "priority": "high",
            "xp_reward": streak * 5,
            "node_id": None,
        })

    priority_order = {"high": 0, "medium": 1, "low": 2}
    quests.sort(key=lambda q: priority_order.get(q["priority"], 1))
    return quests[:3]


def _generate_weekly_quests(tree_data, reviews_data, profile):
    """Generate up to 2 weekly quests based on rules + data (no AI calls)."""
    quests = []
    nodes = tree_data.get("nodes", {})
    titles = _build_title_map()

    # === Type 1: 🏆 Complete a Node ===
    almost_done = []
    for nid, node in nodes.items():
        if node.get("status") == "in_progress":
            progress = node.get("quest", {}).get("progress", {})
            coverage = progress.get("overall_coverage", 0)
            quiz_passed = progress.get("quiz_passed", False)
            threshold = node.get("quest", {}).get("coverage_threshold", 0.7)
            completion = (min(coverage / threshold, 1.0) * 0.5) + (0.5 if quiz_passed else 0)
            if completion > 0.3:
                almost_done.append((nid, node, completion, coverage))

    almost_done.sort(key=lambda x: x[2], reverse=True)

    if almost_done:
        nid, node, comp, coverage = almost_done[0]
        quests.append({
            "id": f"weekly_complete_{nid}",
            "type": "complete_node",
            "icon": "🏆",
            "title": "Light Up a Node",
            "short_desc": f'{titles.get(nid, nid)} — {comp * 100:.0f}% done',
            "detail": f'You\'re {comp * 100:.0f}% of the way to lighting up "{titles.get(nid, nid)}". Focus on filling knowledge gaps and passing the quiz this week.',
            "actions": [
                f"Coverage: {coverage * 100:.0f}% — find more resources to fill gaps",
                "Pass the Knowledge Check with 80%+",
                "Complete the optional Practice Task for bonus XP",
            ],
            "priority": "high",
            "xp_reward": 100,
            "node_id": nid,
        })

    # === Type 2: 📖 Deep Dive ===
    template = load_json(TECH_TREE_TEMPLATE_FILE, {"version": "1.0", "tree": {"children": []}})
    branches = template.get("tree", {}).get("children", [])

    branch_activity = []
    for branch in branches:
        leaves = _get_leaves_from_branch(branch)
        in_prog = sum(1 for l in leaves if nodes.get(l["id"], {}).get("status") == "in_progress")
        if in_prog >= 2:
            branch_activity.append((branch, in_prog))

    if branch_activity:
        branch_activity.sort(key=lambda x: x[1], reverse=True)
        branch, count = branch_activity[0]
        quests.append({
            "id": f'weekly_dive_{branch["id"]}',
            "type": "deep_dive",
            "icon": "📖",
            "title": f'Deep Dive: {branch.get("title", "")}',
            "short_desc": f"{count} concepts in progress — go deeper",
            "detail": f'You have {count} concepts in progress under "{branch.get("title", "")}". Focus on this branch this week to make solid progress.',
            "actions": [
                f'Add 2-3 articles related to {branch.get("title", "")}',
                "Complete quizzes for all in-progress nodes",
                "Aim to light up at least 1 node",
            ],
            "priority": "medium",
            "xp_reward": 200,
            "node_id": None,
        })

    # === Type 3: 🔄 Review Sprint ===
    now_iso = datetime.utcnow().isoformat()
    total_stale = sum(
        1 for nid, n in nodes.items()
        if n.get("status") in ("in_progress", "lit")
        and n.get("review_status", {}).get("next_review", "")
        and n["review_status"]["next_review"] < now_iso
    )

    if total_stale >= 3:
        quests.append({
            "id": "weekly_review_sprint",
            "type": "review_sprint",
            "icon": "🔄",
            "title": "Review Sprint",
            "short_desc": f"{total_stale} nodes overdue for review",
            "detail": f"You have {total_stale} nodes that are overdue for review. Clear them all this week to keep your knowledge fresh.",
            "actions": [
                "Use Start Review to go through overdue nodes",
                "Aim for 80%+ on each quiz",
                "Clear all overdue reviews by Friday",
            ],
            "priority": "high" if total_stale >= 5 else "medium",
            "xp_reward": total_stale * 15,
            "node_id": None,
        })

    return quests[:2]


@knowledge_tree_bp.route("/api/knowledge-tree/recommended-tasks")
def kt_recommended_tasks():
    """Get rule-based recommended learning tasks (daily + weekly). No AI calls."""
    tree_data = _load_tree()
    reviews_data = load_json(KNOWLEDGE_REVIEWS_FILE, {"reviews": []})
    profile = _load_profile()
    study_videos_data = load_json(STUDY_VIDEOS_FILE, {"videos": []})
    study_videos = study_videos_data.get("videos", []) if isinstance(study_videos_data, dict) else study_videos_data

    daily = _generate_daily_quests(tree_data, reviews_data, profile, study_videos)
    weekly = _generate_weekly_quests(tree_data, reviews_data, profile)

    return jsonify({
        "ok": True,
        "daily": daily,
        "weekly": weekly,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    })


# ---------------------------------------------------------------------------
# Routes — Learning Guides
# ---------------------------------------------------------------------------

def _generate_leaf_guides(template: dict) -> dict:
    """AI-generate learning guides for all leaf nodes. Returns {node_id: guide_dict}."""
    leaves = _get_all_leaves(template)
    branches = _get_top_level_branches(template)

    # Build branch path map for each leaf
    leaf_paths = {}
    for branch in branches:
        for mid in branch.get("children", []):
            for leaf in mid.get("children", []):
                leaf_paths[leaf["id"]] = f"{branch.get('icon', '')} {branch['title']} > {mid['title']}"

    # Build prerequisite map (leaves in same mid-level category)
    leaf_siblings = {}
    for branch in branches:
        for mid in branch.get("children", []):
            mid_leaves = [l["id"] for l in mid.get("children", [])]
            for lid in mid_leaves:
                leaf_siblings[lid] = [s for s in mid_leaves if s != lid]

    leaves_info = json.dumps(
        [{"id": l["id"], "title": l["title"], "branch_path": leaf_paths.get(l["id"], "")} for l in leaves],
        ensure_ascii=False,
    )

    prompt = (
        "Generate learning guides for the following tech tree leaf nodes. Each node needs:\n"
        "- what: 1-2 sentences explaining what this concept is (English)\n"
        "- why: 1 sentence explaining why to learn this (English)\n"
        "- resources: 2-3 learning suggestions (English)\n\n"
        f"Leaf node list:\n{leaves_info}\n\n"
        'Return JSON:\n'
        '{"guides": {"node_id": {"what": "...", "why": "...", "resources": ["...", "..."]}, ...}}'
    )

    # Split into batches of ~15 leaves to avoid token limits
    all_guides = {}
    batch_size = 15
    for i in range(0, len(leaves), batch_size):
        batch = leaves[i:i + batch_size]
        batch_info = json.dumps(
            [{"id": l["id"], "title": l["title"], "branch_path": leaf_paths.get(l["id"], "")} for l in batch],
            ensure_ascii=False,
        )
        batch_prompt = (
            "Generate learning guides for the following tech tree leaf nodes. Each node needs:\n"
            "- what: 1-2 sentences explaining what this concept is (English)\n"
            "- why: 1 sentence explaining why to learn this (English)\n"
            "- resources: 2-3 learning suggestions (English)\n\n"
            f"Leaf node list:\n{batch_info}\n\n"
            'Return JSON:\n'
            '{"guides": {"node_id": {"what": "...", "why": "...", "resources": ["...", "..."]}, ...}}'
        )
        try:
            result = _call_claude(
                system_prompt="You are an AI/ML learning consultant. Generate concise learning guides for tech tree nodes. Return strict JSON.",
                user_prompt=batch_prompt,
                max_tokens=3000,
            )
            all_guides.update(result.get("guides", {}))
        except Exception as e:
            log.warning("Failed to generate guides for batch %d: %s", i, e)

    # Add prerequisites from siblings
    for lid, guide in all_guides.items():
        guide["prerequisites"] = leaf_siblings.get(lid, [])

    log.info("Generated learning guides for %d leaf nodes", len(all_guides))
    return all_guides


@knowledge_tree_bp.route("/api/knowledge-tree/generate-guides", methods=["POST"])
def kt_generate_guides():
    """Generate AI learning guides for all leaf nodes and store in template."""
    template = _load_template()
    guides = _generate_leaf_guides(template)

    if not guides:
        return jsonify({"ok": False, "error": "Guide generation failed"}), 500

    # Store guides in template leaf nodes
    def _attach_guides(node):
        if not node.get("children"):
            guide = guides.get(node["id"])
            if guide:
                node["guide"] = guide
        else:
            for c in node["children"]:
                _attach_guides(c)

    _attach_guides(template.get("tree", {}))
    save_json(TECH_TREE_TEMPLATE_FILE, template)

    return jsonify({"ok": True, "guides_generated": len(guides)})


@knowledge_tree_bp.route("/api/knowledge-tree/node-guide/<node_id>")
def kt_node_guide(node_id):
    """Get learning guide for a specific node."""
    template = _load_template()
    tree_data = _load_tree()
    nodes = tree_data.get("nodes", {})

    # Find the leaf in template
    for leaf in _get_all_leaves(template):
        if leaf["id"] == node_id:
            guide = leaf.get("guide", {})
            # Add prerequisite status
            prereqs = []
            for pid in guide.get("prerequisites", []):
                for pl in _get_all_leaves(template):
                    if pl["id"] == pid:
                        status = nodes.get(pid, {}).get("status", "locked")
                        prereqs.append({"id": pid, "title": pl["title"], "status": status})
                        break

            # Build branch path
            branches = _get_top_level_branches(template)
            branch_path = ""
            for branch in branches:
                for mid in branch.get("children", []):
                    for l in mid.get("children", []):
                        if l["id"] == node_id:
                            branch_path = f"{branch.get('icon', '')} {branch['title']} > {mid['title']}"
                            break

            return jsonify({
                "ok": True,
                "node_id": node_id,
                "title": leaf["title"],
                "branch_path": branch_path,
                "guide": {
                    "what": guide.get("what", ""),
                    "why": guide.get("why", ""),
                    "resources": guide.get("resources", []),
                },
                "prerequisites": prereqs,
            })

    return jsonify({"ok": False, "error": "node not found"}), 404


# ---------------------------------------------------------------------------
# Helpers — Quest generation
# ---------------------------------------------------------------------------

def _default_quest(practice_task: dict | None = None, coverage_threshold: float = 0.7) -> dict:
    """Return a default quest config for a leaf node."""
    return {
        "dimensions": [],
        "coverage_threshold": coverage_threshold,
        "required_quiz_pass": True,
        "quiz_pass_threshold": 0.8,
        "practice_task": practice_task,
        "progress": {
            "sources_count": 0,
            "dimension_scores": {},
            "overall_coverage": 0,
            "source_coverages": {},
            "quiz_passed": False,
            "quiz_best_score": 0,
            "quiz_attempts": 0,
            "practice_completed": False,
        },
    }


def _generate_quests_for_all_nodes(tree_data: dict, template: dict):
    """AI-generate quest configs for all leaf nodes. Writes into tree_data['nodes']."""
    leaves = _get_all_leaves(template)
    branches = _get_top_level_branches(template)

    # Build branch path map
    leaf_paths = {}
    for branch in branches:
        for mid in branch.get("children", []):
            for leaf in mid.get("children", []):
                leaf_paths[leaf["id"]] = f"{branch.get('icon', '')} {branch['title']} > {mid['title']}"

    nodes = tree_data.get("nodes", {})
    generated = []

    # Process in batches
    batch_size = 15
    for i in range(0, len(leaves), batch_size):
        batch = leaves[i:i + batch_size]
        batch_info = json.dumps(
            [{"id": l["id"], "title": l["title"], "branch_path": leaf_paths.get(l["id"], "")} for l in batch],
            ensure_ascii=False,
        )
        prompt = (
            "Design learning quests for the following tech tree leaf nodes. Based on concept complexity, determine:\n"
            "- practice_task: Optional practice task description (string or null). Only set for concepts that truly need hands-on practice.\n"
            "  If setting practice_task, also set practice_required: true/false for whether it must be completed\n\n"
            f"Node list:\n{batch_info}\n\n"
            'Return JSON:\n'
            '{"quests": [{"node_id": "...", "practice_task": "..." or null, "practice_required": false}, ...]}\n\n'
            "Write all practice_task descriptions in English."
        )
        try:
            result = _call_claude(
                system_prompt="You are a learning course designer. Design appropriate learning quests for tech tree nodes based on concept complexity. Return strict JSON.",
                user_prompt=prompt,
                max_tokens=3000,
            )
            for q in result.get("quests", []):
                nid = q.get("node_id", "")
                node = nodes.get(nid)
                if not node:
                    continue

                practice = None
                if q.get("practice_task"):
                    practice = {
                        "description": q["practice_task"],
                        "required": bool(q.get("practice_required", False)),
                    }

                # Preserve existing progress and dimensions if re-generating
                old_quest = node.get("quest", {})
                old_progress = old_quest.get("progress", {})
                old_dims = old_quest.get("dimensions", [])
                old_threshold = old_quest.get("coverage_threshold", 0.7)
                quest = _default_quest(practice_task=practice)
                if old_dims:
                    quest["dimensions"] = old_dims
                    quest["coverage_threshold"] = old_threshold
                if old_progress:
                    quest["progress"] = old_progress

                node["quest"] = quest
                generated.append(nid)
        except Exception as e:
            log.warning("Failed to generate quests for batch %d: %s", i, e)

    # Fill in defaults for any leaves without quest configs
    for leaf in leaves:
        node = nodes.get(leaf["id"])
        if node and "quest" not in node:
            node["quest"] = _default_quest()
            generated.append(leaf["id"])

    log.info("Generated quest configs for %d leaf nodes", len(generated))
    return generated


def _check_quiz_completion(node_id: str, tree_data: dict) -> bool:
    """Check if a node's quiz requirements are met based on review history.

    Looks at last 5 reviews: easy=1.0, remembered=0.8, hard=0.5, forgot=0.
    If average >= quiz_pass_threshold (0.8), marks quiz as passed.
    Only evaluates when review count reaches milestones (3, 5, then every 5).
    Returns True if quiz was just passed.
    """
    node = tree_data.get("nodes", {}).get(node_id)
    if not node:
        return False

    quest = node.get("quest", {})
    if not quest:
        return False  # No quest config, skip

    progress = quest.get("progress", {})
    if progress.get("quiz_passed"):
        return False  # Already passed

    reviews_data = load_json(KNOWLEDGE_REVIEWS_FILE, {"reviews": [], "settings": {}})
    node_reviews = [r for r in reviews_data.get("reviews", []) if r.get("node_id") == node_id]

    review_count = len(node_reviews)
    if review_count < 3:
        return False  # Need at least 3 reviews

    # Only evaluate at meaningful milestones: 3, 5, then every 5 reviews
    check_points = {3, 5}
    if review_count not in check_points and review_count % 5 != 0:
        return False

    last_5 = node_reviews[-5:]
    score_map = {"easy": 1.0, "remembered": 0.8, "hard": 0.5, "forgot": 0}
    scores = [score_map.get(r.get("result", ""), 0) for r in last_5]
    avg_score = sum(scores) / len(scores)

    threshold = quest.get("quiz_pass_threshold", 0.8)
    progress["quiz_attempts"] = progress.get("quiz_attempts", 0) + 1
    progress["quiz_best_score"] = max(progress.get("quiz_best_score", 0), round(avg_score, 2))

    if avg_score >= threshold:
        progress["quiz_passed"] = True
        _update_node_status(node)
        return True

    return False


@knowledge_tree_bp.route("/api/knowledge-tree/generate-quests", methods=["POST"])
def kt_generate_quests():
    """Generate AI quest configs for all leaf nodes."""
    template = _load_template()

    with _id_lock:
        tree_data = _load_tree()
        generated = _generate_quests_for_all_nodes(tree_data, template)

        # Update quest progress for all nodes with sources
        for nid in generated:
            node = tree_data.get("nodes", {}).get(nid)
            if node:
                _update_quest_progress(node, tree_data)

        _save_tree(tree_data)

    return jsonify({"ok": True, "generated": len(generated), "nodes": generated})


@knowledge_tree_bp.route("/api/knowledge-tree/complete-practice", methods=["POST"])
def kt_complete_practice():
    """Mark a node's practice task as completed."""
    body = request.get_json(silent=True) or {}
    node_id = (body.get("node_id") or "").strip()
    if not node_id:
        return jsonify({"ok": False, "error": "node_id required"}), 400

    with _id_lock:
        tree_data = _load_tree()
        node = tree_data.get("nodes", {}).get(node_id)
        if not node:
            return jsonify({"ok": False, "error": "Node not found"}), 404

        quest = node.get("quest", {})
        if not quest.get("practice_task"):
            return jsonify({"ok": False, "error": "No practice task for this node"}), 400

        old_status = node.get("status")
        progress = quest.setdefault("progress", {})
        progress["practice_completed"] = True
        _update_node_status(node)
        _save_tree(tree_data)

    # Award XP
    xp_result = _award_xp(50, f"practice completed: {node_id}")

    return jsonify({
        "ok": True,
        "node_id": node_id,
        "node_status": node.get("status"),
        "xp_result": xp_result,
        "quest_completed": old_status == "in_progress" and node.get("status") in ("lit", "mastered"),
    })


# ---------------------------------------------------------------------------
# Routes — Dimension generation & coverage migration
# ---------------------------------------------------------------------------

def _generate_dimensions_for_all_nodes(tree_data: dict, template: dict):
    """AI-generate knowledge dimensions for all leaf nodes. Returns list of updated node IDs."""
    leaves = _get_all_leaves(template)
    nodes = tree_data.get("nodes", {})
    updated = []

    # Process in batches
    batch_size = 15
    for i in range(0, len(leaves), batch_size):
        batch = leaves[i:i + batch_size]
        batch_info = json.dumps(
            [{"id": l["id"], "title": l["title"]} for l in batch],
            ensure_ascii=False,
        )
        prompt = (
            "Design knowledge dimensions for the following AI/ML concept nodes. Each concept needs core dimensions to master (3-6), each with a weight (sum to 1.0).\n\n"
            f"Concept list:\n{batch_info}\n\n"
            'Return JSON:\n'
            '{"nodes": [{"node_id": "prod_patterns", "dimensions": [{"id": "architecture", "title": "Architecture Design", "weight": 0.3}, ...], "coverage_threshold": 0.7}, ...]}\n\n'
            "Rules:\n"
            "- 3-6 dimensions per concept\n"
            "- Dimension id in snake_case English\n"
            "- Dimension title in English\n"
            "- Weights sum to 1.0, more important dimensions get higher weight\n"
            "- coverage_threshold: simple concepts 0.6, moderate 0.7, complex 0.8\n"
            "- Dimensions should represent different aspects/angles of the concept, not details"
        )
        try:
            result = _call_claude(
                system_prompt="You are a curriculum design expert. Return strict JSON.",
                user_prompt=prompt,
                max_tokens=4000,
            )
            for item in result.get("nodes", []):
                nid = item.get("node_id", "")
                node = nodes.get(nid)
                if not node:
                    continue
                quest = node.setdefault("quest", _default_quest())
                quest["dimensions"] = item.get("dimensions", [])
                quest["coverage_threshold"] = item.get("coverage_threshold", 0.7)
                updated.append(nid)
        except Exception as e:
            log.warning("Failed to generate dimensions for batch %d: %s", i, e)

    log.info("Generated dimensions for %d leaf nodes", len(updated))
    return updated


@knowledge_tree_bp.route("/api/knowledge-tree/generate-dimensions", methods=["POST"])
def kt_generate_dimensions():
    """Generate knowledge dimensions for all leaf nodes and evaluate existing sources.

    1. AI generates 3-6 dimensions per leaf node
    2. Evaluates coverage for all existing sources
    3. Recalculates overall coverage and node statuses
    """
    template = _load_template()

    # Backup
    if KNOWLEDGE_TREE_FILE.exists():
        backup_path = str(KNOWLEDGE_TREE_FILE) + ".pre_dimensions_backup"
        shutil.copy2(KNOWLEDGE_TREE_FILE, backup_path)
        log.info("Dimensions migration: backup saved to %s", backup_path)

    with _id_lock:
        tree_data = _load_tree()

        # Step 1: Generate dimensions
        dim_updated = _generate_dimensions_for_all_nodes(tree_data, template)

        # Step 2: Evaluate coverage for existing sources on nodes that have dimensions
        sources_evaluated = 0
        nodes_with_sources = {
            nid: node for nid, node in tree_data.get("nodes", {}).items()
            if node.get("source_ids") and node.get("quest", {}).get("dimensions")
        }

        all_sources = {s["id"]: s for s in tree_data.get("sources", [])}

        for nid, node in nodes_with_sources.items():
            quest = node["quest"]
            progress = quest.setdefault("progress", {})
            sc = progress.setdefault("source_coverages", {})

            for sid in node.get("source_ids", []):
                if sid in sc:
                    continue  # Already evaluated
                source = all_sources.get(sid)
                if not source:
                    continue
                try:
                    scores = _evaluate_source_coverage(source, node)
                    if scores:
                        sc[sid] = scores
                        sources_evaluated += 1
                except Exception as e:
                    log.warning("Coverage eval failed for source %s on node %s: %s", sid, nid, e)

            # Recalculate coverage and status
            _update_coverage(node)
            _update_node_status(node)

        _save_tree(tree_data)

    return jsonify({
        "ok": True,
        "dimensions_generated": len(dim_updated),
        "nodes": dim_updated,
        "sources_evaluated": sources_evaluated,
        "backup": str(backup_path) if KNOWLEDGE_TREE_FILE.exists() else None,
    })


# ---------------------------------------------------------------------------
# Routes — Migration / Rebuild
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/migrate-quests", methods=["POST"])
def kt_migrate_quests():
    """Migrate existing tree to quest system.

    1. Backup knowledge_tree.json
    2. Generate quest configs for all leaf nodes
    3. Regress lit nodes to in_progress (quiz not passed yet)
    4. Recalculate XP (sources only, no lit bonuses)
    """
    template = _load_template()

    # Backup
    if KNOWLEDGE_TREE_FILE.exists():
        backup_path = str(KNOWLEDGE_TREE_FILE) + ".pre_quest_backup"
        shutil.copy2(KNOWLEDGE_TREE_FILE, backup_path)
        log.info("Quest migration: backup saved to %s", backup_path)

    with _id_lock:
        tree_data = _load_tree()

        # Generate quest configs
        generated = _generate_quests_for_all_nodes(tree_data, template)

        # Initialize progress from actual source counts and regress lit → in_progress
        regressed = 0
        for nid, node in tree_data.get("nodes", {}).items():
            quest = node.get("quest", {})
            progress = quest.get("progress", {})
            progress["sources_count"] = len(node.get("source_ids", []))
            progress["quiz_passed"] = False  # Nobody has passed quizzes yet
            progress["quiz_best_score"] = 0
            progress["quiz_attempts"] = 0
            progress["practice_completed"] = False

            old_status = node.get("status")
            _update_node_status(node)
            if old_status in ("lit", "mastered") and node.get("status") == "in_progress":
                regressed += 1

        _save_tree(tree_data)

    # Recalculate XP: sources only (30 each), no lit bonuses
    source_count = len(tree_data.get("sources", []))
    new_xp = source_count * 30

    profile = _load_profile()
    profile["total_xp"] = new_xp
    profile["current_xp"] = new_xp
    # Recalculate level
    level = 1
    xp_remaining = new_xp
    while True:
        xp_needed = xp_for_level(level)
        if xp_remaining >= xp_needed:
            xp_remaining -= xp_needed
            level += 1
        else:
            break
    profile["level"] = level
    profile["current_xp"] = xp_remaining
    profile["xp_to_next_level"] = xp_for_level(level)
    profile["rank"] = _rank_for_level(level)
    profile["title"] = _title_for_level(level)
    profile["subtitle"] = _subtitle_for_level(level)
    _save_profile(profile)

    log.info("Quest migration complete: %d quests generated, %d nodes regressed, XP=%d",
             len(generated), regressed, new_xp)

    return jsonify({
        "ok": True,
        "quests_generated": len(generated),
        "nodes_regressed": regressed,
        "new_xp": new_xp,
        "profile": profile,
        "backup": str(KNOWLEDGE_TREE_FILE) + ".pre_quest_backup",
    })


@knowledge_tree_bp.route("/api/knowledge-tree/rebuild-tree", methods=["POST"])
def kt_rebuild_tree():
    """Rebuild tech tree from template, migrating existing sources."""
    template = _load_template()
    all_leaves = _get_all_leaves(template)

    # Backup old data
    if KNOWLEDGE_TREE_FILE.exists():
        backup_path = str(KNOWLEDGE_TREE_FILE) + ".pre_rebuild_backup"
        shutil.copy2(KNOWLEDGE_TREE_FILE, backup_path)
        log.info("Knowledge Tree rebuild: backup saved to %s", backup_path)

    old_data = _load_tree()

    # Collect existing sources (from old format or current format)
    existing_sources = list(old_data.get("sources", []))

    # Also harvest sources from old-format nodes (concept/source hierarchy)
    old_nodes = old_data.get("nodes", []) if isinstance(old_data.get("nodes"), list) else []
    for n in old_nodes:
        src = n.get("source", {})
        if src.get("study_item_id") or src.get("url"):
            # Check not already in sources list
            study_id = src.get("study_item_id")
            if study_id and any(s.get("study_item_id") == study_id for s in existing_sources):
                continue
            existing_sources.append({
                "id": _next_source_id(existing_sources),
                "title": n.get("title", "Untitled"),
                "type": src.get("type", "article"),
                "url": src.get("url", ""),
                "study_item_id": study_id,
                "summary": n.get("summary", ""),
                "key_takeaways": n.get("key_takeaways", []),
                "tags": n.get("tags", []),
                "raw_excerpt": n.get("raw_excerpt", ""),
                "node_ids": [],
                "created_at": n.get("created_at", _now_iso()),
                "captured_from": "migration",
            })

    # Initialize all leaf nodes as unlit
    nodes_dict = {}
    for leaf in all_leaves:
        nodes_dict[leaf["id"]] = {
            "id": leaf["id"],
            "status": "locked",
            "confidence": 0,
            "xp": 0,
            "review_status": {
                "ease_factor": 2.5,
                "interval_days": 1,
                "next_review": None,
                "review_count": 0,
                "last_reviewed": None,
            },
            "summary": "",
            "key_takeaways": [],
            "tags": [],
            "source_ids": [],
            "first_lit_at": None,
            "updated_at": None,
        }

    new_tree_data = {
        "tech_tree_version": "1.0",
        "nodes": nodes_dict,
        "sources": [],
        "edges": [],
    }

    # Re-classify each existing source to tree nodes
    classified_count = 0
    newly_lit_nodes = set()

    for src in existing_sources:
        source, node_ids, any_newly_lit = _add_source_and_classify(src, new_tree_data, template)
        classified_count += 1
        if any_newly_lit:
            newly_lit_nodes.update(node_ids)
        log.info("Rebuild: classified source '%s' → %s", src.get("title", "")[:50], node_ids)

    # Generate summaries for lit nodes
    for nid, node in new_tree_data["nodes"].items():
        if node["status"] != "locked":
            result = _generate_node_summary(nid, new_tree_data)
            if result:
                node["summary"] = result.get("summary", "")
                node["key_takeaways"] = result.get("key_takeaways", [])
                if result.get("tags"):
                    node["tags"] = sorted(set(node.get("tags", []) + result["tags"]))
                node["updated_at"] = _now_iso()

    _save_tree(new_tree_data)

    # Generate quest configs for all leaf nodes
    try:
        _generate_quests_for_all_nodes(new_tree_data, template)
        for nid, node in new_tree_data["nodes"].items():
            _update_quest_progress(node, new_tree_data)
        _save_tree(new_tree_data)
    except Exception as e:
        log.warning("Quest generation during rebuild failed: %s", e)

    # Initialize hunter profile
    lit_count = sum(1 for n in new_tree_data["nodes"].values() if n["status"] != "locked")
    source_count = len(new_tree_data["sources"])
    initial_xp = lit_count * 100 + source_count * 30

    profile = _default_profile()
    _save_profile(profile)

    # Award initial XP
    xp_result = {}
    if initial_xp > 0:
        xp_result = _award_xp(initial_xp, f"initial migration: {lit_count} lit nodes, {source_count} sources", new_tree_data)

    log.info("Knowledge Tree rebuild complete: %d sources classified, %d nodes lit, %d initial XP",
             classified_count, lit_count, initial_xp)

    return jsonify({
        "ok": True,
        "sources_classified": classified_count,
        "nodes_lit": lit_count,
        "initial_xp": initial_xp,
        "xp_result": xp_result,
        "backup": str(KNOWLEDGE_TREE_FILE) + ".pre_rebuild_backup",
    })


# ---------------------------------------------------------------------------
# Routes — Capture (Chrome extension)
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/capture", methods=["POST"])
def kt_capture():
    """Receive conversation from Chrome extension, extract knowledge, classify to tree."""
    body = request.get_json(silent=True) or {}
    conversation = body.get("conversation", [])
    chat_id = body.get("chat_id", "")
    chat_title = body.get("chat_title", "Untitled")
    chat_url = body.get("chat_url", "")
    user_notes = body.get("user_notes", "")

    if not conversation:
        return jsonify({"ok": False, "error": "No conversation provided"}), 400

    log.info("Knowledge Tree capture: %d messages from '%s'", len(conversation), chat_title)

    formatted = _format_conversation(conversation)
    extracted = _extract_knowledge_with_ai(formatted, user_notes)
    knowledge_points = extracted.get("knowledge_points", [])

    if not knowledge_points:
        return jsonify({
            "ok": True, "sources_created": 0, "nodes_lit": [],
            "message": "No valuable knowledge points found.",
        })

    template = _load_template()
    xp_events = []
    all_node_ids = []

    with _id_lock:
        tree_data = _load_tree()

        for kp in knowledge_points:
            source_data = {
                "title": kp.get("title", "Untitled"),
                "type": "claude_chat",
                "url": chat_url,
                "study_item_id": None,
                "summary": kp.get("summary", ""),
                "key_takeaways": kp.get("key_takeaways", []),
                "tags": kp.get("tags", []),
                "raw_excerpt": kp.get("raw_excerpt", ""),
                "captured_from": "chrome_extension",
            }

            source, node_ids, any_newly_lit = _add_source_and_classify(source_data, tree_data, template)
            all_node_ids.extend(node_ids)

            xp = 30  # source XP
            if any_newly_lit:
                newly_lit_count = sum(1 for nid in node_ids
                                     if tree_data["nodes"].get(nid, {}).get("status") != "locked")
                xp += newly_lit_count * 100
            xp_events.append({"source": source["id"], "xp": xp, "nodes": node_ids})

        _save_tree(tree_data)

    # Award total XP
    total_xp = sum(e["xp"] for e in xp_events)
    xp_result = {}
    if total_xp > 0:
        xp_result = _award_xp(total_xp, f"capture: {len(knowledge_points)} knowledge points")

    # Generate summaries for newly lit nodes
    tree_data = _load_tree()
    for nid in set(all_node_ids):
        node = tree_data.get("nodes", {}).get(nid)
        if node and node.get("status") != "locked" and not node.get("summary"):
            result = _generate_node_summary(nid, tree_data)
            if result:
                node["summary"] = result.get("summary", "")
                node["key_takeaways"] = result.get("key_takeaways", [])
                node["updated_at"] = _now_iso()
    _save_tree(tree_data)

    return jsonify({
        "ok": True,
        "sources_created": len(knowledge_points),
        "nodes_lit": list(set(all_node_ids)),
        "xp_result": xp_result,
    })


# ---------------------------------------------------------------------------
# Routes — Review
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/review/due")
def kt_review_due():
    """Get nodes due for review."""
    tree_data = _load_tree()
    due = _get_due_nodes(tree_data)
    next_due = _get_next_due_time(tree_data) if not due else None

    # Enrich with template titles
    template = _load_template()
    leaf_map = {l["id"]: l["title"] for l in _get_all_leaves(template)}
    for d in due:
        d["title"] = leaf_map.get(d["id"], d["id"])

    return jsonify({"ok": True, "due_count": len(due), "nodes": due, "next_due": next_due})


@knowledge_tree_bp.route("/api/knowledge-tree/review/generate", methods=["POST"])
def kt_review_generate():
    """Generate AI review quizzes for due nodes or specific nodes.

    Supports quiz caching: when a single node is requested and its source_ids
    haven't changed, returns cached questions (randomly sampled 5 from pool).
    Pass force=true to regenerate.

    When mode='comprehensive' (or no node_ids given), enter comprehensive
    review: select 5-8 nodes by SRS priority and pull 1 cached question each.
    """
    body = request.get_json(silent=True) or {}
    batch_size = body.get("batch_size", 5)
    specific_node_ids = body.get("node_ids")  # Optional: quiz specific nodes
    force = body.get("force", False)
    mode = body.get("mode", "")
    lang = body.get("lang", "en") if body.get("lang") in ("en", "zh") else "en"
    log.info("Quiz requested: node_ids=%s, lang=%s, mode=%s, force=%s", specific_node_ids, lang, mode, force)

    tree_data = _load_tree()
    template = _load_template()
    leaf_map = {l["id"]: l["title"] for l in _get_all_leaves(template)}

    # ── Comprehensive Review Mode ──
    if mode == "comprehensive" or (not specific_node_ids and not body.get("batch_size")):
        reviews_data = load_json(KNOWLEDGE_REVIEWS_FILE, {"reviews": [], "settings": {}})
        selected = _select_review_nodes(tree_data, reviews_data, count=6)

        if not selected:
            return jsonify({"ok": True, "status": "no_nodes_available",
                            "message": "No nodes available for review",
                            "quizzes": [], "mode": "comprehensive_review"})

        quizzes = []
        for nid, node, reason in selected:
            cached = node.get("cached_quiz", {})
            pool = cached.get(lang, cached.get("en", []))

            if pool:
                q = dict(random.choice(pool))
                q["node_id"] = nid
                q["node_title"] = leaf_map.get(nid, nid)
                q["review_reason"] = reason
                quizzes.append(q)
            else:
                # Fallback: concept recall question
                title = leaf_map.get(nid, nid)
                takeaways = node.get("key_takeaways", [])[:3]
                quizzes.append({
                    "id": f"review_{nid}",
                    "node_id": nid,
                    "node_title": title,
                    "quiz_type": "concept_recall",
                    "format": "open_ended",
                    "question": f"Summarize the key concepts of {title} in 2-3 sentences.",
                    "expected_points": takeaways,
                    "difficulty": "medium",
                    "review_reason": reason,
                })

        random.shuffle(quizzes)

        return jsonify({
            "ok": True, "status": "ok",
            "mode": "comprehensive_review",
            "quizzes": quizzes,
            "node_count": len(selected),
            "total_due": len(_get_due_nodes(tree_data)),
        })

    if specific_node_ids:
        # Generate quizzes for specific nodes (e.g., quest quiz)
        target_nodes = []
        for nid in specific_node_ids:
            node = tree_data.get("nodes", {}).get(nid)
            if node and node.get("source_ids"):
                target_nodes.append({
                    "id": nid,
                    "title": leaf_map.get(nid, nid),
                    **{k: node[k] for k in ("confidence", "review_status", "summary", "key_takeaways", "tags") if k in node},
                })
        if not target_nodes:
            return jsonify({"ok": True, "status": "no_content", "quizzes": [], "total_due": 0})

        # --- Quiz caching for single-node quizzes ---
        if len(specific_node_ids) == 1 and len(target_nodes) == 1:
            nid = specific_node_ids[0]
            node = tree_data["nodes"][nid]
            current_sources = sorted(node.get("source_ids", []))
            cache_key = ",".join(current_sources)
            cached_quiz = node.get("cached_quiz")

            if not force and cached_quiz and cached_quiz.get("cache_key") == cache_key:
                # Check 30-day expiry (default expired if timestamp missing)
                generated_at = cached_quiz.get("generated_at", "")
                expired = True
                if generated_at:
                    try:
                        gen_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
                        expired = (datetime.now(timezone.utc) - gen_dt).days > 30
                    except (ValueError, TypeError):
                        expired = True
                pool = cached_quiz.get(lang, cached_quiz.get("en", []))
                if not expired and pool:
                    sample_size = min(5, len(pool))
                    quizzes = random.sample(pool, sample_size)
                    return jsonify({
                        "ok": True, "status": "ok", "quizzes": quizzes,
                        "total_due": len(_get_due_nodes(tree_data)),
                        "cached": True,
                    })
    else:
        target_nodes = _get_due_nodes(tree_data, limit=batch_size)
        if not target_nodes:
            next_due = _get_next_due_time(tree_data)
            return jsonify({"ok": True, "status": "no_reviews_due", "next_due": next_due, "quizzes": [], "total_due": 0})
        for d in target_nodes:
            d["title"] = leaf_map.get(d["id"], d["id"])

    related_context = _get_related_context(target_nodes, tree_data)
    all_quizzes_en = _generate_quizzes_with_ai(target_nodes, related_context)
    all_quizzes_zh = _translate_quizzes_to_zh(all_quizzes_en)

    # Cache the full pool (both languages) for single-node quizzes
    if specific_node_ids and len(specific_node_ids) == 1 and len(target_nodes) == 1 and len(all_quizzes_en) > 1:
        nid = specific_node_ids[0]
        with _id_lock:
            tree_data = _load_tree()
            node = tree_data["nodes"].get(nid)
            if node:
                current_sources = sorted(node.get("source_ids", []))
                # Clean up old per-language cache keys
                node.pop("cached_quiz_en", None)
                node.pop("cached_quiz_zh", None)
                node["cached_quiz"] = {
                    "cache_key": ",".join(current_sources),
                    "en": all_quizzes_en,
                    "zh": all_quizzes_zh,
                    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                save_json(KNOWLEDGE_TREE_FILE, tree_data)
        # Return random 5 from the newly generated pool in requested language
        pool = all_quizzes_zh if lang == "zh" else all_quizzes_en
        sample_size = min(5, len(pool))
        quizzes = random.sample(pool, sample_size)
    else:
        quizzes = all_quizzes_zh if lang == "zh" else all_quizzes_en

    return jsonify({
        "ok": True, "status": "ok", "quizzes": quizzes,
        "total_due": len(_get_due_nodes(tree_data)),
    })


@knowledge_tree_bp.route("/api/knowledge-tree/review/submit", methods=["POST"])
def kt_review_submit():
    """Submit review result, update SRS, award XP. Supports multiple_choice and open_ended."""
    body = request.get_json(silent=True) or {}
    node_id = (body.get("node_id") or "").strip()
    quiz_format = body.get("format", "multiple_choice")
    quiz_type = body.get("quiz_type", "concept_recall")
    question = body.get("question", "")
    time_spent = body.get("time_spent_seconds", 0)

    if not node_id:
        return jsonify({"ok": False, "error": "Missing node_id"}), 400

    # Determine result based on format
    evaluation = None
    score = 0.0

    if quiz_format == "multiple_choice":
        selected = body.get("selected_answer", "")
        correct = body.get("correct_answer", "")
        is_correct = selected == correct
        score = 1.0 if is_correct else 0.0
        result = "remembered" if is_correct else "forgot"
    elif quiz_format == "open_ended":
        user_answer = body.get("user_answer", "").strip()
        expected_points = body.get("expected_points", [])
        if not user_answer:
            return jsonify({"ok": False, "error": "Empty answer"}), 400
        evaluation = _evaluate_open_answer(question, user_answer, expected_points)
        score = evaluation.get("score_percentage", 0)
        if score >= 0.9:
            result = "easy"
        elif score >= 0.7:
            result = "remembered"
        elif score >= 0.4:
            result = "hard"
        else:
            result = "forgot"
    else:
        # Legacy self-rating format
        result = (body.get("result") or "forgot").strip()
        if result not in ("forgot", "hard", "remembered", "easy"):
            result = "forgot"
        score = {"easy": 1.0, "remembered": 0.8, "hard": 0.5, "forgot": 0}.get(result, 0)

    quest_completed = False
    with _id_lock:
        tree_data = _load_tree()
        node = tree_data.get("nodes", {}).get(node_id)
        if not node:
            return jsonify({"ok": False, "error": "Node not found"}), 404

        old_status = node.get("status")
        _update_srs(node, result)

        # Record review history — save complete quiz data for wrong answer book
        reviews_data = load_json(KNOWLEDGE_REVIEWS_FILE, {"reviews": [], "settings": {}})
        review_entry = {
            "node_id": node_id,
            "reviewed_at": _now_iso(),
            "quiz_type": quiz_type,
            "format": quiz_format,
            "question": question,
            "result": result,
            "score": round(score, 2),
            "time_spent_seconds": time_spent,
            "difficulty": body.get("difficulty", ""),
            "session_id": body.get("session_id", ""),
        }
        if quiz_format == "multiple_choice":
            review_entry["options"] = body.get("options", [])
            review_entry["correct_answer"] = body.get("correct_answer", "")
            review_entry["user_answer"] = body.get("selected_answer", "")
            review_entry["explanation"] = body.get("explanation", "")
        elif quiz_format == "open_ended":
            review_entry["expected_points"] = body.get("expected_points", [])
            review_entry["user_answer"] = body.get("user_answer", "")
            if evaluation:
                review_entry["evaluation"] = evaluation
        reviews_data.setdefault("reviews", []).append(review_entry)
        save_json(KNOWLEDGE_REVIEWS_FILE, reviews_data)

        # Check quest quiz completion
        quiz_just_passed = _check_quiz_completion(node_id, tree_data)
        if quiz_just_passed and node.get("status") in ("lit", "mastered") and old_status == "in_progress":
            quest_completed = True

        _save_tree(tree_data)

        new_interval = node["review_status"]["interval_days"]
        next_review = node["review_status"]["next_review"]
        confidence = node["confidence"]
        new_status = node.get("status")

    # Award XP
    xp_map = {"easy": 25, "remembered": 20, "hard": 10, "forgot": 5}
    xp = xp_map.get(result, 10)
    quest_bonus = 100 if quest_completed else 0
    mastered_bonus = 200 if new_status == "mastered" and old_status != "mastered" else 0

    profile = _load_profile()
    _update_streak(profile)
    streak_bonus = profile.get("daily_streak", 0) * 5
    _save_profile(profile)

    total_xp = xp + mastered_bonus + streak_bonus + quest_bonus
    xp_result = _award_xp(total_xp, f"review: {result} on {node_id}")

    # Daily login bonus
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_reviews = [r for r in reviews_data.get("reviews", []) if r.get("reviewed_at", "").startswith(today_prefix)]
    if len(today_reviews) == 1:
        _award_xp(15, "daily review login bonus")

    log.info("Review: %s → %s (format=%s, score=%.2f, xp=%d)", node_id, result, quiz_format, score, total_xp)

    resp = {
        "ok": True,
        "node_id": node_id,
        "result": result,
        "score": round(score, 2),
        "new_interval": new_interval,
        "next_review": next_review,
        "confidence": confidence,
        "xp_result": xp_result,
        "quest_completed": quest_completed,
    }
    if evaluation:
        resp["evaluation"] = evaluation
    return jsonify(resp)


@knowledge_tree_bp.route("/api/knowledge-tree/review/complete-bonus", methods=["POST"])
def kt_review_complete_bonus():
    """Award bonus XP for completing a comprehensive review session."""
    body = request.get_json(silent=True) or {}
    all_correct = body.get("all_correct", False)
    node_count = body.get("node_count", 0)

    completion_xp = 15
    perfect_xp = 30 if all_correct else 0
    total = completion_xp + perfect_xp

    reason = f"comprehensive review completion ({node_count} nodes)"
    if all_correct:
        reason += " — perfect!"
    xp_result = _award_xp(total, reason)
    log.info("Comprehensive review bonus: %d XP (all_correct=%s, nodes=%d)", total, all_correct, node_count)

    return jsonify({"ok": True, "bonus_xp": total, "xp_result": xp_result})


@knowledge_tree_bp.route("/api/knowledge-tree/review/stats")
def kt_review_stats():
    """Review statistics."""
    tree_data = _load_tree()
    reviews_data = load_json(KNOWLEDGE_REVIEWS_FILE, {"reviews": [], "settings": {}})
    reviews = reviews_data.get("reviews", [])
    profile = _load_profile()

    due_nodes = _get_due_nodes(tree_data)
    next_due = _get_next_due_time(tree_data) if not due_nodes else None

    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_reviews = [r for r in reviews if r.get("reviewed_at", "").startswith(today_prefix)]

    by_result = {"forgot": 0, "hard": 0, "remembered": 0, "easy": 0}
    for r in reviews:
        res = r.get("result", "")
        if res in by_result:
            by_result[res] += 1

    nodes = tree_data.get("nodes", {})
    confidences = [n.get("confidence", 0) for n in nodes.values() if n.get("status") != "locked"]
    avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0

    return jsonify({
        "ok": True,
        "stats": {
            "total_reviews": len(reviews),
            "due_now": len(due_nodes),
            "next_due": next_due,
            "avg_confidence": avg_confidence,
            "streak_days": profile.get("daily_streak", 0),
            "today_reviews": len(today_reviews),
            "by_result": by_result,
        },
    })


@knowledge_tree_bp.route("/api/knowledge-tree/review/history")
def kt_review_history():
    """Recent review history. Optional ?node_id= to filter by node."""
    limit = request.args.get("limit", 50, type=int)
    node_id = request.args.get("node_id", "").strip()
    reviews_data = load_json(KNOWLEDGE_REVIEWS_FILE, {"reviews": [], "settings": {}})
    reviews = reviews_data.get("reviews", [])
    if node_id:
        reviews = [r for r in reviews if r.get("node_id") == node_id]
    reviews_sorted = sorted(reviews, key=lambda r: r.get("reviewed_at", ""), reverse=True)
    return jsonify({"ok": True, "reviews": reviews_sorted[:limit], "total": len(reviews)})


# ---------------------------------------------------------------------------
# Routes — Graph
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/graph")
def kt_graph():
    """Return D3 graph data for tech tree visualization."""
    template = _load_template()
    tree_data = _load_tree()
    nodes = tree_data.get("nodes", {})

    graph_nodes = []
    graph_edges = []

    # Add all template nodes (branches, intermediates, leaves)
    def _walk_template(tpl_node, parent_id=None, depth=0):
        nid = tpl_node["id"]
        children = tpl_node.get("children", [])
        is_leaf = not children

        node_data = nodes.get(nid, {}) if is_leaf else {}
        graph_node = {
            "id": nid,
            "title": tpl_node.get("title", nid),
            "icon": tpl_node.get("icon"),
            "depth": depth,
            "is_leaf": is_leaf,
            "status": node_data.get("status", "locked") if is_leaf else "branch",
            "confidence": node_data.get("confidence", 0) if is_leaf else 0,
            "source_count": len(node_data.get("source_ids", [])) if is_leaf else 0,
        }

        if is_leaf:
            rs = node_data.get("review_status", {})
            graph_node["review_count"] = rs.get("review_count", 0)
            graph_node["is_due"] = bool(rs.get("next_review") and rs["next_review"] <= _now_iso())

        if not is_leaf:
            all_leaves = _get_leaves_under(tpl_node)
            leaf_ids = [l["id"] for l in all_leaves]
            lit_count = sum(1 for lid in leaf_ids if nodes.get(lid, {}).get("status") in ("lit", "mastered"))
            graph_node["lit_count"] = lit_count
            graph_node["total_leaves"] = len(leaf_ids)

        graph_nodes.append(graph_node)

        if parent_id:
            graph_edges.append({"source": parent_id, "target": nid, "relation": "parent_child"})

        for c in children:
            _walk_template(c, nid, depth + 1)

    _walk_template(template.get("tree", {}))

    # Add user-created edges
    for e in tree_data.get("edges", []):
        graph_edges.append({
            "source": e["source_id"], "target": e["target_id"],
            "relation": e.get("relation", "related_to"),
            "strength": e.get("strength", 0.5),
        })

    return jsonify({"ok": True, "nodes": graph_nodes, "edges": graph_edges})


# ---------------------------------------------------------------------------
# Routes — Search
# ---------------------------------------------------------------------------

_embed_model = None
_embed_model_lock = threading.Lock()


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        with _embed_model_lock:
            if _embed_model is None:
                from sentence_transformers import SentenceTransformer
                _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
                log.info("Loaded embedding model for knowledge tree")
    return _embed_model


@knowledge_tree_bp.route("/api/knowledge-tree/search", methods=["POST"])
def kt_search():
    """Semantic search over sources and nodes."""
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    limit = body.get("limit", 10)

    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    tree_data = _load_tree()
    sources = tree_data.get("sources", [])
    if not sources:
        return jsonify({"ok": True, "results": [], "query": query})

    try:
        model = _get_embed_model()
        texts = [f"{s.get('title', '')}. {s.get('summary', '')}. {' '.join(s.get('tags', []))}" for s in sources]
        embeddings = model.encode(texts, normalize_embeddings=True).astype(np.float32)

        import faiss
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        query_vec = model.encode([query], normalize_embeddings=True).astype(np.float32)
        k = min(limit, len(sources))
        scores, indices = index.search(query_vec, k)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(sources):
                s = sources[idx]
                results.append({
                    "source": {"id": s["id"], "title": s.get("title", ""), "summary": s.get("summary", ""), "node_ids": s.get("node_ids", [])},
                    "score": round(float(scores[0][i]), 4),
                })

        return jsonify({"ok": True, "results": results, "query": query})
    except Exception as e:
        log.warning("Search failed: %s", e)
        return jsonify({"ok": False, "error": "Search unavailable"}), 503


# ---------------------------------------------------------------------------
# Routes — Study item import (batch, for backwards compat)
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/import-study-items", methods=["POST"])
def kt_import_study_items():
    """Batch import study items as sources."""
    study_videos_file = DATA_DIR / "study_videos.json"
    study_analyses_dir = DATA_DIR / "study_analyses"
    study_highlights_file = DATA_DIR / "study_highlights.json"

    study_data = load_json(study_videos_file, {"videos": []})
    done_items = [v for v in study_data.get("videos", []) if v.get("status") == "done"]

    tree_data = _load_tree()
    existing_study_ids = {s.get("study_item_id") for s in tree_data.get("sources", []) if s.get("study_item_id")}

    highlights_data = load_json(study_highlights_file, {"highlights": []})
    highlights_by_article = {}
    for h in highlights_data.get("highlights", []):
        aid = h.get("article_id", "")
        if aid:
            highlights_by_article.setdefault(aid, []).append(h)

    template = _load_template()
    imported = 0
    skipped = 0
    total_xp = 0

    with _id_lock:
        for item in done_items:
            vid = item.get("video_id", "")
            if vid in existing_study_ids:
                skipped += 1
                continue

            analysis_path = study_analyses_dir / f"{vid}.json"
            if not analysis_path.exists():
                skipped += 1
                continue

            try:
                analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            except Exception:
                skipped += 1
                continue

            source_data = _study_item_to_source(item, analysis)

            for h in highlights_by_article.get(vid, []):
                line = f"\n\n📌 Highlight: {h.get('text', '')}"
                if h.get("note"):
                    line += f"\n💬 Note: {h['note']}"
                source_data["raw_excerpt"] += line

            source, node_ids, any_newly_lit = _add_source_and_classify(source_data, tree_data, template)
            imported += 1
            total_xp += 30
            if any_newly_lit:
                total_xp += 100

        _save_tree(tree_data)

    xp_result = {}
    if total_xp > 0:
        xp_result = _award_xp(total_xp, f"import {imported} study items")

    log.info("Knowledge Tree import: %d imported, %d skipped", imported, skipped)

    return jsonify({
        "ok": True, "imported": imported, "skipped": skipped,
        "xp_result": xp_result,
    })


# ---------------------------------------------------------------------------
# Routes — Edges
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/edges")
def kt_list_edges():
    data = _load_tree()
    return jsonify({"ok": True, "edges": data.get("edges", [])})


@knowledge_tree_bp.route("/api/knowledge-tree/edges", methods=["POST"])
def kt_create_edge():
    body = request.get_json(silent=True) or {}
    source_id = str(body.get("source_id") or "").strip()
    target_id = str(body.get("target_id") or "").strip()

    if not source_id or not target_id:
        return jsonify({"ok": False, "error": "source_id and target_id required"}), 400
    if source_id == target_id:
        return jsonify({"ok": False, "error": "cannot link node to itself"}), 400

    with _id_lock:
        data = _load_tree()
        edges = data.get("edges", [])

        for e in edges:
            if e.get("source_id") == source_id and e.get("target_id") == target_id:
                return jsonify({"ok": True, "edge": e, "duplicate": True})

        max_num = 0
        for e in edges:
            try:
                max_num = max(max_num, int(e["id"].split("_")[1]))
            except (ValueError, IndexError):
                pass

        edge = {
            "id": f"ke_{max_num + 1}",
            "source_id": source_id,
            "target_id": target_id,
            "relation": body.get("relation", "related_to"),
            "strength": body.get("strength", 0.5),
            "auto_generated": False,
            "created_at": _now_iso(),
        }
        edges.append(edge)
        data["edges"] = edges
        _save_tree(data)

    return jsonify({"ok": True, "edge": edge}), 201


@knowledge_tree_bp.route("/api/knowledge-tree/edges/<edge_id>", methods=["DELETE"])
def kt_delete_edge(edge_id):
    with _id_lock:
        data = _load_tree()
        before = len(data.get("edges", []))
        data["edges"] = [e for e in data.get("edges", []) if e["id"] != edge_id]
        if len(data["edges"]) == before:
            return jsonify({"ok": False, "error": "not found"}), 404
        _save_tree(data)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Routes — Backwards compat (kept for study.py import)
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/topics")
def kt_topics():
    """Return branch-level topic info."""
    template = _load_template()
    tree_data = _load_tree()
    nodes = tree_data.get("nodes", {})
    branches = _get_top_level_branches(template)

    topics = []
    for b in branches:
        leaves = _get_leaves_under(b)
        leaf_ids = [l["id"] for l in leaves]
        lit = sum(1 for lid in leaf_ids if nodes.get(lid, {}).get("status") in ("lit", "mastered"))
        topics.append({"topic": b["title"], "branch_id": b["id"], "icon": b.get("icon"), "count": lit, "total": len(leaf_ids)})

    return jsonify({"ok": True, "topics": topics})


# ---------------------------------------------------------------------------
# Audio Overview — AI Podcast via ElevenLabs TTS
# ---------------------------------------------------------------------------

AUDIO_DIR = DATA_DIR / "audio_overviews"
os.makedirs(AUDIO_DIR, exist_ok=True)

# ElevenLabs voice IDs — update after checking /audio/voices
HOST_A_VOICE = "iP95p4xoKVk53GoZ742B"   # Chris — charming, casual (Alex)
HOST_B_VOICE = "XrExE9yKIg1WjnnlVkGX"   # Matilda — knowledgeable, upbeat (Sam)


@knowledge_tree_bp.route("/api/knowledge-tree/audio/voices", methods=["GET"])
def kt_audio_voices():
    """List available ElevenLabs voices for selection."""
    try:
        from elevenlabs import ElevenLabs
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            return jsonify({"error": "ELEVENLABS_API_KEY not set"}), 500
        client = ElevenLabs(api_key=api_key)
        voices = client.voices.get_all()
        result = []
        for v in voices.voices:
            result.append({
                "voice_id": v.voice_id,
                "name": v.name,
                "labels": dict(v.labels) if v.labels else {},
            })
        return jsonify({"ok": True, "voices": result})
    except Exception as e:
        log.warning("Failed to list voices: %s", e)
        return jsonify({"error": str(e)}), 500


def _audio_path_for(node_id: str, lang: str) -> "pathlib.Path":
    suffix = f"_{lang}" if lang != "en" else ""
    return AUDIO_DIR / f"{node_id}{suffix}.mp3"


def _audio_url_for(node_id: str, lang: str) -> str:
    q = f"?lang={lang}" if lang != "en" else ""
    return f"/api/knowledge-tree/audio/{node_id}{q}"


@knowledge_tree_bp.route("/api/knowledge-tree/audio/<node_id>/status", methods=["GET"])
def kt_audio_status(node_id):
    """Check whether audio has been generated (both en and zh)."""
    result = {}
    for lang in ("en", "zh"):
        p = _audio_path_for(node_id, lang)
        exists = p.exists()
        result[lang] = {"exists": exists, "url": _audio_url_for(node_id, lang) if exists else None}
    return jsonify(result)


@knowledge_tree_bp.route("/api/knowledge-tree/audio/<node_id>", methods=["GET"])
def kt_audio_serve(node_id):
    """Serve the generated audio file."""
    lang = request.args.get("lang", "en")
    audio_path = _audio_path_for(node_id, lang)
    if not audio_path.exists():
        return jsonify({"error": "Audio not generated yet"}), 404
    return send_file(str(audio_path), mimetype="audio/mpeg")


@knowledge_tree_bp.route("/api/knowledge-tree/audio/<node_id>/generate", methods=["POST"])
def kt_audio_generate(node_id):
    """Generate Audio Overview: podcast script via Claude + TTS via ElevenLabs."""
    lang = request.args.get("lang", "en")
    if lang not in ("en", "zh"):
        return jsonify({"error": "Unsupported lang, use en or zh"}), 400

    tree_data = _load_tree()
    node = tree_data.get("nodes", {}).get(node_id)
    if not node:
        return jsonify({"error": "Node not found"}), 404

    if node.get("status") == "locked":
        return jsonify({"error": "Cannot generate audio for locked nodes"}), 400

    audio_path = _audio_path_for(node_id, lang)
    if audio_path.exists():
        return jsonify({"status": "exists", "url": _audio_url_for(node_id, lang)})

    # Gather rich knowledge content
    all_sources = tree_data.get("sources", [])
    source_ids = set(node.get("source_ids", []))
    node_sources = [s for s in all_sources if s["id"] in source_ids]
    all_takeaways = []
    for src in node_sources:
        all_takeaways.extend(src.get("key_takeaways", []))

    title = node.get("title", node_id)
    summary = node.get("summary", "")

    if not all_takeaways and not summary:
        return jsonify({"error": "Node has no content to discuss"}), 400

    # Quest dimensions
    quest = node.get("quest", {})
    dimensions = quest.get("dimensions", [])
    dim_scores = quest.get("progress", {}).get("dimension_scores", {})

    # Mind map summary
    mindmap = node.get("mindmap")
    mindmap_summary = ""
    if mindmap and mindmap.get("branches"):
        parts = []
        for b in mindmap["branches"]:
            children = ", ".join(c.get("label", "?") for c in b.get("children", [])[:5])
            parts.append(f"  {b.get('label', '?')}: {children}")
        mindmap_summary = "\n".join(parts)

    # 1. Generate podcast script via Claude
    try:
        script = _generate_podcast_script(
            title, summary, all_takeaways,
            lang=lang,
            sources=node_sources,
            dimensions=dimensions,
            dim_scores=dim_scores,
            mindmap_summary=mindmap_summary,
        )
    except Exception as e:
        log.warning("Podcast script generation failed for %s (%s): %s", node_id, lang, e)
        return jsonify({"error": f"Script generation failed: {e}"}), 500

    # 2. Synthesize audio via ElevenLabs
    try:
        audio_bytes = _synthesize_podcast(script)
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

        # Save script for debugging / subtitles
        suffix = f"_{lang}" if lang != "en" else ""
        script_path = AUDIO_DIR / f"{node_id}{suffix}_script.json"
        with open(script_path, "w") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)

        return jsonify({
            "status": "generated",
            "url": _audio_url_for(node_id, lang),
            "duration_segments": len(script.get("dialogue", [])),
        })
    except Exception as e:
        log.warning("Audio synthesis failed for %s (%s): %s", node_id, lang, e)
        return jsonify({"error": f"Audio synthesis failed: {e}"}), 500


def _generate_podcast_script(
    title: str,
    summary: str,
    takeaways: list[str],
    *,
    lang: str = "en",
    sources: list[dict] | None = None,
    dimensions: list[dict] | None = None,
    dim_scores: dict | None = None,
    mindmap_summary: str = "",
) -> dict:
    """Generate a two-host podcast discussion script via Claude with rich context."""

    if lang == "zh":
        system_prompt = (
            "你是一个播客脚本编剧。写一段两人对话式的深度知识讨论，风格类似 NotebookLM 的 Audio Overview。\n\n"
            "角色：\n"
            "- Host A (Alex): 好奇心强，会提有深度的追问，代表学习者视角\n"
            "- Host B (Sam): 知识丰富、善于用具体例子和类比解释复杂概念，代表专家视角\n\n"
            "风格要求：\n"
            "- 用中文对话，但技术名词保留英文原词，类似中国程序员日常交流的风格\n"
            "- 保留英文的词汇：Agent, Tokenization, Embedding, RAG, Prompt, Pipeline, Deploy, API, SDK, CLI, "
            "Model serving, Inference, Training, Fine-tuning（微调也可以）, Framework, Runtime, Latency 等\n"
            "- 只有被广泛使用的中文对应词才用中文，如：微调、模型、数据集、向量、权重\n"
            "- 自然口语化，不要太正式\n"
            "- 有来有回，不是一个人的独白\n"
            '- 适当使用过渡语（"说到这个..."、"对，而且..."、"等等，我想确认一下..."）\n'
            "- 不只是复述要点，要有分析、对比、举例\n"
            "- Alex 提出有深度的追问（'那这个和 X 有什么区别？'、'实际应用中会遇到什么问题？'）\n"
            "- Sam 用具体例子和类比来解释\n"
            "- 总时长控制在 5-8 分钟阅读量（约 2500-4000 字符）\n"
            "- 开头有简短的引入，结尾有总结"
        )
        lang_rule = "- 对话用中文，技术名词保留英文（中英混合风格）"
    else:
        system_prompt = (
            "You are a podcast script writer. Write a deep, insightful two-person knowledge discussion, "
            "similar to NotebookLM's Audio Overview style.\n\n"
            "Characters:\n"
            "- Host A (Alex): Curious, asks insightful follow-up questions, represents the learner\n"
            "- Host B (Sam): Knowledgeable, uses concrete examples and analogies, represents the expert\n\n"
            "Style:\n"
            "- Natural conversational tone, not too formal\n"
            "- Back-and-forth dialogue, not monologue\n"
            '- Use transitions ("Speaking of which...", "Right, and also...", "Wait, let me make sure I understand...")\n'
            "- Don't just restate points — analyze, compare, give examples\n"
            '- Alex asks deep follow-ups ("How is that different from X?", "What problems come up in practice?")\n'
            "- Sam explains with concrete examples and analogies\n"
            "- Total length: 5-8 minutes reading time (~2500-4000 characters)\n"
            "- Brief intro at the start, summary at the end"
        )
        lang_rule = "- Write the dialogue in English"

    # Build rich content sections
    content_parts = [f"Concept: {title}", f"Description: {summary}"]

    # Knowledge dimensions
    if dimensions:
        scores = dim_scores or {}
        dims_text = "\n".join(
            f"• {d.get('title', d.get('id', '?'))} (coverage: {scores.get(d.get('id', ''), 0)*100:.0f}%)"
            for d in dimensions
        )
        content_parts.append(f"\nKnowledge dimensions (dialogue should cover these aspects):\n{dims_text}")

    # Source summaries
    if sources:
        src_summaries = "\n".join(
            f"--- {s.get('title', '?')} ---\n{s.get('summary', '')}"
            for s in sources if s.get("summary")
        )
        if src_summaries:
            content_parts.append(f"\nSource summaries:\n{src_summaries}")

    # All takeaways (no limit)
    if takeaways:
        content_parts.append(f"\nAll key takeaways:\n" + "\n".join(f"• {t}" for t in takeaways))

    # Mind map structure
    if mindmap_summary:
        content_parts.append(f"\nMind map structure:\n{mindmap_summary}")

    # Raw excerpts (budget-aware: fit within ~6000 char total)
    user_so_far = "\n".join(content_parts)
    budget = 6000 - len(user_so_far)
    if sources and budget > 200:
        excerpts = []
        for s in sources:
            raw = s.get("raw_excerpt", "")
            if not raw:
                continue
            chunk = raw[:500]
            if len("\n".join(excerpts)) + len(chunk) + 50 > budget:
                break
            excerpts.append(f"--- {s.get('title', '?')} ---\n{chunk}")
        if excerpts:
            content_parts.append(f"\nRaw content excerpts:\n" + "\n".join(excerpts))

    user_content = "\n".join(content_parts)

    return _call_claude(
        system_prompt=system_prompt,
        user_prompt=(
            user_content + "\n\n"
            "Generate an in-depth podcast dialogue script, return JSON:\n"
            '{\n'
            '  "title": "Episode title",\n'
            '  "dialogue": [\n'
            '    {"speaker": "A", "text": "Alex says..."},\n'
            '    {"speaker": "B", "text": "Sam says..."},\n'
            "    ...\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- 15-25 dialogue turns\n"
            "- Each turn 1-3 sentences\n"
            "- Cover all listed knowledge dimensions and important takeaways\n"
            "- Don't just restate — analyze, compare, give examples\n"
            f"{lang_rule}\n"
            "- Alex introduces the topic at the start, Sam summarizes at the end"
        ),
        max_tokens=4000,
    )


def _synthesize_podcast(script: dict) -> bytes:
    """Synthesize podcast audio from dialogue script via ElevenLabs."""
    from elevenlabs import ElevenLabs

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY not set")

    client = ElevenLabs(api_key=api_key)
    dialogue = script.get("dialogue", [])
    if not dialogue:
        raise ValueError("Empty dialogue script")

    audio_segments = []
    for line in dialogue:
        voice_id = HOST_A_VOICE if line["speaker"] == "A" else HOST_B_VOICE
        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            text=line["text"],
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        audio_segments.append(b"".join(audio))

    # Merge segments with pydub (300ms silence between speakers)
    try:
        from pydub import AudioSegment

        combined = AudioSegment.empty()
        silence = AudioSegment.silent(duration=300)
        for i, seg_bytes in enumerate(audio_segments):
            segment = AudioSegment.from_mp3(io.BytesIO(seg_bytes))
            if i > 0:
                combined += silence
            combined += segment

        output = io.BytesIO()
        combined.export(output, format="mp3", bitrate="128k")
        return output.getvalue()
    except ImportError:
        # Fallback: raw concatenation
        return b"".join(audio_segments)


# ---------------------------------------------------------------------------
# Deep Research — AI-powered learning resource discovery
# ---------------------------------------------------------------------------

RESEARCH_DIR = DATA_DIR / "research_reports"
os.makedirs(RESEARCH_DIR, exist_ok=True)


def _get_parent_path(node_id: str, template: dict) -> str:
    """Build a breadcrumb path for a node from the template tree."""
    def _walk(node, path):
        if node.get("id") == node_id:
            return path
        for child in node.get("children", []):
            label = child.get("title", child.get("id", ""))
            result = _walk(child, (path + " > " + label) if path else label)
            if result is not None:
                return result
        return None
    return _walk(template.get("tree", {}), "") or ""


def _gather_research_context(node_id: str, node: dict | None, tree_data: dict, template: dict) -> dict:
    """Collect all context for a node to help AI generate better searches."""
    context = {
        "title": "",
        "status": "locked",
        "dimensions": [],
        "weak_dimensions": [],
        "existing_sources": [],
        "summary": "",
        "guide": {},
        "parent_path": "",
    }

    node_info = _find_node_in_template(node_id, template)
    if node_info:
        context["title"] = node_info.get("title", "")
        context["guide"] = node_info.get("guide", {})
        context["parent_path"] = _get_parent_path(node_id, template)

    if node:
        context["status"] = node.get("status", "locked")
        context["summary"] = node.get("summary", "")
        context["dimensions"] = node.get("quest", {}).get("dimensions", [])

        progress = node.get("quest", {}).get("progress", {})
        dim_scores = progress.get("dimension_scores", {})
        for d in context["dimensions"]:
            score = dim_scores.get(d["id"], 0)
            if score < 0.5:
                context["weak_dimensions"].append({"title": d["title"], "score": score})

        sources = tree_data.get("sources", [])
        for src in sources:
            if src["id"] in node.get("source_ids", []):
                context["existing_sources"].append(src.get("title", ""))

    return context


def _generate_search_plan(title: str, context: dict) -> dict:
    """AI generates search queries based on node context."""
    existing = context["existing_sources"]
    weak = context["weak_dimensions"]

    return _call_claude(
        system_prompt="You are a learning resource research expert. Generate precise search queries based on the learning goal.",
        user_prompt=f"""Learning goal: {title}
Domain: {context.get('parent_path', '')}
Current status: {context.get('status', 'locked')}

{f"Existing learning resources (avoid duplicates): {existing}" if existing else "No learning resources yet."}

{f"Weak knowledge dimensions (focus search on these): {json.dumps(weak, ensure_ascii=False)}" if weak else ""}

Generate 3-5 precise English search queries to find the best learning resources.

Return JSON:
{{
  "queries": [
    "query 1 — beginner tutorials",
    "query 2 — in-depth articles",
    "query 3 — hands-on projects / code examples",
    "query 4 — latest developments (add 2025 or 2026)",
    "query 5 — resources for weak dimensions (if applicable)"
  ]
}}

Rules:
- Search queries in English (English resources are higher quality)
- Each query 5-10 words
- Include different types: tutorial, guide, best practices, comparison, hands-on
- At least one query with year (2025 or 2026) for latest content
- If there are weak dimensions, at least one query targeting them""",
        max_tokens=1000,
    )


def _execute_searches(queries: list[str]) -> list[dict]:
    """Execute web searches via Tavily."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        log.warning("TAVILY_API_KEY not set")
        return []

    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)
    all_results = []
    seen_urls: set[str] = set()

    for query in queries[:5]:
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_answer=False,
                include_raw_content=False,
            )
            for result in response.get("results", []):
                url = result.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append({
                        "title": result.get("title", ""),
                        "url": url,
                        "snippet": result.get("content", "")[:300],
                        "score": result.get("score", 0),
                        "query": query,
                    })
        except Exception as e:
            log.warning("Tavily search failed for '%s': %s", query, e)

    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return all_results[:20]


def _generate_research_report(title: str, context: dict, search_results: list[dict]) -> dict:
    """AI synthesizes classic recommendations + search results into a structured report."""
    results_for_prompt = json.dumps(
        [{"title": r["title"], "url": r["url"], "snippet": r["snippet"]} for r in search_results[:15]],
        ensure_ascii=False,
    )

    return _call_claude(
        system_prompt="""You are an AI/ML learning consultant. Based on search results and your knowledge, generate a comprehensive learning resource report for the student.

Your goal is to help the student find the most efficient learning path. Always respond in English.""",
        user_prompt=f"""Learning goal: {title}
Domain: {context.get('parent_path', '')}
Student current status: {context.get('status', 'locked')}
{f"Existing resources: {context['existing_sources']}" if context['existing_sources'] else "Starting from scratch"}
{f"Weak dimensions: {json.dumps(context['weak_dimensions'], ensure_ascii=False)}" if context['weak_dimensions'] else ""}

Search results:
{results_for_prompt}

Generate a learning resource report. Return JSON:
{{
  "overview": "A paragraph overview of this concept (3-4 sentences)",
  "learning_path": [
    {{
      "step": 1,
      "title": "Step 1: Fundamentals",
      "description": "Start by understanding core concepts and basic principles",
      "resources": [
        {{
          "title": "Resource title",
          "url": "https://...",
          "type": "article | video | tutorial | course | docs | github",
          "difficulty": "beginner | intermediate | advanced",
          "why": "Why this is recommended (1 sentence)",
          "estimated_time": "30 min",
          "from_search": true
        }}
      ]
    }}
  ],
  "classic_resources": [
    {{
      "title": "Classic must-read resource",
      "url": "https://...",
      "type": "article | book | docs",
      "why": "Why this is a classic",
      "from_search": false
    }}
  ],
  "weak_dimension_resources": [
    {{
      "dimension": "Weak dimension name",
      "resources": [
        {{
          "title": "...",
          "url": "...",
          "why": "Specifically strengthens this dimension"
        }}
      ]
    }}
  ],
  "practice_projects": [
    {{
      "title": "Practice project suggestion",
      "description": "How to do it specifically",
      "difficulty": "beginner | intermediate | advanced",
      "estimated_time": "2 hours"
    }}
  ],
  "total_estimated_time": "~8 hours"
}}

Rules:
- learning_path has 2-4 steps, from beginner to advanced
- Each step has 2-4 resources
- Mix search results (from_search: true) and classic recommendations (from_search: false)
- Classic recommendations come from your domain knowledge (official docs, renowned blogs, seminal papers, etc.)
- If there are weak dimensions, list specific resources to strengthen them
- practice_projects: 1-3 hands-on projects
- Estimate total learning time
- Write all descriptions in English
- Resource URLs should be real, accessible links""",
        max_tokens=4000,
    )


def _validate_report_urls(report: dict) -> dict:
    """Validate all resource URLs in parallel, remove dead links."""
    import requests as _req
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Collect all URLs
    all_urls: set[str] = set()
    for step in report.get("learning_path", []):
        for r in step.get("resources", []):
            if r.get("url"):
                all_urls.add(r["url"])
    for r in report.get("classic_resources", []):
        if r.get("url"):
            all_urls.add(r["url"])
    for dim in report.get("weak_dimension_resources", []):
        for r in dim.get("resources", []):
            if r.get("url"):
                all_urls.add(r["url"])

    if not all_urls:
        return report

    # Parallel HEAD requests
    valid_urls: set[str] = set()

    def _check(url: str) -> tuple[str, bool]:
        try:
            resp = _req.head(url, timeout=5, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            return url, resp.status_code < 400
        except Exception:
            return url, False

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_check, u): u for u in all_urls}
        for fut in as_completed(futures):
            url, ok = fut.result()
            if ok:
                valid_urls.add(url)
            else:
                log.info("Dead link removed from research report: %s", url)

    # Filter out dead links
    for step in report.get("learning_path", []):
        step["resources"] = [r for r in step.get("resources", []) if not r.get("url") or r["url"] in valid_urls]
    report["classic_resources"] = [r for r in report.get("classic_resources", []) if not r.get("url") or r["url"] in valid_urls]
    for dim in report.get("weak_dimension_resources", []):
        dim["resources"] = [r for r in dim.get("resources", []) if not r.get("url") or r["url"] in valid_urls]
    # Remove empty weak dimension entries
    report["weak_dimension_resources"] = [d for d in report.get("weak_dimension_resources", []) if d.get("resources")]

    return report


@knowledge_tree_bp.route("/api/knowledge-tree/research/<node_id>", methods=["POST"])
def generate_research(node_id):
    """Generate a Deep Research report for a node."""
    tree_data = _load_tree()
    template = _load_template()
    node = tree_data.get("nodes", {}).get(node_id)

    node_info = _find_node_in_template(node_id, template)
    if not node_info and not node:
        return jsonify({"error": "Node not found"}), 404

    title = node.get("title", "") if node else node_info.get("title", "")

    # Check cache (7-day TTL) unless force refresh
    force = request.args.get("force") == "1"
    cache_path = RESEARCH_DIR / f"{node_id}.json"
    if not force and cache_path.exists():
        cached = load_json(cache_path, {})
        generated = cached.get("generated_at", "")
        if generated:
            try:
                gen_time = datetime.fromisoformat(generated.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - gen_time < timedelta(days=7):
                    return jsonify(cached)
            except Exception:
                pass

    # 1. Gather context
    context = _gather_research_context(node_id, node, tree_data, template)
    if not context["title"] and title:
        context["title"] = title

    # 2. Generate search plan
    try:
        search_plan = _generate_search_plan(title, context)
        queries = search_plan.get("queries", [])
    except Exception as e:
        log.warning("Search plan generation failed: %s", e)
        queries = [f"{title} tutorial guide", f"{title} best practices 2026"]

    # 3. Tavily search
    search_results = _execute_searches(queries)

    # 4. Generate report (works even with empty search_results as fallback)
    try:
        report = _generate_research_report(title, context, search_results)
    except Exception as e:
        log.warning("Research report generation failed: %s", e)
        return jsonify({"error": f"Report generation failed: {e}"}), 500

    # 4b. Validate resource URLs (remove dead links)
    report = _validate_report_urls(report)

    # 5. Cache report
    report["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report["node_id"] = node_id
    report["search_queries"] = queries
    report["search_result_count"] = len(search_results)
    save_json(cache_path, report)

    # 6. Award XP for first research
    if node:
        quest = node.setdefault("quest", {})
        progress = quest.setdefault("progress", {})
        if not progress.get("research_generated"):
            progress["research_generated"] = True
            _award_xp(10, f"Deep Research generated for {title}", tree_data)
            _save_tree(tree_data)

    return jsonify(report)


@knowledge_tree_bp.route("/api/knowledge-tree/research/<node_id>", methods=["GET"])
def get_research(node_id):
    """Get cached Deep Research report."""
    cache_path = RESEARCH_DIR / f"{node_id}.json"
    if not cache_path.exists():
        return jsonify({"exists": False}), 404
    return jsonify(load_json(cache_path, {}))


# ---------------------------------------------------------------------------
# Language — normalize + translate
# ---------------------------------------------------------------------------

@knowledge_tree_bp.route("/api/knowledge-tree/normalize-language", methods=["POST"])
def kt_normalize_language():
    """Move Chinese summaries to node['zh'], regenerate English defaults."""
    body = request.get_json(silent=True) or {}
    limit = min(body.get("limit", 5), 10)

    tree_data = _load_tree()
    nodes = tree_data.get("nodes", {})

    # Identify nodes with Chinese content
    to_normalize = []
    remaining = 0
    for nid, node in nodes.items():
        summary = node.get("summary", "")
        takeaways = node.get("key_takeaways", [])
        takeaways_text = " ".join(takeaways) if takeaways else ""
        if not _is_chinese(summary) and not _is_chinese(takeaways_text):
            continue
        if len(to_normalize) >= limit:
            remaining += 1
            continue
        to_normalize.append((nid, summary, list(takeaways)))

    # Perform AI calls outside the lock
    regen_results = {}  # nid -> {summary, key_takeaways, tags}
    for nid, _, _ in to_normalize:
        result = _generate_node_summary(nid, tree_data)
        if result:
            regen_results[nid] = result

    # Also find practice_task descriptions in Chinese
    practice_fixed = []
    for nid, node in nodes.items():
        practice = node.get("quest", {}).get("practice_task", {})
        if isinstance(practice, dict):
            desc = practice.get("description", "")
            if desc and _is_chinese(desc):
                practice_fixed.append((nid, desc))

    # Translate practice tasks to English
    practice_translations = {}
    for nid, desc in practice_fixed:
        try:
            result = _call_claude(
                system_prompt="You are a translator. Translate the practice task description to English. Keep technical terms as-is. Return strict JSON.",
                user_prompt=f'Translate to English:\n"{desc}"\n\nReturn JSON:\n{{"description": "English translation"}}',
                max_tokens=300,
            )
            practice_translations[nid] = result.get("description", desc)
        except Exception as e:
            log.warning("Practice task translation failed for %s: %s", nid, e)

    # Apply all changes under lock
    normalized = [t[0] for t in to_normalize]
    regenerated = list(regen_results.keys())
    if to_normalize or practice_translations:
        with _id_lock:
            tree_data = _load_tree()
            for nid, summary, takeaways in to_normalize:
                nd = tree_data.get("nodes", {}).get(nid)
                if not nd:
                    continue
                zh = nd.setdefault("zh", {})
                if summary:
                    zh["summary"] = summary
                if takeaways:
                    zh["key_takeaways"] = takeaways

                regen = regen_results.get(nid)
                if regen:
                    nd["summary"] = regen.get("summary", "")
                    nd["key_takeaways"] = regen.get("key_takeaways", [])
                    nd["tags"] = regen.get("tags", nd.get("tags", []))
                else:
                    nd["summary"] = ""
                    nd["key_takeaways"] = []

            # Apply practice task translations
            for nid, en_desc in practice_translations.items():
                nd = tree_data.get("nodes", {}).get(nid)
                if nd:
                    practice = nd.get("quest", {}).get("practice_task", {})
                    if isinstance(practice, dict):
                        zh = nd.setdefault("zh", {})
                        zh["practice_task"] = practice.get("description", "")
                        practice["description"] = en_desc

            _save_tree(tree_data)

    return jsonify({
        "ok": True,
        "normalized": normalized,
        "regenerated": regenerated,
        "practice_fixed": [t[0] for t in practice_fixed],
        "remaining": remaining,
    })


@knowledge_tree_bp.route("/api/knowledge-tree/translate/<node_id>", methods=["POST"])
def kt_translate_node(node_id):
    """Translate a node's summary + key_takeaways to Chinese (cached)."""
    tree_data = _load_tree()
    node = tree_data.get("nodes", {}).get(node_id)
    if not node:
        return jsonify({"ok": False, "error": "not found"}), 404

    zh = node.get("zh", {})
    if zh.get("summary") and zh.get("key_takeaways"):
        return jsonify({"ok": True, "zh": zh, "cached": True})

    summary = node.get("summary", "")
    takeaways = node.get("key_takeaways", [])
    if not summary and not takeaways:
        return jsonify({"ok": False, "error": "no content to translate"}), 400

    try:
        result = _call_claude(
            system_prompt="You are a translator. Translate the given content to Simplified Chinese. Keep technical terms in English (e.g. RAG, Embedding, Fine-tuning, Agent, Pipeline, API, SDK, CLI). Return strict JSON.",
            user_prompt=f"""Translate the following to Simplified Chinese:

Summary: {summary}

Key Takeaways:
{json.dumps(takeaways, ensure_ascii=False)}

Return JSON:
{{"summary": "Chinese translation of summary", "key_takeaways": ["Chinese takeaway 1", "Chinese takeaway 2", ...]}}""",
            max_tokens=1500,
        )
    except Exception as e:
        log.warning("Translation failed for %s: %s", node_id, e)
        return jsonify({"ok": False, "error": str(e)}), 500

    zh_data = {
        "summary": result.get("summary", ""),
        "key_takeaways": result.get("key_takeaways", []),
    }
    # Save under lock to prevent concurrent write conflicts
    with _id_lock:
        tree_data = _load_tree()
        nd = tree_data.get("nodes", {}).get(node_id)
        if nd:
            existing_zh = nd.get("zh", {})
            existing_zh.update(zh_data)
            nd["zh"] = existing_zh
            _save_tree(tree_data)
            return jsonify({"ok": True, "zh": nd["zh"], "cached": False})

    return jsonify({"ok": True, "zh": zh_data, "cached": False})


@knowledge_tree_bp.route("/api/knowledge-tree/translate-all", methods=["POST"])
def kt_translate_all():
    """Batch translate nodes missing zh content."""
    body = request.get_json(silent=True) or {}
    limit = min(body.get("limit", 5), 10)

    tree_data = _load_tree()
    nodes = tree_data.get("nodes", {})

    # Collect nodes that need translation
    to_translate = []
    remaining = 0
    for nid, node in nodes.items():
        if not node.get("summary") and not node.get("key_takeaways"):
            continue
        zh = node.get("zh", {})
        if zh.get("summary") and zh.get("key_takeaways"):
            continue
        if len(to_translate) >= limit:
            remaining += 1
            continue
        to_translate.append((nid, node.get("summary", ""), node.get("key_takeaways", [])))

    # Perform AI calls outside the lock
    results = {}  # nid -> zh_data
    for nid, summary, takeaways in to_translate:
        try:
            result = _call_claude(
                system_prompt="You are a translator. Translate the given content to Simplified Chinese. Keep technical terms in English (e.g. RAG, Embedding, Fine-tuning, Agent, Pipeline, API, SDK, CLI). Return strict JSON.",
                user_prompt=f"""Translate the following to Simplified Chinese:

Summary: {summary}

Key Takeaways:
{json.dumps(takeaways, ensure_ascii=False)}

Return JSON:
{{"summary": "Chinese translation", "key_takeaways": ["Chinese takeaway 1", ...]}}""",
                max_tokens=1500,
            )
            results[nid] = {
                "summary": result.get("summary", ""),
                "key_takeaways": result.get("key_takeaways", []),
            }
        except Exception as e:
            log.warning("Batch translation failed for %s: %s", nid, e)

    # Apply all results under lock
    translated = list(results.keys())
    if results:
        with _id_lock:
            tree_data = _load_tree()
            for nid, zh_data in results.items():
                nd = tree_data.get("nodes", {}).get(nid)
                if nd:
                    existing_zh = nd.get("zh", {})
                    existing_zh.update(zh_data)
                    nd["zh"] = existing_zh
            _save_tree(tree_data)

    return jsonify({"ok": True, "translated": translated, "remaining": remaining})
