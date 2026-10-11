# Fleet SSH certificate surface (CHIT-bundle wrapped)

One fleet SSH CA; short-TTL user certs issued per enrollment; no forever keys.

## Flow
1. `generate_ca(base_dir)` — one-time fleet CA (private key = funnel secret, NEVER committed).
2. `generate-enrollment.py --role <r> --ttl <t>` — CHIT-signed token (existing flow), ledger row with serial.
3. `issue_cert(token, ca_key, enrollee_pubkey)` — cert validity = min(token remaining, 24h ceiling); principals from ROLES (owner/partner/guest-demo); serial = ledger serial.
4. `wrap_bundle(token, ssh_info, passphrase)` — cert + principals + serial wrapped into the CHIT-signed bundle; verify with the existing `--verify` path.
5. Node side (one-time per node): `sudo ./install_ssh_surface.sh --ca-pub <ca.pub> [--krl <krl>]` — writes TrustedUserCAKeys (+ RevokedKeys) drop-in, `sshd -t`, restart.
6. Revocation: `gen_krl(serials, krl_path, ca_pub)` from ledger serials; redistribute KRL (same installer `--krl` path).

## Security properties
- Cert TTL never exceeds token TTL (hard 24h ceiling); expired tokens cannot mint certs.
- Bundle integrity: any field tamper breaks the HMAC (verified in tests).
- Role principals let sshd Match blocks restrict shells per role (owner/fleet-admin, partner, guest-demo).
- CA private key distribution via secrets funnel only; serials ledger-aligned so KRL revocation is deterministic.

## Tests
`pytest test_ssh_surface.py` — CA generation, TTL ceiling, expired/unknown-role refusal, bundle roundtrip + tamper rejection, KRL generation, trust-line shape.
