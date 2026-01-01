#!/usr/bin/env python3
"""
FastAPI @app.on_event → lifespan migration script.

Migrates deprecated FastAPI startup/shutdown events to modern lifespan context manager.
"""

import os
import re
import sys
from pathlib import Path

# Files to migrate - all services with @app.on_event
FILES_TO_MIGRATE = [
    "pmoves/services/hi-rag-gateway-v2/app.py",
    "pmoves/services/pdf-ingest/app.py",
    "pmoves/services/supaserch/app.py",
    "pmoves/services/gateway-agent/app.py",
    "pmoves/services/jellyfin-bridge/main.py",
    "pmoves/services/messaging-gateway/main.py",
    "pmoves/services/notebook-sync/sync.py",
    "pmoves/services/publisher-discord/main.py",
    "pmoves/services/session-context-worker/main.py",
    "pmoves/services/mcp_youtube_adapter.py",
    "pmoves/services/agent-zero/main.py",
    "pmoves/services/evo-controller/app.py",
    "pmoves/services/gateway/gateway/main.py",
    "pmoves/services/channel-monitor/channel_monitor/main.py",
    "pmoves/services/pmoves-yt/yt.py",
]

def migrate_file(filepath: Path) -> bool:
    """Migrate a single file from @app.on_event to lifespan."""
    if not filepath.exists():
        print(f"  ⚠️  File not found: {filepath}")
        return False

    content = filepath.read_text()
    original = content

    # Check if already migrated (has lifespan=)
    if re.search(r'app\s*=\s*FastAPI\([^)]*lifespan\s*=', content):
        print(f"  ✓ Already migrated: {filepath}")
        return True

    # Check if has asynccontextmanager import
    if "from contextlib import asynccontextmanager" not in content:
        if "import contextlib" in content:
            content = re.sub(
                r'import contextlib',
                'import contextlib\nfrom contextlib import asynccontextmanager',
                content,
                count=1
            )
        elif "from fastapi import" in content:
            # Add after fastapi import
            content = re.sub(
                r'(from fastapi import [^\n]+)',
                r'\1\nfrom contextlib import asynccontextmanager',
                content,
                count=1
            )

    # Extract startup and shutdown handlers
    startup_match = re.search(
        r'@app\.on_event\("startup"\)\s*\n\s*async def \w+\([^)]*\):\s*\n(.*?)(?=\n@app\.on_event\("shutdown"\))',
        content,
        re.MULTILINE | re.DOTALL
    )
    shutdown_match = re.search(
        r'@app\.on_event\("shutdown"\)\s*\n\s*async def \w+\([^)]*\):\s*\n(.*?)(?=\n@app\.get\(|\n\nclass |\n@app\.post\(|\nclass |^app = |\ndef [^_]|\Z)',
        content,
        re.MULTILINE | re.DOTALL
    )

    if not startup_match:
        # Try alternate pattern (no shutdown following startup)
        startup_match = re.search(
            r'@app\.on_event\("startup"\)\s*\n\s*async def \w+\([^)]*\):\s*\n(.*?)(?=\n@app\.on_event\("shutdown"\)|\n@app\.get\(|\nclass |^app = )',
            content,
            re.MULTILINE | re.DOTALL
        )

    if not startup_match or not shutdown_match:
        print(f"  ⚠️  Could not find startup/shutdown handlers: {filepath}")
        return False

    startup_body = startup_match.group(1)
    shutdown_body = shutdown_match.group(1)

    # Build lifespan function
    lifespan_func = '''@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
''' + startup_body.strip() + '''
    yield
    # Shutdown
''' + shutdown_body.strip()

    # Insert lifespan before app = FastAPI
    app_match = re.search(r'\napp = FastAPI\(', content)
    if not app_match:
        print(f"  ⚠️  Could not find FastAPI app definition: {filepath}")
        return False

    insert_pos = app_match.start()
    content = content[:insert_pos] + '\n' + lifespan_func + '\n' + content[insert_pos:]

    # Update FastAPI app to include lifespan (handle both empty and non-empty cases)
    if 'app = FastAPI()' in content:
        # Empty FastAPI() case - no comma needed
        content = re.sub(
            r'app = FastAPI\(\)',
            'app = FastAPI(lifespan=lifespan)',
            content,
            count=1
        )
    else:
        # FastAPI with existing arguments - add comma
        content = re.sub(
            r'(app = FastAPI\([^)]*)(\))',
            r'\1, lifespan=lifespan\2',
            content,
            count=1
        )

    # Remove old @app.on_event decorators and handlers
    content = re.sub(
        r'@app\.on_event\("startup"\)\s*\n\s*async def \w+\([^)]*\):.*?(?=\n@app\.on_event\("shutdown"\))',
        '',
        content,
        flags=re.DOTALL | re.MULTILINE
    )
    content = re.sub(
        r'@app\.on_event\("shutdown"\)\s*\n\s*async def \w+\([^)]*\):.*?(?=\n@app\.get\(|\n@app\.post\(|\nclass |^app = |\ndef [^_]|\Z)',
        '',
        content,
        flags=re.DOTALL | re.MULTILINE
    )

    if content != original:
        filepath.write_text(content)
        print(f"  ✓ Migrated: {filepath}")
        return True
    else:
        print(f"  - No changes: {filepath}")
        return False

def main():
    # Derive root from script location for portability
    script_path = Path(__file__).resolve()
    # Script is at .claude/scripts/migrate_lifespan.py, so root is 2 levels up
    root = script_path.parents[1]
    if not (root / "pmoves").exists():
        # Fallback to current directory if structure doesn't match
        root = Path.cwd()
    print("🔄 Migrating FastAPI @app.on_event to lifespan pattern...")

    migrated = 0
    for relpath in FILES_TO_MIGRATE:
        filepath = root / relpath
        print(f"\n{relpath}")
        if migrate_file(filepath):
            migrated += 1

    print(f"\n✅ Migrated {migrated}/{len(FILES_TO_MIGRATE)} files")
    return 0

if __name__ == "__main__":
    sys.exit(main())
