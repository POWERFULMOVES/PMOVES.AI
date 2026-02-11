#!/usr/bin/env python3
"""
PMOVES.AI Credential Setup Wizard

Automated CLI wizard for setting up PMOVES.AI credentials.
Supports GitHub/Docker authentication and provides branded defaults.

Usage:
    python3 -m pmoves.tools.credential_setup
    python3 pmoves/tools/credential_setup.py
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# =============================================================================
# Constants
# =============================================================================

PMOVES_ROOT = Path(__file__).parent.parent.parent
TIER_FILES = {
    "llm": "env.tier-llm",
    "data": "env.tier-data",
    "api": "env.tier-api",
    "agent": "env.tier-agent",
    "worker": "env.tier-worker",
    "media": "env.tier-media",
}

# Branded defaults that work out of the box
BRANDED_DEFAULTS = {
    # Service URLs
    "NATS_URL": "nats://nats:4222",
    "TENSORZERO_URL": "http://tensorzero-gateway:3030",
    "SUPABASE_URL": "http://supabase_kong_PMOVES.AI:8000",
    "QDRANT_URL": "http://qdrant:6333",
    "NEO4J_URL": "http://neo4j:7474",
    "MEILISEARCH_URL": "http://meilisearch:7700",
    "MINIO_ENDPOINT": "http://minio:9000",

    # Default ports
    "AGENT_ZERO_URL": "http://agent-zero:8080",
    "ARCHON_URL": "http://archon:8091",
    "HIRAG_V2_URL": "http://hi-rag-gateway-v2:8086",
    "PMOVES_YT_URL": "http://pmoves-yt:8077",
    "PROMETHEUS_URL": "http://prometheus:9090",
    "GRAFANA_URL": "http://grafana:3000",

    # Environment
    "PMOVES_ENV": "production",
    "LOG_LEVEL": "INFO",
    "METRICS_ENABLED": "true",
}

# =============================================================================
# Colors for Terminal Output
# =============================================================================

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def log_header(text: str):
    print(f"{Colors.HEADER}{text}{Colors.ENDC}")

def log_info(text: str):
    print(f"{Colors.OKBLUE}ℹ{Colors.ENDC} {text}")

def log_success(text: str):
    print(f"{Colors.OKGREEN}✓{Colors.ENDC} {text}")

def log_warning(text: str):
    print(f"{Colors.WARNING}⚠{Colors.ENDC} {text}")

def log_error(text: str):
    print(f"{Colors.FAIL}✗{Colors.ENDC} {text}")

def log_step(num: int, total: int, text: str):
    print(f"\n{Colors.BOLD}[{num}/{total}] {Colors.OKCYAN}{text}{Colors.ENDC}")

# =============================================================================
# GitHub Authentication
# =============================================================================

def check_github_cli() -> bool:
    """Check if GitHub CLI (gh) is installed and authenticated."""
    try:
        result = os.popen("gh auth status 2>&1").read()
        return "Logged in as" in result
    except Exception:
        return False

def get_github_secrets(owner: str, repo: str, token: Optional[str] = None) -> Dict[str, str]:
    """
    Fetch secrets from GitHub repository using API.

    Returns dictionary of secret names and placeholder values.
    (Actual secret values cannot be retrieved via API)
    """
    if not HAS_REQUESTS:
        log_warning("requests module not available. Install with: pip install requests")
        return {}

    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    # We can't list secret values, but we can list secret names
    # This helps users know which secrets they need to set
    try:
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/actions/secrets",
            headers=headers
        )
        if response.status_code == 200:
            secrets = response.json().get("secrets", {})
            return {s["name"]: "***" for s in secrets}
        else:
            log_warning(f"Could not fetch GitHub secrets: {response.status_code}")
            return {}
    except Exception as e:
        log_warning(f"Error fetching GitHub secrets: {e}")
        return {}

# =============================================================================
# Docker Authentication
# =============================================================================

def check_docker() -> bool:
    """Check if Docker is installed and running."""
    try:
        result = os.popen("docker info > /dev/null 2>&1 && echo 'running'").read()
        return "running" in result
    except Exception:
        return False

def get_docker_config() -> Dict[str, str]:
    """Read Docker config for registry credentials."""
    config_path = Path.home() / ".docker" / "config.json"
    if not config_path.exists():
        return {}

    try:
        with open(config_path) as f:
            config = json.load(f)

        creds = {}
        auths = config.get("auths", {})
        for registry, auth_data in auths.items():
            if "auth" in auth_data:
                import base64
                decoded = base64.b64decode(auth_data["auth"]).decode()
                username, password = decoded.split(":", 1)
                if "ghcr.io" in registry:
                    creds["GHCR_USERNAME"] = username
                    creds["GHCR_PASSWORD"] = password
                elif "index.docker.io" in registry or "docker.io" in registry:
                    creds["DOCKERHUB_USERNAME"] = username
                    creds["DOCKERHUB_PASSWORD"] = password
        return creds
    except Exception:
        return {}

# =============================================================================
# Tier Management
# =============================================================================

def get_tier_credentials(tier: str) -> List[str]:
    """Get list of credentials for a specific tier."""
    tier_credentials = {
        "llm": [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "COHERE_API_KEY",
            "DEEPSEEK_API_KEY",
            "MISTRAL_API_KEY",
            "OPENROUTER_API_KEY",
            "PERPLEXITYAI_API_KEY",
            "VOYAGE_API_KEY",
            "XAI_API_KEY",
            "FIREWORKS_AI_API_KEY",
            "ELEVENLABS_API_KEY",
        ],
        "data": [
            "POSTGRES_PASSWORD",
            "MINIO_ROOT_PASSWORD",
            "QDRANT_API_KEY",
            "NEO4J_USERNAME",
            "NEO4J_PASSWORD",
            "MEILISEARCH_API_KEY",
            "SURREAL_USER",
            "SURREAL_PASS",
        ],
        "api": [
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_JWT_SECRET",
            "PRESIGN_SHARED_SECRET",
        ],
        "agent": [
            "AGENT_ZERO_EVENTS_TOKEN",
            "DISCORD_WEBHOOK_URL",
            "DISCORD_USERNAME",
            "DISCORD_AVATAR_URL",
        ],
        "worker": [
            # Worker inherits from other tiers as needed
        ],
        "media": [
            "ELEVENLABS_API_KEY",
            "REPLICATE_API_TOKEN",
            "TINIFY_API_KEY",
        ],
    }
    return tier_credentials.get(tier, [])

def create_env_tier_file(tier: str, credentials: Dict[str, str]) -> Path:
    """Create env.tier-{tier} file with credentials."""
    tier_file = PMOVES_ROOT / f"env.tier-{tier}"

    # Add branded defaults first
    lines = []
    lines.append(f"# PMOVES.AI {tier.upper()} Tier Credentials")
    lines.append(f"# Generated by PMOVES.AI Credential Setup Wizard")
    lines.append(f"# Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("# Branded Defaults")
    for key, value in sorted(BRANDED_DEFAULTS.items()):
        lines.append(f"{key}={value}")
    lines.append("")
    lines.append("# User Credentials")
    for key, value in sorted(credentials.items()):
        if value:  # Only add non-empty values
            lines.append(f"{key}={value}")

    tier_file.write_text("\n".join(lines))
    return tier_file

# =============================================================================
# Interactive Prompts
# =============================================================================

def prompt_yes_no(question: str, default: bool = False) -> bool:
    """Prompt user for yes/no response."""
    default_str = "Y/n" if default else "y/N"
    response = input(f"{question} [{default_str}]: ").strip().lower()
    if not response:
        return default
    return response in ["y", "yes"]

def prompt_choice(question: str, choices: List[str], default: int = 0) -> int:
    """Prompt user to choose from a list."""
    for i, choice in enumerate(choices):
        default_mark = " (default)" if i == default else ""
        print(f"  {i + 1}. {choice}{default_mark}")

    while True:
        response = input(f"{question} [1-{len(choices)}]: ").strip()
        if not response:
            return default
        try:
            choice_idx = int(response) - 1
            if 0 <= choice_idx < len(choices):
                return choice_idx
        except ValueError:
            pass

        log_error("Invalid choice. Please enter a number between 1 and {}".format(len(choices)))

def prompt_credential(name: str, current: str = "") -> str:
    """Prompt user for a credential value."""
    if current:
        display = f"{name} [{current}]: "
    else:
        display = f"{name}: "

    import getpass
    if "SECRET" in name or "PASSWORD" in name or "TOKEN" in name or "KEY" in name:
        value = getpass.getpass(display)
    else:
        value = input(display).strip()

    return value or current

# =============================================================================
# Main Wizard Flow
# =============================================================================

def wizard_github_auth():
    """Step 1: GitHub Authentication."""
    log_step(1, 6, "GitHub Authentication")

    print("\nThis wizard can help you set up credentials from GitHub Secrets.")
    print("GitHub Secrets are the recommended way to manage credentials in production.")
    print()

    use_github = prompt_yes_no("Do you want to use GitHub Secrets?", default=True)

    if not use_github:
        return {}, ""

    if not check_github_cli():
        log_error("GitHub CLI (gh) is not installed or not authenticated.")
        print("\nTo install GitHub CLI:")
        print("  # macOS")
        print("  brew install gh")
        print("  # Linux")
        print("  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg")
        print("  sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg")
        print("  echo \"deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null")
        print("  sudo apt update")
        print("  sudo apt install gh")
        print("\nTo authenticate:")
        print("  gh auth login")
        return {}, ""

    # Get repo info
    default_owner = os.environ.get("GITHUB_OWNER", "POWERFULMOVES")
    default_repo = os.environ.get("GITHUB_REPO", "PMOVES.AI")

    owner = input(f"GitHub owner [{default_owner}]: ").strip() or default_owner
    repo = input(f"GitHub repository [{default_repo}]: ").strip() or default_repo

    # Try to fetch secret names (not values)
    secrets = get_github_secrets(owner, repo)
    if secrets:
        log_success(f"Found {len(secrets)} secrets in GitHub (values cannot be retrieved via API)")
        for secret_name in sorted(secrets.keys())[:10]:
            print(f"  - {secret_name}")
        if len(secrets) > 10:
            print(f"  ... and {len(secrets) - 10} more")

    return {"owner": owner, "repo": repo}, f"{owner}/{repo}"

def wizard_docker_auth():
    """Step 2: Docker Authentication."""
    log_step(2, 6, "Docker Authentication")

    print("\nPMOVES.AI uses Docker for container orchestration.")
    print("Docker registry credentials are needed for pulling/pushing images.")
    print()

    if not check_docker():
        log_warning("Docker is not running or not installed.")
        print("\nTo install Docker:")
        print("  # Ubuntu/Debian")
        print("  curl -fsSL https://get.docker.com | sh")
        print("  # macOS")
        print("  brew install --cask docker")
        return {}

    docker_creds = get_docker_config()
    if docker_creds:
        log_success("Found Docker credentials:")
        for key, value in docker_creds.items():
            print(f"  {key}: {value[:10]}..." if len(value) > 10 else f"  {key}: {value}")

    return docker_creds

def wizard_select_tier():
    """Step 3: Select Tier to Configure."""
    log_step(3, 6, "Select Service Tier")

    print("\nPMOVES.AI organizes credentials into service tiers.")
    print("Each tier contains credentials for that type of service.")
    print()

    tier_choices = [
        "LLM - Large Language Model providers (OpenAI, Anthropic, etc.)",
        "DATA - Databases and storage (Postgres, Qdrant, MinIO, etc.)",
        "API - API gateways and authentication (Supabase, JWT)",
        "AGENT - Agent orchestration (Agent Zero, Discord)",
        "WORKER - Background workers (PMOVES.YT, extract)",
        "MEDIA - Media processing (TTS, ASR, video)",
        "ALL - Configure all tiers",
    ]

    choice = prompt_choice("Which tier do you want to configure?", tier_choices, default=6)

    tiers = ["llm", "data", "api", "agent", "worker", "media"]
    if choice == 6:  # ALL
        return tiers
    return [tiers[choice]]

def wizard_collect_credentials(tiers: List[str]):
    """Step 4: Collect Credentials."""
    log_step(4, 6, "Collect Credentials")

    print("\nFor each credential, you can:")
    print("  - Enter a value")
    print("  - Press Enter to skip (will use empty default)")
    print("  - Type 'github' to load from GitHub Secrets")
    print("  - Type 'skip' to skip this credential")
    print()

    credentials = {}

    # Collect unique credentials from all selected tiers
    all_creds = set()
    for tier in tiers:
        all_creds.update(get_tier_credentials(tier))

    # Sort for consistent display
    for cred in sorted(all_creds):
        value = ""
        while True:
            try:
                value = prompt_credential(cred, value)

                if value.lower() == "skip":
                    value = ""
                    break
                elif value.lower() == "github":
                    # Use GitHub Actions secret reference format
                    # This creates a placeholder that will be resolved by GitHub Actions
                    value = f"${{{{cred}}}}"
                    break
                else:
                    break
            except KeyboardInterrupt:
                print()
                log_warning("Skipping remaining credentials")
                return credentials

        if value:
            credentials[cred] = value

    return credentials

def wizard_write_files(tiers: List[str], credentials: Dict[str, str]):
    """Step 5: Write Configuration Files."""
    log_step(5, 6, "Write Configuration Files")

    print(f"\nWriting tier files to: {PMOVES_ROOT}")
    print()

    for tier in tiers:
        tier_file = create_env_tier_file(tier, credentials)
        log_success(f"Created {tier_file.name}")

    # Create/update .env file with all credentials
    env_file = PMOVES_ROOT / ".env"
    lines = []
    lines.append("# PMOVES.AI Environment")
    lines.append("# Generated by Credential Setup Wizard")
    lines.append(f"# Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    # Add all credentials
    for key, value in sorted(credentials.items()):
        lines.append(f"{key}={value}")

    env_file.write_text("\n".join(lines))
    log_success(f"Created .env file")

def wizard_complete():
    """Step 6: Complete and Instructions."""
    log_step(6, 6, "Setup Complete!")

    print("\n" + "=" * 60)
    log_success("PMOVES.AI credentials configured successfully!")
    print("=" * 60)
    print()
    print("Next Steps:")
    print()
    print("1. Start PMOVES.AI services:")
    print("   cd PMOVES.AI")
    print("   docker compose up -d")
    print()
    print("2. Verify services are running:")
    print("   docker compose ps")
    print()
    print("3. Check service health:")
    print("   curl http://localhost:8080/healthz  # Agent Zero")
    print("   curl http://localhost:3030/healthz  # TensorZero")
    print()
    print("4. View metrics:")
    print("   http://localhost:9090  # Prometheus")
    print("   http://localhost:3000  # Grafana")
    print()
    print("For more information, see:")
    print("  - docs/TIER_BASED_CREDENTIAL_ARCHITECTURE.md")
    print("  - docs/SECRETS.md")
    print("  - pmoves/docs/SECRETS_ONBOARDING.md")
    print()

    log_info("To update credentials later, re-run this wizard or:")
    print("  - Edit env.tier-* files directly")
    print("  - Run: python3 -m pmoves.tools.credential_setup")

# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="PMOVES.AI Credential Setup Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 -m pmoves.tools.credential_setup
  python3 pmoves/tools/credential_setup.py --tier llm
  python3 pmoves/tools/credential_setup.py --all-tiers

Environment Variables:
  GITHUB_OWNER  - GitHub repository owner (default: POWERFULMOVES)
  GITHUB_REPO   - GitHub repository name (default: PMOVES.AI)
  GITHUB_TOKEN  - GitHub personal access token (for API access)
        """
    )

    parser.add_argument(
        "--tier",
        choices=["llm", "data", "api", "agent", "worker", "media"],
        help="Configure specific tier (default: interactive)"
    )
    parser.add_argument(
        "--all-tiers",
        action="store_true",
        help="Configure all tiers"
    )
    parser.add_argument(
        "--github-owner",
        help="GitHub repository owner"
    )
    parser.add_argument(
        "--github-repo",
        help="GitHub repository name"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without prompts (use with --tier)"
    )

    args = parser.parse_args()

    # Print welcome message
    print()
    log_header("PMOVES.AI Credential Setup Wizard")
    print()
    print("This wizard will help you set up credentials for PMOVES.AI.")
    print("You can authenticate via GitHub/Docker and configure service tiers.")
    print()

    try:
        if args.non_interactive and args.tier:
            # Non-interactive mode for specific tier
            log_info(f"Configuring {args.tier} tier in non-interactive mode")
            credentials = {}
            tier_file = create_env_tier_file(args.tier, credentials)
            log_success(f"Created {tier_file.name} with branded defaults")
            log_info("Edit the file to add your actual credentials")
            return 0

        if args.all_tiers:
            tiers = ["llm", "data", "api", "agent", "worker", "media"]
        elif args.tier:
            tiers = [args.tier]
        else:
            # Interactive mode
            github_info, github_repo = wizard_github_auth()
            docker_creds = wizard_docker_auth()
            tiers = wizard_select_tier()
            credentials = wizard_collect_credentials(tiers)
            wizard_write_files(tiers, credentials)
            wizard_complete()

        return 0

    except KeyboardInterrupt:
        print()
        log_warning("Setup cancelled by user")
        return 1
    except Exception as e:
        log_error(f"Error during setup: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
