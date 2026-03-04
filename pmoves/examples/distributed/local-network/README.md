# Local Network Distributed Deployment

Example configuration for deploying PMOVES submodules across machines on the same LAN.

## Scenario

- **DoX** on workstation (192.168.1.20) - RTX 4090 GPU
- **BoTZ** on server (192.168.1.30) - RTX 5090 GPU
- **Tokenism** on NAS (192.168.1.40) - CPU only
- **TensorZero + NATS** on primary server (192.168.1.10)

## Network Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Local Network (192.168.1.0/24)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│   │  192.168.1.10    │  │  192.168.1.20    │  │  192.168.1.30    │      │
│   │  Primary Server  │  │  Workstation     │  │  GPU Server      │      │
│   │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │      │
│   │  │ TensorZero │  │  │  │ PMOVES-DoX │  │  │  │ PMOVES-BoTZ│  │      │
│   │  │   :3030    │  │  │  │   :8484    │  │  │  │   :2091    │  │      │
│   │  ├────────────┤  │  │  ├────────────┤  │  │  ├────────────┤  │      │
│   │  │ NATS       │  │  │  │ NATS WS    │  │  │  │ Cipher     │  │      │
│   │  │   :4222    │  │  │  │   :9223    │  │  │  │   :8081    │  │      │
│   │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │      │
│   │  RTX 5090        │  │  RTX 4090        │  │  RTX 3090Ti      │      │
│   └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                          │
│   ┌──────────────────┐                                                   │
│   │  192.168.1.40    │                                                   │
│   │  NAS/Tokenism    │                                                   │
│   │  ┌────────────┐  │                                                   │
│   │  │ Tokenism   │  │                                                   │
│   │  │   :5000    │  │                                                   │
│   │  └────────────┘  │                                                   │
│   │  CPU only        │                                                   │
│   └──────────────────┘                                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Setup

### 1. Primary Server (192.168.1.10)

Deploy TensorZero and NATS as the central hub:

```bash
cd PMOVES.AI
docker compose -f pmoves/docker-compose.yml up -d tensorzero nats
```

### 2. Workstation - DoX (192.168.1.20)

```bash
cd PMOVES-DoX
cp ../pmoves/examples/distributed/local-network/dox.env .env.distributed
docker compose -f docker-compose.yml -f docker-compose.distributed.yml \
  --env-file .env.distributed up -d
```

### 3. GPU Server - BoTZ (192.168.1.30)

```bash
cd PMOVES-BoTZ
cp ../pmoves/examples/distributed/local-network/botz.env .env
docker compose -f docker-compose.yml -f docker-compose.distributed.yml \
  --profile cipher --profile tools up -d
```

### 4. NAS - Tokenism (192.168.1.40)

```bash
cd PMOVES-ToKenism-Multi
cp ../pmoves/examples/distributed/local-network/tokenism.env .env
docker compose up -d
```

## Verification

```bash
# Test DoX
curl http://192.168.1.20:8484/healthz

# Test BoTZ
curl http://192.168.1.30:2091/health

# Test Tokenism
curl http://192.168.1.40:5000/health

# Test cross-service (DoX → TensorZero)
curl http://192.168.1.10:3030/health
```

## Firewall Rules

Ensure these ports are open between machines:

| Port | Service | Direction |
|------|---------|-----------|
| 4222 | NATS Core | All → Primary |
| 9223 | NATS WS | Frontend → DoX |
| 3030 | TensorZero | All → Primary |
| 8484 | DoX Backend | All → Workstation |
| 2091 | BoTZ Gateway | All → GPU Server |
| 5000 | Tokenism | All → NAS |
