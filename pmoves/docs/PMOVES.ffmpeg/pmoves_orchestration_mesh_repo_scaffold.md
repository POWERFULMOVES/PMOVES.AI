# PMOVES Orchestration Mesh

A Docker‑first, MCP‑enabled, multi‑node stack for Agent Zero + Vision (YOLO), FFmpeg‑Whisper ASR, Open Deep Research, LangExtract → Neo4j/Qdrant/Supabase, with profiles for 5090/4090/3090 Ti and Jetson Orin.

> **Status:** Scaffold / starter template. Pin images and tweak env before first run.

---

## 📁 Repo Structure

```
pmoves-orchestration-mesh/
├─ README.md
├─ compose.yml
├─ compose.jetson.yml
├─ compose.archon.yml
├─ Makefile
├─ .env.example
├─ agent-zero.env
├─ services/
│  ├─ yolo/
│  │  ├─ app.py
│  │  └─ requirements.txt
│  ├─ ffmpeg-whisper/
│  │  ├─ Dockerfile
│  │  ├─ server.py
│  │  └─ requirements.txt
│  └─ odr/            # Open Deep Research (optional shim)
│     └─ README.md
├─ grafana/
│  └─ dashboards/
│     └─ gpu-overview.json   # placeholder dashboard
└─ docs/
   ├─ jetson-notes.md
   ├─ archon-notes.md
   └─ operations.md
   ├─ jetson-notes.md
   └─ operations.md
```

---

## 🔧 Quick Start

````bash
cp .env.example .env
# 1) Set image tags for your stack in .env (pinned versions)
# 2) Set secrets (NEO4J_PASSWORD, MINIO creds, SUPABASE_* )
# 3) Pick a profile and launch
make up          # heavy-5090 profile (default)
```bash
cp .env.example .env
# edit secrets, URLs, and image tags
make up          # brings up the heavy-5090 profile by default
````

Other hosts:

```bash
make up-3090     # vision-3090ti profile
make up-4090     # gen-4090 profile
make up-jetson   # edge-jetson (uses compose.jetson.yml override)
make up-archon   # bring up Archon services via compose.archon.yml
```

Access:

- Agent Zero UI → `https://a0.local` (via Traefik rule)
- Neo4j Browser → `http://localhost:7474`
- Qdrant → `http://localhost:6333`
- MinIO Console → `http://localhost:9001`

> Uses Tailscale for cross‑host access (recommended). If not using Traefik DNS, change Host rules accordingly.

---

## 🐳 `compose.yml`

````yaml
version: "3.9"

x-common-env: &common_env
  TZ: America/New_York
  PUID: "1000"
  PGID: "1000"

x-nvidia: &nvidia
  deploy:
    resources:
      reservations:
        devices:
          - capabilities: ["gpu"]
  runtime: nvidia

services:
  traefik:
    image: traefik:${TRAEFIK_TAG:-3.1}
    command:
      - --api.dashboard=true
      - --providers.docker=true
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.ts.acme.tlschallenge=true
      - --certificatesresolvers.ts.acme.email=${ACME_EMAIL}
      - --certificatesresolvers.ts.acme.storage=/letsencrypt/acme.json
    ports: ["80:80","443:443"]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_letsencrypt:/letsencrypt
    labels:
      - traefik.enable=true

  agent_zero:
    image: agent0ai/agent-zero:${AGENT_ZERO_TAG:-latest}
    env_file:
      - agent-zero.env
    environment:
      <<: *common_env
    volumes:
      - a0_data:/data
    labels:
      - traefik.enable=true
      - traefik.http.routers.a0.rule=Host(`${A0_HOST}`)
      - traefik.http.services.a0.loadbalancer.server.port=7860
    depends_on: [neo4j, qdrant]

  neo4j:
    image: neo4j:${NEO4J_TAG:-5.23.0}-community
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
    volumes:
      - neo4j_data:/data
    ports: ["7474:7474","7687:7687"]

  qdrant:
    image: qdrant/qdrant:${QDRANT_TAG:-v1.12.4}
    volumes:
      - qdrant_data:/qdrant/storage
    ports: ["6333:6333"]

  minio:
    image: minio/minio:${MINIO_TAG:-RELEASE.2025-07-10T00-00-00Z}
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_PASS}
    volumes: [ "minio_data:/data" ]
    ports: ["9000:9000","9001:9001"]

  research_http:
    image: ghcr.io/langchain-ai/open-deep-research:${ODR_TAG:-latest}
    environment:
      <<: *common_env
      ODR_PORT: "3000"
    ports: ["3005:3000"]

  langextract_worker:
    image: ghcr.io/google/langextract:${LANGEXTRACT_TAG:-latest}
    environment:
      <<: *common_env
      OUTPUT_GRAPH_BOLT: bolt://neo4j:7687
      OUTPUT_VECTOR_URL: http://qdrant:6333
    volumes:
      - extracts:/extracts
    depends_on: [neo4j, qdrant]

  triton:
    <<: *nvidia
    image: nvcr.io/nvidia/tritonserver:${TRITON_TAG:-24.08}-py3
    command: ["tritonserver","--model-repository=/models"]
    volumes:
      - triton_models:/models
    ports: ["8000:8000","8001:8001","8002:8002"]
    profiles: ["heavy-5090"]

  yolo_serve:
    <<: *nvidia
    image: ultralytics/ultralytics:${ULTRALYTICS_TAG:-8.3.0}
    command: bash -lc "pip install -r requirements.txt && uvicorn app:app --host 0.0.0.0 --port 8080"
    working_dir: /srv
    volumes:
      - ./services/yolo:/srv
      - yolo_models:/root/.cache/ultralytics
    ports: ["8080:8080"]
    profiles: ["vision-3090ti","gen-4090","heavy-5090"]

  ffmpeg_whisper:
    <<: *nvidia
    build:
      context: ./services/ffmpeg-whisper
      args:
        FFMPEG_TAG: ${FFMPEG_TAG:-git}
        BASE_IMAGE: ${FFMPEG_BASE:-ubuntu:22.04}
    image: pmoves/ffmpeg-whisper:${FFMPEG_IMAGE_TAG:-local}
    command: ["python","server.py"]
    volumes:
      - /media/ingest:/ingest
      - /media/out:/out
    ports: ["6060:6060"]
    profiles: ["heavy-5090","gen-4090","vision-3090ti","edge-jetson"]

volumes:
  traefik_letsencrypt:
  a0_data:
  neo4j_data:
  qdrant_data:
  minio_data:
  triton_models:
  yolo_models:
  extracts:
```yaml
version: "3.9"

x-common-env: &common_env
  TZ: America/New_York
  PUID: "1000"
  PGID: "1000"

x-nvidia: &nvidia
  deploy:
    resources:
      reservations:
        devices:
          - capabilities: ["gpu"]
  runtime: nvidia

services:
  traefik:
    image: traefik:3
    command:
      - --api.dashboard=true
      - --providers.docker=true
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.ts.acme.tlschallenge=true
      - --certificatesresolvers.ts.acme.email=${ACME_EMAIL}
      - --certificatesresolvers.ts.acme.storage=/letsencrypt/acme.json
    ports: ["80:80","443:443"]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_letsencrypt:/letsencrypt
    labels:
      - traefik.enable=true

  agent_zero:
    image: agent0ai/agent-zero:latest
    env_file:
      - agent-zero.env
    environment:
      <<: *common_env
    volumes:
      - a0_data:/data
    labels:
      - traefik.enable=true
      - traefik.http.routers.a0.rule=Host(`${A0_HOST}`)
      - traefik.http.services.a0.loadbalancer.server.port=7860
    depends_on: [neo4j, qdrant]

  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
    volumes:
      - neo4j_data:/data
    ports: ["7474:7474","7687:7687"]

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    ports: ["6333:6333"]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_PASS}
    volumes: [ "minio_data:/data" ]
    ports: ["9000:9000","9001:9001"]

  research_http:
    image: ghcr.io/langchain-ai/open-deep-research:latest
    environment:
      <<: *common_env
      ODR_PORT: "3000"
    ports: ["3005:3000"]

  langextract_worker:
    image: ghcr.io/google/langextract:latest
    environment:
      <<: *common_env
      OUTPUT_GRAPH_BOLT: bolt://neo4j:7687
      OUTPUT_VECTOR_URL: http://qdrant:6333
    volumes:
      - extracts:/extracts
    depends_on: [neo4j, qdrant]

  triton:
    <<: *nvidia
    image: nvcr.io/nvidia/tritonserver:24.08-py3
    command: ["tritonserver","--model-repository=/models"]
    volumes:
      - triton_models:/models
    ports: ["8000:8000","8001:8001","8002:8002"]
    profiles: ["heavy-5090"]

  yolo_serve:
    <<: *nvidia
    image: ultralytics/ultralytics:latest
    command: bash -lc "pip install -r requirements.txt && uvicorn app:app --host 0.0.0.0 --port 8080"
    working_dir: /srv
    volumes:
      - ./services/yolo:/srv
      - yolo_models:/root/.cache/ultralytics
    ports: ["8080:8080"]
    profiles: ["vision-3090ti","gen-4090","heavy-5090"]

  ffmpeg_whisper:
    <<: *nvidia
    build:
      context: ./services/ffmpeg-whisper
    image: pmoves/ffmpeg-whisper:local
    command: ["python","server.py"]
    volumes:
      - /media/ingest:/ingest
      - /media/out:/out
    ports: ["6060:6060"]
    profiles: ["heavy-5090","gen-4090","vision-3090ti","edge-jetson"]

volumes:
  traefik_letsencrypt:
  a0_data:
  neo4j_data:
  qdrant_data:
  minio_data:
  triton_models:
  yolo_models:
  extracts:
````

---

## 🐳 `compose.jetson.yml`

````yaml
services:
  yolo_serve:
    platform: linux/arm64
    image: nvcr.io/nvidia/l4t-ml:${JETSON_L4T_TAG:-r36.3.0}-py3
    command: bash -lc "pip install -r requirements.txt && uvicorn app:app --host 0.0.0.0 --port 8080"
    environment:
      NVIDIA_VISIBLE_DEVICES: all
      NVIDIA_DRIVER_CAPABILITIES: all

  ffmpeg_whisper:
    platform: linux/arm64
    build:
      context: ./services/ffmpeg-whisper
      args:
        ARCH: arm64
        BASE_IMAGE: ${JETSON_BASE:-ubuntu:22.04}
    image: pmoves/ffmpeg-whisper:${FFMPEG_IMAGE_TAG:-arm64}
```yaml
services:
  yolo_serve:
    platform: linux/arm64
    image: nvcr.io/nvidia/l4t-ml:r35.4.1-py3
    command: bash -lc "pip install -r requirements.txt && uvicorn app:app --host 0.0.0.0 --port 8080"
    environment:
      NVIDIA_VISIBLE_DEVICES: all
      NVIDIA_DRIVER_CAPABILITIES: all

  ffmpeg_whisper:
    platform: linux/arm64
    build:
      context: ./services/ffmpeg-whisper
      dockerfile: Dockerfile
      args:
        ARCH: arm64
````

---

## 🛠️ `Makefile`

```make
up:
	docker compose --profile heavy-5090 up -d

up-3090:
	docker compose --profile vision-3090ti up -d

up-4090:
	docker compose --profile gen-4090 up -d

up-jetson:
	docker compose -f compose.yml -f compose.jetson.yml --profile edge-jetson up -d

up-archon:
	docker compose -f compose.yml -f compose.archon.yml up -d

logs:
	docker compose logs -f --tail=200

down:
	docker compose down
```make
up:
	docker compose --profile heavy-5090 up -d

up-3090:
	docker compose --profile vision-3090ti up -d

up-4090:
	docker compose --profile gen-4090 up -d

up-jetson:
	docker compose -f compose.yml -f compose.jetson.yml --profile edge-jetson up -d

logs:
	docker compose logs -f --tail=200

down:
	docker compose down
```

---

## 🔑 `.env.example`

```env
# ==== Domains & TLS (Traefik) ====
ACME_EMAIL=you@example.com
A0_HOST=a0.local

# ==== Core service tags (pin for reproducibility) ====
TRAEFIK_TAG=3.1
AGENT_ZERO_TAG=latest
NEO4J_TAG=5.23.0
QDRANT_TAG=v1.12.4
MINIO_TAG=RELEASE.2025-07-10T00-00-00Z
TRITON_TAG=24.08
ULTRALYTICS_TAG=8.3.0
FFMPEG_TAG=git
FFMPEG_BASE=ubuntu:22.04
FFMPEG_IMAGE_TAG=local

# ==== Jetson (set to your JetPack/L4T) ====
JETSON_L4T_TAG=r36.3.0
JETSON_BASE=ubuntu:22.04

# ==== Neo4j ====
NEO4J_PASSWORD=change_me

# ==== MinIO ====
MINIO_USER=admin
MINIO_PASS=strongpassword

# ==== Supabase (used by Agent Zero MCP + Archon) ====
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=sbp_...
SUPABASE_ANON_KEY=ey...
SUPABASE_JWT_SECRET=supersecret

# ==== Optional: ODR/LangExtract ====
ODR_TAG=latest
LANGEXTRACT_TAG=latest

# ==== Archon (service hostnames/ports) ====
ARCHON_HOST=archon.local
ARCHON_API_PORT=8050
ARCHON_MCP_PORT=8051
ARCHON_UI_PORT=8052
````env
# ==== Domains & TLS (Traefik) ====
ACME_EMAIL=you@example.com
A0_HOST=a0.local

# ==== Core service tags (pin for reproducibility) ====
TRAEFIK_TAG=3.1
AGENT_ZERO_TAG=latest
NEO4J_TAG=5.23.0
QDRANT_TAG=v1.12.4
MINIO_TAG=RELEASE.2025-07-10T00-00-00Z
TRITON_TAG=24.08
ULTRALYTICS_TAG=8.3.0
FFMPEG_TAG=git
FFMPEG_BASE=ubuntu:22.04
FFMPEG_IMAGE_TAG=local

# ==== Jetson (set to your JetPack/L4T) ====
JETSON_L4T_TAG=r36.3.0
JETSON_BASE=ubuntu:22.04

# ==== Neo4j ====
NEO4J_PASSWORD=change_me

# ==== MinIO ====
MINIO_USER=admin
MINIO_PASS=strongpassword

# ==== Supabase (used by Agent Zero MCP + clients) ====
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=sbp_...
SUPABASE_ANON_KEY=ey...
SUPABASE_JWT_SECRET=supersecret

# ==== Optional: ODR/LangExtract ====
ODR_TAG=latest
LANGEXTRACT_TAG=latest
```env
# Traefik
ACME_EMAIL=you@example.com
A0_HOST=a0.local

# Neo4j
NEO4J_PASSWORD=change_me

# MinIO
MINIO_USER=admin
MINIO_PASS=strongpassword

# Supabase (used by Agent Zero MCP + clients)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=sbp_...
````

---

## 🤖 `agent-zero.env`

```env
# Allow shell and register MCP servers
A0_ALLOW_SHELL=true

# === MCP servers ===
# Filesystem scoped to /data volume
A0_MCP_SERVERS=
  fs: "mcp://filesystem?roots=/data";
  # Neo4j graph (Cypher tool)
  neo4j: "mcp://neo4j?url=bolt://neo4j:7687&user=neo4j&password=${NEO4J_PASSWORD}";
  # Supabase REST + Vector (custom MCP; swap to your server URL if using an MCP adapter)
  supabase: "mcp://supabase?url=${SUPABASE_URL}&key=${SUPABASE_SERVICE_KEY}";
  # HTTP research endpoint (Open Deep Research)
  research: "mcp://http?endpoint=http://research_http:3000";
  # Archon MCP (tools for RAG/task/project ops/coding)
  archon: "mcp://http?endpoint=http://archon_mcp:${ARCHON_MCP_PORT}";

# === Suggested prompts (inline hints) ===
A0_STARTUP_HINTS=
  "Use 'neo4j.run' to upsert nodes/edges from LangExtract outputs.";
  "Use 'supabase.query' to fetch document chunks then 'neo4j.query' to traverse relationships.";
  "Call 'http.post' to /research with a topic, then pipe sources into LangExtract.";
  "For coding-heavy tasks, call 'archon.tools' endpoints to generate or refactor code, then execute via Agent Zero instruments.";
````env
# Allow shell and register MCP servers
A0_ALLOW_SHELL=true

# === MCP servers ===
# Filesystem scoped to /data volume
A0_MCP_SERVERS=
  fs: "mcp://filesystem?roots=/data";
  # Neo4j graph (Cypher tool)
  neo4j: "mcp://neo4j?url=bolt://neo4j:7687&user=neo4j&password=${NEO4J_PASSWORD}";
  # Supabase REST + Vector (custom MCP; swap to your server URL if using an MCP adapter)
  supabase: "mcp://supabase?url=${SUPABASE_URL}&key=${SUPABASE_SERVICE_KEY}";
  # HTTP research endpoint (Open Deep Research)
  research: "mcp://http?endpoint=http://research_http:3000";

# === Suggested prompts (inline hints) ===
A0_STARTUP_HINTS=
  "Use 'neo4j.run' to upsert nodes/edges from LangExtract outputs.";
  "Use 'supabase.query' to fetch document chunks then 'neo4j.query' to traverse relationships.";
  "Call 'http.post' to /research with a topic, then pipe sources into LangExtract.";
```env
A0_ALLOW_SHELL=true
# Register MCP servers (adjust to your actual MCP plugins)
A0_MCP_SERVERS=
  fs: "mcp://filesystem?roots=/data";
  neo4j: "mcp://neo4j?url=bolt://neo4j:7687&user=neo4j&password=${NEO4J_PASSWORD}";
  supabase: "mcp://supabase?url=${SUPABASE_URL}&key=${SUPABASE_SERVICE_KEY}";
  http: "mcp://browserless?endpoint=http://research_http:3000";
````

---

## 🐍 `services/yolo/requirements.txt`

```text
ultralytics>=8.2.0
fastapi
uvicorn
opencv-python-headless
```

## 🐍 `services/yolo/app.py`

```python
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from ultralytics import YOLO
import tempfile, os

MODEL_NAME = os.getenv("YOLO_MODEL", "yolov8n.pt")
model = YOLO(MODEL_NAME)
app = FastAPI(title="YOLO Serve")

@app.post("/detect")
async def detect(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    results = model.predict(tmp_path, conf=0.25)
    res = results[0]
    boxes = []
    for b in res.boxes:
        boxes.append({
            "xyxy": b.xyxy[0].tolist(),
            "cls": int(b.cls[0]),
            "conf": float(b.conf[0])
        })
    os.unlink(tmp_path)
    return JSONResponse({
        "names": res.names,
        "boxes": boxes
    })
```

---

## 🎙 `services/ffmpeg-whisper/requirements.txt`

```text
fastapi
uvicorn
pydantic
```

## 🎙 `services/ffmpeg-whisper/server.py`

```python
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, PlainTextResponse
import subprocess, tempfile, os

app = FastAPI(title="FFmpeg Whisper ASR")

# Simple HTTP shim that shells out to ffmpeg built with af_whisper.
# Example command:
# ffmpeg -nostdin -hide_banner -y -i input.wav -af "whisper=model=/models/ggml-base.en.bin:language=en:format=json:destination=-" -f null -

FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "/models/ggml-base.en.bin")
LANG = os.getenv("LANGUAGE", "auto")

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    output_format: str = Form("json"),  # json|srt
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        tmp.write(await file.read())
        in_path = tmp.name
    try:
        if output_format == "srt":
            # emit SRT to stdout via destination='-'
            cmd = [
                FFMPEG, "-nostdin", "-hide_banner", "-y",
                "-i", in_path,
                "-af", f"whisper=model={WHISPER_MODEL}:language={LANG}:format=srt:destination=-",
                "-f", "null", "-"
            ]
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            return PlainTextResponse(out.decode("utf-8", errors="ignore"))
        else:
            cmd = [
                FFMPEG, "-nostdin", "-hide_banner", "-y",
                "-i", in_path,
                "-af", f"whisper=model={WHISPER_MODEL}:language={LANG}:format=json:destination=-",
                "-f", "null", "-"
            ]
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            return JSONResponse(content={"whisper": out.decode("utf-8", errors="ignore")})
    finally:
        os.unlink(in_path)
```

## 🎙 `services/ffmpeg-whisper/Dockerfile`

```dockerfile
# NOTE: This Dockerfile attempts to build FFmpeg from source with the af_whisper filter enabled.
# Depending on upstream changes, you may need to tweak configure flags.

ARG BASE=ubuntu:22.04
FROM ${BASE} as build

RUN apt-get update && apt-get install -y \
    autoconf automake build-essential cmake git libtool pkg-config \
    libssl-dev libx264-dev libx265-dev libvpx-dev libfdk-aac-dev libopus-dev \
    libasound2-dev libsndfile1-dev libsoxr-dev libnuma-dev curl wget python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Build whisper.cpp library (used by FFmpeg's whisper filter)
WORKDIR /opt
RUN git clone https://github.com/ggerganov/whisper.cpp.git
WORKDIR /opt/whisper.cpp
RUN make -j$(nproc)

# Build FFmpeg with whisper filter
WORKDIR /opt
RUN git clone https://github.com/FFmpeg/FFmpeg.git ffmpeg
WORKDIR /opt/ffmpeg
# Use master; pin a commit as needed
RUN ./configure \
    --enable-gpl --enable-nonfree \
    --enable-libx264 --enable-libx265 --enable-libvpx --enable-libfdk-aac --enable-libopus \
    --enable-whisper \
    --extra-cflags="-I/opt/whisper.cpp" \
    --extra-ldflags="-L/opt/whisper.cpp/build" && \
    make -j$(nproc) && make install

FROM ubuntu:22.04
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=build /usr/local/bin/ffprobe /usr/local/bin/ffprobe

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY server.py .
ENV FFMPEG_BIN=/usr/local/bin/ffmpeg
ENV WHISPER_MODEL=/models/ggml-base.en.bin
EXPOSE 6060
CMD ["python3","server.py"]
```

> If the `--enable-whisper` flag changes upstream, search FFmpeg’s docs for the current option; update `extra-cflags/ldflags` if the filter expects a different include/lib layout.

---

## 🧭 `docs/operations.md`

- Prefer **pinned tags** from `.env` to ensure reproducible rollouts.
- Use **Watchtower** (optional) for controlled auto‑updates; or pin and update manually.
- Add **NVIDIA DCGM Exporter** + **Prometheus/Grafana** for GPU metrics; ship a default dashboard in `grafana/dashboards`.
- Register additional MCP servers by extending `agent-zero.env`.
- **Supabase Auth wiring**:
  - Store `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_KEY` in `.env`.
  - If using an MCP adapter for Supabase, configure its env to point at these and expose tools like `supabase.query`, `supabase.upsert`, and `supabase.embeddings.search`.
- **Neo4j**: consider `NEO4J_dbms_memory_heap_max__size` envs for larger graphs; backup `/data`.
- For **Jetson**, keep image tags aligned to your **JetPack/L4T**; mismatched CUDA/cuDNN causes runtime errors.

---

## 🧪 Sanity Checks

- `docker compose ps` shows services healthy.
- `curl -F file=@sample.jpg http://localhost:8080/detect` returns boxes.
- `curl -F file=@audio.wav -F output_format=json http://localhost:6060/transcribe` returns JSON/SRT.
- Neo4j Browser reachable; run `:server connect` with `neo4j / ${NEO4J_PASSWORD}`.

---

## 📓 Notes

- Jetson images should be pinned to your L4T/JetPack version. See `docs/jetson-notes.md`.
- Qwen3‑Image / Wan‑2.2 can be added on the 4090 profile in a `services/gen/` folder later.
- Consider adding **NATS** for cross‑node eventing and **ROS 2** bridge for robotics.
- See `docs/archon-notes.md` for connecting Archon UI/API/MCP to Supabase and exposing Archon to Agent Zero over MCP.

---

## 📝 `docs/jetson-notes.md`

- Ensure NVIDIA Container Runtime is installed on Jetsons.
- Match container CUDA/cuDNN to your L4T version.
- Prefer **TensorRT** engines for YOLO; consider a separate `yolo-trt` service.

---

## 📘 README.md (snippet)

```md
# PMOVES Orchestration Mesh

A multi-node Docker stack for Agent Zero + Archon + Vision + ASR + Research + Graph/RAG.

## Profiles
- heavy-5090 — Triton, Agent Zero, Neo4j, Qdrant, ODR, LangExtract
- vision-3090ti — Ultralytics YOLO low-latency server
- gen-4090 — image/video generation services (coming next)
- edge-jetson — ARM64 overrides for Jetson Orin
- archon — Archon UI/API/MCP/Agents services (via compose.archon.yml)

## Bring it up
```bash
cp .env.example .env
make up
make up-archon
```
````md
# PMOVES Orchestration Mesh

A multi-node Docker stack for Agent Zero + Vision + ASR + Research + Graph/RAG.

## Profiles
- heavy-5090 — Triton, Agent Zero, Neo4j, Qdrant, ODR, LangExtract
- vision-3090ti — Ultralytics YOLO low-latency server
- gen-4090 — image/video generation services (coming next)
- edge-jetson — ARM64 overrides for Jetson Orin

## Bring it up
```bash
cp .env.example .env
make up
````

```
```
---

## 🧩 `compose.archon.yml`

```yaml
version: "3.9"

services:
  archon_api:
    image: ghcr.io/coleam00/archon-api:latest
    environment:
      HOST: 0.0.0.0
      PORT: ${ARCHON_API_PORT:-8050}
      SUPABASE_URL: ${SUPABASE_URL}
      SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY}
      SUPABASE_SERVICE_ROLE_KEY: ${SUPABASE_SERVICE_KEY}
    ports: ["${ARCHON_API_PORT:-8050}:8050"]

  archon_mcp:
    image: ghcr.io/coleam00/archon-mcp:latest
    environment:
      HOST: 0.0.0.0
      PORT: ${ARCHON_MCP_PORT:-8051}
      ARCHON_API_URL: http://archon_api:${ARCHON_API_PORT:-8050}
    ports: ["${ARCHON_MCP_PORT:-8051}:8051"]
    depends_on: [archon_api]

  archon_agents:
    image: ghcr.io/coleam00/archon-agents:latest
    environment:
      HOST: 0.0.0.0
      PORT: 8053
      ARCHON_API_URL: http://archon_api:${ARCHON_API_PORT:-8050}
      # Point to your preferred LLMs (OpenAI, Ollama, local inference server)
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OLLAMA_HOST: http://ollama:11434
    depends_on: [archon_api]

  archon_ui:
    image: ghcr.io/coleam00/archon-ui:latest
    environment:
      NEXT_PUBLIC_API_URL: http://archon_api:${ARCHON_API_PORT:-8050}
      NEXT_PUBLIC_MCP_URL: http://archon_mcp:${ARCHON_MCP_PORT:-8051}
    ports: ["${ARCHON_UI_PORT:-8052}:3000"]
    depends_on: [archon_api, archon_mcp]
```

---

## 🗒️ `docs/archon-notes.md`

- **Supabase:** Archon expects a Postgres/PGVector backend (Supabase). Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_KEY` in `.env`. Use the same Supabase project you already configured for vectors to avoid duplication.
- **Service URLs:** The Agent Zero → Archon MCP mapping is configured in `agent-zero.env` as `archon: mcp://http?endpoint=http://archon_mcp:${ARCHON_MCP_PORT}`. Ensure containers share a network (Compose default) or adjust to your hostnames.
- **LLMs:** Point `archon_agents` to your preferred LLMs. For all-local, deploy **Ollama** on the 4090 node and set `OLLAMA_HOST` here. For cloud, set provider keys.
- **Access:** Archon UI on `http://localhost:${ARCHON_UI_PORT}`. From the UI, connect to the backend API/MCP via the configured URLs.
- **Security:** If exposing outside LAN, front with Traefik (add routers) and auth. Keep Supabase keys secret.

