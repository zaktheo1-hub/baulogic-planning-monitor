"""Baulogic planning lead monitor — orchestrator.

Pipeline:
  1. Fetch recent applications from the PLD API
  2. Filter to new-build residential only
  3. Score and rank by postcode tier + value signals + recency
  4. Render HTML email + markdown digest
  5. Send email via Resend
  6. Save markdown to /digests/ as audit trail
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from src.fetch import fetch_recent_applications
from src.filter import filter_applications
from src.score import score_and_rank
from src.render import render_html, render_markdown
from src.send import send_email


# How far back to look. 7 days = one week of new applications.
DAYS_BACK = 7

# Where to save the markdown audit trail
DIGESTS_DIR = Path("digests")


def main() -> int:
    print("=" * 70)
    print(f"Baulogic Planning Monitor — {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 70)

    # ---- Read config from environment ----
    resend_api_key = os.environ.get("RESEND_API_KEY")
    recipient = os.environ.get("DIGEST_RECIPIENT")

    if not resend_api_key:
        print("[fatal] RESEND_API_KEY not set")
        return 1
    if not recipient:
        print("[fatal] DIGEST_RECIPIENT not set")
        return 1

    # ---- Pipeline ----
    try:
        apps = fetch_recent_applications(days_back=DAYS_BACK)
        qualifying = filter_applications(apps)
        ranked = score_and_rank(qualifying)
    except Exception as e:
        print(f"[fatal] Pipeline failed before rendering: {e}")
        raise

    # ---- Render ----
    html_body = render_html(ranked, days_back=DAYS_BACK)
    markdown_body = render_markdown(ranked, days_back=DAYS_BACK)

    # ---- Save markdown audit trail ----
    DIGESTS_DIR.mkdir(exist_ok=True)
    digest_path = DIGESTS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    digest_path.write_text(markdown_body, encoding="utf-8")
    print(f"[main] Wrote audit trail to {digest_path}")

    # ---- Send email ----
    week_label = datetime.now().strftime("%-d %b %Y")
    lead_count = len(ranked)
    if lead_count == 0:
        subject = f"Planning leads · {week_label} · no qualifying applications"
    else:
        ultra = sum(
            1 for a in ranked if "ultra-prime" in a["_score"]["postcode_tier"]
        )
        subject = (
            f"Planning leads · {week_label} · "
            f"{lead_count} lead{'s' if lead_count != 1 else ''}"
            + (f" ({ultra} ultra-prime)" if ultra else "")
        )

    send_email(
        html_body=html_body,
        subject=subject,
        to_email=recipient,
        api_key=resend_api_key,
    )

    print("[main] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
