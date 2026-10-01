"""Neo4j graph database driver, warm dictionary, and graph term lookup."""

import re
import time
import logging
from typing import Dict, List, Optional, Set

from config import NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DICT_REFRESH_SEC, NEO4J_DICT_LIMIT, logger


def _redact_url(url: object) -> str:
    """Return *url* with userinfo (``user:password@``) removed, for logging.

    Same contract as ``services/common/nats_client.py::_redact_url``; kept
    module-local so this file needs no cross-service import. Also handles
    comma-separated server lists (``nats://u:p@a:4222,nats://u:p@b:4222``).
    """
    import re

    return re.sub(r"(?<=://)[^@/\s]+@", "", str(url))


# Lazy/optional Neo4j: allow running without the neo4j service
driver = None
if NEO4J_URL:
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception:
        logging.getLogger("hirag.gateway.v2").warning(
            "Neo4j unavailable at %s; graph features disabled", _redact_url(NEO4J_URL)
        )
        driver = None

_warm_entities: Dict[str, set] = {}
_warm_last = 0.0


def refresh_warm_dictionary():
    global _warm_entities, _warm_last
    if driver is None:
        _warm_entities = {}
        _warm_last = time.time()
        return
    try:
        tmp: Dict[str, set] = {}
        with driver.session() as s:
            # Avoid Neo4j "UnknownLabelWarning" when the graph hasn't been seeded yet.
            count_result = s.run(
                "MATCH (e) WHERE 'Entity' IN labels(e) RETURN count(e) AS cnt"
            ).single()
            if not count_result or not count_result["cnt"]:
                _warm_entities = {}
                _warm_last = time.time()
                return
            recs = s.run(
                (
                    "MATCH (e) WHERE 'Entity' IN labels(e) "
                    "WITH e, CASE WHEN 'type' IN keys(e) THEN e.type ELSE 'UNK' END AS typ "
                    "RETURN e.value AS v, typ AS t "
                    "LIMIT $lim"
                ),
                lim=NEO4J_DICT_LIMIT,
            )
            for r in recs:
                v = r["v"]
                t = (r["t"] or "UNK").upper()
                if not v:
                    continue
                tmp.setdefault(t, set()).add(v)
        _warm_entities = tmp
        _warm_last = time.time()
    except Exception:
        logger.exception("warm dictionary error")


def warm_loop():
    while True:
        try:
            refresh_warm_dictionary()
        except Exception:
            logger.exception("warm loop error")
        time.sleep(max(15, NEO4J_DICT_REFRESH_SEC))


import threading as _t
if driver is not None:
    _t.Thread(target=warm_loop, daemon=True).start()


def graph_terms(query: str, limit: int = 8, entity_types: Optional[List[str]] = None):
    toks = [t.lower() for t in re.split(r"\W+", query) if t and len(t) > 2]
    if not toks: return []
    types_norm = (
        {x.strip().upper() for x in (entity_types or []) if isinstance(x, str) and x.strip()}
        if entity_types
        else None
    )
    out: Set[str] = set()
    for tname, values in _warm_entities.items():
        if types_norm and tname not in types_norm:
            continue
        for val in values:
            lv = val.lower()
            if any(tok in lv for tok in toks):
                out.add(val)
                if len(out) >= limit:
                    return list(out)[:limit]
    return list(out)[:limit]
