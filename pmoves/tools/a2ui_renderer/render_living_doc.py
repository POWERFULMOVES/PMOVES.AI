#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
render_living_doc.py — convert a markdown living doc into a provenance-shaped MP4
via the a2ui-renderer service (port 8107, /render/provenance).

Lane 2228 (2026-08-02): first-class CLI for the living-doc animation lane.
The script is dependency-free (stdlib only) so it can run from a uv-script shim,
in CI, or from the Makefile `make docs-render-living` target.

Two modes:

  1. Single-doc: convert one markdown file to one MP4
       python render_living_doc.py --doc pmoves/docs/X.md --output /tmp/x.mp4

  2. Registry iterator: walk pmoves/configs/living_docs_registry.yaml and render
     every entry under the `renderable:` section.
       python render_living_doc.py \\
           --registry pmoves/configs/living_docs_registry.yaml \\
           --output-dir pmoves/docs/living-docs/rendered \\
           --minio-bucket outputs

The registry mode is what `make docs-render-living` calls. Each rendered artifact
lands in $output_dir/<id>.<format> locally and (if --minio-bucket is set)
gets re-uploaded to s3://<bucket>/a2ui/living-docs/<id>.<format>.

The script is a thin orchestrator on top of the /render/provenance HTTP endpoint,
so all of the rendering/Remotion/MinIO/NATS work lives in the TypeScript service
(pmoves/services/a2ui-renderer/src/index.ts) — this script just speaks HTTP.

See pmoves/docs/specs/a2ui-renderer-compose-2026-08-02.md for the full design.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Force UTF-8 on stdout/stderr (Windows charmap default breaks the success
# markers + JSON dump on non-ASCII titles). This is a no-op on POSIX where
# stdout is already utf-8.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

# Provenance palette mirrors the ARMOR palette in
# pmoves/services/a2ui-renderer/src/provenanceLivingDoc.ts so the rendered
# output is visually consistent with the rest of the PMOVES surface.
DEFAULT_PALETTE: dict[str, str] = {
    "background": "#050508",
    "panel": "rgba(18, 18, 26, 0.82)",
    "panelAlt": "rgba(10, 10, 15, 0.78)",
    "accent": "#7C3AED",
    "accentSoft": "#0D9488",
    "ink": "#f8f8f8",
    "muted": "#a0a0a8",
}

# Cap matches the TS service's normalizeProvenanceLivingDoc(): 4 sections max,
# 8 weighted terms max, 6 provenance refs max, 8 favorite words max.
MAX_SECTIONS = 4
MAX_WEIGHTED_TERMS = 8
MAX_PROVENANCE_REFS = 6
MAX_FAVORITE_WORDS = 8

ALLOWED_FORMATS = ("mp4", "gif", "webm")

# Words we don't want showing up as "favorite" or "weighted" terms.
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your",
    "you", "are", "but", "not", "have", "has", "was", "were", "they",
    "their", "them", "will", "would", "could", "should", "can", "may",
    "all", "any", "one", "out", "via", "use", "used", "using", "uses",
    "per", "see", "also", "such", "than", "then", "these", "those",
    "when", "where", "what", "which", "who", "how", "why", "more",
    "most", "less", "few", "many", "much", "very", "just", "only",
    "lane", "issue", "section", "file", "files", "code", "data",
    "render", "renders", "rendered", "make", "service", "services",
}

# Heading regexes (CommonMark ATX headings only — setext is rare in our docs).
_H1_RE = re.compile(r"^#\s+(.+?)\s*$")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_H3_RE = re.compile(r"^###\s+(.+?)\s*$")
# Pull inline links out so we don't count "Click [here](url)" as a word.
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
# Words: 3+ chars, alphanumeric, allow dashes.
_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9-]{2,}\b")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ProvenanceSection:
    heading: str
    body: str


@dataclasses.dataclass
class ProvenanceDoc:
    title: str
    subtitle: str
    summary: str
    merkle_root: str
    shape_id: str
    favorite_words: list[str]
    weighted_terms: list[dict[str, Any]]
    sections: list[ProvenanceSection]
    provenance_refs: list[dict[str, str]]
    duration_ms: int
    palette: dict[str, str]
    source_path: str

    def to_request_body(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "summary": self.summary,
            "merkle_root": self.merkle_root,
            "shape_id": self.shape_id,
            "favorite_words": self.favorite_words,
            "weighted_terms": self.weighted_terms,
            "sections": [
                {"heading": s.heading, "body": s.body} for s in self.sections
            ],
            "provenance_refs": self.provenance_refs,
            "duration_ms": self.duration_ms,
            "palette": self.palette,
        }


# ---------------------------------------------------------------------------
# Markdown parsing (CommonMark subset, dependency-free)
# ---------------------------------------------------------------------------


def _strip_markdown(text: str) -> str:
    """Cheap markdown stripper — drop link syntax, code fences, emphasis chars."""
    text = _LINK_RE.sub(r"\1", text)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"[*_]{1,3}(\S[\s\S]*?\S|\S)[*_]{1,3}", r"\1", text)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    return text


def _word_frequencies(text: str) -> dict[str, int]:
    """Return {word: count} for non-stopword tokens of length >= 3."""
    cleaned = _strip_markdown(text).lower()
    out: dict[str, int] = {}
    for match in _WORD_RE.finditer(cleaned):
        word = match.group(0).lower()
        if word in _STOPWORDS:
            continue
        out[word] = out.get(word, 0) + 1
    return out


def _top_terms(
    freqs: dict[str, int], n: int = MAX_WEIGHTED_TERMS
) -> list[dict[str, Any]]:
    """Return the top-n terms as provenance-shaped dicts with weights in [0, 1]."""
    if not freqs:
        return []
    sorted_terms = sorted(freqs.items(), key=lambda kv: (-kv[1], kv[0]))
    top = sorted_terms[:n]
    max_count = top[0][1] or 1
    return [
        {
            "term": term,
            "weight": round(0.5 + 0.5 * (count / max_count), 3),
            "cluster": _cluster_for(term),
        }
        for term, count in top
    ]


# Cheap semantic clustering: map a small set of well-known PMOVES terms to
# cluster names. Anything else gets "lexicon" as a default. This is intentionally
# tiny — the goal is to give the renderer *some* structure, not to be a real
# taxonomy. The a2ui-renderer service just sorts/keeps the first 8 weighted terms.
_CLUSTER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "trust": ("provenance", "attestation", "chit", "signature", "merkle", "verify", "audit"),
    "semantic-shape": ("lexicon", "term", "terms", "weighted", "cluster", "embedding", "shape"),
    "visual-surface": ("render", "remotion", "frame", "animation", "motion", "mp4", "video"),
    "agent-pass": ("agent", "agents", "spark", "claude", "knuckles", "gpt", "kilocode"),
    "index": ("hirag", "index", "search", "qdrant", "meilisearch", "ingest"),
    "fleet": ("node", "nodes", "fleet", "host", "hosts", "tailscale", "kvm4", "z890", "5090"),
    "ops": ("compose", "container", "containerd", "make", "makefile", "k8s", "kubectl"),
    "spec": ("spec", "schema", "yaml", "json", "openapi", "contract"),
    "human": ("operator", "operator's", "operator-", "session", "prompt", "claude", "mavis"),
    "evidence": ("evidence", "screenshot", "playwright", "log", "logs", "trace", "metric", "metrics"),
    "shard": ("shard", "shards", "rolling", "merge", "rebase", "branch", "pr", "squash"),
    "pretext": ("pretext", "layout", "text", "bounded", "line", "lines"),
}


def _cluster_for(term: str) -> str:
    lower = term.lower()
    for cluster, keywords in _CLUSTER_KEYWORDS.items():
        if any(kw in lower or lower in kw for kw in keywords):
            return cluster
    return "lexicon"


def parse_markdown_to_provenance(
    source_path: Path, raw_text: str
) -> ProvenanceDoc:
    """Parse a CommonMark-subset doc into a ProvenanceDoc.

    Conventions:
      - First H1 is the title; if none, use the filename stem.
      - First paragraph after the H1 (or first 240 chars of body) is the
        subtitle; first paragraph after *that* is the summary.
      - Each H2 starts a new section; everything until the next H2 (or EOF)
        is the section body (markdown stripped of headings/code-fences).
      - Up to MAX_SECTIONS sections; later H2s are dropped silently to match
        the TS service's slice behavior.
      - Top MAX_WEIGHTED_TERMS words (by frequency, after stopwords) become
        weighted_terms. Top MAX_FAVORITE_WORDS become favorite_words.
      - merkle_root = first 16 hex chars of sha256(normalized_content).
      - shape_id = sha256(source_path)[:16] prefixed with "shape.doc.".
    """
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    title: str | None = None
    sections: list[ProvenanceSection] = []
    current_heading: str | None = None
    current_body: list[str] = []
    paragraphs: list[str] = []  # for subtitle/summary extraction

    def flush_section() -> None:
        nonlocal current_heading, current_body
        if current_heading is not None and len(sections) < MAX_SECTIONS:
            body = "\n".join(current_body).strip()
            if body:
                sections.append(ProvenanceSection(current_heading, body))
        current_heading = None
        current_body = []

    for line in lines:
        h1 = _H1_RE.match(line)
        if h1 and title is None:
            title = h1.group(1).strip()
            continue
        h2 = _H2_RE.match(line)
        if h2:
            flush_section()
            current_heading = h2.group(1).strip()
            continue
        h3 = _H3_RE.match(line)
        if h3:
            # H3s are part of the current section's body, demoted to bold-ish.
            current_body.append(f"**{h3.group(1).strip()}**")
            continue
        if current_heading is not None:
            current_body.append(line)
        elif title is not None and line.strip() and not line.startswith("#"):
            # Collecting paragraphs after the H1 (but not under a section)
            if not (line.startswith("```") or line.startswith("---")):
                paragraphs.append(line)

    flush_section()

    # Fall back to filename if no H1.
    if not title:
        title = source_path.stem.replace("-", " ").replace("_", " ").title()

    # Extract subtitle + summary from the prelude paragraphs (before first H2).
    clean_paragraphs = [p.strip() for p in paragraphs if p.strip()]
    subtitle = clean_paragraphs[0][:240] if clean_paragraphs else (
        f"Living-doc surface for {title}"
    )
    summary = (
        " ".join(clean_paragraphs[1:3])[:800]
        if len(clean_paragraphs) > 1
        else subtitle
    )

    # If no H2s at all, synthesize a single "Overview" section from the
    # full text. The TS service's normalize() guarantees at least one section.
    if not sections:
        body = _strip_markdown(text).strip()
        if title and body.lower().startswith(title.lower()):
            body = body[len(title):].lstrip(" :-\n")
        sections.append(ProvenanceSection("Overview", body[:1200] or title))

    # Frequencies across the whole doc (weighted + favorite).
    freqs = _word_frequencies(text)
    weighted_terms = _top_terms(freqs, MAX_WEIGHTED_TERMS)
    favorite_words = [t["term"] for t in weighted_terms[:MAX_FAVORITE_WORDS]]

    # merkle_root + shape_id.
    normalized = "\n".join(line.strip() for line in lines if line.strip())
    merkle_root = "mkl_" + hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()[:16]
    shape_id = (
        "shape.doc." + hashlib.sha256(
            str(source_path).encode("utf-8")
        ).hexdigest()[:16]
    )

    # Pull provenance_refs from the trailing "See also" / "References" /
    # "Related" section if present, otherwise leave empty.
    provenance_refs = _extract_provenance_refs(sections, text)

    # duration_ms: server estimates from section/term counts; we mirror that
    # formula so dry-runs match the actual render.
    duration_ms = _estimate_duration_ms(sections, weighted_terms, provenance_refs, summary)

    return ProvenanceDoc(
        title=title,
        subtitle=subtitle,
        summary=summary,
        merkle_root=merkle_root,
        shape_id=shape_id,
        favorite_words=favorite_words,
        weighted_terms=weighted_terms,
        sections=sections,
        provenance_refs=provenance_refs,
        duration_ms=duration_ms,
        palette=DEFAULT_PALETTE,
        source_path=str(source_path),
    )


def _extract_provenance_refs(
    sections: list[ProvenanceSection], full_text: str
) -> list[dict[str, str]]:
    """Pull link-style provenance refs from a trailing 'See also' section."""
    refs: list[dict[str, str]] = []
    for section in sections:
        heading_lc = section.heading.strip().lower()
        if heading_lc in ("see also", "references", "related", "links"):
            for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", section.body):
                label = match.group(1).strip()
                uri = match.group(2).strip()
                if not label or not uri:
                    continue
                refs.append({"label": label[:120], "uri": uri[:240], "kind": "link"})
                if len(refs) >= MAX_PROVENANCE_REFS:
                    return refs
    # If no trailing refs section, also harvest any markdown links in the
    # overview/intro area as fallback (capped at 3 to keep noise down).
    if not refs:
        for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", full_text[:4000]):
            label, uri = match.group(1).strip(), match.group(2).strip()
            if label and uri and not uri.startswith("#"):
                refs.append({"label": label[:120], "uri": uri[:240], "kind": "link"})
                if len(refs) >= 3:
                    break
    return refs


def _estimate_duration_ms(
    sections: list[ProvenanceSection],
    weighted_terms: list[dict[str, Any]],
    provenance_refs: list[dict[str, str]],
    summary: str,
) -> int:
    """Mirror of estimateProvenanceDurationMs() in provenanceLivingDoc.ts."""
    base = 9000
    base += len(sections) * 1500
    base += len(weighted_terms) * 180
    base += len(provenance_refs) * 160
    base += (max(1, len(summary) // 40)) * 120
    return max(9000, min(24000, base))


# ---------------------------------------------------------------------------
# Registry loading (small YAML subset, no PyYAML dependency)
# ---------------------------------------------------------------------------


def _strip_yaml_value(raw: str) -> str:
    """Strip quotes / comments from a single-line YAML scalar."""
    s = raw.strip()
    if not s or s == "~" or s.lower() == "null":
        return ""
    # strip trailing comment
    if " #" in s:
        s = s[: s.index(" #")].rstrip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    return s


def load_renderable_registry(registry_path: Path) -> list[dict[str, str]]:
    """Parse just the `renderable:` section of living_docs_registry.yaml.

    The registry is a tiny, well-known YAML file (see
    pmoves/configs/living_docs_registry.yaml) — we don't need a full YAML
    parser. Each entry is a flat list of `key: value` lines, separated by
    blank lines; the list lives under a `renderable:` key.
    """
    text = registry_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_renderable = False
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    base_indent: int | None = None

    for raw_line in lines:
        # skip comments and blank lines (blank ends current entry)
        stripped = raw_line.split("#", 1)[0]
        if not stripped.strip():
            if current:
                entries.append(current)
                current = {}
                base_indent = None
            continue

        indent = len(raw_line) - len(raw_line.lstrip())
        content = stripped.strip()

        if indent == 0 and content.endswith(":"):
            key = content[:-1].strip()
            if key == "renderable":
                in_renderable = True
                if current:
                    entries.append(current)
                    current = {}
                    base_indent = None
                continue
            else:
                # any other top-level key closes the renderable section
                if in_renderable:
                    in_renderable = False
                continue

        if not in_renderable:
            continue

        if base_indent is None:
            # first item line establishes the list-item indent
            if content.startswith("- "):
                base_indent = indent
                content = content[2:].strip()
            else:
                # no list yet — keep scanning
                continue
        elif content.startswith("- "):
            # new list item — close out previous
            if current:
                entries.append(current)
                current = {}
            content = content[2:].strip()

        if ":" in content:
            k, _, v = content.partition(":")
            current[k.strip()] = _strip_yaml_value(v)

    if current:
        entries.append(current)

    return entries


# ---------------------------------------------------------------------------
# HTTP orchestration
# ---------------------------------------------------------------------------


def _post_provenance(
    renderer_url: str,
    token: str | None,
    body: dict[str, Any],
    fmt: str,
    timeout_s: float = 600.0,
) -> dict[str, Any]:
    """POST to /render/provenance and return the parsed JSON response."""
    url = f"{renderer_url.rstrip('/')}/render/provenance?format={fmt}"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "pmoves-render-living-doc/1.0",
        },
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _download(url: str, dest: Path, timeout_s: float = 120.0) -> int:
    """Download url → dest, returning the byte count. Streams to disk."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "pmoves-render-living-doc/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
        return dest.stat().st_size


# ---------------------------------------------------------------------------
# Render flow
# ---------------------------------------------------------------------------


def render_one(
    source: Path,
    output: Path,
    *,
    renderer_url: str,
    token: str | None,
    fmt: str = "mp4",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Render a single markdown source → output. Returns a result dict."""
    if not source.exists():
        raise FileNotFoundError(f"source markdown not found: {source}")
    if fmt not in ALLOWED_FORMATS:
        raise ValueError(
            f"unsupported format: {fmt!r} (allowed: {', '.join(ALLOWED_FORMATS)})"
        )

    raw = source.read_text(encoding="utf-8")
    doc = parse_markdown_to_provenance(source, raw)
    body = doc.to_request_body()

    if dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(body, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return {
            "ok": True,
            "dry_run": True,
            "source": str(source),
            "output": str(output),
            "merkle_root": doc.merkle_root,
            "shape_id": doc.shape_id,
            "section_count": len(doc.sections),
            "weighted_term_count": len(doc.weighted_terms),
            "duration_ms": doc.duration_ms,
        }

    started = time.time()
    response = _post_provenance(renderer_url, token, body, fmt)
    elapsed_ms = int((time.time() - started) * 1000)

    if not response.get("ok"):
        raise RuntimeError(
            f"renderer returned error for {source}: {response.get('error')!r}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    download_url = response["url"]
    bytes_written = _download(download_url, output)

    return {
        "ok": True,
        "dry_run": False,
        "source": str(source),
        "output": str(output),
        "minio_url": download_url,
        "render_key": download_url.split("/")[-1],
        "merkle_root": response.get("merkle_root", doc.merkle_root),
        "shape_id": response.get("shape_id", doc.shape_id),
        "format": response.get("format", fmt),
        "duration_ms": response.get("duration_ms", doc.duration_ms),
        "elapsed_ms": elapsed_ms,
        "bytes": bytes_written,
        "composition_id": response.get("composition_id", "ProvenanceLivingDoc"),
    }


def render_registry(
    registry_path: Path,
    output_dir: Path,
    *,
    renderer_url: str,
    token: str | None,
    minio_bucket: str | None = None,
    repo_root: Path | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Render every entry under the renderable: section of the registry."""
    entries = load_renderable_registry(registry_path)
    if not entries:
        print(f"warning: no renderable entries found in {registry_path}", file=sys.stderr)
        return []

    repo_root = repo_root or Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for entry in entries:
        entry_id = entry.get("id", "").strip()
        source_rel = entry.get("source_doc", "").strip()
        output_key = entry.get("output_key", entry_id).strip() or entry_id
        fmt = entry.get("format", "mp4").strip().lower() or "mp4"
        if not entry_id or not source_rel:
            print(f"warning: skipping malformed entry: {entry}", file=sys.stderr)
            continue
        source = (repo_root / source_rel).resolve()
        output = (output_dir / f"{output_key}.{fmt}").resolve()
        try:
            result = render_one(
                source,
                output,
                renderer_url=renderer_url,
                token=token,
                fmt=fmt,
                dry_run=dry_run,
            )
            if minio_bucket and not dry_run and result.get("minio_url"):
                # The renderer already uploaded to MinIO; we just record the
                # canonical key for downstream consumers.
                result["canonical_minio_key"] = f"a2ui/living-docs/{output_key}.{fmt}"
                result["canonical_minio_uri"] = f"s3://{minio_bucket}/{result['canonical_minio_key']}"
            results.append(result)
            print(
                f"  ✓ {entry_id}: {result.get('bytes', 0)} bytes "
                f"-> {output}  (merkle={result['merkle_root']})"
            )
        except (FileNotFoundError, RuntimeError, ValueError, urllib.error.URLError) as exc:
            results.append({
                "ok": False,
                "source": str(source),
                "entry_id": entry_id,
                "error": str(exc),
            })
            print(f"  ✗ {entry_id}: {exc}", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="render_living_doc",
        description=(
            "Convert markdown living docs into provenance-shaped MP4s/GIFs/WebMs "
            "via the a2ui-renderer service (port 8107)."
        ),
    )

    mode = p.add_argument_group("mode (pick one)")
    mode.add_argument(
        "--doc",
        type=Path,
        help="path to a single markdown source file",
    )
    mode.add_argument(
        "--registry",
        type=Path,
        help="path to living_docs_registry.yaml (iterates the renderable: section)",
    )
    mode.add_argument(
        "--output",
        type=Path,
        help="output file path (for --doc mode)",
    )
    mode.add_argument(
        "--output-dir",
        type=Path,
        help="output directory (for --registry mode)",
    )
    mode.add_argument(
        "--format",
        choices=ALLOWED_FORMATS,
        default="mp4",
        help="output format (default: mp4)",
    )
    mode.add_argument(
        "--minio-bucket",
        help="MinIO bucket to record canonical keys under (registry mode only)",
    )
    mode.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="root for resolving source_doc paths in the registry (default: cwd)",
    )

    server = p.add_argument_group("server")
    server.add_argument(
        "--renderer-url",
        default=os.environ.get("A2UI_RENDERER_URL", "http://localhost:8107"),
        help="base URL of the a2ui-renderer (default: $A2UI_RENDERER_URL or http://localhost:8107)",
    )
    server.add_argument(
        "--token",
        default=os.environ.get("A2UI_RENDERER_TOKEN") or os.environ.get("SUPABASE_JWT_SECRET"),
        help="Supabase JWT for /render/provenance (default: $A2UI_RENDERER_TOKEN or $SUPABASE_JWT_SECRET)",
    )
    server.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="HTTP timeout in seconds (default: 600)",
    )

    flow = p.add_argument_group("flow control")
    flow.add_argument(
        "--dry-run",
        action="store_true",
        help="parse the markdown + build the ProvenanceLivingDoc JSON, but don't POST",
    )
    flow.add_argument(
        "--force",
        action="store_true",
        help="overwrite output file if it already exists",
    )
    flow.add_argument(
        "--print-doc",
        action="store_true",
        help="print the parsed ProvenanceLivingDoc JSON to stdout (for debugging)",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if not args.doc and not args.registry:
        print("error: must provide --doc <file> or --registry <yaml>", file=sys.stderr)
        return 2
    if args.doc and args.registry:
        print("error: --doc and --registry are mutually exclusive", file=sys.stderr)
        return 2
    if args.doc and not args.output:
        print("error: --doc mode requires --output <path>", file=sys.stderr)
        return 2
    if args.registry and not args.output_dir:
        print("error: --registry mode requires --output-dir <path>", file=sys.stderr)
        return 2

    if args.doc:
        if args.output.exists() and not args.force:
            print(
                f"error: output {args.output} already exists (use --force to overwrite)",
                file=sys.stderr,
            )
            return 2
        result = render_one(
            args.doc,
            args.output,
            renderer_url=args.renderer_url,
            token=args.token,
            fmt=args.format,
            dry_run=args.dry_run,
        )
        if args.print_doc:
            # Re-parse and print (the response is renderer-side; print the
            # request body the script would have sent).
            doc = parse_markdown_to_provenance(
                args.doc, args.doc.read_text(encoding="utf-8")
            )
            print(json.dumps(doc.to_request_body(), indent=2, ensure_ascii=False))
            return 0
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    results = render_registry(
        args.registry,
        args.output_dir,
        renderer_url=args.renderer_url,
        token=args.token,
        minio_bucket=args.minio_bucket,
        repo_root=args.repo_root,
        dry_run=args.dry_run,
    )
    failed = [r for r in results if not r.get("ok")]
    summary = {
        "registry": str(args.registry),
        "output_dir": str(args.output_dir),
        "total": len(results),
        "succeeded": len(results) - len(failed),
        "failed": len(failed),
        "results": results,
    }
    print(json.dumps(summary, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
