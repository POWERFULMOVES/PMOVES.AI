module.exports = {
  version: "1.0",
  title: "PMOVES Creator — Image (Ideogram-Ultra)",
  description: "1-click ComfyUI + Ideogram-Ultra workflow for the creator-operator.",
  icon: "icon.png",
  menu: async (kernel) => {
    const installed = kernel.exists(__dirname, "ComfyUI");
    return [
      { text: installed ? "Start" : "Install",
        href: installed ? "start.js" : "install.js" },
    ];
  },
};
