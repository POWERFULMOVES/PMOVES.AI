# ComfyUI ↔ MinIO Presign Microservice

A tiny FastAPI service that issues **presigned PUT/GET/POST** URLs for MinIO/S3, plus **ComfyUI custom nodes** to upload images/files directly to MinIO.

## Service

### .env
```
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
AWS_DEFAULT_REGION=us-east-1
ALLOWED_BUCKETS=assets,outputs
PRESIGN_SHARED_SECRET=change_me
```

### Compose snippet
Add under `services:`
```yaml
presign:
  build: ./services/presign
  restart: unless-stopped
  env_file: [.env]
  environment:
    MINIO_ENDPOINT: ${MINIO_ENDPOINT}
    MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY}
    MINIO_SECRET_KEY: ${MINIO_SECRET_KEY}
    MINIO_SECURE: ${MINIO_SECURE:-false}
    AWS_DEFAULT_REGION: ${AWS_DEFAULT_REGION:-us-east-1}
    ALLOWED_BUCKETS: ${ALLOWED_BUCKETS:-assets,outputs}
    PRESIGN_SHARED_SECRET: ${PRESIGN_SHARED_SECRET}
  ports: ["8088:8080"]
  profiles: ["data","orchestration"]
```

### Endpoints
- `POST /presign/put` — body: `{bucket,key,expires,content_type?}` → `{url, method:"PUT", headers}`  
- `POST /presign/get` — body: `{bucket,key,expires}` → `{url, method:"GET"}`  
- `POST /presign/post` — browser-friendly multipart form fields

Send `Authorization: Bearer <PRESIGN_SHARED_SECRET>` if set.

## ComfyUI Nodes

Copy `comfyui/custom_nodes/pmoves_minio_nodes` into your ComfyUI `custom_nodes/` and restart ComfyUI.

Env for nodes (optional):
```
PMOVES_PRESIGN_URL=http://localhost:8088
PMOVES_PRESIGN_TOKEN=change_me
```

Nodes:
- **PMOVES • Upload Image (MinIO)** — takes `IMAGE`, `bucket`, `key_prefix`, `filename`; returns `s3://…` and a temporary GET URL.
- **PMOVES • Upload File Path (MinIO)** — uploads any on-disk file.

## Quick Test
```bash
# PUT
curl -s http://localhost:8088/presign/put -H "authorization: Bearer $PRESIGN_SHARED_SECRET"   -H 'content-type: application/json'   -d '{"bucket":"outputs","key":"comfy/hello.txt","expires":600,"content_type":"text/plain"}' | jq -r .url |   xargs -I{} curl -s -X PUT -H 'content-type: text/plain' --data 'hello pmoves' '{}'

# GET
curl -s http://localhost:8088/presign/get -H "authorization: Bearer $PRESIGN_SHARED_SECRET"   -H 'content-type: application/json'   -d '{"bucket":"outputs","key":"comfy/hello.txt","expires":600}' | jq -r .url | xargs -I{} curl -s '{}'
```

## Notes
- Limit access by setting `ALLOWED_BUCKETS` and a strong `PRESIGN_SHARED_SECRET`.
- For public Discord embeds, use a publicly reachable MinIO or a CDN in front (or host via presigned GET).
