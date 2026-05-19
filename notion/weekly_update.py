"""
Reads the 1:1 Meeting Notes database and parses per-department entries.

DB ID   : 2e7c88be4d3c8014a3edccf7ee3fd496
Schema  : Meeting name (title), Category (multi_select), Date (date)

Content structure (3 levels deep):
  page
    transcription  (has_children=True)
      paragraph    (has_children=True, empty — acts as container)
        heading_3  "Update"
        paragraph  / bulleted_list_item  … highlights …
        heading_3  "Notes"
        paragraph  / bulleted_list_item  … notes …
        heading_3  "Next Task"
        paragraph  / bulleted_list_item  … action items …
    paragraph  (empty)
"""
from .client import get_all_block_children, query_database

MEETING_NOTES_DB_ID = "2e7c88be4d3c8014a3edccf7ee3fd496"

# Map Category multi_select values → canonical dept key
DEPT_MAP = {
    "marketing":            "marketing",
    "finance":              "finance",
    "general affair":       "ga",
    "ga":                   "ga",
    "account manager":      "am",
    "am":                   "am",
    "hr":                   "hr",
    "human resources":      "hr",
    "busdev":               "bd",
    "business dev":         "bd",
    "business development": "bd",
    "bd":                   "bd",
}

# Section headings that map to highlights / notes / actions
HIGHLIGHT_SECTIONS = ("update", "highlight", "progress", "pencapaian", "hasil")
NOTES_SECTIONS     = ("note", "catatan", "keterangan", "context")
ACTION_SECTIONS    = ("next task", "action", "outstanding", "tracker",
                      "follow", "todo", "to do", "tindak lanjut")
ISSUE_SECTIONS     = ("isu", "issue", "kendala", "problem", "blocker", "hambatan")
ISSUE_PREFIXES     = ("⚠", "⛔", "🔴")


def _rich_text(rt_list: list) -> str:
    return "".join(r.get("plain_text", "") for r in (rt_list or []))


def _block_text(block: dict) -> str:
    bt = block.get("type", "")
    if bt in ("paragraph", "heading_1", "heading_2", "heading_3",
              "bulleted_list_item", "numbered_list_item", "to_do",
              "quote", "callout"):
        return _rich_text(block.get(bt, {}).get("rich_text", []))
    return ""


def _collect_content_blocks(block_id: str, _depth: int = 0) -> list:
    """
    Walk the block tree and return all content-bearing blocks,
    transparently skipping 'transcription' wrappers and empty-paragraph containers.
    """
    if _depth > 5:
        return []

    try:
        blocks = get_all_block_children(block_id)
    except Exception:
        return []

    result = []
    for b in blocks:
        bt   = b.get("type", "")
        text = _block_text(b).strip()
        hc   = b.get("has_children", False)

        # Transparent containers — recurse and don't include the wrapper itself
        if bt == "transcription":
            result.extend(_collect_content_blocks(b["id"], _depth + 1))
            continue

        if bt == "paragraph" and not text and hc:
            # Empty paragraph acting as a section container
            result.extend(_collect_content_blocks(b["id"], _depth + 1))
            continue

        # Actual content block — include it
        result.append(b)

        # Recurse into list items / toggles that may have nested bullets
        if hc and bt in ("bulleted_list_item", "numbered_list_item",
                         "to_do", "toggle", "heading_1", "heading_2", "heading_3"):
            result.extend(_collect_content_blocks(b["id"], _depth + 1))

    return result


def _parse_actions(raw_items: list) -> list:
    """Return list of (item, owner, due) tuples from free-text action lines."""
    actions = []
    for item in raw_items:
        parts = [p.strip() for p in item.split("|")]
        if len(parts) >= 3:
            actions.append((parts[0], parts[1], parts[2]))
        elif len(parts) == 2:
            actions.append((parts[0], parts[1], "—"))
        else:
            for sep in (" — ", " - ", " / "):
                if sep in item:
                    p2 = item.split(sep, 2)
                    actions.append((
                        p2[0].strip(),
                        p2[1].strip() if len(p2) > 1 else "—",
                        p2[2].strip() if len(p2) > 2 else "—",
                    ))
                    break
            else:
                actions.append((item, "—", "—"))
    return actions


def _parse_page_content(page_id: str) -> dict:
    """Fetch a meeting-notes page and extract highlights / issues / actions."""
    blocks = _collect_content_blocks(page_id)

    highlights  = []
    issues      = []
    action_raw  = []
    current_sec = None   # "highlight" | "note" | "action" | None

    for b in blocks:
        bt   = b.get("type", "")
        text = _block_text(b).strip()

        if not text:
            continue

        # Heading → update current section
        if bt in ("heading_1", "heading_2", "heading_3"):
            tl = text.lower()
            if any(kw in tl for kw in HIGHLIGHT_SECTIONS):
                current_sec = "highlight"
            elif any(kw in tl for kw in NOTES_SECTIONS):
                current_sec = "note"
            elif any(kw in tl for kw in ACTION_SECTIONS):
                current_sec = "action"
            elif any(kw in tl for kw in ISSUE_SECTIONS):
                current_sec = "issue"
            else:
                current_sec = None
            continue

        # Skip template placeholder text
        if text.lower().startswith("add any") or text.lower().startswith("add next"):
            continue

        # Route block to correct bucket
        tl = text.lower()
        is_issue_prefix = any(tl.startswith(p) for p in ISSUE_PREFIXES)

        # Also treat "Isu: ..." style colon-labels as issues
        label_part = text.split(": ", 1)[0].lower() if ": " in text else ""
        is_issue_label = any(kw in label_part for kw in ISSUE_SECTIONS)

        # Detect clinic/group headers: bulleted items that have nested children
        # (e.g. "• Pasar Baru" with sub-bullets for that clinic's updates)
        is_group_header = (
            bt in ("bulleted_list_item", "numbered_list_item")
            and b.get("has_children", False)
            and current_sec in ("highlight", "note", None)
            and not is_issue_label
        )

        if current_sec == "action":
            action_raw.append(text)
        elif current_sec == "issue" or is_issue_prefix or is_issue_label:
            issues.append(text.lstrip("⚠⛔🔴").strip())
        elif is_group_header:
            highlights.append(("__group__", text))
        elif current_sec in ("highlight", "note", None):
            if bt in ("bulleted_list_item", "numbered_list_item"):
                # Plain nested bullet — indent under its parent group
                highlights.append(("•", text))
            elif ": " in text:
                label, body = text.split(": ", 1)
                highlights.append((label.strip(), body.strip()))
            else:
                highlights.append(("Update", text))

    return {
        "highlights": highlights,
        "issues":     issues,
        "actions":    _parse_actions(action_raw),
    }


def fetch_all_dept_updates() -> dict:
    """
    Query the 1:1 Meeting Notes DB, pick the most recent entry per dept,
    and return parsed highlights / issues / actions keyed by canonical dept name.
    """
    result = {k: {"highlights": [], "issues": [], "actions": []}
              for k in ("marketing", "finance", "ga", "am", "hr", "bd")}

    try:
        rows = query_database(
            MEETING_NOTES_DB_ID,
            sorts=[{"property": "Date", "direction": "descending"}],
        )
    except Exception as e:
        result["_error"] = str(e)
        return result

    filled = set()

    for row in rows:
        props      = row.get("properties", {})
        categories = [c["name"] for c in props.get("Category", {}).get("multi_select", [])]

        for cat in categories:
            canonical = None
            for kw, key in DEPT_MAP.items():
                if kw in cat.lower():
                    canonical = key
                    break
            if canonical and canonical not in filled:
                filled.add(canonical)
                result[canonical] = _parse_page_content(row["id"])

        if len(filled) == 6:
            break

    return result
