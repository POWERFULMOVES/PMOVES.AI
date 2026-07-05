# Custom Plugin Audit Report (v2.1 readiness)

## Plugin: _model_config

### Manifest
- **WARN**: plugin.yaml missing (required for discovery; optional for private config-only plugins)

### Structure
- **PASS**: directory name valid: _model_config
- **PASS**: top-level layout matches standard
- **PASS**: no extensions/python directory

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **WARN**: LICENSE missing (required for Plugin Index; optional for local)
- **PASS**: not a git repo (manual install)

## Plugin: _oauth

### Manifest
- **WARN**: plugin.yaml missing (required for discovery; optional for private config-only plugins)

### Structure
- **PASS**: directory name valid: _oauth
- **PASS**: top-level layout matches standard
- **PASS**: no extensions/python directory

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **WARN**: LICENSE missing (required for Plugin Index; optional for local)
- **PASS**: not a git repo (manual install)

## Plugin: _office

### Manifest
- **WARN**: plugin.yaml missing (required for discovery; optional for private config-only plugins)

### Structure
- **PASS**: directory name valid: _office
- **PASS**: top-level layout matches standard
- **PASS**: no extensions/python directory

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **WARN**: LICENSE missing (required for Plugin Index; optional for local)
- **PASS**: not a git repo (manual install)

## Plugin: _whatsapp_integration

### Manifest
- **WARN**: plugin.yaml missing (required for discovery; optional for private config-only plugins)

### Structure
- **PASS**: directory name valid: _whatsapp_integration
- **PASS**: top-level layout matches standard
- **PASS**: no extensions/python directory

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **WARN**: LICENSE missing (required for Plugin Index; optional for local)
- **PASS**: not a git repo (manual install)

## Plugin: _whisper_stt

### Manifest
- **WARN**: plugin.yaml missing (required for discovery; optional for private config-only plugins)

### Structure
- **PASS**: directory name valid: _whisper_stt
- **PASS**: top-level layout matches standard
- **PASS**: no extensions/python directory

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **WARN**: LICENSE missing (required for Plugin Index; optional for local)
- **PASS**: not a git repo (manual install)

## Plugin: a0_agent_skills

### Manifest
- **PASS**: plugin.yaml valid YAML
- **PASS**: name: a0_agent_skills
- **PASS**: title: Agent Skills
- **PASS**: description: Production-grade engineering skills for Agent Zero. 21 skills covering the full SDLC (spec, plan, build, test, review, ship), 3 specialist agent profiles (code-reviewer, security-auditor, test-engineer), 7 slash commands, telemetry logging, and declarative routing via system prompt extension.
- **PASS**: version: 0.4.0
- **PASS**: settings_sections: ['agent']
- **PASS**: per_project_config: True
- **PASS**: per_agent_config: False
- **WARN**: always_enabled absent

### Structure
- **PASS**: directory name valid: a0_agent_skills
- **WARN**: unexpected top-level entries (may be legitimate): ['__pycache__', 'CHANGELOG.md']
- **PASS**: extension layout follows named hook point or _functions/.../start|end/

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **PASS**: LICENSE present
- **PASS**: plugin up to date with origin

## Plugin: a0_swarm

### Manifest
- **PASS**: plugin.yaml valid YAML
- **PASS**: name: a0_swarm
- **PASS**: title: A0 Swarm
- **PASS**: description: Spawn parallel subagents with a real-time monitoring panel.
- **PASS**: version: 1.3.0
- **PASS**: settings_sections: ['agent']
- **PASS**: per_project_config: False
- **PASS**: per_agent_config: False
- **PASS**: always_enabled: False

### Structure
- **PASS**: directory name valid: a0_swarm
- **WARN**: unexpected top-level entries (may be legitimate): ['__pycache__']
- **WARN**: unrecognized extension point dirs: ['extensions/python/__pycache__']

### Code/Security
- **WARN**: eval/exec found in webui/swarm-store.js
- **WARN**: eval/exec found in extensions/webui/send_message_before/_10_swarm_mentions.js

### License/Update
- **WARN**: LICENSE missing (required for Plugin Index; optional for local)
- **PASS**: plugin up to date with origin

## Plugin: channels_provider

### Manifest
- **PASS**: plugin.yaml valid YAML
- **PASS**: name: channels_provider
- **PASS**: title: Channels
- **PASS**: description: Unified messaging adapter for Telegram, Discord, and WhatsApp. Routes platform messages to Agent Zero and agent responses back to platforms.
- **PASS**: version: 0.1.0
- **PASS**: settings_sections: ['external']
- **PASS**: per_project_config: False
- **PASS**: per_agent_config: False
- **WARN**: always_enabled absent

### Structure
- **PASS**: directory name valid: channels_provider
- **PASS**: top-level layout matches standard
- **PASS**: extension layout follows named hook point or _functions/.../start|end/

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **PASS**: LICENSE present
- **PASS**: plugin up to date with origin

## Plugin: github

### Manifest
- **PASS**: plugin.yaml valid YAML
- **PASS**: name: github
- **PASS**: title: GitHub
- **PASS**: description: Reliable, skill-guided GitHub operations for Agent Zero via the gh CLI. Bundles tested command-template skills for opening PRs, triaging issues, reviewing PRs, searching, watching repos for new issues/PRs, and cutting releases with notes. Authenticates from an A0 Secret.
- **PASS**: version: 1.5.4
- **PASS**: settings_sections: ['agent']
- **PASS**: per_project_config: False
- **PASS**: per_agent_config: False
- **PASS**: always_enabled: False

### Structure
- **PASS**: directory name valid: github
- **WARN**: unexpected top-level entries (may be legitimate): ['__pycache__']
- **PASS**: extension layout follows named hook point or _functions/.../start|end/

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **PASS**: LICENSE present
- **WARN**: plugin update available: local f2703b1a vs remote 6b105090

## Plugin: google

### Manifest
- **PASS**: plugin.yaml valid YAML
- **PASS**: name: google
- **PASS**: title: Google Suite
- **PASS**: description: Unified Google integration — Gmail, Calendar, Drive, Contacts, Tasks, and Sheets with shared OAuth2 authentication.
- **PASS**: version: 1.1.0
- **PASS**: settings_sections: ['external']
- **PASS**: per_project_config: True
- **PASS**: per_agent_config: True
- **PASS**: always_enabled: False

### Structure
- **PASS**: directory name valid: google
- **WARN**: unexpected top-level entries (may be legitimate): ['initialize.py', 'install.sh', 'docs', 'data', '__pycache__', 'thumbnail.png', 'RELEASE.md']
- **PASS**: no extensions/python directory

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **PASS**: LICENSE present
- **PASS**: plugin up to date with origin

## Plugin: pmoves_launcher

### Manifest
- **PASS**: plugin.yaml valid YAML
- **PASS**: name: pmoves_launcher
- **PASS**: title: PMOVES Launcher
- **PASS**: description: Launch the PMOVES.AI fork from within Agent Zero. Provides an agent tool and a sidebar action that runs the PMOVES mini_cli bootstrap/profile_apply workflow against the active project.
- **PASS**: version: 1.0.0
- **PASS**: settings_sections: ['external']
- **PASS**: per_project_config: True
- **PASS**: per_agent_config: False
- **PASS**: always_enabled: False

### Structure
- **PASS**: directory name valid: pmoves_launcher
- **PASS**: top-level layout matches standard
- **PASS**: no extensions/python directory

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **WARN**: LICENSE missing (required for Plugin Index; optional for local)
- **PASS**: not a git repo (manual install)

## Plugin: stop_process

### Manifest
- **PASS**: plugin.yaml valid YAML
- **PASS**: name: stop_process
- **PASS**: title: Stop Process
- **PASS**: description: Adds a Stop button to the chat input actions bar that cancels the currently running agent process in the active session.
- **PASS**: version: 1.0.0
- **PASS**: settings_sections: []
- **PASS**: per_project_config: False
- **PASS**: per_agent_config: False
- **WARN**: always_enabled absent

### Structure
- **PASS**: directory name valid: stop_process
- **PASS**: top-level layout matches standard
- **PASS**: no extensions/python directory

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **PASS**: LICENSE present
- **PASS**: plugin up to date with origin

## Plugin: youtube_transcribe

### Manifest
- **PASS**: plugin.yaml valid YAML
- **PASS**: name: youtube_transcribe
- **PASS**: title: YouTube Transcriber
- **PASS**: description: Transcribe YouTube videos, playlists, and entire channels with adaptive rate-limiting to avoid YouTube throttling. AI-powered summaries, timestamped notes, visual context extraction, and resumable channel jobs.
- **PASS**: version: 1.0.0
- **PASS**: settings_sections: ['external']
- **PASS**: per_project_config: True
- **PASS**: per_agent_config: True
- **PASS**: always_enabled: False

### Structure
- **PASS**: directory name valid: youtube_transcribe
- **WARN**: unexpected top-level entries (may be legitimate): ['initialize.py', 'install.sh', 'docs', 'data', '__pycache__', 'RELEASE.md']
- **PASS**: no extensions/python directory

### Code/Security
- **PASS**: no obvious hardcoded secrets or eval/exec found

### License/Update
- **PASS**: LICENSE present
- **PASS**: plugin up to date with origin
