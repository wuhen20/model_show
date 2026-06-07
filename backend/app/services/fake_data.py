"""Fake data service for FAKE_MODE — loads config JSON and computes derived values.

When FAKE_MODE is enabled, this module is loaded once at startup. It reads
`data/fake_data_config.json` and computes all derived values (totals,
percentages, summaries) to guarantee self-consistency.

Usage from route handlers::

    if settings.fake_mode:
        return {"code": 0, "data": fake_data.get_fake_response("/stats")}
"""

import json
import os
from copy import deepcopy
from typing import Any

from app.core.config import settings

_config: dict[str, Any] | None = None


def _load_config() -> dict[str, Any]:
    """Load and parse the fake data config file. Called once at startup."""
    global _config
    config_path = settings.fake_data_config_path
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.getcwd(), config_path)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _config = json.load(f)
        print(f"[fake_data] Loaded config from {config_path}")
    except Exception as e:
        print(f"[fake_data] Failed to load config from {config_path}: {e}")
        _config = {}
    _compute_derived()
    return _config


def _compute_derived():
    """Ensure self-consistency by computing all derived values from base data."""
    if not _config:
        return

    # 1. /stats: unstructured_count = total_count - structured_count
    stats = _config.get("/stats", {})
    if stats:
        stats["unstructured_count"] = stats.get("total_count", 0) - stats.get("structured_count", 0)

    # 2. /folder/asset-stats: compute total_count, total_size, value, extension_summary
    asset_stats = _config.get("/folder/asset-stats", {})
    categories = asset_stats.get("categories", [])
    if categories:
        total_count = sum(c.get("count", 0) for c in categories)
        total_size = sum(c.get("size", 0) for c in categories)
        for c in categories:
            c["value"] = round(c["count"] / total_count * 100, 1) if total_count else 0
        asset_stats["total_count"] = total_count
        asset_stats["total_size"] = total_size
        # Extension summary (aggregate across all categories)
        ext_map: dict[str, dict] = {}
        for cat in categories:
            for ext_item in cat.get("extensions", []):
                ext = ext_item["ext"]
                if ext not in ext_map:
                    ext_map[ext] = {"ext": ext, "count": 0, "value": 0}
                ext_map[ext]["count"] += ext_item.get("count", 0)
        all_ext_total = sum(e["count"] for e in ext_map.values()) or 1
        for e in ext_map.values():
            e["value"] = round(e["count"] / all_ext_total * 100, 1)
        asset_stats["extension_summary"] = list(ext_map.values())

    # 3. /folder/source-distribution: compute value (percentage) from count
    source_dist = _config.get("/folder/source-distribution", [])
    if source_dist:
        total_src = sum(item.get("count", 0) for item in source_dist) or 1
        for item in source_dist:
            item["value"] = round(item["count"] / total_src * 100, 1)

    # 4. /folder/trend: compute summary from series data
    trend = _config.get("/folder/trend", {})
    if trend and "series" in trend:
        summary = trend.setdefault("summary", {})
        for s in trend["series"]:
            data = s.get("data", [])
            if not data:
                continue
            if s["name"] == "新增知识":
                new_count = data[-1]
                prev = data[-2] if len(data) > 1 else new_count
                summary["new_count"] = new_count
                summary["new_change_pct"] = round((new_count - prev) / prev * 100, 1) if prev else 0
            elif s["name"] == "更新知识":
                updated_count = data[-1]
                prev = data[-2] if len(data) > 1 else updated_count
                summary["updated_count"] = updated_count
                summary["updated_change_pct"] = round((updated_count - prev) / prev * 100, 1) if prev else 0

    # 5. /folder/bases: compute total
    bases = _config.get("/folder/bases", {})
    if "bases" in bases:
        bases["total"] = len(bases["bases"])

    # 6. /folder/list: ensure total field exists
    list_data = _config.get("/folder/list", {})
    if "items" in list_data and "total" not in list_data:
        list_data["total"] = len(list_data["items"])

    # 7. Per-KB files: ensure total field in each KB's file list
    per_kb = _config.get("/folder/bases/{name}", {}).get("files", {})
    for kb_name, kb_files in per_kb.items():
        if "items" in kb_files and "total" not in kb_files:
            kb_files["total"] = len(kb_files["items"])


def get_fake_response(endpoint: str, **kwargs) -> dict[str, Any]:
    """Return fake data for a given endpoint key.

    Args:
        endpoint: The JSON config key, e.g. "/stats", "/folder/asset-stats".
        **kwargs: Optional overrides:
            - kb_name: for /folder/bases/{name}/files and /tags
            - kb_id: for /bases/{id} endpoints
            - item_id: for /detail/{id}
            - page, page_size: for paginated list endpoints

    Returns:
        The data payload (will be wrapped in {"code": 0, "data": ...} by the router).
    """
    global _config
    if _config is None:
        _load_config()
    if not _config:
        return {}

    # Handle dynamic endpoints that don't have a direct config key
    # These are resolved from their parent config sections
    if endpoint == "/folder/bases/{name}/files" and "kb_name" in kwargs:
        kb_name = kwargs["kb_name"]
        per_kb = _config.get("/folder/bases/{name}", {}).get("files", {})
        if kb_name in per_kb:
            result = deepcopy(per_kb[kb_name])
        elif per_kb:
            result = deepcopy(next(iter(per_kb.values())))
        else:
            return {"items": [], "total": 0}

    elif endpoint == "/folder/bases/{name}/tags" and "kb_name" in kwargs:
        kb_name = kwargs["kb_name"]
        per_kb = _config.get("/folder/bases/{name}", {}).get("tags", {})
        if kb_name in per_kb:
            result = deepcopy(per_kb[kb_name])
        elif per_kb:
            result = deepcopy(next(iter(per_kb.values())))
        else:
            return []

    elif endpoint == "/detail/{id}":
        item_id = kwargs.get("item_id")
        # Try to find the item in /folder/list items by id
        items = _config.get("/folder/list", {}).get("items", [])
        result = deepcopy(_config.get("/detail/{id}", {}))
        for item in items:
            if item.get("id") == item_id:
                result.update(item)
                break

    elif endpoint == "/bases/{id}":
        kb_id = kwargs.get("kb_id")
        kb_data = _config.get("/bases/{id}", {}).get("kb", {})
        if kb_id in kb_data:
            result = deepcopy(kb_data[kb_id])
        elif kb_data:
            result = deepcopy(next(iter(kb_data.values())))
        else:
            return {}

    elif endpoint == "/bases/{id}/documents":
        kb_id = kwargs.get("kb_id")
        doc_data = _config.get("/bases/{id}", {}).get("documents", {})
        if kb_id in doc_data:
            result = deepcopy(doc_data[kb_id])
        elif doc_data:
            result = deepcopy(next(iter(doc_data.values())))
        else:
            return {"items": [], "total": 0, "page": 1, "page_size": 20}

    elif endpoint == "/bases/{id}/tags":
        kb_id = kwargs.get("kb_id")
        tags_data = _config.get("/bases/{id}", {}).get("tags_tree", {})
        if kb_id in tags_data:
            result = deepcopy(tags_data[kb_id])
        elif tags_data:
            result = deepcopy(next(iter(tags_data.values())))
        else:
            return []

    elif endpoint == "/documents/{id}/chunks":
        result = deepcopy(_config.get("/bases/{id}", {}).get("chunks", []))

    else:
        # Direct endpoint match for simple keys
        data = _config.get(endpoint)
        if data is None:
            return {}
        result = deepcopy(data)

    # Support pagination and filtering for list endpoints
    if endpoint in ("/folder/list", "/folder/bases/{name}/files", "/bases/{id}/documents"):
        if isinstance(result, dict) and "items" in result:
            all_items = list(result["items"])

            # Filter by category_id (match category_name or parent_category)
            category_id = kwargs.get("category_id")
            if category_id:
                all_items = [
                    i for i in all_items
                    if i.get("category_name") == category_id
                    or i.get("parent_category") == category_id
                ]

            # Filter by keyword
            keyword = kwargs.get("keyword")
            if keyword:
                kw = keyword.lower()
                all_items = [
                    i for i in all_items
                    if kw in i.get("title", "").lower()
                    or kw in i.get("description", "").lower()
                ]

            # Tab-based sorting / filtering (mirrors folder_kb_service logic)
            tab = kwargs.get("tab", "latest")
            if tab == "popular":
                all_items = [i for i in all_items if i.get("score", 0) >= 4]
                all_items.sort(key=lambda x: x.get("score", 0), reverse=True)
            elif tab == "valuable":
                all_items = [i for i in all_items if i.get("score", 0) >= 5]
            elif tab == "pending":
                all_items = [i for i in all_items if i.get("status") in ("待审核", "PENDING")]
            else:
                # latest: sort by update_time descending
                all_items.sort(key=lambda x: x.get("update_time", ""), reverse=True)

            total = result.get("total", len(all_items))
            if category_id or keyword:
                total = len(all_items)
            elif tab == "latest":
                total = result.get("latest_total", total)
            elif tab == "popular":
                total = result.get("popular_total", result.get("latest_total", len(all_items)))
            elif tab == "valuable":
                total = result.get("valuable_total", len(all_items))
            elif tab == "pending":
                total = len(all_items)
            page = kwargs.get("page", 1)
            page_size = kwargs.get("page_size", 20)
            start = (page - 1) * page_size
            result["items"] = all_items[start : start + page_size]
            result["total"] = total
            result["page"] = page
            result["page_size"] = page_size

    return result


# Auto-load on import when fake_mode is enabled
if settings.fake_mode:
    _load_config()
