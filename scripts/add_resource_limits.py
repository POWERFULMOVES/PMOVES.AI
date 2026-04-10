#!/usr/bin/env python3
"""
PMOVES.AI Docker Compose Resource Limits Patcher
PMOVES-P2 Recommendation #3: Add Container Resource Limits

Usage:
  python3 scripts/add_resource_limits.py [--group GROUP]

Groups: infrastructure, agents, aiml, media, integration
If --group is omitted, all groups are applied.
"""

import sys
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

yaml = YAML()
yaml.preserve_quotes = True
yaml.width = 4096

TIERS = {
    'lightweight': {'cpus': '0.5', 'memory': '256M'},
    'standard':    {'cpus': '1.0', 'memory': '512M'},
    'heavy':       {'cpus': '2.0', 'memory': '2G'},
    'gpu':         {'cpus': '4.0', 'memory': '8G'},
    'database':    {'cpus': '2.0', 'memory': '4G'},
}

SERVICE_CLASS = {
    'nats':                    ('standard',    'infrastructure'),
    'nats-init':               ('lightweight', 'infrastructure'),
    'nats-echo-req':           ('lightweight', 'infrastructure'),
    'nats-echo-res':           ('lightweight', 'infrastructure'),
    'neo4j':                   ('database',    'infrastructure'),
    'qdrant':                  ('database',    'infrastructure'),
    'meilisearch':             ('database',    'infrastructure'),
    'minio':                   ('database',    'infrastructure'),
    'invidious-db':            ('database',    'infrastructure'),
    'supabase-db':             ('database',    'infrastructure'),
    'supabase-analytics':      ('database',    'infrastructure'),
    'tensorzero-clickhouse':   ('database',    'infrastructure'),
    'wger-db':                 ('database',    'infrastructure'),

    'agent-zero':              ('heavy',       'agents'),
    'archon':                  ('heavy',       'agents'),
    'gateway-agent':           ('standard',    'agents'),
    'mesh-agent':              ('standard',    'agents'),
    'a2ui-nats-bridge':        ('standard',    'agents'),
    'consciousness-service':   ('heavy',       'agents'),
    'evo-controller':          ('standard',    'agents'),
    'deepresearch':            ('heavy',       'agents'),

    'hi-rag-gateway':          ('heavy',       'aiml'),
    'hi-rag-gateway-v2':       ('heavy',       'aiml'),
    'hi-rag-gateway-gpu':      ('gpu',         'aiml'),
    'hi-rag-gateway-v2-gpu':   ('gpu',         'aiml'),
    'tensorzero-gateway':      ('heavy',       'aiml'),
    'tensorzero-ui':           ('standard',    'aiml'),
    'pmoves-ollama':           ('gpu',         'aiml'),
    'llama-throughput-lab':    ('gpu',         'aiml'),
    'gpu-orchestrator':        ('gpu',         'aiml'),
    'ffmpeg-whisper':          ('gpu',         'aiml'),
    'media-audio':             ('gpu',         'aiml'),
    'media-video':             ('gpu',         'aiml'),
    'langextract':             ('heavy',       'aiml'),
    'retrieval-eval':          ('heavy',       'aiml'),
    'model-registry':          ('standard',    'aiml'),
    'tokenism-simulator':      ('heavy',       'aiml'),
    'pdf-ingest':              ('standard',    'aiml'),

    'cast-tts-gateway':        ('standard',    'media'),
    'ultimate-tts-studio':     ('gpu',         'media'),
    'voice-relay':             ('lightweight', 'media'),
    'flute-gateway':           ('standard',    'media'),
    'transcribe-backend':      ('standard',    'media'),
    'invidious':               ('standard',    'media'),
    'invidious-companion':     ('standard',    'media'),
    'invidious-companion-proxy': ('lightweight','media'),
    'bgutil-pot-provider':     ('standard',    'media'),
    'grayjay-server':          ('standard',    'media'),
    'grayjay-plugin-host':     ('standard',    'media'),

    'botz-gateway':            ('standard',    'integration'),
    'cipher-api':              ('standard',    'integration'),
    'cloudflared':             ('lightweight', 'integration'),
    'comfy-watcher':           ('standard',    'integration'),
    'channel-monitor':         ('standard',    'integration'),
    'github-branch-cleanup':   ('lightweight', 'integration'),
    'github-branch-naming':    ('lightweight', 'integration'),
    'github-crossrepo-pr':     ('lightweight', 'integration'),
    'github-crossrepo-sync':   ('lightweight', 'integration'),
    'github-issue-triage':     ('lightweight', 'integration'),
    'github-runner-ctl':       ('lightweight', 'integration'),
    'jellyfin-bridge':         ('standard',    'integration'),
    'notebook-sync':           ('standard',    'integration'),
    'presign':                 ('lightweight', 'integration'),
    'publisher-discord':       ('standard',    'integration'),
    'render-webhook':          ('lightweight', 'integration'),
    'supabase-edge-functions': ('standard',    'integration'),
    'supabase-gotrue':         ('standard',    'integration'),
    'supabase-imgproxy':       ('lightweight', 'integration'),
    'supabase-kong':           ('lightweight', 'integration'),
    'supabase-meta':           ('standard',    'integration'),
    'supabase-pooler':         ('lightweight', 'integration'),
    'supabase-postgrest':      ('standard',    'integration'),
    'supabase-realtime':       ('standard',    'integration'),
    'supabase-storage':        ('standard',    'integration'),
    'supabase-studio':         ('standard',    'integration'),
    'supabase-vector':         ('standard',    'integration'),
    'pmoves-ui':               ('standard',    'integration'),
    'pmoves-yt':               ('standard',    'integration'),
    'wger':                    ('standard',    'integration'),
    'supaserch':               ('standard',    'integration'),
    'tokenism-ui':             ('standard',    'integration'),
    'extract-worker':          ('standard',    'integration'),
    'session-context-worker':  ('standard',    'integration'),
}


def ensure_deploy_limits(svc_data, tier_name, service_name):
    tier = TIERS[tier_name]
    target_cpu = tier['cpus']
    target_mem = tier['memory']

    if 'deploy' not in svc_data:
        svc_data['deploy'] = CommentedMap()
    deploy = svc_data['deploy']

    if 'resources' not in deploy:
        deploy['resources'] = CommentedMap()
    resources = deploy['resources']

    if 'limits' not in resources:
        resources['limits'] = CommentedMap()
    limits = resources['limits']

    current_cpu = str(limits.get('cpus', ''))
    current_mem = str(limits.get('memory', ''))

    needs_cpu = current_cpu != target_cpu
    needs_mem = current_mem != target_mem

    if needs_cpu:
        limits['cpus'] = target_cpu
    if needs_mem:
        limits['memory'] = target_mem

    changed = needs_cpu or needs_mem
    if changed:
        print(f'  {service_name}: SET cpu={target_cpu} mem={target_mem}')
    else:
        print(f'  {service_name}: SKIP (already cpu={current_cpu} mem={current_mem})')

    return changed


def main():
    group_filter = None
    if '--group' in sys.argv:
        idx = sys.argv.index('--group')
        if idx + 1 < len(sys.argv):
            group_filter = sys.argv[idx + 1]

    compose_path = Path('/a0/usr/workdir/PMOVES.AI/pmoves/docker-compose.yml')
    with open(compose_path, 'r') as f:
        data = yaml.load(f)

    services = data.get('services', {})
    modified = []
    skipped = []

    print(f'Scanning {len(services)} services (filter: {group_filter or "ALL"})...')
    print()

    for name in sorted(services.keys()):
        svc = services[name]
        if name not in SERVICE_CLASS:
            print(f'  UNCLASSIFIED: {name}')
            continue

        tier_name, commit_group = SERVICE_CLASS[name]
        if group_filter and commit_group != group_filter:
            continue

        changed = ensure_deploy_limits(svc, tier_name, name)
        if changed:
            modified.append((name, tier_name, commit_group))
        else:
            skipped.append(name)

    print()
    print(f'Modified: {len(modified)}  Skipped: {len(skipped)}')

    if modified:
        print(f'\nWriting to {compose_path}...')
        with open(compose_path, 'w') as f:
            yaml.dump(data, f)
        print('Written.')
    else:
        print('No changes needed.')


if __name__ == '__main__':
    main()
