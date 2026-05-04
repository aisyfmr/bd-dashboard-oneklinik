#!/usr/bin/env python3
"""
fetch_notion_data.py

Local utility script — run manually to pull leads from Notion and push them
to data.json via POST /update-data.  NOT imported by app.py and NOT required
for the Railway deployment to work.

Usage (local only):
    python fetch_notion_data.py

NOTE: NOTION_TOKEN and direct Notion API calls are not used by the deployed app.
Data is managed via data.json which is bundled with the repo.
"""
import os
import sys
import requests

# ── Config ─────────────────────────────────────────────────────────────────
DATABASE_ID   = "34fc88be-4d3c-8045-ab26-df687a6be8ce"
NOTION_API    = "https://api.notion.com/v1"
NOTION_VER    = "2022-06-28"
DASHBOARD_URL = "http://localhost:5000/update-data"

# NOTION_TOKEN is only needed when running this script locally.
# It is NOT read on startup and NOT required by the Railway deployment.
# To use: set NOTION_TOKEN in your local .env file before running.


# ── Notion request headers ──────────────────────────────────────────────────

def notion_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VER,
        "Content-Type": "application/json",
    }


# ── Property value extractors ───────────────────────────────────────────────

def get_text(prop):
    if not prop:
        return ""
    ptype = prop.get("type", "")
    items = prop.get(ptype, [])
    if isinstance(items, list):
        return "".join(chunk.get("plain_text", "") for chunk in items).strip()
    return ""


def get_select(prop):
    if not prop:
        return ""
    ptype = prop.get("type", "")
    value = prop.get(ptype) or {}
    return value.get("name", "") if isinstance(value, dict) else ""


def get_email(prop):
    if not prop:
        return ""
    if prop.get("type") == "email":
        return prop.get("email") or ""
    return get_text(prop)


def get_created_time(page, props):
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
    return page["created_time"]


# ── Notion database fetcher ─────────────────────────────────────────────────

def query_database(database_id, headers):
    url = f"{NOTION_API}/databases/{database_id}/query"
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("results", [])
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]


# ── Page → lead mapper ──────────────────────────────────────────────────────

def page_to_lead(page):
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


# ── Main (local use only) ───────────────────────────────────────────────────

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

    print(f"Fetching from Notion database {DATABASE_ID} ...")
    try:
        pages = list(query_database(DATABASE_ID, headers))
    except requests.exceptions.ConnectionError:
        sys.exit("Error: Could not reach api.notion.com — check your internet connection.")

    print(f"  {len(pages)} page(s) retrieved from Notion")

    leads = [page_to_lead(p) for p in pages]
    leads = [l for l in leads if l["companyName"]]
    print(f"  {len(leads)} lead(s) after filtering empty rows")

    if not leads:
        print("Nothing to push — exiting.")
        return

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
