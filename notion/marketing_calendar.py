"""Reads the Marketing Calendar Notion database and formats it for the dashboard."""
from .client import query_database

MARKETING_CAL_DB_ID = "34fc88be4d3c804fb02ed1ede853dc10"

MONTHS_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
             "Jul", "Ags", "Sep", "Okt", "Nov", "Des"]

TYPE_MAP = {
    "homecare": "homecare", "home care": "homecare",
    "hpv": "hpv", "vaksinasi": "hpv", "jagadiri": "hpv",
    "wag": "wag", "whatsapp": "wag", "community": "wag", "sehat duluan": "wag",
    "promo": "promo", "kartini": "promo", "diskon": "promo",
    "standalone": "standalone", "pekerja": "standalone", "imun": "standalone",
    "free consult": "standalone", "pma": "standalone",
}


def _prop(props: dict, *names: str):
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
            return [s["name"] for s in p.get("multi_select", [])]
        if pt == "date":
            d = p.get("date")
            return d if d else None
        if pt == "status":
            s = p.get("status")
            return s["name"] if s else ""
    return ""


def _fmt(date_str: str) -> str:
    try:
        m = int(date_str[5:7]) - 1
        d = int(date_str[8:10])
        return f"{d} {MONTHS_ID[m]}"
    except (IndexError, ValueError):
        return date_str


def _css_type(raw: str) -> str:
    rl = raw.lower()
    for key, val in TYPE_MAP.items():
        if key in rl:
            return val
    return "standalone"


def fetch_marketing_calendar() -> list:
    try:
        pages = query_database(MARKETING_CAL_DB_ID)
    except Exception as e:
        return [{"error": str(e)}]

    events = []
    for page in pages:
        props = page.get("properties", {})
        name = _prop(props, "Name", "Event Name", "Program", "Nama")
        raw_type = _prop(props, "Project", "Type", "Category", "Kategori", "Program Type", "Tipe", "Class") or ""
        date_obj = _prop(props, "Periode", "Date", "Tanggal", "Period", "Start Date")
        status = _prop(props, "Status", "State") or ""

        if isinstance(raw_type, list):
            raw_type = ", ".join(raw_type)

        # If type can't be determined from the Type column, infer from name
        inferred_type = _css_type(raw_type) if raw_type else _css_type(str(name))

        events.append({
            "id": page["id"],
            "name": str(name),
            "type": inferred_type,
            "raw_type": raw_type,
            "date": date_obj,
            "status": status,
            "created_time": page.get("created_time", ""),
        })

    return events


def format_for_dashboard(events: list) -> dict:
    """Convert flat list → CAL_DATA dict for the dashboard JS."""
    cal: dict = {}
    for ev in events:
        if "error" in ev:
            continue
        date = ev.get("date")
        if not date or not isinstance(date, dict):
            continue
        start = date.get("start") or ""
        if not start:
            continue
        try:
            month_key = start[:7]
            day = int(start[8:10])
            week_num = (day - 1) // 7 + 1
            week_label = f"W{week_num}"

            end = date.get("end") or ""
            d_str = (f"{_fmt(start)} – {_fmt(end)}" if end and end != start
                     else _fmt(start))

            cal.setdefault(month_key, []).append({
                "w": week_label,
                "n": ev["name"],
                "t": ev["type"],
                "d": d_str,
            })
        except (ValueError, IndexError):
            continue
    return cal
