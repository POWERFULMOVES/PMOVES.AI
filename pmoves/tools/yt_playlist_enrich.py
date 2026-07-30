#!/usr/bin/env python3
"""
DARKXSIDE Playlist Enrichment — Resonance Taxonomy + School of PowerfulMoves

Classifies YouTube playlist videos by:
  1. PMOVES resonance domain (maps to agent_signatures.yaml)
  2. School of PowerfulMoves curriculum track
  3. Extracted resource links (github, docs, tools, courses)
  4. Persona signal (which PMOVES agent this resonates with)
  5. Health/wealth topic tagging for cross-integration

Usage:
  python3 yt_playlist_enrich.py                          # enrich all unclassified
  python3 yt_playlist_enrich.py --video-id VIDEO_ID      # single video
  python3 yt_playlist_enrich.py --stats                  # show classification stats
"""

import argparse
import json
import logging
import os
import re
import sys
from urllib.parse import urlparse

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("yt-enrich")

# ---------------------------------------------------------------------------
# Resonance Taxonomy — maps keywords to PMOVES resonance domains
# ---------------------------------------------------------------------------

RESONANCE_MAP = {
    "ai-ml": {
        "keywords": ["ai", "machine learning", "neural", "llm", "gpt", "transformer", "deep learning",
                      "model", "training", "fine-tune", "rag", "embedding", "vector", "quantum computing",
                      "agi", "chatbot", "openai", "anthropic", "ollama", "huggingface", "pytorch",
                      "tensorflow", "diffusion", "stable diffusion", "generative"],
        "persona": "darkxside",
        "curriculum": {"track": "ai-engineering", "subject": "machine-learning"},
    },
    "dev-tools": {
        "keywords": ["github", "git", "docker", "kubernetes", "ci/cd", "devops", "programming",
                      "python", "javascript", "rust", "go ", "typescript", "react", "vue", "svelte",
                      "database", "postgres", "redis", "api", "rest", "graphql", "linux", "terminal",
                      "vim", "vscode", "ide", "compiler", "debugger", "ssh", "nginx"],
        "persona": "crush",
        "curriculum": {"track": "software-craft", "subject": "development-tools"},
    },
    "energy": {
        "keywords": ["battery", "solar", "nuclear", "fusion", "energy", "grid", "power", "electric",
                      "lithium", "hydrogen", "fuel cell", "ev", "electric vehicle", "charging",
                      "renewable", "wind", "geothermal", "fission", "reactor", "uranium", "thorium"],
        "persona": "powerfulmoves",
        "curriculum": {"track": "physical-systems", "subject": "energy"},
    },
    "media-creative": {
        "keywords": ["music", "video", "film", "animation", "blender", "after effects", "premiere",
                      "photoshop", "3d", "rendering", "vfx", "creative", "art", "design", "photography",
                      "audio", "mixing", "mastering", "fl studio", "ableton", "davinci", "obsidian",
                      "writing", "storytelling", "narrative"],
        "persona": "darkxside",
        "curriculum": {"track": "creative-arts", "subject": "media-production"},
    },
    "business": {
        "keywords": ["startup", "entrepreneur", "business", "marketing", "saas", "funding", "vc",
                      "revenue", "growth", "strategy", "market", "sales", "crypto", "bitcoin",
                      "ethereum", "defi", "web3", "blockchain", "trading", "investing", "stocks",
                      "portfolio", "passive income", "side hustle", "dropship", "ecommerce"],
        "persona": "powerfulmoves",
        "curriculum": {"track": "wealth-building", "subject": "entrepreneurship"},
    },
    "community": {
        "keywords": ["community", "open source", "collaboration", "social", "network", "governance",
                      "cooperative", "mutual aid", "decentralized", "dao", "voting", "democracy",
                      "activism", "organizing", "union", "collective"],
        "persona": "fordham-steward",
        "curriculum": {"track": "civic-engagement", "subject": "community-organizing"},
    },
    "health-fitness": {
        "keywords": ["nutrition", "diet", "workout", "fitness", "exercise", "gym", "muscle", "protein",
                      "calories", "weight loss", "fasting", "keto", "vegan", "meal prep", "cooking",
                      "recipe", "vitamin", "supplement", "sleep", "meditation", "mental health",
                      "longevity", "anti-aging", "biotech", "medicine", "health", "wellness",
                      "wger", "firefly", "body weight", "cardio", "strength"],
        "persona": "powerfulmoves",
        "curriculum": {"track": "health-wellness", "subject": "fitness-nutrition"},
    },
    "science-philosophy": {
        "keywords": ["physics", "quantum", "relativity", "mathematics", "philosophy", "consciousness",
                      "metaphysics", "atlantis", "ancient", "archeology", "history", "mythology",
                      "esoteric", "hermetic", "emerald tablet", "thoth", "secret", "mystery",
                      "simulation", "multiverse", "dimension", "sacred geometry"],
        "persona": "darkxside",
        "curriculum": {"track": "liberal-arts", "subject": "philosophy-esoterica"},
    },
    "hardware-makers": {
        "keywords": ["arduino", "raspberry pi", "esp32", "pcb", "soldering", "electronics", "iot",
                      "robotics", "drone", "3d printing", "maker", "diy", "hardware", "fpga",
                      "microcontroller", "sensor", "actuator", "cnc", "laser cutter"],
        "persona": "crush",
        "curriculum": {"track": "hardware-lab", "subject": "electronics"},
    },
    "security-privacy": {
        "keywords": ["security", "privacy", "encryption", "vpn", "tor", "surveillance", "rfid",
                      "hacking", "cybersecurity", "malware", "firewall", "network security",
                      "opsec", "signal", "encrypted", "zero knowledge", "audit"],
        "persona": "claude-opus",
        "curriculum": {"track": "digital-defense", "subject": "infosec"},
    },
    "infrastructure": {
        "keywords": ["network", "server", "datacenter", "cloud", "self-hosted", "homelab",
                      "tailscale", "wireguard", "router", "switch", "vlan", "dns", "reverse proxy",
                      "docker compose", "k8s", "proxmox", "virtualization", "backup", "storage",
                      "nas", "zfs"],
        "persona": "crush",
        "curriculum": {"track": "infrastructure", "subject": "systems-ops"},
    },
}

# YouTube category ID → human readable
YT_CATEGORIES = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music",
    "15": "Pets & Animals", "17": "Sports", "19": "Travel & Events",
    "20": "Gaming", "22": "People & Blogs", "23": "Comedy",
    "24": "Entertainment", "25": "News & Politics", "26": "Howto & Style",
    "27": "Education", "28": "Science & Technology", "29": "Nonprofits & Activism",
    "30": "Movies",
}

# Difficulty tiers based on duration signals
def assign_difficulty(duration_seconds: int, tags: list | None) -> str:
    if not duration_seconds or duration_seconds < 300:
        return "foundation"
    if duration_seconds > 3600:
        return "deep-dive"
    if tags and any("advanced" in str(t).lower() or "expert" in str(t).lower() for t in tags):
        return "advanced"
    return "intermediate"


# ---------------------------------------------------------------------------
# Link extraction from descriptions
# ---------------------------------------------------------------------------

LINK_RE = re.compile(r'https?://[^\s<>"\')\]]+', re.IGNORECASE)


def extract_links(description: str | None) -> list[dict]:
    if not description:
        return []
    links = []
    seen = set()
    for match in LINK_RE.finditer(description):
        url = match.group().rstrip(".,;!?")
        if url in seen:
            continue
        seen.add(url)
        parsed = urlparse(url)
        host = parsed.hostname or ""
        link_type = "web"
        if "github.com" in host:
            link_type = "github"
        elif any(d in host for d in ["youtube.com", "youtu.be"]):
            link_type = "youtube"
        elif any(d in host for d in ["udemy.com", "coursera.org", "edx.org", "freecodecamp.org"]):
            link_type = "course"
        elif any(d in host for d in ["amazon.com", "amzn.to"]):
            link_type = "product"
        elif any(d in host for d in ["patreon.com", "ko-fi.com", "buymeacoffee.com"]):
            link_type = "support"
        elif "discord.gg" in host or "discord.com" in host:
            link_type = "community"
        elif any(d in host for d in ["twitter.com", "x.com", "instagram.com", "tiktok.com",
                                      "facebook.com", "linkedin.com"]):
            link_type = "social"
        elif any(d in host for d in ["wikipedia.org", "scholar.google", "arxiv.org", "doi.org",
                                      "nature.com", "science.org"]):
            link_type = "reference"
        links.append({"url": url, "type": link_type, "host": host})
    return links


# ---------------------------------------------------------------------------
# Classification engine
# ---------------------------------------------------------------------------

def classify_video(video: dict) -> dict:
    title = (video.get("title") or "").lower()
    desc = (video.get("description") or "").lower()
    tags = [str(t).lower() for t in (video.get("tags") or [])]
    cat_id = video.get("category_id")
    channel = (video.get("channel_title") or "").lower()
    combined = f"{title} {desc} {' '.join(tags)} {channel}"

    scores: dict[str, int] = {}
    for domain, config in RESONANCE_MAP.items():
        score = 0
        for kw in config["keywords"]:
            if kw in combined:
                score += combined.count(kw)
                if kw in title:
                    score += 5
                if kw in tags:
                    score += 3
        if score > 0:
            scores[domain] = score

    if not scores:
        primary = "media-creative" if cat_id in ("24", "23", "10") else "science-philosophy"
        scores[primary] = 1

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    primary_domain = ranked[0][0]
    secondary = [d for d, _ in ranked[1:4]] if len(ranked) > 1 else []

    config = RESONANCE_MAP[primary_domain]
    result = {
        "resonance_domain": primary_domain,
        "resonance_secondary": secondary,
        "curriculum_track": config["curriculum"]["track"],
        "curriculum_subject": config["curriculum"]["subject"],
        "persona_signal": config["persona"],
        "difficulty_tier": assign_difficulty(video.get("duration_seconds"), video.get("tags")),
        "resource_links": json.dumps(extract_links(video.get("description"))),
        "health_topic": None,
        "wealth_topic": None,
    }

    # Health cross-tag
    health_kw = [k for k in RESONANCE_MAP.get("health-fitness", {}).get("keywords", [])
                 if k in combined]
    if health_kw:
        if any(k in combined for k in ["nutrition", "diet", "protein", "calories", "recipe",
                                        "meal", "vitamin", "supplement", "keto", "vegan"]):
            result["health_topic"] = "nutrition"
        elif any(k in combined for k in ["workout", "fitness", "exercise", "gym", "muscle",
                                          "cardio", "strength", "body weight"]):
            result["health_topic"] = "fitness"
        elif any(k in combined for k in ["sleep", "meditation", "mental health", "longevity",
                                          "anti-aging", "wellness"]):
            result["health_topic"] = "wellness"

    # Wealth cross-tag
    wealth_kw = [k for k in RESONANCE_MAP.get("business", {}).get("keywords", [])
                 if k in combined]
    if wealth_kw:
        if any(k in combined for k in ["investing", "stocks", "portfolio", "crypto", "bitcoin",
                                        "trading", "ethereum", "defi"]):
            result["wealth_topic"] = "investing"
        elif any(k in combined for k in ["startup", "entrepreneur", "business", "saas",
                                          "side hustle", "revenue"]):
            result["wealth_topic"] = "entrepreneurship"
        elif any(k in combined for k in ["budget", "saving", "frugal", "deal", "discount",
                                          "passive income"]):
            result["wealth_topic"] = "budget-optimization"

    return result


# ---------------------------------------------------------------------------
# Supabase read/write
# ---------------------------------------------------------------------------

def fetch_videos(rest_url: str, key: str, video_id: str | None = None) -> list[dict]:
    base = rest_url.rstrip("/")
    if not base.endswith("/rest/v1"):
        base = f"{base}/rest/v1"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "pmoves_core",
    }
    select = ("video_id,title,description,tags,category_id,channel_title,"
              "duration_seconds,resonance_domain")
    if video_id:
        url = f"{base}/youtube_videos?select={select}&video_id=eq.{video_id}"
    else:
        url = f"{base}/youtube_videos?select={select}&resonance_domain=is.null&limit=500"
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        log.error(f"Fetch failed: {resp.status_code} {resp.text[:200]}")
        return []
    return resp.json()


def update_video(rest_url: str, key: str, video_id: str, enrichment: dict):
    base = rest_url.rstrip("/")
    if not base.endswith("/rest/v1"):
        base = f"{base}/rest/v1"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Content-Profile": "pmoves_core",
        "Prefer": "return=minimal",
    }
    payload = {k: v for k, v in enrichment.items()}
    resp = requests.patch(
        f"{base}/youtube_videos?video_id=eq.{video_id}",
        json=payload,
        headers=headers,
        timeout=15,
    )
    if resp.status_code not in (200, 204):
        log.warning(f"Update {video_id} failed: {resp.status_code} {resp.text[:150]}")


def fetch_stats(rest_url: str, key: str) -> dict:
    base = rest_url.rstrip("/")
    if not base.endswith("/rest/v1"):
        base = f"{base}/rest/v1"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "pmoves_core",
    }
    stats = {}
    # Resonance breakdown
    resp = requests.get(
        f"{base}/youtube_videos?select=resonance_domain,curriculum_track,persona_signal,health_topic,wealth_topic",
        headers=headers, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        from collections import Counter
        stats["total"] = len(data)
        stats["by_resonance"] = dict(Counter(d["resonance_domain"] for d in data if d.get("resonance_domain")))
        stats["by_curriculum"] = dict(Counter(d["curriculum_track"] for d in data if d.get("curriculum_track")))
        stats["by_persona"] = dict(Counter(d["persona_signal"] for d in data if d.get("persona_signal")))
        stats["health_tagged"] = sum(1 for d in data if d.get("health_topic"))
        stats["wealth_tagged"] = sum(1 for d in data if d.get("wealth_topic"))
    return stats


def main():
    parser = argparse.ArgumentParser(description="DARKXSIDE Playlist Enrichment")
    parser.add_argument("--video-id", help="Enrich single video")
    parser.add_argument("--stats", action="store_true", help="Show classification stats")
    parser.add_argument("--dry-run", action="store_true", help="Classify without writing")
    parser.add_argument("--limit", type=int, default=500, help="Max videos to process")
    args = parser.parse_args()

    rest_url = os.environ.get("SUPA_REST_URL") or os.environ.get("SUPABASE_URL", "")
    rest_url = rest_url.rstrip("/")
    if not rest_url.endswith("/rest/v1"):
        rest_url = f"{rest_url}/rest/v1"
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not key or not rest_url:
        log.error("Missing SUPA_REST_URL and SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    if args.stats:
        stats = fetch_stats(rest_url, key)
        print(json.dumps(stats, indent=2, sort_keys=True))
        return

    videos = fetch_videos(rest_url, key, args.video_id)
    if not videos:
        log.info("No videos to enrich")
        return

    log.info(f"Enriching {len(videos)} videos...")
    classified = 0
    for v in videos:
        enrichment = classify_video(v)
        if not args.dry_run:
            update_video(rest_url, key, v["video_id"], enrichment)
        classified += 1
        if classified % 100 == 0:
            log.info(f"  Processed {classified}/{len(videos)}...")

    log.info(f"Done: {classified} videos enriched")
    if args.dry_run:
        for v in videos[:10]:
            e = classify_video(v)
            print(f"  {v['video_id']}  [{e['resonance_domain']:20s}]  {e['curriculum_track']:25s}  {(v.get('title') or '')[:50]}")


if __name__ == "__main__":
    main()
