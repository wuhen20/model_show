"""Knowledge API routes — integrates LightRAG + Memgraph."""

import json
import os
from typing import Any

import httpx
from fastapi import APIRouter, Query

from app.core.config import settings
from app.services import lightrag_service, memgraph_service

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


_load_data()


# ---------------------------------------------------------------------------
# Knowledge base list (new)
# ---------------------------------------------------------------------------


@router.get("/bases", response_model=dict)
async def get_knowledge_bases():
    """Return all registered knowledge bases with their processing status."""
    result = []
    for kb in settings.knowledge_bases:
        status_counts: dict[str, int] = {}
        try:
            status_counts = await lightrag_service.get_status_counts(workspace=kb["workspace"])
        except Exception:
            pass
        # Exclude the "all" key from the count to avoid double-counting
        doc_count = sum(v for k, v in status_counts.items() if k != "all") if status_counts else 0
        result.append(
            {
                "id": kb["id"],
                "name": kb["name"],
                "workspace": kb["workspace"],
                "description": kb.get("description", ""),
                "icon": kb.get("icon", "brain"),
                "color": kb.get("color", "#00d4ff"),
                "doc_count": doc_count,
                "status_counts": status_counts,
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


@router.get("/stats", response_model=dict)
async def get_knowledge_stats():
    structured = sum(
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
    # Try to get real entity count from Memgraph
    graph_entities = 36584
    try:
        graph_data = await memgraph_service.get_graph_data(
            workspace="cai_ji_zi_yu", max_nodes=1
        )
        real_count = graph_data.get("stats", {}).get("entity_count", 0)
        if real_count > 0:
            graph_entities = real_count
    except Exception:
        pass

    return {
        "code": 0,
        "data": {
            "total_count": _total_files,
            "structured_count": structured,
            "unstructured_count": _total_files - structured,
            "graph_entities": graph_entities,
            "business_domains": len([k for k in _categories_raw if k]),
            "completeness": 92.5,
            "availability": 95.8,
        },
    }


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
# Graph — now reads from Memgraph when workspace is specified
# ---------------------------------------------------------------------------


@router.get("/graph", response_model=dict)
async def get_knowledge_graph(
    workspace: str | None = None,
    max_nodes: int = Query(default=200, ge=10, le=1000),
):
    """Return knowledge graph data.

    If *workspace* is given, query Memgraph directly for that workspace's
    entities and relationships.  Otherwise fall back to the static type-map
    graph derived from parsed_data.json.
    """
    if workspace:
        try:
            graph_data = await memgraph_service.get_graph_data(
                workspace=workspace, max_nodes=max_nodes
            )
            return {"code": 0, "data": graph_data}
        except Exception as e:
            # Graceful fallback if Memgraph is unavailable
            print(f"[Knowledge] Memgraph query failed: {e}")
            return {
                "code": 1,
                "data": {
                    "nodes": [],
                    "links": [],
                    "stats": {"entity_count": 0, "relation_count": 0, "coverage": 0},
                },
                "message": f"Memgraph 查询失败: {e}",
            }

    # Fallback: static graph from parsed_data types
    type_map: dict[str, int] = {}
    for item in _all_items:
        t = item['knowledge_type']
        type_map[t] = type_map.get(t, 0) + 1

    kb_nodes = []
    kb_links = []
    type_colors = {
        '国家标准': '#00d4ff', '行业标准': '#00ff88', '检定规程': '#a855f7',
        '企业标准': '#ffaa00', '作业指导书': '#ff5555', '法律法规': '#36a3f7',
        '技术规范': '#eb2f96', '操作手册': '#00d4ff', '培训题库': '#00ff88',
        '管理制度': '#a855f7', '培训资料': '#ffaa00', '计量规范': '#ff5555',
        '产品规范': '#36a3f7', '技术规程': '#eb2f96', '技术文档': '#00d4ff',
        '技术方案': '#00ff88', '国家计量规程': '#a855f7', '电力行业标准': '#ffaa00',
        '国家电网企业标准': '#ff5555', '国家法律法规': '#36a3f7',
        '建筑行业标准': '#eb2f96', '能源行业标准': '#00d4ff', '团体标准': '#00ff88',
    }

    for cat_name, cat_data in _categories_raw.items():
        if not cat_name:
            continue
        kb_nodes.append(
            {
                'name': cat_name,
                'symbolSize': min(70, 30 + cat_data.get('total', 0) // 30),
                'category': 0,
                'itemStyle': {'color': '#00d4ff'},
            }
        )

        sub_items = list(cat_data.get('subs', {}).items())
        sorted_subs = sorted(sub_items, key=lambda x: x[1].get('total', 0), reverse=True)
        for sub_key, sub_data in sorted_subs[:6]:
            sub_name = sub_data.get('name', sub_key)
            if sub_name == cat_name:
                continue
            kb_nodes.append(
                {
                    'name': sub_name,
                    'symbolSize': min(50, 20 + sub_data.get('total', 0) // 50),
                    'category': 1,
                    'itemStyle': {'color': '#00ff88'},
                }
            )
            kb_links.append({'source': cat_name, 'target': sub_name})

            for tk, tc in list(type_map.items())[:4]:
                if tk in ['内部文档', '技术文档']:
                    continue
                node_name = f"{sub_name}_{tk}"
                if any(n['name'] == node_name for n in kb_nodes):
                    continue
                kb_nodes.append(
                    {
                        'name': node_name,
                        'symbolSize': 18,
                        'category': 2,
                        'itemStyle': {'color': type_colors.get(tk, '#00d4ff')},
                        'label': {'show': False},
                    }
                )
                kb_links.append({'source': sub_name, 'target': node_name})

    total_entities = sum(n['symbolSize'] for n in kb_nodes) * 50
    total_relations = len(kb_links) * 35

    return {
        "code": 0,
        "data": {
            "nodes": kb_nodes[:80],
            "links": kb_links[:120],
            "stats": {
                "entity_count": total_entities,
                "relation_count": total_relations,
                "coverage": 89.7,
            },
        },
    }


# ---------------------------------------------------------------------------
# LightRAG proxy endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------

LIGHTRAG_BASE = os.environ.get("LIGHTRAG_BASE_URL", "http://127.0.0.1:9621")


@router.get("/lightrag/graph", response_model=dict)
def get_lightrag_graph():
    labels = []
    try:
        r = httpx.get(
            f"{LIGHTRAG_BASE}/graph/label/popular", params={"limit": 20}, timeout=15
        )
        labels = r.json()
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
            r = httpx.get(
                f"{LIGHTRAG_BASE}/graphs",
                params={"label": lbl, "max_depth": 2, "max_nodes": 30},
                timeout=30,
            )
            sub = r.json()
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
def get_lightrag_status():
    try:
        r = httpx.get(f"{LIGHTRAG_BASE}/documents/status_counts", timeout=10)
        return {"code": 0, "data": r.json()}
    except Exception as e:
        return {"code": -1, "message": str(e)}


@router.get("/lightrag/labels", response_model=dict)
def get_lightrag_labels(limit: int = 50):
    try:
        r = httpx.get(
            f"{LIGHTRAG_BASE}/graph/label/popular", params={"limit": limit}, timeout=10
        )
        return {"code": 0, "data": r.json()}
    except Exception as e:
        return {"code": -1, "message": str(e)}
