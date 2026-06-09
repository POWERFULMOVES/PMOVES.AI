// Brings up PMOVES-Creator ComfyUI + installs the Ideogram-Ultra models/nodes.
// Mirrors installs/IDEOGRAM_ULTRA-MODELS-NODES_INSTALL.bat steps via Pinokio.
module.exports = {
  run: [
    { method: "shell.run", params: { message: "git clone https://github.com/POWERFULMOVES/PMOVES-Creator ComfyUI" } },
    { method: "script.start", params: { uri: "torch.js", params: { venv: "ComfyUI/venv", path: "ComfyUI" } } },
    { method: "shell.run", params: { path: "ComfyUI", venv: "venv", message: "pip install -r requirements.txt" } },
    // Place the saved workflow where the operator can open it.
    { method: "fs.copy", params: { src: "../../IDEOGRAM_ULTRA_WORKFLOW-V2.json", dest: "ComfyUI/user/default/workflows/ideogram-ultra.json" } },
    { method: "json.set", params: { "ComfyUI/_pmoves_ready.json": { ready: true, workflow: "image.ideogram-ultra" } } },
  ],
};
