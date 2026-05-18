"""Reads the BD Pipeline Notion database and returns structured lead data."""
from .client import query_database

BD_PIPELINE_DB_ID = "34fc88be4d3c8045ab26df687a6be8ce"

# Map Notion Outreach Status → dashboard stage CSS class
STATUS_TO_STAGE = {
    "New": "new",
    "Researching": "new",
    "Contacted": "contacted",
    "Replied": "warm",
    "Follow Up": "contacted",
    "Meeting Set": "warm",
    "Proposal Sent": "warm",
    "Qualified/ Won": "won",
    "Closed Won": "won",
    "Not a Fit": "rejected",
    "Ghosted": "cold",
    "Rejected": "rejected",
    # generate_v4 style statuses
    "Prospect": "new",
    "Meeting": "warm",
    "Proposal": "warm",
    "Negotiation": "warm",
    "Closed Lost": "rejected",
}

# For BD pipeline table in PDF
STATUS_TO_DISPLAY = {
    "new": "Prospect",
    "contacted": "Contacted",
    "warm": "Meeting",
    "won": "Closed Won",
    "cold": "Cold/No Reply",
    "rejected": "Closed Lost",
}


def _prop(props: dict, *names: str) -> str:
    """Try multiple column name variants and return plain text."""
    for name in names:
        p = props.get(name)
        if not p:
            continue
        pt = p.get("type", "")
        if pt == "title":
            return "".join(r["plain_text"] for r in p.get("title", []))
        if pt == "rich_text":
            return "".join(r["plain_text"] for r in p.get("rich_text", []))
        if pt == "select":
            sel = p.get("select")
            return sel["name"] if sel else ""
        if pt == "multi_select":
            return ", ".join(s["name"] for s in p.get("multi_select", []))
        if pt == "number":
            v = p.get("number")
            return str(v) if v is not None else ""
        if pt == "people":
            return ", ".join(
                u.get("name", "") for u in p.get("people", [])
            )
        if pt == "date":
            d = p.get("date")
            return d.get("start", "") if d else ""
    return ""


def fetch_bd_pipeline() -> list:
    try:
        pages = query_database(BD_PIPELINE_DB_ID)
    except Exception as e:
        return [{"error": str(e)}]

    leads = []
    for i, page in enumerate(pages):
        props = page.get("properties", {})
        company = _prop(props, "Company Name", "Perusahaan", "Name")
        contact = _prop(props, "Contact Name", "Nama Kontak", "Contact")
        title   = _prop(props, "Contact Title", "Jabatan", "Title", "Position")
        status  = _prop(props, "Outreach Status", "Status", "Stage")
        segment = _prop(props, "ICP Segment", "Segment", "ICP")
        industry= _prop(props, "Industry", "Industri")
        location= _prop(props, "Location", "Lokasi", "Kota")
        priority= _prop(props, "Priority Score", "Priority", "Score")
        owner   = _prop(props, "PIC", "Owner", "Assigned To", "BD Team")
        channel = _prop(props, "Channel", "Outreach Channel", "Kanal")
        notes   = _prop(props, "Notes", "Catatan", "Keterangan")
        next_act= _prop(props, "Next Action", "Action", "Next Step")

        stage = STATUS_TO_STAGE.get(status, "new")

        leads.append({
            "id": i + 1,
            "notion_id": page["id"],
            "name": contact or company,
            "company": company,
            "title": title,
            "stage": stage,
            "outreach_status": status,
            "owner": owner or "—",
            "channel": channel or "—",
            "icp_segment": segment,
            "industry": industry,
            "location": location,
            "priority_score": priority,
            "lastActivity": _prop(props, "Last Activity", "Aktivitas Terakhir") or "—",
            "nextAction": next_act or "—",
            "note": notes or "",
            "dateContacted": page.get("created_time", "")[:10],
            "created_time": page.get("created_time", ""),
            "last_edited": page.get("last_edited_time", ""),
        })

    return leads


def compute_funnel(leads: list) -> list:
    counts = {"all": 0, "contacted": 0, "warm": 0, "cold": 0, "rejected": 0}
    for lead in leads:
        if "error" in lead:
            continue
        counts["all"] += 1
        stage = lead.get("stage", "new")
        if stage in counts:
            counts[stage] += 1

    return [
        {"id": "all",       "label": "Total Leads",    "count": counts["all"],      "sub": "All leads",         "cls": "s-all"},
        {"id": "contacted", "label": "Contacted",      "count": counts["contacted"],"sub": "Reached out",       "cls": "s-contacted"},
        {"id": "warm",      "label": "Warm",           "count": counts["warm"],     "sub": "Positive response", "cls": "s-warm"},
        {"id": "cold",      "label": "Cold/No Reply",  "count": counts["cold"],     "sub": "No response",       "cls": "s-cold"},
        {"id": "rejected",  "label": "Rejected",       "count": counts["rejected"], "sub": "Not a fit",         "cls": "s-rejected"},
    ]


def build_pipeline_for_pdf(leads: list, max_rows: int = 20) -> list:
    """
    Return (company, display_stage, owner, notes) tuples for the PDF pipeline table.
    Only includes contacted/warm/won leads (excludes pure 'new').
    """
    active = [l for l in leads if l.get("stage") not in ("new",) and "error" not in l]
    active.sort(key=lambda l: {"won": 0, "warm": 1, "contacted": 2, "cold": 3, "rejected": 4}.get(l.get("stage", "new"), 5))
    rows = []
    for l in active[:max_rows]:
        stage_display = STATUS_TO_DISPLAY.get(l["stage"], l.get("outreach_status", "—"))
        rows.append((
            l["company"] or l["name"],
            stage_display,
            l["owner"],
            l.get("note") or l.get("nextAction") or "—",
        ))
    return rows
