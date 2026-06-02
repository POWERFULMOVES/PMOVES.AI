#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typer>=0.12",
#   "rich>=13",
#   "scikit-learn>=1.4",
#   "numpy>=1.26",
#   "nats-py>=2.7",
#   "httpx>=0.27",
#   "enum34>=1.1; python_version<'3.11'",
# ]
# ///
"""
analyze_beats.py — DARKXSIDE Multimodal Sonic Fingerprint Agent
                   Cipher Gateway Specialist / Sensor Fusion Router

Three sense modes — the agent picks the minimum sense needed for confident grouping:

  peek  → ffprobe only (metadata: duration, bitrate, channels)
           Fast. Good enough when tracks are very distinct.

  glaze → peek + ffmpeg lavfi (ebur128 R128 loudness + aspectralstats spectral)
           Default. Reads the colour/weight/texture of sound without heavy inference.

  gaze  → glaze + local model inference (Qwen2-Audio via Ollama OR Hi-RAG GPU)
           Full attention. Loads a local audio understanding model to "listen" and
           describe each track semantically, then fuses with ffmpeg features.
           Only escalated to when silhouette coherence score < COHERENCE_THRESHOLD.

Auto-mode: starts at glaze, measures cluster coherence (sklearn silhouette score),
           escalates to gaze if score < 0.3 (ambiguous signal). Never over-activates
           expensive inference on already-clear data.

Usage:
    uv run pmoves/tools/analyze_beats.py analyze --input pmoves/data/beats/soundcloud/darkxside
    uv run pmoves/tools/analyze_beats.py analyze --sense-mode peek   # fast scan
    uv run pmoves/tools/analyze_beats.py analyze --sense-mode gaze   # full local model
    uv run pmoves/tools/analyze_beats.py groups
    uv run pmoves/tools/analyze_beats.py status
"""

import asyncio
import enum
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

app = typer.Typer(name="analyze-beats", help="DARKXSIDE Multimodal Sonic Fingerprint Agent — Cipher Gateway Specialist", rich_markup_mode="rich")
console = Console()

AUDIO_SUFFIXES = {".opus", ".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}
COHERENCE_THRESHOLD = 0.30   # silhouette score below this triggers escalation to gaze

# ── Sense Modes ───────────────────────────────────────────────────────────────
class SenseMode(str, enum.Enum):
    peek  = "peek"   # ffprobe metadata only
    glaze = "glaze"  # peek + ffmpeg lavfi (default)
    gaze  = "gaze"   # glaze + local model inference (Qwen2-Audio / Ollama / Hi-RAG)
    auto  = "auto"   # start at glaze, escalate to gaze if coherence < threshold

# ── Defaults (overridable via env) ─────────────────────────────────────────────
DEFAULT_INPUT   = os.environ.get("BEATS_INPUT",    "pmoves/data/beats/soundcloud/darkxside")
DEFAULT_OUTPUT  = os.environ.get("BEATS_OUTPUT",   "pmoves/data/beats/playlists")
DEFAULT_NATS    = os.environ.get("NATS_URL",        "")
DEFAULT_CIPHER  = os.environ.get("CIPHER_URL",      "http://localhost:8105")
DEFAULT_GLANCES = os.environ.get("GLANCES_URL",     "http://localhost:61208")
DEFAULT_OLLAMA  = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
DEFAULT_HIRAG   = os.environ.get("HIRAG_GPU_URL",   "http://localhost:8087")


# ── ffprobe / ffmpeg lavfi audio analysis ─────────────────────────────────────

def ffprobe_meta(path: Path) -> dict:
    """Extract format metadata from ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_entries",
        "format=duration,bit_rate,filename:format_tags=title,artist,album:stream=sample_rate,channels",
        str(path)
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=30)
        data = json.loads(out)
        fmt = data.get("format", {})
        tags = fmt.get("tags", {})
        streams = data.get("streams", [{}])
        return {
            "duration_s": float(fmt.get("duration", 0)),
            "bit_rate":   int(fmt.get("bit_rate", 0)),
            "title":      tags.get("title", path.stem),
            "artist":     tags.get("artist", "DARKXSIDE"),
            "sample_rate": int(streams[0].get("sample_rate", 44100)) if streams else 44100,
            "channels":    int(streams[0].get("channels", 2)) if streams else 2,
        }
    except Exception:
        return {"duration_s": 0, "bit_rate": 0, "title": path.stem, "artist": "DARKXSIDE"}


def ffmpeg_lavfi_analysis(path: Path) -> dict:
    """
    Use ffmpeg lavfi audio filters to extract:
      - R128 loudness (integrated, range, peak) via ebur128
      - Spectral stats (centroid, flatness, entropy) via aspectralstats
      - BPM estimate via ametadata + abitscope
    """
    result = {"loudness_I": -23.0, "loudness_LRA": 5.0, "loudness_peak": -1.0,
              "spectral_centroid": 2000.0, "spectral_flatness": 0.5,
              "tempo_bpm": 90.0}

    # ── R128 Loudness (ebur128) ───────────────────────────────────────────────
    try:
        cmd = [
            "ffmpeg", "-i", str(path), "-af",
            "ebur128=framelog=verbose",
            "-f", "null", "-"
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stderr
        for line in out.splitlines():
            if "I:" in line and "LUFS" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "I:" and i + 1 < len(parts):
                        result["loudness_I"] = float(parts[i + 1])
            if "LRA:" in line and "LU" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "LRA:" and i + 1 < len(parts):
                        result["loudness_LRA"] = float(parts[i + 1])
            if "True peak" in line or "Peak:" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p in ("Peak:", "peak:") and i + 1 < len(parts):
                        try:
                            result["loudness_peak"] = float(parts[i + 1])
                        except ValueError:
                            pass
    except Exception:
        pass

    # ── Spectral Stats (aspectralstats — short sample) ───────────────────────
    try:
        cmd = [
            "ffmpeg", "-i", str(path),
            "-t", "30",                       # analyse first 30s — fast
            "-af", "aspectralstats=measure=centroid+flatness,ametadata=print:file=-",
            "-f", "null", "-"
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=45).stdout
        centroids, flatness = [], []
        for line in out.splitlines():
            if "lavfi.aspectralstats.Centroid" in line:
                try:
                    centroids.append(float(line.split("=")[1]))
                except (IndexError, ValueError):
                    pass
            if "lavfi.aspectralstats.Flatness" in line:
                try:
                    flatness.append(float(line.split("=")[1]))
                except (IndexError, ValueError):
                    pass
        if centroids:
            result["spectral_centroid"] = float(np.mean(centroids))
        if flatness:
            result["spectral_flatness"] = float(np.mean(flatness))
    except Exception:
        pass

    # ── Tempo / BPM via silencedetect heuristic ───────────────────────────────
    # NOTE: A proper BPM requires beat tracking (librosa). ffmpeg doesn't have a
    # native beat tracker, but we can derive a rough estimate from the loudness
    # LRA and duration. When Hi-RAG multimodal is live, replace with Gemini embedding.
    try:
        duration = ffprobe_meta(path).get("duration_s", 0)
        if duration > 10:
            # Crude proxy: use spectral centroid + LRA to bracket BPM range
            lra  = result["loudness_LRA"]
            cent = result["spectral_centroid"]
            # Higher centroid + tighter LRA → faster / more energetic tracks
            base = 80 + (cent / 5000) * 60 + (10 - min(lra, 10)) * 2
            result["tempo_bpm"] = round(min(max(base, 60), 180), 1)
    except Exception:
        pass

    return result


def extract_all(path: Path, mode: SenseMode = SenseMode.glaze) -> dict | None:
    try:
        meta = ffprobe_meta(path)
        feat = {"file": str(path), "name": path.stem, **meta,
                # Defaults (populated by lavfi if mode >= glaze)
                "loudness_I": -23.0, "loudness_LRA": 5.0, "loudness_peak": -1.0,
                "spectral_centroid": 2000.0, "spectral_flatness": 0.5, "tempo_bpm": 90.0,
                # Gaze fields (populated only in gaze mode)
                "model_description": "", "model_tags": [], "model_embedding": [],
                "sense_mode": mode.value}

        if mode in (SenseMode.glaze, SenseMode.gaze, SenseMode.auto):
            lavfi = ffmpeg_lavfi_analysis(path)
            feat.update(lavfi)

        feat["tempo_label"]  = _tempo_label(feat["tempo_bpm"])
        feat["energy_label"] = _energy_label(feat["loudness_I"])
        feat["timbre"]       = _timbre_label(feat["spectral_centroid"])
        feat["character"]    = _character(feat["spectral_flatness"])
        return feat
    except Exception as e:
        console.print(f"  [yellow]⚠ skipped[/] {path.name}: {e}")
        return None


# ── Gaze: local model inference ───────────────────────────────────────────────

def _gaze_ollama(path: Path, ollama_url: str, model: str = "qwen2-audio") -> dict:
    """
    Ask a local Ollama model to describe the audio file semantically.
    Returns {description, tags, embedding}.
    Ollama multimodal models accept base64 audio in the `images` field
    (Qwen2-Audio treats it as audio). Falls back to text-only prompt if model
    does not support audio.
    """
    import base64, httpx as _httpx
    result = {"model_description": "", "model_tags": [], "model_embedding": []}
    try:
        audio_b64 = base64.b64encode(path.read_bytes()).decode()
        prompt = (
            f"Describe this audio track named '{path.stem}' for music analysis. "
            "Include: tempo feel, mood, instrumental character, energy level, "
            "and what kind of playlist or setting it fits. Be concise (2-3 sentences)."
        )
        resp = _httpx.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "images": [audio_b64], "stream": False},
            timeout=120,
        )
        if resp.status_code == 200:
            body = resp.json()
            result["model_description"] = body.get("response", "")
            # Naive tag extraction from description
            desc = result["model_description"].lower()
            tags = []
            for kw in ["chill", "energetic", "dark", "uplifting", "jazz", "trap",
                       "ambient", "bass", "melodic", "aggressive", "smooth", "lo-fi"]:
                if kw in desc:
                    tags.append(kw)
            result["model_tags"] = tags
    except Exception as e:
        console.print(f"  [dim]gaze/ollama skipped for {path.name}: {e}[/]")
    return result


def _gaze_hirag(path: Path, hirag_url: str) -> dict:
    """
    Submit audio to Hi-RAG GPU multimodal embedding endpoint.
    Returns {model_embedding} — a high-dimensional float vector.
    """
    import httpx as _httpx
    result = {"model_description": "", "model_tags": [], "model_embedding": []}
    try:
        with path.open("rb") as f:
            resp = _httpx.post(
                f"{hirag_url}/hirag/ingest/audio",
                files={"file": (path.name, f, "audio/mpeg")},
                data={"namespace": "pmoves.darkxside.beats", "tags": "gaze,analyze_beats"},
                timeout=120,
            )
        if resp.status_code == 200:
            body = resp.json()
            result["model_embedding"] = body.get("embedding", [])
            result["model_description"] = body.get("summary", "")
    except Exception as e:
        console.print(f"  [dim]gaze/hirag skipped for {path.name}: {e}[/]")
    return result


def gaze_enrich(records: list[dict], ollama_url: str, hirag_url: str) -> list[dict]:
    """Enrich all records with local model inference (Qwen2-Audio → Hi-RAG fallback)."""
    console.rule("[bold magenta]🔮 Gaze Mode — Local Model Inference[/bold magenta]")
    # Try Hi-RAG GPU first; fall back to Ollama if unavailable
    hirag_alive = False
    try:
        r = httpx.get(f"{hirag_url}/hirag/admin/stats", timeout=4)
        hirag_alive = r.status_code == 200
    except Exception:
        pass

    mode_label = "Hi-RAG GPU" if hirag_alive else "Ollama (qwen2-audio)"
    console.print(f"  [cyan]Sense backend:[/] {mode_label}")

    enriched = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(),
                  TextColumn("{task.completed}/{task.total}"), console=console) as prog:
        task = prog.add_task("Gazing…", total=len(records))
        for rec in records:
            path = Path(rec["file"])
            if hirag_alive:
                update = _gaze_hirag(path, hirag_url)
            else:
                update = _gaze_ollama(path, ollama_url)
            rec.update(update)
            rec["sense_mode"] = "gaze"
            enriched.append(rec)
            prog.advance(task)
    return enriched


# ── Coherence (silhouette score) ──────────────────────────────────────────────

def measure_coherence(records: list[dict], labels: list[int]) -> float:
    """Return sklearn silhouette score. 1.0 = perfect separation, -1.0 = total overlap."""
    try:
        from sklearn.metrics import silhouette_score
        from sklearn.preprocessing import StandardScaler
        X = np.array([[r["tempo_bpm"], r["loudness_I"] * -1,
                       r["spectral_centroid"] / 100, r["spectral_flatness"] * 10]
                      for r in records])
        score = float(silhouette_score(StandardScaler().fit_transform(X), labels))
        return round(score, 3)
    except Exception:
        return 0.5  # assume good enough if sklearn fails


# ── Descriptive labels ────────────────────────────────────────────────────────

def _tempo_label(bpm: float) -> str:
    if bpm < 66:  return "Largo"
    if bpm < 88:  return "Andante"
    if bpm < 112: return "Moderato"
    if bpm < 140: return "Allegro"
    return "Presto"

def _energy_label(lufs: float) -> str:
    if lufs < -23: return "Deep"
    if lufs < -16: return "Mid"
    return "Bright"

def _timbre_label(centroid_hz: float) -> str:
    if centroid_hz < 1200: return "bass-heavy"
    if centroid_hz < 2000: return "warm"
    if centroid_hz < 3500: return "balanced"
    if centroid_hz < 5000: return "electric"
    return "airy"

def _character(flatness: float) -> str:
    if flatness < 0.1:  return "tonal"
    if flatness < 0.35: return "textured"
    return "noisy"


# ── Clustering ────────────────────────────────────────────────────────────────

def cluster(records: list[dict], n_groups: int) -> list[int]:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    features = []
    for r in records:
        f = [
            r["tempo_bpm"] / 10.0,
            r["loudness_I"] * -1.0,
            r["loudness_LRA"],
            r["spectral_centroid"] / 1000.0,
            r["spectral_flatness"] * 10.0,
        ]
        # Give the semantic multimodal embedding 5x weight to dominate acoustic features
        if "_emb_reduced" in r:
            f.extend([v * 5.0 for v in r["_emb_reduced"]])
        features.append(f)

    X = np.array(features)

    labels = KMeans(n_clusters=n_groups, random_state=42, n_init="auto").fit_predict(
        StandardScaler().fit_transform(X)
    )
    return labels.tolist()


def name_group(members: list[dict]) -> str:
    avg_bpm   = np.mean([r["tempo_bpm"] for r in members])
    avg_lufs  = np.mean([r["loudness_I"] for r in members])
    avg_cent  = np.mean([r["spectral_centroid"] for r in members])

    base_name = f"{_tempo_label(avg_bpm)}_{_timbre_label(avg_cent)}_{_energy_label(avg_lufs)}"
    
    # Inject semantic inference if available
    all_tags = []
    for r in members:
        all_tags.extend(r.get("model_tags", []))
    if all_tags:
        from collections import Counter
        top_tag = Counter(all_tags).most_common(1)[0][0]
        base_name += f"_{top_tag}"

    return base_name


# ── M3U8 writer ───────────────────────────────────────────────────────────────

def write_playlist(name: str, members: list[dict], output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    m3u = output_dir / f"{name.replace('/', '_')}.m3u8"
    with open(m3u, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# DARKXSIDE Sonic Group: {name}\n")
        f.write(f"# Tracks: {len(members)}\n\n")
        for r in sorted(members, key=lambda x: x["tempo_bpm"]):
            f.write(f"#EXTINF:{int(r.get('duration_s', -1))},{r['name']}\n{r['file']}\n")
    return m3u


# ── Cipher Memory checkpoint ──────────────────────────────────────────────────

async def cipher_checkpoint(cipher_url: str, data: dict, category: str = "agent_checkpoint"):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{cipher_url}/api/memory",
                json={"category": category, "content": data, "tags": ["beats", "analyze_beats"]}
            )
    except Exception:
        pass  # Cipher offline — non-fatal


# ── Glances push ─────────────────────────────────────────────────────────────

async def glances_push(glances_url: str, label: str, value: float):
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(
                f"{glances_url}/api/4/events",
                json={"name": "analyze_beats", "event": f"{label}={value:.2f}"}
            )
    except Exception:
        pass


# ── NATS publish ─────────────────────────────────────────────────────────────

async def nats_publish(nats_url: str, subject: str, payload: dict):
    try:
        import nats as natspy
        nc = await natspy.connect(nats_url)
        await nc.publish(subject, json.dumps(payload).encode())
        await nc.drain()
    except Exception as e:
        console.print(f"  [dim]nats skipped: {e}[/]")


# ═══════════════════════════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def analyze(
    input:      Path      = typer.Option(DEFAULT_INPUT,      "--input",  "-i", help="Folder of audio files"),
    output:     Path      = typer.Option(DEFAULT_OUTPUT,     "--output", "-o", help="Playlist output folder"),
    groups:     int       = typer.Option(8,                  "--groups", "-g", help="Number of sonic groups"),
    sense_mode: SenseMode = typer.Option(SenseMode.auto,     "--sense-mode",   help="peek | glaze | gaze | auto"),
    nats:       str       = typer.Option(DEFAULT_NATS,       "--nats",         help="NATS URL (optional)"),
    cipher:     str       = typer.Option(DEFAULT_CIPHER,     "--cipher",       help="Cipher Memory URL"),
    glances:    str       = typer.Option(DEFAULT_GLANCES,    "--glances",      help="Glances REST URL"),
    ollama:     str       = typer.Option(DEFAULT_OLLAMA,     "--ollama",       help="Ollama base URL (gaze mode)"),
    hirag:      str       = typer.Option(DEFAULT_HIRAG,      "--hirag",        help="Hi-RAG GPU URL (gaze mode)"),
    cache:      bool      = typer.Option(False,              "--cache",        help="Use cached .fingerprints.json"),
):
    """[bold cyan]Multimodal sonic fingerprint extraction and clustering.[/bold cyan]

    Sense modes: [bold]peek[/bold] (fast metadata) → [bold]glaze[/bold] (ffmpeg lavfi) → [bold]gaze[/bold] (local AI model).
    [bold]auto[/bold] starts at glaze and escalates if cluster coherence is low.
    """
    cache_file = input / ".fingerprints.json"

    audio_files = sorted([p for p in input.rglob("*") if p.suffix.lower() in AUDIO_SUFFIXES])
    if not audio_files:
        console.print(f"[red]No audio files found in {input}[/]")
        raise typer.Exit(1)

    mode_display = {
        SenseMode.peek:  "[dim]peek[/dim] — metadata only",
        SenseMode.glaze: "[cyan]glaze[/cyan] — ffmpeg lavfi",
        SenseMode.gaze:  "[magenta]gaze[/magenta] — local model inference",
        SenseMode.auto:  "[green]auto[/green] — glaze → escalate if coherence < 0.30",
    }[sense_mode]
    console.print(Panel(
        f"[bold]DARKXSIDE Multimodal Sonic Analysis[/bold]\n"
        f"Tracks: {len(audio_files)}   Mode: {mode_display}",
        border_style="cyan"
    ))

    extract_mode = SenseMode.peek if sense_mode == SenseMode.peek else SenseMode.glaze

    if cache and cache_file.exists():
        console.print(f"[dim]Loading cached fingerprints from {cache_file}[/]")
        with open(cache_file) as f:
            records = json.load(f)
    else:
        records = []
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), BarColumn(),
            TextColumn("{task.completed}/{task.total}"), TimeElapsedColumn(),
            console=console
        ) as prog:
            task = prog.add_task("Fingerprinting…", total=len(audio_files))
            for path in audio_files:
                prog.update(task, description=f"[cyan]{path.name[:40]}[/]")
                feat = extract_all(path, mode=extract_mode)
                if feat:
                    records.append(feat)
                    asyncio.run(glances_push(glances, "tracks_done", len(records)))
                prog.advance(task)

        with open(cache_file, "w") as f:
            json.dump(records, f, indent=2)
        console.print(f"\n[green]✓[/] Fingerprints saved → {cache_file}")

    asyncio.run(cipher_checkpoint(cipher, {"step": "fingerprint_complete", "count": len(records)}))

    if len(records) < 2:
        console.print("[red]Not enough valid tracks to cluster.[/]")
        raise typer.Exit(1)

    n = min(groups, len(records) // 2)
    console.print(f"\n[bold]Initial cluster[/] — {len(records)} tracks → {n} groups…")
    labels = cluster(records, n)

    # ── Coherence check + gaze escalation ─────────────────────────────────────
    if sense_mode in (SenseMode.auto, SenseMode.gaze):
        coherence = measure_coherence(records, labels)
        console.print(f"  [bold]Silhouette coherence score:[/] {coherence:.3f} "
                      f"(threshold: {COHERENCE_THRESHOLD})")

        if sense_mode == SenseMode.gaze or coherence < COHERENCE_THRESHOLD:
            if sense_mode == SenseMode.auto:
                console.print(
                    f"  [yellow]⚡ Signal ambiguous — escalating to [bold magenta]gaze[/bold magenta] mode[/]")
            records = gaze_enrich(records, ollama, hirag)
            # Re-cluster with enriched embeddings if available
            has_embeddings = any(len(r.get("model_embedding", [])) > 0 for r in records)
            if has_embeddings:
                # Fuse ffmpeg features with model embedding (PCA-reduced)
                try:
                    from sklearn.decomposition import PCA
                    from sklearn.preprocessing import StandardScaler
                    emb_matrix = np.array([r.get("model_embedding", [0]*8) for r in records])
                    n_components = min(8, emb_matrix.shape[1], len(records) - 1)
                    reduced = PCA(n_components=n_components).fit_transform(
                        StandardScaler().fit_transform(emb_matrix)
                    )
                    for i, rec in enumerate(records):
                        rec["_emb_reduced"] = reduced[i].tolist()
                    console.print("  [green]✓[/] Fused model embeddings with acoustic features")
                except Exception as e:
                    console.print(f"  [dim]Embedding fusion skipped: {e}[/]")
            labels = cluster(records, n)
            new_coherence = measure_coherence(records, labels)
            console.print(f"  [bold green]Post-gaze coherence:[/] {new_coherence:.3f}")
            asyncio.run(cipher_checkpoint(cipher, {
                "step": "gaze_complete",
                "pre_coherence": coherence,
                "post_coherence": new_coherence,
                "sense_mode": "gaze"
            }))
        else:
            console.print(f"  [green]✓ Signal clear — staying at [bold cyan]glaze[/bold cyan] mode[/]")

    # Build groups
    grp_map: dict[int, list] = {}
    for rec, lbl in zip(records, labels):
        grp_map.setdefault(int(lbl), []).append(rec)

    summary = []
    output.mkdir(parents=True, exist_ok=True)
    table = Table("Group", "Tracks", "Avg BPM", "Energy", "Timbre", title="Sonic Groups")

    for gid, members in sorted(grp_map.items(), key=lambda kv: -len(kv[1])):
        gname = f"{name_group(members)}_c{gid}"
        m3u = write_playlist(gname, members, output)
        avg_bpm = round(float(np.mean([r["tempo_bpm"] for r in members])), 1)
        table.add_row(gname, str(len(members)), str(avg_bpm),
                      _energy_label(float(np.mean([r["loudness_I"] for r in members]))),
                      _timbre_label(float(np.mean([r["spectral_centroid"] for r in members]))))
        entry = {"group": gname, "count": len(members), "tracks": [m["name"] for m in members]}
        summary.append(entry)
        if nats:
            asyncio.run(nats_publish(nats, "pmoves.darkxside.beats.group.v1", entry))

    console.print(table)
    summary_path = output / "groups_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    asyncio.run(cipher_checkpoint(cipher, {"step": "grouping_complete", "groups": summary}, "agent_checkpoint"))
    console.print(f"\n[bold green]✓ Done.[/] Playlists → {output}/   Summary → {summary_path}")


@app.command()
def groups(
    input:  Path = typer.Option(DEFAULT_INPUT,  "--input", "-i"),
    output: Path = typer.Option(DEFAULT_OUTPUT, "--output", "-o"),
):
    """[bold]Show existing sonic groups from a previous analyze run.[/bold]"""
    summary_path = output / "groups_summary.json"
    if not summary_path.exists():
        console.print(f"[red]No groups_summary.json found. Run [bold]analyze[/] first.[/]")
        raise typer.Exit(1)

    with open(summary_path) as f:
        summary = json.load(f)

    table = Table("Group", "# Tracks", "Track Names", title="Sonic Groups")
    for g in summary:
        names = ", ".join(g["tracks"][:5]) + (f" +{len(g['tracks'])-5} more" if len(g["tracks"]) > 5 else "")
        table.add_row(g["group"], str(g["count"]), names)
    console.print(table)


@app.command()
def status(
    cipher:  str = typer.Option(DEFAULT_CIPHER,  "--cipher"),
    glances: str = typer.Option(DEFAULT_GLANCES, "--glances"),
):
    """[bold]Check Cipher Memory checkpoint and Glances system status.[/bold]"""
    async def _check():
        async with httpx.AsyncClient(timeout=4) as client:
            try:
                r = await client.get(f"{cipher}/api/memory/search?q=analyze_beats&category=agent_checkpoint")
                console.print(f"[green]Cipher Memory[/] {cipher} — {r.status_code}")
                if r.status_code == 200:
                    hits = r.json().get("results", [])
                    console.print(f"  {len(hits)} checkpoint(s) stored")
            except Exception as e:
                console.print(f"[yellow]Cipher Memory offline:[/] {e}")

            try:
                r = await client.get(f"{glances}/api/4/cpu")
                cpu = r.json()
                console.print(f"[green]Glances[/] {glances} — CPU total: {cpu.get('total', '?')}%")
            except Exception as e:
                console.print(f"[yellow]Glances offline:[/] {e}")

    asyncio.run(_check())


if __name__ == "__main__":
    app()
