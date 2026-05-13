"""New-build qualifying rules for Baulogic planning leads.

Baulogic only fits during first fix on new builds. This filter rejects
refurbishments, extensions, conversions, and anything that isn't a fresh
residential build."""

import re

# We don't care about Householder (alterations to existing dwellings) or
# Prior Approval (permitted-development minor stuff). "All Other" is the
# bucket containing full planning permission, the only one with new builds.
ACCEPTED_APPLICATION_TYPES = {"All Other"}

# At least ONE of these phrases must appear in the description.
# These are the words planners use when describing a new structure.
NEW_BUILD_SIGNALS = [
    "new build",
    "new-build",
    "newbuild",
    "erection of",
    "redevelopment",
    "construction of",
    "replacement dwelling",
    "replacement building",
    "new dwelling",
    "new dwellings",
    "new house",
    "new houses",
    "new flat",
    "new flats",
    "new apartment",
    "new apartments",
    "new residential",
]

# At least ONE of these must appear — confirms the end use is residential.
RESIDENTIAL_SIGNALS = [
    "dwelling",
    "house",
    "houses",
    "residential",
    "flat",
    "flats",
    "apartment",
    "apartments",
    "mews",
    "townhouse",
    "townhouses",
    "maisonette",
]

# If ANY of these appear, the application is rejected — even if it also
# contains new-build signals. These are strong "not a new build" markers.
DISQUALIFIERS = [
    "extension",
    "extensions",
    "refurbishment",
    "refurbish",
    "refurbished",
    "conversion",
    "convert",
    "converting",
    "alteration to existing",
    "internal alterations",
    "internal works",
    "change of use",
    "tree",
    "advertisement",
    "advertising consent",
    "signage",
    "hoarding",
    "telecoms",
    "telecommunications",
    "antenna",
    "shopfront",
]


def _contains_any(text: str, phrases: list[str]) -> list[str]:
    """Return the list of phrases found in `text` (case-insensitive,
    word-boundary aware so 'house' doesn't match 'household')."""
    if not text:
        return []
    text_lower = text.lower()
    matches = []
    for phrase in phrases:
        # \b is a word boundary — prevents 'house' matching 'household'.
        # For multi-word phrases we only enforce boundary at the ends.
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, text_lower):
            matches.append(phrase)
    return matches


def qualify(app: dict) -> tuple[bool, dict]:
    """Return (qualifies, reasoning).

    `reasoning` is a dict with the matches found at each stage — useful
    for the email digest and for debugging false positives/negatives."""
    description = app.get("description") or ""
    app_type = app.get("application_type") or ""

    reasoning: dict = {
        "new_build_matches": [],
        "residential_matches": [],
        "disqualifier_matches": [],
        "rejected_reason": None,
    }

    # Gate 1: application type
    if app_type not in ACCEPTED_APPLICATION_TYPES:
        reasoning["rejected_reason"] = f"application_type='{app_type}' not accepted"
        return False, reasoning

    # Gate 2: new-build signal must be present
    new_build_matches = _contains_any(description, NEW_BUILD_SIGNALS)
    reasoning["new_build_matches"] = new_build_matches
    if not new_build_matches:
        reasoning["rejected_reason"] = "no new-build signal in description"
        return False, reasoning

    # Gate 3: residential signal must be present
    residential_matches = _contains_any(description, RESIDENTIAL_SIGNALS)
    reasoning["residential_matches"] = residential_matches
    if not residential_matches:
        reasoning["rejected_reason"] = "no residential signal in description"
        return False, reasoning

    # Gate 4: disqualifiers
    disqualifier_matches = _contains_any(description, DISQUALIFIERS)
    reasoning["disqualifier_matches"] = disqualifier_matches
    if disqualifier_matches:
        reasoning["rejected_reason"] = (
            f"disqualified by: {', '.join(disqualifier_matches)}"
        )
        return False, reasoning

    return True, reasoning


def filter_applications(apps: list[dict]) -> list[dict]:
    """Apply the new-build filter to a list of applications.
    Returns only the qualifying ones, each enriched with a `_reasoning` key."""
    qualifying = []
    rejected_counts: dict[str, int] = {}

    for app in apps:
        ok, reasoning = qualify(app)
        if ok:
            app["_reasoning"] = reasoning
            qualifying.append(app)
        else:
            reason = reasoning.get("rejected_reason", "unknown")
            # Bucket rejection reasons for the summary
            bucket = reason.split(":")[0] if ":" in reason else reason
            rejected_counts[bucket] = rejected_counts.get(bucket, 0) + 1

    print(f"[filter] {len(qualifying)} of {len(apps)} applications qualified")
    if rejected_counts:
        print(f"[filter] Rejection breakdown:")
        for reason, count in sorted(
            rejected_counts.items(), key=lambda x: -x[1]
        ):
            print(f"  - {reason}: {count}")

    return qualifying
