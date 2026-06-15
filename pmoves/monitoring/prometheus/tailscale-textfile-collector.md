# Tailscale Metrics via node-exporter Textfile Collector

This runbook wires Tailscale's client metrics into Prometheus **without** opening the
Tailscale web/local API port (`:5252`) or holding a Tailscale API key. Each node writes
its own `tailscaled` metrics to a node-exporter textfile drop, and Prometheus scrapes
node-exporter over the tailnet.

```
tailscale metrics write  ->  /var/lib/node_exporter/textfile_collector/tailscaled.prom
        (systemd timer)                       |
                                              v
node-exporter --collector.textfile.directory=...  exposes them at :9100/metrics
                                              |
                                              v
              Prometheus job_name: node-exporter  (targets: pmoves-<node>:9100)
                                              |
                                              v
              Grafana dashboard "Tailscale Network Health"
```

Metrics exposed (each `tailscaled_*_bytes_total` / `*_packets_total` carries a `path`
label of `direct_ipv4` / `direct_ipv6` / `derp` / `peer_relay_*`):

- `tailscaled_inbound_bytes_total`, `tailscaled_outbound_bytes_total`
- `tailscaled_inbound_packets_total`, `tailscaled_outbound_packets_total`
- `tailscaled_advertised_routes`, `tailscaled_approved_routes`
- `tailscaled_health_messages` and other health gauges

> `tailscale metrics write <file>` emits node-exporter textfile format directly.
> Preview with `tailscale metrics print`.

---

## 1. Prerequisites (per node)

- `tailscale` >= 1.78 (the `metrics write` subcommand).
- `node_exporter` installed and running as a service.
- Textfile collector directory exists and is writable by the metrics writer:

```bash
sudo mkdir -p /var/lib/node_exporter/textfile_collector
```

Ensure node-exporter is started with the textfile collector pointed at it:

```bash
# /etc/default/prometheus-node-exporter  (Debian/Ubuntu) or the unit ExecStart
ARGS="--collector.textfile.directory=/var/lib/node_exporter/textfile_collector"
```

or directly on the binary:

```
node_exporter --collector.textfile.directory=/var/lib/node_exporter/textfile_collector
```

---

## 2. systemd service + timer (preferred)

`tailscale metrics write` is a one-shot. A `.timer` runs it every minute. Write to a
temp file and rename so node-exporter never reads a half-written file.

`/etc/systemd/system/tailscale-metrics.service`:

```ini
[Unit]
Description=Write Tailscale metrics to node-exporter textfile collector
After=tailscaled.service
Wants=tailscaled.service

[Service]
Type=oneshot
# Atomic write: temp file then rename into place.
ExecStart=/usr/bin/tailscale metrics write /var/lib/node_exporter/textfile_collector/.tailscaled.prom.tmp
ExecStartPost=/bin/mv /var/lib/node_exporter/textfile_collector/.tailscaled.prom.tmp /var/lib/node_exporter/textfile_collector/tailscaled.prom
# node-exporter must be able to read the result.
UMask=0022
```

`/etc/systemd/system/tailscale-metrics.timer`:

```ini
[Unit]
Description=Run tailscale-metrics every minute

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
AccuracySec=5s
Unit=tailscale-metrics.service

[Install]
WantedBy=timers.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tailscale-metrics.timer
# Verify
sudo systemctl start tailscale-metrics.service
cat /var/lib/node_exporter/textfile_collector/tailscaled.prom
systemctl list-timers tailscale-metrics.timer
```

---

## 3. cron alternative (if not using systemd)

```cron
# /etc/cron.d/tailscale-metrics  — every minute, atomic rename
* * * * * root /usr/bin/tailscale metrics write /var/lib/node_exporter/textfile_collector/.tailscaled.prom.tmp && /bin/mv /var/lib/node_exporter/textfile_collector/.tailscaled.prom.tmp /var/lib/node_exporter/textfile_collector/tailscaled.prom
```

---

## 4. Prometheus scrape job

Add a `node-exporter` job targeting each fleet node's node-exporter (`:9100`) by its
Tailscale hostname. Prometheus reaches them over the tailnet.

```yaml
  # === Fleet node-exporter (carries Tailscale textfile metrics) ===
  - job_name: node-exporter
    static_configs:
      - targets:
          - pmoves-kvm2:9100
          - pmoves-kvm4-1:9100
          - pmoves-kvm4-2:9100
          - pmoves-4090:9100
```

The matching commented stanza in `prometheus.yml` points back to this runbook. To
activate, uncomment that block (or the snippet above), confirm each node runs
node-exporter with `--collector.textfile.directory` set and the timer enabled, then
reload Prometheus.

---

## 5. Verify end-to-end

```bash
# On a node: metrics present in textfile drop
grep -c tailscaled_ /var/lib/node_exporter/textfile_collector/tailscaled.prom

# node-exporter is surfacing them
curl -s http://pmoves-kvm4-2:9100/metrics | grep tailscaled_inbound_bytes_total

# Prometheus has the target up
#   http://pmoves-kvm4-2:9090/targets  -> job "node-exporter" all UP
# Grafana: open "Tailscale Network Health" dashboard
```

## Why this approach

- No `:5252` local-API exposure and no Tailscale API key / ACL grant needed.
- node-exporter is already the standard host-metrics path; this rides it.
- Per-node atomic writes keep Prometheus from scraping partial files.
