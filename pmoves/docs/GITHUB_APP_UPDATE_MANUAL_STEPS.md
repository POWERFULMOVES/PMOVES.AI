# GitHub App Configuration Update - Manual Steps

**Date:** 2026-03-14
**Status:** Code Complete | Manual GitHub.com Update Required

---

## Summary of Automated Changes

### ✅ Files Created
1. `pmoves/n8n/flows/github_webhook_processor_v2.json` - Enhanced webhook workflow with 12 event types

### ✅ Files Modified
1. `pmoves/chit/secrets_manifest.yaml` - Added `gh_webhook_secret` entry with `env.tier-worker` target
2. `pmoves/env.shared` - Added `GH_WEBHOOK_SECRET=changeme-generate-in-github-app-settings`
3. `pmoves/docker-compose.n8n.yml` - Added `GH_WEBHOOK_SECRET` environment variable to n8n service
4. `pmoves/docs/GITHUB_APP_INTEGRATION_STATUS.md` - Added Phase 7 and n8n configuration documentation
5. `pmoves/docs/infrastructure/github-app-strategy.md` - Updated permissions matrix and event table

---

## Manual Steps Required

### Step 1: Navigate to GitHub App Settings

```
https://github.com/organizations/POWERFULMOVES/settings/apps/PMOVES.AI
```

**Prerequisites:** Org admin access for POWERFULMOVES

---

### Step 2: Update Permissions (Basic Permissions Tab)

| Permission | Current | New | Reason |
|------------|---------|-----|--------|
| **Contents** | Read | **Read & Write** | Agents need to modify files |
| **Metadata** | - | **Read-only** (add) | Repository metadata for dashboard |
| **Pull requests** | Write | Write (keep) | Create/modify PRs |
| **Issues** | Write | Write (keep) | Create/modify issues |
| **Actions** | Read | Read (keep) | Read workflow status |
| **Workflows** | - | **Read & Write** (add) | Trigger/enable workflows via API |
| **Packages** | Write | Write (keep) | GHCR push/pull |
| **Repositories** | - | **Read-only** (add) | Repo settings for dashboard |
| **Projects** | - | **Read-only** (add) | GitHub Projects tracking |

**Action:** Click "Edit" on permissions, make changes, save.

---

### Step 3: Subscribe to Webhook Events (Webhook Tab)

**Current Events (3):**
- `workflow_run`
- `workflow_job`
- `check_run`

**Events to Add (9):**
- ✅ `push` - Code pushes → trigger builds, index new code
- ✅ `pull_request` - PR opened/closed/merged → agent triage
- ✅ `pull_request_review` - Review submitted → dashboard update
- ✅ `issues` - Issue opened/edited/closed → agent processing
- ✅ `issue_comment` - Comment activity → sentiment/response
- ✅ `release` - New releases → auto-deploy, changelog
- ✅ `create` - Branch/tag created → notifications
- ✅ `repository` - Repo settings changed → config sync
- ✅ `delete` - Branch deletion → cleanup

**Total After Update:** 12 events

**Action:** Check additional event boxes, save.

---

### Step 4: Configure Webhook URL & Secret (Webhook Tab)

**Current Settings:**
- Active: ❓ (verify)
- URL: Smee/dev or n8n
- Secret: Not configured

**New Settings:**

| Setting | Value |
|---------|-------|
| **Active** | ✅ (checked) |
| **URL** | `https://<your-n8n-public-domain>/webhook/github` |
| **Content type** | `application/json` |
| **Secret** | Click "Generate" button |

**After Generating Secret:**
1. Copy the generated secret
2. Run: `make -C pmoves secrets-funnel` to open editor
3. Replace `changeme-generate-in-github-app-settings` with the actual secret in `env.shared`
4. Run: `make -C pmoves secrets-funnel` again to propagate to tier files
5. Restart services: `make -C pmoves up`

**Example:**
```bash
# In env.shared, find this line:
GH_WEBHOOK_SECRET=changeme-generate-in-github-app-settings

# Replace with:
GH_WEBHOOK_SECRET=gits hmac random_generated_secret_value_from_github
```

---

### Step 5: Verify Installation Scope

**Current Setting:** All POWERFULMOVES repositories ✅

**Action:** Verify this is still selected (no change needed).

---

### Step 6: Save Changes

**Action:** Click "Save changes" at bottom of page

**Expected Result:** Green success banner, no errors

---

## Post-Update Verification

### Test Webhook Delivery

```bash
# Trigger a test event (create an issue)
gh api repos/POWERFULMOVES/PMOVES.AI/issues --method POST \
  -f title="Webhook Test $(date +%s)" \
  -f body="Testing GitHub webhook v2"
```

### Verify NATS Events

```bash
# Monitor NATS for GitHub events
nats sub "github.>" --csv

# Should see events like:
# github.push.v1
# github.pull_request.v1
# github.issues.v1
# etc.
```

### Verify Discord Notifications

Check Discord channel for webhook notifications. Should see formatted embeds with:
- Repository name
- Event emoji (📝, 🔥, 🚀, etc.)
- Event details
- Links to relevant resources

### Verify n8n Workflow

1. Login to n8n: `http://<n8n-domain>:5678`
2. Import `pmoves/n8n/flows/github_webhook_processor_v2.json`
3. Activate the workflow
4. Trigger a test event
5. Check workflow execution history

---

## Troubleshooting

### Webhook Not Received

1. Check GitHub App webhook delivery log:
   - Go to GitHub App settings
   - Click "Advanced" → "Recent deliveries"
   - Look for failed deliveries with error codes

2. Common issues:
   - **404**: Webhook URL incorrect or n8n not accessible
   - **401/403**: Signature mismatch (check GH_WEBHOOK_SECRET)
   - **Timeout**: n8n workflow processing too slow

### Signature Verification Errors

If n8n reports signature verification failures:

1. Verify secret matches exactly (no extra spaces)
2. Check n8n has access to `GH_WEBHOOK_SECRET` environment variable
3. Restart n8n service after updating secret

### Events Not Published to NATS

1. Check n8n workflow execution history
2. Verify NATS is running: `docker compose ps nats`
3. Test NATS connection:
   ```bash
   curl -X POST http://nats:4222/pub \
     -H "subject: test.subject" \
     -d '{"test": true}'
   ```

---

## Rollback Plan

If issues arise:

1. **Revert GitHub App permissions:**
   - Uncheck newly added events
   - Change `contents` back to Read-only
   - Save changes

2. **Remove webhook secret:**
   - In GitHub App settings, click "Reveal" then "Delete" secret
   - Regenerate env.tier files without secret

3. **Disable n8n workflow v2:**
   - Deactivate `github_webhook_processor_v2.json`
   - Re-enable v1 workflow if needed

---

## Success Criteria

After completing manual steps:

- ✅ GitHub App permissions updated (contents:write, workflows:write, etc.)
- ✅ All 12 webhook events subscribed
- ✅ Webhook URL configured to n8n endpoint
- ✅ Webhook secret added to env.shared and synced
- ✅ n8n workflow v2 imported and active
- ✅ Test events received and processed
- ✅ NATS events published correctly
- ✅ Discord notifications working

---

## References

- **GitHub App Strategy:** `pmoves/docs/infrastructure/github-app-strategy.md`
- **Integration Status:** `pmoves/docs/GITHUB_APP_INTEGRATION_STATUS.md`
- **n8n Workflow:** `pmoves/n8n/flows/github_webhook_processor_v2.json`
- **Secrets Manifest:** `pmoves/chit/secrets_manifest.yaml`
