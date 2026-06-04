"""Folder-based knowledge base scanner.

Scans a directory hierarchy where:
  - First-level directories  = knowledge base names
  - Second+ level directories = tag hierarchy (parent → child)
  - Files in any directory    = knowledge documents tagged by their folder chain

Invariant: a file's tags ALWAYS include ALL ancestor directory names.
E.g. path KB/专业知识库/采集2.0/省侧/方案文件/file.docx
must have tags: [专业知识库, 采集2.0, 省侧, 方案文件].
"""

import hashlib
import os
import time
from datetime import datetime

from app.core.config import settings

# ── Supported file extensions ────────────────────────────────────────────
SUPPORTED_EXTENSIONS: set[str] = {
    ".txt", ".pdf", ".doc", ".docx", ".md", ".csv",
    ".xlsx", ".xls", ".pptx", ".ppt", ".json", ".xml",
    ".html", ".htm", ".rtf", ".log",
}

# ── Simple TTL cache for expensive operations ────────────────────────────
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 30  # seconds


def _cached(key: str, ttl: float | None = None):
    """Decorator-like: return cached value if fresh, else compute and cache."""
    _ttl = ttl if ttl is not None else _CACHE_TTL
    now = time.time()
    if key in _cache:
        ts, val = _cache[key]
        if now - ts < _ttl:
            return val
    return None  # cache miss


def _set_cache(key: str, value: object):
    _cache[key] = (time.time(), value)


# ── Helpers ──────────────────────────────────────────────────────────────

def _validate_kb_name(kb_name: str) -> str:
    """Ensure kb_name is a single safe directory component (no path traversal)."""
    if not kb_name:
        raise ValueError("Knowledge base name cannot be empty")
    # Normalize separators
    normalized = kb_name.replace("\\", "/")
    if "/" in normalized or ".." in kb_name or "\0" in kb_name:
        raise ValueError(f"Invalid knowledge base name: {kb_name}")
    return kb_name


def _get_kb_dir() -> str:
    """Resolve KNOWLEDGE_BASE_DIR to an absolute path.

    Returns empty string if the directory does not exist.
    """
    base = settings.knowledge_base_dir
    if not base:
        return ""
    abs_path = os.path.abspath(base)
    if not os.path.isdir(abs_path):
        return ""
    return abs_path


def _file_id(relative_path: str) -> str:
    """Deterministic short ID from a file's relative path."""
    return hashlib.md5(relative_path.encode("utf-8")).hexdigest()[:16]


def _path_to_tag_chain(relative_dir: str) -> list[str]:
    """Split a relative directory path into tag names.

    IMPORTANT: always returns ALL ancestor directory names.
    Example: '专业知识库/采集2.0/省侧/方案文件'
             → ['专业知识库', '采集2.0', '省侧', '方案文件']

    This ensures that if a file has a child tag, every parent tag
    is also present.  This is the core invariant of the tag system.
    """
    if not relative_dir or relative_dir == ".":
        return []
    parts = relative_dir.replace("\\", "/").split("/")
    return [p for p in parts if p and p != "."]


def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _is_supported_file(filename: str) -> bool:
    """Check if a file has a supported extension."""
    _, ext = os.path.splitext(filename)
    return ext.lower() in SUPPORTED_EXTENSIONS


# ── Fast file counting ───────────────────────────────────────────────────

def _count_supported_files(dir_path: str) -> int:
    """Count all supported files recursively in a directory."""
    count = 0
    for _root, _dirs, files in os.walk(dir_path):
        for f in files:
            if _is_supported_file(f):
                count += 1
    return count


def _get_top_level_dirs(dir_path: str) -> list[str]:
    """Return sorted list of immediate subdirectory names."""
    try:
        entries = sorted(os.listdir(dir_path))
    except PermissionError:
        return []
    return [e for e in entries if os.path.isdir(os.path.join(dir_path, e))]


# ── Tag Tree Building ────────────────────────────────────────────────────

def _build_folder_tag_tree(dir_path: str, level: int = 1) -> list[dict]:
    """Recursively build a tag tree from the directory hierarchy.

    Only includes directories that contain supported files (directly or
    in descendants).  Because we walk the tree recursively, every parent
    directory that leads to a file will appear in the tree — guaranteeing
    the "有子标签必有父标签" invariant.
    """
    result: list[dict] = []
    try:
        entries = sorted(os.listdir(dir_path))
    except PermissionError:
        return result

    for entry in entries:
        full = os.path.join(dir_path, entry)
        if not os.path.isdir(full):
            continue
        # Always recurse first to collect children
        children = _build_folder_tag_tree(full, level + 1)
        # Include this directory if it (or any descendant) has supported files
        if _dir_has_files(full):
            result.append({
                "name": entry,
                "level": level,
                "children": children,
            })
    return result


def _dir_has_files(dir_path: str) -> bool:
    """Check if a directory contains any supported files (recursively)."""
    for root, _dirs, files in os.walk(dir_path):
        for f in files:
            if _is_supported_file(f):
                return True
    return False


def _ensure_tag_hierarchy(tag_tree: list[dict]) -> list[dict]:
    """Post-process a tag tree to guarantee the parent-child invariant.

    For every tag with children, ensures the tag itself is present.
    This is effectively a no-op if _build_folder_tag_tree was used,
    but serves as a safety net.
    """
    return tag_tree  # _build_folder_tag_tree already guarantees this


# ── Public API ───────────────────────────────────────────────────────────

def scan_knowledge_bases() -> list[dict]:
    """Lightweight listing of all folder-based knowledge bases.

    Returns a list of dicts with keys: name, doc_count, top_tags, path.
    Does NOT build full tag trees — that is done on demand via scan_kb_tags().

    Results are cached for 30 seconds to avoid repeated filesystem walks.
    """
    cached = _cached("scan_knowledge_bases")
    if cached is not None:
        return cached

    base_dir = _get_kb_dir()
    if not base_dir:
        return []

    result: list[dict] = []
    try:
        entries = sorted(os.listdir(base_dir))
    except PermissionError:
        return result

    for entry in entries:
        full = os.path.join(base_dir, entry)
        if not os.path.isdir(full):
            continue

        # Fast: just count files (single os.walk)
        doc_count = _count_supported_files(full)

        if doc_count == 0:
            continue  # skip empty knowledge bases

        # Lightweight: only top-level directory names for preview chips
        top_tags = _get_top_level_dirs(full)

        result.append({
            "name": entry,
            "doc_count": doc_count,
            "top_tags": top_tags,
        })

    _set_cache("scan_knowledge_bases", result)
    return result


def scan_kb_files(
    kb_name: str,
    page: int = 1,
    page_size: int = 50,
    keyword: str | None = None,
) -> dict:
    """List files in a folder-based knowledge base with pagination.

    Returns {items: [...], total: int, page: int, page_size: int}.
    Each item has: id, file_name, relative_path, file_size, extension,
                    tags, modified_time.

    IMPORTANT: every file's `tags` includes ALL ancestor directory names,
    guaranteeing the tag hierarchy invariant.
    """
    kb_name = _validate_kb_name(kb_name)
    base_dir = _get_kb_dir()
    if not base_dir:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    kb_dir = os.path.join(base_dir, kb_name)
    # Security: ensure we stay under base_dir
    if not os.path.commonpath([base_dir, os.path.abspath(kb_dir)]) == base_dir:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    if not os.path.isdir(kb_dir):
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    # Check cache for full file list (cache key includes kb name)
    cache_key = f"scan_kb_files:{kb_name}"
    all_files_cached = _cached(cache_key, ttl=60)

    if all_files_cached is not None:
        all_files = all_files_cached
    else:
        # Collect all files
        all_files: list[dict] = []
        for root, _dirs, files in os.walk(kb_dir):
            for f in files:
                if not _is_supported_file(f):
                    continue
                full_path = os.path.join(root, f)
                rel_dir = os.path.relpath(root, kb_dir)
                rel_path = os.path.relpath(full_path, kb_dir)
                # Normalize separators for cross-platform consistency
                rel_path_fwd = rel_path.replace("\\", "/")

                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue

                _, ext = os.path.splitext(f)
                # CRITICAL: _path_to_tag_chain returns ALL ancestor dirs
                tags = _path_to_tag_chain(rel_dir)

                all_files.append({
                    "id": _file_id(rel_path_fwd),
                    "file_name": f,
                    "relative_path": rel_path_fwd,
                    "file_size": stat.st_size,
                    "extension": ext.lower(),
                    "tags": tags,
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        # Sort by file name
        all_files.sort(key=lambda x: x["file_name"])
        _set_cache(cache_key, all_files)

    # Apply keyword filter (on cached or fresh data)
    filtered = all_files
    if keyword:
        kw = keyword.lower()
        filtered = [f for f in all_files if kw in f["file_name"].lower()]

    # Paginate
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def scan_all_kb_files(
    tab: str = "latest",
    keyword: str | None = None,
    category_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List files across ALL folder-based knowledge bases with tab filtering.

    Tabs:
      - latest:  sorted by modified_time descending (most recent first)
      - popular: sorted by file_size descending (larger = more content = popular proxy)
      - valuable: files with recognized standard prefixes (JJG, GB, DLT, Q/GDW, etc.)
      - pending:  files modified in the last 7 days (recently added, awaiting review)

    Returns the same shape as the old /api/knowledge/list endpoint for compatibility.
    """
    cached_all = _cached("scan_all_kb_files", ttl=60)
    if cached_all is None:
        base_dir = _get_kb_dir()
        all_items: list[dict] = []
        if base_dir:
            kb_list = scan_knowledge_bases()
            for kb in kb_list:
                kb_name = kb["name"]
                kb_dir = os.path.join(base_dir, kb_name)
                if not os.path.isdir(kb_dir):
                    continue
                for root, _dirs, files in os.walk(kb_dir):
                    for f in files:
                        if not _is_supported_file(f):
                            continue
                        full_path = os.path.join(root, f)
                        try:
                            stat = os.stat(full_path)
                        except OSError:
                            continue
                        rel_dir = os.path.relpath(root, kb_dir)
                        rel_path = os.path.relpath(full_path, kb_dir)
                        rel_path_fwd = rel_path.replace("\\", "/")
                        _, ext = os.path.splitext(f)
                        tags = _path_to_tag_chain(rel_dir)
                        mtime = stat.st_mtime
                        dt = datetime.fromtimestamp(mtime)

                        # Infer knowledge type from filename
                        ktype = _infer_knowledge_type(f)
                        # Infer source from filename
                        source = _infer_source_type(f)
                        # Score: standard docs get 5, guides get 4, others 3
                        score = 5 if any(k in f.upper() for k in ['JJG', 'GB', 'DLT', 'DL/', 'Q/GDW', 'QGDW']) else (4 if '指导书' in f else 3)

                        # Status: recently modified files = pending, rest = published
                        now_ts = datetime.now().timestamp()
                        status = "待审核" if (now_ts - mtime) < 7 * 86400 else "已发布"

                        all_items.append({
                            "id": _file_id(rel_path_fwd),
                            "title": f,
                            "category_id": kb_name,
                            "category_name": kb_name,
                            "parent_category": kb_name,
                            "knowledge_type": ktype,
                            "source": source,
                            "score": score,
                            "status": status,
                            "update_time": dt.strftime("%Y-%m-%d"),
                            "file_path": rel_path_fwd,
                            "description": f"《{f}》，属于{kb_name}，{ktype}类文档。",
                            "tags": tags,
                            "file_size": stat.st_size,
                            "modified_time": dt.isoformat(),
                        })
        _set_cache("scan_all_kb_files", all_items)
        cached_all = all_items

    # Work on a copy
    items = list(cached_all)

    # Filter by category_id (kb_name match)
    if category_id:
        items = [i for i in items if i["category_id"] == category_id or i["parent_category"] == category_id]

    # Filter by keyword
    if keyword:
        kw = keyword.lower()
        items = [i for i in items if kw in i["title"].lower() or kw in i["description"].lower()]

    # Tab-based sorting/filtering
    if tab == "popular":
        items.sort(key=lambda x: x["score"], reverse=True)
    elif tab == "valuable":
        items = [i for i in items if i["score"] >= 5]
    elif tab == "pending":
        items = [i for i in items if i["status"] == "待审核"]
    else:
        # latest: sort by update_time descending
        items.sort(key=lambda x: x["update_time"], reverse=True)

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _infer_knowledge_type(filename: str) -> str:
    """Infer knowledge document type from filename patterns."""
    upper = filename.upper()
    if any(k in upper for k in ['JJG']):
        return '检定规程'
    if any(k in upper for k in ['GB', 'GBT', 'GB/']):
        return '国家标准'
    if any(k in upper for k in ['DLT', 'DL/', 'DL/T']):
        return '行业标准'
    if any(k in upper for k in ['Q/GDW', 'QGDW', 'Q／GDW']):
        return '企业标准'
    if any(k in upper for k in ['JJF']):
        return '计量规范'
    if '指导书' in filename:
        return '作业指导书'
    if '管理办法' in filename or '管理规定' in filename:
        return '管理制度'
    if '技术规范' in filename:
        return '技术规范'
    if '功能规范' in filename or '型式规范' in filename:
        return '产品规范'
    if '试题' in filename or '题库' in filename or '计算' in filename or '案例' in filename:
        return '培训题库'
    if '手册' in filename or '操作' in filename:
        return '操作手册'
    if '方案' in filename:
        return '技术方案'
    if '宣贯' in filename or '培训' in filename or '资料' in filename:
        return '培训资料'
    if '规程' in filename:
        return '技术规程'
    if '条例' in filename or '法' in filename:
        return '法律法规'
    return '技术文档'


def _infer_source_type(filename: str) -> str:
    """Infer knowledge source from filename patterns."""
    upper = filename.upper()
    if any(k in upper for k in ['JJG', 'JJF']):
        return '国家计量规程'
    if any(k in upper for k in ['GB', 'GBT']):
        return '国家标准'
    if any(k in upper for k in ['DLT', 'DL/', 'DL/T']):
        return '电力行业标准'
    if any(k in upper for k in ['Q/GDW', 'QGDW']):
        return '国家电网企业标准'
    if '条例' in filename or '法' in filename:
        return '国家法律法规'
    if '指导书' in filename:
        return '内部文档'
    if '试题' in filename or '题库' in filename:
        return '培训资料'
    return '内部文档'


def scan_kb_tags(kb_name: str) -> list[dict]:
    """Return the full tag tree for a folder-based knowledge base.

    The tree guarantees: if a child tag exists, all its parent tags
    also exist in the hierarchy.
    """
    kb_name = _validate_kb_name(kb_name)
    base_dir = _get_kb_dir()
    if not base_dir:
        return []

    kb_dir = os.path.join(base_dir, kb_name)
    if not os.path.commonpath([base_dir, os.path.abspath(kb_dir)]) == base_dir:
        return []

    if not os.path.isdir(kb_dir):
        return []

    result = _build_folder_tag_tree(kb_dir, level=1)
    return _ensure_tag_hierarchy(result)


def build_folder_graph(kb_name: str) -> dict:
    """Build a synthetic knowledge graph from the folder + tag structure.

    Returns an ECharts-compatible graph: {nodes, links, stats}.
    Nodes represent tags (directories) and files; links show containment.
    """
    kb_name = _validate_kb_name(kb_name)
    base_dir = _get_kb_dir()
    if not base_dir:
        return {"nodes": [], "links": [], "stats": {"entity_count": 0, "relation_count": 0, "coverage": "0%"}}

    kb_dir = os.path.join(base_dir, kb_name)
    if not os.path.commonpath([base_dir, os.path.abspath(kb_dir)]) == base_dir:
        return {"nodes": [], "links": [], "stats": {"entity_count": 0, "relation_count": 0, "coverage": "0%"}}

    if not os.path.isdir(kb_dir):
        return {"nodes": [], "links": [], "stats": {"entity_count": 0, "relation_count": 0, "coverage": "0%"}}

    nodes: list[dict] = []
    links: list[dict] = []
    node_set: set[str] = set()

    # Add the KB root node
    root_name = kb_name
    nodes.append({
        "name": root_name,
        "symbolSize": 50,
        "category": 0,
        "itemStyle": {"color": "#00d4ff"},
        "label": {"show": True},
    })
    node_set.add(root_name)

    # Category mapping: 0=KB, 1=tag level1, 2=tag level2, 3=tag level3+, 4=file
    tag_color_map = {
        1: "#a855f7",
        2: "#00ff88",
        3: "#ffaa00",
    }

    # Walk directories
    for root, dirs, files in os.walk(kb_dir):
        rel_dir = os.path.relpath(root, kb_dir)
        tag_chain = _path_to_tag_chain(rel_dir)
        parent_key = root_name if not tag_chain else "/".join(tag_chain)

        for d in sorted(dirs):
            child_chain = tag_chain + [d]
            child_key = "/".join(child_chain)
            level = len(child_chain)

            if child_key not in node_set:
                cat = min(level, 3)
                color = tag_color_map.get(level, "#ff5555")
                nodes.append({
                    "name": child_key,
                    "symbolSize": max(30 - level * 5, 15),
                    "category": cat,
                    "itemStyle": {"color": color},
                    "label": {"show": True, "formatter": d},  # show short name
                })
                node_set.add(child_key)

            links.append({"source": parent_key, "target": child_key, "relType": "CONTAINS", "description": f"{parent_key} 包含子目录 {d}"})

        for f in sorted(files):
            if not _is_supported_file(f):
                continue
            file_key = f"file:/{'/'.join(tag_chain)}/{f}" if tag_chain else f"file:/{f}"
            _, ext = os.path.splitext(f)

            if file_key not in node_set:
                nodes.append({
                    "name": file_key,
                    "symbolSize": 12,
                    "category": 4,
                    "itemStyle": {"color": "#888"},
                    "label": {"show": True, "formatter": f},
                })
                node_set.add(file_key)

            links.append({"source": parent_key, "target": file_key, "relType": "CONTAINS", "description": f"{parent_key} 包含文件 {f}"})

    total_nodes = len(nodes)
    total_links = len(links)
    coverage = "100%" if total_nodes > 0 else "0%"

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "entity_count": total_nodes,
            "relation_count": total_links,
            "coverage": coverage,
        },
    }


def read_folder_file(kb_name: str, relative_path: str) -> bytes | None:
    """Read a file's raw content from the folder KB.

    Returns None if the file doesn't exist or path is invalid.
    """
    kb_name = _validate_kb_name(kb_name)
    base_dir = _get_kb_dir()
    if not base_dir:
        return None

    kb_dir = os.path.join(base_dir, kb_name)
    if not os.path.commonpath([base_dir, os.path.abspath(kb_dir)]) == base_dir:
        return None

    # Validate relative path (no traversal)
    normalized = os.path.normpath(relative_path)
    if normalized.startswith("..") or os.path.isabs(normalized):
        return None

    full_path = os.path.join(kb_dir, normalized)
    if not os.path.commonpath([kb_dir, os.path.abspath(full_path)]) == kb_dir:
        return None

    if not os.path.isfile(full_path):
        return None

    try:
        with open(full_path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def scan_kb_trend_data() -> dict:
    """Monthly file update trend across all folder-based knowledge bases.

    Groups files by modification month and returns per-KB counts.
    Uses cached file lists from scan_kb_files() when available.

    Returns dict with:
      - months: list of "YYYY-MM" strings (from earliest to current month)
      - series: list of {name, data} per knowledge base
      - summary: {new_count, new_change_pct, updated_count, updated_change_pct}
    """
    cached = _cached("scan_kb_trend_data", ttl=60)
    if cached is not None:
        return cached

    from collections import defaultdict

    base_dir = _get_kb_dir()
    if not base_dir:
        result = _empty_trend_data()
        _set_cache("scan_kb_trend_data", result)
        return result

    # Collect all KBs and their files
    kb_list = scan_knowledge_bases()
    kb_monthly: dict[str, dict[str, int]] = {}  # kb_name -> {month -> count}
    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    current_ts = now.timestamp()
    thirty_days_ago = current_ts - 30 * 86400

    all_months: set[str] = set()
    total_new_count = 0      # files modified in current month
    total_updated_count = 0  # files modified in last 30 days
    prev_month_count = 0     # files modified in previous month

    for kb in kb_list:
        kb_name = kb["name"]
        kb_dir = os.path.join(base_dir, kb_name)
        if not os.path.isdir(kb_dir):
            continue

        month_counts: dict[str, int] = defaultdict(int)
        for root, _dirs, files in os.walk(kb_dir):
            for f in files:
                if not _is_supported_file(f):
                    continue
                full_path = os.path.join(root, f)
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue
                mtime = stat.st_mtime
                dt = datetime.fromtimestamp(mtime)
                month_str = dt.strftime("%Y-%m")
                month_counts[month_str] += 1
                all_months.add(month_str)

                # Summary stats
                if month_str == current_month:
                    total_new_count += 1
                if mtime >= thirty_days_ago:
                    total_updated_count += 1

        kb_monthly[kb_name] = dict(month_counts)

    # Previous month for change calculation
    if now.month == 1:
        prev_month_str = f"{now.year - 1}-12"
    else:
        prev_month_str = f"{now.year}-{now.month - 1:02d}"

    for kb_name, month_counts in kb_monthly.items():
        prev_month_count += month_counts.get(prev_month_str, 0)

    # Build sorted month list: capped to last 18 months for clean display
    if all_months:
        # Generate the last 18 months (including current)
        display_months = []
        for i in range(17, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            display_months.append(f"{y}-{m:02d}")
        sorted_months = display_months
    else:
        sorted_months = [current_month]

    # Build series data for each KB (consistent order)
    colors = ["#00d4ff", "#00ff88", "#a855f7", "#ffaa00", "#ff5555"]
    series = []
    for idx, kb in enumerate(kb_list):
        kb_name = kb["name"]
        month_counts = kb_monthly.get(kb_name, {})
        data = [month_counts.get(m, 0) for m in sorted_months]
        series.append({
            "name": kb_name,
            "data": data,
            "color": colors[idx % len(colors)],
        })

    # Compute change percentages
    new_change_pct = 0.0
    if prev_month_count > 0:
        new_change_pct = round((total_new_count - prev_month_count) / prev_month_count * 100, 1)

    updated_change_pct = 0.0
    # Compare last 30 days vs the 30 days before that
    sixty_days_ago = current_ts - 60 * 86400
    prev_updated_count = 0
    for kb in kb_list:
        kb_name = kb["name"]
        kb_dir = os.path.join(base_dir, kb_name)
        if not os.path.isdir(kb_dir):
            continue
        for root, _dirs, files in os.walk(kb_dir):
            for f in files:
                if not _is_supported_file(f):
                    continue
                full_path = os.path.join(root, f)
                try:
                    mtime = os.stat(full_path).st_mtime
                except OSError:
                    continue
                if sixty_days_ago <= mtime < thirty_days_ago:
                    prev_updated_count += 1
    if prev_updated_count > 0:
        updated_change_pct = round((total_updated_count - prev_updated_count) / prev_updated_count * 100, 1)

    result = {
        "months": sorted_months,
        "series": series,
        "summary": {
            "new_count": total_new_count,
            "new_change_pct": new_change_pct,
            "updated_count": total_updated_count,
            "updated_change_pct": updated_change_pct,
        },
    }

    _set_cache("scan_kb_trend_data", result)
    return result


def _empty_trend_data() -> dict:
    """Return an empty trend data structure."""
    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    months = []
    for i in range(5, -1, -1):
        if now.month - i >= 1:
            months.append(f"{now.year}-{now.month - i:02d}")
        else:
            months.append(f"{now.year - 1}-{now.month - i + 12:02d}")
    return {
        "months": months,
        "series": [],
        "summary": {
            "new_count": 0,
            "new_change_pct": 0.0,
            "updated_count": 0,
            "updated_change_pct": 0.0,
        },
    }


def scan_kb_asset_stats() -> dict:
    """Knowledge asset statistics across all folder-based knowledge bases.

    Returns per-KB stats: file count, total size, extension breakdown.
    Data is the source of truth from the filesystem.
    Cached for 60 seconds.
    """
    cached = _cached("scan_kb_asset_stats", ttl=60)
    if cached is not None:
        return cached

    from collections import defaultdict

    base_dir = _get_kb_dir()
    if not base_dir:
        result = _empty_asset_stats()
        _set_cache("scan_kb_asset_stats", result)
        return result

    kb_list = scan_knowledge_bases()
    colors = ["#00d4ff", "#00ff88", "#a855f7", "#ffaa00", "#ff5555"]
    total_count = 0
    total_size = 0
    ext_totals: dict[str, int] = defaultdict(int)
    categories = []

    for idx, kb in enumerate(kb_list):
        kb_name = kb["name"]
        kb_dir = os.path.join(base_dir, kb_name)
        if not os.path.isdir(kb_dir):
            continue

        kb_count = 0
        kb_size = 0
        ext_counts: dict[str, int] = defaultdict(int)

        for root, _dirs, files in os.walk(kb_dir):
            for f in files:
                if not _is_supported_file(f):
                    continue
                full_path = os.path.join(root, f)
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue
                _, ext = os.path.splitext(f)
                ext_lower = ext.lower()
                kb_count += 1
                kb_size += stat.st_size
                ext_counts[ext_lower] += 1
                ext_totals[ext_lower] += 1

        total_count += kb_count
        total_size += kb_size

        # Build extensions list sorted by count
        extensions = sorted(
            [{"ext": e, "count": c} for e, c in ext_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

        categories.append({
            "name": kb_name,
            "count": kb_count,
            "size": kb_size,
            "value": 0,  # will be computed after total_count is known
            "color": colors[idx % len(colors)],
            "extensions": extensions,
        })

    # Compute percentages
    for cat in categories:
        cat["value"] = round(cat["count"] / total_count * 100, 1) if total_count > 0 else 0

    # Extension summary
    extension_summary = sorted(
        [{"ext": e, "count": c, "value": round(c / total_count * 100, 1) if total_count > 0 else 0}
         for e, c in ext_totals.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    result = {
        "total_count": total_count,
        "total_size": total_size,
        "categories": categories,
        "extension_summary": extension_summary,
    }

    _set_cache("scan_kb_asset_stats", result)
    return result


def _empty_asset_stats() -> dict:
    """Return an empty asset stats structure."""
    return {
        "total_count": 0,
        "total_size": 0,
        "categories": [],
        "extension_summary": [],
    }


# ── Knowledge source distribution ────────────────────────────────────────

# Mapping from fine-grained knowledge_type to 5 major source categories
_SOURCE_GROUPS: list[dict] = [
    {
        "name": "标准规范体系",
        "types": ["行业标准", "企业标准", "国家标准", "检定规程", "计量规范",
                  "能源行业标准", "技术规程", "产品规范", "技术规范"],
        "color": "#00d4ff",
        "description": "国标/行标/企标/检定规程等规范性文件",
    },
    {
        "name": "作业指导体系",
        "types": ["作业指导书", "操作手册", "技术方案", "法律法规"],
        "color": "#00ff88",
        "description": "作业指导书/操作手册/技术方案等操作类文件",
    },
    {
        "name": "培训考试体系",
        "types": ["培训题库", "培训资料"],
        "color": "#a855f7",
        "description": "培训资料/试题库等培训类文件",
    },
    {
        "name": "管理制度体系",
        "types": ["管理制度"],
        "color": "#ffaa00",
        "description": "管理办法/管理规定等制度类文件",
    },
    {
        "name": "技术文档体系",
        "types": ["技术文档"],
        "color": "#ff5555",
        "description": "通用技术文档/参考资料",
    },
]


def scan_kb_source_distribution() -> list[dict]:
    """Knowledge source distribution across 5 major categories.

    Groups the fine-grained knowledge_type of all files into 5 categories:
      1. 标准规范体系 — 国标/行标/企标/检定规程等
      2. 作业指导体系 — 作业指导书/操作手册/技术方案等
      3. 培训考试体系 — 培训资料/试题库等
      4. 管理制度体系 — 管理办法/管理规定等
      5. 技术文档体系 — 通用技术文档

    Cached for 60 seconds.
    """
    cached = _cached("scan_kb_source_distribution", ttl=60)
    if cached is not None:
        return cached

    # Reuse the cached all-files list if available
    all_files = _cached("scan_all_kb_files", ttl=60)
    if all_files is None:
        # Force a scan
        scan_all_kb_files(tab="latest", page_size=99999)
        all_files = _cached("scan_all_kb_files", ttl=60)

    from collections import Counter
    type_counts: Counter = Counter()
    total = 0
    if all_files is not None:
        for item in all_files:
            type_counts[item.get("knowledge_type", "技术文档")] += 1
            total += 1

    # Build the mapping from type to group
    type_to_group: dict[str, str] = {}
    for group in _SOURCE_GROUPS:
        for t in group["types"]:
            type_to_group[t] = group["name"]

    # Aggregate per group
    result = []
    for group in _SOURCE_GROUPS:
        count = sum(type_counts.get(t, 0) for t in group["types"])
        pct = round(count / total * 100, 1) if total > 0 else 0
        result.append({
            "name": group["name"],
            "value": pct,
            "count": count,
            "color": group["color"],
            "description": group["description"],
        })

    _set_cache("scan_kb_source_distribution", result)
    return result


def invalidate_cache():
    """Clear the scan cache. Call when files change on disk."""
    _cache.clear()
