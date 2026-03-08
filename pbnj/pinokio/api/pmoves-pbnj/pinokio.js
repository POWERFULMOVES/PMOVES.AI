// pbnj/pinokio/api/pmoves-pbnj/pinokio.js
module.exports = {
  title: "PBnJ | PMOVES + Pinokio",
  description: "One-click bridge into your PMOVES lab, KVM4, and local dev stacks.",
  icon: "icon.png",
  menu: [
    { text: "Start AI Lab (K8s)",       href: "lab-up.json" },
    { text: "Stop AI Lab (K8s)",        href: "lab-down.json" },

    { text: "Start KVM4 Stack (K8s)",   href: "kvm4-up.json" },
    { text: "Stop KVM4 Stack (K8s)",    href: "kvm4-down.json" },

    { text: "Local Dev (Docker) - Up",  href: "local-up.json" },
    { text: "Local Dev (Docker) - Down",href: "local-down.json" },
    { text: "Local Dev (Docker) Logs",  href: "local-logs.json" },

    { text: "Cluster Status (AI Lab)",  href: "status.json" },

    { text: "─── VPS Fleet ───",        href: "" },
    { text: "Deploy KVM4-1 (API Gateway)",  href: "kvm4-1-deploy.json" },
    { text: "Deploy KVM4-2 (Data Services)",href: "kvm4-2-deploy.json" },
    { text: "Deploy KVM2 (Exit Node)",      href: "kvm2-deploy.json" },
    { text: "VPS Fleet Status",             href: "vps-status.json" }
  ]
};
