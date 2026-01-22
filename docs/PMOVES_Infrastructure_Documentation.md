# PMOVES.AI Infrastructure Documentation
**The "Darkxside Initiative" Technical Reference**

This document details the underlying infrastructure powering the PMOVES.AI "Visionary AI" ecosystem. It covers the hardware virtualization layer (Proxmox), the private network fabric (Headscale), edge connectivity (Cloudflare, OpenMANET), and local AI automation (Pinokio).

---

## 1. The Hardware Layer: Proxmox Virtual Environment

The "Core" of the PMOVES.AI infrastructure typically runs on bare-metal servers using Proxmox VE for virtualization.

### 1.1 Virtual Machine Layout (Reference Architecture)
We recommend a "Hub-and-Spoke" VM segmentation model:

| VM ID | Role | OS | Resources | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **100** | **Docker Host (Core)** | Ubuntu 22.04 | 32G/8vCPU | Main Docker Swarm/Compose node. Runs PMOVES stack. |
| **101** | **Dev Workstation** | Ubuntu 22.04 | 16G/4vCPU | Persistent development environment with VS Code Server. |
| **102** | **Headscale Hub** | Debian 12 | 2G/2vCPU | Self-hosted VPN control plane ("The Brain"). |
| **103** | **Gateway/Router** | PfSense/OpnSense | 4G/2vCPU | Network firewall and edge routing. |

### 1.2 GPU Passthrough Configuration
To expose NVIDIA GPUs (e.g., RTX 3090/4090) to the **Docker Host (VM 100)** for AI inference:

1.  **Enable IOMMU** in `/etc/default/grub`:
    ```bash
    GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt"
    ```
2.  **Blacklist Nouveau Drivers**:
    ```bash
    echo "blacklist nouveau" >> /etc/modprobe.d/blacklist.conf
    echo "options nouveau modeset=0" >> /etc/modprobe.d/blacklist.conf
    update-initramfs -u
    ```
3.  **Add VFIO Modules** to `/etc/modules`:
    `vfio`, `vfio_iommu_type1`, `vfio_pci`, `vfio_virqfd`
4.  **Assign PCI Device** in Proxmox UI:
    -   Select VM 100 -> Hardware -> Add PCI Device -> Select NVIDIA card.
    -   Check **"All Functions"**, **"ROM-Bar"**, and **"PCI-Express"**.

---

## 2. The Network Fabric: Headscale & Tailscale

Security relies on a **Zero-Trust Network Architecture (ZTNA)**. We do not expose ports to the public internet. Instead, we use **Headscale**, a self-hosted implementation of the Tailscale control server, ensuring total data sovereignty.

### 2.1 The Headscale Advantage
Unlike SaaS VPNs, Headscale keeps the control plane (ACLs, Key Exchange) on our own hardware.
-   **Reference:** [Headscale GitHub](https://github.com/juanfont/headscale)
-   **Access:** Only devices authenticated via Headscale can see the internal API Tier (e.g., Supabase, Qdrant).

### 2.2 Secure GitHub Runners
To allow GitHub Actions to deploy code without opening firewall ports, we treat Runners as nodes on the Tailscale network.

**Architecture:**
1.  **Ephemeral Runner:** The runner spins up.
2.  **Tailscale Sidecar:** It joins the Tailnet using an ephemeral auth key with `tag:ci`.
3.  **Direct Access:** The runner pushes code directly to the private IP of the **Docker Host (VM 100)**.

**GitHub Workflow Example:**
```yaml
steps:
  - name: Tailscale
    uses: tailscale/github-action@v2
    with:
      oauth-client-id: ${{ secrets.TS_OAUTH_CLIENT_ID }}
      oauth-secret: ${{ secrets.TS_OAUTH_SECRET }}
      tags: tag:ci
  - name: Deploy
    run: |
      # Deploy using the private Tailscale IP
      ssh user@100.64.0.5 "docker compose up -d"
```

### 2.3 RustDesk Integration (Peer-to-Peer Remote Access)
For remote desktop access, we utilize RustDesk over Tailscale to avoid public relays.

-   **Why:** Complete self-sovereignty over remote access sessions.
-   **Configuration:**
    1.  Install Tailscale on both the Target (Host) and Client.
    2.  Open RustDesk on the Target.
    3.  On the Client, enter the **Tailscale IP** of the Target.
    4.  Enable **"Direct IP Access"** in RustDesk settings for faster peer-to-peer performance.

---

## 3. The Edge: Cloudflare & OpenMANET

### 3.1 Cloudflare Tunnels (Zero Trust Ingress)
For services that *must* be publicly accessible (e.g., client demos), we use **Cloudflared Tunnels**.
-   **No Open Ports:** No incoming ports 80/443 mapping required.
-   **Zero Trust Policies:** Wrap the endpoint in Cloudflare Access (SSO required) to restrict access to specific emails (e.g., `@powerfulmoves.ai`).

### 3.2 OpenMANET (Off-Grid Resilience)
In disaster scenarios ("The Cataclysm Use Case"), we deploy **OpenMANET** nodes.

**Hardware Stack:**
-   **Controller:** Raspberry Pi 4/5 running OpenWrt + `batman-adv` routing protocol.
-   **Radio:** **Wi-Fi HaLow (IEEE 802.11ah)** adapter for long-range (1km+) high-bandwidth connectivity suitable for voice AI.
-   **Compute:** NVIDIA Jetson Nano running quantized local models (Ollama).

**Gateway Strategy:**
The Raspberry Pi runs as a **Tailscale Subnet Router**. It connects to the internet (via Starlink/Cellular) and advertises the local OpenMANET subnet (e.g., `10.42.0.0/24`) to the global Headscale network. This allows local field devices to reach the "Core" AI Factory transparently.

---

## 4. Local AI Automation: Pinokio

[Pinokio](https://pinokio.co/) is a browser-based AI engine that allows "one-click" installation and execution of complex AI scripts.

**Use Case:** Rapid prototyping and running experimental tools on local workstations (VM 101 or Local Machines).

**Key Scripts:**
-   **FaceFusion:** Real-time face swapping research.
-   **ComfyUI:** Advanced Stable Diffusion workflows.
-   **Ollama:** Local LLM inference.

**Integration:**
PMOVES developers should check the `pinokio/` directory in our repos for custom `.json` install scripts that pre-configure these tools with our preferred settings/models.

---

## 5. Provably Private Compute (PPC)

For high-security partners (UN/NGOs), we utilize **E2B Sandboxes**.

**Architecture:**
-   **Technology:** Firecracker microVMs.
-   **Guarantee:** **Zero-Retention**. The compute environment is instantly destroyed (`kill()`) after the transaction.
-   **Flow:**
    1.  Request arrives via Headscale Tunnel.
    2.  An ephemeral E2B sandbox is spawned (Start-up ~150ms).
    3.  Data is decrypted and processed *only* inside this sandbox.
    4.  Response sent; Sandbox destroyed.
    5.  Audit log records the destruction event.

---

*For more details on service deployment, see [PMOVES_Services_Documentation_Complete.md](./PMOVES_Services_Documentation_Complete.md).*
