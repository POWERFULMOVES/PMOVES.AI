import asyncio
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Mapping, Optional, Tuple

import requests

from eval_utils import evaluate_thresholds
from evaluate import evaluate_dataset
from services.common.events import envelope

logger = logging.getLogger("pmoves.retrieval_eval.publish_gate")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
SUPA_REST_URL = os.environ.get("SUPA_REST_URL", "http://postgrest:3000")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
DEFAULT_TIMEOUT = float(os.environ.get("RETRIEVAL_EVAL_GATE_TIMEOUT", "30"))
DEFAULT_K = int(os.environ.get("RETRIEVAL_EVAL_GATE_K", "10"))
DEFAULT_INCLUDE_HITS = os.environ.get("RETRIEVAL_EVAL_GATE_INCLUDE_HITS", "false").lower() == "true"
DEFAULT_QUERY_DETAILS = os.environ.get("RETRIEVAL_EVAL_GATE_QUERY_DETAILS", "false").lower() != "false"

BASE_DATASET_DIR = Path(__file__).resolve().parents[2] / "datasets"

PERSONA_DATASETS: Dict[str, Dict[str, Any]] = {
    "Archon@1.0": {
        "dataset_id": "archon-smoke-10",
        "queries_path": "personas/archon-smoke-10.jsonl",
        "thresholds": {
            "mrr": {"min": 0.80},
            "ndcg": {"min": 0.75},
        },
    }
}


def _resolve_dataset_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    if path.startswith("pmoves/"):
        return Path(__file__).resolve().parents[2] / path.split("pmoves/", 1)[1]
    return (BASE_DATASET_DIR / path).resolve()


def _merge_dataset_config(
    persona_key: str, payload_dataset: Mapping[str, Any] | None
) -> Dict[str, Any]:
    base = PERSONA_DATASETS.get(persona_key, {}).copy()
    payload_dataset = dict(payload_dataset or {})
    for key, value in payload_dataset.items():
        base[key] = value
    return base


def _build_args(dataset_cfg: Mapping[str, Any], label: str) -> SimpleNamespace:
    queries_path = _resolve_dataset_path(str(dataset_cfg.get("queries_path")))
    suites_path = dataset_cfg.get("suites_path")
    if suites_path:
        suites_path = _resolve_dataset_path(str(suites_path))
    return SimpleNamespace(
        queries=str(queries_path),
        k=int(dataset_cfg.get("k") or DEFAULT_K),
        hirag_url=dataset_cfg.get("hirag_url") or os.environ.get(
            "HIRAG_URL", "http://hi-rag-gateway-v2:8086"
        ),
        timeout=float(dataset_cfg.get("timeout") or DEFAULT_TIMEOUT),
        suites=str(suites_path) if suites_path else None,
        output=None,
        csv=False,
        csv_path=None,
        label=label,
        include_hits=bool(dataset_cfg.get("include_hits", DEFAULT_INCLUDE_HITS)),
        no_query_details=bool(
            dataset_cfg.get("no_query_details", DEFAULT_QUERY_DETAILS)
        ),
    )


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if SERVICE_KEY:
        headers["apikey"] = SERVICE_KEY
        headers["Authorization"] = f"Bearer {SERVICE_KEY}"
    return headers


def _resolve_persona_id(persona_id: Optional[str], persona: Mapping[str, Any]) -> Optional[str]:
    if persona_id:
        return persona_id
    if not SUPA_REST_URL:
        return None
    name = persona.get("name")
    version = persona.get("version")
    if not name or not version:
        return None
    try:
        resp = requests.get(
            f"{SUPA_REST_URL}/pmoves_core.personas",
            params={
                "name": f"eq.{name}",
                "version": f"eq.{version}",
                "select": "persona_id",
                "limit": 1,
            },
            headers=_headers(),
            timeout=10,
        )
        if resp.ok:
            rows = resp.json() or []
            if rows:
                return rows[0].get("persona_id")
    except Exception:
        logger.exception("Failed to resolve persona id via PostgREST", extra={"name": name, "version": version})
    return None


def _persist_thresholds(
    persona_id: Optional[str],
    dataset_id: str,
    last_run: str,
    evaluations: Mapping[str, Mapping[str, Any]],
    thresholds: Mapping[str, Mapping[str, Any]],
) -> None:
    if not persona_id:
        logger.warning("Skipping gate persistence due to missing persona_id", extra={"dataset_id": dataset_id})
        return
    if not SUPA_REST_URL:
        logger.warning("SUPA_REST_URL unset; cannot persist persona eval gate", extra={"dataset_id": dataset_id})
        return
    rows = []
    for metric, evaluation in evaluations.items():
        th_config = thresholds.get(metric) or {}
        threshold_value = th_config.get("min")
        if threshold_value is None:
            continue
        rows.append(
            {
                "persona_id": persona_id,
                "dataset_id": dataset_id,
                "metric": metric,
                "threshold": float(threshold_value),
                "last_run": last_run,
                "pass": bool(evaluation.get("passed")),
            }
        )
    if not rows:
        return
    try:
        resp = requests.post(
            f"{SUPA_REST_URL}/pmoves_core.persona_eval_gates",
            data=json.dumps(rows),
            headers={**_headers(), "Prefer": "resolution=merge-duplicates"},
            timeout=10,
        )
        if not resp.ok:
            logger.error(
                "Failed to persist persona eval gates", extra={"status": resp.status_code, "body": resp.text}
            )
    except Exception:
        logger.exception("Exception persisting persona eval gates", extra={"rows": rows})


def _evaluate(dataset_cfg: Mapping[str, Any], label: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    args = _build_args(dataset_cfg, label)
    output, _ = evaluate_dataset(args)
    overall_metrics = output.get("overall", {}).get("metrics", {})
    return output, overall_metrics


def _flatten_thresholds(thresholds: Mapping[str, Mapping[str, Any]] | None) -> Dict[str, float]:
    flat: Dict[str, float] = {}
    for metric, cfg in (thresholds or {}).items():
        value = cfg.get("min")
        if value is not None:
            flat[metric] = float(value)
    return flat


def _build_persona_key(persona: Mapping[str, Any]) -> str:
    return f"{persona.get('name')}@{persona.get('version')}"


async def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
    from nats.aio.client import Client as NATS

    nc = NATS()
    await nc.connect(servers=[NATS_URL])

    async def handler(msg):  # type: ignore[no-redef]
        try:
            env = json.loads(msg.data.decode())
        except Exception:
            logger.exception("Failed to decode persona publish event payload")
            return
        payload = env.get("payload") or {}
        persona = payload.get("persona") or {}
        dataset_cfg = _merge_dataset_config(_build_persona_key(persona), payload.get("dataset"))
        dataset_id = dataset_cfg.get("dataset_id") or dataset_cfg.get("id")
        if not dataset_id:
            logger.error("persona.publish.request missing dataset id", extra={"payload": payload})
            return
        persona_id = _resolve_persona_id(payload.get("persona_id"), persona)
        if not persona_id:
            logger.error(
                "Missing persona identifier for publish gate",
                extra={"persona": persona, "dataset_id": dataset_id},
            )
            return
        label = f"{_build_persona_key(persona)}:{dataset_id}"

        loop = asyncio.get_running_loop()
        try:
            output, metrics = await loop.run_in_executor(None, _evaluate, dataset_cfg, label)
        except Exception:
            logger.exception("Retrieval evaluation failed", extra={"persona": persona, "dataset_id": dataset_id})
            return

        thresholds = dataset_cfg.get("thresholds", {})
        passed, evaluations = evaluate_thresholds(metrics, thresholds)
        _persist_thresholds(persona_id, dataset_id, output.get("generated_at"), evaluations, thresholds)

        event_payload = {
            "persona_id": persona_id,
            "name": persona.get("name"),
            "version": persona.get("version"),
            "dataset_id": dataset_id,
            "metrics": {k: float(v) for k, v in metrics.items()},
            "thresholds": _flatten_thresholds(thresholds),
            "generated_at": output.get("generated_at"),
            "evaluations": evaluations,
            "passed": passed,
            "correlation_id": payload.get("correlation_id") or env.get("correlation_id"),
        }
        topic = "persona.published.v1" if passed else "persona.publish.failed.v1"
        if not passed:
            logger.warning(
                "Persona publish gate failed", extra={"persona": persona, "dataset_id": dataset_id, "evaluations": evaluations}
            )
        evt = envelope(topic, event_payload, correlation_id=env.get("correlation_id"), parent_id=env.get("id"), source="retrieval-eval")
        await nc.publish(topic, json.dumps(evt).encode())
        logger.info(
            "Persona publish evaluation complete", extra={"persona": persona, "dataset_id": dataset_id, "passed": passed}
        )

    await nc.subscribe("persona.publish.request.v1", cb=handler)
    logger.info("Retrieval-eval persona gate listening", extra={"topic": "persona.publish.request.v1"})
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
