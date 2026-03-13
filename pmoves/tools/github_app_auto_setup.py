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


def verify_gh_auth():
    """Verify GitHub CLI is authenticated."""
    print_step(1, "Verifying GitHub CLI authentication...")

    try:
        result = run_command("gh auth status")
        if result.returncode == 0:
            print_success("GitHub CLI authenticated")
            # Extract username
            if "Logged in to" in result.stdout:
                for line in result.stdout.split('\n'):
                    if "github.com" in line:
                        print(f"  {line.strip()}")
            return True
        else:
            print_error("GitHub CLI not authenticated")
            print("  Run: gh auth login")
            return False
    except Exception as e:
        print_error(f"Failed to verify GitHub CLI: {e}")
        return False


def get_github_secrets():
    """Fetch GitHub App credentials from GitHub Secrets."""
    print_step(2, "Fetching GitHub App credentials from GitHub Secrets...")

    gh_app_keys = ['GH_APP_ID', 'GH_APP_SEC', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID']
    credentials = {}

    print("  Checking GitHub Secrets for POWERFULMOVES/PMOVES.AI:")
    for key in gh_app_keys:
        try:
            # Use gh secret list to check if secret exists
            result = run_command(f"gh secret list --repo POWERFULMOVES/PMOVES.AI | grep '^{key}'")
            if result.returncode == 0 and key in result.stdout:
                credentials[key] = "PRESENT_IN_GH_SECRETS"
                print_success(f"  {key}: Found in GitHub Secrets")
            else:
                print_warning(f"  {key}: Not found in GitHub Secrets")
        except:
            print_warning(f"  {key}: Could not verify")

    if len(credentials) == 4:
        print_success("All 4 GitHub App credentials found in GitHub Secrets")
        return credentials
    else:
        print_error(f"Only {len(credentials)}/4 credentials found in GitHub Secrets")
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
                print_success(f"  Uncommented: {updated_line.strip()}")
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
                print(f"  Error: {result.stderr}")
            return False
    except Exception as e:
        print_error(f"Failed to run secrets-funnel: {e}")
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
    """Main execution flow."""
    print_header("GitHub App Credential Auto-Setup")

    # Verify prerequisites
    if not verify_gh_auth():
        print_error("\nPlease install and authenticate GitHub CLI first:")
        print("  1. Install: https://cli.github.com/")
        print("  2. Authenticate: gh auth login")
        return 1

    # Check GitHub Secrets
    credentials = get_github_secrets()
    if credentials is None:
        print_error("\nGitHub App credentials not found in GitHub Secrets")
        print("\nTo add them:")
        print("  1. Visit: https://github.com/organizations/POWERFULMOVES/settings/apps")
        print("  2. Select the PMOVES.AI GitHub App")
        print("  3. Copy credentials to GitHub Secrets")
        return 1

    # Update env.shared
    if not update_env_shared():
        print_error("Failed to update env.shared")
        return 1

    # Run secrets-funnel
    if not run_secrets_funnel():
        print_error("Failed to run secrets-funnel")
        return 1

    # Verify tier files
    if not verify_tier_files():
        print_error("Failed to verify tier files")
        return 1

    # Success!
    print_header("Setup Complete! 🎉")
    print_success("GitHub App credentials successfully populated")
    print("\nNext steps:")
    print("  1. Start services: docker compose up -d archon botz-gateway")
    print("  2. Verify credentials: docker compose logs archon | grep GH_APP")
    print("  3. Test token minting: cd PMOVES-BoTZ && python features/github/mint_and_exec.py")
    print()

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print_warning("\nSetup cancelled by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
