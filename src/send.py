"""Send the rendered digest via Resend."""

import requests

RESEND_API_URL = "https://api.resend.com/emails"

# Resend's default sender — works without domain verification.
# Swap to a verified domain (e.g. "Baulogic Leads <leads@baulogic.com>")
# once you've added DNS records in Resend.
DEFAULT_FROM = "Planning Monitor <onboarding@resend.dev>"


def send_email(
    html_body: str,
    subject: str,
    to_email: str,
    api_key: str,
    from_address: str = DEFAULT_FROM,
) -> dict:
    """Send the digest email via Resend. Returns Resend's response payload."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": from_address,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    print(f"[send] Sending email to {to_email}")
    response = requests.post(
        RESEND_API_URL, headers=headers, json=payload, timeout=30
    )
    if response.status_code >= 400:
        print(f"[send] Resend error {response.status_code}: {response.text}")
        response.raise_for_status()
    data = response.json()
    print(f"[send] Email sent successfully (id: {data.get('id', 'unknown')})")
    return data
