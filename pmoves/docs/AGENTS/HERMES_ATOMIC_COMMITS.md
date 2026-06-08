# Atomic Commits & Targeted PRs Guide
# PMOVES.AI HERMES Agent Integration
# Node: Z890 (Elder-Melchor)

## Atomic Commit Rules

### 1. One Concern Per Commit
Each commit must address exactly one logical concern:
- ✅ `fix: correct Z890 GPU spec from RTX 3090 Ti to GTX 1650`
- ✅ `feat: add OpenShell sandbox_policy to room manifest`
- ✅ `docs: update HERMES_AGENT_INTEGRATION.md with Neotron 3 Ultra research`
- ❌ `fix: update specs and add features and docs` (TOO BIG)

### 2. Commit Message Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: new feature
- `fix`: bug fix
- `docs`: documentation only
- `style`: formatting, missing semicolons, etc.
- `refactor`: code change that neither fixes a bug nor adds a feature
- `test`: adding tests
- `chore`: build process, auxiliary tools, libraries

Scopes for HERMES integration:
- `hermes-agent`: agent definition
- `hermes-room`: room manifest
- `hermes-profile`: node profile configs
- `hermes-skill`: operator skills
- `hermes-tac`: TAC tree
- `hermes-registry`: agent registry/signature
- `hermes-docs`: integration docs
- `hermes-research`: research findings

### 3. Targeted PR Rules

| Rule | Description |
|------|-------------|
| **Small** | < 400 lines changed per PR |
| **Focused** | One feature or fix per PR |
| **Reviewable** | Can be reviewed in < 30 minutes |
| **Green CI** | All checks pass before merge |
| **Signed** | CHIT attestation on PR |

### 4. PR Template for HERMES

```markdown
## Type
- [ ] feat
- [ ] fix
- [ ] docs
- [ ] refactor
- [ ] test
- [ ] chore

## Scope
hermes-*(agent|room|profile|skill|tac|registry|docs|research)

## Description
<!-- What does this PR do? -->

## Node Impact
<!-- Which nodes affected? -->
- [ ] Z890
- [ ] 5090
- [ ] 4090
- [ ] Spark
- [ ] B850
- [ ] KVM4-1

## Checklist
- [ ] Atomic commit(s)
- [ ] CHIT signed
- [ ] Profile specs verified (if hardware-related)
- [ ] Glances monitoring updated (if system-related)
- [ ] AGNOTE references updated
- [ ] TAC tree status updated
```

### 5. Hardware Change Protocol
When updating node specs (like Z890 GPU correction):
1. Run live system scan (`python -c "import psutil; ..."`)
2. Update profile YAML
3. Update system-specs.json
4. Update glances.conf thresholds
5. Update any docs referencing the old spec
6. Single commit with scope `hermes-profile`
7. PR titled: `fix(hermes-profile): correct Z890 GPU from RTX 3090 Ti to GTX 1650`

### 6. Example: The GPU Correction PR
This is a perfect example of why atomic commits matter:
- **Before**: Z890 profile claimed RTX 3090 Ti 24GB
- **Actual**: GTX 1650 4GB (live scan confirmed)
- **Impact**: Model routing, Ollama config, glances thresholds all wrong
- **Fix**: One atomic commit correcting the spec, triggering cascade updates

## Glances Monitoring for PR Validation

Before submitting hardware-related PRs:
```bash
# Verify specs match reality
python -c "import psutil, json; print(json.dumps({'cpu': psutil.cpu_count(), 'ram': psutil.virtual_memory().total}"
nvidia-smi --query-gpu=name,memory.total --format=csv

# Update glances thresholds in profile if specs changed
```
