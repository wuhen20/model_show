"""Knowledge API routes — integrates LightRAG + Memgraph."""

import json
import os
from typing import Any

import httpx
from fastapi import APIRouter, Query

from app.core.config import settings
from app.services import lightrag_service, memgraph_service
from app.services import fake_data

router = APIRouter()

PARSED_DATA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'parsed_data.json'
)

_all_items: list[dict] = []
_categories_raw: dict = {}
_total_files: int = 0


def _load_data():
    global _all_items, _categories_raw, _total_files
    abs_path = os.path.abspath(PARSED_DATA_PATH)
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _total_files = data.get('total_files', 0)
        _categories_raw = data.get('categories', {})
    except Exception as e:
        print(f"[Knowledge] Failed to load data: {e}")
        _total_files = 0
        _categories_raw = {}
        return

    idx = 1
    for cat_name, cat_data in _categories_raw.items():
        if not cat_name:
            continue
        for sub_key, sub_data in cat_data.get('subs', {}).items():
            sub_display = sub_data.get('name', sub_key)
            for fname in sub_data.get('files', []):
                clean = fname
                for prefix in (
                    [str(i) + '.' for i in range(1, 200)]
                    + [str(i) + '-' for i in range(1, 200)]
                    + [str(i) + '、' for i in range(1, 200)]
                    + ['0-']
                ):
                    if clean.startswith(prefix):
                        clean = clean[len(prefix):]
                        break
                clean = (
                    clean.replace('.docx', '')
                    .replace('.doc', '')
                    .replace('.txt', '')
                    .replace('.xlsx', '')
                    .replace('.pdf', '')
                )
                ktype = _infer_type(clean, sub_display)
                source = _infer_source(clean, sub_display, cat_name)
                score = (
                    5
                    if any(k in clean.upper() for k in ['JJG', 'GB', 'DLT', 'DL/', 'Q/GDW', 'QGDW'])
                    else (4 if '指导书' in clean else 3)
                )
                status = '已发布'
                if '新增' in fname:
                    status = '待审核'
                    score = max(score - 1, 2)
                _all_items.append(
                    {
                        'id': f'k{idx:04d}',
                        'title': clean,
                        'category_id': sub_key,
                        'category_name': sub_display,
                        'parent_category': cat_name,
                        'knowledge_type': ktype,
                        'source': source,
                        'score': score,
                        'status': status,
                        'update_time': f'2026-{(idx % 12) + 1:02d}-{(idx % 28) + 1:02d}',
                        'file_path': f'{cat_name}/{sub_key}/{fname}',
                        'description': f'《{clean}》，属于{cat_name}/{sub_display}类目，{ktype}类文档。',
                    }
                )
                idx += 1

    _all_items.sort(key=lambda x: x['update_time'], reverse=True)


def _infer_type(name: str, sub_name: str) -> str:
    upper = name.upper()
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
    if '指导书' in name or '指导书' in sub_name:
        return '作业指导书'
    if '管理办法' in name or '管理规定' in name:
        return '管理制度'
    if '技术规范' in name:
        return '技术规范'
    if '功能规范' in name or '型式规范' in name:
        return '产品规范'
    if '试题' in name or '题库' in name or '计算' in name or '案例' in name:
        return '培训题库'
    if '手册' in name or '操作' in name:
        return '操作手册'
    if '方案' in name:
        return '技术方案'
    if '宣贯' in name or '培训' in name or '资料' in name:
        return '培训资料'
    if '规程' in name:
        return '技术规程'
    if '条例' in name or '法' in name:
        return '法律法规'
    return '技术文档'


def _infer_source(name: str, sub_name: str, cat_name: str) -> str:
    upper = name.upper()
    if any(k in upper for k in ['JJG', 'JJF']):
        return '国家计量规程'
    if any(k in upper for k in ['GB', 'GBT']):
        return '国家标准'
    if any(k in upper for k in ['DLT', 'DL/', 'DL/T']):
        return '电力行业标准'
    if any(k in upper for k in ['Q/GDW', 'QGDW']):
        return '国家电网企业标准'
    if any(k in upper for k in ['JGT']):
        return '建筑行业标准'
    if any(k in upper for k in ['NBT']):
        return '能源行业标准'
    if any(k in upper for k in ['TCEC']):
        return '团体标准'
    if '条例' in name or '法' in name:
        return '国家法律法规'
    if '指导书' in name:
        return '内部文档'
    if '试题' in name or '题库' in name:
        return '培训资料'
    return '内部文档'


# _load_data()  # 暂时注释，避免启动时因缺少 parsed_data.json 而报错


# ---------------------------------------------------------------------------
# Knowledge base list (new)
# ---------------------------------------------------------------------------


@router.get("/bases", response_model=dict)
async def get_knowledge_bases():
    """Return all registered knowledge bases with their processing status.

    Reads from SQLite (which is seeded from settings.knowledge_bases on first run).
    LightRAG and Memgraph calls will fail fast if those services are unreachable.
    """
    from app.services import db_service

    all_kbs = db_service.list_knowledge_bases()
    result = []
    for kb in all_kbs:
        status_counts: dict[str, int] = {}
        try:
            status_counts = await lightrag_service.get_status_counts(workspace=kb["workspace"])
        except Exception:
            pass
        # doc_count from local DB (uploaded docs), plus LightRAG counts
        lr_doc_count = sum(v for k, v in status_counts.items() if k != "all") if status_counts else 0
        local_doc_count = db_service.count_documents(kb["id"])
        # Get tags for this KB
        tags = db_service.get_tags_tree(kb["id"])

        result.append(
            {
                "id": kb["id"],
                "name": kb["name"],
                "workspace": kb["workspace"],
                "description": kb.get("description", ""),
                "icon": kb.get("icon", "brain"),
                "color": kb.get("color", "#00d4ff"),
                "doc_count": max(lr_doc_count, local_doc_count),
                "status_counts": status_counts,
                "tags": tags,
            }
        )
    return {"code": 0, "data": result}


# ---------------------------------------------------------------------------
# Pipeline status (new)
# ---------------------------------------------------------------------------


@router.get("/pipeline-status", response_model=dict)
async def get_pipeline_status(workspace: str | None = None):
    """Proxy LightRAG pipeline status."""
    try:
        data = await lightrag_service.get_pipeline_status(workspace=workspace)
        return {"code": 0, "data": data}
    except Exception as e:
        return {"code": -1, "message": str(e)}


# ---------------------------------------------------------------------------
# Original endpoints — kept for backward compatibility
# ---------------------------------------------------------------------------


# ── Stats cache (TTL 60s) ─────────────────────────────────────────────────
_stats_cache: dict[str, Any] | None = None
_stats_cache_ts: float = 0.0
_STATS_TTL = 60.0  # seconds
_structured_count: int | None = None  # lazy-computed, never changes


def _get_structured_count() -> int:
    """Count structured items from the in-memory list (pure CPU, fast)."""
    global _structured_count
    if _structured_count is None:
        _structured_count = sum(
            1
            for i in _all_items
            if i['knowledge_type']
            in [
                '国家标准', '行业标准', '检定规程', '企业标准', '计量规范',
                '国家计量规程', '电力行业标准', '国家电网企业标准', '产品规范',
                '技术规范', '技术规程', '建筑行业标准', '能源行业标准',
                '团体标准', '国家法律法规', '法律法规', '管理制度',
            ]
        )
    return _structured_count


@router.get("/stats", response_model=dict)
async def get_knowledge_stats():
    """Knowledge stats — uses folder KB filesystem scan as the source of truth.

    The Memgraph entity count is fetched in the background and cached.
    If Memgraph is down, the default value is used (no blocking).
    """
    if settings.fake_mode:
        return {"code": 0, "data": fake_data.get_fake_response("/stats")}

    global _stats_cache, _stats_cache_ts
    import time as _time

    now = _time.time()

    # Return cached data if fresh
    if _stats_cache is not None and (now - _stats_cache_ts) < _STATS_TTL:
        return {"code": 0, "data": _stats_cache}

    # Use folder KB filesystem scan as the source of truth
    from app.services import folder_kb_service
    folder_stats = folder_kb_service.scan_kb_asset_stats()
    total_count = folder_stats["total_count"]

    # Count structured items from folder KB file list
    structured_count = 0
    structured_types = {
        '国家标准', '行业标准', '检定规程', '企业标准', '计量规范',
        '国家计量规程', '电力行业标准', '国家电网企业标准', '产品规范',
        '技术规范', '技术规程', '国家法律法规', '法律法规', '管理制度',
    }
    try:
        all_items = folder_kb_service.scan_all_kb_files(tab="latest", page_size=999999)
        structured_count = sum(1 for item in all_items.get("items", []) if item.get("knowledge_type") in structured_types)
        # scan_all_kb_files paginates, so count from the full cached list instead
        cached_all = folder_kb_service._cached("scan_all_kb_files")
        if cached_all is not None:
            structured_count = sum(1 for item in cached_all if item.get("knowledge_type") in structured_types)
    except Exception:
        pass

    # Use cached graph_entities if we have one, else default to 0
    graph_entities = _stats_cache.get("graph_entities", 0) if _stats_cache else 0

    data = {
        "total_count": total_count,
        "structured_count": structured_count,
        "unstructured_count": total_count - structured_count,
        "graph_entities": graph_entities,
        "business_domains": len(folder_stats["categories"]),
        "completeness": 92.5,
        "availability": 95.8,
    }

    _stats_cache = data
    _stats_cache_ts = now

    # Kick off a background refresh of graph_entities (non-blocking)
    # Only when Memgraph is enabled — otherwise it stays at 0
    if settings.memgraph_enabled:
        async def _refresh_graph_entities():
            # _stats_cache is a module-level global
            global _stats_cache
            try:
                real_count = await memgraph_service.get_total_entity_count()
                if real_count > 0 and _stats_cache is not None:
                    _stats_cache["graph_entities"] = real_count
            except Exception:
                pass

        import asyncio
        asyncio.create_task(_refresh_graph_entities())

    return {"code": 0, "data": data}


@router.get("/categories", response_model=dict)
def get_categories(parent_id: str | None = None):
    result = []
    colors = ['#00d4ff', '#00ff88', '#a855f7', '#ffaa00', '#ff5555', '#36a3f7']
    icons = ['brain', 'plug', 'database', 'scale', 'trending-down', 'shield']
    cat_idx = 0
    for cat_name, cat_data in _categories_raw.items():
        if not cat_name:
            continue
        color = colors[cat_idx % len(colors)]
        icon = icons[cat_idx % len(icons)]

        sub_cats = []
        for sub_key, sub_data in cat_data.get('subs', {}).items():
            sub_cats.append(
                {
                    'id': sub_key,
                    'name': sub_data.get('name', sub_key),
                    'doc_count': sub_data.get('total', 0),
                    'color': color,
                }
            )
        sub_cats.sort(key=lambda x: x['doc_count'], reverse=True)

        if parent_id and cat_name != parent_id:
            for sc in sub_cats:
                if sc['id'] == parent_id or sc['name'] == parent_id:
                    return {"code": 0, "data": [sc]}
            continue

        top_names = [s['name'] for s in sub_cats[:5]]
        desc = f"涵盖{'、'.join(top_names)}等{len(sub_cats)}个分类，共{cat_data.get('total', 0)}份文档"
        result.append(
            {
                "id": cat_name,
                "name": cat_name,
                "description": desc,
                "parent_id": None,
                "doc_count": cat_data.get('total', 0),
                "icon": icon,
                "color": color,
                "sub_categories": sub_cats[:8],
            }
        )
        cat_idx += 1
    return {"code": 0, "data": result}


@router.get("/list", response_model=dict)
async def get_knowledge_list(
    category_id: str | None = None,
    tab: str = "latest",
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    workspace: str | None = None,
):
    """Knowledge list — if *workspace* is given, data comes from LightRAG;
    otherwise falls back to the static parsed_data.json."""
    if workspace:
        try:
            lr_data = await lightrag_service.get_documents_paginated(
                workspace=workspace, page=page, page_size=page_size
            )
            docs = lr_data.get("documents", [])
            items = []
            for d in docs:
                status = d.get("status", "PENDING").upper()
                # Use file_path from LightRAG response as the display title
                file_name = d.get("file_path", d.get("id", ""))
                # Strip common extensions for cleaner display
                for ext in (".docx", ".doc", ".txt", ".pdf", ".xlsx"):
                    if file_name.endswith(ext):
                        file_name = file_name[: -len(ext)]
                        break
                items.append(
                    {
                        "id": d.get("id", ""),
                        "title": file_name,
                        "category_id": workspace,
                        "category_name": "采集自愈知识库",
                        "parent_category": workspace,
                        "knowledge_type": "文档",
                        "source": "LightRAG",
                        "score": 5 if status == "PROCESSED" else 3,
                        "status": status,
                        "update_time": d.get("updated_at", "")[:10] if d.get("updated_at") else "",
                        "file_path": d.get("file_path", ""),
                        "description": (d.get("content_summary", "") or "")[:100],
                    }
                )
            pagination = lr_data.get("pagination", {})
            # status_counts may be nested under "status_counts" key
            raw_sc = lr_data.get("status_counts", {})
            if isinstance(raw_sc, dict) and "status_counts" in raw_sc:
                raw_sc = raw_sc["status_counts"]
            return {
                "code": 0,
                "data": {
                    "items": items,
                    "total": pagination.get("total_count", len(items)),
                    "page": pagination.get("page", page),
                    "page_size": pagination.get("page_size", page_size),
                    "status_counts": raw_sc,
                },
            }
        except Exception as e:
            return {"code": -1, "message": f"LightRAG 请求失败: {e}"}

    # Fallback: static data
    items = _all_items[:]
    if category_id:
        items = [
            i
            for i in items
            if i['category_id'] == category_id or i['parent_category'] == category_id
        ]
    if keyword:
        items = [i for i in items if keyword in i['title'] or keyword in i['description']]
    if tab == "popular":
        items.sort(key=lambda x: x['score'], reverse=True)
    elif tab == "valuable":
        items = [i for i in items if i['score'] >= 5]
    elif tab == "pending":
        items = [i for i in items if i['status'] == '待审核']
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "code": 0,
        "data": {
            "items": items[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/detail/{item_id}", response_model=dict)
def get_knowledge_detail(item_id: str):
    for item in _all_items:
        if item['id'] == item_id:
            detail = {**item}
            detail['content'] = (
                f"本文档为《{item['title']}》的详细内容。"
                f"该文档属于{item['parent_category']}/{item['category_name']}类目，"
                f"知识类型为{item['knowledge_type']}，来源于{item['source']}。"
                f"文档当前状态为{item['status']}，质量评分为{item['score']}星。"
                f"原始文件路径：{item['file_path']}"
            )
            detail['tags'] = [item['knowledge_type'], item['category_name'], item['source']]
            return {"code": 0, "data": detail}
    return {"code": -1, "message": "知识不存在"}


@router.get("/source-distribution", response_model=dict)
def get_source_distribution():
    if settings.fake_mode:
        return {"code": 0, "data": fake_data.get_fake_response("/folder/source-distribution")}

    source_map: dict[str, int] = {}
    for item in _all_items:
        s = item['source']
        source_map[s] = source_map.get(s, 0) + 1
    total = sum(source_map.values())
    result = []
    color_list = ['#00d4ff', '#00ff88', '#a855f7', '#ffaa00', '#ff5555', '#36a3f7', '#eb2f96']
    sorted_sources = sorted(source_map.items(), key=lambda x: x[1], reverse=True)
    for idx, (name, count) in enumerate(sorted_sources):
        result.append(
            {
                "name": name,
                "value": round(count / total * 100, 1),
                "count": count,
                "color": color_list[idx % len(color_list)],
            }
        )
    return {"code": 0, "data": result}


@router.get("/category-distribution", response_model=dict)
def get_category_distribution():
    if settings.fake_mode:
        return {"code": 0, "data": fake_data.get_fake_response("/folder/source-distribution")}

    color_list = ['#00d4ff', '#00ff88', '#a855f7', '#ffaa00', '#ff5555', '#36a3f7']
    result = []
    total = _total_files or 1
    cat_idx = 0
    for cat_name, cat_data in _categories_raw.items():
        if not cat_name:
            continue
        count = cat_data.get('total', 0)
        result.append(
            {
                "name": cat_name,
                "value": round(count / total * 100, 1),
                "count": count,
                "color": color_list[cat_idx % len(color_list)],
            }
        )
        cat_idx += 1
    return {"code": 0, "data": result}


@router.get("/quality-metrics", response_model=dict)
def get_quality_metrics():
    if settings.fake_mode:
        return {"code": 0, "data": fake_data.get_fake_response("/quality-metrics")}

    return {
        "code": 0,
        "data": {
            "overall_score": 93.6,
            "metrics": [
                {"name": "准确性", "value": 94.2},
                {"name": "完整性", "value": 92.8},
                {"name": "时效性", "value": 93.1},
                {"name": "一致性", "value": 93.8},
                {"name": "可理解性", "value": 93.9},
            ],
        },
    }


# ---------------------------------------------------------------------------
# Graph — reads from Memgraph (written by LightRAG)
# ---------------------------------------------------------------------------


@router.get("/graph", response_model=dict)
async def get_knowledge_graph(
    workspace: str | None = None,
    kb_name: str | None = None,
    max_nodes: int = Query(default=200, ge=10, le=5000),
    full: bool = Query(default=False),
):
    """Return knowledge graph data from Memgraph.

    LightRAG writes entities/relationships into Memgraph. Nodes have a
    `kb_name` property that identifies which folder KB they belong to.

    - kb_name: returns graph for that specific folder KB
    - workspace: returns graph for that specific workspace label (legacy)
    - Neither: merges all folder KB graphs into one combined graph
    - full=True: return all nodes without the per-KB cap (for detail view)
    """
    # When full=True, use a very large limit so the Cypher query returns everything
    effective_max = max_nodes if not full else 5000

    if kb_name:
        try:
            graph_data = await memgraph_service.get_graph_by_kb_name(
                kb_name=kb_name, max_nodes=effective_max, full=full
            )
            return {"code": 0, "data": graph_data}
        except Exception as e:
            return {
                "code": 1,
                "data": {
                    "nodes": [],
                    "links": [],
                    "stats": {"entity_count": 0, "relation_count": 0, "coverage": 0},
                },
                "message": f"Memgraph 图谱查询失败: {e}",
            }

    if workspace:
        try:
            graph_data = await memgraph_service.get_graph_data(
                workspace=workspace, max_nodes=effective_max, full=full
            )
            return {"code": 0, "data": graph_data}
        except Exception as e:
            return {
                "code": 1,
                "data": {
                    "nodes": [],
                    "links": [],
                    "stats": {"entity_count": 0, "relation_count": 0, "coverage": 0},
                },
                "message": f"Memgraph 图谱查询失败: {e}",
            }

    # No workspace or kb_name: merge all folder KB graphs
    try:
        # When full=True, each KB returns all nodes (no per-KB cap);
        # otherwise keep the preview cap (min(80, max_nodes // 3))
        per_ws_limit = 5000 if full else min(80, max_nodes // 3)
        graph_data = await memgraph_service.get_all_workspaces_graph(
            max_nodes_per_ws=per_ws_limit, full=full
        )
        return {"code": 0, "data": graph_data}
    except Exception as e:
        return {
            "code": 1,
            "data": {
                "nodes": [],
                "links": [],
                "stats": {"entity_count": 0, "relation_count": 0, "coverage": 0},
            },
            "message": f"Memgraph 合并图谱查询失败: {e}",
        }

    node_list = list(combined_nodes_map.values())[:max_nodes]
    node_names = {n["name"] for n in node_list}
    link_list = [l for l in combined_links if l["source"] in node_names and l["target"] in node_names][:max_nodes * 2]

    coverage = round(min(95, len(node_list) * 0.5 + 30), 1) if node_list else 0

    return {
        "code": 0,
        "data": {
            "nodes": node_list,
            "links": link_list,
            "stats": {
                "entity_count": total_entities,
                "relation_count": total_relations,
                "coverage": coverage,
            },
        },
    }


# ---------------------------------------------------------------------------
# LightRAG proxy endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------


@router.get("/lightrag/graph", response_model=dict)
async def get_lightrag_graph():
    """Proxy: fetch popular labels then subgraphs from LightRAG."""
    labels = []
    try:
        labels = await lightrag_service.get_graph_labels()
    except Exception:
        pass

    if not labels or not isinstance(labels, list):
        return {
            "code": 1,
            "data": {
                "nodes": [],
                "links": [],
                "stats": {"entity_count": 0, "relation_count": 0, "coverage": 0},
            },
        }

    all_nodes_map: dict[str, dict] = {}
    all_links: list[dict] = []
    seen_edges: set[str] = set()

    seed_labels = labels[:15]
    for lbl in seed_labels:
        try:
            sub = await lightrag_service.get_graph(label=lbl, max_depth=2, max_nodes=30)
        except Exception:
            continue

        nodes_raw = sub.get("nodes", [])
        edges_raw = sub.get("edges", [])
        for n in nodes_raw:
            nid = n.get("id", n.get("label", ""))
            name = n.get("label", nid)
            if name and name not in all_nodes_map:
                degree = n.get("degree", 1)
                etype = n.get("entity_type", "")
                if etype in ["Organization", "Concept", "Method"]:
                    color = "#00d4ff"
                    cat = 0
                elif etype in ["Event", "Artifact", "Data"]:
                    color = "#ffaa00"
                    cat = 2
                else:
                    color = "#00ff88"
                    cat = 1
                all_nodes_map[name] = {
                    "name": name,
                    "symbolSize": min(55, 12 + degree * 2),
                    "category": cat,
                    "itemStyle": {"color": color},
                }

        for e in edges_raw:
            src = e.get("source", "")
            tgt = e.get("target", "")
            key = f"{src}|{tgt}"
            if src and tgt and key not in seen_edges:
                seen_edges.add(key)
                all_links.append({"source": src, "target": tgt})

    node_list = list(all_nodes_map.values())[:100]
    link_list = all_links[:150]

    total_entities = len(all_nodes_map)
    total_relations = len(all_links)

    return {
        "code": 0,
        "data": {
            "nodes": node_list,
            "links": link_list,
            "stats": {
                "entity_count": total_entities,
                "relation_count": total_relations,
                "coverage": round(min(95, total_entities * 0.5 + 30), 1),
            },
        },
    }


@router.get("/lightrag/status", response_model=dict)
async def get_lightrag_status():
    """Proxy: fetch document status counts from LightRAG."""
    try:
        data = await lightrag_service.get_status_counts()
        return {"code": 0, "data": data}
    except Exception as e:
        return {"code": -1, "message": str(e)}


@router.get("/lightrag/labels", response_model=dict)
async def get_lightrag_labels(limit: int = 50):
    """Proxy: fetch popular graph labels from LightRAG."""
    try:
        data = await lightrag_service.get_graph_labels()
        return {"code": 0, "data": data[:limit]}
    except Exception as e:
        return {"code": -1, "message": str(e)}
