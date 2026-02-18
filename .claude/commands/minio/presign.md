# MinIO Presign

Generate presigned URLs for MinIO objects via the Presign service.

## Instructions

Generate a short-lived presigned URL for an object in MinIO. The user should provide:
1. **Bucket** — `assets` or `outputs`
2. **Key** — the object path within the bucket

```bash
# Generate presigned URL via Presign service (port 8088)
curl -s -X POST http://localhost:8088/presign \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $PRESIGN_SHARED_SECRET" \
  -d '{"bucket": "$BUCKET", "key": "$KEY", "expires_in": 3600}'
```

```bash
# Check Presign service health
curl -s http://localhost:8088/healthz
```

**Notes:**
- Presigned URLs expire after the specified duration (default: 1 hour)
- Only `assets` and `outputs` buckets are allowed
- Requires `PRESIGN_SHARED_SECRET` environment variable
