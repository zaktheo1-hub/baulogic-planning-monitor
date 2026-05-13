"""Render ranked leads into an HTML email and a markdown audit file."""

from datetime import datetime
from html import escape


def _format_address(app: dict) -> str:
    """Best-effort address reconstruction from PLD fields."""
    parts = [
        app.get("site_name") or "",
        app.get("site_number") or "",
        app.get("street_name") or "",
        app.get("locality") or "",
        app.get("postcode") or "",
    ]
    return ", ".join(p.strip() for p in parts if p and p.strip())


# Per-borough planning portal search URLs. The app number gets appended
# as a search query — the user lands on a results page with their
# application at the top, then clicks through.
# Westminster uses Idox Public Access. Their keyword search (searchCriteria.simpleSearchString)
# is the most forgiving endpoint — it accepts the raw application reference and lands
# the user on a results page with their application as the only hit.
# K&C also uses Idox now (migrated from their legacy portal), same pattern.
# Each borough's planning portal homepage. We don't try to deep-link — Idox
# uses session-based search and stable per-application URLs aren't reliable.
# Instead we send the user to the search page and they paste the ref.
BOROUGH_PORTAL_HOME: dict[str, str] = {
    "Westminster": "https://idoxpa.westminster.gov.uk/online-applications/",
    "Kensington & Chelsea": "https://www.rbkc.gov.uk/planning/searches/default.aspx?search=true",
}


def _planning_portal_url(app: dict) -> str | None:
    """Return the best available link to the borough's planning portal."""
    # 1. If the PLD record has a direct URL, trust it.
    direct = app.get("url_planning_app")
    if direct:
        return direct

    app_no = app.get("lpa_app_no")
    lpa = app.get("lpa_name")
    if not app_no or not lpa:
        return None

    # 2. Borough-specific Idox keyword search (URL-encode the ref).
    from urllib.parse import quote
    base = BOROUGH_PORTAL_BASE.get(lpa)
    if base:
        encoded_ref = quote(app_no, safe="")
        return IDOX_KEYWORD_SEARCH_TEMPLATE.format(base=base, ref=encoded_ref)

    # 3. Fall back to a Google search (better than nothing for unknown boroughs).
    query = f"{lpa} planning {app_no}".replace(" ", "+")
    return f"https://www.google.com/search?q={query}"


def _score_colour(total: int) -> str:
    """Colour code for the score badge."""
    if total >= 75:
        return "#16a34a"  # green
    if total >= 50:
        return "#f59e0b"  # amber
    return "#94a3b8"  # grey


def render_html(apps: list[dict], days_back: int) -> str:
    """Render the full HTML email body."""
    week_end = datetime.now().strftime("%-d %B %Y")
    total_leads = len(apps)

    # Group by tier for the summary header
    ultra = sum(1 for a in apps if "ultra-prime" in a["_score"]["postcode_tier"])
    prime = sum(
        1
        for a in apps
        if "prime" in a["_score"]["postcode_tier"]
        and "ultra-prime" not in a["_score"]["postcode_tier"]
    )
    other = total_leads - ultra - prime

    header = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 720px; margin: 0 auto; padding: 24px; color: #0f172a;">
      <h1 style="font-size: 24px; margin: 0 0 8px;">Planning leads — week ending {week_end}</h1>
      <p style="color: #64748b; margin: 0 0 24px;">
        New-build residential applications validated in the last {days_back} days
        across Westminster and Kensington &amp; Chelsea.
      </p>
      <div style="background: #f1f5f9; border-radius: 8px; padding: 16px 20px; margin-bottom: 32px;">
        <strong style="font-size: 18px;">{total_leads} qualifying lead{"s" if total_leads != 1 else ""}</strong>
        <span style="color: #64748b;">&nbsp;·&nbsp;</span>
        <span style="color: #16a34a;"><strong>{ultra}</strong> ultra-prime</span>
        <span style="color: #64748b;">&nbsp;·&nbsp;</span>
        <span style="color: #f59e0b;"><strong>{prime}</strong> prime</span>
        <span style="color: #64748b;">&nbsp;·&nbsp;</span>
        <span style="color: #94a3b8;"><strong>{other}</strong> other</span>
      </div>
    """

    if not apps:
        body = """
        <p style="color: #64748b;">No qualifying applications this week.
        That's normal — new builds in prime central London are rare.</p>
        """
        return header + body + "</div>"

    cards = []
    for i, app in enumerate(apps, 1):
        score = app["_score"]
        reasoning = app.get("_reasoning", {})
        address = _format_address(app)
        description = (app.get("description") or "").strip()
        if len(description) > 400:
            description = description[:400].rsplit(" ", 1)[0] + "…"
        portal_url = _planning_portal_url(app)
        new_build_matches = reasoning.get("new_build_matches", [])
        value_matches = score.get("value_matches", [])

        colour = _score_colour(score["total"])

        portal_link = (
            f'<a href="{escape(portal_url)}" style="color: #2563eb; text-decoration: none;">'
            f'View application →</a>'
            if portal_url
            else ""
        )

        signal_chips = ""
        for sig in new_build_matches[:3]:
            signal_chips += (
                f'<span style="background: #dbeafe; color: #1e40af; '
                f'padding: 2px 8px; border-radius: 4px; font-size: 12px; '
                f'margin-right: 4px;">{escape(sig)}</span>'
            )
        for sig in value_matches[:4]:
            signal_chips += (
                f'<span style="background: #fef3c7; color: #92400e; '
                f'padding: 2px 8px; border-radius: 4px; font-size: 12px; '
                f'margin-right: 4px;">{escape(sig)}</span>'
            )

        card = f"""
        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <div style="flex: 1;">
              <div style="font-size: 12px; color: #64748b; margin-bottom: 4px;">
                #{i} &nbsp;·&nbsp; {escape(app.get("lpa_name", ""))} &nbsp;·&nbsp; {escape(score["postcode_tier"])}
              </div>
              <div style="font-size: 16px; font-weight: 600; color: #0f172a;">
                {escape(address) or "(no address)"}
              </div>
            </div>
            <div style="background: {colour}; color: white; font-weight: 700;
                        padding: 6px 12px; border-radius: 6px; font-size: 14px; margin-left: 12px;">
              {score["total"]}
            </div>
          </div>
          <p style="color: #334155; line-height: 1.5; margin: 0 0 12px; font-size: 14px;">
            {escape(description)}
          </p>
          <div style="margin-bottom: 12px;">{signal_chips}</div>
          <div style="font-size: 12px; color: #64748b;">
            Ref: {escape(app.get("lpa_app_no", ""))} &nbsp;·&nbsp;
            Validated: {escape(app.get("valid_date", ""))} &nbsp;·&nbsp;
            {portal_link}
          </div>
        </div>
        """
        cards.append(card)

    footer = """
    <p style="color: #94a3b8; font-size: 12px; margin-top: 32px; padding-top: 16px; border-top: 1px solid #e2e8f0;">
      Generated by baulogic-planning-monitor · Data from Planning London Datahub
    </p>
    </div>
    """

    return header + "".join(cards) + footer


def render_markdown(apps: list[dict], days_back: int) -> str:
    """Render the digest as markdown (for the audit trail in /digests/)."""
    week_end = datetime.now().strftime("%d %B %Y")
    lines = [
        f"# Planning leads — week ending {week_end}",
        "",
        f"New-build residential applications validated in the last "
        f"{days_back} days across Westminster and Kensington & Chelsea.",
        "",
        f"**{len(apps)} qualifying lead{'s' if len(apps) != 1 else ''}**",
        "",
        "---",
        "",
    ]

    if not apps:
        lines.append("_No qualifying applications this week._")
        return "\n".join(lines)

    for i, app in enumerate(apps, 1):
        score = app["_score"]
        reasoning = app.get("_reasoning", {})
        address = _format_address(app)
        description = (app.get("description") or "").strip()
        portal_url = _planning_portal_url(app)

        lines.append(f"## {i}. {address or '(no address)'} — **{score['total']}/100**")
        lines.append("")
        lines.append(
            f"**{app.get('lpa_name', '')}** · {score['postcode_tier']} · "
            f"Ref: `{app.get('lpa_app_no', '')}` · "
            f"Validated: {app.get('valid_date', '')}"
        )
        lines.append("")
        lines.append(f"> {description}")
        lines.append("")
        lines.append(
            f"- **New-build signals:** {', '.join(reasoning.get('new_build_matches', [])) or '—'}"
        )
        lines.append(
            f"- **Value signals:** {', '.join(score.get('value_matches', [])) or '—'}"
        )
        lines.append(
            f"- **Score breakdown:** postcode {score['postcode_points']} + "
            f"value {score['value_points']} + recency {score['recency_points']}"
        )
        if portal_url:
            lines.append(f"- [View application]({portal_url})")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)
