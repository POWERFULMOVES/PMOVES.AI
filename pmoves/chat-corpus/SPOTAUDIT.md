# OPERATOR SPOT-AUDIT WORKSHEET (human-required steps)

Generated 2026-10-03 by the a0-sidecar verification round. Two items in the
audit hard-gate list REQUIRE a human; this worksheet makes them mechanical.
Everything else in the audit list is done and evidenced in
chat-corpus-gate-reports/ (outside the repo: staging provenance dir).

## State snapshot (from run-manifest.json, 2026-10-03)

- gate: rounds 4 -> 0, final PASS | unique secrets redacted: 1,318
- corpus: 16 chats / 473 messages / 3 keyword-excluded
- engine: gitleaks 8.30.1 (sha256 17157e2e...) config sha256 818d11c6...
- second engine (detect-secrets): 8 automated flags -> 8 triaged likely-FP
  (6 = REDACTED marker strings self-triggering the keyword detector;
  3-merge = base64-entropy on YouTube playlist JSON blobs)
  - per-finding masked triage: detect-secrets-triage.json
- gap classes: 677 high-entropy hex/b64 candidates saved for review
  - full list + entropy + context flags: gap-triage.json

## Step 1 - human spot-audit of REDACTED lines (~20 min)

1. Open C:\Users\russe\agent-zero\chat-corpus-staging\findings.csv
   (in the gate-reports dir) - per-chat redaction counts.
2. Spot-check 5 random .jsonl files: grep for 'REDACTED' and read the
   SURROUNDING context only. Confirm no secret-looking value sits next to a
   marker (marker-adjacent fragments are the failure mode we saw before).
3. Specifically eyeball the 8 detect-secrets triage rows
   (detect-secrets-triage.json) - confirm the LIKELY-FP verdicts.
4. Review gap-triage.json candidates - confirm the high-entropy b64 blobs
   are encoded media (playlist JSON), not credentials.
5. Sign off by appending a line to ITERATIONS.md ERRATA:
   'Spot-audit performed <date> by <name>: PASS/FAIL + notes'.

## Step 2 - provider-side revocation evidence (~10 min)

1. Supabase dashboard -> Settings -> API: confirm current anon/service_role
   keys match the live sha8 58a169e9 / f4fa5cc4 (compare by eye or hash).
2. Auth -> JWT Keys / legacy: confirm the OLD JWT secret is revoked (history
   shows rotation timestamp BEFORE the corpus chats that contain it).
3. Wger + Google OAuth (GOCSPX-... literal in burn list): confirm reset in
   provider UI. Screenshots or timestamps -> pmoves/chat-corpus/ locally
   (do NOT commit screenshots showing values).
4. Record result in ITERATIONS.md ERRATA: 'Provider-side revocation
   confirmed <date>: <list> (any exceptions named)'.

After both steps pass, publication block can be lifted by editing the
ERRATA 'Publication remains BLOCKED' line.
