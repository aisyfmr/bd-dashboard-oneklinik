"""
Fetches the Marketing Hub / Projects database.
DB ID : 223c88be4d3c8071a72eef4e9ff306c9
Schema: Class (title), Name (select), Category (select),
        Status (status), Periode (rich_text), Branch/Clinics (relation)

Note: Notion's 'Periode' field uses the company's own sequential week numbers
(e.g. "Week 7 | 11 May - 15 May 2026"), NOT ISO week numbers.
We match by parsing the date range inside the Periode string.
"""
import re
from datetime import datetime, timedelta
from .client import query_database

PROJECTS_DB_ID = "223c88be4d3c8071a72eef4e9ff306c9"

MONTH_MAP = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'mei':5,
    'jun':6,'jul':7,'aug':8,'ags':8,'sep':9,
    'oct':10,'okt':10,'nov':11,'dec':12,'des':12,
}


def _rich_text(rt_list: list) -> str:
    return "".join(r.get("plain_text", "") for r in (rt_list or []))


def _prev_week_range() -> tuple[datetime, datetime]:
    today = datetime.now()
    this_monday = today - timedelta(days=today.weekday())
    prev_monday = this_monday - timedelta(days=7)
    prev_friday  = prev_monday + timedelta(days=4)
    return prev_monday.replace(hour=0,minute=0,second=0), prev_friday.replace(hour=23,minute=59,second=59)


def _parse_periode_date(periode: str) -> datetime | None:
    """
    Try to parse a date from strings like:
      'Week 7 | 11 May - 15 May 2026'
      '11 May - 15 May 2026'
    Returns the START date, or None if parsing fails.
    """
    # Find first occurrence of   <day> <month-word> [<year>]
    m = re.search(r'(\d{1,2})\s+([A-Za-z]{3,})\s*[-–]?\s*(\d{1,2})?\s*[A-Za-z]*\s*(\d{4})?', periode)
    if not m:
        return None
    day  = int(m.group(1))
    mon  = MONTH_MAP.get(m.group(2).lower()[:3])
    # Year: look for 4-digit number anywhere in the string
    yr_m = re.search(r'\b(20\d{2})\b', periode)
    year = int(yr_m.group(1)) if yr_m else datetime.now().year
    if not mon:
        return None
    try:
        return datetime(year, mon, day)
    except ValueError:
        return None


ACTIVE_STATUSES = {"new project active", "new project in progress", "active",
                   "on progress", "in progress", "draft"}


def fetch_marketing_projects() -> dict:
    """
    Returns all currently-active projects from the Marketing Hub DB,
    grouped by category. 'Active' is defined by status keyword, not date,
    because the Periode field uses an internal week numbering system.

    Return shape:
    {
        "groups": {
            "Marketing - Promo":   [{"name", "class", "status", "periode"}, ...],
            "Marketing - Program": [...],
        }
    }
    """
    try:
        rows = query_database(PROJECTS_DB_ID)
    except Exception as e:
        return {"groups": {}, "error": str(e)}

    groups: dict = {}

    for row in rows:
        props = row.get("properties", {})

        name_sel  = (props.get("Name", {}).get("select") or {})
        cat_sel   = (props.get("Category", {}).get("select") or {})
        status_s  = (props.get("Status", {}).get("status") or {})
        periode   = _rich_text(props.get("Periode", {}).get("rich_text", []))
        class_txt = _rich_text(props.get("Class", {}).get("title", []))
        status    = status_s.get("name", "")
        category  = cat_sel.get("name", "Uncategorised")

        # Only include active/in-progress projects (skip Done, Finished, Cancelled)
        if status.lower() not in ACTIVE_STATUSES:
            continue

        # Skip empty entries
        if not name_sel.get("name") and not class_txt:
            continue

        groups.setdefault(category, []).append({
            "name":    name_sel.get("name", ""),
            "class":   class_txt,
            "status":  status,
            "periode": periode,
        })

    return {"groups": groups}
