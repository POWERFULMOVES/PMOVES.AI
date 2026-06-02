# PMOVES Z890 NixOS Configuration Fragment
#
# Include this in /etc/nixos/configuration.nix via:
#   imports = [ /path/to/nixos-post.nix ];
# Then: sudo nixos-rebuild switch
#
# After activation, run the companion imperative wrapper (runs common/*
# modules that can't be declared in Nix, e.g. PMOVES repo clone, tailscale
# enrollment with an auth-key):
#
#   sudo bash deploy/provision/z890/common/00-glances-profile.sh
#   sudo TAILSCALE_AUTHKEY=tskey-xxx bash deploy/provision/z890/common/10-tailscale-enroll.sh
#   sudo bash deploy/provision/z890/common/40-repo-clone.sh
#   sudo bash deploy/provision/z890/common/50-bootstrap-node.sh
#
# (20-docker-install.sh and 30-nvidia-drivers.sh are NO-OPS under NixOS because
# they're declared here instead.)

{ config, pkgs, ... }:

{
  # ── Base PMOVES workstation settings ──────────────────────────────────────
  networking.hostName = "pmoves-z890-nixos";

  # ── Docker + compose (declarative) ────────────────────────────────────────
  virtualisation.docker = {
    enable = true;
    enableNvidia = true;                          # nvidia-container-toolkit equivalent
    daemon.settings = {
      log-driver = "json-file";
      log-opts = { max-size = "100m"; max-file = "3"; };
    };
  };

  # ── NVIDIA RTX 3090 Ti driver ─────────────────────────────────────────────
  services.xserver.videoDrivers = [ "nvidia" ];
  hardware.nvidia = {
    package = config.boot.kernelPackages.nvidiaPackages.stable;
    modesetting.enable = true;
    powerManagement.enable = false;
    nvidiaSettings = true;
    open = false;
  };
  hardware.graphics.enable = true;                # formerly hardware.opengl.enable

  # ── Tailscale (client installed; auth-key applied via imperative 10-*) ────
  services.tailscale = {
    enable = true;
    useRoutingFeatures = "client";
  };

  # ── Baseline packages needed by common/*.sh and PMOVES tooling ────────────
  environment.systemPackages = with pkgs; [
    git curl wget jq unzip htop
    python3 python3Packages.pip
    gnumake gcc
    efibootmgr pciutils lshw
    docker-compose
    nvtopPackages.full
  ];

  # ── Allow wheel users to run sudo without password for provisioning convenience.
  # Remove this for long-term production NixOS hardening.
  security.sudo.wheelNeedsPassword = false;

  # ── Firewall: allow Tailscale + SSH only by default. Docker daemon binds
  # to a Unix socket; no extra ports needed here.
  networking.firewall = {
    enable = true;
    trustedInterfaces = [ "tailscale0" ];
    allowedTCPPorts = [ 22 ];
  };

  # ── /opt/pmoves must exist and be writable by the primary user
  systemd.tmpfiles.rules = [
    "d /opt/pmoves 0755 root root -"
  ];

  # ── Boot: keep GRUB configuration compatible with multi-boot peers
  boot.loader.grub = {
    enable = true;
    useOSProber = true;                           # detect Ubuntu/Fedora/Windows slots
    efiSupport = true;
  };
  boot.loader.efi.canTouchEfiVariables = true;
}
