---
name: pmoves-legal-assist
description: "Legal document review, research, and case-law verification for PMOVES.AI tenant-advocacy and contract analysis workloads."
version: 0.1.0
author: PMOVES-HERMES-Z890
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, courtlistener, documents, contracts, tenant-advocacy, e2b, zero-retention]
    related_skills: [pmoves-folder-monitor, pmoves-email-organizer, hermes-agent]
---

# PMOVES Legal Assist

Skill for legal document review, US case-law research, and contract analysis on the Z890 node.

## What it does

- Ingests legal documents from a folder monitor, email, or manual upload.
- Runs OCR/extraction (if needed) inside a zero-retention E2B sandbox.
- Applies PMOVES-style document workflows inspired by the `PMOVES-mike` legal assistant:
  - Conditions Precedent (CP) checklist generation
  - Credit agreement summary
  - Shareholder agreement summary
  - Tenant complaint / chronology builder
- Performs US case-law lookup via CourtListener when a token is available.
- Outputs structured reports, Markdown, DOCX, or JSON for Notebook writeback.

## Important non-legal-advice guardrail

This skill does **not** provide legal advice or act as an attorney. Final filings, claims, and court submissions must be reviewed by a licensed lawyer before submission. The agent may draft factual chronologies, organize evidence, and cite public case law, but it must label every output as "For attorney review, not legal advice."

## Required environment variables

```bash
COURTLISTENER_API_TOKEN=       # Optional; enables US case-law tools
E2B_API_KEY=                   # Required for zero-retention sandbox processing
LLM_LOCAL_ENDPOINT=            # e.g. http://localhost:11434 or http://spark:11434
```

## Optional environment variables

```bash
PMOVES_LEGAL_NOTEBOOK_WORKSPACE=legal-ops
PMOVES_LEGAL_FOLDER_WATCH=D:/PMOVES.AI/legal-inbox
PMOVES_LEGAL_OUTPUT=D:/PMOVES.AI/legal-out
```

## Workflows

### 1. Tenant chronology / evidence index

Input: emails, letters, photos, HPD complaints, board notices, assessment notices.
Steps:
1. Extract text and dates.
2. Build chronological timeline with source links.
3. Flag missing evidence or gaps.
4. Output Markdown + JSON for attorney review.

### 2. Contract / agreement analysis

Input: credit agreement, shareholder agreement, management contract, offering plan.
Steps:
1. Detect document type.
2. Run the appropriate checklist/summary workflow.
3. Highlight onerous or unusual terms.
4. Generate DOCX if requested.

### 3. Case-law lookup (US only)

Input: legal question or citation.
Steps:
1. Verify citations via CourtListener.
2. Fetch clusters and read opinions.
3. Find passages relevant to the query.
4. Return citations with clickable links and verbatim quotes.

## E2B zero-retention policy

All document content is processed inside an ephemeral E2B sandbox. The sandbox is killed and its filesystem is destroyed after the workflow completes. No document text is retained in the agent's long-term memory or in PMOVES notebooks unless the user explicitly requests a writeback.

## Invocation patterns

```bash
# In Hermes session with this skill loaded
/skill pmoves-legal-assist

# Ask for help
Review the tenant documents in D:/PMOVES.AI/legal-inbox and build a chronology for attorney review.

# Run a contract analysis
Analyze the uploaded management contract and flag fiduciary or vendor irregularities.
```

## Output targets

- `notebook-page: pages/legal-review`
- `chat-response` with "For attorney review" disclaimer
- `artifact: rooms/z890-infra/legal/{date}/...`

## Next steps to make it fully autonomous

1. Implement `pmoves/tools/legal_assist.py` exposing the CourtListener and document-generation tools.
2. Wire the skill into the `z890-infra.room.fabric` manifest via `skill_bindings`.
3. Add a cron job that polls `PMOVES_LEGAL_FOLDER_WATCH` for new documents.
4. Add a CHIT trail subject for each legal review so work is auditable.
