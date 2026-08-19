# mmx-cli — surface catalog

**Submodule:** [Pmoves-minimax-cli](https://github.com/POWERFULMOVES/Pmoves-minimax-cli) (POWERFULMOVES fork of MiniMax-AI/cli)
**Pin:** 24875e0f04220480a7b146fc8db11ca7b0b278aa
**npm name:** `mmx-cli` (v1.0.19)
**Install path on operator nodes:** `mmx` (resolved via `bin/mmx` → `dist/mmx.mjs`)

The Mavis model cascade has two entry points: the MCP server (`pmoves-minimax-mcp`, stdio via `uvx minimax-mcp`, used by WebUI/Agent Zero) and the CLI (`mmx`, used by the sidecar lane — Pinokio on operator devices, headless scripts, and any pipeline that wants to call models without standing up a full MCP client). This doc catalogs the CLI surface.

The upstream MiniMax-AI/cli repo has its own `AGENTS.md` (5471 bytes, build/test/lint rules) and `SDK.md` (4989 bytes, programmatic API surface) and `ERRORS.md` (9996 bytes, error taxonomy). This doc is the Mavis-side summary: what the operator needs to know to drive the CLI from a sidecar or a script.

## Top-level command tree

```text
mmx
├── auth       login, logout, refresh, status
├── config     set, get
├── file       upload, list, delete
├── image      generate
├── music      generate
├── quota      show
├── search     web, news
├── speech     synthesize, list-voices, clone
├── text       chat
├── video      generate
├── vision     describe
├── help       --command <name>
└── update     self
```

| Command | Purpose | Example |
|---------|---------|---------|
| `mmx auth login` | Authenticate (api-key or OAuth) | `mmx auth login --method api-key --api-key sk-...` |
| `mmx auth status` | Show current auth + quota | `mmx auth status` |
| `mmx config set api-key` | Set the API key non-interactively | `mmx config set api-key sk-...` |
| `mmx text chat` | Single-shot chat | `mmx text chat --model MiniMax-M3 --message "hi"` |
| `mmx text chat --stream` | Streaming chat | `mmx text chat --model MiniMax-M3 --message "..." --stream` |
| `mmx image generate` | Text-to-image | `mmx image generate --model image-01 --prompt "a cat" --out-dir ./out` |
| `mmx video generate` | Text-to-video (sync) | `mmx video generate --model MiniMax-H3 --prompt "..."` |
| `mmx video generate --async` | Text-to-video (returns taskId) | `mmx video generate --prompt "..." --async` |
| `mmx speech synthesize` | TTS | `mmx speech synthesize --voice <id> --text "..." --out ./out.mp3` |
| `mmx speech list-voices` | List available voices | `mmx speech list-voices` |
| `mmx speech clone` | Voice clone from a sample | `mmx speech clone --sample ./sample.wav --name my-voice` |
| `mmx vision describe` | Image captioning | `mmx vision describe --image ./cat.png` |
| `mmx music generate` | Text-to-music | `mmx music generate --prompt "lo-fi beats" --out ./out.mp3` |
| `mmx quota show` | Show rate-limit status | `mmx quota show` |
| `mmx search web` | Web search | `mmx search web --query "..."` |
| `mmx file upload` | Upload a file (for vision, voice-clone, etc.) | `mmx file upload --path ./sample.wav` |
| `mmx update` | Self-update | `mmx update` |

## SDK surface (programmatic)

The CLI is also a library: `import { MiniMaxSDK } from 'mmx-cli/sdk'`. The SDK mirrors the top-level commands but returns parsed results instead of printing them.

```typescript
import { MiniMaxSDK } from 'mmx-cli/sdk';

const sdk = new MiniMaxSDK({
  apiKey: 'sk-xxxxx',         // optional if mmx config set
  region: 'global',           // or 'cn'
});

// Text
const response = await sdk.text.chat({
  model: 'MiniMax-M3',
  messages: [{ role: 'user', content: 'Hello!' }],
  max_tokens: 4096,
});

// Image
const result = await sdk.image.generate({
  model: 'image-01',
  prompt: 'A cat in a spacesuit',
  width: 1024,
  height: 1024,
  n: 1,
});

// Video (sync — waits)
const video = await sdk.video.generate({
  model: 'MiniMax-Hailuo-2.3',
  prompt: 'Ocean waves at sunset',
});

// Video (H3 — V2 with request defaults)
const h3Video = await sdk.video.generate({
  model: 'MiniMax-H3',
  prompt: 'Ocean waves at sunset',
});

// Video (async — returns taskId)
const { taskId } = await sdk.video.generate({
  prompt: 'A robot painting',
  async: true,
});
```

The SDK is the right entry point when the sidecar needs to chain model calls (e.g. caption an image, generate a video from the caption, transcribe the audio). The CLI is the right entry point for one-shot human-in-the-loop use.

## Errors (the operator-relevant subset)

The full ERRORS.md has 70+ error scenarios. The five you'll hit most often:

| Command | Scenario | Message |
|---------|----------|---------|
| `auth login` | `--method api-key` without `--api-key` | `--api-key is required when using --method api-key.` |
| `auth login` | API key validation failed | `API key validation failed.` |
| `text chat` | No `--message` in non-interactive mode | `Missing required argument: --message` |
| `text chat` | Stream disconnected mid-response | `Stream disconnected before response completed.` |
| `image generate` | All images rejected | `Image generation failed: all images were rejected (content policy or model error).` |

For all other errors, see `Pmoves-minimax-cli/ERRORS.md`. The error handling is layered: `errors/codes.ts` (machine codes) → `errors/handler.ts` (formatting) → `errors/api.ts` (HTTP-to-error mapping). Scripts that consume the CLI should match on the error code, not the message.

## Sidecar lane (Pinokio)

The Mavis model cascade calls the CLI from Pinokio apps on operator devices (Pixel phones, Tab Ultras, etc., all on the Tailscale tailnet). The pattern:

1. **Sidecar checks for `mmx` on `$PATH`.** If absent, the app surfaces an actionable error: "Install `mmx-cli` via `npm install -g mmx-cli` or Pinokio's `pmoves-minimax-cli` install recipe."
2. **Sidecar runs `mmx auth login --method api-key --api-key "$MINIMAX_API_KEY"` non-interactively** at app start if the env var is set. This populates `~/.mmx/config.json` with the per-device key.
3. **Sidecar runs `mmx quota show`** at app start to surface rate-limit status to the user.
4. **Sidecar issues one-shot CLI calls** for each model operation. The CLI writes to a temp directory under `MMX_TMP_DIR` (defaults to `$TMPDIR/mmx-$$`); the sidecar watches the directory and ingests results as they appear.

The CLI is the sidecar's preferred entry point because (a) it doesn't need an MCP client, (b) the per-device `~/.mmx/config.json` is a stable place to keep the API key, and (c) the `mmx` binary is a small dependency that ships in the Pinokio app's portable bundle.

## Why not always call the MCP?

The MCP server and the CLI cover the same model surface. The split is **who's calling**:

- **MCP (stdio via `uvx minimax-mcp`):** WebUI, Agent Zero, any tool-aware agent. The MCP is the right surface when the caller is already an MCP client and wants tool-discovery + schema-validated calls.
- **CLI (`mmx`):** sidecar apps, headless scripts, CI jobs, anything that's not an MCP client. The CLI is the right surface when the caller is "just a process that wants to call a model."

If a sidecar app grows an MCP-aware component (e.g. a future Pinokio app that ships Claude Code), the right move is to switch the sidecar to the MCP. For now, the CLI is the lighter path.

## Reference

- Submodule: `Pmoves-minimax-cli/` (PMOVES fork of MiniMax-AI/cli)
- Submodule pin: `24875e0f04220480a7b146fc8db11ca7b0b278aa`
- Upstream CLI repo: https://github.com/MiniMax-AI/cli
- Upstream AGENTS.md: `Pmoves-minimax-cli/AGENTS.md` (build/test/lint)
- Upstream SDK.md: `Pmoves-minimax-cli/SDK.md` (programmatic API)
- Upstream ERRORS.md: `Pmoves-minimax-cli/ERRORS.md` (full error catalog)
- npm package: https://www.npmjs.com/package/mmx-cli
- Mavis model cascade context: `pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml` → `services.minimax.cli`
