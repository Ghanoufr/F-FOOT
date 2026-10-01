"""Weighted evaluation formula for Foura Goalkeeper Coach.

Each criterion is converted into a success percentage (0-100), then combined
using its weight. Criteria without data (e.g. no penalty faced) are excluded
and the remaining weights are re-normalised, so the overall score always
reflects what actually happened during the match.
"""

GOALS_REFERENCE = 5  # a keeper conceding 5+ goals scores 0 on the goals criterion

CATEGORIES = (
    {"key": "saves", "weight": 18},
    {"key": "duels", "weight": 14},
    {"key": "crosses", "weight": 12},
    {"key": "goals", "weight": 12},
    {"key": "interventions", "weight": 12},
    {"key": "distribution", "weight": 10},
    {"key": "aerial", "weight": 8},
    {"key": "command", "weight": 6},
    {"key": "sweeper", "weight": 5},
    {"key": "penalties", "weight": 3},
)

# criterion -> (successful field, attempted field)
RATIO_FIELDS = {
    "crosses": ("crosses_successful", "crosses_attempted"),
    "interventions": ("interventions_good", "interventions_total"),
    "duels": ("duels_won", "duels_total"),
    "distribution": ("passes_completed", "passes_attempted"),
    "command": ("commands_good", "commands_total"),
    "aerial": ("aerial_won", "aerial_total"),
    "sweeper": ("sweeper_successful", "sweeper_total"),
    "penalties": ("penalties_saved", "penalties_faced"),
}

RATING_BANDS = (
    (85, "excellent"),
    (70, "good"),
    (55, "average"),
    (40, "below_average"),
    (0, "poor"),
)

COLORS = {
    "excellent": "#22c55e",
    "good": "#84cc16",
    "average": "#eab308",
    "below_average": "#f97316",
    "poor": "#ef4444",
}


def _ratio(successful, total):
    total = max(int(total or 0), 0)
    if total <= 0:
        return None
    successful = min(max(int(successful or 0), 0), total)
    return successful / total


def _category_score(key, stats):
    """Return (score 0..1 or None when the situation never occurred, detail)."""
    if key == "saves":
        saves = max(int(stats.get("saves") or 0), 0)
        conceded = max(int(stats.get("goals_conceded") or 0), 0)
        total = saves + conceded
        ratio = _ratio(saves, total)
        return ratio, (f"{saves}/{total}" if ratio is not None else "\u2014")

    if key == "goals":
        conceded = max(int(stats.get("goals_conceded") or 0), 0)
        ratio = max(0.0, 1 - min(conceded, GOALS_REFERENCE) / GOALS_REFERENCE)
        return ratio, str(conceded)

    successful_field, total_field = RATIO_FIELDS[key]
    successful = max(int(stats.get(successful_field) or 0), 0)
    total = max(int(stats.get(total_field) or 0), 0)
    ratio = _ratio(successful, total)
    detail = f"{min(successful, total)}/{total}" if ratio is not None else "\u2014"
    return ratio, detail


def rating_key(score):
    for threshold, key in RATING_BANDS:
        if score >= threshold:
            return key
    return "poor"


def score_color(score):
    return COLORS[rating_key(score)]


def compute_evaluation(stats):
    """Evaluate a match from its statistics.

    Returns a JSON-serialisable dict with the overall score (0-100), the
    rating key, a display colour and the per-criterion breakdown.
    """
    rows = []
    weighted_sum = 0.0
    applied_weight = 0.0

    for category in CATEGORIES:
        ratio, detail = _category_score(category["key"], stats)
        applicable = ratio is not None
        rows.append({
            "key": category["key"],
            "weight": category["weight"],
            "score": round(ratio * 100, 1) if applicable else None,
            "detail": detail,
            "applicable": applicable,
        })
        if applicable:
            weighted_sum += category["weight"] * ratio
            applied_weight += category["weight"]

    overall = round(weighted_sum / applied_weight * 100, 1) if applied_weight else 0.0
    return {
        "overall": overall,
        "rating_key": rating_key(overall),
        "color": score_color(overall),
        "applied_weight": applied_weight,
        "categories": rows,
    }
