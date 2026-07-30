#!/usr/bin/env python3
"""
Automated GitHub App Webhook Secret Configuration

Generates a cryptographically secure webhook secret locally and updates
env.shared, then runs secrets-funnel to propagate to tier files.

PREREQUISITES:
  - make (for secrets-funnel target)
  - PyJWT package (for GitHub App JWT authentication)
  - requests package (for GitHub API calls)

USAGE:
    # Generate webhook secret only (default)
    python tools/github_webhook_auto_config.py

    # Generate secret AND configure GitHub webhook via API
    python tools/github_webhook_auto_config.py --configure-github

    # Configure with custom webhook URL
    python tools/github_webhook_auto_config.py --configure-github --webhook-url https://your-domain.com/webhook/github

    # Skip secrets-funnel step
    python tools/github_webhook_auto_config.py --skip-funnel

FLOW:
  1. Generates cryptographically secure webhook secret (40 bytes)
  2. Updates env.shared with GH_WEBHOOK_SECRET
  3. Runs secrets-funnel to propagate to tier files
  4. Verifies secret in env.tier-worker (for n8n)
  5. [Optional] Configures GitHub App webhook via API

Author: PMOVES.AI Automation
Version: 2.0.0
"""
__version__ = "2.0.0"

import argparse
import hashlib
import hmac
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import jwt
    import requests
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("\nInstall with: pip install PyJWT requests")
    sys.exit(1)

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
    print(f"{Colors.GREEN}[OK] {text}{Colors.RESET}")


def print_warning(text):
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.RESET}")


def print_error(text):
    """Print error message."""
    print(f"{Colors.RED}[ERROR] {text}{Colors.RESET}")


def run_command(cmd, check=False, capture_output=True, timeout=60):
    """
    Run a shell command with timeout.

    Args:
        cmd: Command string to execute
        check: Raise CalledProcessError on non-zero exit (default: False)
        capture_output: Capture stdout/stderr (default: True)
        timeout: Maximum seconds to wait (default: 60)

    Returns:
        subprocess.CompletedProcess
    """
    try:
        # Use encoding='utf-8' and errors='replace' to handle Windows encoding issues
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture_output,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=check,
            timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired:
        print_error(f"Command timed out after {timeout}s: {cmd[:50]}...")
        raise


def verify_webhook_signature(payload_body, signature_header, secret):
    """Verify GitHub webhook HMAC-SHA256 signature.

    Implements the verification algorithm specified by GitHub:
    https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries

    Args:
        payload_body: Raw request body bytes
        signature_header: Value of x-hub-signature-256 header
        secret: Webhook secret string

    Returns:
        bool: True if signature is valid, False otherwise
    """
    if not signature_header:
        print_warning("No x-hub-signature-256 header present")
        return False

    if not signature_header.startswith("sha256="):
        print_warning("Signature header does not start with 'sha256='")
        return False

    expected_signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        msg=payload_body if isinstance(payload_body, bytes) else payload_body.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


def generate_webhook_secret():
    """Generate a cryptographically secure webhook secret."""
    print_step(1, "Generating webhook secret...")

    # Generate 40 random bytes (320 bits) and encode as URL-safe base64
    # This results in ~53 characters, sufficient for HMAC-SHA256
    webhook_secret = secrets.token_urlsafe(40)

    print_success(f"Generated webhook secret ({len(webhook_secret)} chars)")
    print("  Secret stored in env.shared (not displayed for security)")
    return webhook_secret


def update_env_shared(webhook_secret):
    """Update env.shared with the webhook secret."""
    print_step(2, "Updating env.shared with GH_WEBHOOK_SECRET...")

    # Script is in pmoves/tools/, parent should be pmoves/
    repo_root = Path(__file__).parent.parent.parent
    env_shared = repo_root / "pmoves" / "env.shared"

    if not env_shared.exists():
        print_error(f"env.shared not found at {env_shared}")
        return False

    # Read env.shared
    with open(env_shared) as f:
        lines = f.readlines()

    # Find and update GH_WEBHOOK_SECRET line
    updated = False
    output_lines = []

    for line in lines:
        if line.strip().startswith('GH_WEBHOOK_SECRET='):
            # Replace the line with the new secret
            output_lines.append(f'GH_WEBHOOK_SECRET={webhook_secret}\n')
            updated = True
            print_success("Updated GH_WEBHOOK_SECRET in env.shared")
        else:
            output_lines.append(line)

    if not updated:
        # Append to end of file if not found
        output_lines.append('\n# GitHub App Webhook Secret - Auto-generated\n')
        output_lines.append(f'GH_WEBHOOK_SECRET={webhook_secret}\n')
        print_success("Added GH_WEBHOOK_SECRET to env.shared")

    # Write back to env.shared
    with open(env_shared, 'w') as f:
        f.writelines(output_lines)

    return True


def run_secrets_funnel(skip=False, timeout=300):
    """Run make secrets-funnel to generate tier files.

    Args:
        skip: If True, skip the secrets-funnel step (for manual execution)
        timeout: Maximum seconds to wait (default: 300)
    """
    if skip:
        print_warning("Skipping secrets-funnel step (--skip-funnel specified)")
        print("\n  To manually propagate the secret, run:")
        print("  cd pmoves && make secrets-funnel")
        return True

    print_step(3, "Running secrets-funnel to propagate to tier files...")

    # Script is in pmoves/tools/, parent.parent should be repo root, pmoves is subdir
    repo_root = Path(__file__).parent.parent.parent
    pmoves_dir = repo_root / "pmoves"

    # Check if make is available
    make_check = run_command("make --version", capture_output=True, timeout=10)
    if make_check.returncode != 0:
        print_warning("make not found - skipping secrets-funnel")
        print("  To manually propagate the secret, run:")
        print("  cd pmoves && make secrets-funnel")
        return True  # Not a fatal error

    # Change to pmoves directory and run secrets-funnel
    original_dir = os.getcwd()
    try:
        os.chdir(pmoves_dir)
        result = run_command("make secrets-funnel", timeout=timeout)
        if result.returncode == 0:
            print_success("secrets-funnel completed successfully")
            # Show summary
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if 'env.tier' in line or 'entries' in line or 'Generated' in line or line.strip():
                        print(f"  {line}")
            return True
        else:
            print_warning("secrets-funnel returned non-zero exit code")
            if result.stderr:
                print(f"  Error output: {result.stderr[:200]}")
            print("  You can run it manually later: cd pmoves && make secrets-funnel")
            return True  # Not a fatal error - env.shared was updated
    except subprocess.TimeoutExpired:
        print_warning(f"secrets-funnel timed out after {timeout}s")
        print("  env.shared was updated successfully")
        print("  You can run secrets-funnel manually later: cd pmoves && make secrets-funnel")
        return True  # Not a fatal error - env.shared was updated
    except Exception as e:
        print_warning(f"Failed to run secrets-funnel: {e}")
        print("  env.shared was updated successfully")
        print("  You can run secrets-funnel manually later: cd pmoves && make secrets-funnel")
        return True  # Not a fatal error - env.shared was updated
    finally:
        os.chdir(original_dir)


def verify_tier_files():
    """Verify GH_WEBHOOK_SECRET in env.tier-worker."""
    print_step(4, "Verifying GH_WEBHOOK_SECRET in env.tier-worker...")

    repo_root = Path(__file__).parent.parent.parent
    tier_worker = repo_root / "pmoves" / "env.tier-worker"

    if not tier_worker.exists():
        print_warning("env.tier-worker not found (may not be generated yet)")
        return True  # Not a failure - tier-worker might not exist

    with open(tier_worker) as f:
        content = f.read()

    if 'GH_WEBHOOK_SECRET=' in content and 'changeme' not in content.lower():
        # Extract the value (partial for display)
        for line in content.split('\n'):
            if 'GH_WEBHOOK_SECRET=' in line:
                parts = line.split('=', 1)
                if len(parts) > 1:
                    value = parts[1].strip()
                    if value and value != 'changeme-generate-in-github-app-settings':
                        print_success("GH_WEBHOOK_SECRET found in env.tier-worker (valid)")
                        return True

    print_warning("GH_WEBHOOK_SECRET not properly set in env.tier-worker")
    return False


def display_manual_instructions():
    """Display manual configuration steps for GitHub.com."""
    print_step(5, "Manual configuration steps for GitHub.com...")

    print("\n" + "="*70)
    print("MANUAL GITHUB.COM CONFIGURATION REQUIRED")
    print("="*70)
    print("\nThe webhook secret has been generated locally and added to env.shared.")
    print("You MUST also configure this secret in GitHub App Settings:\n")

    print("1. Visit GitHub App Settings:")
    print("   https://github.com/organizations/POWERFULMOVES/settings/apps/PMOVES.AI/webhooks")

    print("\n2. Under 'Webhook', set:")
    print("   - Active: [CHECKED]")
    print("   - URL: https://<your-n8n-public-domain>/webhook/github")
    print("   - Content type: application/json")
    print("   - Secret: [Paste the secret below]")

    print("\n3. Subscribe to webhook events (if not already done):")
    events = [
        "push", "pull_request", "pull_request_review", "issues", "issue_comment",
        "release", "create", "workflow_run", "workflow_job", "check_run",
        "repository", "delete"
    ]
    print("   " + ", ".join(events))

    print("\n4. Click 'Save changes'")

    print("\n" + "="*70)
    print("\nNext steps:")
    print("  1. Restart n8n: docker compose -f docker-compose.n8n.yml restart n8n")
    print("  2. Test webhook: Trigger a GitHub event (push, PR, etc.)")
    print("  3. Monitor n8n logs: docker logs pmoves-n8n --tail 50 -f")
    print()


def load_env_file(env_path):
    """Load environment variables from a file.

    Args:
        env_path: Path to the environment file

    Returns:
        dict: Environment variables as key-value pairs
    """
    env_vars = {}
    if not env_path.exists():
        return env_vars

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip()

                # Special handling for GH_APP_SEC which has complex escaping
                # Format in file: GH_APP_SEC="\"-----BEGIN...\\n...\""
                if k == 'GH_APP_SEC' and v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]  # Remove outer quotes
                    # Remove escaped quotes at the boundaries
                    if v.startswith('\\"'):
                        v = v[2:]
                    if v.endswith('\\"'):
                        v = v[:-2]
                    # Handle any remaining leading/trailing quotes
                    v = v.strip('"')
                    # Handle escaped newlines
                    if '\\n' in v:
                        v = v.replace('\\\\n', '\n')
                        v = v.replace('\\n', '\n')
                    env_vars[k] = v
                    continue

                # Standard quote handling for other variables
                if v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                    # Handle escaped quotes at start/end
                    if v.startswith('\\"'):
                        v = v[1:]
                    if v.endswith('\\"'):
                        v = v[:-1]
                    # Handle trailing backslash
                    if v.endswith('\\'):
                        v = v[:-1]
                    # Handle escaped newlines and backslashes
                    if '\\n' in v:
                        v = v.replace('\\\\n', '\n')
                        v = v.replace('\\n', '\n')
                    if '\\r' in v:
                        v = v.replace('\\\\r', '\r')
                        v = v.replace('\\r', '\r')
                    if '\\t' in v:
                        v = v.replace('\\\\t', '\t')
                        v = v.replace('\\t', '\t')
                    if '\\"' in v:
                        v = v.replace('\\"', '"')
                elif v.startswith("'") and v.endswith("'"):
                    v = v[1:-1]
                    if v.endswith('\\'):
                        v = v[:-1]
                env_vars[k] = v

    return env_vars


def generate_github_jwt(app_id, app_secret):
    """Generate a JWT for GitHub App authentication.

    Args:
        app_id: GitHub App ID
        app_secret: GitHub App PEM private key (with newlines preserved)

    Returns:
        str: JWT token for GitHub App authentication
    """
    now = int(time.time())

    # GitHub requires: exp - iat <= 600 seconds (10 minutes max JWT lifetime)
    payload = {
        "iat": now - 30,  # issued 30 seconds ago for clock skew
        "exp": now + 570,  # expires 9.5 minutes from now (total lifetime < 10 min)
        "iss": str(app_id),
    }

    jwt_token = jwt.encode(payload, app_secret, algorithm="RS256")
    return jwt_token


def configure_github_webhook(webhook_url, webhook_secret):
    """Configure GitHub App webhook via GitHub API.

    Args:
        webhook_url: The public URL where GitHub will send webhooks
        webhook_secret: The webhook secret for signature verification

    Returns:
        tuple: (success: bool, message: str, response_data: dict)
    """
    print_step(5, "Configuring GitHub App webhook via API...")

    repo_root = Path(__file__).parent.parent.parent
    env_agent = repo_root / "pmoves" / "env.tier-agent"

    # Load GitHub App credentials from env.tier-agent
    if not env_agent.exists():
        return False, "env.tier-agent not found - GitHub App credentials unavailable", {}

    env_vars = load_env_file(env_agent)

    app_id = env_vars.get("GH_APP_ID")
    app_secret = env_vars.get("GH_APP_SEC")
    installation_id = env_vars.get("GH_APP_INSTALLATION_ID")

    if not app_id or not app_secret:
        return False, "GH_APP_ID or GH_APP_SEC not found in env.tier-agent", {}

    print(f"  Using GitHub App ID: {app_id}")
    print(f"  Installation ID: {installation_id}")

    # Generate JWT for GitHub App authentication
    try:
        jwt_token = generate_github_jwt(app_id, app_secret)
        print_success("JWT token generated successfully")
    except Exception as e:
        return False, f"Failed to generate JWT: {e}", {}

    # Prepare API request
    api_url = "https://api.github.com/app"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    payload = {
        "hook_attributes": {
            "active": True,
            "url": webhook_url,
            "insecure_ssl": False  # Require valid SSL
        },
        "events": [
            "push",
            "pull_request",
            "pull_request_review",
            "issues",
            "issue_comment",
            "release",
            "create",
            "workflow_run",
            "workflow_job",
            "check_run",
            "repository",
            "delete"
        ]
    }

    # If webhook secret is provided, add it (note: GitHub API may not accept this in all cases)
    # The secret typically needs to be set manually in GitHub App Settings for security reasons
    if webhook_secret:
        payload["hook_attributes"]["secret"] = webhook_secret

    print(f"  Webhook URL: {webhook_url}")
    print(f"  Events: {len(payload['events'])} event types")

    # Make API request
    try:
        response = requests.patch(api_url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            response_data = response.json()
            webhook_config = response_data.get("hook_attributes", {})

            print_success("GitHub webhook configured successfully via API")
            print(f"  Webhook URL: {webhook_config.get('url', 'N/A')}")
            print(f"  Active: {webhook_config.get('active', False)}")

            # Check if secret was set
            if webhook_config.get("secret"):
                print_success("  Webhook secret set via API")
            else:
                print_warning("  Webhook secret NOT set via API (GitHub API limitation)")
                print_warning("  You MUST manually set the secret in GitHub App Settings")

            return True, "Webhook configured successfully", response_data

        elif response.status_code == 401:
            return False, "Authentication failed - Check GitHub App credentials", {}
        elif response.status_code == 403:
            return False, "Permission denied - GitHub App lacks required permissions", {}
        elif response.status_code == 404:
            return False, "GitHub App not found - Check GH_APP_ID", {}
        else:
            error_msg = response.json().get("message", "Unknown error") if response.headers.get("content-type", "").startswith("application/json") else response.text
            return False, f"GitHub API error ({response.status_code}): {error_msg}", {}

    except requests.exceptions.Timeout:
        return False, "Request timed out - GitHub API may be slow", {}
    except requests.exceptions.RequestException as e:
        return False, f"Network error: {e}", {}
    except Exception as e:
        return False, f"Unexpected error: {e}", {}


def display_webhook_instructions(webhook_url):
    """Display instructions for manual webhook configuration if API fails.

    Args:
        webhook_url: The webhook URL to configure
    """
    print("\n" + "="*70)
    print("MANUAL WEBHOOK CONFIGURATION REQUIRED")
    print("="*70)
    print("\nGitHub API was unable to set the webhook secret automatically.")
    print("Please configure the webhook manually in GitHub App Settings:\n")

    print("1. Visit GitHub App Settings:")
    print("   https://github.com/organizations/POWERFULMOVES/settings/apps/PMOVES.AI/webhooks")

    print("\n2. Under 'Webhook', configure:")
    print("   - Active: [CHECKED]")
    print(f"   - URL: {webhook_url}")
    print("   - Content type: application/json")
    print("   - Secret: [retrieve from env.shared GH_WEBHOOK_SECRET]")

    print("\n3. Ensure these events are subscribed:")
    events = [
        "push", "pull_request", "pull_request_review", "issues", "issue_comment",
        "release", "create", "workflow_run", "workflow_job", "check_run",
        "repository", "delete"
    ]
    print("   " + ", ".join(events))

    print("\n4. Click 'Save changes'")
    print("\n" + "="*70)


def main():
    """Main execution flow."""
    parser = argparse.ArgumentParser(
        description="Automated GitHub App Webhook Secret Configuration"
    )
    parser.add_argument(
        "--configure-github",
        action="store_true",
        help="Configure GitHub App webhook via API after generating secret"
    )
    parser.add_argument(
        "--webhook-url",
        default=None,
        help="Public webhook URL (default: https://localhost/webhook/github)"
    )
    parser.add_argument(
        "--skip-funnel",
        action="store_true",
        help="Skip secrets-funnel step"
    )
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Output result as JSON for machine parsing"
    )

    args = parser.parse_args()

    # Set default webhook URL if not provided
    webhook_url = args.webhook_url or "https://localhost/webhook/github"

    # For JSON output mode, suppress color codes
    if args.output_json:
        class Colors:
            GREEN = ''
            YELLOW = ''
            RED = ''
            BLUE = ''
            RESET = ''
            BOLD = ''

        def print_header(text):
            pass  # Suppress headers in JSON mode

        def print_step(step_num, text):
            pass  # Suppress steps in JSON mode

        def print_success(text):
            pass  # Suppress success in JSON mode

        def print_warning(text):
            pass  # Suppress warnings in JSON mode

        def print_error(text):
            pass  # Suppress errors in JSON mode
    else:
        print_header("GitHub App Webhook Secret Auto-Configuration")

    env_shared_backup = None
    skip_funnel = args.skip_funnel

    result = {
        "success": False,
        "webhook_secret_set": False,
        "webhook_url": webhook_url,
        "github_configured": False,
        "message": "",
        "error": None
    }

    try:
        # Generate webhook secret
        webhook_secret = generate_webhook_secret()

        # Backup env.shared before modification
        repo_root = Path(__file__).parent.parent.parent
        env_shared = repo_root / "pmoves" / "env.shared"

        if env_shared.exists():
            env_shared_backup = env_shared.with_suffix('.bak')
            shutil.copy(env_shared, env_shared_backup)
            print(f"  Backed up env.shared to {env_shared_backup.name}")

        # Update env.shared
        if not update_env_shared(webhook_secret):
            print_error("Failed to update env.shared")
            if env_shared_backup and env_shared_backup.exists():
                shutil.copy(env_shared_backup, env_shared)
                print_success("Restored env.shared from backup")
            return 1

        # Run secrets-funnel (non-fatal - continues even if it fails)
        run_secrets_funnel(skip=skip_funnel)

        # Verify tier files
        verify_tier_files()

        # Success! Clean up backup
        if env_shared_backup and env_shared_backup.exists():
            env_shared_backup.unlink()
            print_success("Cleaned up backup file")

        # Never include the secret in result output - stored in env.shared
        result["webhook_secret_set"] = True
        result["success"] = True
        result["message"] = "Webhook secret generated and added to env.shared"

        # Configure GitHub webhook if requested
        if args.configure_github:
            github_success, message, response_data = configure_github_webhook(webhook_url, webhook_secret)
            result["github_configured"] = github_success
            result["github_message"] = message

            if not github_success:
                result["error"] = message
                print_warning(f"GitHub API configuration failed: {message}")
                display_webhook_instructions(webhook_url)
            else:
                result["message"] += " and GitHub webhook configured"
        else:
            # Display manual instructions
            display_manual_instructions()

        if args.output_json:
            # Output JSON result for machine parsing
            json.dump(result, sys.stdout, indent=2)
            print()  # Add newline
        else:
            print_header("Configuration Complete!")
            print_success("Webhook secret generated and added to env.shared")
            print("\nSecret stored in env.shared (retrieve with: grep GH_WEBHOOK_SECRET pmoves/env.shared)")
            if args.configure_github:
                if result["github_configured"]:
                    print_success("GitHub webhook configured successfully via API")
                else:
                    print_warning("GitHub webhook configuration via API failed")

        return 0 if result["success"] and (not args.configure_github or result["github_configured"]) else 1

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        result["error"] = error_msg

        if not args.output_json:
            print_error(error_msg)
            import traceback
            traceback.print_exc()

        # Rollback on exception
        if env_shared_backup and env_shared_backup.exists():
            repo_root = Path(__file__).parent.parent.parent
            env_shared = repo_root / "pmoves" / "env.shared"
            shutil.copy(env_shared_backup, env_shared)
            if not args.output_json:
                print_success("Restored env.shared from backup after error")

        if args.output_json:
            json.dump(result, sys.stdout, indent=2)
            print()

        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print_warning("\nConfiguration cancelled by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
