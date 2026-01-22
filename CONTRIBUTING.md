# Contributing to PMOVES.AI

Thank you for your interest in contributing to PMOVES.AI! This document provides guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Git with submodule support
- Python 3.11+
- Node.js 18+ (for UI development)
- Make

### Development Setup

1. **Clone the repository with submodules:**
   ```bash
   git clone --recurse-submodules https://github.com/POWERFULMOVES/PMOVES.AI.git
   cd PMOVES.AI
   ```

2. **Run the first-time setup:**
   ```bash
   make first-run
   ```
   This bootstraps the environment, starts services, and runs smoke tests.

3. **Verify your setup:**
   ```bash
   make verify-all
   ```

### Project Structure

- `pmoves/` - Primary application stack (services, compose files, docs)
- `docs/` - High-level documentation and architecture guides
- `.claude/` - Claude Code CLI integration and developer context
- `CATACLYSM_STUDIOS_INC/` - Infrastructure provisioning bundles

## How to Contribute

### Reporting Issues

Before creating an issue:
1. Search existing issues to avoid duplicates
2. Use the appropriate issue template
3. Include reproduction steps, expected behavior, and actual behavior
4. Attach relevant logs (sanitize secrets!)

### Pull Requests

1. **Fork and branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Follow coding standards:**
   - Python: Follow PEP 8, use type hints
   - TypeScript/JavaScript: Use ESLint configuration
   - Docker: Follow multi-stage build patterns
   - All services must expose `/healthz` and `/metrics` endpoints

3. **Write tests:**
   - Add smoke tests for new services
   - Include functional tests for new features
   - Run existing tests before submitting

4. **Commit messages:**
   Use conventional commits format:
   ```
   type(scope): description

   [optional body]

   [optional footer]
   ```
   Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`

5. **Submit PR:**
   - Target the `main` branch
   - Fill out the PR template completely
   - Link related issues
   - Ensure CI passes

### Development Patterns

#### Service Integration
- Use existing services (Hi-RAG, TensorZero, Agent Zero) - don't duplicate
- Publish events to NATS for async coordination
- Store artifacts in MinIO via Presign service
- Follow the observability patterns (Prometheus metrics, Loki logging)

#### Docker Services
All new services should:
- Run as non-root user (`USER pmoves` or similar)
- Expose health check endpoint at `/healthz`
- Expose Prometheus metrics at `/metrics`
- Include in appropriate compose profile
- Document in `pmoves/docs/services/`

#### Environment Variables
- Add new variables to `pmoves/env.shared.example`
- Document in service README
- Never commit secrets to the repository

### Testing Requirements

Before submitting a PR:

```bash
# Run smoke tests
make verify-all

# Run functional tests
cd pmoves/tests && ./run-functional-tests.sh

# Check specific service
make <service>-smoke
```

### Documentation

- Update relevant README files
- Add entries to `pmoves/docs/services/` for new services
- Keep `CLAUDE.md` files current for AI-assisted development
- Document NATS subjects in `.claude/context/nats-subjects.md`

## Architecture Decisions

Major architectural changes require:
1. Discussion in a GitHub issue first
2. Update to relevant architecture documentation
3. Approval from maintainers

## Trademark Notice

When contributing, be aware that certain names are trademarks of Cataclysm Studios Inc. (see [LICENSE](LICENSE)):
- CATACLYSM STUDIOS, PMOVES, PMOVES.AI, POWERFULMOVES, DARKXSIDE
- CHIT protocol, Geometry Bus, Shape Attribution, CGP specification

Use of trademarks in marketing or branding requires explicit permission.

## Getting Help

- Check [pmoves/docs/](pmoves/docs/) for detailed documentation
- Review [.claude/CLAUDE.md](.claude/CLAUDE.md) for service catalog
- Open a discussion for questions

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
