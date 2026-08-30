#!/usr/bin/env python3
"""PostToolUse hook — captures agent insights and matches against chit_phrases.

Reads tool output from stdin (Claude Code JSON format), extracts candidate
insight lines via signal-word regex, matches against chit_phrases table,
and writes matches to pmoves_core.insights table.

Fire-and-forget: all errors are swallowed (exit 0 always). Never blocks
the tool pipeline.

Usage (in .claude/settings.json hooks):
  "hooks": {
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 pmoves/scripts/insight_capture_hook.py"}]}]
  }

Env:
  DATABASE_URL — PostgreSQL URL with pgvector (optional; silent no-op if unset)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

# Signal words that indicate an insight-worthy line
SIGNAL_WORDS = re.compile(
    r"\b(insight|pattern|finding|blocker|risk|lesson|anti-?pattern|gotcha|drift)\b",
    re.IGNORECASE,
)

PHRASE_ANCHOR = re.compile(r"\$\$([^$]+)\$\$|\[\[([^\]]+)\]\]")  # $$phrase$$ or [[phrase]]

MAX_INSIGHTS_PER_RUN = 10


def _extract_candidates(text: str) -> list[str]:
    """Extract candidate insight lines from tool output text."""
    candidates: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 10:
            continue
        if SIGNAL_WORDS.search(line):
            candidates.append(line[:500])  # cap line length
        if len(candidates) >= MAX_INSIGHTS_PER_RUN:
            break
    return candidates


async def _match_and_store(candidates: list[str]) -> int:
    """Match candidates against chit_phrases and store hits.

    Returns number of insights stored.
    """
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return 0

    try:
        import asyncpg
    except ImportError:
        return 0

    stored = 0
    try:
        conn = await asyncpg.connect(db_url)
        try:
            # Fetch phrase anchors for matching
            rows = await conn.fetch(
                "SELECT phrase_id, phrase_canonical, category FROM pmoves_core.chit_phrases"
            )
            if not rows:
                return 0

            phrases = {(r["phrase_canonical"].lower()): r for r in rows}

            now = datetime.now(timezone.utc)
            for candidate in candidates:
                # Check for explicit phrase anchors
                anchors = PHRASE_ANCHOR.findall(candidate)
                anchor_texts = [a[0] or a[1] for a in anchors if (a[0] or a[1])]

                matched_phrase_id = None
                for anchor in anchor_texts:
                    row = phrases.get(anchor.lower())
                    if row:
                        matched_phrase_id = row["phrase_id"]
                        break

                # Also check substring match against canonical phrases
                if not matched_phrase_id:
                    candidate_lower = candidate.lower()
                    for canonical, row in phrases.items():
                        if canonical in candidate_lower:
                            matched_phrase_id = row["phrase_id"]
                            break

                if matched_phrase_id:
                    await conn.execute(
                        """
                        INSERT INTO pmoves_core.insights (insight_text, phrase_id, captured_at)
                        VALUES ($1, $2, $3)
                        ON CONFLICT DO NOTHING
                        """,
                        candidate,
                        matched_phrase_id,
                        now,
                    )
                    stored += 1
        finally:
            await conn.close()
    except Exception:
        pass  # fire-and-forget — never block

    return stored


async def main() -> None:
    """Read stdin, extract insights, match, store."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return

        # Parse Claude Code JSON format
        try:
            data = json.loads(raw)
            text = ""
            if isinstance(data, dict):
                # Extract text from tool_output or tool_response
                tool_output = data.get("tool_output") or data.get("tool_response") or {}
                if isinstance(tool_output, dict):
                    text = tool_output.get("content", "") or tool_output.get("stdout", "")
                elif isinstance(tool_output, str):
                    text = tool_output
                # Also check for direct stdout/stderr
                text += str(data.get("stdout", ""))
            elif isinstance(data, str):
                text = data
        except json.JSONDecodeError:
            text = raw

        if not text or len(text) < 10:
            return

        candidates = _extract_candidates(text)
        if candidates:
            await _match_and_store(candidates)

    except Exception:
        pass  # fire-and-forget — never block


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)
