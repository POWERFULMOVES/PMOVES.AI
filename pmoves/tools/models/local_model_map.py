#!/usr/bin/env python3
"""Local model layer map: one row per installed Ollama model, every layer joined.

Read-only. Never creates, modifies, pulls or unloads an Ollama model, and never
writes host config. It reads:

  L1 runtime   Ollama HTTP API (the CLI equivalent is ``ollama show``):
               GET /api/tags, POST /api/show, GET /api/ps.
  L2 card      Hugging Face model card + config.json for the repo the model is
               DECLARED to come from (model suit ``huggingface.model_id``, then
               ``pmoves/config/hf_mappings.yaml`` ``ollama_variant``, then the
               Ollama parent tag of a local variant). Never guessed: no
               declaration -> ``hf: unmapped``. When the hf-research worker's
               ``card_evidence`` module is present (PR #3354) licence / gated /
               library come from it; otherwise from the Hub REST API.
  L3 suit      ``pmoves/configs/model-suits/*.yaml`` ``model_config`` +
               ``ollama_config`` (num_gpu / num_ctx / num_batch / variant).
  L4 demand    ``journalctl -u ollama`` slot lines (``n_ctx_slot = N ...
               task.n_tokens = T``, ``truncated = 1``) attributed to models via
               load-time weight blobs and ``/api/ps``; plus consumers that
               declare a model statically (A0 presets ``ctx_length``,
               TensorZero ``embedding_models``, compose env defaults).

Verdicts per row (worst first): TRUNCATING, OVER-NATIVE, SUIT-DRIFT,
UNDER-GPU, NOT-INSTALLED, UNMAPPED, OK. Each carries the evidence line that
produced it.

Exit codes (doctrine): 0 clean, 1 a layer conflicts (only with ``--check``),
3 could not measure (Ollama unreachable).

Why it exists (SPARK, 2026-10-21): three mismatches were found by hand -- an
A0 prompt of ~14.5k tokens against Ollama's 8192 default (one-token replies),
TensorZero embedding inputs clipped at 8191 tokens by an 8192 slot, and a
26.7-30.8k Claude Code prompt in a 32768 slot on a model trained to 40960.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

try:  # PyYAML is a repo-wide tool dependency
    import yaml  # type: ignore
except Exception:  # pragma: no cover - reported at use
    yaml = None  # type: ignore

try:
    import tomllib  # py311+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES = REPO_ROOT / "pmoves"
DEFAULT_SUITS_DIR = PMOVES / "configs" / "model-suits"
DEFAULT_HF_MAPPINGS = PMOVES / "config" / "hf_mappings.yaml"
DEFAULT_A0_PRESETS = PMOVES / "data" / "agent-zero" / "usr" / "plugins" / "_model_config" / "presets.yaml"
DEFAULT_TZ_CONFIG = PMOVES / "tensorzero" / "config" / "tensorzero.toml"
DEFAULT_CARD_EVIDENCE = PMOVES / "services" / "hf-research-agent" / "card_evidence.py"
HF_BASE = "https://huggingface.co"

EXIT_OK, EXIT_CONFLICT, EXIT_COULD_NOT_MEASURE = 0, 1, 3

# Worst first. Severity "conflict" fails --check; "warn"/"info" do not.
VERDICT_ORDER = ["TRUNCATING", "OVER-NATIVE", "SUIT-DRIFT", "UNDER-GPU", "NOT-INSTALLED", "UNMAPPED", "OK"]

FetchJSON = Callable[[str, str, Any], Any]  # (method, url, body) -> parsed JSON; raises on HTTP error


# ── HTTP ───────────────────────────────────────────────────────────


class HTTPStatusError(Exception):
    def __init__(self, status: int, url: str):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status


def urllib_fetch_json(method: str, url: str, body: Any = None, timeout: float = 10.0,
                      headers: dict[str, str] | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"content-type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed schemes
            return json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as exc:
        raise HTTPStatusError(exc.code, url) from None


# ── L1 runtime ─────────────────────────────────────────────────────


def parse_parameters(text: str | None) -> dict[str, str]:
    """``/api/show`` ``parameters`` is a Modelfile-style block; keep the last value per key."""
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            out[parts[0]] = parts[1].strip().strip('"')
    return out


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _blobs_from_modelfile(modelfile: str | None) -> list[str]:
    return re.findall(r"^FROM\s+\S*sha256[-:]([0-9a-f]{64})", modelfile or "", flags=re.M)


@dataclass
class Runtime:
    tag: str
    digest: str = ""
    quant: str = ""
    params_size: str = ""
    arch: str = ""
    capabilities: list[str] = field(default_factory=list)
    num_ctx: int | None = None
    num_gpu: int | None = None
    num_batch: int | None = None
    native_ctx: int | None = None
    rope_scaling: str | None = None
    parent: str = ""
    blobs: list[str] = field(default_factory=list)
    loaded_ctx: int | None = None
    cloud: bool = False
    show_error: str | None = None

    @property
    def is_embedding(self) -> bool:
        return "embedding" in self.capabilities and "completion" not in self.capabilities


def collect_runtime(base_url: str, fetch: FetchJSON) -> dict[str, Runtime]:
    base = base_url.rstrip("/")
    tags = fetch("GET", f"{base}/api/tags", None) or {}
    try:
        ps = fetch("GET", f"{base}/api/ps", None) or {}
    except Exception:  # /api/ps is optional evidence
        ps = {}
    loaded = {m.get("name") or m.get("model"): _int(m.get("context_length")) for m in ps.get("models", [])}
    out: dict[str, Runtime] = {}
    for m in tags.get("models", []):
        tag = m.get("name") or m.get("model")
        if not tag:
            continue
        details = m.get("details") or {}
        rt = Runtime(tag=tag, digest=(m.get("digest") or "")[:12], quant=details.get("quantization_level") or "",
                     params_size=details.get("parameter_size") or "", loaded_ctx=loaded.get(tag))
        rt.cloud = tag.endswith((":cloud", "-cloud")) or (m.get("size") or 0) < 1_000_000 or bool(m.get("remote_host"))
        try:
            show = fetch("POST", f"{base}/api/show", {"model": tag}) or {}
        except Exception as exc:
            rt.show_error = str(exc)
            out[tag] = rt
            continue
        params = parse_parameters(show.get("parameters"))
        rt.num_ctx, rt.num_gpu, rt.num_batch = _int(params.get("num_ctx")), _int(params.get("num_gpu")), _int(params.get("num_batch"))
        info = show.get("model_info") or {}
        rt.arch = str(info.get("general.architecture") or "")
        rt.native_ctx = _int(info.get(f"{rt.arch}.context_length")) if rt.arch else None
        scaling = [k for k in info if k.startswith(f"{rt.arch}.rope.scaling")]
        if scaling:
            rt.rope_scaling = ",".join(f"{k.split('.')[-1]}={info[k]}" for k in sorted(scaling))
        rt.capabilities = list(show.get("capabilities") or [])
        sd = show.get("details") or {}
        parent = sd.get("parent_model") or ""
        rt.parent = "" if ("/" in parent or parent.startswith("sha256")) else parent
        rt.blobs = _blobs_from_modelfile(show.get("modelfile"))
        rt.cloud = rt.cloud or (sd.get("format") == "" and not rt.blobs)
        out[tag] = rt
    return out


# ── L3 suits / declared HF mapping ─────────────────────────────────


def _load_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML is required")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass
class Suit:
    name: str
    path: str
    model_name: str
    variant: str | None
    num_ctx: int | None
    ctx_source: str
    num_gpu: int | None
    num_batch: int | None
    quant: str | None
    hf_model_id: str | None
    endpoint: str

    @property
    def runtime_tag(self) -> str:
        """The tag that must carry ``ollama_config`` (#3379: the variant when declared)."""
        return self.variant or self.model_name


def load_suits(suits_dir: Path) -> list[Suit]:
    suits: list[Suit] = []
    for path in sorted(suits_dir.glob("*.yaml")):
        try:
            doc = _load_yaml(path) or {}
        except Exception:
            continue
        if not str(doc.get("provider") or "").startswith("ollama"):
            continue
        mc = doc.get("model_config") or {}
        oc = mc.get("ollama_config") or {}
        if not mc.get("model_name"):
            continue
        num_ctx, src = _int(oc.get("num_ctx")), "ollama_config.num_ctx"
        if num_ctx is None:
            num_ctx, src = _int(mc.get("context_window")), "model_config.context_window"
        hf = doc.get("huggingface") or {}
        suits.append(Suit(
            name=str(doc.get("name") or path.stem), path=str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
            model_name=str(mc["model_name"]), variant=oc.get("variant"), num_ctx=num_ctx, ctx_source=src,
            num_gpu=_int(oc.get("num_gpu")), num_batch=_int(oc.get("num_batch")),
            quant=oc.get("quantization"), hf_model_id=hf.get("model_id"), endpoint=str(mc.get("endpoint") or ""),
        ))
    return suits


def load_hf_mappings(path: Path) -> dict[str, str]:
    """``ollama_variant`` -> ``hf_id`` from hf_mappings.yaml (any nesting)."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("ollama_variant") and node.get("hf_id"):
                out.setdefault(_normalize_tag(str(node["ollama_variant"])), str(node["hf_id"]))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(_load_yaml(path))
    return out


def _normalize_tag(tag: str) -> str:
    """Ollama's own rule: a name with no tag is ``:latest``. Nothing else is normalised."""
    return tag if ":" in tag.split("/")[-1] else f"{tag}:latest"


def resolve_hf_repo(tag: str, rt: Runtime | None, suits: list[Suit], mappings: dict[str, str]) -> tuple[str | None, str]:
    for s in suits:
        if s.hf_model_id and tag in (_normalize_tag(s.model_name), _normalize_tag(s.variant or "")):
            return s.hf_model_id, f"suit:{s.name}"
    if tag in mappings:
        return mappings[tag], "hf_mappings.yaml"
    if rt and rt.parent:
        parent = _normalize_tag(rt.parent)
        for s in suits:
            if s.hf_model_id and parent == _normalize_tag(s.model_name):
                return s.hf_model_id, f"parent:{rt.parent}->suit:{s.name}"
        if parent in mappings:
            return mappings[parent], f"parent:{rt.parent}->hf_mappings.yaml"
    return None, "unmapped"


# ── L2 HF card ─────────────────────────────────────────────────────


def _card_evidence_module(path: Path = DEFAULT_CARD_EVIDENCE) -> Any | None:
    """The hf-research worker's card reader (#3354), when it is on this checkout."""
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("pmoves_hf_card_evidence", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod if hasattr(mod, "load_card_evidence") else None


def hf_layer(repo: str, fetch: FetchJSON, card_module: Any | None = None, token: str | None = None) -> dict[str, Any]:
    """Licence, gated, library and native context for a declared repo."""
    out: dict[str, Any] = {"repo": repo, "license": None, "gated": None, "library": None,
                           "native_ctx": None, "rope_scaling": None, "source": None, "errors": []}
    if card_module is not None:
        ev = card_module.load_card_evidence(repo, token=token, timeout=10.0)
        out.update(license=ev.get("license"), gated=ev.get("gated"), library=ev.get("library_name"),
                   source="hf-research-agent/card_evidence")
        out["errors"].extend(ev.get("errors") or [])
    else:
        try:
            info = fetch("GET", f"{HF_BASE}/api/models/{repo}", None) or {}
            out.update(license=(info.get("cardData") or {}).get("license"), gated=info.get("gated"),
                       library=info.get("library_name"), source="hub-api")
        except Exception as exc:
            out["errors"].append(f"model_info: {exc}")
    try:
        cfg = fetch("GET", f"{HF_BASE}/{repo}/resolve/main/config.json", None) or {}
        text_cfg = cfg.get("text_config") if isinstance(cfg.get("text_config"), dict) else {}
        out["native_ctx"] = _int(cfg.get("max_position_embeddings") or text_cfg.get("max_position_embeddings"))
        out["rope_scaling"] = cfg.get("rope_scaling") or text_cfg.get("rope_scaling")
    except HTTPStatusError as exc:
        out["errors"].append(f"config.json: HTTP {exc.status}" + (" (gated)" if exc.status in (401, 403) else ""))
    except Exception as exc:
        out["errors"].append(f"config.json: {exc}")
    return out


# ── L4 demand: journal ─────────────────────────────────────────────

_RE_LOAD = re.compile(r"(?:loading model|starting (?:runner|llama-server)|loaded meta data).*?sha256[-:]([0-9a-f]{64})")
_RE_OFFLOAD = re.compile(r"offloaded (\d+)/(\d+) layers to GPU")
_RE_NCTX = re.compile(r"(?:new slot, n_ctx|llama_context: n_ctx)\s*=\s*(\d+)")
_RE_PROMPT = re.compile(r"task (\d+) \| new prompt, n_ctx_slot = (\d+).*?task\.n_tokens = (\d+)")
_RE_RELEASE = re.compile(r"task (\d+) \| stop processing: n_tokens = (\d+), truncated = (\d+)")
_RE_GIN = re.compile(r"\[GIN\].*?\|\s*(\d{3})\s*\|[^|]*\|\s*(\S+)\s*\|\s*(GET|POST|PUT|DELETE)\s+\"([^\"]+)\"")


@dataclass
class Load:
    blob: str
    n_ctx: int | None = None
    offload: tuple[int, int] | None = None


@dataclass
class SlotDemand:
    slot: int
    blob: str | None = None  # weights blob of the runner the prompt ran on (None: no load seen)
    prompts: int = 0
    max_tokens: int = 0
    full: int = 0         # task.n_tokens >= slot-1 (input clipped to the slot)
    truncated: int = 0    # release line said truncated = 1


@dataclass
class JournalFacts:
    loads: list[Load] = field(default_factory=list)
    slots: dict[tuple[str | None, int], SlotDemand] = field(default_factory=dict)
    clients: dict[tuple[str, str], int] = field(default_factory=dict)
    lines: int = 0
    skipped: str | None = None


def parse_journal(text: str) -> JournalFacts:
    """Each prompt is attributed to the most recent runner load whose n_ctx equals its
    n_ctx_slot (line order). Two runners alive with the same n_ctx cannot be told apart
    from the journal alone; the most recent one wins."""
    facts = JournalFacts()
    task_key: dict[str, tuple[str | None, int]] = {}
    current: Load | None = None
    for line in text.splitlines():
        facts.lines += 1
        m = _RE_LOAD.search(line)
        if m:
            if current is None or current.blob != m.group(1) or current.n_ctx is not None:
                current = Load(blob=m.group(1))
                facts.loads.append(current)
            continue
        m = _RE_OFFLOAD.search(line)
        if m and current is not None:
            current.offload = (int(m.group(1)), int(m.group(2)))
            continue
        m = _RE_NCTX.search(line)
        if m and current is not None and current.n_ctx is None:
            current.n_ctx = int(m.group(1))
            continue
        m = _RE_PROMPT.search(line)
        if m:
            task, slot, ntok = m.group(1), int(m.group(2)), int(m.group(3))
            blob = next((ld.blob for ld in reversed(facts.loads) if ld.n_ctx == slot), None)
            key = (blob, slot)
            task_key[task] = key
            d = facts.slots.setdefault(key, SlotDemand(slot=slot, blob=blob))
            d.prompts += 1
            d.max_tokens = max(d.max_tokens, ntok)
            if ntok >= slot - 1:
                d.full += 1
            continue
        m = _RE_RELEASE.search(line)
        if m:
            if int(m.group(3)) and m.group(1) in task_key:
                facts.slots[task_key[m.group(1)]].truncated += 1
            continue
        m = _RE_GIN.search(line)
        if m and m.group(4).startswith(("/api/chat", "/api/generate", "/api/embed", "/v1/")):
            k = (m.group(2), m.group(4))
            facts.clients[k] = facts.clients.get(k, 0) + 1
    return facts


def read_journal(since: str, unit: str = "ollama", runner: Callable[..., Any] = subprocess.run) -> tuple[str | None, str | None]:
    """(text, skip_reason). Never raises: a missing journal is a skipped layer, not a failure."""
    try:
        proc = runner(["journalctl", "-u", unit, "--since", since, "--no-pager", "-o", "short"],
                      capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        return None, "journalctl not available"
    except Exception as exc:
        return None, f"journalctl failed: {exc}"
    if proc.returncode != 0:
        return None, f"journalctl exit {proc.returncode}: {(proc.stderr or '').strip()[:160]}"
    out = proc.stdout or ""
    if "not seeing messages from other users" in (proc.stderr or "") + out and "n_ctx" not in out:
        return None, "journalctl: no permission to read the ollama unit (add the user to systemd-journal)"
    return out, None


# ── L4 demand: declared consumers ──────────────────────────────────


@dataclass
class Consumer:
    who: str
    tag: str
    ctx: int | None = None
    note: str = ""


def consumers_from_a0_presets(path: Path) -> list[Consumer]:
    if not path.exists():
        return []
    out: list[Consumer] = []
    for preset in _load_yaml(path) or []:
        if not isinstance(preset, dict):
            continue
        for role in ("chat", "utility", "embedding"):
            cfg = preset.get(role) or {}
            if str(cfg.get("provider") or "") != "ollama" or not cfg.get("name"):
                continue
            out.append(Consumer(who=f"A0 preset '{preset.get('name')}' {role}", tag=_normalize_tag(str(cfg["name"])),
                                ctx=_int(cfg.get("ctx_length"))))
    return out


def tz_embedding_targets(path: Path) -> dict[str, str]:
    """TensorZero ``embedding_models.<name>`` -> Ollama tag, for providers on :11434."""
    if tomllib is None or not path.exists():
        return {}
    with path.open("rb") as fh:
        doc = tomllib.load(fh)
    out: dict[str, str] = {}
    for name, cfg in (doc.get("embedding_models") or {}).items():
        for prov in (cfg.get("providers") or {}).values():
            if ":11434" in str(prov.get("api_base") or "") and prov.get("model_name"):
                out[name] = _normalize_tag(str(prov["model_name"]))
    return out


_RE_DEFAULT = re.compile(r"^\$\{[A-Z0-9_]+:-([^}]*)\}$")


def consumers_from_compose(compose_files: Iterable[Path], tz_embed: dict[str, str], known_tags: set[str]) -> list[Consumer]:
    """Compose env DEFAULTS only (``${VAR:-default}`` or a literal); env files are never read."""
    out: list[Consumer] = []
    for path in compose_files:
        try:
            doc = _load_yaml(path) or {}
        except Exception:
            continue
        for svc, spec in (doc.get("services") or {}).items():
            env = (spec or {}).get("environment") or {}
            items = env.items() if isinstance(env, dict) else (e.split("=", 1) for e in env if isinstance(e, str) and "=" in e)
            for key, raw in items:
                if "MODEL" not in str(key):
                    continue
                val = str(raw or "").strip()
                m = _RE_DEFAULT.match(val)
                val = m.group(1) if m else val
                tz = re.match(r"^tensorzero::embedding_model_name::(\S+)$", val)
                if tz and tz.group(1) in tz_embed:
                    out.append(Consumer(who=f"{svc} ({key} -> TensorZero {tz.group(1)})", tag=tz_embed[tz.group(1)],
                                        note=f"{path.name} default"))
                elif val and _normalize_tag(val) in known_tags:
                    out.append(Consumer(who=f"{svc} ({key})", tag=_normalize_tag(val), note=f"{path.name} default"))
    return out


# ── Join + verdicts ────────────────────────────────────────────────


@dataclass
class Verdict:
    kind: str
    severity: str  # conflict | warn | info
    evidence: str


@dataclass
class Row:
    tag: str
    runtime: Runtime | None
    suits: list[str] = field(default_factory=list)
    hf_repo: str | None = None
    hf_source: str = "unmapped"
    hf: dict[str, Any] | None = None
    effective_slot: int | None = None
    slot_source: str = ""
    offload: tuple[int, int] | None = None
    demand: list[dict[str, Any]] = field(default_factory=list)
    consumers: list[str] = field(default_factory=list)
    verdicts: list[Verdict] = field(default_factory=list)

    @property
    def primary(self) -> str:
        kinds = {v.kind for v in self.verdicts}
        return next((k for k in VERDICT_ORDER if k in kinds), "OK")


def attribute_slots(facts: JournalFacts, runtime: dict[str, Runtime]) -> dict[str, list[tuple[SlotDemand, bool]]]:
    """Slot demand -> tags. Each demand carries the weights blob of its runner; the tags
    built on that blob are the candidates. A tag whose own num_ctx contradicts the slot
    is dropped; ``/api/ps`` naming the tag at that ctx wins; otherwise a tag whose
    num_ctx equals the slot (the variant that asked for it) beats tags on the server
    default. Returns tag -> [(demand, ambiguous)]."""
    blob_tags: dict[str, list[str]] = {}
    for tag, rt in runtime.items():
        for b in rt.blobs:
            blob_tags.setdefault(b, []).append(tag)
    out: dict[str, list[tuple[SlotDemand, bool]]] = {}
    for demand in facts.slots.values():
        if demand.blob is not None:
            cands = set(blob_tags.get(demand.blob, ()))
        else:  # no load in the window: fall back to whatever /api/ps says is resident at this ctx
            cands = {t for t, rt in runtime.items() if rt.loaded_ctx == demand.slot}
        cands = {t for t in cands if runtime[t].num_ctx in (None, demand.slot)}
        chosen = ({t for t in cands if runtime[t].loaded_ctx == demand.slot}
                  or {t for t in cands if runtime[t].num_ctx == demand.slot}
                  or cands)
        for t in chosen:
            out.setdefault(t, []).append((demand, len(chosen) > 1))
    return out


def build_rows(runtime: dict[str, Runtime], suits: list[Suit], mappings: dict[str, str], facts: JournalFacts | None,
               consumers: list[Consumer], *, unified_memory: bool, output_reserve: int,
               hf_lookup: Callable[[str], dict[str, Any]] | None) -> list[Row]:
    rows: dict[str, Row] = {tag: Row(tag=tag, runtime=rt) for tag, rt in runtime.items()}

    # Per-blob measured offload / load ctx from the journal (last load wins).
    blob_load: dict[str, Load] = {}
    for ld in (facts.loads if facts else []):
        blob_load[ld.blob] = ld
    attributed = attribute_slots(facts, runtime) if facts else {}

    for tag, row in rows.items():
        rt = row.runtime
        assert rt is not None
        if rt.num_ctx:
            row.effective_slot, row.slot_source = rt.num_ctx, "tag num_ctx"
        elif rt.loaded_ctx:
            row.effective_slot, row.slot_source = rt.loaded_ctx, "/api/ps (server default)"
        elif attributed.get(tag):
            # The slot this tag's own prompts ran in. A sibling variant on the same
            # weights may have loaded the blob at a different n_ctx.
            row.effective_slot = min(d.slot for d, _ in attributed[tag])
            row.slot_source = "journal prompts (server default)"
        else:
            lds = [blob_load[b] for b in rt.blobs if b in blob_load and blob_load[b].n_ctx]
            if lds:
                row.effective_slot, row.slot_source = lds[-1].n_ctx, "journal load (server default)"
        offs = [blob_load[b].offload for b in rt.blobs if b in blob_load and blob_load[b].offload]
        row.offload = offs[-1] if offs else None
        for demand, ambiguous in attributed.get(tag, []):
            row.demand.append({"slot": demand.slot, "prompts": demand.prompts, "max_tokens": demand.max_tokens,
                               "full": demand.full, "truncated": demand.truncated, "ambiguous": ambiguous})

    # Suits (L3).
    for s in suits:
        tag = _normalize_tag(s.runtime_tag)
        row = rows.get(tag)
        if row is None:
            row = rows.setdefault(tag, Row(tag=tag, runtime=None))
            row.suits.append(s.name)
            row.verdicts.append(Verdict("SUIT-DRIFT", "conflict",
                                        f"suit {s.name} ({s.path}) names {tag}, which is not installed on this Ollama"))
            continue
        row.suits.append(s.name)
        rt = row.runtime
        assert rt is not None
        diffs = []
        for key, want, have in (("num_gpu", s.num_gpu, rt.num_gpu), ("num_ctx", s.num_ctx, rt.num_ctx), ("num_batch", s.num_batch, rt.num_batch)):
            if want is not None and want != have:
                src = s.ctx_source if key == "num_ctx" else f"ollama_config.{key}"
                diffs.append(f"{key} suit={want} ({src}) tag={have if have is not None else 'unset'}")
        if s.quant and rt.quant and not rt.quant.upper().startswith(str(s.quant).upper()):
            diffs.append(f"quantization suit={s.quant} tag={rt.quant}")
        if diffs:
            row.verdicts.append(Verdict("SUIT-DRIFT", "conflict", f"suit {s.name}: " + "; ".join(diffs)))

    # Declared consumers (L4 static).
    for c in consumers:
        row = rows.get(c.tag)
        label = c.who + (f" ctx_length={c.ctx}" if c.ctx else "") + (f" [{c.note}]" if c.note else "")
        if row is None or row.runtime is None:
            row = rows.setdefault(c.tag, Row(tag=c.tag, runtime=None))
            row.consumers.append(label)
            row.verdicts.append(Verdict("NOT-INSTALLED", "conflict", f"{c.who} requests {c.tag}, not installed"))
            continue
        row.consumers.append(label)
        if c.ctx and row.effective_slot and c.ctx > row.effective_slot:
            row.verdicts.append(Verdict("TRUNCATING", "conflict",
                                        f"{c.who} budgets ctx_length={c.ctx} but the slot is {row.effective_slot} "
                                        f"({row.slot_source}); prompts past {row.effective_slot} tokens are cut"))

    # Per-row runtime/HF/demand verdicts.
    for tag, row in rows.items():
        rt = row.runtime
        if rt is None:
            continue
        if rt.cloud:
            row.hf_source = "cloud"
            continue
        consumed = bool(row.consumers or row.demand or rt.loaded_ctx)
        # Measured demand.
        for d in row.demand:
            amb = " (slot shared by several tags; attribution ambiguous)" if d["ambiguous"] else ""
            if d["truncated"]:
                row.verdicts.append(Verdict("TRUNCATING", "conflict",
                                            f"journal: {d['truncated']}/{d['prompts']} prompts in the {d['slot']} slot released truncated=1{amb}"))
            if d["full"]:
                row.verdicts.append(Verdict("TRUNCATING", "conflict",
                                            f"journal: {d['full']}/{d['prompts']} inputs hit task.n_tokens={d['max_tokens']} "
                                            f"= slot {d['slot']}-1, i.e. clipped to fit{amb}"))
            elif not rt.is_embedding and d["max_tokens"] + output_reserve > d["slot"]:
                head = f"; native {rt.native_ctx} allows a larger num_ctx" if rt.native_ctx and rt.native_ctx > d["slot"] else ""
                row.verdicts.append(Verdict("TRUNCATING", "conflict",
                                            f"journal: max prompt {d['max_tokens']} + {output_reserve} output reserve > slot {d['slot']}{head}{amb}"))
        # Over native.
        requested = [(rt.num_ctx, "tag num_ctx"), (rt.loaded_ctx, "/api/ps context_length")]
        requested += [(s.num_ctx, f"suit {s.name} {s.ctx_source}") for s in suits if _normalize_tag(s.runtime_tag) == tag]
        native = rt.native_ctx
        native_src = "GGUF context_length"
        if native is None and row.hf and row.hf.get("native_ctx"):
            native, native_src = row.hf["native_ctx"], "HF config.json max_position_embeddings"
        if native:
            for val, src in requested:
                if val and val > native and not rt.rope_scaling:
                    row.verdicts.append(Verdict("OVER-NATIVE", "conflict",
                                                f"{src}={val} > native {native} ({native_src}) with no rope scaling"))
        # GPU offload.
        # A partial offload measured on shared weights cannot come from a tag that pins num_gpu.
        if row.offload and row.offload[0] < row.offload[1] and not rt.num_gpu:
            row.verdicts.append(Verdict("UNDER-GPU", "conflict" if consumed else "warn",
                                        f"journal: offloaded {row.offload[0]}/{row.offload[1]} layers to GPU"
                                        + ("" if rt.num_gpu else "; num_gpu unset")))
        elif unified_memory and rt.num_gpu is None and not (row.offload and row.offload[0] >= row.offload[1]):
            row.verdicts.append(Verdict("UNDER-GPU", "conflict" if consumed else "warn",
                                        "num_gpu unset on a unified-memory node: Ollama sizes offload from 'free' "
                                        "memory and loads part of the layers on CPU (set num_gpu 999 via a suit variant)"))

    # HF (L2) -- after the cheap layers so --no-hf still yields a full row.
    for tag, row in rows.items():
        if row.runtime is not None and row.runtime.cloud:
            continue
        row.hf_repo, row.hf_source = resolve_hf_repo(tag, row.runtime, suits, mappings)
        if row.hf_repo is None:
            row.verdicts.append(Verdict("UNMAPPED", "info", "no suit huggingface.model_id, hf_mappings ollama_variant, or mapped parent tag"))
            continue
        if hf_lookup is not None:
            row.hf = hf_lookup(row.hf_repo)
            rt = row.runtime
            if rt and rt.native_ctx and row.hf.get("native_ctx") and row.hf["native_ctx"] != rt.native_ctx:
                row.verdicts.append(Verdict("OK", "info",
                                            f"native ctx differs: GGUF {rt.native_ctx} vs HF {row.hf['native_ctx']} ({row.hf_repo})"))
            if rt and not rt.native_ctx and row.hf.get("native_ctx") and not row.hf.get("rope_scaling"):
                for val, src in ((rt.num_ctx, "tag num_ctx"), (rt.loaded_ctx, "/api/ps context_length")):
                    if val and val > row.hf["native_ctx"]:
                        row.verdicts.append(Verdict("OVER-NATIVE", "conflict",
                                                    f"{src}={val} > HF max_position_embeddings {row.hf['native_ctx']} with no rope_scaling"))
    return sorted(rows.values(), key=lambda r: (VERDICT_ORDER.index(r.primary), r.tag))


# ── Output ─────────────────────────────────────────────────────────


def _fmt(v: Any) -> str:
    return "-" if v in (None, "") else str(v)


def render_table(rows: list[Row], facts: JournalFacts | None, notes: list[str]) -> str:
    hdr = ["MODEL", "NATIVE", "NUM_CTX", "SLOT", "NUM_GPU", "GPU_LAYERS", "SUIT", "HF", "MAX_DEMAND", "VERDICT"]
    body = []
    for r in rows:
        rt = r.runtime
        demand = max((d["max_tokens"] for d in r.demand), default=None)
        slots = sorted({d["slot"] for d in r.demand})
        body.append([
            r.tag + ("" if rt else " (absent)"),
            _fmt(rt.native_ctx if rt else None),
            _fmt(rt.num_ctx if rt else None),
            _fmt(r.effective_slot),
            _fmt(rt.num_gpu if rt else None),
            f"{r.offload[0]}/{r.offload[1]}" if r.offload else "-",
            ",".join(r.suits) or "-",
            r.hf_repo or r.hf_source,
            f"{demand}/{','.join(map(str, slots))}" if demand is not None else "-",
            r.primary,
        ])
    widths = [max(len(str(x)) for x in col) for col in zip(hdr, *body)] if body else [len(h) for h in hdr]
    lines = ["  ".join(h.ljust(w) for h, w in zip(hdr, widths))]
    lines += ["  ".join(str(c).ljust(w) for c, w in zip(rowv, widths)) for rowv in body]
    lines.append("")
    lines.append("Evidence:")
    for r in rows:
        for v in r.verdicts:
            if v.kind == "OK" and v.severity == "info":
                lines.append(f"  {r.tag}: note: {v.evidence}")
            elif v.kind not in ("OK", "UNMAPPED"):
                lines.append(f"  {r.tag}: {v.kind} [{v.severity}] {v.evidence}")
        for c in r.consumers:
            lines.append(f"  {r.tag}: consumer: {c}")
        if r.hf:
            lines.append(f"  {r.tag}: hf {r.hf['repo']} ({r.hf_source}) licence={_fmt(r.hf.get('license'))} "
                         f"gated={_fmt(r.hf.get('gated'))} library={_fmt(r.hf.get('library'))} "
                         f"native={_fmt(r.hf.get('native_ctx'))}" + (f" errors={r.hf['errors']}" if r.hf.get("errors") else ""))
    if facts is not None and facts.clients:
        lines.append("")
        lines.append("Ollama clients seen in the journal window (ip  path  requests):")
        for (ip, path), n in sorted(facts.clients.items(), key=lambda kv: -kv[1])[:12]:
            lines.append(f"  {ip}  {path}  {n}")
    for n in notes:
        lines.append(f"note: {n}")
    return "\n".join(lines)


def rows_json(rows: list[Row], facts: JournalFacts | None, notes: list[str]) -> dict[str, Any]:
    def rt_dict(rt: Runtime | None) -> dict[str, Any] | None:
        return None if rt is None else {k: getattr(rt, k) for k in (
            "digest", "quant", "params_size", "arch", "capabilities", "num_ctx", "num_gpu", "num_batch",
            "native_ctx", "rope_scaling", "parent", "blobs", "loaded_ctx", "cloud", "show_error")}
    return {
        "rows": [{
            "tag": r.tag, "verdict": r.primary, "runtime": rt_dict(r.runtime), "suits": r.suits,
            "hf": {"repo": r.hf_repo, "source": r.hf_source, **({k: v for k, v in r.hf.items() if k != "repo"} if r.hf else {})},
            "effective_slot": r.effective_slot, "slot_source": r.slot_source,
            "gpu_layers": list(r.offload) if r.offload else None, "demand": r.demand, "consumers": r.consumers,
            "verdicts": [{"kind": v.kind, "severity": v.severity, "evidence": v.evidence} for v in r.verdicts],
        } for r in rows],
        "journal": None if facts is None else {
            "lines": facts.lines, "skipped": facts.skipped,
            "clients": [{"ip": ip, "path": p, "requests": n} for (ip, p), n in sorted(facts.clients.items(), key=lambda kv: -kv[1])],
        },
        "notes": notes,
    }


def has_conflict(rows: list[Row]) -> bool:
    return any(v.severity == "conflict" for r in rows for v in r.verdicts)


def detect_unified_memory() -> bool:
    """DGX Spark (GB10) and other aarch64 Linux GPU hosts share one memory pool."""
    if os.environ.get("PMOVES_UNIFIED_MEMORY", "").lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("PMOVES_UNIFIED_MEMORY", "").lower() in ("0", "false", "no"):
        return False
    return Path("/etc/dgx-release").exists() or (platform.system() == "Linux" and platform.machine() == "aarch64")


# ── CLI ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None, *, fetch: FetchJSON | None = None,
         journal_runner: Callable[..., Any] = subprocess.run) -> int:
    ap = argparse.ArgumentParser(prog="local_model_map", description=__doc__.split("\n\n")[0])
    ap.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    ap.add_argument("--since", default="-24h", help="journalctl --since window (default -24h)")
    ap.add_argument("--journal-file", type=Path, help="read journal text from a file instead of journalctl")
    ap.add_argument("--no-journal", action="store_true")
    ap.add_argument("--no-hf", action="store_true", help="skip the Hugging Face network layer")
    ap.add_argument("--suits-dir", type=Path, default=DEFAULT_SUITS_DIR)
    ap.add_argument("--hf-mappings", type=Path, default=DEFAULT_HF_MAPPINGS)
    ap.add_argument("--a0-presets", type=Path, default=DEFAULT_A0_PRESETS)
    ap.add_argument("--tz-config", type=Path, default=DEFAULT_TZ_CONFIG)
    ap.add_argument("--compose", type=Path, action="append", help="compose file(s) to read env defaults from")
    ap.add_argument("--card-evidence", type=Path, default=DEFAULT_CARD_EVIDENCE)
    ap.add_argument("--output-reserve", type=int, default=2048, help="tokens a completion needs beyond the prompt")
    mem = ap.add_mutually_exclusive_group()
    mem.add_argument("--unified-memory", dest="unified", action="store_true", default=None)
    mem.add_argument("--no-unified-memory", dest="unified", action="store_false")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true", help="exit 1 when any layer conflicts")
    args = ap.parse_args(argv)

    fetch = fetch or urllib_fetch_json
    notes: list[str] = []
    try:
        runtime = collect_runtime(args.ollama_url, fetch)
    except Exception as exc:
        print(f"COULD-NOT-MEASURE: Ollama at {args.ollama_url} unreachable: {exc}", file=sys.stderr)
        return EXIT_COULD_NOT_MEASURE

    suits = load_suits(args.suits_dir) if args.suits_dir.exists() else []
    mappings = load_hf_mappings(args.hf_mappings)

    facts: JournalFacts | None = None
    if args.journal_file:
        facts = parse_journal(args.journal_file.read_text(encoding="utf-8", errors="replace"))
    elif not args.no_journal:
        text, skip = read_journal(args.since, runner=journal_runner)
        if text is None:
            facts = JournalFacts(skipped=skip)
            notes.append(f"demand layer (journal) skipped: {skip}")
        else:
            facts = parse_journal(text)

    known = set(runtime) | {_normalize_tag(s.runtime_tag) for s in suits}
    tz_embed = tz_embedding_targets(args.tz_config)
    compose_files = args.compose if args.compose is not None else sorted(PMOVES.glob("docker-compose*.yml"))
    consumers = consumers_from_a0_presets(args.a0_presets) + consumers_from_compose(compose_files, tz_embed, known)
    if not args.a0_presets.exists():
        notes.append(f"A0 presets not found at {args.a0_presets}")

    hf_lookup = None
    if not args.no_hf:
        if "huggingface_hub" not in sys.modules and "HF_HUB_CACHE" not in os.environ:
            # card_evidence reads the card through hf_hub_download, which caches.
            # Point that at a throwaway dir so this read-only tool leaves the
            # host's HF cache untouched.
            import tempfile
            os.environ["HF_HUB_CACHE"] = tempfile.mkdtemp(prefix="local-model-map-hf-")
        card_mod = _card_evidence_module(args.card_evidence)
        notes.append("HF layer: " + ("hf-research-agent card_evidence (#3354)" if card_mod else
                                     "Hub REST API (card_evidence module not on this checkout; #3354 adds it)"))
        token = os.environ.get("HF_TOKEN") or None
        headers = {"authorization": f"Bearer {token}"} if token else None
        cache: dict[str, dict[str, Any]] = {}

        def hf_fetch(method: str, url: str, body: Any = None) -> Any:
            if fetch is not urllib_fetch_json:
                return fetch(method, url, body)
            return urllib_fetch_json(method, url, body, headers=headers)

        def hf_lookup(repo: str) -> dict[str, Any]:  # type: ignore[no-redef]
            if repo not in cache:
                cache[repo] = hf_layer(repo, hf_fetch, card_mod, token)
            return cache[repo]

    unified = detect_unified_memory() if args.unified is None else args.unified
    rows = build_rows(runtime, suits, mappings, facts, consumers, unified_memory=unified,
                      output_reserve=args.output_reserve, hf_lookup=hf_lookup)
    if args.json:
        print(json.dumps(rows_json(rows, facts, notes), indent=2, default=str))
    else:
        print(render_table(rows, facts, notes))
    if args.check and has_conflict(rows):
        return EXIT_CONFLICT
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
