"""Neo4j client with connection pooling, query execution, and migration support.

Preserves the exact Cypher queries from the original linker.py while adding
proper driver lifecycle management, connection pooling, and error handling.

CHIT signing is available when CHIT_SIGN_NEO4J=true — see chit_signer.py.
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Any, Optional

import structlog
from neo4j import GraphDatabase, Driver, ManagedTransaction
from neo4j.exceptions import ServiceUnavailable, AuthError, Neo4jError

from config import Settings

# CHIT signing — additive, gated by env var
from chit_signer import sign_neo4j_node, CHIT_SIGN_NEO4J

logger = structlog.get_logger(__name__)


class Neo4jClient:
    """""""""Manages Neo4j driver lifecycle, connection pooling, and query execution."""""""""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._driver: Optional[Driver] = None

    # -- Lifecycle --------------------------------------------------------

    async def connect(self) -> None:
        """""""""Initialize the Neo4j driver with connection pooling."""""""""
        try:
            self._driver = GraphDatabase.driver(
                self._settings.neo4j_url,
                auth=(self._settings.neo4j_user, self._settings.neo4j_password),
                max_connection_pool_size=self._settings.neo4j_max_connection_pool_size,
                connection_timeout=self._settings.neo4j_connection_timeout,
                max_transaction_retry_time=self._settings.neo4j_max_transaction_retry_time,
            )
            self._driver.verify_connectivity()
            logger.info(
                "neo4j.connected",
                url=self._settings.neo4j_url,
                database=self._settings.neo4j_database,
            )
        except AuthError as exc:
            logger.error("neo4j.auth_failed", error=str(exc))
            raise
        except ServiceUnavailable as exc:
            logger.error("neo4j.unavailable", url=self._settings.neo4j_url, error=str(exc))
            raise

    async def close(self) -> None:
        """""""""Close the Neo4j driver and all connections."""""""""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("neo4j.closed")

    @property
    def driver(self) -> Driver:
        """""""""Return the active driver or raise if not connected."""""""""
        if self._driver is None:
            raise RuntimeError("Neo4j driver not initialized")
        return self._driver

    # -- Health -----------------------------------------------------------

    def is_healthy(self) -> bool:
        """""""""Check if Neo4j connection is alive."""""""""
        if self._driver is None:
            return False
        try:
            self._driver.verify_connectivity()
            return True
        except (ServiceUnavailable, Neo4jError):
            return False

    # -- Migrations -------------------------------------------------------

    def apply_migrations(self) -> None:
        """""""""Apply Cypher migration files from the configured migrations directory."""""""""
        migrations_dir = self._settings.migrations_dir
        if not Path(migrations_dir).is_dir():
            logger.warning("migrations.dir_missing", path=migrations_dir)
            return

        files = sorted(glob.glob(str(Path(migrations_dir) / "*.cypher")))
        if not files:
            logger.info("migrations.no_files", path=migrations_dir)
            return

        with self._driver.session(database=self._settings.neo4j_database) as session:
            for filepath in files:
                with open(filepath, "r", encoding="utf-8") as fh:
                    cypher = fh.read()
                for stmt in (s.strip() for s in cypher.split(";") if s.strip()):
                    try:
                        session.run(stmt)
                        logger.info("migration.applied", file=filepath)
                    except Neo4jError as exc:
                        logger.error("migration.failed", file=filepath, error=str(exc))
                        raise

        logger.info("migrations.complete", count=len(files))

    # -- Query execution -------------------------------------------------

    def execute_write(
        self,
        cypher: str,
        parameters: Optional[dict[str, Any]] = None,
    ) -> None:
        """""""""Execute a write query against Neo4j with proper parameterization.

        When CHIT_SIGN_NEO4J is enabled, parameters are signed before writing.
        """""""""
        parameters = parameters or {}

        # CHIT signing — additive, gated by CHIT_SIGN_NEO4J env var
        if CHIT_SIGN_NEO4J:
            parameters = sign_neo4j_node(parameters)
            logger.debug("neo4j.chit_signed", cypher_preview=cypher[:80])

        try:
            with self._driver.session(database=self._settings.neo4j_database) as session:
                session.execute_write(self._run_tx, cypher, parameters)
        except Neo4jError as exc:
            logger.error(
                "neo4j.query_failed",
                cypher_preview=cypher[:120],
                error=str(exc),
            )
            raise

    @staticmethod
    def _run_tx(
        tx: ManagedTransaction,
        cypher: str,
        parameters: dict[str, Any],
    ) -> None:
        """""""""Run a single write transaction."""""""""
        tx.run(cypher, **parameters)

    # -- Handler methods (preserve exact Cypher from linker.py) -----------

    def handle_gen_image_result(self, msg) -> None:
        """""""""Persist image generation result to Neo4j."""""""""
        if not msg.uri:
            logger.debug("gen_image_result.no_uri", evt_id=msg.evt_id)
            return

        CYPHER = """
        MERGE (a:Asset:Image {uri:$uri})
          ON CREATE SET a.created_at = datetime($ts)
        SET a.bucket=$bucket, a.key=$key, a.public_url=$public_url,
            a.presigned_url=$presigned_url, a.updated_at = datetime($ts)
        MERGE (w:Workflow {name:'comfyui', kind:'image'})
        MERGE (g:Generation {id:$evt_id})
          ON CREATE SET g.ts = datetime($ts), g.source=$source
          ON MATCH SET  g.ts = datetime($ts), g.source=$source
        MERGE (ag:Agent {name:$source})
        MERGE (ag)-[:EMITTED]->(g)
        MERGE (g)-[:PRODUCED]->(a)
        MERGE (g)-[:USED_WORKFLOW]->(w)
        """
        self.execute_write(CYPHER, {
            "uri": msg.uri,
            "bucket": msg.bucket,
            "key": msg.key,
            "public_url": msg.public_url,
            "presigned_url": msg.presigned_url,
            "evt_id": msg.evt_id,
            "ts": msg.ts,
            "source": msg.source,
        })
        logger.info("gen_image_result.stored", uri=msg.uri, evt_id=msg.evt_id)

    def handle_analysis_topics_result(self, msg) -> None:
        """""""""Persist topic analysis result to Neo4j."""""""""
        CYPHER_MEDIA = (
            "MERGE (m:Media {id:$id}) ON CREATE SET m.created_at=datetime($ts)"
        )
        CYPHER_TOPIC = """
        MERGE (t:Topic {label:$label})
          ON CREATE SET t.created_at = datetime($ts)
        SET t.last_score = $score, t.updated_at = datetime($ts)
        MERGE (m:Media {id:$mid})
        MERGE (m)-[:HAS_TOPIC {score:$score}]->(t)
        """
        self.execute_write(CYPHER_MEDIA, {"id": msg.media_id, "ts": msg.ts})
        for topic in msg.topics:
            self.execute_write(CYPHER_TOPIC, {
                "label": topic.label,
                "score": topic.score,
                "mid": msg.media_id,
                "ts": msg.ts,
            })
        logger.info(
            "analysis_topics.stored",
            media_id=msg.media_id,
            topic_count=len(msg.topics),
        )

    def handle_kb_upsert_request(self, msg) -> None:
        """""""""Persist knowledge-base upsert to Neo4j."""""""""
        CYPHER = """
        MERGE (ns:Namespace {name:$ns})
        WITH ns
        UNWIND $items AS it
          MERGE (k:KBItem {id:it.id})
            ON CREATE SET k.created_at = datetime($ts)
          SET k.text = it.text, k.metadata = it.metadata, k.updated_at = datetime($ts)
          MERGE (ns)-[:CONTAINS]->(k)
        """
        items = [
            {"id": x.id, "text": x.text, "metadata": x.metadata}
            for x in msg.items
        ]
        self.execute_write(CYPHER, {
            "ns": msg.namespace,
            "items": items,
            "ts": msg.ts,
        })
        logger.info(
            "kb_upsert.stored",
            namespace=msg.namespace,
            item_count=len(items),
        )
