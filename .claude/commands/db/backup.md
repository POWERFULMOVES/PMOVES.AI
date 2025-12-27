# Database Backup

Create, list, or restore PMOVES Supabase database backups.

## Usage

```
/db:backup [action] [backup_id]
```

## Arguments

- `action`: `create`, `list`, `restore`, `status` (default: `list`)
- `backup_id`: Backup identifier (required for `restore`)

## What This Command Does

1. **List Backups:**
   ```bash
   # Via Supabase Management API
   curl -X GET "https://api.supabase.com/v1/projects/${SUPABASE_PROJECT_ID}/database/backups" \
     -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}"

   # Or list MinIO backup files
   mc ls minio/backups/supabase/
   ```

2. **Create Manual Backup:**
   ```bash
   # pg_dump to MinIO
   BACKUP_FILE="pmoves_$(date +%Y%m%d_%H%M%S).sql.gz"
   pg_dump "${SUPABASE_DB_URL}" | gzip | \
     mc pipe minio/backups/supabase/${BACKUP_FILE}
   ```

3. **Restore from Backup:**
   ```bash
   # Download and restore
   mc cat minio/backups/supabase/${BACKUP_FILE} | gunzip | \
     psql "${SUPABASE_DB_URL}"
   ```

4. **Check Backup Status:**
   ```bash
   # Verify latest backup
   mc stat minio/backups/supabase/latest.sql.gz
   ```

## Backup Types

| Type | Frequency | Retention | Method |
|------|-----------|-----------|--------|
| Automatic | Daily | 7 days | Supabase managed |
| Point-in-Time | Continuous | 7 days | WAL archiving |
| Manual | On-demand | 30 days | pg_dump to MinIO |
| Pre-Migration | Before migrate | 90 days | Tagged backup |

## Safety Rules

### Before Restore
- [ ] Verify backup integrity (checksum)
- [ ] Test restore on staging first
- [ ] Notify team of maintenance window
- [ ] Document current state for rollback

### BLOCKED Operations
- Restore to production without approval
- Delete backups less than 7 days old
- Overwrite without verification

### ALLOWED Operations
- Create manual backups anytime
- List and inspect backups
- Restore to local/staging
- Download backup files

## Output Format

```markdown
## Backup Status

### Latest Backups
| ID | Type | Size | Created | Status |
|----|------|------|---------|--------|
| backup_20250607_120000 | Manual | 245 MB | 2025-06-07 12:00 | Completed |
| backup_20250606_000000 | Auto | 242 MB | 2025-06-06 00:00 | Completed |
| backup_20250605_000000 | Auto | 240 MB | 2025-06-05 00:00 | Completed |

### Storage Summary
- **Total Backups:** 12
- **Total Size:** 2.8 GB
- **Oldest Backup:** 2025-05-08
- **Latest Backup:** 2025-06-07 12:00:00

### Point-in-Time Recovery
- **Available Range:** 2025-05-31 to 2025-06-07
- **WAL Size:** 1.2 GB
```

## Example

```bash
# List all backups
/db:backup list

# Create manual backup
/db:backup create

# Check backup status
/db:backup status

# Restore specific backup (staging only)
/db:backup restore backup_20250607_120000
```

## Backup Scripts

### Automated Backup Script
```bash
#!/bin/bash
# scripts/backup-database.sh

set -euo pipefail

BACKUP_NAME="pmoves_$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="backups/supabase/${BACKUP_NAME}.sql.gz"

echo "Creating backup: ${BACKUP_NAME}"

# Dump and compress
pg_dump "${SUPABASE_DB_URL}" \
  --format=plain \
  --no-owner \
  --no-acl \
  --schema=pmoves_core \
  --schema=archon \
  | gzip > "/tmp/${BACKUP_NAME}.sql.gz"

# Upload to MinIO
mc cp "/tmp/${BACKUP_NAME}.sql.gz" "minio/${BACKUP_PATH}"

# Update latest symlink
mc cp "minio/${BACKUP_PATH}" "minio/backups/supabase/latest.sql.gz"

# Cleanup local
rm "/tmp/${BACKUP_NAME}.sql.gz"

# Publish NATS event
nats pub "backup.database.completed.v1" "{\"backup\": \"${BACKUP_NAME}\", \"path\": \"${BACKUP_PATH}\"}"

echo "Backup completed: ${BACKUP_PATH}"
```

### Selective Table Backup
```bash
# Backup specific tables
pg_dump "${SUPABASE_DB_URL}" \
  --table=pmoves_core.content_items \
  --table=pmoves_core.embeddings \
  --data-only \
  | gzip > "content_backup.sql.gz"
```

### Schema-Only Backup
```bash
# Backup schema without data
pg_dump "${SUPABASE_DB_URL}" \
  --schema-only \
  --schema=pmoves_core \
  > schema_backup.sql
```

## Environment Variables

Required:
- `SUPABASE_DB_URL` - Direct Postgres connection string
- `MINIO_ENDPOINT` - MinIO server URL
- `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` - MinIO credentials

Optional:
- `SUPABASE_PROJECT_ID` - For Supabase managed backups
- `SUPABASE_ACCESS_TOKEN` - For management API

## MinIO Backup Storage

```
minio/
└── backups/
    └── supabase/
        ├── latest.sql.gz          # Symlink to most recent
        ├── pmoves_20250607_120000.sql.gz
        ├── pmoves_20250606_000000.sql.gz
        ├── pre_migration/         # Tagged pre-migration backups
        │   └── before_v2_schema.sql.gz
        └── monthly/               # Long-term retention
            └── pmoves_202505.sql.gz
```

## Restore Procedures

### Local Development Restore
```bash
# Download and restore to local Supabase
mc cat minio/backups/supabase/latest.sql.gz | gunzip | \
  psql "postgresql://postgres:postgres@localhost:54322/postgres"
```

### Staging Restore
```bash
# Restore to staging environment
mc cat minio/backups/supabase/${BACKUP_ID}.sql.gz | gunzip | \
  psql "${STAGING_DB_URL}"
```

### Production Restore (Requires Approval)
```bash
# 1. Create pre-restore backup
/db:backup create

# 2. Enable maintenance mode
# 3. Restore from backup
# 4. Verify data integrity
# 5. Disable maintenance mode
```

## Notes

- Supabase Pro includes automatic daily backups
- Point-in-time recovery available on Pro plan
- Always test restore procedures regularly
- Monitor backup sizes for growth trends
- Keep at least 3 verified restore points
