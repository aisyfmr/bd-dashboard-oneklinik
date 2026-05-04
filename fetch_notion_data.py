#!/usr/bin/env python3
"""
fetch_notion_data.py

Pulls leads from the OneKlinik BD Notion database and pushes them
to the local dashboard via POST /update-data.

Usage:
    python fetch_notion_data.py

Requires:
    - .env file with NOTION_TOKEN set (copy from .env.example)
    - Dashboard running on http://localhost:5000
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

DATABASE_ID   = "34fc88be-4d3c-8045-ab26-df687a6be8ce"
NOTION_API    = "https://api.notion.com/v1"
NOTION_VER    = "2022-06-28"
DASHBOARD_URL = "http://localhost:5000/update-data"


# ── Notion request headers ─────────────────────────────────────────────────

def notion_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VER,
        "Content-Type": "application/json",
    }


# ── Property value extractors ──────────────────────────────────────────────

def get_text(prop):
    """Extract plain text from a title or rich_text property."""
    if not prop:
        return ""
    ptype = prop.get("type", "")
    items = prop.get(ptype, [])
    if isinstance(items, list):
        return "".join(chunk.get("plain_text", "") for chunk in items).strip()
    return ""


def get_select(prop):
    """Extract the option name from a select or status property."""
    if not prop:
        return ""
    ptype = prop.get("type", "")
    value = prop.get(ptype) or {}
    return value.get("name", "") if isinstance(value, dict) else ""


def get_email(prop):
    """Extract value from an email property, falling back to rich_text."""
    if not prop:
        return ""
    if prop.get("type") == "email":
        return prop.get("email") or ""
    return get_text(prop)


def get_created_time(page, props):
    """
    Resolve the createdTime field by checking (in order):
      1. A database property of type created_time or date with a matching name
      2. The page-level created_time from Notion metadata (always present)
    """
    candidate_keys = (
        "Created Time", "Created time", "createdTime",
        "Date Created", "Date", "Tanggal",
    )
    for key in candidate_keys:
        p = props.get(key)
        if not p:
            continue
        ptype = p.get("type")
        if ptype == "created_time":
            return p.get("created_time") or page["created_time"]
        if ptype == "date" and p.get("date"):
            return p["date"]["start"]

    # Fallback: every Notion page object has a top-level created_time
    return page["created_time"]


# ── Notion database fetcher ────────────────────────────────────────────────

def query_database(database_id, headers):
    """
    Generator that yields every page from a Notion database,
    automatically following pagination cursors.
    """
    url = f"{NOTION_API}/databases/{database_id}/query"
    cursor = None

    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor

        resp = requests.post(url, headers=headers, json=body, timeout=30)

        if resp.status_code == 401:
            sys.exit(
                "Error: NOTION_TOKEN is invalid or expired.\n"
                "Check the token in your .env file."
            )
        if resp.status_code == 403:
            sys.exit(
                "Error: Integration does not have access to this database.\n"
                "In Notion, open the database → ··· menu → Connections → add your integration."
            )
        if resp.status_code == 404:
            sys.exit(
                f"Error: Database '{database_id}' not found.\n"
                "Double-check the DATABASE_ID in this script."
            )

        resp.raise_for_status()
        data = resp.json()

        yield from data.get("results", [])

        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]


# ── Page → lead mapper ─────────────────────────────────────────────────────

def page_to_lead(page):
    """Map one Notion page object to our data.json lead structure."""
    props = page.get("properties", {})
    return {
        "companyName":    get_text(props.get("Company Name")),
        "icpSegment":     get_select(props.get("ICP Segment")),
        "location":       get_text(props.get("Location")),
        "contactName":    get_text(props.get("Contact Name")),
        "contactTitle":   get_text(props.get("Contact Title")),
        "contactEmail":   get_email(props.get("Contact Email")),
        "outreachStatus": get_select(props.get("Outreach Status")),
        "createdTime":    get_created_time(page, props),
    }


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        sys.exit(
            "Error: NOTION_TOKEN is not set.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Fill in your Notion integration token\n"
            "  3. Re-run this script"
        )

    headers = notion_headers(token)

    # ── Fetch ──────────────────────────────────────────────
    print(f"Fetching from Notion database {DATABASE_ID} ...")
    try:
        pages = list(query_database(DATABASE_ID, headers))
    except requests.exceptions.ConnectionError:
        sys.exit("Error: Could not reach api.notion.com — check your internet connection.")

    print(f"  {len(pages)} page(s) retrieved from Notion")

    # ── Map ────────────────────────────────────────────────
    leads = [page_to_lead(p) for p in pages]

    # Drop blank rows (deleted/empty pages in Notion show up with no title)
    leads = [l for l in leads if l["companyName"]]
    print(f"  {len(leads)} lead(s) after filtering empty rows")

    if not leads:
        print("Nothing to push — exiting.")
        return

    # ── Push ───────────────────────────────────────────────
    print(f"Pushing to {DASHBOARD_URL} ...")
    try:
        resp = requests.post(DASHBOARD_URL, json=leads, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(
            "Error: Could not connect to the dashboard.\n"
            "Make sure 'python app.py' is running on port 5000."
        )
    except requests.exceptions.HTTPError as exc:
        sys.exit(f"Dashboard rejected the data: {exc}\n{resp.text}")

    result = resp.json()
    print(f"Done — {result['saved']} record(s) saved to data.json")


if __name__ == "__main__":
    main()
