"""Hardware profile utilities for pmoves mini CLI."""

from __future__ import annotations

import json
import os
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import yaml


PROFILE_DIR = Path(__file__).resolve().parents[1] / "config" / "profiles"
STATE_PATH = Path.home() / ".pmoves" / "profile.json"


@dataclass
class Profile:
    id: str
    name: str
    description: str
    hardware: dict
    compose_overrides: List[str] = field(default_factory=list)
    model_bundles: List[str] = field(default_factory=list)
    mcp: List[str] = field(default_factory=list)
    messaging: dict = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def load_profiles(directory: Path | None = None) -> Dict[str, Profile]:
    directory = directory or PROFILE_DIR
    profiles: Dict[str, Profile] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict) or "id" not in data:
            continue
        profile = Profile(
            id=data["id"],
            name=data.get("name", data["id"]),
            description=data.get("description", ""),
            hardware=data.get("hardware", {}),
            compose_overrides=data.get("compose_overrides", []) or [],
            model_bundles=data.get("model_bundles", []) or [],
            mcp=data.get("mcp", []) or [],
            messaging=data.get("messaging", {}) or {},
            notes=data.get("notes", []) or [],
            raw=data,
        )
        profiles[profile.id] = profile
    return profiles


def _get_cpu_string() -> str:
    cpu = platform.processor() or ""
    if cpu:
        return cpu.lower()
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if "model name" in line.lower():
                    return line.split(":", 1)[1].strip().lower()
    except FileNotFoundError:
        pass
    return cpu.lower()


def _get_gpu_names() -> List[str]:
    names: List[str] = []
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                cleaned = line.strip()
                if cleaned:
                    names.append(cleaned.lower())
    except FileNotFoundError:
        pass
    return names


def _is_jetson() -> bool:
    try:
        with open("/proc/device-tree/model", "r", encoding="utf-8") as handle:
            return "jetson" in handle.read().lower()
    except FileNotFoundError:
        return False


def detect_profiles(profiles: Iterable[Profile]) -> List[Tuple[int, Profile]]:
    cpu = _get_cpu_string()
    gpus = _get_gpu_names()
    is_jetson = _is_jetson()
    results: List[Tuple[int, Profile]] = []

    for profile in profiles:
        score = 0
        hardware = profile.hardware or {}
        cpu_info = hardware.get("cpu", {})
        gpu_info = hardware.get("gpu", {})
        tags = set((hardware.get("tags") or []))

        cpu_model = (cpu_info.get("model") or "").lower()
        cpu_vendor = (cpu_info.get("vendor") or "").lower()
        if cpu_model and cpu_model in cpu:
            score += 5
        if cpu_vendor and cpu_vendor in cpu:
            score += 2

        gpu_models = [m.lower() for m in gpu_info.get("models", [])]
        if gpus and gpu_models:
            for gpu in gpus:
                if any(model in gpu for model in gpu_models):
                    score += 5

        if is_jetson and "jetson" in tags:
            score += 10
        if "edge" in tags and not gpus:
            score += 1

        if score > 0:
            results.append((score, profile))

    results.sort(key=lambda item: item[0], reverse=True)
    return results


def save_active_profile(profile_id: str) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"profile": profile_id}, indent=2), encoding="utf-8")


def load_active_profile_id() -> str | None:
    if not STATE_PATH.exists():
        return None
    try:
        data = json.loads(STATE_PATH.read_text())
    except json.JSONDecodeError:
        return None
    return data.get("profile")
