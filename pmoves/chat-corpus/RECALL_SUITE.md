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

    gitleaks detect --source <cases-dir> --no-git \
      --config pmoves/chat-corpus/gitleaks.toml \
      --report-format json --report-path r.json --no-banner
