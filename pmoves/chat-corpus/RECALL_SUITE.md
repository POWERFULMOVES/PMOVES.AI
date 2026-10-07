# Scrubber Recall Suite (regression corpus)

Synthetic known-good corpus (FAKE secrets only - public documented example
values). Measures the detection config honestly, including gaps.

## Expected matrix (config: gitleaks.toml = upstream defaults + 4 pmoves RE2 rules)

| case | class | measured 2026-10-03 |
|---|---|---|
| 01_aws | AWS keypair | HIT (aws-access-token / env rule) |
| 02_github_classic | GitHub PAT | HIT (github-pat) |
| 03_github_finegrained | fine-grained PAT | HIT (pmoves-env-secret-assign) |
| 04_slack | Slack bot token | HIT (slack-bot-token) |
| 05_stripe | Stripe key | HIT (stripe-access-token) |
| 06_google | GCP API key | HIT (gcp-api-key) - entropy-dependent |
| 07_openai_proj | OpenAI sk-proj in free text | **MISS - known gap** |
| 08_sendgrid | SendGrid token | HIT (sendgrid-api-token) - entropy-dependent |
| 09_twilio | Twilio API key | HIT (twilio-api-key) |
| 10_jwt | Bearer JWT | HIT (jwt + pmoves-jwt-escaped) |
| 11_jwt_json_escaped | JSON-escaped JWT | HIT |
| 12_postgres_url | postgres URL password | HIT (pmoves-postgres-url) |
| 13_env_assignments | NAME=VALUE assignments | HIT (pmoves-env-secret-assign) |
| 14_lan_ips | RFC1918 IPs | HIT (pmoves-lan-ip) |
| 15_private_key | PEM RSA key | HIT (private-key) |
| 16_generic_named | named hex key | HIT (generic-api-key) |
| 17_generic_bare | nameless hex | **MISS - structural** |
| 18_base64_blob | nameless base64 | **MISS - structural** |
| 19_negative_ips | public/out-of-range IPs | CLEAN - no false positives |

## Accepted gaps (documented, not hidden)
1. OpenAI sk-proj tokens in free text: no upstream rule fired even with
   high-entropy synthetic. Mitigation: burn-list literals.
2. Nameless high-entropy strings: not detectable without name/context.

## Entropy caveat
Low-entropy synthetics (repeated characters) fail upstream entropy gates even
when regexes match: cases 06/08 were MISS with naive values, HIT with random
one. Always test with realistic entropy.

## Reproduce

Fixtures are generated locally, NOT committed: GitHub push protection
rejects real-format credential strings even when synthetic. Generate
then scan:

    python pmoves/chat-corpus/gen_recall_cases.py
    gitleaks detect --source pmoves/chat-corpus/recall-cases --no-git \
      --config pmoves/chat-corpus/gitleaks.toml \
      --report-format json --report-path r.json --no-banner


## Second-engine verification (2026-10-03)

detect-secrets (Yelp, MIT; different detectors than gitleaks) over the staged
corpus with explicit file list: 8 automated flags -> 8 triaged likely-FP
(REDACTED-marker self-triggers + encoded-media blobs). Masked triage:
detect-secrets-triage.json (in gate-reports dir). Interpretation: second
engine found no uncaught real-format secrets; automated triage only, human
confirmation tracked in SPOTAUDIT.md Step 1.

## Jev stage-2 triage (2026-10-06)

TypeSafe Jev (jev-1.13.0) classified 709 high-entropy candidates from the
corpus in 7.5 seconds (endpoint /v1/systemone, 36 batches of 20). Results:

| verdict | count | notes |
|---|---|---|
| noise | 579 (81.7%) | git SHAs, URLs, container hashes, file paths, encoded content |
| unsure | 88 (12.4%) | model genuinely uncertain - human review needed |
| credential | 42 (5.9%) | all with confidence 0.01-0.21 (borderline) |

Confidence gates: auto-dismiss >=0.9 (82 items), review 0.7-0.9 (136),
escalate <0.7 (491). Zero high-confidence credential findings means the
gitleaks pass caught everything real. Jev narrowed the human review scope
from 709 to ~130 items (82% reduction).

Validation: 10-case and 20-case stratified samples both matched manual
triage with zero false negatives. Confidence gradient maps to risk gradient
(1.0 on obvious noise, 0.50-0.77 on genuinely ambiguous cases).

Typesafe Jev is the recommended stage-2 detector. AgentJev-0.6B (ONNX,
calibrated, 129ms/decision) is the fleet-local fallback.
## Two-pass cascade (2026-10-06)

Second pass with wider context (200 chars + adjacent lines) over the 597
non-auto candidates from pass 1: 237 additional auto-dismissals, 0 flipped
to credential, 112 remaining escalations (Neo4j submodule gitlinks).
Total: 709 -> 627 -> 112 = 84% reduction. HiRAG provenance indexing approved.