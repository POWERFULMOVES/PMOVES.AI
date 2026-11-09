#!/usr/bin/env python3
"""
Automated GitHub App Credential Population Script

This script automatically retrieves GitHub App credentials from GitHub Secrets
and populates them into env.shared, then runs the secrets-funnel to generate
tier environment files.

PREREQUISITES:
  - gh CLI installed and authenticated
  - GitHub App credentials in GitHub Secrets (GH_APP_ID, GH_APP_SEC, etc.)

USAGE:
    python tools/github_app_auto_setup.py

FLOW:
  1. Verifies GitHub CLI authentication
  2. Fetches GitHub App credentials from GitHub Secrets
  3. Updates env.shared with uncommented credentials
  4. Runs secrets-funnel to generate tier files
  5. Verifies credentials in env.tier-agent

Author: PMOVES.AI Automation
Version: 1.2.0
"""
import logging
import os
import shutil
import sys
import subprocess
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print a formatted header."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*70}{Colors.RESET}\n")


def print_step(step_num, text):
    """Print a step indicator."""
    print(f"{Colors.GREEN}{Colors.BOLD}[Step {step_num}]{Colors.RESET} {text}")


def print_success(text):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_warning(text):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_error(text):
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def setup_logging(script_name):
    """
    Set up logging to both file and console.

    Args:
        script_name: Name of script for log file naming

    Returns:
        Path: Log file path
    """
    log_dir = Path.home() / '.pmoves' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f'{script_name}.log'

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logging.info(f"=== Starting {script_name} ===")
    logging.info(f"Log file: {log_file}")
    return log_file


def run_command(cmd, check=False, capture_output=True, timeout=30):
    """
    Run a shell command with timeout.

    Args:
        cmd: Command string to execute
        check: Raise CalledProcessError on non-zero exit (default: False)
        capture_output: Capture stdout/stderr (default: True)
        timeout: Maximum seconds to wait (default: 30)

    Returns:
        subprocess.CompletedProcess

    Raises:
        subprocess.TimeoutExpired: If command exceeds timeout
        subprocess.CalledProcessError: If check=True and command fails
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture_output,
            text=True,
            check=check,
            timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired:
        print_error(f"Command timed out after {timeout}s: {cmd[:50]}...")
        raise


def verify_gh_auth():
    """Verify GitHub CLI is authenticated."""
    print_step(1, "Verifying GitHub CLI authentication...")

    try:
        result = run_command("gh auth status")
        if result.returncode == 0:
            print_success("GitHub CLI authenticated")
            # Extract username
            if "Logged in to" in result.stdout:
                from urllib.parse import urlparse
                for line in result.stdout.split('\n'):
                    stripped = line.strip()
                    # Validate host is exactly github.com, not a substring match
                    try:
                        parsed = urlparse(f"https://{stripped}")
                        if parsed.hostname == "github.com":
                            print(f"  {stripped}")
                    except Exception:
                        pass  # Skip lines that cannot be parsed as URLs
            return True
        else:
            print_error("GitHub CLI not authenticated")
            print("  Run: gh auth login")
            return False
    except Exception:
        print_error("Failed to verify GitHub CLI — check logs for details")
        return False


def get_github_secrets():
    """Fetch GitHub App credentials from GitHub Secrets."""
    print_step(2, "Fetching GitHub App credentials from GitHub Secrets...")

    gh_app_keys = {'GH_APP_ID', 'GH_APP_SEC', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID'}
    credentials = {}

    try:
        # Get all secrets at once, filter in Python (no shell injection)
        result = run_command("gh secret list --repo POWERFULMOVES/PMOVES.AI", timeout=30)

        if result.returncode != 0:
            print_error("Failed to list GitHub Secrets — check GitHub CLI auth status")
            return None

        print("  Checking GitHub Secrets for POWERFULMOVES/PMOVES.AI:")

        # Parse output safely in Python - count matches without logging tainted values
        found_count = 0
        for line in result.stdout.split('\n'):
            if not line.strip():
                continue
            # Extract secret name (first word in line)
            secret_name = line.strip().split()[0]
            if secret_name in gh_app_keys:
                credentials[secret_name] = "PRESENT_IN_GH_SECRETS"
                found_count += 1

        # Report results using only hardcoded key names (not tainted output)
        for key in gh_app_keys:
            if key in credentials:
                print_success(f"  {key}: Found in GitHub Secrets")

    except subprocess.TimeoutExpired as e:
        print_error(f"Timeout after {e.timeout}s - check network connectivity")
        return None
    except FileNotFoundError:
        print_error("GitHub CLI not found - install from https://cli.github.com/")
        return None
    except PermissionError:
        print_error("Permission denied executing GitHub CLI")
        return None
    except Exception:
        print_error("Failed to fetch GitHub Secrets — check logs for details")
        return None

    if len(credentials) == 4:
        print_success("All 4 GitHub App credentials found in GitHub Secrets")
        return credentials
    else:
        missing = gh_app_keys - set(credentials.keys())
        print_error(f"Only {len(credentials)}/4 credentials found in GitHub Secrets")
        for key in missing:
            print_warning(f"  {key}: Not found")
        print("\n  Missing credentials must be added to GitHub Secrets first:")
        print("  https://github.com/organizations/POWERFULMOVES/PMOVES.AI/settings/secrets/actions")
        return None


def update_env_shared():
    """Update env.shared with uncommented GitHub App credentials."""
    print_step(3, "Updating env.shared with GitHub App credentials...")

    repo_root = Path(__file__).parent.parent
    env_shared = repo_root / "pmoves" / "env.shared"

    if not env_shared.exists():
        print_error(f"env.shared not found at {env_shared}")
        return False

    # Read env.shared
    with open(env_shared) as f:
        lines = f.readlines()

    # Find and update GitHub App credential lines
    gh_app_keys = ['GH_APP_ID', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID', 'GH_APP_SEC']
    updated_count = 0
    output_lines = []

    for line in lines:
        is_commented = False
        is_gh_app_line = False

        # Check if this is a GitHub App credential line
        for key in gh_app_keys:
            if line.startswith(f'#{key}='):
                is_commented = True
                is_gh_app_line = True
                break
            elif line.startswith(f'{key}='):
                is_gh_app_line = True
                break

        if is_gh_app_line:
            if is_commented:
                # Uncomment the line (remove the #)
                updated_line = line.lstrip('#')
                output_lines.append(updated_line)
                updated_count += 1
                # Only print the key name, not the value (avoid clear-text secret logging)
                key_name = updated_line.split('=', 1)[0].strip() if '=' in updated_line else "unknown"
                print_success(f"  Uncommented: {key_name}=***")
            else:
                # Already uncommented
                output_lines.append(line)
        else:
            output_lines.append(line)

    if updated_count > 0:
        # Write back to env.shared
        with open(env_shared, 'w') as f:
            f.writelines(output_lines)
        print_success(f"Updated {updated_count} GitHub App credential lines in env.shared")
        return True
    else:
        print_warning("GitHub App credentials already uncommented in env.shared")
        return True


def run_secrets_funnel():
    """Run make secrets-funnel to generate tier files."""
    print_step(4, "Running secrets-funnel to generate tier files...")

    repo_root = Path(__file__).parent.parent
    os.chdir(repo_root / "pmoves")

    try:
        result = run_command("make secrets-funnel")
        if result.returncode == 0:
            print_success("secrets-funnel completed successfully")
            # Show summary of generated files
            if "env.tier-agent:" in result.stdout:
                for line in result.stdout.split('\n'):
                    if 'env.tier-agent:' in line:
                        print(f"  {line.strip()}")
            return True
        else:
            print_error("secrets-funnel failed")
            if result.stderr:
                logging.error(f"secrets-funnel stderr: {result.stderr}")
                print("  Check logs for error details")
            return False
    except Exception:
        print_error("Failed to run secrets-funnel — check logs for details")
        return False


def verify_tier_files():
    """Verify GitHub App credentials in env.tier-agent."""
    print_step(5, "Verifying GitHub App credentials in env.tier-agent...")

    repo_root = Path(__file__).parent.parent
    tier_agent = repo_root / "pmoves" / "env.tier-agent"

    if not tier_agent.exists():
        print_error("env.tier-agent not found")
        return False

    with open(tier_agent) as f:
        content = f.read()

    gh_app_keys = ['GH_APP_ID', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID', 'GH_APP_SEC']
    found_count = 0

    for key in gh_app_keys:
        if f'{key}=' in content:
            found_count += 1
            print_success(f"  {key}: Found in env.tier-agent")
        else:
            print_warning(f"  {key}: Not found in env.tier-agent")

    if found_count == 4:
        print_success("All 4 GitHub App credentials found in env.tier-agent")
        return True
    else:
        print_error(f"Only {found_count}/4 credentials found in env.tier-agent")
        return False


def main():
    """Main execution flow with rollback support."""
    log_file = setup_logging('github_app_auto_setup')

    print_header("GitHub App Credential Auto-Setup")

    env_shared_backup = None

    try:
        logging.info("Starting GitHub App credential auto-setup")

        # Verify prerequisites
        if not verify_gh_auth():
            print_error("\nPlease install and authenticate GitHub CLI first:")
            print("  1. Install: https://cli.github.com/")
            print("  2. Authenticate: gh auth login")
            logging.error("GitHub CLI authentication failed")
            return 1

        # Check GitHub Secrets
        credentials = get_github_secrets()
        if credentials is None:
            print_error("\nGitHub App credentials not found in GitHub Secrets")
            print("\nTo add them:")
            print("  1. Visit: https://github.com/organizations/POWERFULMOVES/settings/apps")
            print("  2. Select the PMOVES.AI GitHub App")
            print("  3. Copy credentials to GitHub Secrets")
            logging.error("GitHub App credentials not found in GitHub Secrets")
            return 1

        logging.info(f"Found {len(credentials)} GitHub App credentials in GitHub Secrets")

        # Backup env.shared before modification
        repo_root = Path(__file__).parent.parent
        env_shared = repo_root / "pmoves" / "env.shared"

        if env_shared.exists():
            env_shared_backup = env_shared.with_suffix('.bak')
            shutil.copy(env_shared, env_shared_backup)
            print(f"  Backed up env.shared to {env_shared_backup.name}")
            logging.info(f"Created backup: {env_shared_backup}")

        # Update env.shared
        if not update_env_shared():
            print_error("Failed to update env.shared")
            logging.error("Failed to update env.shared")
            return 1

        logging.info("Updated env.shared with GitHub App credentials")

        # Run secrets-funnel
        if not run_secrets_funnel():
            print_error("Rolling back env.shared changes due to secrets-funnel failure")
            if env_shared_backup and env_shared_backup.exists():
                shutil.copy(env_shared_backup, env_shared)
                print_success("Restored env.shared from backup")
            logging.error("secrets-funnel failed, rolled back changes")
            return 1

        logging.info("secrets-funnel completed successfully")

        # Verify tier files
        if not verify_tier_files():
            print_error("Rolling back env.shared changes due to verification failure")
            if env_shared_backup and env_shared_backup.exists():
                shutil.copy(env_shared_backup, env_shared)
                print_success("Restored env.shared from backup")
            logging.error("Tier file verification failed, rolled back changes")
            return 1

        logging.info("Tier file verification passed")

        # Success! Clean up backup
        if env_shared_backup and env_shared_backup.exists():
            env_shared_backup.unlink()
            print_success("Cleaned up backup file")
            logging.info("Cleaned up backup file")

        print_header("Setup Complete! 🎉")
        print_success("GitHub App credentials successfully populated")
        print("\nNext steps:")
        print("  1. Start services: docker compose up -d archon botz-gateway")
        print("  2. Verify credentials: docker compose logs archon | grep GH_APP")
        print("  3. Test token minting: cd PMOVES-BoTZ && python features/github/mint_and_exec.py")
        print()

        logging.info("GitHub App credential auto-setup completed successfully")
        return 0

    except Exception as e:
        logging.error(f"Setup failed with exception: {e}")
        print_error("Unexpected error during setup — check logs for details")
        print(f"  Full log: {log_file}")
        # Rollback on exception
        if env_shared_backup and env_shared_backup.exists():
            repo_root = Path(__file__).parent.parent
            env_shared = repo_root / "pmoves" / "env.shared"
            shutil.copy(env_shared_backup, env_shared)
            print_success("Restored env.shared from backup after error")
        raise


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print_warning("\nSetup cancelled by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print_error("Unexpected error — check logs for details")
        sys.exit(1)
