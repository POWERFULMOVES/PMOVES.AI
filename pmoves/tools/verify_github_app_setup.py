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
Version: 1.0.0
"""
import json
import os
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


def run_command(cmd, check=True, capture_output=True):
    """Run a shell command and return output."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=capture_output,
        text=True,
        check=check
    )
    return result


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
    gh_app_keys = ['GH_APP_ID', 'GH_APP_SEC', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID']
    found_count = 0

    for key in gh_app_keys:
        try:
            result = run_command(f"gh secret list --repo POWERFULMOVES/PMOVES.AI | grep '^{key}'")
            if result.returncode == 0 and key in result.stdout:
                found_count += 1
        except:
            pass

    passed = found_count == 4
    print_check("GitHub Secrets", f"GitHub App credentials ({found_count}/4 found)", passed)
    return passed


def verify_env_shared():
    """Verify GitHub App credentials in env.shared (uncommented)."""
    repo_root = Path(__file__).parent.parent
    env_shared = repo_root / "pmoves" / "env.shared"

    if not env_shared.exists():
        print_check("env.shared", "File not found", False)
        return False

    with open(env_shared) as f:
        content = f.read()

    # Check for uncommented credentials (not starting with #)
    gh_app_keys = ['GH_APP_ID', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID', 'GH_APP_SEC']
    found_count = 0

    for key in gh_app_keys:
        # Look for uncommented lines (key=value, not #key=value)
        lines = content.split('\n')
        for line in lines:
            if line.strip().startswith(f'{key}='):
                found_count += 1
                break

    passed = found_count == 4
    print_check("env.shared", f"GitHub App credentials uncommented ({found_count}/4)", passed)
    return passed


def verify_env_tier_agent():
    """Verify GitHub App credentials in env.tier-agent."""
    repo_root = Path(__file__).parent.parent
    tier_agent = repo_root / "pmoves" / "env.tier-agent"

    if not tier_agent.exists():
        print_check("env.tier-agent", "File not found (run 'make secrets-funnel' first)", False)
        return False

    with open(tier_agent) as f:
        content = f.read()

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

    with open(manifest_file) as f:
        content = f.read()

    # Check for gh_app entries
    has_gh_app = 'gh_app' in content.lower()
    passed = has_gh_app

    print_check("CHIT Manifest", f"GitHub App entries {'present' if passed else 'NOT found'}", passed)
    return passed


def main():
    """Main verification flow."""
    print_header("GitHub App Setup Verification")

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
    print()

    # Failure details
    failures = [k for k, v in results.items() if not v]
    if failures:
        print(f"{Colors.YELLOW}Failed checks:{Colors.RESET}")
        for check in failures:
            print(f"  - {check}")
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
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}Verification failed!{Colors.RESET}")
        print(f"\nPlease fix the {len(failures)} failed check(s) above.")
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
