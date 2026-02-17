from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Set


@dataclass
class QueryRecord:
    """Flattened notebook query definition."""

    query: str
    namespace: str
    gold_ids: List[str]
    source_path: Path
    notebook_id: Optional[str]
    metadata: Dict[str, Any]
    tags: List[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export synced notebook query annotations into retrieval-eval JSONL format. "
            "Each output line contains {query, namespace, gold_ids, metadata, tags}."
        )
    )
    parser.add_argument(
        "--source",
        required=True,
        nargs="+",
        help=(
            "Path(s) to synced notebook JSON/JSONL payloads. Directories are searched recursively "
            "for '*.json*' files."
        ),
    )
    parser.add_argument(
        "--chunks",
        nargs="+",
        help=(
            "Optional extract-worker payloads used to validate gold chunk_ids. Accepts JSON or JSONL. "
            "When omitted, gold_ids are not validated."
        ),
    )
    parser.add_argument(
        "--namespace",
        default="pmoves",
        help="Default namespace applied when records omit an explicit namespace.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Destination JSONL file for the flattened dataset.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any gold chunk_id is missing from the provided extract-worker payloads.",
    )
    return parser.parse_args()


def iter_source_files(paths: Sequence[str]) -> Iterator[Path]:
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(f"Source path not found: {path}")
        if path.is_dir():
            for child in sorted(path.rglob("*.json")):
                if child.is_file():
                    yield child
            for child in sorted(path.rglob("*.jsonl")):
                if child.is_file():
                    yield child
        else:
            suffix = path.suffix.lower()
            if suffix not in {".json", ".jsonl"}:
                raise ValueError(f"Unsupported source file type: {path}")
            yield path


def load_json_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON from {path}: {exc}") from exc


def load_jsonl_file(path: Path) -> List[Any]:
    rows: List[Any] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSONL from {path}:{line_no}: {exc}") from exc
    return rows


def normalize_iterable(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def ensure_str_list(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    for v in values:
        if v is None:
            continue
        if not isinstance(v, str):
            raise TypeError(f"Gold chunk id must be str, got {type(v)!r} ({v!r})")
        if v:
            out.append(v)
    return out


def gather_chunk_ids(data: Any, out: Optional[Set[str]] = None) -> Set[str]:
    if out is None:
        out = set()
    if isinstance(data, Mapping):
        maybe_chunk = data.get("chunk_id")
        if isinstance(maybe_chunk, str) and maybe_chunk:
            out.add(maybe_chunk)
        for value in data.values():
            gather_chunk_ids(value, out)
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            gather_chunk_ids(item, out)
    return out


def load_chunk_index(paths: Optional[Sequence[str]]) -> Set[str]:
    if not paths:
        return set()
    chunk_ids: Set[str] = set()
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(f"Chunks payload not found: {path}")
        if path.is_dir():
            for child in sorted(path.rglob("*.json")):
                chunk_ids.update(gather_chunk_ids(load_json_file(child)))
            for child in sorted(path.rglob("*.jsonl")):
                for row in load_jsonl_file(child):
                    chunk_ids.update(gather_chunk_ids(row))
        else:
            if path.suffix.lower() == ".jsonl":
                for row in load_jsonl_file(path):
                    chunk_ids.update(gather_chunk_ids(row))
            else:
                chunk_ids.update(gather_chunk_ids(load_json_file(path)))
    return chunk_ids


def merge_metadata(*items: Mapping[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for item in items:
        for key, value in item.items():
            if value is None:
                continue
            if isinstance(value, Mapping):
                base = merged.get(key)
                if isinstance(base, MutableMapping):
                    base.update(value)  # type: ignore[arg-type]
                else:
                    merged[key] = dict(value)
            else:
                merged[key] = value
    return merged


def extract_queries(payload: Any, *, default_namespace: str, source_path: Path) -> Iterator[QueryRecord]:
    if payload is None:
        return
    if isinstance(payload, list):
        for item in payload:
            yield from extract_queries(item, default_namespace=default_namespace, source_path=source_path)
        return
    if not isinstance(payload, Mapping):
        return

    notebook_id = payload.get("notebook_id") or payload.get("id") or payload.get("name")
    namespace = payload.get("namespace") or default_namespace
    queries: Iterable[Any]
    if "queries" in payload and isinstance(payload["queries"], Iterable):
        queries = payload["queries"]
    elif "entries" in payload and isinstance(payload["entries"], Iterable):
        queries = payload["entries"]
    elif "cells" in payload and isinstance(payload["cells"], Iterable):
        queries = payload["cells"]
    elif "query" in payload:
        queries = [payload]
    else:
        # Some sync payloads nest notebooks under a top-level object
        for key in ("notebooks", "items", "data"):
            maybe = payload.get(key)
            if isinstance(maybe, Iterable):
                for item in maybe:
                    yield from extract_queries(item, default_namespace=default_namespace, source_path=source_path)
                return
        return

    for entry in queries:
        if not isinstance(entry, Mapping):
            continue
        query_text = entry.get("query") or entry.get("text")
        if not isinstance(query_text, str) or not query_text.strip():
            continue
        entry_namespace = entry.get("namespace") or namespace or default_namespace
        gold_fields = (
            entry.get("gold_chunks"),
            entry.get("gold_ids"),
            entry.get("chunk_ids"),
            entry.get("relevant"),
            entry.get("chunks"),
        )
        gold_ids: List[str] = []
        for field in gold_fields:
            if isinstance(field, Mapping):
                # Some payloads embed {ids: [...]} wrappers
                if "ids" in field:
                    gold_ids.extend(ensure_str_list(field.get("ids")))
                elif "chunk_ids" in field:
                    gold_ids.extend(ensure_str_list(field.get("chunk_ids")))
            else:
                gold_ids.extend(ensure_str_list(normalize_iterable(field)))
        if not gold_ids:
            continue
        tags = ensure_str_list(normalize_iterable(entry.get("tags")))
        metadata = merge_metadata(
            {"source_path": str(source_path)},
            {"notebook_id": notebook_id} if notebook_id else {},
            payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {},
            {"title": payload.get("title")} if payload.get("title") else {},
            entry,
        )
        # Remove potentially large or redundant fields
        for drop_key in ("gold_chunks", "gold_ids", "chunk_ids", "chunks", "relevant", "query", "tags"):
            metadata.pop(drop_key, None)
        yield QueryRecord(
            query=query_text.strip(),
            namespace=str(entry_namespace),
            gold_ids=gold_ids,
            source_path=source_path,
            notebook_id=notebook_id,
            metadata=metadata,
            tags=tags,
        )


def write_jsonl(path: Path, records: Iterable[QueryRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            obj = {
                "query": rec.query,
                "namespace": rec.namespace,
                "gold_ids": rec.gold_ids,
                "metadata": rec.metadata,
            }
            if rec.tags:
                obj["tags"] = rec.tags
            fh.write(json.dumps(obj, ensure_ascii=False))
            fh.write("\n")


def main() -> None:
    args = parse_args()
    chunk_index = load_chunk_index(args.chunks)
    records: List[QueryRecord] = []
    missing: Dict[str, Set[str]] = {}

    for source_path in iter_source_files(args.source):
        data: Any
        if source_path.suffix.lower() == ".jsonl":
            data = load_jsonl_file(source_path)
        else:
            data = load_json_file(source_path)
        for record in extract_queries(data, default_namespace=args.namespace, source_path=source_path):
            if chunk_index:
                absent = {cid for cid in record.gold_ids if cid not in chunk_index}
                if absent:
                    missing.setdefault(str(source_path), set()).update(absent)
                    if args.strict:
                        raise ValueError(
                            f"Missing chunk ids for {source_path}: {', '.join(sorted(absent))}"
                        )
            records.append(record)

    if missing and not args.strict:
        for src, absent in missing.items():
            print(
                f"[warn] {src} references {len(absent)} chunk ids not present in extract payloads: "
                + ", ".join(sorted(absent)),
                file=sys.stderr,
            )

    if not records:
        raise SystemExit("No notebook queries exported; ensure source payloads contain query annotations.")

    write_jsonl(Path(args.output), records)
    print(f"Wrote {len(records)} queries → {args.output}")


if __name__ == "__main__":
    main()
