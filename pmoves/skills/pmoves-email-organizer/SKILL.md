---
name: pmoves-email-organizer
description: "Email ingestion, triage, and review workflows for Titanmail and Gmail accounts using the Himalaya CLI and local-only processing."
version: 0.1.0
author: PMOVES-HERMES-Z890
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [email, himalaya, titanmail, gmail, imap, smtp, organization, triage, review]
    related_skills: [pmoves-folder-monitor, pmoves-legal-assist, hermes-agent, himalaya]
---

# PMOVES Email Organizer

Organizes, triages, and reviews emails from Titanmail and Gmail accounts, with local-only processing and optional zero-retention E2B sandbox for attachments.

## Supported accounts

- Titanmail (IMAP/SMTP) — typically host: imap.titan.email / smtp.titan.email
- Gmail (IMAP/SMTP) — requires App Password if 2FA is enabled

## Required environment variables

```bash
# Titanmail
TITAN_IMAP_HOST=imap.titan.email
TITAN_IMAP_PORT=993
TITAN_EMAIL=user@domain.com
TITAN_PASSWORD=app-specific-password

# Gmail
GMAIL_IMAP_HOST=imap.gmail.com
GMAIL_IMAP_PORT=993
GMAIL_EMAIL=user@gmail.com
GMAIL_PASSWORD=app-password

# Output
PMOVES_EMAIL_OUTPUT=D:/PMOVES.AI/email-archive
PMOVES_EMAIL_NOTEBOOK_WORKSPACE=email-ops
PMOVES_EMAIL_THREAD=review
```

## What it does

1. Connects to configured IMAP accounts via Himalaya CLI or Python `imaplib`.
2. Fetches unread/backlogged messages.
3. Extracts sender, date, subject, body, and attachments.
4. Classifies into buckets: `legal`, `finance`, `operations`, `marketing`, `spam`, `needs-review`.
5. For `legal` emails, routes to the folder-monitor legal pipeline.
6. For `finance` emails, routes to Firefly III / spreadsheet extraction.
7. Summarizes high-volume threads.
8. Optionally drafts replies for human approval.

## Backlog processing strategy

Start with date-windowed batches to avoid flooding:

```bash
# Last 30 days, unread only
python pmoves/tools/email_organizer.py --account titan --days 30 --unread-only

# Gmail backlog from 2023-01-01 to 2024-01-01
python pmoves/tools/email_organizer.py --account gmail --since 2023-01-01 --before 2024-01-01 --batch-size 100
```

## Titanmail → Gmail migration

For porting Titanmail into Gmail:

1. Create a Gmail label `Titanmail-Imported`.
2. Run the organizer with `--migrate-to gmail --label Titanmail-Imported`.
3. It uploads each fetched Titanmail message to Gmail via IMAP append.
4. Preserves original headers and timestamps.

## Zero-retention for attachments

Attachments are sent to the E2B zero-retention sandbox if the file type is PDF, DOCX, DOC, EML, MSG, TXT, MD, or image. Extracted text is returned; the attachment is not stored locally unless the user explicitly saves it.

## Command examples

```bash
# Ingest today's Titanmail
PMOVES-HERMES-Z890 himalaya --account titan list --folder INBOX | head -50

# Triage inbox with this skill
/skill pmoves-email-organizer
Organize my Titanmail inbox from the last 30 days and flag legal documents for attorney review.
```

## Notebook output

Results are written to:

```
workspace: email-ops
thread: review
page: triage/{yyyy-mm-dd}
```

## Autonomous scope

Allowed autonomously:
- Fetch and classify emails on schedule.
- Generate summaries and draft replies.
- Move messages to labeled folders.

Not allowed autonomously:
- Sending emails without explicit human approval.
- Deleting emails.
- Filing legal documents or complaints.

## Cron job

```bash
hermes cron create "0 9,21 * * *" --prompt "Run PMOVES email organizer: triage Titanmail and Gmail inboxes, classify legal/finance/operations, draft replies for review, and route legal attachments to the zero-retention folder monitor pipeline." --skills pmoves-email-organizer,pmoves-folder-monitor,pmoves-legal-assist
```

## Next implementation steps

1. Implement `pmoves/tools/email_organizer.py` with Himalaya CLI or `imaplib`/`smtplib`.
2. Add classification prompt/module using local LLM.
3. Add migration helper `Titanmail → Gmail`.
4. Wire to the z890 room manifest as `email-organizer` skill binding.
5. Add cron job.
