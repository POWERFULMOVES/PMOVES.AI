# Review Dump — POWERFULMOVES/PMOVES.AI#2439

**feat(review): App-token review-collect pipeline — automatic harvesting into LLM-readable format**

- State: `OPEN` | Branch: `feat/review-collect-pipeline` → `main` | +502/-0 (5 files)
- Author: POWERFULMOVES | Collected: 2026-08-06T17:37:39.128719+00:00

## Summary

| Metric | Count |
|---|---|
| Total threads | 14 |
| Resolved | 7 |
| Open P1/P2 (actionable) | 0 |
| Committable suggestions | 3 |

**Severity breakdown:** P1=1, P2=6, unclassified=7

## Reviews (2)

- **chatgpt-codex-connector** (COMMENTED) —  ### 💡 Codex Review  Here are some automated review suggestions for this pull request.  **Reviewed commit:** `cd66910faf`       <details> <summary>ℹ️ About Codex in GitHub</summary> <br/>  [Your team 
- **coderabbitai** (COMMENTED) — **Actionable comments posted: 7**  <details> <summary>🤖 Prompt for all review comments with AI agents</summary>  ``` Verify each finding against current code. Fix only still-valid issues, skip the res

## Threads

### 1. ✅ [P1] chatgpt-codex-connector — `.github/workflows/review-collect.yml:50`

**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Invoke the reusable token workflow at job level**

Every trigger stops before collection because `_app-token.yml` declares a `workflow_call` reusable workflow, while this step-level `uses` makes GitHub treat the path as a local action; there is no action metadata at that file path, so no token or artifact is produced. Call the reusable workflow from `jobs.<id>.uses` with its required secrets, or mint the token with an actual action in this job.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,83 @@
+name: Review Collect
+
+# Collects PR review threads (CodeRabbit, Codex, human) into LLM-readable
+# JSON + Markdown artifacts using the GitHub App token for auth.
+#
+# REPLACES the disabled review-comment-monitor.yml (which depended on
+# ANTHROPIC_API_KEY for Claude triage). This workflow is pure Python —
+# no API key needed beyond the App token. The App token provides
+# pull-requests:read scope to fetch review threads via GraphQL.
+#
+# Artifacts are uploaded for download and optionally committed to
+# pmoves/docs/logs/review-dumps/ for searchability.
+#
+# Ingestion into Hi-RAG/Cipher is OPT-IN via repository variables
+# (PMOVES_REVIEW_INGEST_HIRAG / PMOVES_REVIEW_INGEST_CIPHER).
+
+on:
+  pull_request_review:
+    types: [submitted]
+  pull_request_review_comment:
+    types: [created]
+  schedule:
+    # Every 2 hours — catches threads posted between events
+    - cron: "0 */2 * * *"
+  workflow_dispatch:
+    inputs:
+      repo:
+        description: "Repo name (default: PMOVES.AI)"
+        required: false
+        default: PMOVES.AI
+      pr:
+        description: "Single PR number (blank = all open)"
+        required: false
+
+concurrency:
+  group: review-collect-${{ github.event.pull_request.number || github.run_id }}
+  cancel-in-progress: false
+
+permissions:
+  contents: read
+  pull-requests: read
+
+jobs:
+  collect:
+    runs-on: ubuntu-latest
+    timeout-minutes: 5
+    steps:
+      - name: Mint GitHub App token
+        id: app-token
+        uses: ./.github/workflows/_app-token.yml
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730573116)

### 2. ✅ [P2] chatgpt-codex-connector — `.github/workflows/review-collect.yml:69`

**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Honor the repository selected during manual dispatch**

When an operator supplies the documented `workflow_dispatch.inputs.repo`, the collection step still hardcodes the current repository name, and the token step is likewise scoped to the current repository. Consequently, manual cross-repository collection silently dumps PMOVES.AI rather than the requested repository; use the input for both token scope and `--repo`, falling back to the event repository only when it is blank.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,83 @@
+name: Review Collect
+
+# Collects PR review threads (CodeRabbit, Codex, human) into LLM-readable
+# JSON + Markdown artifacts using the GitHub App token for auth.
+#
+# REPLACES the disabled review-comment-monitor.yml (which depended on
+# ANTHROPIC_API_KEY for Claude triage). This workflow is pure Python —
+# no API key needed beyond the App token. The App token provides
+# pull-requests:read scope to fetch review threads via GraphQL.
+#
+# Artifacts are uploaded for download and optionally committed to
+# pmoves/docs/logs/review-dumps/ for searchability.
+#
+# Ingestion into Hi-RAG/Cipher is OPT-IN via repository variables
+# (PMOVES_REVIEW_INGEST_HIRAG / PMOVES_REVIEW_INGEST_CIPHER).
+
+on:
+  pull_request_review:
+    types: [submitted]
+  pull_request_review_comment:
+    types: [created]
+  schedule:
+    # Every 2 hours — catches threads posted between events
+    - cron: "0 */2 * * *"
+  workflow_dispatch:
+    inputs:
+      repo:
+        description: "Repo name (default: PMOVES.AI)"
+        required: false
+        default: PMOVES.AI
+      pr:
+        description: "Single PR number (blank = all open)"
+        required: false
+
+concurrency:
+  group: review-collect-${{ github.event.pull_request.number || github.run_id }}
+  cancel-in-progress: false
+
+permissions:
+  contents: read
+  pull-requests: read
+
+jobs:
+  collect:
+    runs-on: ubuntu-latest
+    timeout-minutes: 5
+    steps:
+      - name: Mint GitHub App token
+        id: app-token
+        uses: ./.github/workflows/_app-token.yml
+        with:
+          owner: ${{ github.repository_owner }}
+          repositories: ${{ github.event.repository.name }}
+          permission-pull-requests: read
+          permission-contents: read
+
+      - name: Checkout repository
+        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
+        with:
+          token: ${{ steps.app-token.outputs.token }}
+          fetch-depth: 0
+
+      - name: Collect review threads
+        env:
+          GH_TOKEN: ${{ steps.app-token.outputs.token }}
+          PMOVES_GITHUB_ORG: ${{ github.repository_owner }}
+        run: |
+          REPO="${{ github.event.repository.name }}"
+          PR="${{ github.event.inputs.pr || github.event.pull_request.number || '' }}"
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730573120)

### 3. ✅ [P2] chatgpt-codex-connector — `.github/workflows/review-collect.yml:74`

**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Wire the opt-in ingestion variables into the command**

Even when `PMOVES_REVIEW_INGEST_HIRAG` or `PMOVES_REVIEW_INGEST_CIPHER` is enabled as documented at the top of this workflow, every invocation unconditionally passes `--dry-run` and neither variable is read. Since `dump_pr` explicitly suppresses ingestion during a dry run, scheduled and event-driven runs can never fan out to either backend.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,83 @@
+name: Review Collect
+
+# Collects PR review threads (CodeRabbit, Codex, human) into LLM-readable
+# JSON + Markdown artifacts using the GitHub App token for auth.
+#
+# REPLACES the disabled review-comment-monitor.yml (which depended on
+# ANTHROPIC_API_KEY for Claude triage). This workflow is pure Python —
+# no API key needed beyond the App token. The App token provides
+# pull-requests:read scope to fetch review threads via GraphQL.
+#
+# Artifacts are uploaded for download and optionally committed to
+# pmoves/docs/logs/review-dumps/ for searchability.
+#
+# Ingestion into Hi-RAG/Cipher is OPT-IN via repository variables
+# (PMOVES_REVIEW_INGEST_HIRAG / PMOVES_REVIEW_INGEST_CIPHER).
+
+on:
+  pull_request_review:
+    types: [submitted]
+  pull_request_review_comment:
+    types: [created]
+  schedule:
+    # Every 2 hours — catches threads posted between events
+    - cron: "0 */2 * * *"
+  workflow_dispatch:
+    inputs:
+      repo:
+        description: "Repo name (default: PMOVES.AI)"
+        required: false
+        default: PMOVES.AI
+      pr:
+        description: "Single PR number (blank = all open)"
+        required: false
+
+concurrency:
+  group: review-collect-${{ github.event.pull_request.number || github.run_id }}
+  cancel-in-progress: false
+
+permissions:
+  contents: read
+  pull-requests: read
+
+jobs:
+  collect:
+    runs-on: ubuntu-latest
+    timeout-minutes: 5
+    steps:
+      - name: Mint GitHub App token
+        id: app-token
+        uses: ./.github/workflows/_app-token.yml
+        with:
+          owner: ${{ github.repository_owner }}
+          repositories: ${{ github.event.repository.name }}
+          permission-pull-requests: read
+          permission-contents: read
+
+      - name: Checkout repository
+        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
+        with:
+          token: ${{ steps.app-token.outputs.token }}
+          fetch-depth: 0
+
+      - name: Collect review threads
+        env:
+          GH_TOKEN: ${{ steps.app-token.outputs.token }}
+          PMOVES_GITHUB_ORG: ${{ github.repository_owner }}
+        run: |
+          REPO="${{ github.event.repository.name }}"
+          PR="${{ github.event.inputs.pr || github.event.pull_request.number || '' }}"
+
+          if [ -n "$PR" ]; then
+            python -m pmoves.tools.review_dump --repo "$REPO" --pr "$PR" --dry-run
+          else
+            python -m pmoves.tools.review_dump --repo "$REPO" --state open --limit 20 --dry-run
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730573124)

### 4. ✅ [P2] chatgpt-codex-connector — `pmoves/tools/review_dump.py:146`

**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Normalize the captured severity before validating it**

For comments formatted as `Severity: P1` or `severity P2`, the regex captures `P1`/`P2` in its second group, but this loop accepts only digit-only groups, so these comments become `unclassified`. That removes them from the actionable count and prevents their Cipher ingestion; strip an optional `P` or make both alternatives capture only the digit.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,352 @@
+#!/usr/bin/env python3
+"""Review Dump — collect PR review threads into LLM-readable JSON + Markdown.
+
+Extends collect_review_comments.py (which writes to Supabase) with:
+  - GraphQL review threads (resolved state + reply chains — REST misses these)
+  - Committable-suggestion extraction (CodeRabbit ```suggestion blocks)
+  - Diff context (the diff_hunk around each comment)
+  - Structured JSON export for tooling
+  - Human/LLM-readable Markdown export for local analysis
+  - Optional fan-out to Hi-RAG (POST /hirag/upsert-batch) and Cipher (POST /api/memory)
+
+Usage:
+    # Dump a single PR to local files:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434
+
+    # Dump all open PRs:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --state open
+
+    # Dump + ingest into Hi-RAG and Cipher:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --ingest-hirag --ingest-cipher
+
+    # Dry-run (collect + export, no ingestion):
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --dry-run
+
+Output files land in pmoves/docs/logs/review-dumps/<repo>-<pr>.{json,md} by default.
+"""
+
+from __future__ import annotations
+
+import argparse
+import json
+import os
+import re
+import sys
+import urllib.request
+import urllib.error
+from datetime import datetime, timezone
+from pathlib import Path
+from typing import Any
+
+_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
+if str(_REPO_ROOT) not in sys.path:
+    sys.path.insert(0, str(_REPO_ROOT))
+
+GITHUB_ORG = os.environ.get("PMOVES_GITHUB_ORG", "POWERFULMOVES")
+GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
+HIRAG_URL = os.environ.get("HIRAG_UPSERT_URL") or os.environ.get("HIRAG_URL", "http://localhost:8086")
+CIPHER_URL = os.environ.get("CIPHER_API_URL", "http://localhost:8105")
+CIPHER_TOKEN = os.environ.get("CIPHER_API_TOKEN", "")
+OUTPUT_DIR = Path(os.environ.get("REVIEW_DUMP_DIR", _REPO_ROOT / "pmoves" / "docs" / "logs" / "review-dumps"))
+
+SEVERITY_RE = re.compile(r"(?:P(\d)\s+Badge|severity[:\s]*(P\d))", re.IGNORECASE)
+SUGGESTION_RE = re.compile(r"```suggestion\n(.*?)```", re.DOTALL)
+NITPICK_RE = re.compile(r"\b(nitpick|nit\b)", re.IGNORECASE)
+
+
+def _gh_headers() -> dict[str, str]:
+    if not GITHUB_TOKEN:
+        raise SystemExit("ERROR: GH_TOKEN or GITHUB_TOKEN not set")
+    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
+
+
+def gh_rest(path: str) -> Any:
+    req = urllib.request.Request(f"https://api.github.com{path}", headers=_gh_headers())
+    try:
+        return json.loads(urllib.request.urlopen(req, timeout=30).read())
+    except urllib.error.HTTPError as e:
+        if e.code == 404:
+            return []
+        raise
+
+
+def gh_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
+    body = json.dumps({"query": query, "variables": variables}).encode()
+    req = urllib.request.Request(
+        "https://api.github.com/graphql",
+        data=body,
+        headers={**_gh_headers(), "Content-Type": "application/json"},
+    )
+    return json.loads(urllib.request.urlopen(req, timeout=30).read())
+
+
+THREADS_QUERY = """
+query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
+  repository(owner: $owner, name: $name) {
+    pullRequest(number: $number) {
+      title state mergedAt headRefName baseRefName additions deletions changedFiles
+      author { login }
+      reviewThreads(first: 100, after: $cursor) {
+        pageInfo { hasNextPage endCursor }
+        nodes {
+          id isResolved isOutdated path line
+          comments(first: 20) {
+            nodes {
+              databaseId author { login } body path line originalLine diffHunk createdAt url
+            }
+          }
+        }
+      }
+      reviews(first: 50) {
+        nodes { author { login } state body submittedAt }
+      }
+    }
+  }
+}
+"""
+
+
+def fetch_threads(repo: str, pr_number: int) -> dict[str, Any]:
+    owner, *rest = repo.split("/", 1)
+    name = rest[0] if rest else repo
+    result: dict[str, Any] = {}
+    cursor = None
+    while True:
+        data = gh_graphql(THREADS_QUERY, {"owner": owner, "name": name, "number": pr_number, "cursor": cursor})
+        pr = data["data"]["repository"]["pullRequest"]
+        if not pr:
+            raise SystemExit(f"ERROR: PR {repo}#{pr_number} not found")
+        if not result:
+            result = {
+                "repo": repo, "pr_number": pr_number, "title": pr["title"], "state": pr["state"],
+                "merged_at": pr.get("mergedAt"), "branch": pr["headRefName"], "base": pr["baseRefName"],
+                "additions": pr["additions"], "deletions": pr["deletions"], "changed_files": pr["changedFiles"],
+                "author": (pr.get("author") or {}).get("login", "unknown"),
+                "collected_at": datetime.now(timezone.utc).isoformat(),
+                "threads": [],
+                "reviews": [
+                    {"author": (r.get("author") or {}).get("login", "unknown"), "state": r["state"],
+                     "body": r.get("body") or "", "submitted_at": r.get("submittedAt")}
+                    for r in pr.get("reviews", {}).get("nodes", [])
+                ],
+            }
+        result["threads"].extend(pr["reviewThreads"]["nodes"])
+        if pr["reviewThreads"]["pageInfo"]["hasNextPage"]:
+            cursor = pr["reviewThreads"]["pageInfo"]["endCursor"]
+        else:
+            break
+    return result
+
+
+def extract_severity(body: str) -> str:
+    m = SEVERITY_RE.search(body)
+    if m:
+        for g in m.groups():
+            if g and g.isdigit():
+                return f"P{g}"
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730573128)

### 5. ✅ [P2] chatgpt-codex-connector — `pmoves/tools/review_dump.py:337`

**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Preserve the independently selected ingestion backends**

When a caller supplies only `--ingest-hirag` or only `--ingest-cipher`, combining the flags into one boolean causes `dump_pr` to invoke both backend functions. In particular, a Cipher-only run unexpectedly posts every record to Hi-RAG, while a Hi-RAG-only run also attempts Cipher; pass the two selections separately and guard each sink independently.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,352 @@
+#!/usr/bin/env python3
+"""Review Dump — collect PR review threads into LLM-readable JSON + Markdown.
+
+Extends collect_review_comments.py (which writes to Supabase) with:
+  - GraphQL review threads (resolved state + reply chains — REST misses these)
+  - Committable-suggestion extraction (CodeRabbit ```suggestion blocks)
+  - Diff context (the diff_hunk around each comment)
+  - Structured JSON export for tooling
+  - Human/LLM-readable Markdown export for local analysis
+  - Optional fan-out to Hi-RAG (POST /hirag/upsert-batch) and Cipher (POST /api/memory)
+
+Usage:
+    # Dump a single PR to local files:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434
+
+    # Dump all open PRs:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --state open
+
+    # Dump + ingest into Hi-RAG and Cipher:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --ingest-hirag --ingest-cipher
+
+    # Dry-run (collect + export, no ingestion):
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --dry-run
+
+Output files land in pmoves/docs/logs/review-dumps/<repo>-<pr>.{json,md} by default.
+"""
+
+from __future__ import annotations
+
+import argparse
+import json
+import os
+import re
+import sys
+import urllib.request
+import urllib.error
+from datetime import datetime, timezone
+from pathlib import Path
+from typing import Any
+
+_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
+if str(_REPO_ROOT) not in sys.path:
+    sys.path.insert(0, str(_REPO_ROOT))
+
+GITHUB_ORG = os.environ.get("PMOVES_GITHUB_ORG", "POWERFULMOVES")
+GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
+HIRAG_URL = os.environ.get("HIRAG_UPSERT_URL") or os.environ.get("HIRAG_URL", "http://localhost:8086")
+CIPHER_URL = os.environ.get("CIPHER_API_URL", "http://localhost:8105")
+CIPHER_TOKEN = os.environ.get("CIPHER_API_TOKEN", "")
+OUTPUT_DIR = Path(os.environ.get("REVIEW_DUMP_DIR", _REPO_ROOT / "pmoves" / "docs" / "logs" / "review-dumps"))
+
+SEVERITY_RE = re.compile(r"(?:P(\d)\s+Badge|severity[:\s]*(P\d))", re.IGNORECASE)
+SUGGESTION_RE = re.compile(r"```suggestion\n(.*?)```", re.DOTALL)
+NITPICK_RE = re.compile(r"\b(nitpick|nit\b)", re.IGNORECASE)
+
+
+def _gh_headers() -> dict[str, str]:
+    if not GITHUB_TOKEN:
+        raise SystemExit("ERROR: GH_TOKEN or GITHUB_TOKEN not set")
+    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
+
+
+def gh_rest(path: str) -> Any:
+    req = urllib.request.Request(f"https://api.github.com{path}", headers=_gh_headers())
+    try:
+        return json.loads(urllib.request.urlopen(req, timeout=30).read())
+    except urllib.error.HTTPError as e:
+        if e.code == 404:
+            return []
+        raise
+
+
+def gh_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
+    body = json.dumps({"query": query, "variables": variables}).encode()
+    req = urllib.request.Request(
+        "https://api.github.com/graphql",
+        data=body,
+        headers={**_gh_headers(), "Content-Type": "application/json"},
+    )
+    return json.loads(urllib.request.urlopen(req, timeout=30).read())
+
+
+THREADS_QUERY = """
+query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
+  repository(owner: $owner, name: $name) {
+    pullRequest(number: $number) {
+      title state mergedAt headRefName baseRefName additions deletions changedFiles
+      author { login }
+      reviewThreads(first: 100, after: $cursor) {
+        pageInfo { hasNextPage endCursor }
+        nodes {
+          id isResolved isOutdated path line
+          comments(first: 20) {
+            nodes {
+              databaseId author { login } body path line originalLine diffHunk createdAt url
+            }
+          }
+        }
+      }
+      reviews(first: 50) {
+        nodes { author { login } state body submittedAt }
+      }
+    }
+  }
+}
+"""
+
+
+def fetch_threads(repo: str, pr_number: int) -> dict[str, Any]:
+    owner, *rest = repo.split("/", 1)
+    name = rest[0] if rest else repo
+    result: dict[str, Any] = {}
+    cursor = None
+    while True:
+        data = gh_graphql(THREADS_QUERY, {"owner": owner, "name": name, "number": pr_number, "cursor": cursor})
+        pr = data["data"]["repository"]["pullRequest"]
+        if not pr:
+            raise SystemExit(f"ERROR: PR {repo}#{pr_number} not found")
+        if not result:
+            result = {
+                "repo": repo, "pr_number": pr_number, "title": pr["title"], "state": pr["state"],
+                "merged_at": pr.get("mergedAt"), "branch": pr["headRefName"], "base": pr["baseRefName"],
+                "additions": pr["additions"], "deletions": pr["deletions"], "changed_files": pr["changedFiles"],
+                "author": (pr.get("author") or {}).get("login", "unknown"),
+                "collected_at": datetime.now(timezone.utc).isoformat(),
+                "threads": [],
+                "reviews": [
+                    {"author": (r.get("author") or {}).get("login", "unknown"), "state": r["state"],
+                     "body": r.get("body") or "", "submitted_at": r.get("submittedAt")}
+                    for r in pr.get("reviews", {}).get("nodes", [])
+                ],
+            }
+        result["threads"].extend(pr["reviewThreads"]["nodes"])
+        if pr["reviewThreads"]["pageInfo"]["hasNextPage"]:
+            cursor = pr["reviewThreads"]["pageInfo"]["endCursor"]
+        else:
+            break
+    return result
+
+
+def extract_severity(body: str) -> str:
+    m = SEVERITY_RE.search(body)
+    if m:
+        for g in m.groups():
+            if g and g.isdigit():
+                return f"P{g}"
+    if NITPICK_RE.search(body):
+        return "nitpick"
+    low = body.lower()
+    if "praise" in low:
+        return "praise"
+    if "question" in low:
+        return "question"
+    return "unclassified"
+
+
+def extract_suggestions(body: str) -> list[str]:
+    return [m.group(1).rstrip() for m in SUGGESTION_RE.finditer(body)]
+
+
+def classify_author(author: str) -> str:
+    if "[bot]" in author or author in {"coderabbitai", "chatgpt-codex-connector", "github-actions", "dependabot"}:
+        return "bot"
+    return "human"
+
+
+def thread_to_record(thread: dict[str, Any]) -> dict[str, Any]:
+    comments = thread.get("comments", {}).get("nodes", [])
+    if not comments:
+        return {}
+    first = comments[0]
+    body = first.get("body", "")
+    path = thread.get("path") or first.get("path")
+    line = thread.get("line") or first.get("line") or first.get("originalLine")
+    replies = [
+        {"author": (r.get("author") or {}).get("login", "unknown"), "body": r.get("body", ""), "created_at": r.get("createdAt")}
+        for r in comments[1:]
+    ]
+    return {
+        "thread_id": thread["id"], "is_resolved": thread.get("isResolved", False),
+        "is_outdated": thread.get("isOutdated", False), "path": path, "line": line,
+        "severity": extract_severity(body),
+        "author": (first.get("author") or {}).get("login", "unknown"),
+        "author_type": classify_author((first.get("author") or {}).get("login", "unknown")),
+        "body": body, "suggestions": extract_suggestions(body),
+        "diff_hunk": first.get("diffHunk", ""), "replies": replies,
+        "url": first.get("url", ""), "created_at": first.get("createdAt"),
+    }
+
+
+def export_json(data: dict[str, Any], path: Path) -> None:
+    path.parent.mkdir(parents=True, exist_ok=True)
+    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
+
+
+def export_markdown(data: dict[str, Any], path: Path) -> None:
+    lines: list[str] = []
+    repo, pr = data["repo"], data["pr_number"]
+    lines.append(f"# Review Dump — {repo}#{pr}\n\n**{data['title']}**\n\n")
+    lines.append(f"- State: `{data['state']}` | Branch: `{data['branch']}` → `{data['base']}` | "
+                 f"+{data['additions']}/-{data['deletions']} ({data['changed_files']} files)\n")
+    lines.append(f"- Author: {data['author']} | Collected: {data['collected_at']}\n")
+    records = data.get("thread_records", [])
+    resolved = sum(1 for r in records if r["is_resolved"])
+    actionable = [r for r in records if r["severity"] in ("P1", "P2") and not r["is_resolved"]]
+    suggestions = [s for r in records for s in r["suggestions"]]
+    lines.append(f"\n## Summary\n\n| Metric | Count |\n|---|---|\n")
+    lines.append(f"| Total threads | {len(records)} |\n| Resolved | {resolved} |\n")
+    lines.append(f"| Open P1/P2 (actionable) | {len(actionable)} |\n| Committable suggestions | {len(suggestions)} |\n")
+    sev_counts: dict[str, int] = {}
+    for r in records:
+        sev_counts[r["severity"]] = sev_counts.get(r["severity"], 0) + 1
+    if sev_counts:
+        lines.append(f"\n**Severity breakdown:** {', '.join(f'{k}={v}' for k, v in sorted(sev_counts.items()))}\n")
+    if data.get("reviews"):
+        lines.append(f"\n## Reviews ({len(data['reviews'])})\n\n")
+        for rev in data["reviews"]:
+            lines.append(f"- **{rev['author']}** ({rev['state']}) — {(rev.get('body') or '')[:200].replace(chr(10), ' ')}\n")
+    if not records:
+        lines.append(f"\n*No review threads found.*\n")
+    else:
+        lines.append(f"\n## Threads\n\n")
+        for i, r in enumerate(records, 1):
+            status = "✅" if r["is_resolved"] else ("⚠️" if r["is_outdated"] else "🔴")
+            lines.append(f"### {i}. {status} [{r['severity']}] {r['author']} — `{r['path']}:{r['line']}`\n\n")
+            lines.append(f"{r['body'][:2000]}\n\n")
+            if r["suggestions"]:
+                lines.append(f"**Committable suggestion(s):**\n\n")
+                for s in r["suggestions"]:
+                    lines.append(f"```suggestion\n{s}\n```\n\n")
+            if r["diff_hunk"]:
+                lines.append(f"<details><summary>Diff context</summary>\n\n```diff\n{r['diff_hunk']}\n```\n\n</details>\n\n")
+            if r["replies"]:
+                lines.append(f"<details><summary>{len(r['replies'])} repl{'y' if len(r['replies'])==1 else 'ies'}</summary>\n\n")
+                for rep in r["replies"]:
+                    lines.append(f"- **{rep['author']}**: {rep['body'][:300]}\n")
+                lines.append(f"\n</details>\n\n")
+            if r["url"]:
+                lines.append(f"[→ thread]({r['url']})\n\n")
+    path.parent.mkdir(parents=True, exist_ok=True)
+    path.write_text("".join(lines), encoding="utf-8")
+
+
+def _record_to_text(r: dict[str, Any], pr_data: dict[str, Any]) -> str:
+    parts = [
+        f"PR {pr_data['repo']}#{pr_data['pr_number']}: {pr_data['title']}",
+        f"Severity: {r['severity']} | Author: {r['author']} | Resolved: {r['is_resolved']}",
+    ]
+    if r.get("path"):
+        parts.append(f"Location: {r['path']}:{r['line']}")
+    parts.append(f"\n{r['body']}")
+    if r["suggestions"]:
+        parts.append("\nSuggested fix:")
+        for s in r["suggestions"]:
+            parts.append(f"  {s[:200]}")
+    return "\n".join(parts)
+
+
+def ingest_hirag(records: list[dict[str, Any]], pr_data: dict[str, Any]) -> int:
+    items = [{
+        "id": f"review-{pr_data['repo']}-{pr_data['pr_number']}-{r['thread_id'][-12:]}",
+        "content": _record_to_text(r, pr_data),
+        "metadata": {"type": "review_comment", "repo": pr_data["repo"], "pr_number": pr_data["pr_number"],
+                     "severity": r["severity"], "path": r.get("path"), "author": r["author"], "is_resolved": r["is_resolved"]},
+    } for r in records]
+    body = json.dumps({"items": items}).encode()
+    req = urllib.request.Request(f"{HIRAG_URL}/hirag/upsert-batch", data=body,
+                                 headers={"Content-Type": "application/json"}, method="POST")
+    try:
+        urllib.request.urlopen(req, timeout=30)
+        return len(items)
+    except Exception as e:
+        print(f"  [hirag] error: {e}", file=sys.stderr)
+        return 0
+
+
+def ingest_cipher(records: list[dict[str, Any]], pr_data: dict[str, Any]) -> int:
+    if not CIPHER_TOKEN:
+        print("  [cipher] skip: CIPHER_API_TOKEN not set", file=sys.stderr)
+        return 0
+    count = 0
+    for r in records:
+        if r["severity"] not in ("P1", "P2"):
+            continue
+        body = json.dumps({
+            "agentId": "review-collector", "category": "review_learning",
+            "content": _record_to_text(r, pr_data),
+            "metadata": {"repo": pr_data["repo"], "pr_number": pr_data["pr_number"],
+                         "severity": r["severity"], "path": r.get("path"), "thread_id": r["thread_id"]},
+            "tags": ["review", r["severity"], pr_data["repo"], "pr-learning"],
+        }).encode()
+        req = urllib.request.Request(f"{CIPHER_URL}/api/memory", data=body,
+                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {CIPHER_TOKEN}"},
+                                     method="POST")
+        try:
+            urllib.request.urlopen(req, timeout=10)
+            count += 1
+        except Exception as e:
+            print(f"  [cipher] error on thread {r['thread_id'][-8:]}: {e}", file=sys.stderr)
+    return count
+
+
+def dump_pr(repo: str, pr_number: int, dry_run: bool, ingest: bool) -> dict[str, Any]:
+    full_repo = f"{GITHUB_ORG}/{repo}" if "/" not in repo else repo
+    print(f"[review-dump] {full_repo}#{pr_number}")
+    data = fetch_threads(full_repo, pr_number)
+    records = [t for t in (thread_to_record(t) for t in data["threads"]) if t]
+    data["thread_records"] = records
+    slug = repo.replace("/", "-")
+    json_path = OUTPUT_DIR / f"{slug}-{pr_number}.json"
+    md_path = OUTPUT_DIR / f"{slug}-{pr_number}.md"
+    export_json(data, json_path)
+    export_markdown(data, md_path)
+    print(f"  exported: {json_path.relative_to(_REPO_ROOT)}")
+    print(f"  exported: {md_path.relative_to(_REPO_ROOT)}")
+    print(f"  threads: {len(records)} ({sum(1 for r in records if r['is_resolved'])} resolved, "
+          f"{sum(1 for r in records if r['severity'] in ('P1','P2') and not r['is_resolved'])} open P1/P2, "
+          f"{sum(len(r['suggestions']) for r in records)} suggestions)")
+    if ingest and not dry_run:
+        n = ingest_hirag(records, data)
+        print(f"  [hirag] ingested {n} records")
+        n = ingest_cipher(records, data)
+        print(f"  [cipher] ingested {n} P1/P2 learnings")
+    return data
+
+
+def main() -> None:
+    parser = argparse.ArgumentParser(description="Collect PR review threads into LLM-readable JSON + Markdown")
+    parser.add_argument("--repo", required=True, help="Repo name (e.g. PMOVES.AI, Pmoves-cipher)")
+    parser.add_argument("--pr", type=int, help="Single PR number")
+    parser.add_argument("--state", default="open", choices=["open", "merged", "closed", "all"])
+    parser.add_argument("--limit", type=int, default=10, help="Max PRs to scan (when not --pr)")
+    parser.add_argument("--dry-run", action="store_true", help="Collect + export only, no ingestion")
+    parser.add_argument("--ingest-hirag", action="store_true", help="Fan out to Hi-RAG")
+    parser.add_argument("--ingest-cipher", action="store_true", help="Fan out to Cipher memory")
+    args = parser.parse_args()
+    ingest = args.ingest_hirag or args.ingest_cipher
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730573133)

### 6. ✅ [P2] chatgpt-codex-connector — `pmoves/tools/review_dump.py:343`

**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Include open pull requests when state is all**

When the CLI is invoked with the advertised `--state all`, this mapping requests `state=closed`, so every open PR is omitted. The resulting historical dump is incomplete while still being reported as an `all` scan; request GitHub's `state=all` value rather than collapsing all non-open choices to `closed`.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,352 @@
+#!/usr/bin/env python3
+"""Review Dump — collect PR review threads into LLM-readable JSON + Markdown.
+
+Extends collect_review_comments.py (which writes to Supabase) with:
+  - GraphQL review threads (resolved state + reply chains — REST misses these)
+  - Committable-suggestion extraction (CodeRabbit ```suggestion blocks)
+  - Diff context (the diff_hunk around each comment)
+  - Structured JSON export for tooling
+  - Human/LLM-readable Markdown export for local analysis
+  - Optional fan-out to Hi-RAG (POST /hirag/upsert-batch) and Cipher (POST /api/memory)
+
+Usage:
+    # Dump a single PR to local files:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434
+
+    # Dump all open PRs:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --state open
+
+    # Dump + ingest into Hi-RAG and Cipher:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --ingest-hirag --ingest-cipher
+
+    # Dry-run (collect + export, no ingestion):
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --dry-run
+
+Output files land in pmoves/docs/logs/review-dumps/<repo>-<pr>.{json,md} by default.
+"""
+
+from __future__ import annotations
+
+import argparse
+import json
+import os
+import re
+import sys
+import urllib.request
+import urllib.error
+from datetime import datetime, timezone
+from pathlib import Path
+from typing import Any
+
+_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
+if str(_REPO_ROOT) not in sys.path:
+    sys.path.insert(0, str(_REPO_ROOT))
+
+GITHUB_ORG = os.environ.get("PMOVES_GITHUB_ORG", "POWERFULMOVES")
+GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
+HIRAG_URL = os.environ.get("HIRAG_UPSERT_URL") or os.environ.get("HIRAG_URL", "http://localhost:8086")
+CIPHER_URL = os.environ.get("CIPHER_API_URL", "http://localhost:8105")
+CIPHER_TOKEN = os.environ.get("CIPHER_API_TOKEN", "")
+OUTPUT_DIR = Path(os.environ.get("REVIEW_DUMP_DIR", _REPO_ROOT / "pmoves" / "docs" / "logs" / "review-dumps"))
+
+SEVERITY_RE = re.compile(r"(?:P(\d)\s+Badge|severity[:\s]*(P\d))", re.IGNORECASE)
+SUGGESTION_RE = re.compile(r"```suggestion\n(.*?)```", re.DOTALL)
+NITPICK_RE = re.compile(r"\b(nitpick|nit\b)", re.IGNORECASE)
+
+
+def _gh_headers() -> dict[str, str]:
+    if not GITHUB_TOKEN:
+        raise SystemExit("ERROR: GH_TOKEN or GITHUB_TOKEN not set")
+    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
+
+
+def gh_rest(path: str) -> Any:
+    req = urllib.request.Request(f"https://api.github.com{path}", headers=_gh_headers())
+    try:
+        return json.loads(urllib.request.urlopen(req, timeout=30).read())
+    except urllib.error.HTTPError as e:
+        if e.code == 404:
+            return []
+        raise
+
+
+def gh_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
+    body = json.dumps({"query": query, "variables": variables}).encode()
+    req = urllib.request.Request(
+        "https://api.github.com/graphql",
+        data=body,
+        headers={**_gh_headers(), "Content-Type": "application/json"},
+    )
+    return json.loads(urllib.request.urlopen(req, timeout=30).read())
+
+
+THREADS_QUERY = """
+query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
+  repository(owner: $owner, name: $name) {
+    pullRequest(number: $number) {
+      title state mergedAt headRefName baseRefName additions deletions changedFiles
+      author { login }
+      reviewThreads(first: 100, after: $cursor) {
+        pageInfo { hasNextPage endCursor }
+        nodes {
+          id isResolved isOutdated path line
+          comments(first: 20) {
+            nodes {
+              databaseId author { login } body path line originalLine diffHunk createdAt url
+            }
+          }
+        }
+      }
+      reviews(first: 50) {
+        nodes { author { login } state body submittedAt }
+      }
+    }
+  }
+}
+"""
+
+
+def fetch_threads(repo: str, pr_number: int) -> dict[str, Any]:
+    owner, *rest = repo.split("/", 1)
+    name = rest[0] if rest else repo
+    result: dict[str, Any] = {}
+    cursor = None
+    while True:
+        data = gh_graphql(THREADS_QUERY, {"owner": owner, "name": name, "number": pr_number, "cursor": cursor})
+        pr = data["data"]["repository"]["pullRequest"]
+        if not pr:
+            raise SystemExit(f"ERROR: PR {repo}#{pr_number} not found")
+        if not result:
+            result = {
+                "repo": repo, "pr_number": pr_number, "title": pr["title"], "state": pr["state"],
+                "merged_at": pr.get("mergedAt"), "branch": pr["headRefName"], "base": pr["baseRefName"],
+                "additions": pr["additions"], "deletions": pr["deletions"], "changed_files": pr["changedFiles"],
+                "author": (pr.get("author") or {}).get("login", "unknown"),
+                "collected_at": datetime.now(timezone.utc).isoformat(),
+                "threads": [],
+                "reviews": [
+                    {"author": (r.get("author") or {}).get("login", "unknown"), "state": r["state"],
+                     "body": r.get("body") or "", "submitted_at": r.get("submittedAt")}
+                    for r in pr.get("reviews", {}).get("nodes", [])
+                ],
+            }
+        result["threads"].extend(pr["reviewThreads"]["nodes"])
+        if pr["reviewThreads"]["pageInfo"]["hasNextPage"]:
+            cursor = pr["reviewThreads"]["pageInfo"]["endCursor"]
+        else:
+            break
+    return result
+
+
+def extract_severity(body: str) -> str:
+    m = SEVERITY_RE.search(body)
+    if m:
+        for g in m.groups():
+            if g and g.isdigit():
+                return f"P{g}"
+    if NITPICK_RE.search(body):
+        return "nitpick"
+    low = body.lower()
+    if "praise" in low:
+        return "praise"
+    if "question" in low:
+        return "question"
+    return "unclassified"
+
+
+def extract_suggestions(body: str) -> list[str]:
+    return [m.group(1).rstrip() for m in SUGGESTION_RE.finditer(body)]
+
+
+def classify_author(author: str) -> str:
+    if "[bot]" in author or author in {"coderabbitai", "chatgpt-codex-connector", "github-actions", "dependabot"}:
+        return "bot"
+    return "human"
+
+
+def thread_to_record(thread: dict[str, Any]) -> dict[str, Any]:
+    comments = thread.get("comments", {}).get("nodes", [])
+    if not comments:
+        return {}
+    first = comments[0]
+    body = first.get("body", "")
+    path = thread.get("path") or first.get("path")
+    line = thread.get("line") or first.get("line") or first.get("originalLine")
+    replies = [
+        {"author": (r.get("author") or {}).get("login", "unknown"), "body": r.get("body", ""), "created_at": r.get("createdAt")}
+        for r in comments[1:]
+    ]
+    return {
+        "thread_id": thread["id"], "is_resolved": thread.get("isResolved", False),
+        "is_outdated": thread.get("isOutdated", False), "path": path, "line": line,
+        "severity": extract_severity(body),
+        "author": (first.get("author") or {}).get("login", "unknown"),
+        "author_type": classify_author((first.get("author") or {}).get("login", "unknown")),
+        "body": body, "suggestions": extract_suggestions(body),
+        "diff_hunk": first.get("diffHunk", ""), "replies": replies,
+        "url": first.get("url", ""), "created_at": first.get("createdAt"),
+    }
+
+
+def export_json(data: dict[str, Any], path: Path) -> None:
+    path.parent.mkdir(parents=True, exist_ok=True)
+    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
+
+
+def export_markdown(data: dict[str, Any], path: Path) -> None:
+    lines: list[str] = []
+    repo, pr = data["repo"], data["pr_number"]
+    lines.append(f"# Review Dump — {repo}#{pr}\n\n**{data['title']}**\n\n")
+    lines.append(f"- State: `{data['state']}` | Branch: `{data['branch']}` → `{data['base']}` | "
+                 f"+{data['additions']}/-{data['deletions']} ({data['changed_files']} files)\n")
+    lines.append(f"- Author: {data['author']} | Collected: {data['collected_at']}\n")
+    records = data.get("thread_records", [])
+    resolved = sum(1 for r in records if r["is_resolved"])
+    actionable = [r for r in records if r["severity"] in ("P1", "P2") and not r["is_resolved"]]
+    suggestions = [s for r in records for s in r["suggestions"]]
+    lines.append(f"\n## Summary\n\n| Metric | Count |\n|---|---|\n")
+    lines.append(f"| Total threads | {len(records)} |\n| Resolved | {resolved} |\n")
+    lines.append(f"| Open P1/P2 (actionable) | {len(actionable)} |\n| Committable suggestions | {len(suggestions)} |\n")
+    sev_counts: dict[str, int] = {}
+    for r in records:
+        sev_counts[r["severity"]] = sev_counts.get(r["severity"], 0) + 1
+    if sev_counts:
+        lines.append(f"\n**Severity breakdown:** {', '.join(f'{k}={v}' for k, v in sorted(sev_counts.items()))}\n")
+    if data.get("reviews"):
+        lines.append(f"\n## Reviews ({len(data['reviews'])})\n\n")
+        for rev in data["reviews"]:
+            lines.append(f"- **{rev['author']}** ({rev['state']}) — {(rev.get('body') or '')[:200].replace(chr(10), ' ')}\n")
+    if not records:
+        lines.append(f"\n*No review threads found.*\n")
+    else:
+        lines.append(f"\n## Threads\n\n")
+        for i, r in enumerate(records, 1):
+            status = "✅" if r["is_resolved"] else ("⚠️" if r["is_outdated"] else "🔴")
+            lines.append(f"### {i}. {status} [{r['severity']}] {r['author']} — `{r['path']}:{r['line']}`\n\n")
+            lines.append(f"{r['body'][:2000]}\n\n")
+            if r["suggestions"]:
+                lines.append(f"**Committable suggestion(s):**\n\n")
+                for s in r["suggestions"]:
+                    lines.append(f"```suggestion\n{s}\n```\n\n")
+            if r["diff_hunk"]:
+                lines.append(f"<details><summary>Diff context</summary>\n\n```diff\n{r['diff_hunk']}\n```\n\n</details>\n\n")
+            if r["replies"]:
+                lines.append(f"<details><summary>{len(r['replies'])} repl{'y' if len(r['replies'])==1 else 'ies'}</summary>\n\n")
+                for rep in r["replies"]:
+                    lines.append(f"- **{rep['author']}**: {rep['body'][:300]}\n")
+                lines.append(f"\n</details>\n\n")
+            if r["url"]:
+                lines.append(f"[→ thread]({r['url']})\n\n")
+    path.parent.mkdir(parents=True, exist_ok=True)
+    path.write_text("".join(lines), encoding="utf-8")
+
+
+def _record_to_text(r: dict[str, Any], pr_data: dict[str, Any]) -> str:
+    parts = [
+        f"PR {pr_data['repo']}#{pr_data['pr_number']}: {pr_data['title']}",
+        f"Severity: {r['severity']} | Author: {r['author']} | Resolved: {r['is_resolved']}",
+    ]
+    if r.get("path"):
+        parts.append(f"Location: {r['path']}:{r['line']}")
+    parts.append(f"\n{r['body']}")
+    if r["suggestions"]:
+        parts.append("\nSuggested fix:")
+        for s in r["suggestions"]:
+            parts.append(f"  {s[:200]}")
+    return "\n".join(parts)
+
+
+def ingest_hirag(records: list[dict[str, Any]], pr_data: dict[str, Any]) -> int:
+    items = [{
+        "id": f"review-{pr_data['repo']}-{pr_data['pr_number']}-{r['thread_id'][-12:]}",
+        "content": _record_to_text(r, pr_data),
+        "metadata": {"type": "review_comment", "repo": pr_data["repo"], "pr_number": pr_data["pr_number"],
+                     "severity": r["severity"], "path": r.get("path"), "author": r["author"], "is_resolved": r["is_resolved"]},
+    } for r in records]
+    body = json.dumps({"items": items}).encode()
+    req = urllib.request.Request(f"{HIRAG_URL}/hirag/upsert-batch", data=body,
+                                 headers={"Content-Type": "application/json"}, method="POST")
+    try:
+        urllib.request.urlopen(req, timeout=30)
+        return len(items)
+    except Exception as e:
+        print(f"  [hirag] error: {e}", file=sys.stderr)
+        return 0
+
+
+def ingest_cipher(records: list[dict[str, Any]], pr_data: dict[str, Any]) -> int:
+    if not CIPHER_TOKEN:
+        print("  [cipher] skip: CIPHER_API_TOKEN not set", file=sys.stderr)
+        return 0
+    count = 0
+    for r in records:
+        if r["severity"] not in ("P1", "P2"):
+            continue
+        body = json.dumps({
+            "agentId": "review-collector", "category": "review_learning",
+            "content": _record_to_text(r, pr_data),
+            "metadata": {"repo": pr_data["repo"], "pr_number": pr_data["pr_number"],
+                         "severity": r["severity"], "path": r.get("path"), "thread_id": r["thread_id"]},
+            "tags": ["review", r["severity"], pr_data["repo"], "pr-learning"],
+        }).encode()
+        req = urllib.request.Request(f"{CIPHER_URL}/api/memory", data=body,
+                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {CIPHER_TOKEN}"},
+                                     method="POST")
+        try:
+            urllib.request.urlopen(req, timeout=10)
+            count += 1
+        except Exception as e:
+            print(f"  [cipher] error on thread {r['thread_id'][-8:]}: {e}", file=sys.stderr)
+    return count
+
+
+def dump_pr(repo: str, pr_number: int, dry_run: bool, ingest: bool) -> dict[str, Any]:
+    full_repo = f"{GITHUB_ORG}/{repo}" if "/" not in repo else repo
+    print(f"[review-dump] {full_repo}#{pr_number}")
+    data = fetch_threads(full_repo, pr_number)
+    records = [t for t in (thread_to_record(t) for t in data["threads"]) if t]
+    data["thread_records"] = records
+    slug = repo.replace("/", "-")
+    json_path = OUTPUT_DIR / f"{slug}-{pr_number}.json"
+    md_path = OUTPUT_DIR / f"{slug}-{pr_number}.md"
+    export_json(data, json_path)
+    export_markdown(data, md_path)
+    print(f"  exported: {json_path.relative_to(_REPO_ROOT)}")
+    print(f"  exported: {md_path.relative_to(_REPO_ROOT)}")
+    print(f"  threads: {len(records)} ({sum(1 for r in records if r['is_resolved'])} resolved, "
+          f"{sum(1 for r in records if r['severity'] in ('P1','P2') and not r['is_resolved'])} open P1/P2, "
+          f"{sum(len(r['suggestions']) for r in records)} suggestions)")
+    if ingest and not dry_run:
+        n = ingest_hirag(records, data)
+        print(f"  [hirag] ingested {n} records")
+        n = ingest_cipher(records, data)
+        print(f"  [cipher] ingested {n} P1/P2 learnings")
+    return data
+
+
+def main() -> None:
+    parser = argparse.ArgumentParser(description="Collect PR review threads into LLM-readable JSON + Markdown")
+    parser.add_argument("--repo", required=True, help="Repo name (e.g. PMOVES.AI, Pmoves-cipher)")
+    parser.add_argument("--pr", type=int, help="Single PR number")
+    parser.add_argument("--state", default="open", choices=["open", "merged", "closed", "all"])
+    parser.add_argument("--limit", type=int, default=10, help="Max PRs to scan (when not --pr)")
+    parser.add_argument("--dry-run", action="store_true", help="Collect + export only, no ingestion")
+    parser.add_argument("--ingest-hirag", action="store_true", help="Fan out to Hi-RAG")
+    parser.add_argument("--ingest-cipher", action="store_true", help="Fan out to Cipher memory")
+    args = parser.parse_args()
+    ingest = args.ingest_hirag or args.ingest_cipher
+    if args.pr:
+        dump_pr(args.repo, args.pr, args.dry_run, ingest)
+        return
+    gh_state = "open" if args.state == "open" else "closed"
+    full_repo = f"{GITHUB_ORG}/{args.repo}" if "/" not in args.repo else args.repo
+    prs = gh_rest(f"/repos/{full_repo}/pulls?state={gh_state}&per_page={min(args.limit, 100)}&sort=updated&direction=desc")
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730573137)

### 7. ✅ [P2] chatgpt-codex-connector — `pmoves/tools/review_dump.py:96`

**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Paginate comments within each review thread**

For any review thread containing more than 20 comments, this query returns only the first page and requests no comment `pageInfo`, so later replies are silently absent from both exports and downstream ingestion. This contradicts the collector's reply-chain guarantee and can omit the final discussion or fix confirmation; paginate the thread's comments or request enough data through a separate paginated query.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,352 @@
+#!/usr/bin/env python3
+"""Review Dump — collect PR review threads into LLM-readable JSON + Markdown.
+
+Extends collect_review_comments.py (which writes to Supabase) with:
+  - GraphQL review threads (resolved state + reply chains — REST misses these)
+  - Committable-suggestion extraction (CodeRabbit ```suggestion blocks)
+  - Diff context (the diff_hunk around each comment)
+  - Structured JSON export for tooling
+  - Human/LLM-readable Markdown export for local analysis
+  - Optional fan-out to Hi-RAG (POST /hirag/upsert-batch) and Cipher (POST /api/memory)
+
+Usage:
+    # Dump a single PR to local files:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434
+
+    # Dump all open PRs:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --state open
+
+    # Dump + ingest into Hi-RAG and Cipher:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --ingest-hirag --ingest-cipher
+
+    # Dry-run (collect + export, no ingestion):
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --dry-run
+
+Output files land in pmoves/docs/logs/review-dumps/<repo>-<pr>.{json,md} by default.
+"""
+
+from __future__ import annotations
+
+import argparse
+import json
+import os
+import re
+import sys
+import urllib.request
+import urllib.error
+from datetime import datetime, timezone
+from pathlib import Path
+from typing import Any
+
+_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
+if str(_REPO_ROOT) not in sys.path:
+    sys.path.insert(0, str(_REPO_ROOT))
+
+GITHUB_ORG = os.environ.get("PMOVES_GITHUB_ORG", "POWERFULMOVES")
+GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
+HIRAG_URL = os.environ.get("HIRAG_UPSERT_URL") or os.environ.get("HIRAG_URL", "http://localhost:8086")
+CIPHER_URL = os.environ.get("CIPHER_API_URL", "http://localhost:8105")
+CIPHER_TOKEN = os.environ.get("CIPHER_API_TOKEN", "")
+OUTPUT_DIR = Path(os.environ.get("REVIEW_DUMP_DIR", _REPO_ROOT / "pmoves" / "docs" / "logs" / "review-dumps"))
+
+SEVERITY_RE = re.compile(r"(?:P(\d)\s+Badge|severity[:\s]*(P\d))", re.IGNORECASE)
+SUGGESTION_RE = re.compile(r"```suggestion\n(.*?)```", re.DOTALL)
+NITPICK_RE = re.compile(r"\b(nitpick|nit\b)", re.IGNORECASE)
+
+
+def _gh_headers() -> dict[str, str]:
+    if not GITHUB_TOKEN:
+        raise SystemExit("ERROR: GH_TOKEN or GITHUB_TOKEN not set")
+    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
+
+
+def gh_rest(path: str) -> Any:
+    req = urllib.request.Request(f"https://api.github.com{path}", headers=_gh_headers())
+    try:
+        return json.loads(urllib.request.urlopen(req, timeout=30).read())
+    except urllib.error.HTTPError as e:
+        if e.code == 404:
+            return []
+        raise
+
+
+def gh_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
+    body = json.dumps({"query": query, "variables": variables}).encode()
+    req = urllib.request.Request(
+        "https://api.github.com/graphql",
+        data=body,
+        headers={**_gh_headers(), "Content-Type": "application/json"},
+    )
+    return json.loads(urllib.request.urlopen(req, timeout=30).read())
+
+
+THREADS_QUERY = """
+query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
+  repository(owner: $owner, name: $name) {
+    pullRequest(number: $number) {
+      title state mergedAt headRefName baseRefName additions deletions changedFiles
+      author { login }
+      reviewThreads(first: 100, after: $cursor) {
+        pageInfo { hasNextPage endCursor }
+        nodes {
+          id isResolved isOutdated path line
+          comments(first: 20) {
+            nodes {
+              databaseId author { login } body path line originalLine diffHunk createdAt url
+            }
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730573145)

### 8. 🔴 [unclassified] coderabbitai — `.github/workflows/review-collect.yml:51`

_🔒 Security & Privacy_ | _🟠 Major_ | _⚡ Quick win_

<details>
<summary>🧩 Analysis chain</summary>

🏁 Script executed:

```shell
#!/bin/bash
set -euo pipefail

ast-grep outline .github/workflows/_app-token.yml --items all
sed -n '1,240p' .github/workflows/_app-token.yml
rg -n -C 5 --glob '*.yml' 'repositories:|permission-pull-requests|create-github-app-token|inputs\.repo' .github/workflows
```

Repository: POWERFULMOVES/PMOVES.AI

Length of output: 28550

---

🏁 Script executed:

```shell
#!/bin/bash
set -euo pipefail

echo "== review-collect.yml =="
sed -n '1,140p' .github/workflows/review-collect.yml

echo "== workflow definitions for review-collect =="
python3 - <<'PY'
from pathlib import Path
p=Path('.github/workflows/review-collect.yml')
text=p.read_text()
for needle in ['on:', 'workflow_dispatch:', 'permissions:', 'name:', 'workflow_call:', 'repository_dispatch:']:
    print(f'{needle!r}: {needle in text}')
PY

rg -n "review-collect|review-collect\.yml|workflow_dispatch|workflow_call:|repository_dispatch:" .github/workflows
```

Repository: POWERFULMOVES/PMOVES.AI

Length of output: 8563

---

🌐 Web query:

`GitHub create-github-app-token repositories parameter syntax repository name`

💡 Result:

In the `actions/create-github-app-token` GitHub Action, the `repositories` input accepts a list of repositories to grant the token access to [1][2]. The syntax and usage guidelines are as follows: Format The `repositories` input accepts either a comma-separated or newline-separated string [1][2][3]. Repository Name Syntax Entries can be provided as: - Bare repository names (e.g., `repo1`) [2][4]. - Full repository names in `owner/repo` format (e.g., `my-org/repo1`) [2][4]. Constraints and Behavior - Owner Consistency: When using the full `owner/repo` format, the owner portion must match the `owner` input (or the current repository owner if `owner` is unset) [2][4]. If the owner does not match, the action will reject the entry [4][5]. - Token Scoping: The action generat

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,106 @@
+name: Review Collect
+
+# Collects PR review threads (CodeRabbit, Codex, human) into LLM-readable
+# JSON + Markdown artifacts using the GitHub App token for auth.
+#
+# REPLACES the disabled review-comment-monitor.yml (which depended on
+# ANTHROPIC_API_KEY for Claude triage). This workflow is pure Python —
+# no API key needed beyond the App token. The App token provides
+# pull-requests:read scope to fetch review threads via GraphQL.
+#
+# Artifacts are uploaded for download and optionally committed to
+# pmoves/docs/logs/review-dumps/ for searchability.
+#
+# Ingestion into Hi-RAG/Cipher is OPT-IN via repository variables
+# (PMOVES_REVIEW_INGEST_HIRAG / PMOVES_REVIEW_INGEST_CIPHER).
+
+on:
+  pull_request_review:
+    types: [submitted]
+  pull_request_review_comment:
+    types: [created]
+  schedule:
+    # Every 2 hours — catches threads posted between events
+    - cron: "0 */2 * * *"
+  workflow_dispatch:
+    inputs:
+      repo:
+        description: "Repo name (default: current repo)"
+        required: false
+        default: ""
+      pr:
+        description: "Single PR number (blank = all open)"
+        required: false
+
+concurrency:
+  group: review-collect-${{ github.event.pull_request.number || github.run_id }}
+  cancel-in-progress: false
+
+permissions:
+  contents: read
+  pull-requests: read
+
+jobs:
+  # P1 fix: _app-token.yml is a reusable workflow — must be called at job
+  # level via `uses:`, not as a step-level action. This is the same pattern
+  # used by pat-health-check.yml and pr-closeout.yml.
+  token:
+    uses: ./.github/workflows/_app-token.yml
+    with:
+      owner: ${{ github.repository_owner }}
+      repositories: ${{ inputs.repo || github.event.repository.name }}
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730770869)

### 9. 🔴 [unclassified] coderabbitai — `.github/workflows/review-collect.yml:73`

_🗄️ Data Integrity & Integration_ | _🟠 Major_ | _⚡ Quick win_

**Provide the selected ingestion services with their required configuration.**

The job sets ingestion flags only. It never sets `CIPHER_API_TOKEN`, so Cipher always skips. It never sets a Hi-RAG endpoint, so Hi-RAG uses `http://localhost:8086`, where no service is started on this GitHub-hosted runner.

Map the service URLs and Cipher token into this job. Fail the workflow when explicitly enabled ingestion cannot authenticate or reach its target.

<details>
<summary>Proposed fix</summary>

```diff
         env:
           GH_TOKEN: ${{ needs.token.outputs.token }}
           PMOVES_GITHUB_ORG: ${{ github.repository_owner }}
+          HIRAG_UPSERT_URL: ${{ vars.HIRAG_UPSERT_URL }}
+          CIPHER_API_URL: ${{ vars.CIPHER_API_URL }}
+          CIPHER_API_TOKEN: ${{ secrets.CIPHER_API_TOKEN }}
           INGEST_HIRAG: ${{ vars.PMOVES_REVIEW_INGEST_HIRAG }}
           INGEST_CIPHER: ${{ vars.PMOVES_REVIEW_INGEST_CIPHER }}
```
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In @.github/workflows/review-collect.yml around lines 68 - 73, Update the
workflow job environment near INGEST_HIRAG and INGEST_CIPHER to provide the
configured Hi-RAG endpoint and CIPHER_API_TOKEN, using the
repository/environment variables or secrets that hold those values. Ensure
explicitly enabled ingestion validates authentication and target reachability
and fails the workflow when either service cannot be contacted; preserve opt-in
behavior when ingestion is disabled.
```

</details>

<!-- fingerprinting:phantom:medusa:tapir -->

<!-- cr-indicator-types:potential_issue -->

<!-- cr-comment:v1:968f979ad1e28c07aae93fba -->

<!-- This is an auto-generated comment by CodeRabbit -->

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,106 @@
+name: Review Collect
+
+# Collects PR review threads (CodeRabbit, Codex, human) into LLM-readable
+# JSON + Markdown artifacts using the GitHub App token for auth.
+#
+# REPLACES the disabled review-comment-monitor.yml (which depended on
+# ANTHROPIC_API_KEY for Claude triage). This workflow is pure Python —
+# no API key needed beyond the App token. The App token provides
+# pull-requests:read scope to fetch review threads via GraphQL.
+#
+# Artifacts are uploaded for download and optionally committed to
+# pmoves/docs/logs/review-dumps/ for searchability.
+#
+# Ingestion into Hi-RAG/Cipher is OPT-IN via repository variables
+# (PMOVES_REVIEW_INGEST_HIRAG / PMOVES_REVIEW_INGEST_CIPHER).
+
+on:
+  pull_request_review:
+    types: [submitted]
+  pull_request_review_comment:
+    types: [created]
+  schedule:
+    # Every 2 hours — catches threads posted between events
+    - cron: "0 */2 * * *"
+  workflow_dispatch:
+    inputs:
+      repo:
+        description: "Repo name (default: current repo)"
+        required: false
+        default: ""
+      pr:
+        description: "Single PR number (blank = all open)"
+        required: false
+
+concurrency:
+  group: review-collect-${{ github.event.pull_request.number || github.run_id }}
+  cancel-in-progress: false
+
+permissions:
+  contents: read
+  pull-requests: read
+
+jobs:
+  # P1 fix: _app-token.yml is a reusable workflow — must be called at job
+  # level via `uses:`, not as a step-level action. This is the same pattern
+  # used by pat-health-check.yml and pr-closeout.yml.
+  token:
+    uses: ./.github/workflows/_app-token.yml
+    with:
+      owner: ${{ github.repository_owner }}
+      repositories: ${{ inputs.repo || github.event.repository.name }}
+      permission-pull-requests: read
+      permission-contents: read
+    secrets: inherit
+
+  collect:
+    needs: token
+    runs-on: ubuntu-latest
+    timeout-minutes: 5
+    steps:
+      - name: Checkout repository
+        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
+        with:
+          token: ${{ needs.token.outputs.token }}
+          fetch-depth: 0
+
+      - name: Collect review threads
+        env:
+          GH_TOKEN: ${{ needs.token.outputs.token }}
+          PMOVES_GITHUB_ORG: ${{ github.repository_owner }}
+          # P2 fix: wire opt-in ingestion variables into the command
+          INGEST_HIRAG: ${{ vars.PMOVES_REVIEW_INGEST_HIRAG }}
+          INGEST_CIPHER: ${{ vars.PMOVES_REVIEW_INGEST_CIPHER }}
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730770880)

### 10. 🔴 [unclassified] coderabbitai — `.github/workflows/review-collect.yml:77`

_🔒 Security & Privacy_ | _🔴 Critical_ | _⚡ Quick win_

**Move workflow inputs out of shell template expansion.**

A manual dispatcher can supply shell syntax in `inputs.repo` or `inputs.pr`. GitHub expands these expressions before Bash parses the script. The injected command can read `GH_TOKEN` and exfiltrate it.

Pass the expressions through `env`, then reference quoted shell variables.

<details>
<summary>Proposed fix</summary>

```diff
         env:
           GH_TOKEN: ${{ needs.token.outputs.token }}
+          DISPATCH_REPO: ${{ inputs.repo || github.event.repository.name }}
+          DISPATCH_PR: ${{ inputs.pr || github.event.pull_request.number || '' }}
           PMOVES_GITHUB_ORG: ${{ github.repository_owner }}
@@
-          REPO="${{ inputs.repo || github.event.repository.name }}"
-          PR="${{ inputs.pr || github.event.pull_request.number || '' }}"
+          REPO="$DISPATCH_REPO"
+          PR="$DISPATCH_PR"
```
</details>

<!-- suggestion_start -->

<details>
<summary>📝 Committable suggestion</summary>

> ‼️ **IMPORTANT**
> Carefully review the code before committing. Ensure that it accurately replaces the highlighted code, contains no missing lines, and has no issues with indentation. Thoroughly test & benchmark the code to ensure it meets the requirements.

```suggestion
        env:
          GH_TOKEN: ${{ needs.token.outputs.token }}
          DISPATCH_REPO: ${{ inputs.repo || github.event.repository.name }}
          DISPATCH_PR: ${{ inputs.pr || github.event.pull_request.number || '' }}
          PMOVES_GITHUB_ORG: ${{ github.repository_owner }}

          REPO="$DISPATCH_REPO"
          PR="$DISPATCH_PR"
```

</details>

<!-- suggestion_end -->

<details>
<summary>🧰 Tools</summary>

<details>
<summary>🪛 zizmor (1.29.0)</summary>

[error] 76-76: code injection via template expansion (template-injection): may expand into attacker-controllable code

(template-injection)

---

[error] 76-76: code injection via template expansion (template-inje

**Committable suggestion(s):**

```suggestion
        env:
          GH_TOKEN: ${{ needs.token.outputs.token }}
          DISPATCH_REPO: ${{ inputs.repo || github.event.repository.name }}
          DISPATCH_PR: ${{ inputs.pr || github.event.pull_request.number || '' }}
          PMOVES_GITHUB_ORG: ${{ github.repository_owner }}

          REPO="$DISPATCH_REPO"
          PR="$DISPATCH_PR"
```

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,106 @@
+name: Review Collect
+
+# Collects PR review threads (CodeRabbit, Codex, human) into LLM-readable
+# JSON + Markdown artifacts using the GitHub App token for auth.
+#
+# REPLACES the disabled review-comment-monitor.yml (which depended on
+# ANTHROPIC_API_KEY for Claude triage). This workflow is pure Python —
+# no API key needed beyond the App token. The App token provides
+# pull-requests:read scope to fetch review threads via GraphQL.
+#
+# Artifacts are uploaded for download and optionally committed to
+# pmoves/docs/logs/review-dumps/ for searchability.
+#
+# Ingestion into Hi-RAG/Cipher is OPT-IN via repository variables
+# (PMOVES_REVIEW_INGEST_HIRAG / PMOVES_REVIEW_INGEST_CIPHER).
+
+on:
+  pull_request_review:
+    types: [submitted]
+  pull_request_review_comment:
+    types: [created]
+  schedule:
+    # Every 2 hours — catches threads posted between events
+    - cron: "0 */2 * * *"
+  workflow_dispatch:
+    inputs:
+      repo:
+        description: "Repo name (default: current repo)"
+        required: false
+        default: ""
+      pr:
+        description: "Single PR number (blank = all open)"
+        required: false
+
+concurrency:
+  group: review-collect-${{ github.event.pull_request.number || github.run_id }}
+  cancel-in-progress: false
+
+permissions:
+  contents: read
+  pull-requests: read
+
+jobs:
+  # P1 fix: _app-token.yml is a reusable workflow — must be called at job
+  # level via `uses:`, not as a step-level action. This is the same pattern
+  # used by pat-health-check.yml and pr-closeout.yml.
+  token:
+    uses: ./.github/workflows/_app-token.yml
+    with:
+      owner: ${{ github.repository_owner }}
+      repositories: ${{ inputs.repo || github.event.repository.name }}
+      permission-pull-requests: read
+      permission-contents: read
+    secrets: inherit
+
+  collect:
+    needs: token
+    runs-on: ubuntu-latest
+    timeout-minutes: 5
+    steps:
+      - name: Checkout repository
+        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
+        with:
+          token: ${{ needs.token.outputs.token }}
+          fetch-depth: 0
+
+      - name: Collect review threads
+        env:
+          GH_TOKEN: ${{ needs.token.outputs.token }}
+          PMOVES_GITHUB_ORG: ${{ github.repository_owner }}
+          # P2 fix: wire opt-in ingestion variables into the command
+          INGEST_HIRAG: ${{ vars.PMOVES_REVIEW_INGEST_HIRAG }}
+          INGEST_CIPHER: ${{ vars.PMOVES_REVIEW_INGEST_CIPHER }}
+        run: |
+          # P2 fix: honor workflow_dispatch repo input; fall back to event repo
+          REPO="${{ inputs.repo || github.event.repository.name }}"
+          PR="${{ inputs.pr || github.event.pull_request.number || '' }}"
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730770886)

### 11. 🔴 [unclassified] coderabbitai — `pmoves/mk/review.mk:3`

_🎯 Functional Correctness_ | _🟡 Minor_ | _⚡ Quick win_

**Align `.PHONY` with the implemented targets.**

`review-dump-latest` has no recipe, so `make review-dump-latest` succeeds without collecting anything. `review-dump-ingest` has a recipe but is not phony, so a file with that name can suppress ingestion.

<details>
<summary>Proposed fix</summary>

```diff
-.PHONY: review-dump review-dump-all review-dump-latest review-collect-help
+.PHONY: review-dump review-dump-all review-dump-ingest review-collect-help
```
</details>

<!-- suggestion_start -->

<details>
<summary>📝 Committable suggestion</summary>

> ‼️ **IMPORTANT**
> Carefully review the code before committing. Ensure that it accurately replaces the highlighted code, contains no missing lines, and has no issues with indentation. Thoroughly test & benchmark the code to ensure it meets the requirements.

```suggestion
.PHONY: review-dump review-dump-all review-dump-ingest review-collect-help
```

</details>

<!-- suggestion_end -->

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@pmoves/mk/review.mk` at line 3, Update the .PHONY declaration to remove
review-dump-latest, which has no recipe, and add review-dump-ingest so its
recipe always runs even when a file with that name exists. Keep the other
implemented phony targets unchanged.
```

</details>

<!-- fingerprinting:phantom:medusa:tapir -->

<!-- cr-indicator-types:potential_issue -->

<!-- cr-comment:v1:90eca25357e8fed91aef85b1 -->

<!-- This is an auto-generated comment by CodeRabbit -->

**Committable suggestion(s):**

```suggestion
.PHONY: review-dump review-dump-all review-dump-ingest review-collect-help
```

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,40 @@
+# review.mk — Review collection and dump targets
+
+.PHONY: review-dump review-dump-all review-dump-latest review-collect-help
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730770904)

### 12. 🔴 [unclassified] coderabbitai — `pmoves/mk/review.mk:30`

_🩺 Stability & Availability_ | _🟠 Major_ | _⚡ Quick win_

**Return failure when any repository collection fails.**

`2>/dev/null || true` discards authentication, API, and export failures. The target reports success even when it creates no review dump.

Continue processing other repositories if needed, but retain a failure flag and exit non-zero after the loop.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@pmoves/mk/review.mk` around lines 28 - 30, Update the repository loop in the
review dump target to track whether any `pmoves.tools.review_dump` invocation
fails, while continuing to process remaining repositories. Remove the
unconditional success suppression, set a failure flag for command errors, and
return a non-zero status after the loop when any collection failed.
```

</details>

<!-- fingerprinting:phantom:medusa:tapir -->

<!-- cr-indicator-types:potential_issue -->

<!-- cr-comment:v1:473a5f28442e82628e1c5d61 -->

<!-- This is an auto-generated comment by CodeRabbit -->

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,40 @@
+# review.mk — Review collection and dump targets
+
+.PHONY: review-dump review-dump-all review-dump-latest review-collect-help
+
+REVIEW_REPO ?= PMOVES.AI
+REVIEW_PR ?=
+REVIEW_STATE ?= open
+REVIEW_LIMIT ?= 20
+
+## Review dump: collect PR threads into LLM-readable JSON + Markdown
+review-dump:
+ifdef REVIEW_PR
+	@bash scripts/with-env.sh python -m pmoves.tools.review_dump --repo $(REVIEW_REPO) --pr $(REVIEW_PR) --dry-run
+else
+	@bash scripts/with-env.sh python -m pmoves.tools.review_dump --repo $(REVIEW_REPO) --state $(REVIEW_STATE) --limit $(REVIEW_LIMIT) --dry-run
+endif
+
+## Review dump with Hi-RAG + Cipher ingestion (requires services up)
+review-dump-ingest:
+ifdef REVIEW_PR
+	@bash scripts/with-env.sh python -m pmoves.tools.review_dump --repo $(REVIEW_REPO) --pr $(REVIEW_PR) --ingest-hirag --ingest-cipher
+else
+	@bash scripts/with-env.sh python -m pmoves.tools.review_dump --repo $(REVIEW_REPO) --state $(REVIEW_STATE) --limit $(REVIEW_LIMIT) --ingest-hirag --ingest-cipher
+endif
+
+## Dump all open PRs across the org
+review-dump-all:
+	@for repo in PMOVES.AI PMOVES-Agent-Zero PMOVES-Archon PMOVES-BoTZ PMOVES-Creator PMOVES-HiRAG PMOVES-ToKenism-Multi PMOVES-DoX; do \
+		echo "--- $$repo ---"; \
+		bash scripts/with-env.sh python -m pmoves.tools.review_dump --repo $$repo --state open --limit 5 --dry-run 2>/dev/null || true; \
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730770909)

### 13. 🔴 [unclassified] coderabbitai — `pmoves/tools/review_dump.py:97`

_🗄️ Data Integrity & Integration_ | _🟠 Major_ | _🏗️ Heavy lift_

**Paginate review-thread comments or mark the report as truncated.**

`comments(first: 20)` has no `pageInfo`. A thread with more than 20 comments silently loses later replies. This conflicts with the reply-chain export contract.

Fetch subsequent comment pages for each thread. Alternatively, emit an explicit truncation field in JSON and Markdown.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@pmoves/tools/review_dump.py` around lines 93 - 97, Update the review-thread
comment retrieval around the GraphQL comments selection and its consuming export
logic to fetch all comment pages for each thread, using pageInfo and cursors
until no further pages remain. Preserve the complete reply chain in both JSON
and Markdown output rather than silently limiting results to the first 20
comments.
```

</details>

<!-- fingerprinting:phantom:medusa:tapir -->

<!-- cr-indicator-types:potential_issue -->

<!-- cr-comment:v1:417490d1cfbd19e9885335e9 -->

<!-- This is an auto-generated comment by CodeRabbit -->

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,352 @@
+#!/usr/bin/env python3
+"""Review Dump — collect PR review threads into LLM-readable JSON + Markdown.
+
+Extends collect_review_comments.py (which writes to Supabase) with:
+  - GraphQL review threads (resolved state + reply chains — REST misses these)
+  - Committable-suggestion extraction (CodeRabbit ```suggestion blocks)
+  - Diff context (the diff_hunk around each comment)
+  - Structured JSON export for tooling
+  - Human/LLM-readable Markdown export for local analysis
+  - Optional fan-out to Hi-RAG (POST /hirag/upsert-batch) and Cipher (POST /api/memory)
+
+Usage:
+    # Dump a single PR to local files:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434
+
+    # Dump all open PRs:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --state open
+
+    # Dump + ingest into Hi-RAG and Cipher:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --ingest-hirag --ingest-cipher
+
+    # Dry-run (collect + export, no ingestion):
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --dry-run
+
+Output files land in pmoves/docs/logs/review-dumps/<repo>-<pr>.{json,md} by default.
+"""
+
+from __future__ import annotations
+
+import argparse
+import json
+import os
+import re
+import sys
+import urllib.request
+import urllib.error
+from datetime import datetime, timezone
+from pathlib import Path
+from typing import Any
+
+_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
+if str(_REPO_ROOT) not in sys.path:
+    sys.path.insert(0, str(_REPO_ROOT))
+
+GITHUB_ORG = os.environ.get("PMOVES_GITHUB_ORG", "POWERFULMOVES")
+GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
+HIRAG_URL = os.environ.get("HIRAG_UPSERT_URL") or os.environ.get("HIRAG_URL", "http://localhost:8086")
+CIPHER_URL = os.environ.get("CIPHER_API_URL", "http://localhost:8105")
+CIPHER_TOKEN = os.environ.get("CIPHER_API_TOKEN", "")
+OUTPUT_DIR = Path(os.environ.get("REVIEW_DUMP_DIR", _REPO_ROOT / "pmoves" / "docs" / "logs" / "review-dumps"))
+
+SEVERITY_RE = re.compile(r"(?:P(\d)\s+Badge|severity[:\s]*P(\d))", re.IGNORECASE)
+SUGGESTION_RE = re.compile(r"```suggestion\n(.*?)```", re.DOTALL)
+NITPICK_RE = re.compile(r"\b(nitpick|nit\b)", re.IGNORECASE)
+
+
+def _gh_headers() -> dict[str, str]:
+    if not GITHUB_TOKEN:
+        raise SystemExit("ERROR: GH_TOKEN or GITHUB_TOKEN not set")
+    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
+
+
+def gh_rest(path: str) -> Any:
+    req = urllib.request.Request(f"https://api.github.com{path}", headers=_gh_headers())
+    try:
+        return json.loads(urllib.request.urlopen(req, timeout=30).read())
+    except urllib.error.HTTPError as e:
+        if e.code == 404:
+            return []
+        raise
+
+
+def gh_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
+    body = json.dumps({"query": query, "variables": variables}).encode()
+    req = urllib.request.Request(
+        "https://api.github.com/graphql",
+        data=body,
+        headers={**_gh_headers(), "Content-Type": "application/json"},
+    )
+    return json.loads(urllib.request.urlopen(req, timeout=30).read())
+
+
+THREADS_QUERY = """
+query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
+  repository(owner: $owner, name: $name) {
+    pullRequest(number: $number) {
+      title state mergedAt headRefName baseRefName additions deletions changedFiles
+      author { login }
+      reviewThreads(first: 100, after: $cursor) {
+        pageInfo { hasNextPage endCursor }
+        nodes {
+          id isResolved isOutdated path line
+          comments(first: 20) {
+            nodes {
+              databaseId author { login } body path line originalLine diffHunk createdAt url
+            }
+          }
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730770912)

### 14. 🔴 [unclassified] coderabbitai — `pmoves/tools/review_dump.py:315`

_🩺 Stability & Availability_ | _🟡 Minor_ | _⚡ Quick win_

**Do not require the output directory to be inside the repository.**

When `REVIEW_DUMP_DIR` is outside `_REPO_ROOT`, both `relative_to()` calls raise `ValueError` after the reports are written. The command then exits before optional ingestion.

<details>
<summary>Proposed fix</summary>

```diff
-    print(f"  exported: {json_path.relative_to(_REPO_ROOT)}")
-    print(f"  exported: {md_path.relative_to(_REPO_ROOT)}")
+    print(f"  exported: {os.path.relpath(json_path, _REPO_ROOT)}")
+    print(f"  exported: {os.path.relpath(md_path, _REPO_ROOT)}")
```
</details>

<!-- suggestion_start -->

<details>
<summary>📝 Committable suggestion</summary>

> ‼️ **IMPORTANT**
> Carefully review the code before committing. Ensure that it accurately replaces the highlighted code, contains no missing lines, and has no issues with indentation. Thoroughly test & benchmark the code to ensure it meets the requirements.

```suggestion
    print(f"  exported: {os.path.relpath(json_path, _REPO_ROOT)}")
    print(f"  exported: {os.path.relpath(md_path, _REPO_ROOT)}")
```

</details>

<!-- suggestion_end -->

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@pmoves/tools/review_dump.py` around lines 314 - 315, Update the reporting
output in the review dump command so exported paths work when REVIEW_DUMP_DIR is
outside _REPO_ROOT. Replace the direct relative_to calls for json_path and
md_path with path formatting that preserves repository-relative paths when
possible and safely displays absolute or otherwise non-relative paths without
raising ValueError, allowing optional ingestion to continue.
```

</details>

<!-- fingerprinting:phantom:medusa:tapir -->

<!-- cr-indicator-types:potential_issue -->

<!-- cr-comment:v1:88708dedb7d0c0fcf8b8f6f9 -->

<!-- This is an auto-generated com

**Committable suggestion(s):**

```suggestion
    print(f"  exported: {os.path.relpath(json_path, _REPO_ROOT)}")
    print(f"  exported: {os.path.relpath(md_path, _REPO_ROOT)}")
```

<details><summary>Diff context</summary>

```diff
@@ -0,0 +1,352 @@
+#!/usr/bin/env python3
+"""Review Dump — collect PR review threads into LLM-readable JSON + Markdown.
+
+Extends collect_review_comments.py (which writes to Supabase) with:
+  - GraphQL review threads (resolved state + reply chains — REST misses these)
+  - Committable-suggestion extraction (CodeRabbit ```suggestion blocks)
+  - Diff context (the diff_hunk around each comment)
+  - Structured JSON export for tooling
+  - Human/LLM-readable Markdown export for local analysis
+  - Optional fan-out to Hi-RAG (POST /hirag/upsert-batch) and Cipher (POST /api/memory)
+
+Usage:
+    # Dump a single PR to local files:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434
+
+    # Dump all open PRs:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --state open
+
+    # Dump + ingest into Hi-RAG and Cipher:
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --ingest-hirag --ingest-cipher
+
+    # Dry-run (collect + export, no ingestion):
+    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --dry-run
+
+Output files land in pmoves/docs/logs/review-dumps/<repo>-<pr>.{json,md} by default.
+"""
+
+from __future__ import annotations
+
+import argparse
+import json
+import os
+import re
+import sys
+import urllib.request
+import urllib.error
+from datetime import datetime, timezone
+from pathlib import Path
+from typing import Any
+
+_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
+if str(_REPO_ROOT) not in sys.path:
+    sys.path.insert(0, str(_REPO_ROOT))
+
+GITHUB_ORG = os.environ.get("PMOVES_GITHUB_ORG", "POWERFULMOVES")
+GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
+HIRAG_URL = os.environ.get("HIRAG_UPSERT_URL") or os.environ.get("HIRAG_URL", "http://localhost:8086")
+CIPHER_URL = os.environ.get("CIPHER_API_URL", "http://localhost:8105")
+CIPHER_TOKEN = os.environ.get("CIPHER_API_TOKEN", "")
+OUTPUT_DIR = Path(os.environ.get("REVIEW_DUMP_DIR", _REPO_ROOT / "pmoves" / "docs" / "logs" / "review-dumps"))
+
+SEVERITY_RE = re.compile(r"(?:P(\d)\s+Badge|severity[:\s]*P(\d))", re.IGNORECASE)
+SUGGESTION_RE = re.compile(r"```suggestion\n(.*?)```", re.DOTALL)
+NITPICK_RE = re.compile(r"\b(nitpick|nit\b)", re.IGNORECASE)
+
+
+def _gh_headers() -> dict[str, str]:
+    if not GITHUB_TOKEN:
+        raise SystemExit("ERROR: GH_TOKEN or GITHUB_TOKEN not set")
+    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
+
+
+def gh_rest(path: str) -> Any:
+    req = urllib.request.Request(f"https://api.github.com{path}", headers=_gh_headers())
+    try:
+        return json.loads(urllib.request.urlopen(req, timeout=30).read())
+    except urllib.error.HTTPError as e:
+        if e.code == 404:
+            return []
+        raise
+
+
+def gh_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
+    body = json.dumps({"query": query, "variables": variables}).encode()
+    req = urllib.request.Request(
+        "https://api.github.com/graphql",
+        data=body,
+        headers={**_gh_headers(), "Content-Type": "application/json"},
+    )
+    return json.loads(urllib.request.urlopen(req, timeout=30).read())
+
+
+THREADS_QUERY = """
+query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
+  repository(owner: $owner, name: $name) {
+    pullRequest(number: $number) {
+      title state mergedAt headRefName baseRefName additions deletions changedFiles
+      author { login }
+      reviewThreads(first: 100, after: $cursor) {
+        pageInfo { hasNextPage endCursor }
+        nodes {
+          id isResolved isOutdated path line
+          comments(first: 20) {
+            nodes {
+              databaseId author { login } body path line originalLine diffHunk createdAt url
+            }
+          }
+        }
+      }
+      reviews(first: 50) {
+        nodes { author { login } state body submittedAt }
+      }
+    }
+  }
+}
+"""
+
+
+def fetch_threads(repo: str, pr_number: int) -> dict[str, Any]:
+    owner, *rest = repo.split("/", 1)
+    name = rest[0] if rest else repo
+    result: dict[str, Any] = {}
+    cursor = None
+    while True:
+        data = gh_graphql(THREADS_QUERY, {"owner": owner, "name": name, "number": pr_number, "cursor": cursor})
+        pr = data["data"]["repository"]["pullRequest"]
+        if not pr:
+            raise SystemExit(f"ERROR: PR {repo}#{pr_number} not found")
+        if not result:
+            result = {
+                "repo": repo, "pr_number": pr_number, "title": pr["title"], "state": pr["state"],
+                "merged_at": pr.get("mergedAt"), "branch": pr["headRefName"], "base": pr["baseRefName"],
+                "additions": pr["additions"], "deletions": pr["deletions"], "changed_files": pr["changedFiles"],
+                "author": (pr.get("author") or {}).get("login", "unknown"),
+                "collected_at": datetime.now(timezone.utc).isoformat(),
+                "threads": [],
+                "reviews": [
+                    {"author": (r.get("author") or {}).get("login", "unknown"), "state": r["state"],
+                     "body": r.get("body") or "", "submitted_at": r.get("submittedAt")}
+                    for r in pr.get("reviews", {}).get("nodes", [])
+                ],
+            }
+        result["threads"].extend(pr["reviewThreads"]["nodes"])
+        if pr["reviewThreads"]["pageInfo"]["hasNextPage"]:
+            cursor = pr["reviewThreads"]["pageInfo"]["endCursor"]
+        else:
+            break
+    return result
+
+
+def extract_severity(body: str) -> str:
+    m = SEVERITY_RE.search(body)
+    if m:
+        for g in m.groups():
+            if g and g.isdigit():
+                return f"P{g}"
+    if NITPICK_RE.search(body):
+        return "nitpick"
+    low = body.lower()
+    if "praise" in low:
+        return "praise"
+    if "question" in low:
+        return "question"
+    return "unclassified"
+
+
+def extract_suggestions(body: str) -> list[str]:
+    return [m.group(1).rstrip() for m in SUGGESTION_RE.finditer(body)]
+
+
+def classify_author(author: str) -> str:
+    if "[bot]" in author or author in {"coderabbitai", "chatgpt-codex-connector", "github-actions", "dependabot"}:
+        return "bot"
+    return "human"
+
+
+def thread_to_record(thread: dict[str, Any]) -> dict[str, Any]:
+    comments = thread.get("comments", {}).get("nodes", [])
+    if not comments:
+        return {}
+    first = comments[0]
+    body = first.get("body", "")
+    path = thread.get("path") or first.get("path")
+    line = thread.get("line") or first.get("line") or first.get("originalLine")
+    replies = [
+        {"author": (r.get("author") or {}).get("login", "unknown"), "body": r.get("body", ""), "created_at": r.get("createdAt")}
+        for r in comments[1:]
+    ]
+    return {
+        "thread_id": thread["id"], "is_resolved": thread.get("isResolved", False),
+        "is_outdated": thread.get("isOutdated", False), "path": path, "line": line,
+        "severity": extract_severity(body),
+        "author": (first.get("author") or {}).get("login", "unknown"),
+        "author_type": classify_author((first.get("author") or {}).get("login", "unknown")),
+        "body": body, "suggestions": extract_suggestions(body),
+        "diff_hunk": first.get("diffHunk", ""), "replies": replies,
+        "url": first.get("url", ""), "created_at": first.get("createdAt"),
+    }
+
+
+def export_json(data: dict[str, Any], path: Path) -> None:
+    path.parent.mkdir(parents=True, exist_ok=True)
+    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
+
+
+def export_markdown(data: dict[str, Any], path: Path) -> None:
+    lines: list[str] = []
+    repo, pr = data["repo"], data["pr_number"]
+    lines.append(f"# Review Dump — {repo}#{pr}\n\n**{data['title']}**\n\n")
+    lines.append(f"- State: `{data['state']}` | Branch: `{data['branch']}` → `{data['base']}` | "
+                 f"+{data['additions']}/-{data['deletions']} ({data['changed_files']} files)\n")
+    lines.append(f"- Author: {data['author']} | Collected: {data['collected_at']}\n")
+    records = data.get("thread_records", [])
+    resolved = sum(1 for r in records if r["is_resolved"])
+    actionable = [r for r in records if r["severity"] in ("P1", "P2") and not r["is_resolved"]]
+    suggestions = [s for r in records for s in r["suggestions"]]
+    lines.append(f"\n## Summary\n\n| Metric | Count |\n|---|---|\n")
+    lines.append(f"| Total threads | {len(records)} |\n| Resolved | {resolved} |\n")
+    lines.append(f"| Open P1/P2 (actionable) | {len(actionable)} |\n| Committable suggestions | {len(suggestions)} |\n")
+    sev_counts: dict[str, int] = {}
+    for r in records:
+        sev_counts[r["severity"]] = sev_counts.get(r["severity"], 0) + 1
+    if sev_counts:
+        lines.append(f"\n**Severity breakdown:** {', '.join(f'{k}={v}' for k, v in sorted(sev_counts.items()))}\n")
+    if data.get("reviews"):
+        lines.append(f"\n## Reviews ({len(data['reviews'])})\n\n")
+        for rev in data["reviews"]:
+            lines.append(f"- **{rev['author']}** ({rev['state']}) — {(rev.get('body') or '')[:200].replace(chr(10), ' ')}\n")
+    if not records:
+        lines.append(f"\n*No review threads found.*\n")
+    else:
+        lines.append(f"\n## Threads\n\n")
+        for i, r in enumerate(records, 1):
+            status = "✅" if r["is_resolved"] else ("⚠️" if r["is_outdated"] else "🔴")
+            lines.append(f"### {i}. {status} [{r['severity']}] {r['author']} — `{r['path']}:{r['line']}`\n\n")
+            lines.append(f"{r['body'][:2000]}\n\n")
+            if r["suggestions"]:
+                lines.append(f"**Committable suggestion(s):**\n\n")
+                for s in r["suggestions"]:
+                    lines.append(f"```suggestion\n{s}\n```\n\n")
+            if r["diff_hunk"]:
+                lines.append(f"<details><summary>Diff context</summary>\n\n```diff\n{r['diff_hunk']}\n```\n\n</details>\n\n")
+            if r["replies"]:
+                lines.append(f"<details><summary>{len(r['replies'])} repl{'y' if len(r['replies'])==1 else 'ies'}</summary>\n\n")
+                for rep in r["replies"]:
+                    lines.append(f"- **{rep['author']}**: {rep['body'][:300]}\n")
+                lines.append(f"\n</details>\n\n")
+            if r["url"]:
+                lines.append(f"[→ thread]({r['url']})\n\n")
+    path.parent.mkdir(parents=True, exist_ok=True)
+    path.write_text("".join(lines), encoding="utf-8")
+
+
+def _record_to_text(r: dict[str, Any], pr_data: dict[str, Any]) -> str:
+    parts = [
+        f"PR {pr_data['repo']}#{pr_data['pr_number']}: {pr_data['title']}",
+        f"Severity: {r['severity']} | Author: {r['author']} | Resolved: {r['is_resolved']}",
+    ]
+    if r.get("path"):
+        parts.append(f"Location: {r['path']}:{r['line']}")
+    parts.append(f"\n{r['body']}")
+    if r["suggestions"]:
+        parts.append("\nSuggested fix:")
+        for s in r["suggestions"]:
+            parts.append(f"  {s[:200]}")
+    return "\n".join(parts)
+
+
+def ingest_hirag_records(records: list[dict[str, Any]], pr_data: dict[str, Any]) -> int:
+    items = [{
+        "id": f"review-{pr_data['repo']}-{pr_data['pr_number']}-{r['thread_id'][-12:]}",
+        "content": _record_to_text(r, pr_data),
+        "metadata": {"type": "review_comment", "repo": pr_data["repo"], "pr_number": pr_data["pr_number"],
+                     "severity": r["severity"], "path": r.get("path"), "author": r["author"], "is_resolved": r["is_resolved"]},
+    } for r in records]
+    body = json.dumps({"items": items}).encode()
+    req = urllib.request.Request(f"{HIRAG_URL}/hirag/upsert-batch", data=body,
+                                 headers={"Content-Type": "application/json"}, method="POST")
+    try:
+        urllib.request.urlopen(req, timeout=30)
+        return len(items)
+    except Exception as e:
+        print(f"  [hirag] error: {e}", file=sys.stderr)
+        return 0
+
+
+def ingest_cipher_records(records: list[dict[str, Any]], pr_data: dict[str, Any]) -> int:
+    if not CIPHER_TOKEN:
+        print("  [cipher] skip: CIPHER_API_TOKEN not set", file=sys.stderr)
+        return 0
+    count = 0
+    for r in records:
+        if r["severity"] not in ("P1", "P2"):
+            continue
+        body = json.dumps({
+            "agentId": "review-collector", "category": "review_learning",
+            "content": _record_to_text(r, pr_data),
+            "metadata": {"repo": pr_data["repo"], "pr_number": pr_data["pr_number"],
+                         "severity": r["severity"], "path": r.get("path"), "thread_id": r["thread_id"]},
+            "tags": ["review", r["severity"], pr_data["repo"], "pr-learning"],
+        }).encode()
+        req = urllib.request.Request(f"{CIPHER_URL}/api/memory", data=body,
+                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {CIPHER_TOKEN}"},
+                                     method="POST")
+        try:
+            urllib.request.urlopen(req, timeout=10)
+            count += 1
+        except Exception as e:
+            print(f"  [cipher] error on thread {r['thread_id'][-8:]}: {e}", file=sys.stderr)
+    return count
+
+
+def dump_pr(repo: str, pr_number: int, dry_run: bool, ingest_hirag: bool = False, ingest_cipher: bool = False) -> dict[str, Any]:
+    full_repo = f"{GITHUB_ORG}/{repo}" if "/" not in repo else repo
+    print(f"[review-dump] {full_repo}#{pr_number}")
+    data = fetch_threads(full_repo, pr_number)
+    records = [t for t in (thread_to_record(t) for t in data["threads"]) if t]
+    data["thread_records"] = records
+    slug = repo.replace("/", "-")
+    json_path = OUTPUT_DIR / f"{slug}-{pr_number}.json"
+    md_path = OUTPUT_DIR / f"{slug}-{pr_number}.md"
+    export_json(data, json_path)
+    export_markdown(data, md_path)
+    print(f"  exported: {json_path.relative_to(_REPO_ROOT)}")
+    print(f"  exported: {md_path.relative_to(_REPO_ROOT)}")
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2439#discussion_r3730770916)

