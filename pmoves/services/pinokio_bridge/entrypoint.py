#!/usr/local/bin/python3
"""Entrypoint for pinokio_bridge container.

Resolves the Docker gateway IP and writes ~/.pinokio/config.json so that
pterm (Node.js, on PATH via the PINOKIO_HOME bind-mount) can reach the
host's Pinokio control plane at :42000.
"""
import json
import os
import socket
import sys


def _resolve_gateway() -> str:
    """Best-effort resolution of the host gateway IP."""
    candidates = []

    # 1. /proc/net/route — the default route gateway in hex
    try:
        with open("/proc/net/route") as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    hex_ip = parts[2]
                    if len(hex_ip) == 8 and hex_ip != "00000000":
                        octets = [str(int(hex_ip[i:i+2], 16)) for i in range(6, -1, -2)]
                        candidates.append(".".join(octets))
    except Exception:
        pass

    # 2. host.docker.internal (set via extra_hosts in compose)
    try:
        candidates.append(socket.gethostbyname("host.docker.internal"))
    except Exception:
        pass

    # 3. Known Docker bridge subnets (pmoves networks use 172.30.x.1)
    for subnet in ["172.30.2.1", "172.30.1.1", "172.17.0.1"]:
        candidates.append(subnet)

    # Probe each candidate for an open :42000
    for ip in candidates:
        try:
            s = socket.socket()
            s.settimeout(1)
            s.connect((ip, 42000))
            s.close()
            return ip
        except Exception:
            pass

    return candidates[0] if candidates else "172.30.2.1"


def main():
    gw = _resolve_gateway()
    home = os.environ.get("PINOKIO_HOME", "/pinokio")
    config_dir = os.path.expanduser("~/.pinokio")
    os.makedirs(config_dir, exist_ok=True)
    config = {
        "home": home,
        "access": {"protocol": "http", "host": gw, "port": 42000},
    }
    config_path = os.path.join(config_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f)
    print(f"[pinokio-bridge] Pinokio control plane: {gw}:42000", flush=True)

    if len(sys.argv) < 2:
        print("[pinokio-bridge] No command specified", file=sys.stderr)
        sys.exit(1)

    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
