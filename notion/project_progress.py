"""Reads the Project Progress Notion page."""
from .client import get_all_block_children

PROJECT_PROGRESS_PAGE_ID = "33ac88be4d3c8050a4afd516bc034799"


def _rich_text(rt_list: list) -> str:
    return "".join(r.get("plain_text", "") for r in rt_list)


def _parse_block(block: dict) -> dict:
    bt = block.get("type", "")
    result = {"type": bt, "id": block["id"]}
    if bt in ("paragraph", "heading_1", "heading_2", "heading_3",
              "bulleted_list_item", "numbered_list_item", "to_do", "quote"):
        content = block.get(bt, {})
        result["text"] = _rich_text(content.get("rich_text", []))
        if bt == "to_do":
            result["checked"] = content.get("checked", False)
    elif bt == "child_page":
        result["title"] = block.get("child_page", {}).get("title", "")
        result["child_id"] = block["id"]
    return result


def fetch_project_progress() -> dict:
    try:
        raw = get_all_block_children(PROJECT_PROGRESS_PAGE_ID)
        parsed = [_parse_block(b) for b in raw]

        # Group child_pages as project sub-pages
        sub_pages = [b for b in parsed if b["type"] == "child_page"]
        text_blocks = [b for b in parsed if b.get("text", "").strip()]

        return {
            "page_id": PROJECT_PROGRESS_PAGE_ID,
            "sub_pages": sub_pages,
            "text_blocks": text_blocks,
            "raw_count": len(raw),
        }
    except Exception as e:
        return {"error": str(e), "sub_pages": [], "text_blocks": []}
