// reset.js — remove the built llama.cpp fork so install.js rebuilds from scratch.
// Does NOT touch downloaded models under models/ (those come from the registry).
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: [
          "rm -rf llama.cpp-rdna4-gfx1201"
        ]
      }
    },
    {
      method: "notify",
      params: {
        html: "llama.cpp (gfx1201) build removed. Run Install to clone + rebuild.",
        type: "warning"
      }
    }
  ]
}
