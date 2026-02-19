# MinIO Status

Check the status of MinIO S3-compatible object storage.

## Instructions

Check health of:
1. **MinIO Server** (port 9000) - Object storage API
2. **MinIO Console** (port 9001) - Web management UI
3. **Buckets** - Verify `assets` and `outputs` exist

```bash
# MinIO health check
curl -s http://localhost:9000/minio/health/live && echo "MinIO: healthy" || echo "MinIO: unhealthy"
```

```bash
# List buckets (requires mc client or curl with auth)
docker exec -it minio mc ls local/ 2>/dev/null || echo "Use MinIO Console at http://localhost:9001"
```

```bash
# Container status
docker ps --filter "name=minio" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Report:
- MinIO health (live/dead)
- Bucket listing (assets, outputs)
- Storage usage if available
- Console accessibility
