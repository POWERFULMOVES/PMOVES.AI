"""
CHIT (Cognitive Holographic Information Transfer) Module

Provides encoding/decoding of environment secrets using CGP (CHIT Geometry Packets).
Supports multi-target output: tier env files, GitHub Secrets, Docker Secrets.
"""

from __future__ import annotations

import hashlib
import json
import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# CHIT CGP Spec Version
CHIT_CGP_VERSION = "chit.cgp.v0.1"


@dataclass
class CGPPoint:
    """A single point in the CHIT Geometry Packet."""
    label: str
    value: str
    anchor: List[float]  # 3D vector (x, y, z)
    encoding: str = "cleartext"  # or "hex"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "value": self.value if self.encoding == "cleartext" else _hex_encode(self.value),
            "anchor": self.anchor,
            "encoding": self.encoding,
        }


@dataclass
class CGPPayload:
    """CHIT Geometry Packet payload."""
    version: str = CHIT_CGP_VERSION
    namespace: str = "pmoves.secrets"
    description: str = ""
    points: List[CGPPoint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "namespace": self.namespace,
            "description": self.description,
            "points": [p.to_dict() for p in self.points],
        }


def _generate_anchor(label: str, salt: str = "") -> List[float]:
    """
    Generate a deterministic 3D anchor vector from a label using SHA-256.

    The anchor is derived from the first 12 bytes of SHA-256(label + salt),
    converted to 3 float values in [0, 1).
    """
    digest = hashlib.sha256(f"{label}{salt}".encode()).digest()[:12]
    # Convert 12 bytes to 3 floats in [0, 1]
    floats = []
    for i in range(3):
        chunk = digest[i*4:(i+1)*4]
        value = int.from_bytes(chunk, "big") / 2**32
        floats.append(round(value, 10))
    return floats


def _hex_encode(value: str) -> str:
    """Hex-encode a string value."""
    return base64.b16encode(value.encode()).decode()


def _hex_decode(value: str) -> str:
    """Hex-decode a string value."""
    # Remove any non-hex characters
    clean = value.strip().replace(" ", "")
    return base64.b16decode(clean.encode()).decode()


def encode_secret_map(
    secrets: Dict[str, str],
    namespace: str = "pmoves.secrets",
    description: str = "",
    include_cleartext: bool = True,
) -> Dict[str, Any]:
    """
    Encode a secret map into a CHIT Geometry Packet.

    Args:
        secrets: Dictionary of secret key-value pairs
        namespace: Namespace for the CGP
        description: Human-readable description
        include_cleartext: If True, store cleartext values alongside hex

    Returns:
        CGP dictionary ready for JSON serialization
    """
    payload = CGPPayload(
        version=CHIT_CGP_VERSION,
        namespace=namespace,
        description=description,
    )

    for label, value in sorted(secrets.items()):
        anchor = _generate_anchor(label)

        # Store both cleartext and hex if requested
        if include_cleartext:
            point = CGPPoint(
                label=label,
                value=value,
                anchor=anchor,
                encoding="cleartext",
            )
        else:
            point = CGPPoint(
                label=label,
                value=value,
                anchor=anchor,
                encoding="hex",
            )

        payload.points.append(point)

    return payload.to_dict()


def decode_secret_map(cgp_dict: Dict[str, Any]) -> Dict[str, str]:
    """
    Decode a CHIT Geometry Packet back into a secret map.

    Args:
        cgp_dict: CGP dictionary (from JSON)

    Returns:
        Dictionary of secret key-value pairs
    """
    secrets = {}

    for point_data in cgp_dict.get("points", []):
        label = point_data["label"]
        value = point_data["value"]
        encoding = point_data.get("encoding", "cleartext")

        # Handle hex encoding
        if encoding == "hex" or "\\" in value or value.startswith(("0x", "\\x")):
            try:
                # Try hex decode
                if value.startswith("0x"):
                    value = value[2:]
                decoded = _hex_decode(value)
                secrets[label] = decoded
            except (ValueError, TypeError) as e:
                # Fallback to raw value on decode failure
                logger.warning(f"Failed to hex-decode value for '{label}': {e}, using raw value")
                secrets[label] = value
        else:
            secrets[label] = value

    return secrets


def load_cgp(path: Path) -> Dict[str, Any]:
    """Load a CGP JSON file."""
    with open(path) as f:
        return json.load(f)


def save_cgp(cgp_dict: Dict[str, Any], path: Path) -> None:
    """Save a CGP dictionary to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cgp_dict, f, indent=2)


def write_to_tier_envs(
    secrets: Dict[str, str],
    tier_files: Dict[str, List[str]],
    base_dir: Path,
) -> None:
    """
    Write secrets to tier env files.

    Args:
        secrets: Dictionary of secrets (label -> value)
        tier_files: Mapping of tier -> list of secret labels
        base_dir: Base directory for tier files
    """
    for tier, labels in tier_files.items():
        tier_file = base_dir / f"env.tier-{tier}"
        if not tier_file.exists():
            # Create file with header
            tier_file.write_text(
                f"# PMOVES.AI Tier {tier.upper()} Environment\n"
                f"# Auto-generated by CHIT. Do not edit directly.\n"
                f"# Use 'pmoves env init' to regenerate.\n\n"
            )

        # Read existing content
        content = tier_file.read_text()
        lines = content.split("\n")

        # Update or add each secret
        for label in labels:
            if label not in secrets:
                continue

            value = secrets[label]
            env_line = f"{label}={value}"

            # Check if label already exists
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{label}="):
                    lines[i] = env_line
                    found = True
                    break

            if not found:
                lines.append(env_line)

        # Write back
        tier_file.write_text("\n".join(lines) + "\n")


def write_github_secrets(
    secrets: Dict[str, str],
    output_path: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Generate GitHub Actions secrets sync file.

    Args:
        secrets: Dictionary of secrets (label -> value)
        output_path: Optional path to write JSON file

    Returns:
        Dictionary of GitHub secret name -> value
    """
    # GitHub Secrets use the same label (with PMOVES_ prefix if not already)
    github_secrets = {}
    for label, value in secrets.items():
        # Ensure PMOVES_ prefix for consistency
        gh_label = label if label.startswith("PMOVES_") else f"PMOVES_{label}"
        github_secrets[gh_label] = value

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(github_secrets, f, indent=2)

    return github_secrets


def write_docker_secrets(
    secrets: Dict[str, str],
    output_path: Optional[Path] = None,
) -> Dict[str, str]:
    """
    Generate Docker Swarm secrets file.

    Args:
        secrets: Dictionary of secrets (label -> value)
        output_path: Optional path to write JSON file

    Returns:
        Dictionary of Docker secret name -> value
    """
    # Docker Secrets use lowercase with underscore prefix
    docker_secrets = {}
    for label, value in secrets.items():
        docker_name = f"pmoves_{label.lower()}"
        docker_secrets[docker_name] = value

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(docker_secrets, f, indent=2)

    return docker_secrets


def sync_common_credentials(
    base_dir: Path,
    common_creds: Optional[Dict[str, str]] = None,
    force: bool = False,
) -> Dict[str, List[str]]:
    """
    Ensure common credentials are consistent across all tier env files.

    This function ADDS missing credentials to tier env files but does NOT
    overwrite existing values unless force=True. This prevents accidentally
    replacing strong production passwords with weak development defaults.

    WARNING: Default credentials are for development only.
    Do not use 'changeme' or 'minioadmin' in production.

    Args:
        base_dir: Base directory containing env.tier-* files
        common_creds: Optional dict of credential key -> value. If not provided,
                      uses sensible defaults for PMOVES.AI development.
        force: If True, overwrite existing credentials. If False (default),
               only add missing credentials, never replace existing ones.

    Returns:
        Dictionary mapping file paths to lists of changes made:
        {"/path/to/env.tier-data": ["Added POSTGRES_PASSWORD=changeme"], ...}

    Default credentials (when common_creds not provided):
        - POSTGRES_PASSWORD: changeme
        - MINIO_ACCESS_KEY: minioadmin
        - MINIO_SECRET_KEY: minioadmin
        - MINIO_ROOT_USER: minioadmin
        - MINIO_ROOT_PASSWORD: minioadmin
        - MINIO_USER: minioadmin
        - MINIO_PASSWORD: minioadmin
        - NEO4J_AUTH: neo4j/changeme
        - NEO4J_PASSWORD: changeme
        - PGRST_DB_URI: postgres://pmoves:changeme@postgres:5432/pmoves
    """
    if common_creds is None:
        common_creds = {
            "POSTGRES_PASSWORD": "changeme",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin",
            "MINIO_ROOT_USER": "minioadmin",
            "MINIO_ROOT_PASSWORD": "minioadmin",
            "MINIO_USER": "minioadmin",
            "MINIO_PASSWORD": "minioadmin",
            "NEO4J_AUTH": "neo4j/changeme",
            "NEO4J_PASSWORD": "changeme",
            "PGRST_DB_URI": "postgres://pmoves:changeme@postgres:5432/pmoves",
        }

    # Tier files that may contain common credentials
    tier_files = [
        base_dir / "env.tier-data",
        base_dir / "env.tier-api",
        base_dir / "env.tier-media",
        base_dir / "env.tier-worker",
        base_dir / "env.tier-agent",
        base_dir / "env.tier-llm",
    ]

    results: Dict[str, List[str]] = {}

    for tier_path in tier_files:
        changes: List[str] = []

        try:
            if not tier_path.exists():
                logger.debug(f"Tier file does not exist: {tier_path}")
                continue

            content = tier_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            modified = False

            for cred, value in common_creds.items():
                # Check if credential exists in file
                found = False
                for i, line in enumerate(lines):
                    if line.startswith(f"{cred}="):
                        found = True
                        # Only update if force=True and value differs
                        if force:
                            current = line.split("=", 1)[1].strip()
                            if current != value:
                                lines[i] = f"{cred}={value}"
                                changes.append(f"Updated {cred}={value[:8]}..." if len(value) > 8 else f"Updated {cred}={value}")
                                modified = True
                                logger.info(f"Updated credential '{cred}' in {tier_path.name}")
                        break

                # Credential not found - append at end of file
                # before any trailing empty lines
                if not found:
                    for j in range(len(lines) - 1, -1, -1):
                        if lines[j].strip() and not lines[j].startswith("#"):
                            lines.insert(j + 1, f"{cred}={value}")
                            changes.append(f"Added {cred}={value[:8]}..." if len(value) > 8 else f"Added {cred}={value}")
                            modified = True
                            logger.info(f"Added credential '{cred}' to {tier_path.name}")
                            break

            if modified:
                tier_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            if changes:
                results[str(tier_path)] = changes

        except (PermissionError, OSError) as e:
            logger.error(f"Cannot access {tier_path}: {e}")
            results[str(tier_path)] = [f"ERROR: {e}"]
        except UnicodeDecodeError as e:
            logger.error(f"Cannot decode {tier_path}: {e}")
            results[str(tier_path)] = [f"ERROR: Unicode decode failed"]
        except Exception as e:
            logger.error(f"Unexpected error processing {tier_path}: {e}")
            results[str(tier_path)] = [f"ERROR: {e}"]

    return results


def apply_manifest_v2(
    secrets: Dict[str, str],
    manifest_path: Path,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Apply secrets according to a v2 manifest with tier mappings and multi-target output.

    Args:
        secrets: Dictionary of secrets (label -> value)
        manifest_path: Path to secrets_manifest_v2.yaml
        base_dir: Base directory for tier files (defaults to manifest dir parent)

    Returns:
        Summary of what was written

    Raises:
        FileNotFoundError: If manifest file does not exist
        ValueError: If manifest YAML is invalid or malformed
    """
    import yaml

    if base_dir is None:
        base_dir = manifest_path.parent.parent

    # Load manifest with proper error handling
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
    except FileNotFoundError as e:
        logger.error(f"Manifest file not found: {manifest_path}")
        raise FileNotFoundError(f"Manifest not found: {manifest_path}") from e
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in manifest {manifest_path}: {e}")
        raise ValueError(f"Invalid YAML in manifest: {e}") from e
    except (PermissionError, OSError) as e:
        logger.error(f"Cannot read manifest {manifest_path}: {e}")
        raise

    # Validate manifest structure
    if not isinstance(manifest, dict):
        raise ValueError(f"Manifest must be a dictionary, got {type(manifest).__name__}")

    if "entries" not in manifest:
        logger.warning(f"Manifest {manifest_path} has no 'entries' key")
        return {"tier_files": [], "github_secrets": 0, "docker_secrets": 0}

    # Group secrets by tier file
    tier_files: Dict[str, List[str]] = {}
    github_secrets: Dict[str, str] = {}
    docker_secrets: Dict[str, str] = {}

    for entry in manifest.get("entries", []):
        source = entry["source"]

        # Handle static values (configuration, not secrets)
        if source.get("type") == "static":
            value = source["value"]
            label = value  # For tracking/debugging
        # Handle CGP secrets
        else:
            label = source["label"]
            if label not in secrets:
                continue
            value = secrets[label]

        for target in entry.get("targets", []):
            if "file" in target:
                file_path = target["file"]
                if file_path.startswith("env.tier-"):
                    tier = file_path.replace("env.tier-", "")
                    if tier not in tier_files:
                        tier_files[tier] = []
                    tier_files[tier].append(label)

            if "github_secret" in target:
                gh_label = target["github_secret"]
                github_secrets[gh_label] = value

            if "docker_secret" in target:
                docker_name = target["docker_secret"]
                docker_secrets[docker_name] = value

    # Write tier env files
    if tier_files:
        write_to_tier_envs(secrets, tier_files, base_dir)

    # Sync common credentials across all tier files
    sync_common_credentials(base_dir)

    # Write GitHub secrets
    github_path = base_dir / "data" / "chit" / "github_secrets.json"
    if github_secrets:
        write_github_secrets(github_secrets, github_path)

    # Write Docker secrets
    docker_path = base_dir / "data" / "chit" / "docker_secrets.json"
    if docker_secrets:
        write_docker_secrets(docker_secrets, docker_path)

    return {
        "tier_files": list(tier_files.keys()),
        "github_secrets": len(github_secrets),
        "docker_secrets": len(docker_secrets),
    }
