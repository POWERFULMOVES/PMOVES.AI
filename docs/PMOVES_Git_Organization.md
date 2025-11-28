# PMOVES Git Organization & Infrastructure Guide

This document provides a comprehensive guide to PMOVES.AI's GitHub organization, infrastructure setup, and related resources.

## Table of Contents
- [GitHub Actions Self-Hosted Runner Setup](#github-actions-self-hosted-runner-setup)
- [GitHub Documentation Resources](#github-documentation-resources)
- [PMOVES Project Repositories](#pmoves-project-repositories)
- [Infrastructure & Deployment](#infrastructure--deployment)
- [Video Resources & Tutorials](#video-resources--tutorials)
- [Team & Collaboration](#team--collaboration)

---

## GitHub Actions Self-Hosted Runner Setup

### Prerequisites
- Linux x64 environment
- Appropriate permissions to install and configure runners

### Installation Steps

1. **Create a folder for the runner**
   ```bash
   mkdir actions-runner && cd actions-runner
   ```

2. **Download the latest runner package**
   ```bash
   curl -o actions-runner-linux-x64-2.329.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.329.0/actions-runner-linux-x64-2.329.0.tar.gz
   ```

3. **Optional: Validate the hash**
   ```bash
   echo "194f1e1e4bd02f80b7e9633fc546084d8d4e19f3928a324d512ea53430102e1d  actions-runner-linux-x64-2.329.0.tar.gz" | shasum -a 256 -c
   ```

4. **Extract the installer**
   ```bash
   tar xzf ./actions-runner-linux-x64-2.329.0.tar.gz
   ```

### Configuration

1. **Create the runner and start the configuration experience**
   ```bash
   ./config.sh --url https://github.com/POWERFULMOVES/PMOVES.AI --token <RUNNER_REGISTRATION_TOKEN>
   ```
   Obtain a one-time registration token for your runner from the GitHub UI (Settings → Actions → Runners). Never commit real tokens to the repository or documentation.

2. **Run the runner**
   ```bash
   ./run.sh
   ```

### Using Your Self-Hosted Runner

Add this YAML to your workflow file for each job:

```yaml
runs-on: self-hosted
```

---

## GitHub Documentation Resources

### Actions & Runners
- [Self-hosted runners overview](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners)
- [Self-hosted runners concepts](https://docs.github.com/en/actions/concepts/runners/self-hosted-runners)
- [Private networking for runners](https://docs.github.com/en/actions/concepts/runners/private-networking)
- [Runner groups](https://docs.github.com/en/actions/concepts/runners/runner-groups)
- [Actions Runner Controller](https://docs.github.com/en/actions/concepts/runners/actions-runner-controller)

### Workflows & Automation
- [Using workflow templates](https://docs.github.com/en/actions/how-tos/write-workflows/use-workflow-templates)
- [Monitoring workflows](https://docs.github.com/en/actions/how-tos/monitor-workflows)

### Repository Management
- [About GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects)
- [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- [Deciding when to build a GitHub App](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/deciding-when-to-build-a-github-app)

### Security & Dependencies
- [Dependabot configuration template](https://github.com/POWERFULMOVES/PMOVES.AI/new/main?dependabot_template=1&filename=.github%2Fdependabot.yml)

### Secrets & Package Publishing (Org Standard)
- Store credentials only in GitHub Secrets (org/repo/env scope) and the team vault; never in tracked files.
- Standard secret names: `GH_PAT_PUBLISH`, `GHCR_USERNAME`, `DOCKERHUB_PAT`, `DOCKERHUB_USERNAME`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `YOUTUBE_API_KEY`, `GOOGLE_OAUTH_CLIENT_SECRET`, `DISCORD_WEBHOOK` (add more as needed; keep them documented in `docs/SECRETS_ONBOARDING.md`).
- Image publishing: workflows should `docker/login-action` to GHCR and Docker Hub using the secrets above, then `docker/build-push-action` with SBOM+provenance and signed tags.

---

## PMOVES Project Repositories

### Core Components
| Repository | Description |
|------------|-------------|
| [PMOVES-Creator](https://github.com/POWERFULMOVES/PMOVES-Creator.git) | Content creation and management tools |
| [PMOVES-Agent-Zero](https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git) | Primary agent system |
| [PMOVES-Archon](https://github.com/POWERFULMOVES/PMOVES-Archon.git) | Architecture and orchestration layer |
| [PMOVES-Deep-Serch](https://github.com/POWERFULMOVES/PMOVES-Deep-Serch.git) | Advanced search capabilities |
| [PMOVES-HiRAG](https://github.com/POWERFULMOVES/PMOVES-HiRAG.git) | Hierarchical Retrieval-Augmented Generation |

### Media & Content
| Repository | Description |
|------------|-------------|
| [PMOVES.YT](https://github.com/POWERFULMOVES/PMOVES.YT.git) | YouTube integration and processing |
| [PMOVES-Jellyfin](https://github.com/POWERFULMOVES/PMOVES-Jellyfin.git) | Media server integration |
| [Pmoves-Jellyfin-AI-Media-Stack](https://github.com/POWERFULMOVES/Pmoves-Jellyfin-AI-Media-Stack.git) | AI-powered media processing stack |

### Tools & Utilities
| Repository | Description |
|------------|-------------|
| [PMOVES-Open-Notebook](https://github.com/POWERFULMOVES/PMOVES-Open-Notebook.git) | Notebook and documentation system |
| [Pmoves-Health-wger](https://github.com/POWERFULMOVES/Pmoves-Health-wger.git) | Health and fitness integration |
| [PMOVES-Wealth](https://github.com/POWERFULMOVES/PMOVES-Wealth.git) | Financial management tools |
| [PMOVES-ToKenism-Multi](https://github.com/POWERFULMOVES/PMOVES-ToKenism-Multi.git) | Multi-token management system |
| [PMOVES-DoX](https://github.com/POWERFULMOVES/PMOVES-DoX.git) | Documentation and knowledge management |

### Networking & Remote Access
| Repository | Description |
|------------|-------------|
| [PMOVES-Remote-View](https://github.com/POWERFULMOVES/PMOVES-Remote-View.git) | Remote access and viewing capabilities |
| [PMOVES-Tailscale](https://github.com/POWERFULMOVES/PMOVES-Tailscale.git) | VPN and network integration |

---

## Infrastructure & Deployment

### Cloudflare Integration
- [Workers AI Configuration Bindings](https://developers.cloudflare.com/workers-ai/configuration/bindings/)
- [Pages Deploy Hooks](https://developers.cloudflare.com/pages/configuration/deploy-hooks/)

### Reference Implementations
- [Cloudflare AI Hono Durable Objects Example](https://github.com/elizabethsiegle/nbafinals-cloudflare-ai-hono-durable-objects.git) - Can be used to setup users on Cloudflare and add to GitHub users

### RustDesk Server Setup
For self-hosted remote desktop solutions:

- [Installation Guide](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/install/)
- [Docker Deployment](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/)
- [Client Configuration](https://rustdesk.com/docs/en/self-host/client-configuration/)
- [Client Deployment](https://rustdesk.com/docs/en/self-host/client-deployment/)

---

## Video Resources & Tutorials

### ARCHON & Claude Code Integration
For running Claude Code in spinnable VMs with ARCHON:

- [Video 1](https://www.youtube.com/watch?v=XaYpdKGKKtY)
- [Video 2](https://www.youtube.com/watch?v=kFpLzCVLA20)
- [Video 3](https://www.youtube.com/watch?v=OIKTsVjTVJE)
- [Video 4](https://www.youtube.com/watch?v=p0mrXfwAbCg)

### Richard Aragon's Playlists
- [Complete Playlist Collection](https://www.youtube.com/@richardaragon8471/playlists)

---

## Team & Collaboration

### PMOVES.AI-Edition-Hardened
Specialized hardened edition for enhanced security and stability.

### Collaborators

| Username | Role |
|----------|------|
| hunnibear | Collaborator |
| Pmovesjordan | Collaborator |
| Barathicite | Collaborator |
| wdrolle | Collaborator |

---

## Additional Resources

### Claude AI Integration
- [Using the Connectors Directory to Extend Claude's Capabilities](https://support.claude.com/en/articles/11724452-using-the-connectors-directory-to-extend-claude-s-capabilities)

---

## Notes

- This document serves as a central reference for PMOVES.AI's GitHub organization and infrastructure
- Regular updates should be made as new repositories are added or configurations change
- Team members should ensure they have appropriate access to the repositories mentioned above
