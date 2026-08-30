"""
Token Stub Service
==================
Dry-run attestation recorder for work.attested.v1 payloads.

Activation-pack improvements:
  (a) JSONL evidence log at /data/evidence.jsonl
  (b) Rollback plan included in every response
  (c) TOKEN_STUB_ENABLED=false returns 503

Records attestations to Supabase work_attestations table.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError, field_validator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOKEN_STUB_ENABLED = os.getenv("TOKEN_STUB_ENABLED", "true").lower() == "true"
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://supabase:8000")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
EVIDENCE_LOG = os.getenv("EVIDENCE_LOG", "/data/evidence.jsonl")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("token-stub")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = [
    "work_id",
    "contributor",
    "attestation_sig",
    "attested_at",
    "merkle_root",
]


class AttestationPayload(BaseModel):
    work_id: str
    contributor: str
    attestation_sig: str
    attested_at: str
    merkle_root: str
    extra: Optional[Dict[str, Any]] = None

    @field_validator("work_id", "contributor", "attestation_sig", "attested_at", "merkle_root")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("field must not be empty")
        return v.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_evidence(record: Dict[str, Any]) -> None:
    """Append a JSONL evidence line (fail-open)."""
    try:
        os.makedirs(os.path.dirname(EVIDENCE_LOG), exist_ok=True)
        with open(EVIDENCE_LOG, "a") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
        log.debug("evidence written for work_id=%s", record.get("work_id"))
    except Exception as exc:
        log.warning("write_evidence failed: %s", exc)


def build_rollback_plan(work_id: str) -> list[str]:
    return [
        f"DELETE FROM work_attestations WHERE work_id='{work_id}';",
        f"Remove evidence lines for work_id={work_id} from {EVIDENCE_LOG}",
        "Publish work.attestation.revoked.v1 to NATS",
        "Notify audit log of rollback",
    ]


async def record_to_supabase(payload: AttestationPayload) -> bool:
    """Insert attestation into Supabase work_attestations (fail-open)."""
    try:
        headers = {
            "Content-Type": "application/json",
        }
        if SUPABASE_KEY:
            headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
        body = {
            "work_id": payload.work_id,
            "contributor": payload.contributor,
            "attestation_sig": payload.attestation_sig,
            "attested_at": payload.attested_at,
            "merkle_root": payload.merkle_root,
            "recorded_at": _now_iso(),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/work_attestations",
                headers=headers,
                json=body,
            )
            if resp.status_code >= 400:
                log.warning("supabase insert returned %d: %s", resp.status_code, resp.text)
                return False
            return True
    except Exception as exc:
        log.warning("record_to_supabase failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(title="PMOVES Token Stub", version="1.0.0-dryrun")


@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "enabled": TOKEN_STUB_ENABLED,
        "evidence_log": EVIDENCE_LOG,
        "supabase_configured": bool(SUPABASE_URL),
    }


@app.post("/api/v1/attest")
async def attest(payload: dict):
    if not TOKEN_STUB_ENABLED:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "token_stub_disabled",
                "message": "TOKEN_STUB_ENABLED is false",
            },
        )

    # Validate required fields
    missing = [f for f in REQUIRED_FIELDS if not payload.get(f)]
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "missing_fields": missing,
            },
        )

    try:
        att = AttestationPayload(**payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    record = {
        "work_id": att.work_id,
        "contributor": att.contributor,
        "attestation_sig": att.attestation_sig,
        "attested_at": att.attested_at,
        "merkle_root": att.merkle_root,
        "recorded_at": _now_iso(),
        "dry_run": True,
    }

    # (a) JSONL evidence log
    write_evidence(record)

    # Supabase recording (fail-open)
    recorded = await record_to_supabase(att)
    if not recorded:
        log.warning("attestation for %s not persisted (dry-run or supabase unavailable)", att.work_id)

    # (b) Rollback plan in every response
    rollback = build_rollback_plan(att.work_id)

    return {
        "status": "recorded",
        "dry_run": True,
        "work_id": att.work_id,
        "recorded_at": record["recorded_at"],
        "supabase_persisted": recorded,
        "rollback_plan": rollback,
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, log_level="info")
