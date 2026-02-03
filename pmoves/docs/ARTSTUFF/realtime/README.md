# VibeVoice Realtime (Pinokio)

This Pinokio launcher installs and runs the realtime VibeVoice TTS demo from [microsoft/VibeVoice](https://github.com/microsoft/VibeVoice), configured to use the [microsoft/VibeVoice-Realtime-0.5B](https://huggingface.co/microsoft/VibeVoice-Realtime-0.5B) model.

The app starts the official `demo/vibevoice_realtime_demo.py` websocket server and exposes its web UI through Pinokio.

## What this app does

- Clones the official VibeVoice repository into the local `app/` folder
- Creates an isolated Python environment and installs `vibevoice` with `uv pip install -e .`
- Downloads the `microsoft/VibeVoice-Realtime-0.5B` model with Hugging Face
- Launches the realtime websocket demo server and web UI

## How to use

1. Open this project in Pinokio.
2. Click **Install**.
   - This clones `microsoft/VibeVoice` into `app/`, creates an `env` virtual environment, installs dependencies, and downloads the realtime model weights.
3. After installation completes, click **Start**.
   - The launcher runs:
     ```bash
     python demo/vibevoice_realtime_demo.py \
       --model_path models/VibeVoice-Realtime-0.5B \
       --port <AUTO_PORT>
     ```
   - The server binds to `0.0.0.0` on an automatically selected free port.
4. Once the server prints an `http://...` URL, Pinokio captures it and shows an **Open Web UI** tab.

### URLs

When running locally, you can access the UI via:

- `http://127.0.0.1:<PORT>` directly, or
- `https://<PORT>.localhost` via Pinokio's HTTPS proxy.

Pinokio automatically uses the captured URL for the **Open Web UI** menu item.

> Note: The realtime model is designed for GPU inference (CUDA or Apple Silicon). CPU-only performance may be poor or unsupported.

## Programmatic API

The realtime demo exposes:

- A WebSocket streaming endpoint at `GET /stream`
- A configuration endpoint at `GET /config`

## Local speaker bridge (PMOVES Flute → audible audio)

The VibeVoice realtime server only produces audio bytes; it does not automatically play sound on your machine.

PMOVES includes an optional **host-run** helper that calls Flute Gateway and plays audio through your local speakers:

1. Start Flute + VibeVoice (Docker profiles already handle this in the PMOVES stack).
2. Start the local speaker API:
   ```bash
   make -C pmoves voice-speaker-start
   ```
3. Speak a message:
   ```bash
   make -C pmoves voice-say MSG="Hello from PMOVES"
   ```

Notes:
- The speaker runs on `http://127.0.0.1:8120` by default and is meant for local development.
- Playback prefers `ffplay` (install `ffmpeg` if you don’t have it).

### Follow agent responses (auto-speak)

To auto-speak responses as they arrive on NATS:

```bash
make -C pmoves voice-speaker-start
make -C pmoves voice-follow-start
```

Now any `voice.agent.response.v1` (and `agent.response.v1`) messages will be spoken locally.

Below, `BASE_URL` is the server root, for example:

- `http://127.0.0.1:<PORT>` (local direct access), or
- `https://<PORT>.localhost` (Pinokio HTTPS proxy).

### 1. Discover available voices (`GET /config`)

#### Curl

```bash
curl "$BASE_URL/config"
```

#### Python

```python
import requests

BASE_URL = "http://127.0.0.1:3000"  # replace with your port
resp = requests.get(f"{BASE_URL}/config")
resp.raise_for_status()
print(resp.json())
```

#### JavaScript (browser or Node)

```js
const BASE_URL = "https://3000.localhost"; // replace with your port

async function getConfig() {
  const res = await fetch(`${BASE_URL}/config`);
  const data = await res.json();
  console.log(data);
}

getConfig();
```

### 2. Stream audio (`WS /stream`)

The websocket endpoint streams 24 kHz PCM16 audio chunks.

Query parameters:

- `text` – required input text to synthesize
- `cfg` – optional guidance scale (default ~1.5)
- `steps` – optional diffusion steps
- `voice` – optional voice preset; see `/config` response

#### JavaScript (browser)

```js
const BASE_URL = "https://3000.localhost"; // replace with your port
const ws = new WebSocket(`${BASE_URL.replace("https", "wss")}/stream?text=${encodeURIComponent("Hello from VibeVoice!")}`);

ws.binaryType = "arraybuffer";

ws.onmessage = (event) => {
  if (typeof event.data === "string") {
    // Log messages (JSON logs from the backend)
    console.log("log:", event.data);
  } else {
    // Binary audio chunk (Int16 PCM at 24 kHz)
    const audioBuffer = event.data;
    // You can push this into a Web Audio API player or a custom audio pipeline.
  }
};
```

#### Python (websocket client)

```python
import asyncio
import struct

import websockets

BASE_URL = "ws://127.0.0.1:3000"  # replace with your port
TEXT = "Hello from VibeVoice!"


async def main():
  uri = f"{BASE_URL}/stream?text={TEXT}"
  async with websockets.connect(uri) as ws:
    async for message in ws:
      if isinstance(message, bytes):
        # 16-bit PCM, 24 kHz
        samples = struct.unpack("<" + "h" * (len(message) // 2), message)
        print(f"Received {len(samples)} samples")
      else:
        print("log:", message)


asyncio.run(main())
```

### 3. Curl example for health/config check

Even though `curl` does not natively support WebSocket streaming, you can still use it to verify the server and query configuration:

```bash
curl "$BASE_URL/config"
```

This is useful to confirm that the server is running and the model has loaded correctly.

