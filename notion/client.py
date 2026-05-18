import os
import requests

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers():
    token = os.environ.get("NOTION_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def get_page(page_id: str) -> dict:
    resp = requests.get(f"{NOTION_API}/pages/{page_id}", headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_block_children(block_id: str, cursor: str = None) -> dict:
    params = {"page_size": 100}
    if cursor:
        params["start_cursor"] = cursor
    resp = requests.get(
        f"{NOTION_API}/blocks/{block_id}/children",
        headers=_headers(), params=params, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_all_block_children(block_id: str) -> list:
    results, cursor = [], None
    while True:
        data = get_block_children(block_id, cursor)
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results


def query_database(database_id: str, filter_obj: dict = None, sorts: list = None) -> list:
    results, cursor = [], None
    while True:
        body = {"page_size": 100}
        if filter_obj:
            body["filter"] = filter_obj
        if sorts:
            body["sorts"] = sorts
        if cursor:
            body["start_cursor"] = cursor
        resp = requests.post(
            f"{NOTION_API}/databases/{database_id}/query",
            headers=_headers(), json=body, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results


def append_blocks(block_id: str, children: list) -> dict:
    resp = requests.patch(
        f"{NOTION_API}/blocks/{block_id}/children",
        headers=_headers(), json={"children": children}, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def find_heading_block(block_id: str, heading_text: str) -> str | None:
    """Return the block ID of the first heading block whose plain text matches heading_text."""
    for block in get_all_block_children(block_id):
        btype = block.get("type", "")
        if btype in ("heading_1", "heading_2", "heading_3"):
            texts = block.get(btype, {}).get("rich_text", [])
            plain = "".join(t.get("plain_text", "") for t in texts)
            if heading_text.lower() in plain.lower():
                return block["id"]
    return None


def append_pdf_link_to_page(page_id: str, section_heading: str, filename: str, week_label: str, gen_date: str) -> bool:
    """Append a styled entry under section_heading on page_id.
    Returns True on success, False if heading not found (falls back to page root)."""
    target_id = find_heading_block(page_id, section_heading) or page_id

    children = [
        {
            "object": "block",
            "type": "divider",
            "divider": {},
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"📄 {filename}"}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": f"  |  {week_label}  |  Generated: {gen_date}"}},
                ]
            },
        },
    ]
    try:
        append_blocks(target_id, children)
        return True
    except Exception:
        return False


def create_page(parent_id: str, title: str, children: list = None) -> dict:
    body = {
        "parent": {"page_id": parent_id},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
    }
    if children:
        body["children"] = children
    resp = requests.post(
        f"{NOTION_API}/pages", headers=_headers(), json=body, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
