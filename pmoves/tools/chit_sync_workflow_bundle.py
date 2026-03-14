#!/usr/bin/env python3
"""
Sync GitHub App credentials from workflow-generated CHIT bundle to env.shared

This script decodes the CHIT bundle created by sync-secrets-local.yml workflow
and populates env.shared with the GitHub App credentials.

Usage:
    python tools/chit_sync_workflow_bundle.py

Returns:
    int: 0 on success, 1 on failure

Side effects:
    - Modifies pmoves/env.shared in place
    - Prints progress messages to stdout
    - Writes logs to ~/.pmoves/logs/chit_sync_workflow_bundle.log
"""
import json
import logging
import os
import sys
from pathlib import Path

# Add pmoves to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pmoves.chit import decode_secret_map


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
        ]
    )

    logging.info(f"=== Starting {script_name} ===")
    logging.info(f"Log file: {log_file}")
    return log_file


def main():
    """
    Sync GitHub App credentials from CHIT bundle to env.shared.

    Returns:
        int: 0 on success, 1 on failure
    """
    log_file = setup_logging('chit_sync_workflow_bundle')

    try:
        logging.info("Starting CHIT bundle sync for GitHub App credentials")

        # Paths
        repo_root = Path(__file__).parent.parent
        env_shared = repo_root / "pmoves" / "env.shared"

        # CHIT bundle location (cross-platform)
        if sys.platform == 'win32':
            chit_path = Path(os.environ.get('APPDATA',
                            Path.home() / 'AppData' / 'Roaming')) / 'pmoves' / 'chit' / 'env.cgp.json'
        else:
            chit_path = Path(os.environ.get('XDG_CONFIG_HOME',
                            str(Path.home() / '.config'))) / 'pmoves' / 'chit' / 'env.cgp.json'

        if not chit_path.exists():
            print(f"ERROR: CHIT bundle not found at {chit_path}")
            print("Please run the sync-secrets-local.yml workflow first.")
            logging.error(f"CHIT bundle not found at {chit_path}")
            return 1

        # Load and decode CHIT bundle
        print(f"Reading CHIT bundle from {chit_path}")
        logging.info(f"Reading CHIT bundle from {chit_path}")
        with open(chit_path) as f:
            cgp_data = json.load(f)

        secrets = decode_secret_map(cgp_data)
        print(f"Decoded {len(secrets)} secrets from CHIT bundle")
        logging.info(f"Decoded {len(secrets)} secrets from CHIT bundle")

        # Extract GitHub App credentials
        gh_app_keys = ['GH_APP_ID', 'GH_APP_CLIENT_ID', 'GH_APP_INSTALLATION_ID', 'GH_APP_SEC']
        gh_app_creds = {k: v for k, v in secrets.items() if k in gh_app_keys}

        if not gh_app_creds:
            print("ERROR: No GitHub App credentials found in CHIT bundle")
            logging.error("No GitHub App credentials found in CHIT bundle")
            return 1

        print(f"Found {len(gh_app_creds)} GitHub App credentials")
        logging.info(f"Found {len(gh_app_creds)} GitHub App credentials in CHIT bundle")

        # Read env.shared
        print(f"\nUpdating {env_shared}")
        logging.info(f"Updating {env_shared}")
        with open(env_shared) as f:
            env_lines = f.readlines()

        # Update GitHub App credentials
        updated_lines = []
        update_count = 0
        for line in env_lines:
            # Check if this is a GitHub App credential line
            is_gh_app_line = any(line.startswith(f'#{key}=') or line.startswith(f'{key}=')
                                 for key in gh_app_keys)

            if is_gh_app_line:
                # Find which key it is
                for key in gh_app_keys:
                    if line.startswith(f'#{key}=') or line.startswith(f'{key}='):
                        # Replace with uncommented credential
                        value = gh_app_creds.get(key, '')
                        # Format multi-line values (like PEM keys) properly
                        if '\n' in value:
                            # Properly quote multi-line PEM keys for shell parsing
                            # Use single quotes to preserve newlines, escape any existing single quotes
                            escaped_value = value.replace("'", "'\\''")
                            updated_lines.append(f"{key}='{escaped_value}'\n")
                        else:
                            updated_lines.append(f'{key}={value}\n')
                        print(f"  Updated {key}")
                        logging.info(f"Updated {key} in env.shared")
                        update_count += 1
                        break
            else:
                updated_lines.append(line)

        # Write back to env.shared with restricted permissions
        import stat
        with open(env_shared, 'w') as f:
            f.writelines(updated_lines)
        os.chmod(env_shared, stat.S_IRUSR | stat.S_IWUSR)

        print(f"\n✓ Successfully updated env.shared with {update_count} credentials")
        logging.info(f"Successfully updated env.shared with {update_count} credentials")
        return 0

    except Exception as e:
        logging.error(f"Failed to sync CHIT bundle: {e}", exc_info=True)
        print(f"ERROR: {e}")
        print(f"  Full log: {log_file}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
