#!/usr/bin/env python3
"""
GitHub App Setup Verification Script

This script verifies that all components of the GitHub App integration
are properly configured across env.shared, env.tier-agent, and Docker Compose.

USAGE:
    python tools/verify_github_app_setup.py

VERIFICATION CHECKS:
  1. GitHub CLI authentication
  2. GitHub App credentials in GitHub Secrets
  3. GitHub App credentials in env.shared (uncommented)
  4. GitHub App credentials in env.tier-agent
  5. Docker Compose configuration references

Author: PMOVES.AI Automation
Version: 1.2.0
"""
import json
import logging
import os
import re
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


def print_check(category, text, passed):
    """Print a check result."""
    icon = f"{Colors.GREEN}✓{Colors.RESET}" if passed else f"{Colors.RED}✗{Colors.RESET}"
    status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
    print(f"{icon} [{status}] {Colors.BOLD}{category}:{Colors.RESET} {text}")
    return passed


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


def read_env_file(file_path):
    """
    Read environment file with proper error handling.

    Args:
        file_path: Path to environment file

    Returns:
        str: File content

    Raises:
        SystemExit: If file cannot be read (with helpful message)
    """
    try:
        with open(file_path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print_error(f"File not found: {file_path}")
        if "env.shared" in str(file_path):
            print("  Run 'make secrets-funnel' to generate this file")
        sys.exit(1)
    except PermissionError:
        print_error(f"Permission denied reading: {file_path}")
        print("  Check file permissions and try again")
        sys.exit(1)
    except IsADirectoryError:
        print_error(f"Path is a directory, not a file: {file_path}")
        sys.exit(1)
    except UnicodeDecodeError as e:
        print_error(f"File encoding error in {file_path}: {e}")
        print("  Ensure file is UTF-8 encoded")
        sys.exit(1)


def validate_credential_value(key, value):
    """
    Validate GitHub App credential value format.

    Args:
        key: Credential name (e.g., 'GH_APP_ID')
        value: Credential value

    Returns:
        tuple: (is_valid, error_message)
    """
    if not value or value.strip() == "":
        return False, "empty value"

    if key == 'GH_APP_ID':
        if not value.isdigit():
            return False, "must be numeric"

    elif key == 'GH_APP_CLIENT_ID':
        if not re.match(r'^[A-Za-z0-9_-]+$', value):
            return False, "invalid client ID format"

    elif key == 'GH_APP_INSTALLATION_ID':
        if not value.isdigit():
            return False, "must be numeric"

    elif key == 'GH_APP_SEC':
        if not value.startswith('-----BEGIN'):
            return False, "must be PEM-formatted private key"

    return True, None


def verify_gh_cli():
    """Verify GitHub CLI is installed and authenticated."""
    try:
        result = run_command("gh --version")
        if result.returncode == 0:
            version = result.stdout.strip()
            auth_result = run_command("gh auth status")
            is_authed = auth_result.returncode == 0
            print_check("GitHub CLI", f"Installed ({version}) and {'authenticated' if is_authed else 'NOT authenticated'}", is_authed)
            return is_authed
        else:
            print_check("GitHub CLI", "Not installed", False)
            return False
    except Exception as e:
        print_check("GitHub CLI", f"Error: {e}", False)
        return False


def verify_github_secrets():
    """Verify GitHub App credentials in GitHub Secrets."""
    gh_app_keys = {'GH_APP_ID', 'GH_APP_SEC', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID'}
    found_keys = set()

    try:
        # Get all secrets at once, filter in Python (no shell injection)
        result = run_command("gh secret list --repo POWERFULMOVES/PMOVES.AI", timeout=30)

        if result.returncode != 0:
            print_check("GitHub Secrets", f"Failed to list: {result.stderr}", False)
            return False

        print("  Checking GitHub Secrets for POWERFULMOVES/PMOVES.AI:")

        # Parse output safely in Python
        for line in result.stdout.split('\n'):
            if not line.strip():
                continue
            # Extract secret name (first word in line)
            secret_name = line.strip().split()[0]
            if secret_name in gh_app_keys:
                found_keys.add(secret_name)

        # Report results using only hardcoded key names (not tainted values)
        for key in gh_app_keys:
            if key in found_keys:
                print_success(f"  {key}: Found in GitHub Secrets")
            else:
                print_warning(f"  {key}: Not found in GitHub Secrets")

    except subprocess.TimeoutExpired as e:
        print_check("GitHub Secrets", f"Timeout after {e.timeout}s - check network connectivity", False)
        return False
    except FileNotFoundError:
        print_check("GitHub Secrets", "GitHub CLI not found - install from https://cli.github.com/", False)
        return False
    except PermissionError:
        print_check("GitHub Secrets", "Permission denied executing GitHub CLI", False)
        return False
    except Exception as e:
        print_check("GitHub Secrets", f"Unexpected error: {type(e).__name__}: {e}", False)
        return False

    passed = len(found_keys) == 4
    print_check("GitHub Secrets", f"GitHub App credentials ({len(found_keys)}/4 found)", passed)
    return passed


def verify_env_shared():
    """Verify GitHub App credentials in env.shared (uncommented)."""
    repo_root = Path(__file__).parent.parent
    env_shared = repo_root / "pmoves" / "env.shared"

    if not env_shared.exists():
        print_check("env.shared", "File not found", False)
        return False

    content = read_env_file(env_shared)

    # Check for uncommented credentials (not starting with #)
    gh_app_keys = ['GH_APP_ID', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID', 'GH_APP_SEC']
    found_count = 0
    found_invalid = 0

    for key in gh_app_keys:
        # Look for uncommented lines (key=value, not #key=value)
        lines = content.split('\n')
        for line in lines:
            if line.strip().startswith(f'{key}='):
                # Extract value and validate
                value = line.strip().split('=', 1)[1] if '=' in line else ''
                is_valid, error = validate_credential_value(key, value)

                if is_valid:
                    found_count += 1
                    print_success(f"  {key}: Valid (set)")
                else:
                    found_invalid += 1
                    print_error(f"  {key}: Invalid format")
                break

    passed = found_count == 4 and found_invalid == 0
    if found_invalid > 0:
        print_check("env.shared", f"GitHub App credentials: {found_count}/4 valid, {found_invalid} invalid", passed)
    else:
        print_check("env.shared", f"GitHub App credentials uncommented ({found_count}/4)", passed)
    return passed


def verify_env_tier_agent():
    """Verify GitHub App credentials in env.tier-agent."""
    repo_root = Path(__file__).parent.parent
    tier_agent = repo_root / "pmoves" / "env.tier-agent"

    if not tier_agent.exists():
        print_check("env.tier-agent", "File not found (run 'make secrets-funnel' first)", False)
        return False

    content = read_env_file(tier_agent)

    gh_app_keys = ['GH_APP_ID', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID', 'GH_APP_SEC']
    found_count = 0

    for key in gh_app_keys:
        if f'{key}=' in content:
            found_count += 1

    passed = found_count == 4
    print_check("env.tier-agent", f"GitHub App credentials present ({found_count}/4)", passed)
    return passed


def verify_docker_compose():
    """Verify Docker Compose references GitHub App credentials."""
    repo_root = Path(__file__).parent.parent
    compose_file = repo_root / "pmoves" / "docker-compose.yml"

    if not compose_file.exists():
        print_check("docker-compose.yml", "File not found", False)
        return False

    with open(compose_file) as f:
        content = f.read()

    # Check for GH_APP_ references in environment variables
    gh_app_refs = content.count('GH_APP_')
    passed = gh_app_refs > 0

    print_check("docker-compose.yml", f"GitHub App credential references ({gh_app_refs} found)", passed)
    return passed


def verify_chit_manifest():
    """Verify CHIT manifest includes GitHub App credentials."""
    repo_root = Path(__file__).parent.parent
    manifest_file = repo_root / "pmoves" / "chit" / "secrets_manifest.yaml"

    if not manifest_file.exists():
        print_check("CHIT Manifest", "File not found", False)
        return False

    content = read_env_file(manifest_file)

    # Check for specific credential keys, not just "gh_app" string
    required_keys = ['GH_APP_ID', 'GH_APP_SEC', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID']
    has_gh_app = all(key in content for key in required_keys)
    passed = has_gh_app

    print_check("CHIT Manifest", f"GitHub App entries {'present' if passed else 'NOT found'}", passed)
    return passed


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


def main():
    """Main verification flow."""
    log_file = setup_logging('verify_github_app_setup')

    print_header("GitHub App Setup Verification")

    try:
        # Run all verifications
        results = {
            "gh_cli": verify_gh_cli(),
            "github_secrets": verify_github_secrets(),
            "env_shared": verify_env_shared(),
            "env_tier_agent": verify_env_tier_agent(),
            "docker_compose": verify_docker_compose(),
            "chit_manifest": verify_chit_manifest(),
        }

        # Summary
        print_header("Verification Summary")
        total = len(results)
        passed = sum(results.values())

        print(f"Total checks: {passed}/{total} passed")
        logging.info(f"Verification completed: {passed}/{total} checks passed")
        print()

        # Failure details (only print known check names, never values)
        known_checks = {"gh_cli", "github_secrets", "env_shared", "env_tier_agent", "docker_compose", "secrets_funnel", "chit_manifest"}
        failures = [k for k, v in results.items() if not v]
        if failures:
            print(f"{Colors.YELLOW}Failed checks:{Colors.RESET}")
            for check in failures:
                sanitized = check if check in known_checks else "unknown_check"
                print(f"  - {sanitized}")
            print()

            # Troubleshooting hints
            print(f"{Colors.BLUE}Troubleshooting:{Colors.RESET}")
            if "gh_cli" in failures:
                print("  • Install GitHub CLI: https://cli.github.com/")
                print("  • Authenticate: gh auth login")
            if "github_secrets" in failures:
                print("  • Add credentials to GitHub Secrets:")
                print("    https://github.com/organizations/POWERFULMOVES/PMOVES.AI/settings/secrets/actions")
            if "env_shared" in failures:
                print("  • Run: make github-app-setup")
                print("  • Or manually uncomment lines in pmoves/env.shared")
            if "env_tier_agent" in failures:
                print("  • Run: make secrets-funnel")
                print("  • This generates env.tier-agent from env.shared")
            if "docker_compose" in failures:
                print("  • Check docker-compose.yml has GH_APP_* env var references")
            if "chit_manifest" in failures:
                print("  • Verify pmoves/chit/secrets_manifest.yaml has gh_app entries")
            print()

        # Final result
        if passed == total:
            print(f"{Colors.GREEN}{Colors.BOLD}All checks passed! 🎉{Colors.RESET}")
            print("\nGitHub App integration is fully configured.")
            print("\nNext steps:")
            print("  • Start services: docker compose up -d archon botz-gateway")
            print("  • Test token minting: cd PMOVES-BoTZ && python features/github/mint_and_exec.py")
            logging.info("All verification checks passed")
            return 0
        else:
            print(f"{Colors.RED}{Colors.BOLD}Verification failed!{Colors.RESET}")
            print(f"\nPlease fix the {len(failures)} failed check(s) above.")
            logging.warning(f"Verification failed: {len(failures)} checks failed")
            return 1

    except Exception as e:
        logging.error(f"Verification failed with exception: {e}", exc_info=True)
        print_error(f"Unexpected error: {e}")
        print(f"  Full log: {log_file}")
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Verification cancelled by user{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"{Colors.RED}Unexpected error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
