# MinIO Upload

Upload a file to MinIO object storage.

## Instructions

Upload a file to a specified bucket. The user should provide:
1. **File path** — local file to upload
2. **Bucket** — target bucket (`assets` or `outputs`)
3. **Key** — destination object key

```bash
# Upload via mc CLI (if available in container)
docker exec -it minio mc cp "/tmp/$FILENAME" "local/$BUCKET/$KEY"
```

```bash
# Upload via curl with presigned PUT URL
# First generate a presigned PUT URL, then upload
curl -s -X PUT "$PRESIGNED_URL" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @"$FILE_PATH"
```

```bash
# Verify upload
docker exec -it minio mc ls "local/$BUCKET/$KEY"
```

**Notes:**
- For large files, consider using multipart upload
- The Presign service (port 8088) can generate PUT URLs
- Verify bucket exists before uploading
