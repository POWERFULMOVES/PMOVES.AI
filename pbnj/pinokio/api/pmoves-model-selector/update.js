// update.js — pull the latest gfx1201 fork and rebuild the llama-server binary.
module.exports = {
  run: [
    {
      method: "shell.run",
      when: "{{exists('llama.cpp-rdna4-gfx1201')}}",
      params: {
        path: "llama.cpp-rdna4-gfx1201",
        message: [
          "git pull --ff-only",
          "cmake -B build -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DCMAKE_BUILD_TYPE=Release",
          "cmake --build build --config Release -j"
        ]
      }
    },
    {
      method: "notify",
      params: {
        html: "llama.cpp (gfx1201) updated and rebuilt."
      }
    }
  ]
}
