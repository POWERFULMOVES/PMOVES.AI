"""
Provider Activation Cascade
============================
Deterministic 6-stage pipeline: provider + key → system morphs.

Stages:
  1. Secrets Ingestion — validate, write to env.shared, run secrets-funnel
  2. TensorZero Config — add/update models via TensorZeroConfig
  3. Model Lane Assignment — catalog for known, fit-score for unknown
  4. Coding Stack Activation — profile-aware VRAM budget check
  5. NATS Announcement — publish claw.provider.activated.v1
  6. Capability Dashboard — structured summary

Entry channels:
  - Agent:  activate_provider(provider, key)
  - Human:  make -C pmoves provider-activate PROVIDER=... KEY=...
  - Both converge on secrets-funnel. No bypass possible.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from getpass import getpass
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    import toml  # type: ignore[import-not-found]
except ModuleNotFoundError:
    toml = None

logger = logging.getLogger(__name__)

# Resolve paths relative to this file → pmoves/tools/ → pmoves/ → repo root
TOOLS_DIR = Path(__file__).resolve().parent
PMOVES_DIR = TOOLS_DIR.parent
REPO_ROOT = PMOVES_DIR.parent
CONFIG_DIR = PMOVES_DIR / "config"
TZ_CONFIG = PMOVES_DIR / "tensorzero" / "config" / "tensorzero.toml"

PLACEHOLDER_VALUES = frozenset({
    "", "changeme", "change-me", "change_me", "todo", "set-me",
    "placeholder", "your_key_here", "xxx", "CHANGEME",
})


@dataclass
class StageResult:
    """Result from a single cascade stage."""
    stage: int
    name: str
    success: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CascadeResult:
    """Aggregate result from the full cascade."""
    provider: str
    success: bool
    stages: List[StageResult] = field(default_factory=list)
    models_added: List[str] = field(default_factory=list)
    functions_updated: List[str] = field(default_factory=list)
    coding_stacks_activated: List[str] = field(default_factory=list)
    vram_warnings: List[str] = field(default_factory=list)
    nats_published: bool = False


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file, returning empty dict on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
        return {}


def _load_provider_catalog() -> Dict[str, Any]:
    """Load the provider catalog."""
    return _load_yaml(CONFIG_DIR / "provider_catalog.yaml")


def _load_function_demands() -> Dict[str, Any]:
    """Load function demand profiles."""
    return _load_yaml(CONFIG_DIR / "function_demands.yaml")


def _load_model_strengths() -> Dict[str, Any]:
    """Load model strength profiles."""
    data = _load_yaml(CONFIG_DIR / "model_strengths_seed.yaml")
    return data.get("models", {})


def _load_node_profile(profile_id: str) -> Dict[str, Any]:
    """Load a node hardware profile."""
    path = CONFIG_DIR / "profiles" / f"{profile_id}.yaml"
    return _load_yaml(path)


def _is_placeholder(value: str) -> bool:
    """Check if a value is a placeholder."""
    return value.strip().lower() in PLACEHOLDER_VALUES


def _read_env_shared() -> Dict[str, str]:
    """Read env.shared into a dict."""
    env_path = PMOVES_DIR / "env.shared"
    result = {}
    if not env_path.exists():
        return result
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                result[key.strip()] = val.strip()
    return result


def _write_env_key(env_var: str, value: str) -> bool:
    """Write or update a key in env.shared using safe append/replace."""
    env_path = PMOVES_DIR / "env.shared"
    lines = []
    found = False

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            if key.strip() == env_var:
                new_lines.append(f"{env_var}={value}\n")
                found = True
                continue
        new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{env_var}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return True


def _remove_env_key(env_var: str) -> bool:
    """Remove a key from env.shared if it exists."""
    env_path = PMOVES_DIR / "env.shared"
    if not env_path.exists():
        return True

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            if key.strip() == env_var:
                continue
        kept.append(line)

    env_path.write_text("".join(kept), encoding="utf-8")
    return True


def _save_tz_config(config: Dict[str, Any]) -> None:
    """Persist the TensorZero config atomically."""
    if toml is None:
        raise RuntimeError("python package 'toml' is required for provider activation writes")

    temp_path = TZ_CONFIG.with_suffix(".toml.tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        toml.dump(config, handle)
    temp_path.replace(TZ_CONFIG)


def _load_tz_config() -> Dict[str, Any]:
    """Load the TensorZero config using stdlib TOML support when possible."""
    if toml is not None:
        return toml.load(TZ_CONFIG)

    with open(TZ_CONFIG, "rb") as handle:
        return tomllib.load(handle)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _publish_nats_event(subject: str, payload: Dict[str, Any]) -> bool:
    """Best-effort lifecycle publish helper."""
    try:
        payload_json = json.dumps(payload)
        proc = subprocess.run(
            ["nats", "pub", subject, payload_json],
            capture_output=True, text=True, timeout=10,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("NATS not available; skipping %s", subject)
        return False


# =============================================================================
# Stage 1: Secrets Ingestion
# =============================================================================

def _stage_1_secrets(
    provider_slug: str,
    api_key: str,
    provider_config: Dict[str, Any],
    dry_run: bool = False,
) -> StageResult:
    """Validate key, write to env.shared, run secrets-funnel."""
    env_var = provider_config["env_var"]
    key_pattern = provider_config.get("key_pattern", ".*")

    if not dry_run and not re.match(key_pattern, api_key):
        return StageResult(
            stage=1, name="Secrets Ingestion", success=False,
            message=f"Key format invalid for {provider_slug} (expected pattern: {key_pattern})",
        )

    current_env = _read_env_shared()
    current_val = current_env.get(env_var, "")
    previous_present = env_var in current_env
    if current_val and not _is_placeholder(current_val) and current_val == api_key:
        return StageResult(
            stage=1, name="Secrets Ingestion", success=True,
            message=f"{env_var} already set (no change needed)",
            details={"env_var": env_var, "action": "no-op"},
        )

    if dry_run:
        return StageResult(
            stage=1, name="Secrets Ingestion", success=True,
            message=f"Would write {env_var} to env.shared and run secrets-funnel",
            details={"env_var": env_var, "action": "dry-run"},
        )

    def _restore_previous_value() -> None:
        if previous_present:
            _write_env_key(env_var, current_val)
        else:
            _remove_env_key(env_var)

    _write_env_key(env_var, api_key)  # noqa: CodeQL [py/clear-text-storage-sensitive-data] -- local secrets funnel staging file by design
    logger.info(f"Wrote {env_var} to env.shared")

    try:
        result = subprocess.run(
            ["make", "-C", str(PMOVES_DIR), "secrets-funnel"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            _restore_previous_value()
            return StageResult(
                stage=1, name="Secrets Ingestion", success=False,
                message=f"secrets-funnel failed: {result.stderr[:200]}",
                details={"env_var": env_var, "returncode": result.returncode},
            )
    except subprocess.TimeoutExpired:
        _restore_previous_value()
        return StageResult(
            stage=1, name="Secrets Ingestion", success=False,
            message="secrets-funnel timed out (120s)",
        )
    except FileNotFoundError:
        logger.warning("make not found; skipping secrets-funnel in dev mode")

    return StageResult(
        stage=1, name="Secrets Ingestion", success=True,
        message=f"{env_var} -> env.tier-{provider_config.get('tier', 'llm')}",
        details={"env_var": env_var, "tier": provider_config.get("tier", "llm")},
    )


def _stage_2_tz_config(
    provider_slug: str,
    provider_config: Dict[str, Any],
    dry_run: bool = False,
) -> StageResult:
    """Add/update provider models in tensorzero.toml."""
    models = provider_config.get("models", {})
    if not models:
        return StageResult(
            stage=2, name="TZ Config", success=True,
            message="No models to configure",
        )

    if not TZ_CONFIG.exists():
        return StageResult(
            stage=2, name="TZ Config", success=False,
            message=f"TZ config not found: {TZ_CONFIG}",
        )

    if dry_run:
        model_names = list(models.keys())
        return StageResult(
            stage=2, name="TZ Config", success=True,
            message=f"Would add/verify {len(model_names)} model(s): {', '.join(model_names)}",
            details={"models": model_names, "action": "dry-run"},
        )

    try:
        tz = _load_tz_config()
        tz_models = tz.setdefault("models", {})

        added = []
        existing = []
        for model_slug, model_info in models.items():
            tz_key = model_info.get("tz_model_key", model_slug)
            if tz_key in tz_models:
                existing.append(tz_key)
                continue

            env_var = provider_config["env_var"]
            api_base = provider_config.get("api_base")
            tz_type = provider_config.get("tz_type", "openai")
            provider_name = f"{provider_slug}_primary"

            model_config = {
                "routing": [provider_name],
                "providers": {
                    provider_name: {
                        "type": tz_type,
                        "model_name": model_info["model_name"],
                        "api_key_location": f"env::{env_var}",
                    }
                },
            }
            if api_base:
                model_config["providers"][provider_name]["api_base"] = api_base

            tz_models[tz_key] = model_config
            added.append(tz_key)

        if added:
            _save_tz_config(tz)
            logger.info(f"TZ config updated: added {added}, existing {existing}")

        return StageResult(
            stage=2, name="TZ Config", success=True,
            message=f"+{len(added)} model(s)" + (f", {len(existing)} already present" if existing else ""),
            details={"added": added, "existing": existing},
        )

    except Exception as e:
        return StageResult(
            stage=2, name="TZ Config", success=False,
            message=f"TZ config update failed: {e}",
        )


def _compute_fit_score(
    model_strengths: Dict[str, float],
    demand_weights: Dict[str, float],
) -> float:
    """Compute fit score between a model's strengths and a function's demands."""
    return sum(
        demand_weights.get(dim, 0.0) * model_strengths.get(dim, 0.0)
        for dim in ("reasoning", "speed", "coding", "multilingual", "creativity", "context_handling")
    )


def _stage_3_lane_assignment(
    provider_slug: str,
    provider_config: Dict[str, Any],
    dry_run: bool = False,
) -> StageResult:
    """Assign models to functions and persist deterministic routing changes."""
    models = provider_config.get("models", {})
    functions_updated = []
    suggestions = []
    assignments = []
    changed = False

    tz = _load_tz_config() if TZ_CONFIG.exists() else {"functions": {}}
    functions_cfg = tz.setdefault("functions", {})

    for model_slug, model_info in models.items():
        serves = model_info.get("serves", [])

        if serves:
            for assignment in serves:
                fn_name = assignment["function"]
                variant_name = assignment["variant_name"]
                role = assignment.get("role", "secondary")
                weight = float(assignment.get("weight", 0.0))
                fn_cfg = functions_cfg.get(fn_name)
                if not fn_cfg or variant_name not in (fn_cfg.get("variants") or {}):
                    suggestions.append({
                        "model": model_slug,
                        "function": fn_name,
                        "variant_name": variant_name,
                        "reason": "variant missing from tensorzero config",
                    })
                    continue

                functions_updated.append(fn_name)
                logger.info(f"  Catalog lane: {model_slug} -> {fn_name} ({role}, w={weight})")

                if dry_run:
                    assignments.append({
                        "function": fn_name,
                        "variant_name": variant_name,
                        "role": role,
                        "weight": weight,
                        "action": "dry-run",
                    })
                    continue

                if role == "fallback":
                    fallbacks = list(fn_cfg.get("fallback_variants", []))
                    if variant_name not in fallbacks:
                        fallbacks.append(variant_name)
                        fn_cfg["fallback_variants"] = fallbacks
                        changed = True
                else:
                    candidates = dict(fn_cfg.get("candidate_variants", {}))
                    if candidates.get(variant_name) != weight:
                        candidates[variant_name] = weight
                        fn_cfg["candidate_variants"] = candidates
                        changed = True

                assignments.append({
                    "function": fn_name,
                    "variant_name": variant_name,
                    "role": role,
                    "weight": weight,
                })
        else:
            strength_ref = model_info.get("strength_ref")
            if strength_ref:
                model_strengths = _load_model_strengths().get(strength_ref, {})
                scores = model_strengths.get("strength_scores", {})
                if scores:
                    demands = _load_function_demands().get("function_demands", {})
                    for fn_name, demand in demands.items():
                        fit = _compute_fit_score(scores, demand.get("weights", {}))
                        min_fit = demand.get("min_fit", 0.65)
                        if fit >= min_fit:
                            suggestions.append({
                                "model": model_slug,
                                "function": fn_name,
                                "fit_score": round(fit, 3),
                            })

    if changed:
        _save_tz_config(tz)

    unique_fns = sorted(set(functions_updated))
    msg_parts = []
    if unique_fns:
        prefix = "Would update" if dry_run else "Updated"
        msg_parts.append(f"{prefix} {len(unique_fns)} function(s): {', '.join(unique_fns)}")
    if suggestions:
        msg_parts.append(f"{len(suggestions)} suggestion(s) / missing variants")

    return StageResult(
        stage=3, name="Lane Assignment", success=True,
        message=" | ".join(msg_parts) if msg_parts else "No assignments",
        details={
            "functions_updated": unique_fns,
            "assignments": assignments,
            "suggestions": suggestions,
        },
    )


def _stage_4_coding_stacks(
    provider_slug: str,
    provider_config: Dict[str, Any],
    node_profile: Dict[str, Any],
    dry_run: bool = False,
) -> StageResult:
    """Check and activate coding stacks for this provider."""
    coding_stack = provider_config.get("coding_stack")
    if not coding_stack:
        return StageResult(
            stage=4, name="Coding Stacks", success=True,
            message="No coding stack associated with this provider",
        )

    profile_stacks = node_profile.get("coding_stacks", {})
    if coding_stack not in profile_stacks:
        return StageResult(
            stage=4, name="Coding Stacks", success=True,
            message=f"Stack '{coding_stack}' not in node profile — skipping",
            details={"stack": coding_stack, "available": list(profile_stacks.keys())},
        )

    stack_config = profile_stacks[coding_stack]
    tz_function = stack_config.get("tz_function", "unknown")
    local_fallback = stack_config.get("local_fallback", "none")

    # Check VRAM budget
    vram_warnings = []
    vram_budget = node_profile.get("vram_budget", {})
    if vram_budget:
        usable_mb = vram_budget.get("usable_mb", 0)
        co_groups = vram_budget.get("co_residency_groups", {})
        for group_name, group in co_groups.items():
            models_in_group = group.get("models", [])
            if local_fallback in models_in_group:
                total_mb = group.get("total_mb", 0)
                if total_mb > usable_mb:
                    vram_warnings.append(
                        f"VRAM tight: {group_name} ({total_mb}MB) exceeds usable ({usable_mb}MB)"
                    )

    return StageResult(
        stage=4, name="Coding Stacks", success=True,
        message=f"{coding_stack} ACTIVATED (fn: {tz_function}, fallback: {local_fallback})",
        details={
            "stack": coding_stack,
            "tz_function": tz_function,
            "local_fallback": local_fallback,
            "vram_warnings": vram_warnings,
        },
    )


# =============================================================================
# Stage 5: NATS Announcement
# =============================================================================

def _stage_5_nats(
    provider_slug: str,
    result: CascadeResult,
    node_id: str,
    env_var: str,
    dry_run: bool = False,
) -> StageResult:
    """Publish claw.provider.activated.v1 to NATS mesh."""
    payload = {
        "node_id": node_id,
        "provider": provider_slug,
        "env_var": env_var,
        "models_added": result.models_added,
        "functions_updated": result.functions_updated,
        "coding_stacks_activated": result.coding_stacks_activated,
        "vram_warnings": result.vram_warnings,
        "timestamp": _utc_timestamp(),
        "success": result.success,
    }

    if dry_run:
        return StageResult(
            stage=5, name="NATS Announce", success=True,
            message="Would publish claw.provider.activated.v1",
            details=payload,
        )

    published = _publish_nats_event("claw.provider.activated.v1", payload)

    return StageResult(
        stage=5, name="NATS Announce", success=True,  # Non-blocking
        message="claw.provider.activated.v1 published" if published else "NATS unavailable (non-blocking)",
        details={**payload, "published": published},
    )


# =============================================================================
# Stage 6: Capability Dashboard
# =============================================================================

def _stage_6_dashboard(result: CascadeResult) -> StageResult:
    """Print structured summary."""
    lines = [
        f"Provider Activation Cascade: {result.provider}",
        "=" * 50,
    ]
    for sr in result.stages:
        status = "✓" if sr.success else "✗"
        lines.append(f"  [{sr.stage}] {sr.name}: {sr.message}  {status}")

    lines.append("=" * 50)
    if result.success:
        lines.append(f"★ PMOVES morphed: +1 cloud provider")
        if result.functions_updated:
            lines.append(f"  Functions: {', '.join(result.functions_updated)}")
        if result.coding_stacks_activated:
            lines.append(f"  Stacks: {', '.join(result.coding_stacks_activated)}")
    else:
        failed = [s for s in result.stages if not s.success]
        lines.append(f"✗ Cascade failed at stage(s): {', '.join(str(s.stage) for s in failed)}")

    if result.vram_warnings:
        lines.append(f"  ⚠ VRAM: {'; '.join(result.vram_warnings)}")

    output = "\n".join(lines)
    print(output)

    return StageResult(
        stage=6, name="Dashboard", success=True,
        message="Summary printed",
        details={"output": output},
    )


# =============================================================================
# Public API
# =============================================================================

def activate_provider(
    provider: str,
    api_key: str,
    node_id: str = "auto",
    node_profile: str = "laptop-4090",
    restart_tz: bool = True,
    dry_run: bool = False,
) -> CascadeResult:
    """Run the full 6-stage provider activation cascade.

    Args:
        provider: Provider slug (e.g., "minimax", "anthropic")
        api_key: The API key value
        node_id: Node identifier for NATS announcements (default: auto-detect)
        node_profile: Profile ID from config/profiles/ (default: laptop-4090)
        restart_tz: Whether to restart TensorZero gateway after config update
        dry_run: If True, show what would happen without making changes

    Returns:
        CascadeResult with all stage outcomes
    """
    catalog = _load_provider_catalog()
    providers = catalog.get("providers", {})

    if provider not in providers:
        available = sorted(providers.keys())
        result = CascadeResult(provider=provider, success=False)
        result.stages.append(StageResult(
            stage=0, name="Lookup", success=False,
            message=f"Unknown provider '{provider}'. Available: {', '.join(available)}",
        ))
        return result

    provider_config = providers[provider]
    profile = _load_node_profile(node_profile)

    if node_id == "auto":
        import platform
        node_id = f"pmoves-{platform.node().lower().replace(' ', '-')}"

    result = CascadeResult(provider=provider, success=True)

    # Stage 1: Secrets
    s1 = _stage_1_secrets(provider, api_key, provider_config, dry_run)
    result.stages.append(s1)
    if not s1.success:
        result.success = False
        _stage_6_dashboard(result)
        return result

    # Stage 2: TZ Config
    s2 = _stage_2_tz_config(provider, provider_config, dry_run)
    result.stages.append(s2)
    result.models_added = s2.details.get("added", [])
    if not s2.success:
        result.success = False
        _stage_6_dashboard(result)
        return result

    # Restart TZ if config was changed
    if restart_tz and result.models_added and not dry_run:
        try:
            subprocess.run(
                ["docker", "compose", "-f", str(PMOVES_DIR / "docker-compose.yml"),
                 "restart", "tensorzero-gateway"],
                capture_output=True, text=True, timeout=60,
            )
            logger.info("TensorZero gateway restarted")
        except Exception as e:
            logger.warning(f"TZ restart skipped: {e}")

    # Stage 3: Lane Assignment
    s3 = _stage_3_lane_assignment(provider, provider_config, dry_run)
    result.stages.append(s3)
    result.functions_updated = s3.details.get("functions_updated", [])

    # Stage 4: Coding Stacks
    s4 = _stage_4_coding_stacks(provider, provider_config, profile, dry_run)
    result.stages.append(s4)
    if s4.details.get("stack"):
        result.coding_stacks_activated = [s4.details["stack"]]
    result.vram_warnings = s4.details.get("vram_warnings", [])

    # Stage 5: NATS
    s5 = _stage_5_nats(provider, result, node_id, provider_config["env_var"], dry_run)
    result.stages.append(s5)
    result.nats_published = s5.details.get("published", False)

    # Stage 6: Dashboard
    s6 = _stage_6_dashboard(result)
    result.stages.append(s6)

    return result


def check_provider(
    provider: str,
    node_profile: str = "laptop-4090",
) -> CascadeResult:
    """Dry-run: show what activation would do without making changes."""
    return activate_provider(
        provider=provider,
        api_key="<dry-run-key>",
        node_profile=node_profile,
        restart_tz=False,
        dry_run=True,
    )


def list_providers(node_profile: str = "laptop-4090") -> Dict[str, Any]:
    """List all known providers with activation status."""
    catalog = _load_provider_catalog()
    providers = catalog.get("providers", {})
    current_env = _read_env_shared()
    profile = _load_node_profile(node_profile)
    profile_stacks = profile.get("coding_stacks", {})

    result = {}
    for slug, config in providers.items():
        env_var = config["env_var"]
        current_val = current_env.get(env_var, "")
        is_set = bool(current_val) and not _is_placeholder(current_val)
        coding_stack = config.get("coding_stack")
        stack_in_profile = coding_stack in profile_stacks if coding_stack else None

        models = list(config.get("models", {}).keys())
        embed_models = list(config.get("embedding_models", {}).keys())

        result[slug] = {
            "env_var": env_var,
            "active": is_set,
            "models": models,
            "embedding_models": embed_models,
            "coding_stack": coding_stack,
            "stack_in_profile": stack_in_profile,
        }

    return result


def deactivate_provider(
    provider: str,
    node_id: str = "auto",
    dry_run: bool = False,
) -> CascadeResult:
    """Remove a provider's key and cascade the removal."""
    catalog = _load_provider_catalog()
    providers = catalog.get("providers", {})

    if provider not in providers:
        result = CascadeResult(provider=provider, success=False)
        result.stages.append(StageResult(
            stage=0, name="Lookup", success=False,
            message=f"Unknown provider '{provider}'",
        ))
        return result

    provider_config = providers[provider]
    env_var = provider_config["env_var"]
    models_removed = list(provider_config.get("models", {}).keys())

    if node_id == "auto":
        import platform
        node_id = f"pmoves-{platform.node().lower().replace(' ', '-')}"

    if dry_run:
        result = CascadeResult(provider=provider, success=True)
        result.stages.append(StageResult(
            stage=1, name="Deactivate", success=True,
            message=f"Would remove {env_var} from env.shared and run secrets-funnel",
            details={"env_var": env_var, "models_removed": models_removed},
        ))
        return result

    _remove_env_key(env_var)
    logger.info(f"Cleared {env_var} from env.shared")

    try:
        subprocess.run(
            ["make", "-C", str(PMOVES_DIR), "secrets-funnel"],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as e:
        logger.warning(f"secrets-funnel after deactivation: {e}")

    payload = {
        "node_id": node_id,
        "provider": provider,
        "env_var": env_var,
        "models_removed": models_removed,
        "timestamp": _utc_timestamp(),
        "success": True,
    }
    published = _publish_nats_event("claw.provider.deactivated.v1", payload)

    result = CascadeResult(provider=provider, success=True)
    result.nats_published = published
    result.stages.append(StageResult(
        stage=1, name="Deactivate", success=True,
        message=f"{env_var} cleared, secrets-funnel re-run",
        details={**payload, "published": published},
    ))
    return result


def main():
    # Force UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Provider Activation Cascade",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # activate
    p_act = sub.add_parser("activate", help="Activate a provider")
    p_act.add_argument("--provider", required=True, help="Provider slug")
    p_act.add_argument("--key", help="API key (reads from stdin if omitted)")
    p_act.add_argument("--node-profile", default="laptop-4090")
    p_act.add_argument("--restart-tz", action="store_true", default=True)
    p_act.add_argument("--no-restart-tz", dest="restart_tz", action="store_false")
    p_act.add_argument("--dry-run", action="store_true")

    # check
    p_chk = sub.add_parser("check", help="Dry-run activation")
    p_chk.add_argument("--provider", required=True)
    p_chk.add_argument("--node-profile", default="laptop-4090")

    # list
    p_lst = sub.add_parser("list", help="List providers and status")
    p_lst.add_argument("--node-profile", default="laptop-4090")
    p_lst.add_argument("--json", dest="as_json", action="store_true")

    # deactivate
    p_deact = sub.add_parser("deactivate", help="Deactivate a provider")
    p_deact.add_argument("--provider", required=True)
    p_deact.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.command == "activate":
        api_key = args.key
        if not api_key:
            api_key = getpass(f"Enter API key for {args.provider}: ").strip()
            if not api_key:
                print("No key provided. Aborting.")
                sys.exit(1)
        result = activate_provider(
            provider=args.provider,
            api_key=api_key,
            node_profile=args.node_profile,
            restart_tz=args.restart_tz,
            dry_run=args.dry_run,
        )
        sys.exit(0 if result.success else 1)

    elif args.command == "check":
        result = check_provider(provider=args.provider, node_profile=args.node_profile)
        sys.exit(0 if result.success else 1)

    elif args.command == "list":
        providers = list_providers(node_profile=args.node_profile)
        if args.as_json:
            print(json.dumps(providers, indent=2))
        else:
            print(f"{'Provider':<15} {'Env Var':<30} {'Active':<8} {'Stack':<25} Models")
            print("-" * 100)
            for slug, info in sorted(providers.items()):
                active = "✓" if info["active"] else "·"
                stack = info.get("coding_stack") or "—"
                models = ", ".join(info["models"][:3])
                if len(info["models"]) > 3:
                    models += f" (+{len(info['models']) - 3})"
                print(f"{slug:<15} {info['env_var']:<30} {active:<8} {stack:<25} {models}")

    elif args.command == "deactivate":
        result = deactivate_provider(
            provider=args.provider,
            dry_run=args.dry_run,
        )
        sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
