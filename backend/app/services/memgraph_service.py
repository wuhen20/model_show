"""Memgraph service — query knowledge graph data from Memgraph.

LightRAG writes entities and relationships into Memgraph when
LIGHTRAG_GRAPH_STORAGE=MemgraphStorage is configured.

Data model (as written by LightRAG):
  - Each workspace creates nodes with that workspace name as a Label
  - Node properties: entity_id (display name), entity_type, description, source_id, file_path
  - Relationship type: DIRECTED (with description property)
  - There is also a 'base' label for the default workspace
"""

import os
import re
import time
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from app.core.config import settings


_driver: AsyncDriver | None = None
_driver_verified: bool = False
_driver_failed: bool = False
_driver_fail_ts: float = 0.0
_DRIVER_RETRY_AFTER = 30.0

# ── Workspace name mapping ─────────────────────────────────────────────────
# Folder KB names (Chinese) → Memgraph labels (workspace-derived strings)
# These are set when folder KBs are scanned and used to query per-KB graphs.

_FOLDER_KB_WORKSPACES: list[dict] | None = None


def _kb_name_to_workspace(name: str) -> str:
    """Derive a LightRAG workspace name from a KB display name.

    This must match the workspace name used when uploading documents
    to LightRAG.
    """
    ws = name.lower().strip()
    ws = re.sub(r'[\s\-]+', '_', ws)
    ws = re.sub(r'[^a-z0-9_一-鿿]', '', ws)
    return ws


def get_folder_kb_workspaces() -> list[dict]:
    """Get the list of {name, workspace_label} for all folder KBs.

    Lazily loaded and cached.
    """
    global _FOLDER_KB_WORKSPACES
    if _FOLDER_KB_WORKSPACES is not None:
        return _FOLDER_KB_WORKSPACES
    from app.services import folder_kb_service

    bases = folder_kb_service.scan_knowledge_bases()
    _FOLDER_KB_WORKSPACES = [
        {"name": b["name"], "workspace": _kb_name_to_workspace(b["name"])}
        for b in bases
    ]
    return _FOLDER_KB_WORKSPACES


# ── Driver management ──────────────────────────────────────────────────────

def _create_driver() -> AsyncDriver:
    return AsyncGraphDatabase.driver(
        settings.memgraph_uri,
        auth=(settings.memgraph_username, settings.memgraph_password),
        connection_timeout=5.0,
    )


async def get_driver() -> AsyncDriver:
    global _driver, _driver_failed, _driver_fail_ts
    if _driver_failed and (time.time() - _driver_fail_ts) < _DRIVER_RETRY_AFTER:
        raise ConnectionError("Memgraph unavailable (backoff)")
    if _driver is None:
        _driver = _create_driver()
    return _driver


async def close_driver():
    global _driver, _driver_verified, _driver_failed
    if _driver is not None:
        await _driver.close()
        _driver = None
        _driver_verified = False
        _driver_failed = False


def _mark_failed():
    global _driver_verified, _driver_failed, _driver_fail_ts
    _driver_failed = True
    _driver_fail_ts = time.time()
    _driver_verified = False


def _sanitize_label(label: str) -> str:
    """Sanitize a label for use in Cypher backtick quoting."""
    return label.replace("`", "``")


# ── Graph queries ───────────────────────────────────────────────────────────

def _build_node(name: str, deg: int, entity_type: str = "", description: str = "", kb_name: str = "") -> dict:
    """Build an ECharts node dict with visual + detail info.

    The extra fields (entityType, description, kbName, degree) are
    ignored by ECharts but available for the detail dialog.
    """
    if deg >= 5:
        cat, color = 0, "#00d4ff"
    elif deg >= 2:
        cat, color = 1, "#00ff88"
    else:
        cat, color = 2, "#ffaa00"
    size = min(60, max(16, 20 + deg * 5))
    return {
        "name": name,
        "symbolSize": size,
        "category": cat,
        "itemStyle": {"color": color},
        # Detail fields for the dialog
        "entityType": entity_type,
        "description": description,
        "kbName": kb_name,
        "degree": deg,
    }


def _build_link(src: str, tgt: str, rel_type: str = "", description: str = "") -> dict:
    """Build an ECharts link dict with optional description for the dialog."""
    link: dict[str, Any] = {"source": src, "target": tgt}
    if rel_type:
        link["relType"] = rel_type
    if description:
        link["description"] = description
    return link


async def get_graph_data(workspace: str, max_nodes: int = 200) -> dict[str, Any]:
    """Fetch nodes and relationships for a given workspace from Memgraph.

    LightRAG stores each workspace as a node Label (e.g. ``cai_ji_zi_yu``).
    Node properties: entity_id (display name), entity_type, description.
    Relationship type: DIRECTED, with description property.

    Returns a dict with ECharts-compatible ``nodes`` and ``links`` arrays,
    plus ``stats`` (entity_count, relation_count, coverage).
    """
    try:
        driver = await get_driver()
    except ConnectionError:
        raise

    label = _sanitize_label(workspace)

    try:
        async with driver.session() as session:
            # Gather nodes
            node_result = await session.run(
                f"MATCH (n:`{label}`) "
                "RETURN n.entity_id AS id, n.entity_id AS name, "
                "n.entity_type AS type, n.description AS desc, "
                "n.kb_name AS kb "
                "LIMIT $limit",
                limit=max_nodes,
            )
            raw_nodes = await node_result.data()
            await node_result.consume()

            # Gather relationships
            rel_result = await session.run(
                f"MATCH (a:`{label}`)-[r]->(b:`{label}`) "
                "RETURN a.entity_id AS src, b.entity_id AS tgt, "
                "type(r) AS rel_type, r.description AS desc "
                "LIMIT $limit",
                limit=max_nodes * 3,
            )
            raw_rels = await rel_result.data()
            await rel_result.consume()

            # Total counts
            count_result = await session.run(
                f"MATCH (n:`{label}`) RETURN count(n) AS cnt"
            )
            entity_count_rec = await count_result.single()
            await count_result.consume()
            entity_count = entity_count_rec["cnt"] if entity_count_rec else 0

            rel_count_result = await session.run(
                f"MATCH (a:`{label}`)-[r]->(b:`{label}`) RETURN count(r) AS cnt"
            )
            rel_count_rec = await rel_count_result.single()
            await rel_count_result.consume()
            relation_count = rel_count_rec["cnt"] if rel_count_rec else 0

    except Exception:
        _mark_failed()
        raise

    global _driver_verified
    _driver_verified = True

    # Build ECharts nodes — categorize by degree
    degree_map: dict[str, int] = {}
    for r in raw_rels:
        src, tgt = r.get("src", ""), r.get("tgt", "")
        degree_map[src] = degree_map.get(src, 0) + 1
        degree_map[tgt] = degree_map.get(tgt, 0) + 1

    node_ids = set()
    nodes: list[dict] = []
    for rn in raw_nodes:
        name = rn.get("name") or rn.get("id") or ""
        if not name or name in node_ids:
            continue
        node_ids.add(name)
        deg = degree_map.get(name, 0)
        nodes.append(_build_node(
            name=name,
            deg=deg,
            entity_type=(rn.get("type") or "").lower(),
            description=rn.get("desc", ""),
            kb_name=rn.get("kb", ""),
        ))

    # Build ECharts links
    links: list[dict] = []
    seen_links: set[tuple[str, str]] = set()
    for r in raw_rels:
        src = r.get("src", "")
        tgt = r.get("tgt", "")
        if not src or not tgt or (src, tgt) in seen_links:
            continue
        seen_links.add((src, tgt))
        links.append(_build_link(
            src=src, tgt=tgt,
            rel_type=r.get("rel_type", ""),
            description=r.get("desc", ""),
        ))

    # Coverage
    node_names = {n["name"] for n in nodes}
    linked = {r.get("src", "") for r in raw_rels} | {r.get("tgt", "") for r in raw_rels}
    coverage = round(len(linked & node_names) / max(len(node_names), 1) * 100, 1)

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "coverage": coverage,
        },
    }


async def get_graph_by_kb_name(kb_name: str, max_nodes: int = 200) -> dict[str, Any]:
    """Fetch nodes and relationships for a given KB name from Memgraph.

    LightRAG stores all entities under a few labels (base, cai_ji_zi_yu, etc.)
    but we add a `kb_name` property to partition them per folder KB.

    Returns a dict with ECharts-compatible ``nodes`` and ``links`` arrays,
    plus ``stats`` (entity_count, relation_count, coverage).
    """
    try:
        driver = await get_driver()
    except ConnectionError:
        raise

    try:
        async with driver.session() as session:
            # Gather nodes with this kb_name
            node_result = await session.run(
                "MATCH (n) WHERE n.kb_name = $kb_name "
                "RETURN n.entity_id AS id, n.entity_id AS name, "
                "n.entity_type AS type, n.description AS desc "
                "LIMIT $limit",
                kb_name=kb_name,
                limit=max_nodes,
            )
            raw_nodes = await node_result.data()
            await node_result.consume()

            # Gather relationships between nodes of this kb_name
            rel_result = await session.run(
                "MATCH (a)-[r]->(b) WHERE a.kb_name = $kb_name AND b.kb_name = $kb_name "
                "RETURN a.entity_id AS src, b.entity_id AS tgt, "
                "type(r) AS rel_type, r.description AS desc "
                "LIMIT $limit",
                kb_name=kb_name,
                limit=max_nodes * 3,
            )
            raw_rels = await rel_result.data()
            await rel_result.consume()

            # Total count
            count_result = await session.run(
                "MATCH (n) WHERE n.kb_name = $kb_name RETURN count(n) AS cnt",
                kb_name=kb_name,
            )
            entity_count_rec = await count_result.single()
            await count_result.consume()
            entity_count = entity_count_rec["cnt"] if entity_count_rec else 0

            rel_count_result = await session.run(
                "MATCH (a)-[r]->(b) WHERE a.kb_name = $kb_name AND b.kb_name = $kb_name "
                "RETURN count(r) AS cnt",
                kb_name=kb_name,
            )
            rel_count_rec = await rel_count_result.single()
            await rel_count_result.consume()
            relation_count = rel_count_rec["cnt"] if rel_count_rec else 0

    except Exception:
        _mark_failed()
        raise

    global _driver_verified
    _driver_verified = True

    # Build ECharts nodes
    degree_map: dict[str, int] = {}
    for r in raw_rels:
        src, tgt = r.get("src", ""), r.get("tgt", "")
        degree_map[src] = degree_map.get(src, 0) + 1
        degree_map[tgt] = degree_map.get(tgt, 0) + 1

    node_ids = set()
    nodes: list[dict] = []
    for rn in raw_nodes:
        name = rn.get("name") or rn.get("id") or ""
        if not name or name in node_ids:
            continue
        node_ids.add(name)
        deg = degree_map.get(name, 0)
        nodes.append(_build_node(
            name=name,
            deg=deg,
            entity_type=(rn.get("type") or "").lower(),
            description=rn.get("desc", ""),
            kb_name=rn.get("kb", ""),
        ))

    # Build ECharts links
    links: list[dict] = []
    seen_links: set[tuple[str, str]] = set()
    for r in raw_rels:
        src = r.get("src", "")
        tgt = r.get("tgt", "")
        if not src or not tgt or (src, tgt) in seen_links:
            continue
        seen_links.add((src, tgt))
        links.append(_build_link(
            src=src, tgt=tgt,
            rel_type=r.get("rel_type", ""),
            description=r.get("desc", ""),
        ))

    node_names = {n["name"] for n in nodes}
    linked = {r.get("src", "") for r in raw_rels} | {r.get("tgt", "") for r in raw_rels}
    coverage = round(len(linked & node_names) / max(len(node_names), 1) * 100, 1)

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "coverage": coverage,
        },
    }


async def get_all_workspaces_graph(max_nodes_per_ws: int = 80) -> dict[str, Any]:
    """Merge graphs from all folder KB workspaces into a single combined graph.

    Adds a root node per knowledge base and links KB roots to their
    top entities. Returns ECharts-compatible data.
    """
    combined_nodes_map: dict[str, dict] = {}
    combined_links: list[dict] = []
    seen_edges: set[str] = set()
    total_entity_count = 0
    total_rel_count = 0

    ws_list = get_folder_kb_workspaces()

    # Also include the default workspace (labeled 'base' or by old ws name)
    all_kbs = [{"name": ws_info["name"]} for ws_info in ws_list]

    # Get distinct kb_names actually in Memgraph
    try:
        driver = await get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (n) WHERE n.kb_name IS NOT NULL RETURN DISTINCT n.kb_name AS kb"
            )
            records = await result.data()
            await result.consume()
        memgraph_kb_names = {r["kb"] for r in records}
    except Exception:
        memgraph_kb_names = set()

    # Combine: scan all KB names from both sources
    all_kb_names = set()
    for kb_info in all_kbs:
        all_kb_names.add(kb_info["name"])
    all_kb_names.update(memgraph_kb_names)

    for kb_name in sorted(all_kb_names):
        try:
            graph_data = await get_graph_by_kb_name(kb_name=kb_name, max_nodes=max_nodes_per_ws)
        except Exception:
            continue

        nodes = graph_data.get("nodes", [])
        links = graph_data.get("links", [])
        stats = graph_data.get("stats", {})

        if not nodes:
            continue

        # Add KB root node
        combined_nodes_map[kb_name] = {
            "name": kb_name,
            "symbolSize": 45,
            "category": 0,
            "itemStyle": {"color": "#ffaa00"},
        }

        # Add all entity nodes
        for node in nodes:
            nname = node["name"]
            if nname not in combined_nodes_map:
                combined_nodes_map[nname] = node

        # Link KB root to top-degree entities
        for node in sorted(nodes, key=lambda n: n.get("symbolSize", 16), reverse=True)[:5]:
            key = f"{kb_name}|{node['name']}"
            if key not in seen_edges:
                seen_edges.add(key)
                combined_links.append({"source": kb_name, "target": node["name"], "relType": "BELONGS_TO", "description": f"{node['name']} 属于 {kb_name}"})

        # Add intra-KB links
        for link in links:
            key = f"{link['source']}|{link['target']}"
            if key not in seen_edges:
                seen_edges.add(key)
                combined_links.append(link)

        total_entity_count += stats.get("entity_count", 0)
        total_rel_count += stats.get("relation_count", 0)

    # Build final output
    node_list = list(combined_nodes_map.values())
    node_names = {n["name"] for n in node_list}
    link_list = [l for l in combined_links if l["source"] in node_names and l["target"] in node_names]
    coverage = round(min(95, len(node_list) * 0.4 + 30), 1) if node_list else 0

    return {
        "nodes": node_list,
        "links": link_list,
        "stats": {
            "entity_count": total_entity_count,
            "relation_count": total_rel_count,
            "coverage": coverage,
        },
    }


async def get_total_entity_count() -> int:
    """Return the total count of entities across all KBs in Memgraph.

    Counts all nodes that have a kb_name property.
    """
    try:
        driver = await get_driver()
    except ConnectionError:
        raise

    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (n) WHERE n.kb_name IS NOT NULL RETURN count(n) AS cnt"
            )
            rec = await result.single()
            await result.consume()
            return rec["cnt"] if rec else 0
    except Exception:
        _mark_failed()
        raise


async def get_total_relation_count() -> int:
    """Return the total count of relationships across all KBs in Memgraph."""
    try:
        driver = await get_driver()
    except ConnectionError:
        raise

    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (a)-[r]->(b) WHERE a.kb_name IS NOT NULL AND b.kb_name IS NOT NULL "
                "RETURN count(r) AS cnt"
            )
            rec = await result.single()
            await result.consume()
            return rec["cnt"] if rec else 0
    except Exception:
        _mark_failed()
        raise


async def get_all_kb_stats() -> list[dict]:
    """Return per-KB stats (entity_count, relation_count) from Memgraph."""
    try:
        driver = await get_driver()
    except ConnectionError:
        raise

    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (n) WHERE n.kb_name IS NOT NULL "
                "RETURN n.kb_name AS kb, count(n) AS entity_count "
                "ORDER BY entity_count DESC"
            )
            kb_entity_counts = await result.data()
            await result.consume()

            rel_result = await session.run(
                "MATCH (a)-[r]->(b) WHERE a.kb_name IS NOT NULL AND b.kb_name IS NOT NULL "
                "RETURN a.kb_name AS kb, count(r) AS relation_count "
                "ORDER BY relation_count DESC"
            )
            kb_rel_counts = await rel_result.data()
            await rel_result.consume()

        rel_map = {r["kb"]: r["relation_count"] for r in kb_rel_counts}
        return [
            {
                "kb_name": r["kb"],
                "entity_count": r["entity_count"],
                "relation_count": rel_map.get(r["kb"], 0),
            }
            for r in kb_entity_counts
        ]
    except Exception:
        _mark_failed()
        raise


async def get_workspace_labels() -> list[str]:
    """Return all workspace labels that exist in Memgraph.

    Uses Memgraph-compatible syntax (not CALL db.labels()).
    """
    driver = await get_driver()
    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (n) RETURN DISTINCT labels(n) AS lbls"
            )
            records = await result.data()
            await result.consume()
    except Exception:
        _mark_failed()
        raise

    labels = set()
    for r in records:
        for lbl in r.get("lbls", []):
            labels.add(lbl)
    return sorted(labels)


# ── Auto-tagging utility ───────────────────────────────────────────────────

def tag_untagged_nodes() -> int:
    """Synchronous utility: find Memgraph nodes without kb_name and tag them.

    Uses the folder KB file list to match filenames in node.file_path
    to the owning KB name. Called at startup and can be called periodically.

    Returns the number of nodes tagged.
    """
    from neo4j import GraphDatabase as _GD

    # Build filename → kb_name mapping
    from app.services import folder_kb_service
    import re as _re

    filename_to_kb: dict[str, str] = {}
    bases = folder_kb_service.scan_knowledge_bases()
    for b in bases:
        all_files = folder_kb_service.scan_kb_files(b["name"], page=1, page_size=9999)
        for f in all_files["items"]:
            filename_to_kb[f["file_name"]] = b["name"]

    try:
        driver = _GD.driver(
            settings.memgraph_uri,
            auth=(settings.memgraph_username, settings.memgraph_password),
            connection_timeout=5,
        )
    except Exception:
        return 0

    try:
        with driver.session() as session:
            # Find base nodes without kb_name
            result = session.run(
                "MATCH (n) WHERE n.kb_name IS NULL AND n.file_path IS NOT NULL "
                "RETURN id(n) AS nid, n.file_path AS fp LIMIT 1000"
            )
            nodes = list(result)

            if not nodes:
                driver.close()
                return 0

            updated = 0
            for node in nodes:
                nid = node["nid"]
                fp = node["fp"]
                first_file = fp.split("<SEP>")[0].strip()

                kb = filename_to_kb.get(first_file)
                if not kb:
                    for fname, kbname in filename_to_kb.items():
                        if fname in fp:
                            kb = kbname
                            break

                if kb:
                    session.run(
                        "MATCH (n) WHERE id(n) = $nid SET n.kb_name = $kb_name",
                        nid=nid, kb_name=kb,
                    )
                    updated += 1

            return updated
    except Exception:
        return 0
    finally:
        driver.close()
