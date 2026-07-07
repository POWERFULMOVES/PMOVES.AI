// install.js — build llama.cpp (gfx1201 / RDNA4 fork) with HIP for the GGUF lane.
// No model downloads by default: models arrive via the registry / gpu-orchestrator.
// An optional hf.download step exists but ONLY runs when the operator supplies a
// repo id at the prompt — there is never a hardcoded/default model id.
module.exports = {
  requires: {
    // Triggers Pinokio's machine-level AI prerequisites (ROCm/HIP toolchain, hf CLI).
    bundle: "ai"
  },
  run: [
    // 1) Clone the gfx1201 RDNA4 fork (skip if already present).
    {
      method: "shell.run",
      when: "{{!exists('llama.cpp-rdna4-gfx1201')}}",
      params: {
        message: [
          "git clone https://github.com/tlee933/llama.cpp-rdna4-gfx1201"
        ]
      }
    },
    // 2) Configure + build with HIP for gfx1201.
    {
      method: "shell.run",
      params: {
        path: "llama.cpp-rdna4-gfx1201",
        message: [
          "cmake -B build -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DCMAKE_BUILD_TYPE=Release",
          "cmake --build build --config Release -j"
        ]
      }
    },
    // 3) OPTIONAL: pull a GGUF from HuggingFace. Leave the repo id blank to skip.
    //    The id comes entirely from operator input — no default is ever assumed.
    {
      method: "input",
      params: {
        title: "Optional: download a GGUF from HuggingFace",
        description: "Leave blank to skip. Models normally arrive via the registry / gpu-orchestrator.",
        form: [{
          key: "hf_repo",
          title: "HF repo id",
          description: "e.g. TheBloke/Some-Model-GGUF (blank = skip)",
          placeholder: "",
          default: ""
        }, {
          key: "hf_file",
          title: "GGUF filename (optional)",
          description: "Specific *.gguf file inside the repo (blank = whole repo)",
          placeholder: "",
          default: ""
        }]
      }
    },
    {
      method: "hf.download",
      when: "{{input.hf_repo && input.hf_repo.trim().length > 0}}",
      params: {
        path: "models",
        _: "{{input.hf_file && input.hf_file.trim().length > 0 ? [input.hf_repo.trim(), input.hf_file.trim()] : [input.hf_repo.trim()]}}",
        "local-dir": "{{input.hf_repo.trim().split('/').pop()}}"
      }
    },
    {
      method: "notify",
      params: {
        html: "llama.cpp (gfx1201) built. Start the llama-server GGUF lane on :8090, or use Select & Load Model to drive the registry / gpu-orchestrator."
      }
    }
  ]
}
