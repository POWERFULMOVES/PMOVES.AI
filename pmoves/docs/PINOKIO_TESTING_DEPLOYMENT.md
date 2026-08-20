# PMOVES Pinokio Testing & Deployment Workflow

> **Last Updated:** 2026-03-22  
> **Related:** [PINOKIO_PACKAGING_GUIDE.md](./PINOKIO_PACKAGING_GUIDE.md) | [PINOKIO_EXAMPLE_MANIFESTS.md](./PINOKIO_EXAMPLE_MANIFESTS.md)

This document covers the complete workflow for testing, validating, and deploying PMOVES agents as Pinokio packages.

---

## Table of Contents

1. [Development Workflow](#development-workflow)
2. [Local Testing](#local-testing)
3. [Validation Checklist](#validation-checklist)
4. [CI/CD Integration](#cicd-integration)
5. [Distribution & Publishing](#distribution--publishing)
6. [Maintenance & Updates](#maintenance--updates)

---

## Development Workflow

### Phase 1: Package Creation

```
┌─────────────────────────────────────────────────────────────────┐
│                    Package Creation Flow                         │
├─────────────────────────────────────────────────────────────────┤
│  1. Create folder structure                                     │
│     └── PMOVES-pinokio/api/pmoves-agent-name/                   │
│                                                                 │
│  2. Create pinokio.json (metadata)                              │
│     └── Define title, description, requirements                 │
│                                                                 │
│  3. Create pinokio/pinokio.js (menu)                            │
│     └── Define menu items, default states                       │
│                                                                 │
│  4. Create pinokio/install.js                                   │
│     └── Clone repo, install dependencies                         │
│                                                                 │
│  5. Create pinokio/start.js                                     │
│     └── Launch command, URL capture                              │
│                                                                 │
│  6. Create pinokio/reset.js (optional)                          │
│     └── Cleanup script                                           │
│                                                                 │
│  7. Create README.md                                             │
│     └── User-facing documentation                                │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 2: Local Testing

```bash
# 1. Create symlink to Pinokio apps directory
ln -s $(pwd)/PMOVES-pinokio/api/pmoves-agent-name ~/pinokio/api/pmoves-agent-name

# 2. Restart Pinokio or refresh apps
# Pinokio will auto-detect the new app

# 3. Test via Pinokio UI
# Open Pinokio → Find app → Click Install → Click Start
```

### Phase 3: Validation

Run through the complete validation checklist (see below) before publishing.

### Phase 4: Publishing

```bash
# 1. Commit to repository
git add PMOVES-pinokio/api/pmoves-agent-name/
git commit -m "feat(pinokio): add PMOVES Agent Name launcher"

# 2. Tag release
git tag pinokio-agent-name-v1.0.0

# 3. Push to GitHub
git push origin main --tags

# 4. Submit to Pinokio registry (optional)
# Visit https://pinokio.computer/submit
```

---

## Local Testing

### Method 1: Symlink Development

Best for active development with hot-reload:

```bash
# macOS/Linux
ln -s /path/to/PMOVES.AI/PMOVES-pinokio/api/pmoves-agent-name \
  ~/pinokio/api/pmoves-agent-name

# Windows (PowerShell - Admin)
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\pinokio\api\pmoves-agent-name" `
  -Target "C:\path\to\PMOVES.AI\pbnj\pinokio\api\pmoves-agent-name"
```

**Benefits:**
- Changes reflect immediately in Pinokio
- No need to copy files after each edit
- Full Pinokio environment testing

### Method 2: Pterm CLI Testing

Test individual scripts without opening Pinokio UI:

```bash
# Test install script
pterm start /path/to/pmoves-agent-name/install.js

# Test start script
pterm start /path/to/pmoves-agent-name/start.js

# View logs
pterm logs /path/to/pmoves-agent-name

# Stop running script
pterm stop /path/to/pmoves-agent-name/start.js
```

### Method 3: Direct Script Testing

For debugging script logic, test JavaScript directly:

```bash
# Navigate to pinokio folder
cd PMOVES-pinokio/api/pmoves-agent-name/pinokio

# Test script with Node.js (limited - no Pinokio APIs)
node -e "const script = require('./install.js'); console.log(JSON.stringify(script, null, 2))"
```

### Testing Matrix

Test your package across all supported configurations:

| Platform | Architecture | GPU | Status |
|----------|--------------|-----|--------|
| Windows | x64 | NVIDIA | ☐ |
| Windows | x64 | None | ☐ |
| macOS | arm64 (M1/M2) | Metal | ☐ |
| macOS | x64 (Intel) | None | ☐ |
| Linux | x64 | NVIDIA | ☐ |
| Linux | x64 | AMD | ☐ |
| Linux | arm64 | None | ☐ |

---

## Validation Checklist

### Pre-Flight Checks

#### Metadata Validation

- [ ] `pinokio.json` exists and is valid JSON
- [ ] `version` field is `"1"`
- [ ] `title` is concise and descriptive
- [ ] `description` explains what the agent does
- [ ] `icon` path points to existing file (512x512 PNG recommended)
- [ ] `platform` array includes all supported OS
- [ ] `arch` array includes all supported architectures
- [ ] `gpu` field set appropriately (`required`, `optional`, or omitted)

#### Script Validation

- [ ] `pinokio/pinokio.js` exists and exports valid menu structure
- [ ] `pinokio/install.js` exists and completes without errors
- [ ] `pinokio/start.js` exists and captures URL correctly
- [ ] `pinokio/reset.js` exists (optional but recommended)
- [ ] All scripts use correct API methods (see API Reference)

#### Menu Validation

- [ ] Default states change based on installation status
- [ ] Running state reflected in menu items
- [ ] URLs appear when service is running
- [ ] Disabled states work correctly (GPU, platform restrictions)
- [ ] Menu items have clear titles and descriptions

### Functional Testing

#### Installation Test

```bash
# Clean slate test
rm -rf ~/pinokio/api/pmoves-agent-name/app

# Run install
pterm start /path/to/pmoves-agent-name/install.js

# Verify
ls ~/pinokio/api/pmoves-agent-name/app/
# Should show: cloned repo, .installed marker
```

**Checklist:**
- [ ] Repository clones successfully
- [ ] Dependencies install without errors
- [ ] `.installed` marker created
- [ ] Example config files created (if applicable)
- [ ] User notified of completion

#### Start Test

```bash
# Start the service
pterm start /path/to/pmoves-agent-name/start.js

# Check if running
curl http://localhost:PORT/healthz

# Check logs
pterm logs /path/to/pmoves-agent-name
```

**Checklist:**
- [ ] Service starts without errors
- [ ] URL captured correctly via regex
- [ ] URL stored in local variables
- [ ] Service accessible at captured URL
- [ ] Health endpoint returns 200

#### Menu State Test

```bash
# Before install
# - "Install" should be default
# - "Start" should be disabled/hidden

# After install
# - "Start" should be default
# - "Install" should show "Installed" state

# After start
# - "Open WebUI" should be default
# - URL should be accessible
```

#### Reset Test

```bash
# Run reset
pterm start /path/to/pmoves-agent-name/reset.js

# Verify cleanup
ls ~/pinokio/api/pmoves-agent-name/app/
# Should NOT show: .installed, node_modules, .env
```

**Checklist:**
- [ ] Dependencies removed
- [ ] Config files cleaned (optional)
- [ ] Installation marker removed
- [ ] User notified of reset

### Cross-Platform Testing

#### Windows-Specific Checks

- [ ] Shell commands use Windows-compatible syntax
- [ ] Path separators handled correctly
- [ ] Environment variables set properly
- [ ] PowerShell vs CMD compatibility

```javascript
// Example: Windows-compatible command
{
  method: "shell.run",
  params: {
    message: platform === "win32"
      ? "pip install -r requirements.txt"
      : "pip3 install -r requirements.txt"
  }
}
```

#### macOS-Specific Checks

- [ ] Homebrew dependencies documented
- [ ] M1/M2 (arm64) compatibility
- [ ] Metal GPU acceleration (if applicable)

#### Linux-Specific Checks

- [ ] System dependencies documented (ffmpeg, etc.)
- [ ] NVIDIA CUDA setup for GPU services
- [ ] Systemd service compatibility (optional)

### GPU Testing

#### GPU Detection Test

```javascript
// Verify GPU detection works
{
  method: "notify",
  params: {
    message: `GPU detected: ${gpu || "None"}\nArchitecture: ${arch}`
  }
}
```

#### GPU Service Test

- [ ] Service starts with GPU if available
- [ ] Falls back to CPU if no GPU
- [ ] GPU memory usage is reasonable
- [ ] CUDA errors handled gracefully

---

## CI/CD Integration

### GitHub Actions Workflow

Create `.github/workflows/pinokio-validate.yml`:

```yaml
name: Validate Pinokio Package

on:
  push:
    paths:
      - 'PMOVES-pinokio/api/**'
  pull_request:
    paths:
      - 'PMOVES-pinokio/api/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Validate JSON files
        run: |
          for file in PMOVES-pinokio/api/*/pinokio.json; do
            echo "Validating $file"
            python -m json.tool "$file" > /dev/null || exit 1
          done
      
      - name: Validate JavaScript files
        run: |
          for file in PMOVES-pinokio/api/*/pinokio/*.js; do
            echo "Checking syntax: $file"
            node --check "$file" || exit 1
          done
      
      - name: Check required files
        run: |
          for dir in PMOVES-pinokio/api/*/; do
            name=$(basename "$dir")
            echo "Checking $name..."
            
            # Required files
            test -f "$dir/pinokio.json" || { echo "Missing pinokio.json in $name"; exit 1; }
            test -f "$dir/README.md" || { echo "Missing README.md in $name"; exit 1; }
            test -f "$dir/pinokio/pinokio.js" || { echo "Missing pinokio.js in $name"; exit 1; }
            test -f "$dir/pinokio/install.js" || { echo "Missing install.js in $name"; exit 1; }
            test -f "$dir/pinokio/start.js" || { echo "Missing start.js in $name"; exit 1; }
          done
      
      - name: Validate metadata
        run: |
          python3 << 'EOF'
          import json
          import os
          import sys
          
          required_fields = ['version', 'title', 'description', 'icon']
          valid_platforms = ['win32', 'darwin', 'linux']
          valid_archs = ['x64', 'arm64']
          
          errors = []
          
          for root, dirs, files in os.walk('PMOVES-pinokio/api'):
              if 'pinokio.json' in files:
                  path = os.path.join(root, 'pinokio.json')
                  with open(path) as f:
                      try:
                          data = json.load(f)
                      except json.JSONError as e:
                          errors.append(f"{path}: Invalid JSON - {e}")
                          continue
                  
                  # Check required fields
                  for field in required_fields:
                      if field not in data:
                          errors.append(f"{path}: Missing required field '{field}'")
                  
                  # Validate version
                  if data.get('version') != '1':
                      errors.append(f"{path}: version must be '1'")
                  
                  # Validate platforms
                  if 'platform' in data:
                      for p in data['platform']:
                          if p not in valid_platforms:
                              errors.append(f"{path}: Invalid platform '{p}'")
                  
                  # Validate architectures
                  if 'arch' in data:
                      for a in data['arch']:
                          if a not in valid_archs:
                              errors.append(f"{path}: Invalid arch '{a}'")
          
          if errors:
              for e in errors:
                  print(f"ERROR: {e}")
              sys.exit(1)
          
          print("All metadata valid!")
          EOF
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash

# Validate Pinokio packages before commit
changed=$(git diff --cached --name-only | grep 'PMOVES-pinokio/api')

if [ -n "$changed" ]; then
    echo "Validating Pinokio packages..."
    
    # Check JSON syntax
    for file in $(echo "$changed" | grep 'pinokio.json'); do
        if [ -f "$file" ]; then
            python3 -m json.tool "$file" > /dev/null || {
                echo "ERROR: Invalid JSON in $file"
                exit 1
            }
        fi
    done
    
    # Check JS syntax
    for file in $(echo "$changed" | grep '\.js$'); do
        if [ -f "$file" ]; then
            node --check "$file" || {
                echo "ERROR: Invalid JavaScript in $file"
                exit 1
            }
        fi
    done
    
    echo "✓ All Pinokio files valid"
fi
```

---

## Distribution & Publishing

### Internal Distribution (PMOVES Team)

PMOVES packages are distributed internally via the monorepo:

```
PMOVES.AI/
└── PMOVES-pinokio/
    └── api/
        ├── pmoves-agent-zero/
        ├── pmoves-archon/
        ├── pmoves-hirag/
        ├── pmoves-services/
        └── pmoves-pbnj/
```

**Installation Methods:**

1. **Symlink (Recommended for Development)**
   ```bash
   # One-time setup
   ln -s /path/to/PMOVES.AI/PMOVES-pinokio/api/* ~/pinokio/api/
   ```

2. **Copy (For Production)**
   ```bash
   # Copy specific package
   cp -r PMOVES-pinokio/api/pmoves-agent-zero ~/pinokio/api/
   ```

3. **Install Script**
   ```bash
   # Run PMOVES installer
   ./PMOVES-pinokio/scripts/install-pinokio-apps.sh
   ```

### Public Distribution (Pinokio Registry)

To publish to the public Pinokio registry:

1. **Prepare Repository**
   ```bash
   # Create standalone repo for the launcher
   mkdir pmoves-agent-zero-pinokio
   cd pmoves-agent-zero-pinokio
   git init
   
   # Copy launcher files
   cp -r /path/to/PMOVES.AI/PMOVES-pinokio/api/pmoves-agent-zero/* .
   
   # Create README
   echo "# PMOVES Agent Zero - Pinokio Launcher" > README.md
   
   # Commit
   git add .
   git commit -m "Initial release"
   git tag v1.0.0
   ```

2. **Push to GitHub**
   ```bash
   git remote add origin https://github.com/POWERFULMOVES/pmoves-agent-zero-pinokio
   git push -u origin main --tags
   ```

3. **Submit to Pinokio**
   - Visit https://pinokio.computer
   - Click "Submit App"
   - Enter repository URL
   - Wait for review

### Version Management

Follow semantic versioning for launcher updates:

| Version Change | Meaning |
|----------------|---------|
| `v1.0.0` → `v1.0.1` | Bug fixes, script improvements |
| `v1.0.0` → `v1.1.0` | New features, menu additions |
| `v1.0.0` → `v2.0.0` | Breaking changes, restructure |

---

## Maintenance & Updates

### Update Workflow

When updating a PMOVES Pinokio package:

```bash
# 1. Make changes to launcher files
vim PMOVES-pinokio/api/pmoves-agent-name/pinokio/start.js

# 2. Test locally
pterm start PMOVES-pinokio/api/pmoves-agent-name/start.js

# 3. Update version in pinokio.json (if needed)
# Note: "version" field is schema version, NOT app version

# 4. Commit changes
git add PMOVES-pinokio/api/pmoves-agent-name/
git commit -m "fix(pinokio): update start script for Agent Name"

# 5. Update changelog
echo "- Fixed start script timeout issue" >> PMOVES-pinokio/api/pmoves-agent-name/CHANGELOG.md
```

### Monitoring Deployed Packages

#### Health Check Script

Create `PMOVES-pinokio/api/pmoves-agent-name/pinokio/health.js`:

```javascript
// pinokio/health.js
// Health check for deployed Agent Zero

module.exports = {
  run: [
    {
      method: "request",
      params: {
        uri: "http://localhost:8080/healthz",
        method: "GET",
        timeout: 5000
      }
    },
    {
      method: "notify",
      params: {
        title: input.status === 200 ? "✅ Agent Zero Healthy" : "❌ Agent Zero Unhealthy",
        message: input.status === 200 
          ? "All systems operational"
          : `Health check failed: ${input.error || "Unknown error"}`
      }
    }
  ]
}
```

#### Log Rotation

Pinokio automatically handles log rotation, but you can add custom cleanup:

```javascript
// pinokio/cleanup-logs.js
// Clean old logs

module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: platform === "win32"
          ? "forfiles /p logs /m *.log /d -7 /c \"cmd /c del @path\""
          : "find logs -name '*.log' -mtime +7 -delete",
        throws: false
      }
    }
  ]
}
```

### Deprecation Process

When deprecating a package:

1. **Add deprecation notice to README.md:**
   ```markdown
   > ⚠️ **DEPRECATED**: This package is no longer maintained.
   > Please use [pmoves-new-agent](link) instead.
   ```

2. **Update pinokio.json:**
   ```json
   {
     "deprecated": true,
     "deprecation_message": "Use pmoves-new-agent instead",
     "replacement": "https://github.com/POWERFULMOVES/pmoves-new-agent-pinokio"
   }
   ```

3. **Create final release:**
   ```bash
   git tag v1.0.0-deprecated
   git push origin v1.0.0-deprecated
   ```

---

## Troubleshooting Guide

### Common Issues

#### Script Not Found

```
Error: Script not found: install.js
```

**Solution:** Check file path and ensure you're in the correct directory:
```bash
ls -la PMOVES-pinokio/api/pmoves-agent-name/pinokio/
```

#### Regex Not Matching

```
Error: Timeout waiting for event
```

**Solution:** Debug the regex pattern:
```javascript
{
  method: "shell.run",
  params: {
    message: "npm start",
    on: [
      {
        event: "/.*/",  // Match everything to see output
        done: false
      },
      {
        event: "/http:\\/\\/[0-9.:]+/",  // Your actual pattern
        done: true
      }
    ]
  }
}
```

#### Environment Variables Not Loading

**Solution:** Check `.env` file encoding (must be UTF-8) and format:
```bash
# Verify .env format
cat app/.env
# Should be: KEY=value (no quotes for simple values)
```

#### GPU Not Detected

**Solution:** Verify GPU detection:
```javascript
{
  method: "notify",
  params: {
    message: `GPU: ${gpu}\nArch: ${arch}\nPlatform: ${platform}`
  }
}
```

### Debug Mode

Enable verbose logging in scripts:

```javascript
module.exports = {
  debug: true,  // Enable debug output
  run: [
    // ... scripts
  ]
}
```

### Getting Help

1. **Pinokio Documentation:** https://pinokio.co/docs
2. **PMOVES Discord:** https://discord.gg/pmoves
3. **GitHub Issues:** https://github.com/POWERFULMOVES/PMOVES.AI/issues
4. **Pinokio Community:** https://github.com/pinokio/community

---

## Quick Reference

### File Checklist

```
pmoves-agent-name/
├── pinokio.json          ☐ Required - Metadata
├── README.md             ☐ Required - Documentation
├── icon.png              ☐ Required - 512x512 icon
├── CHANGELOG.md          ☐ Optional - Version history
└── pinokio/
    ├── pinokio.js        ☐ Required - Menu definition
    ├── install.js        ☐ Required - Installation
    ├── start.js          ☐ Required - Launch script
    ├── reset.js          ☐ Recommended - Cleanup
    ├── update.js         ☐ Optional - Update script
    ├── health.js         ☐ Optional - Health check
    └── logs/             ☐ Auto-created - Logs
```

### Command Reference

```bash
# Install app
pterm start /path/to/app/install.js

# Start app
pterm start /path/to/app/start.js

# Stop app
pterm stop /path/to/app/start.js

# View logs
pterm logs /path/to/app

# Check status
pterm status /path/to/app
```

---

**Related Documentation:**
- [PINOKIO_PACKAGING_GUIDE.md](./PINOKIO_PACKAGING_GUIDE.md) - Complete API reference
- [PINOKIO_EXAMPLE_MANIFESTS.md](./PINOKIO_EXAMPLE_MANIFESTS.md) - Copy-paste examples
- [PMOVES-pinokio/api/](../../../PMOVES-pinokio/api/) - Existing implementations
