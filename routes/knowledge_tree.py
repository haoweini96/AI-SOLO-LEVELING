"""Knowledge Tree routes — Tech Tree + Solo Leveling XP System.

Blueprint: knowledge_tree_bp
Prefix: /api/knowledge-tree/
"""

from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timedelta, timezone

import numpy as np
from flask import Blueprint, jsonify, request

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
    (1,   5,   "E", "觉醒者",       "E-Rank Hunter"),
    (6,   10,  "E", "E级猎人",      "E级精英"),
    (11,  15,  "D", "D级猎人",      "D级猎人"),
    (16,  20,  "D", "D级精英",      "见习突破者"),
    (21,  27,  "C", "C级猎人",      "C级猎人"),
    (28,  35,  "C", "C级精英",      "正式战力"),
    (36,  42,  "B", "B级猎人",      "B级猎人"),
    (43,  50,  "B", "B级精英",      "攻略组成员"),
    (51,  57,  "A", "A级猎人",      "A级猎人"),
    (58,  65,  "A", "A级精英",      "公会核心"),
    (66,  72,  "S", "S级猎人",      "S级猎人"),
    (73,  80,  "S", "S级精英",      "最强战力"),
    (81,  87,  "National", "国家权力级",  "国家权力级"),
    (88,  95,  "National", "国家权力级精英", "超越人类"),
    (96,  99,  "Monarch",  "君主候选",    "君主"),
    (100, 100, "Shadow Monarch", "暗影君王", "暗影君王"),
]


# ---------------------------------------------------------------------------
# Helpers — basics
# ---------------------------------------------------------------------------

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
    """XP required to reach the next level."""
    return int(100 * (1.15 ** (level - 1)))


def _rank_for_level(level: int) -> str:
    for min_l, max_l, rank, _, _ in RANK_TABLE:
        if min_l <= level <= max_l:
            return rank
    return "E"


def _title_for_level(level: int) -> str:
    for min_l, max_l, _, title_min, title_max in RANK_TABLE:
        if min_l <= level <= max_l:
            if level <= (min_l + max_l) // 2:
                return title_min
            else:
                return title_max
    return "觉醒者"


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

    # Cap at level 100
    if profile["level"] >= 100:
        profile["level"] = 100
        profile["current_xp"] = 0
        profile["xp_to_next_level"] = 0

    # Always recalculate rank/title (handles migration from old rank system)
    profile["rank"] = _rank_for_level(profile["level"])
    profile["title"] = _title_for_level(profile["level"])

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
        system_prompt="你是一个知识评估助手。严格返回 JSON。",
        user_prompt=f"""评估以下学习材料对各知识维度的覆盖程度。

学习材料：
标题：{source.get('title', '')}
摘要：{source.get('summary', '')}
要点：{source.get('key_takeaways', [])[:8]}

需要评估的知识维度：
{dims_json}

对每个维度打分 0-100：
- 0: 完全没涉及
- 20-40: 简单提及
- 50-70: 有一定深度的覆盖
- 80-100: 深入全面的覆盖

返回 JSON：
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

    text = response.content[0].text
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    return json.loads(text.strip())


def _classify_source_to_tree(source: dict, template: dict) -> list[str]:
    """AI-classify a source to 1-3 tech tree leaf nodes."""
    leaves = _get_all_leaves(template)
    leaves_json = json.dumps([{"id": l["id"], "title": l["title"]} for l in leaves], ensure_ascii=False)

    prompt = (
        "以下是一个新的知识来源：\n"
        f"标题：{source.get('title', '')}\n"
        f"摘要：{source.get('summary', '')}\n"
        f"Tags：{source.get('tags', [])}\n"
        f"Key takeaways：{source.get('key_takeaways', [])[:5]}\n\n"
        f"以下是科技树的所有叶子概念节点：\n{leaves_json}\n\n"
        "这个来源应该关联到哪些概念节点？一个来源可以关联 1-3 个节点。\n\n"
        '返回 JSON：\n'
        '{"node_ids": ["node_id_1", "node_id_2"], "reasoning": "简短说明为什么选这些节点"}\n\n'
        "规则：\n"
        "- 只选真正相关的节点，不要为了多选而选\n"
        "- 通常 1-2 个就够了\n"
        "- 只能选叶子节点的 id"
    )

    result = _call_claude(
        system_prompt="你是一个知识分类助手。",
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
            system_prompt="你是知识整理助手。根据来源信息，生成一个概念的综合总结。用来源的主要语言。严格返回 JSON。",
            user_prompt=f"""概念 ID: {node_id}
来源信息：
{json.dumps(sources_info, ensure_ascii=False, indent=2)}

返回 JSON：
{{"summary": "2-3句话综合总结", "key_takeaways": ["要点1", "要点2", ...], "tags": ["tag1", "tag2"]}}""",
            max_tokens=1000,
        )
        return result
    except Exception as e:
        log.warning("Failed to generate summary for node %s: %s", node_id, e)
        return None


def _extract_knowledge_with_ai(conversation_text: str, user_notes: str = "") -> dict:
    """Use Claude to extract structured knowledge points from conversation text."""
    system_prompt = (
        "你是一个知识提取助手。分析用户提供的对话内容，提取有价值的知识点。\n\n"
        "规则：\n"
        "1. 只提取有学习价值的知识，忽略闲聊、debug 过程、重复修改代码等\n"
        "2. 每个知识点应该是一个独立的、可复习的概念或事实\n"
        "3. 如果对话主要是写代码/debug 且没有新知识，返回空数组\n"
        "4. tags 用英文小写，用于搜索\n"
        "5. summary 用对话的主要语言（中文或英文），2-3 句话\n"
        "6. key_takeaways 每条是一个独立的要点，可以直接用于复习\n\n"
        "严格按 JSON 格式返回，不要有其他文字："
    )

    notes_line = f"\n\n用户备注：{user_notes}" if user_notes else ""
    user_prompt = (
        f"对话内容：\n{conversation_text}{notes_line}\n\n"
        "请提取知识点，返回 JSON：\n"
        '{\n'
        '  "knowledge_points": [\n'
        '    {\n'
        '      "title": "简短标题",\n'
        '      "tags": ["tag1", "tag2"],\n'
        '      "summary": "2-3句话总结",\n'
        '      "key_takeaways": ["要点1", "要点2"],\n'
        '      "raw_excerpt": "对话中最相关的原文"\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        '如果对话没有有价值的知识，返回 {"knowledge_points": []}'
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
    """Generate review quizzes with AI."""
    system_prompt = (
        "你是一个知识复习助手。生成复习测验题。\n\n"
        "规则：\n"
        "1. 每个知识点1个问题\n"
        "2. 混合题型：recall（回忆）、application（应用）、connection（关联）\n"
        "3. 问题要具体\n"
        "4. 用知识点的原始语言出题\n\n"
        "严格按 JSON 格式返回。"
    )

    nodes_info = [
        {"id": n["id"], "title": n.get("title", n["id"]), "summary": n.get("summary", ""),
         "key_takeaways": n.get("key_takeaways", []), "confidence": n.get("confidence", 0)}
        for n in nodes
    ]

    related_line = ""
    if related_context:
        related_line = f"\n\n关联知识点：\n{json.dumps(related_context, ensure_ascii=False)}"

    user_prompt = (
        f"知识点：\n{json.dumps(nodes_info, ensure_ascii=False, indent=2)}{related_line}\n\n"
        "返回 JSON：\n"
        '{"quizzes": [{"node_id": "ID", "type": "recall|application|connection", '
        '"question": "问题", "hint": "提示", "expected_answer_points": ["要点"], "difficulty": "easy|medium|hard"}]}'
    )

    try:
        result = _call_claude(system_prompt, user_prompt, max_tokens=2000)
        return result.get("quizzes", [])
    except Exception as e:
        log.warning("Quiz generation failed: %s", e)
        return [
            {"node_id": n["id"], "type": "recall",
             "question": f"请回忆关于「{n.get('title', n['id'])}」的核心要点。",
             "hint": (n.get("summary") or "")[:100],
             "expected_answer_points": n.get("key_takeaways", []),
             "difficulty": "medium"}
            for n in nodes
        ]


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


# ---------------------------------------------------------------------------
# Routes — Recommended Tasks (Daily Quests)
# ---------------------------------------------------------------------------

RECOMMENDED_TASKS_FILE = DATA_DIR / "recommended_tasks.json"


@knowledge_tree_bp.route("/api/knowledge-tree/recommended-tasks")
def kt_recommended_tasks():
    """Get AI-generated recommended learning tasks. Cached for 24h."""
    force = request.args.get("force", "").lower() in ("1", "true")

    cached = load_json(RECOMMENDED_TASKS_FILE, {})
    meta = cached.get("_meta", {})

    # Return cached if fresh (unless force refresh)
    if not force and cached.get("tasks") and not meta.get("stale", True):
        return jsonify({"ok": True, "tasks": cached["tasks"], "_meta": meta})

    # Generate fresh recommendations
    tree_data = _load_tree()
    profile = _load_profile()
    nodes = tree_data.get("nodes", {})

    in_progress = []
    for nid, n in nodes.items():
        if n.get("status") == "in_progress":
            quest = n.get("quest", {})
            progress = quest.get("progress", {})
            in_progress.append({
                "id": nid,
                "title": n.get("title", nid),
                "coverage": progress.get("overall_coverage", 0),
                "threshold": quest.get("coverage_threshold", 0.7),
                "weak_dims": [
                    d["title"] for d in quest.get("dimensions", [])
                    if progress.get("dimension_scores", {}).get(d["id"], 0) < 0.4
                ],
            })

    locked_titles = [
        n.get("title", nid) for nid, n in nodes.items()
        if n.get("status") == "locked"
    ][:15]

    due_nodes = _get_due_nodes(tree_data)
    due_info = [{"title": nodes.get(nid, {}).get("title", nid)} for nid in due_nodes[:5]]

    context = json.dumps({
        "rank": profile.get("rank", "E"),
        "level": profile.get("level", 1),
        "in_progress": in_progress,
        "locked": locked_titles,
        "due_for_review": due_info,
    }, ensure_ascii=False)

    try:
        result = _call_claude(
            system_prompt="你是一个 AI/ML 学习导师。根据学生当前的学习进度，推荐接下来应该做什么。严格返回 JSON。",
            user_prompt=f"""学生当前状态：
{context}

请推荐 3-5 个具体的学习任务，优先级从高到低。

任务类型：
1. "complete" — 继续完成某个 in_progress 节点（覆盖度最接近达标的优先）
2. "review" — 复习某个节点（如果有 due 的复习）
3. "explore" — 开始探索一个新的 locked 节点（和已有知识关联最紧的优先）
4. "practice" — 完成某个实践任务

返回 JSON：
{{"tasks": [{{"type": "complete", "node_title": "...", "node_id": "...", "action": "具体可执行的建议", "reason": "简短原因", "priority": "high/medium/low"}}]}}

规则：
- 优先推荐快要完成的节点（complete 类型）
- 其次推荐和已有知识关联最强的新节点（explore 类型）
- action 要具体可执行，不要泛泛而谈
- node_id 必须是实际存在的节点 ID
- 用中文描述""",
            max_tokens=2000,
        )
        tasks = result.get("tasks", [])
    except Exception as e:
        log.warning("Failed to generate recommended tasks: %s", e)
        # Return stale cache if available
        if cached.get("tasks"):
            return jsonify({"ok": True, "tasks": cached["tasks"], "_meta": meta, "stale_fallback": True})
        return jsonify({"ok": False, "error": str(e), "tasks": []}), 500

    now_iso = datetime.now().isoformat()
    payload = {
        "tasks": tasks,
        "_meta": make_meta(now_iso, stale_after_hours=24),
    }
    save_json(RECOMMENDED_TASKS_FILE, payload)

    return jsonify({"ok": True, "tasks": tasks, "_meta": payload["_meta"]})


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
        "为以下科技树叶子节点生成学习引导信息。每个节点需要：\n"
        "- what: 1-2句话解释这个概念是什么（中文）\n"
        "- why: 1句话说明为什么要学这个（中文）\n"
        "- resources: 2-3条学习建议（英文或中文混合都行）\n\n"
        f"叶子节点列表：\n{leaves_info}\n\n"
        '返回 JSON：\n'
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
            "为以下科技树叶子节点生成学习引导信息。每个节点需要：\n"
            "- what: 1-2句话解释这个概念是什么（中文）\n"
            "- why: 1句话说明为什么要学这个（中文）\n"
            "- resources: 2-3条学习建议（英文或中文混合都行）\n\n"
            f"叶子节点列表：\n{batch_info}\n\n"
            '返回 JSON：\n'
            '{"guides": {"node_id": {"what": "...", "why": "...", "resources": ["...", "..."]}, ...}}'
        )
        try:
            result = _call_claude(
                system_prompt="你是 AI/ML 学习顾问。为科技树节点生成简洁的学习引导。严格返回 JSON。",
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
            "为以下科技树叶子节点设计学习任务(quest)。根据概念的复杂度决定：\n"
            "- practice_task: 可选的实践任务描述（字符串或null）。只有真正需要动手练习的概念才设置。\n"
            "  如果设置practice_task，同时设 practice_required: true/false 表示是否必须完成\n\n"
            f"节点列表：\n{batch_info}\n\n"
            '返回 JSON：\n'
            '{"quests": [{"node_id": "...", "practice_task": "..." or null, "practice_required": false}, ...]}'
        )
        try:
            result = _call_claude(
                system_prompt="你是一个学习课程设计师。根据概念复杂度为科技树节点设计合理的学习任务。严格返回 JSON。",
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
            "为以下 AI/ML 概念节点设计知识维度。每个概念需要掌握的核心维度（3-6 个），每个维度有权重（总和 1.0）。\n\n"
            f"概念列表：\n{batch_info}\n\n"
            '返回 JSON：\n'
            '{"nodes": [{"node_id": "prod_patterns", "dimensions": [{"id": "architecture", "title": "Architecture Design", "weight": 0.3}, ...], "coverage_threshold": 0.7}, ...]}\n\n'
            "规则：\n"
            "- 每个概念 3-6 个维度\n"
            "- 维度 id 用 snake_case 英文\n"
            "- 维度 title 用英文\n"
            "- weight 总和 = 1.0，重要的维度权重高\n"
            "- coverage_threshold: 简单概念 0.6，中等 0.7，复杂 0.8\n"
            "- 维度应该代表该概念的不同方面/角度，不是细节"
        )
        try:
            result = _call_claude(
                system_prompt="你是一个课程设计专家。严格返回 JSON。",
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
    """Generate AI review quizzes for due nodes or specific nodes."""
    body = request.get_json(silent=True) or {}
    batch_size = body.get("batch_size", 5)
    specific_node_ids = body.get("node_ids")  # Optional: quiz specific nodes

    tree_data = _load_tree()
    template = _load_template()
    leaf_map = {l["id"]: l["title"] for l in _get_all_leaves(template)}

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
    else:
        target_nodes = _get_due_nodes(tree_data, limit=batch_size)
        if not target_nodes:
            next_due = _get_next_due_time(tree_data)
            return jsonify({"ok": True, "status": "no_reviews_due", "next_due": next_due, "quizzes": [], "total_due": 0})
        for d in target_nodes:
            d["title"] = leaf_map.get(d["id"], d["id"])

    related_context = _get_related_context(target_nodes, tree_data)
    quizzes = _generate_quizzes_with_ai(target_nodes, related_context)

    return jsonify({
        "ok": True, "status": "ok", "quizzes": quizzes,
        "total_due": len(_get_due_nodes(tree_data)),
    })


@knowledge_tree_bp.route("/api/knowledge-tree/review/submit", methods=["POST"])
def kt_review_submit():
    """Submit review result, update SRS, award XP."""
    body = request.get_json(silent=True) or {}
    node_id = (body.get("node_id") or "").strip()
    result = (body.get("result") or "").strip()
    quiz_type = body.get("quiz_type", "recall")
    question = body.get("question", "")
    time_spent = body.get("time_spent_seconds", 0)

    valid_results = ("forgot", "hard", "remembered", "easy")
    if not node_id or result not in valid_results:
        return jsonify({"ok": False, "error": "Invalid node_id or result"}), 400

    quest_completed = False
    with _id_lock:
        tree_data = _load_tree()
        node = tree_data.get("nodes", {}).get(node_id)
        if not node:
            return jsonify({"ok": False, "error": "Node not found"}), 404

        old_status = node.get("status")
        _update_srs(node, result)

        # Record review history (inside lock to avoid TOCTOU on reviews file)
        reviews_data = load_json(KNOWLEDGE_REVIEWS_FILE, {"reviews": [], "settings": {}})
        reviews_data.setdefault("reviews", []).append({
            "node_id": node_id,
            "reviewed_at": _now_iso(),
            "quiz_type": quiz_type,
            "question": question,
            "result": result,
            "time_spent_seconds": time_spent,
        })
        save_json(KNOWLEDGE_REVIEWS_FILE, reviews_data)

        # Check quest quiz completion
        quiz_just_passed = _check_quiz_completion(node_id, tree_data)
        if quiz_just_passed and node.get("status") in ("lit", "mastered") and old_status == "in_progress":
            quest_completed = True

        _save_tree(tree_data)

        # Snapshot values for response (while node reference is still valid)
        new_interval = node["review_status"]["interval_days"]
        next_review = node["review_status"]["next_review"]
        confidence = node["confidence"]
        new_status = node.get("status")

    # Award XP
    xp_map = {"easy": 25, "remembered": 20, "hard": 10, "forgot": 5}
    xp = xp_map.get(result, 10)

    # Quest completion bonus (node lit via quest)
    quest_bonus = 100 if quest_completed else 0

    # Check if node just became mastered
    mastered_bonus = 0
    if new_status == "mastered" and old_status != "mastered":
        mastered_bonus = 200

    # Streak bonus
    profile = _load_profile()
    _update_streak(profile)
    streak_bonus = profile.get("daily_streak", 0) * 5
    _save_profile(profile)

    total_xp = xp + mastered_bonus + streak_bonus + quest_bonus
    xp_result = _award_xp(total_xp, f"review: {result} on {node_id}")

    # Add daily login XP if first review of the day
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_reviews = [r for r in reviews_data.get("reviews", []) if r.get("reviewed_at", "").startswith(today_prefix)]
    if len(today_reviews) == 1:
        _award_xp(15, "daily review login bonus")

    log.info("Review: %s → %s (interval=%dd, xp=%d)", node_id, result, new_interval, total_xp)

    return jsonify({
        "ok": True,
        "node_id": node_id,
        "new_interval": new_interval,
        "next_review": next_review,
        "confidence": confidence,
        "xp_result": xp_result,
        "quest_completed": quest_completed,
    })


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
