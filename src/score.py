"""Rule-based scoring for qualifying planning applications.

Higher score = more likely to be a Baulogic-fit project. The dominant
signal is postcode — Baulogic's market is prime/ultra-prime central
London, and postcode is the cheapest, most reliable proxy for that."""

import re
from datetime import datetime

# Postcode tiers — score out of 50.
# Ultra-prime: the absolute core market.
ULTRA_PRIME_PREFIXES = ["W1", "SW1", "SW3", "SW7", "W8"]
ULTRA_PRIME_SCORE = 50

# Prime: still strong, slightly less consistent.
PRIME_PREFIXES = ["SW10", "W2", "W11", "NW1", "NW3", "NW8"]
PRIME_SCORE = 35

# Anywhere else in the target boroughs.
OTHER_SCORE = 15

# Value signals — score out of 35 in total, capped.
# Each match adds points; the more luxury indicators, the higher the score.
VALUE_SIGNALS: dict[str, int] = {
    # Basement excavation is the single strongest "prime central London"
    # signal — these are nearly always £multi-million projects.
    "basement": 12,
    "excavation": 10,
    "subterranean": 10,
    # Listed buildings = high-spec restoration + new build
    "listed building": 8,
    "grade i": 10,
    "grade ii": 6,
    # Building type signals
    "mews": 8,
    "townhouse": 6,
    "townhouses": 6,
    # Luxury features
    "swimming pool": 8,
    "pool": 4,
    "spa": 6,
    "gym": 4,
    "cinema": 6,
    "lift": 5,
    "elevator": 5,
    # Scale signals
    "storey": 3,
    "storeys": 3,
    "floors": 2,
    # Quality signals
    "luxury": 5,
    "high-end": 5,
    "high specification": 5,
    "bespoke": 4,
}

VALUE_SIGNAL_CAP = 35  # don't let a single application run away with points

# Recency boost (0-15)
RECENCY_BOOST_DAYS = 7
RECENCY_MAX_BOOST = 15


def _postcode_tier(postcode: str) -> tuple[str, int]:
    """Return (tier_label, points) for the given postcode."""
    if not postcode:
        return ("unknown", 0)

    # Normalise: strip spaces, uppercase. UK postcodes like "W1K 4AB" -> "W1K4AB"
    normalised = postcode.replace(" ", "").upper()

    # Check ultra-prime first (longer prefixes win — SW10 beats SW1 if both matched)
    for prefix in sorted(ULTRA_PRIME_PREFIXES + PRIME_PREFIXES, key=len, reverse=True):
        if normalised.startswith(prefix):
            # Make sure the next char isn't a digit (so "SW1" matches "SW1A"
            # but not "SW10") — UK postcodes have district numbers
            after_prefix = normalised[len(prefix):]
            if after_prefix and after_prefix[0].isdigit():
                # The prefix had more digits — keep looking
                continue
            if prefix in ULTRA_PRIME_PREFIXES:
                return (f"ultra-prime ({prefix})", ULTRA_PRIME_SCORE)
            return (f"prime ({prefix})", PRIME_SCORE)

    return ("other", OTHER_SCORE)


def _value_signal_score(description: str) -> tuple[int, list[str]]:
    """Return (points, matched_signals) from value-signal keywords."""
    if not description:
        return (0, [])
    text_lower = description.lower()
    total = 0
    matched: list[str] = []
    for signal, points in VALUE_SIGNALS.items():
        pattern = r"\b" + re.escape(signal) + r"\b"
        if re.search(pattern, text_lower):
            matched.append(signal)
            total += points
    return (min(total, VALUE_SIGNAL_CAP), matched)


def _recency_boost(valid_date_str: str) -> int:
    """Newer applications score higher. Returns 0-15."""
    if not valid_date_str:
        return 0
    try:
        valid_date = datetime.strptime(valid_date_str, "%d/%m/%Y")
    except ValueError:
        return 0
    days_old = (datetime.now() - valid_date).days
    if days_old < 0:
        # Future-dated (data entry quirks exist in PLD) — treat as today
        days_old = 0
    if days_old >= RECENCY_BOOST_DAYS:
        return 0
    # Linear decay: day 0 = max boost, day 7 = 0
    return int(RECENCY_MAX_BOOST * (1 - days_old / RECENCY_BOOST_DAYS))


def score_application(app: dict) -> dict:
    """Score one application. Mutates the dict to add a `_score` key
    containing both the total and the breakdown."""
    postcode = app.get("postcode") or ""
    description = app.get("description") or ""
    valid_date = app.get("valid_date") or ""

    tier_label, postcode_points = _postcode_tier(postcode)
    value_points, value_matches = _value_signal_score(description)
    recency_points = _recency_boost(valid_date)

    total = postcode_points + value_points + recency_points

    app["_score"] = {
        "total": total,
        "postcode_tier": tier_label,
        "postcode_points": postcode_points,
        "value_points": value_points,
        "value_matches": value_matches,
        "recency_points": recency_points,
    }
    return app


def score_and_rank(apps: list[dict]) -> list[dict]:
    """Score every application and return them sorted by total (high to low)."""
    scored = [score_application(a) for a in apps]
    ranked = sorted(scored, key=lambda a: a["_score"]["total"], reverse=True)
    print(f"[score] Scored and ranked {len(ranked)} applications")
    if ranked:
        top = ranked[0]["_score"]["total"]
        bottom = ranked[-1]["_score"]["total"]
        print(f"[score] Score range: {bottom} → {top}")
    return ranked
