"""PLD API client — fetches planning applications from London City Hall's
Planning London Datahub (Elasticsearch v7.9 under the hood)."""

import requests
from datetime import datetime, timedelta

API_URL = "https://planningdata.london.gov.uk/api-guest/applications/_search"

HEADERS = {
    "X-API-AllowRequest": "be2rmRnt&",
    "Content-Type": "application/json",
    "User-Agent": "BaulogicPlanningMonitor/1.0 (lead generation)",
}

# Exact spellings as they appear in the PLD data (confirmed via recon)
TARGET_BOROUGHS = ["Westminster", "Kensington & Chelsea"]

# Fields we actually use downstream. Pulling fewer fields = faster, cheaper.
FIELDS = [
    "id",
    "lpa_name",
    "lpa_app_no",
    "valid_date",
    "decision_date",
    "decision",
    "status",
    "application_type",
    "application_type_full",
    "description",
    "site_name",
    "site_number",
    "street_name",
    "locality",
    "postcode",
    "ward",
    "centroid",
    "url_planning_app",
    "last_updated",
]

PAGE_SIZE = 200  # max results per request


def _build_query(since_date: str, from_offset: int = 0) -> dict:
    """Build the Elasticsearch query body."""
    return {
        "from": from_offset,
        "size": PAGE_SIZE,
        "sort": [{"valid_date": "desc"}],
        "query": {
            "bool": {
                "must": [
                    {
                        "bool": {
                            "should": [
                                {"term": {"lpa_name.raw": borough}}
                                for borough in TARGET_BOROUGHS
                            ]
                        }
                    },
                    {"range": {"valid_date": {"gte": since_date}}},
                ]
            }
        },
        "_source": FIELDS,
    }


def fetch_recent_applications(days_back: int = 7) -> list[dict]:
    """Fetch all applications validated in the last `days_back` days for
    the target boroughs. Handles pagination automatically."""
    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d/%m/%Y")
    print(f"[fetch] Querying PLD for applications since {since_date}")
    print(f"[fetch] Boroughs: {', '.join(TARGET_BOROUGHS)}")

    all_apps: list[dict] = []
    offset = 0

    while True:
        query = _build_query(since_date, from_offset=offset)
        response = requests.post(API_URL, headers=HEADERS, json=query, timeout=60)
        response.raise_for_status()
        data = response.json()

        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {}).get("value", 0)

        if offset == 0:
            print(f"[fetch] Total matching applications: {total}")

        if not hits:
            break

        # Extract just the _source payload from each hit
        all_apps.extend(hit["_source"] for hit in hits)

        offset += PAGE_SIZE
        if offset >= total:
            break

        # PLD's Elasticsearch caps deep pagination at 10,000 — sanity check
        if offset >= 10000:
            print("[fetch] Hit 10k pagination ceiling — stopping")
            break

    print(f"[fetch] Retrieved {len(all_apps)} applications")
    return all_apps


if __name__ == "__main__":
    # Quick smoke test — only runs when you call `python src/fetch.py` directly
    apps = fetch_recent_applications(days_back=7)
    print(f"\nFirst result keys: {list(apps[0].keys()) if apps else 'no results'}")
