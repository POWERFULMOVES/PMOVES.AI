# Fleet Memory and Room Portability — B850 findings, 2026-09-08

> **Status:** SCAFFOLD — in progress. Findings were measured on node
> `PMOVES-B850-AI-TOP` (knuckles) during the session of 2026-09-08 and are being
> written down before this node is powered off for a physical NVMe pull. Cipher
> (fleet memory) was unreachable this session, so this file is the durable record.

Sections to follow:

1. There is no fleet-reachable Cipher
2. Loopback binding is a fleet-wide pattern, not a Cipher quirk
3. Room portability is mandated; the capability mechanism is undocumented
4. Node role assignments
5. Harness bugs found in our own instruments
