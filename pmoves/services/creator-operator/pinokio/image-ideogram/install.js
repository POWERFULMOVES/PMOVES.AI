// Brings up PMOVES-Creator ComfyUI + installs the Ideogram-Ultra models/nodes.
// Mirrors installs/IDEOGRAM_ULTRA-MODELS-NODES_INSTALL.bat steps via Pinokio.
//
// Workflow source: the first step clones the whole PMOVES-Creator fork into
// ./ComfyUI, so the saved workflow ships INSIDE the clone at
//   ComfyUI/installs/IDEOGRAM_ULTRA_WORKFLOW-V2.json
// (PMOVES-Creator keeps the creator installers under installs/). We copy from
// there — a self-contained source — rather than from a launcher sibling, so the
// installer never depends on a file that isn't part of the cloned repo.
// (Dependency: the vendoring follow-up must keep installs/IDEOGRAM_ULTRA_WORKFLOW-V2.json
// committed to PMOVES-Creator. If the operator can't find the copied workflow it
// opens it from ComfyUI/installs/ directly via the Workflow menu — see the skill.)
module.exports = {
  run: [
    { method: "shell.run", params: { message: "git clone https://github.com/POWERFULMOVES/PMOVES-Creator ComfyUI" } },
    { method: "script.start", params: { uri: "torch.js", params: { venv: "ComfyUI/venv", path: "ComfyUI" } } },
    { method: "shell.run", params: { path: "ComfyUI", venv: "venv", message: "pip install -r requirements.txt" } },
    // Place the saved workflow where the operator can open it (sourced from the clone).
    { method: "fs.copy", params: { src: "ComfyUI/installs/IDEOGRAM_ULTRA_WORKFLOW-V2.json", dest: "ComfyUI/user/default/workflows/ideogram-ultra.json" } },
    { method: "json.set", params: { "ComfyUI/_pmoves_ready.json": { ready: true, workflow: "image.ideogram-ultra", workflow_src: "ComfyUI/installs/IDEOGRAM_ULTRA_WORKFLOW-V2.json" } } },
  ],
};
