import json
import os
from fastapi import APIRouter

router = APIRouter()

PARSED_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'parsed_data.json')

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
                for prefix in [str(i) + '.' for i in range(1, 200)] + [str(i) + '-' for i in range(1, 200)] + [str(i) + '、' for i in range(1, 200)] + ['0-']:
                    if clean.startswith(prefix):
                        clean = clean[len(prefix):]
                        break
                clean = clean.replace('.docx', '').replace('.doc', '').replace('.txt', '').replace('.xlsx', '').replace('.pdf', '')
                ktype = _infer_type(clean, sub_display)
                source = _infer_source(clean, sub_display, cat_name)
                score = 5 if any(k in clean.upper() for k in ['JJG', 'GB', 'DLT', 'DL/', 'Q/GDW', 'QGDW']) else (4 if '指导书' in clean else 3)
                status = '已发布'
                if '新增' in fname:
                    status = '待审核'
                    score = max(score - 1, 2)
                _all_items.append({
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
                    'description': f'《{clean}》，属于{cat_name}/{sub_display}类目，{ktype}类文档。'
                })
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


@router.get("/stats", response_model=dict)
def get_knowledge_stats():
    structured = sum(1 for i in _all_items if i['knowledge_type'] in ['国家标准', '行业标准', '检定规程', '企业标准', '计量规范', '国家计量规程', '电力行业标准', '国家电网企业标准', '产品规范', '技术规范', '技术规程', '建筑行业标准', '能源行业标准', '团体标准', '国家法律法规', '法律法规', '管理制度'])
    return {
        "code": 0,
        "data": {
            "total_count": _total_files,
            "structured_count": structured,
            "unstructured_count": _total_files - structured,
            "graph_entities": 36584,
            "business_domains": len([k for k in _categories_raw if k]),
            "completeness": 92.5,
            "availability": 95.8
        }
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
            sub_cats.append({
                'id': sub_key,
                'name': sub_data.get('name', sub_key),
                'doc_count': sub_data.get('total', 0),
                'color': color,
            })
        sub_cats.sort(key=lambda x: x['doc_count'], reverse=True)

        if parent_id and cat_name != parent_id:
            for sc in sub_cats:
                if sc['id'] == parent_id or sc['name'] == parent_id:
                    return {"code": 0, "data": [sc]}
            continue

        top_names = [s['name'] for s in sub_cats[:5]]
        desc = f"涵盖{'、'.join(top_names)}等{len(sub_cats)}个分类，共{cat_data.get('total', 0)}份文档"
        result.append({
            "id": cat_name,
            "name": cat_name,
            "description": desc,
            "parent_id": None,
            "doc_count": cat_data.get('total', 0),
            "icon": icon,
            "color": color,
            "sub_categories": sub_cats[:8],
        })
        cat_idx += 1
    return {"code": 0, "data": result}


@router.get("/list", response_model=dict)
def get_knowledge_list(
    category_id: str | None = None,
    tab: str = "latest",
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    items = _all_items[:]
    if category_id:
        items = [i for i in items if i['category_id'] == category_id or i['parent_category'] == category_id]
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
            "page_size": page_size
        }
    }


@router.get("/detail/{item_id}", response_model=dict)
def get_knowledge_detail(item_id: str):
    for item in _all_items:
        if item['id'] == item_id:
            detail = {**item}
            detail['content'] = f"本文档为《{item['title']}》的详细内容。该文档属于{item['parent_category']}/{item['category_name']}类目，知识类型为{item['knowledge_type']}，来源于{item['source']}。文档当前状态为{item['status']}，质量评分为{item['score']}星。原始文件路径：{item['file_path']}"
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
        result.append({
            "name": name,
            "value": round(count / total * 100, 1),
            "count": count,
            "color": color_list[idx % len(color_list)]
        })
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
        result.append({
            "name": cat_name,
            "value": round(count / total * 100, 1),
            "count": count,
            "color": color_list[cat_idx % len(color_list)]
        })
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
                {"name": "可理解性", "value": 93.9}
            ]
        }
    }


@router.get("/graph", response_model=dict)
def get_knowledge_graph():
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
        kb_nodes.append({
            'name': cat_name,
            'symbolSize': min(70, 30 + cat_data.get('total', 0) // 30),
            'category': 0,
            'itemStyle': {'color': '#00d4ff'}
        })

        sub_items = list(cat_data.get('subs', {}).items())
        sorted_subs = sorted(sub_items, key=lambda x: x[1].get('total', 0), reverse=True)
        for sub_key, sub_data in sorted_subs[:6]:
            sub_name = sub_data.get('name', sub_key)
            if sub_name == cat_name:
                continue
            kb_nodes.append({
                'name': sub_name,
                'symbolSize': min(50, 20 + sub_data.get('total', 0) // 50),
                'category': 1,
                'itemStyle': {'color': '#00ff88'}
            })
            kb_links.append({'source': cat_name, 'target': sub_name})

            for tk, tc in list(type_map.items())[:4]:
                if tk in ['内部文档', '技术文档']:
                    continue
                node_name = f"{sub_name}_{tk}"
                if any(n['name'] == node_name for n in kb_nodes):
                    continue
                kb_nodes.append({
                    'name': node_name,
                    'symbolSize': 18,
                    'category': 2,
                    'itemStyle': {'color': type_colors.get(tk, '#00d4ff')},
                    'label': {'show': False }
                })
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
                "coverage": 89.7
            }
        }
    }
