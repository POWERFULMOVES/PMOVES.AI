// pmoves/services/clap-embed/torch.js
// Multi-arch torch installer for Pinokio/PBNJ packaging of clap-embed.
module.exports = {
  run: [{
    method: "shell.run",
    params: {
      venv: "env",
      message: [
        "{{platform === 'darwin' ? 'pip install torch librosa transformers' :" +
        " gpu === 'nvidia' ? 'pip install torch --index-url https://download.pytorch.org/whl/cu128 && pip install librosa transformers' :" +
        " gpu === 'amd' ? 'pip install torch --index-url https://download.pytorch.org/whl/rocm6.2 && pip install librosa transformers' :" +
        " 'pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install librosa transformers'}}"
      ]
    }
  }, {
    method: "shell.run",
    params: { venv: "env", message: "python -c \"import torch; print(torch.cuda.get_arch_list()); import librosa, transformers\"" }
  }]
};
