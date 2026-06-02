"""Memgraph service — query knowledge graph data from Memgraph."""

import os
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from app.core.config import settings


_driver: AsyncDriver | None = None


async def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.memgraph_uri,
            auth=(settings.memgraph_username, settings.memgraph_password),
        )
    return _driver


async def close_driver():
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


def _sanitize_workspace(workspace: str) -> str:
    """Sanitize workspace name for use as a Cypher label identifier."""
    return workspace.replace("`", "``")


async def get_graph_data(workspace: str, max_nodes: int = 200) -> dict[str, Any]:
    """Fetch nodes and relationships for a given workspace from Memgraph.

    Returns a dict with echarts-compatible ``nodes`` and ``links`` arrays,
    plus ``stats`` (entity_count, relation_count, coverage).
    """
    driver = await get_driver()
    label = _sanitize_workspace(workspace)

    async with driver.session(database=settings.memgraph_database) as session:
        # --- gather nodes ---
        node_result = await session.run(
            f"MATCH (n:`{label}`) "
            "RETURN n.entity_id AS id, n.entity_name AS name, "
            "n.entity_type AS type, n.description AS desc "
            "LIMIT $limit",
            limit=max_nodes,
        )
        raw_nodes = await node_result.data()
        await node_result.consume()

        # --- gather relationships ---
        rel_result = await session.run(
            f"MATCH (a:`{label}`)-[r]->(b:`{label}`) "
            "RETURN a.entity_id AS src, b.entity_id AS tgt, "
            "type(r) AS rel_type, r.description AS desc "
            "LIMIT $limit",
            limit=max_nodes * 3,
        )
        raw_rels = await rel_result.data()
        await rel_result.consume()

        # --- counts ---
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

    # Build id→name lookup
    id_to_name: dict[str, str] = {}
    for rn in raw_nodes:
        nid = rn.get("id") or rn.get("name") or ""
        name = rn.get("name") or rn.get("id") or ""
        id_to_name[nid] = name

    # Build echarts nodes — size by degree approximation
    node_ids = set()
    degree_map: dict[str, int] = {}
    for r in raw_rels:
        src, tgt = r.get("src", ""), r.get("tgt", "")
        degree_map[src] = degree_map.get(src, 0) + 1
        degree_map[tgt] = degree_map.get(tgt, 0) + 1

    nodes: list[dict] = []
    for rn in raw_nodes:
        nid = rn.get("id") or rn.get("name") or ""
        name = rn.get("name") or rn.get("id") or ""
        if not nid or nid in node_ids:
            continue
        node_ids.add(nid)
        deg = degree_map.get(nid, 0)
        # Categorize by degree
        if deg >= 5:
            cat = 0
            color = "#00d4ff"
        elif deg >= 2:
            cat = 1
            color = "#00ff88"
        else:
            cat = 2
            color = "#ffaa00"
        size = min(60, max(16, 20 + deg * 5))
        nodes.append({
            "name": name,
            "symbolSize": size,
            "category": cat,
            "itemStyle": {"color": color},
        })

    # Build echarts links
    links: list[dict] = []
    seen_links: set[tuple[str, str]] = set()
    for r in raw_rels:
        src_name = id_to_name.get(r.get("src", ""), r.get("src", ""))
        tgt_name = id_to_name.get(r.get("tgt", ""), r.get("tgt", ""))
        if (src_name, tgt_name) in seen_links:
            continue
        if not src_name or not tgt_name:
            continue
        seen_links.add((src_name, tgt_name))
        links.append({"source": src_name, "target": tgt_name})

    # Coverage: rough approximation — ratio of nodes with ≥1 relationship
    linked_nodes = {r.get("src", "") for r in raw_rels} | {r.get("tgt", "") for r in raw_rels}
    coverage = round(len(linked_nodes & node_ids) / max(len(node_ids), 1) * 100, 1)

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "coverage": coverage,
        },
    }


async def get_graph_labels() -> list[str]:
    """Return all workspace labels that exist in Memgraph."""
    driver = await get_driver()
    async with driver.session(database=settings.memgraph_database) as session:
        result = await session.run("CALL db.labels()")
        records = await result.data()
        await result.consume()
    return [r["label"] for r in records]
