// start.js — GGUF lane: launch the gfx1201 llama-server on the fixed port 8090.
//
// Port 8090 is INTENTIONALLY fixed (not {{port}}): the TensorZero `llamacpp_rocm`
// provider pins http://<host>:8090/v1, and 8080 is reserved for Agent Zero
// fleet-wide. This is the documented exception to the {{port}} convention
// (see README "Intentional fixed port" + PINOKIO guide best-practice #1).
//
// Model path: selected via filepicker over models/ (the registry/gpu-orchestrator
// fallback). URL capture mirrors prototype/system/examples/mochi/start.js lines
// 21-40 and the PINOKIO_LAUNCHER_GUIDE "Critical Pattern Lock".
module.exports = {
  daemon: true,
  run: [
    {
      method: "filepicker.open",
      params: {
        title: "Select a GGUF model file to serve",
        type: "file",
        path: "models",
        filetypes: [["GGUF models", "*.gguf"]]
      }
    },
    {
      method: "local.set",
      params: {
        model_path: "{{input.paths[0]}}"
      }
    },
    {
      method: "shell.run",
      params: {
        path: "llama.cpp-rdna4-gfx1201",
        // Dual-GPU tensor split across both R9700 (gfx1201) cards.
        env: {
          HIP_VISIBLE_DEVICES: "0,1"
        },
        message: [
          "./build/bin/llama-server -m \"{{local.model_path}}\" --host 127.0.0.1 --port 8090 --tensor-split 0.5,0.5"
        ],
        on: [{
          // Generic http URL capture (mirrors the guide's mandated pattern).
          event: "/(http:\\/\\/[0-9.:]+)/",
          done: true
        }]
      }
    },
    {
      // Surface the captured URL as a local var for pinokio.js "Open ... UI".
      method: "local.set",
      params: {
        url: "{{input.event[1]}}"
      }
    }
  ]
}
