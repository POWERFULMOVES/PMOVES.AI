# TOPIC 1: SLSA Provenance with GitHub Apps — Full Technical Research

## 1. How `actions/attest-build-provenance` Works Internally (Step by Step)

### Internal Architecture

The action is a wrapper around the `@actions/attest` npm package (as of v4). The internal execution flow is:

1. **Subject Resolution**: The action resolves the artifact subject using one of five methods:
   - `subject-path`: Direct file path on the runner filesystem
   - `subject-name` + `subject-digest`: Container image reference + SHA-256 digest
   - `subject-checksums`: Path to a checksums file (compatible with goreleaser, `sha256sum` output)
   - `base64-subjects`: Base64-encoded SHA-256 digest string for generic artifacts
   - Automatic detection from `push-to-registry` when enabled

2. **OIDC Token Acquisition**: The action requests a GitHub OIDC token using the `id-token: write` permission. This token contains claims including:
   - `sub`: The workflow identity (e.g., `repo:owner/repo:ref:refs/heads/main`)
   - `workflow`: The workflow file path
   - `ref`: The git ref being built
   - `sha`: The commit SHA
   - `actor`: The user or app that triggered the workflow
   - `repository`: The full repository name

3. **Sigstore Certificate Issuance**: The OIDC token is presented to a Sigstore Fulcio CA instance:
   - **Public repositories** → Public-good Sigstore instance (`fulcio.sigstore.dev`)
   - **Private/Internal repositories** → GitHub private Sigstore instance
   - Fulcio issues a short-lived X.509 certificate (typically 10 minutes) binding the OIDC identity to an ephemeral keypair
   - The certificate contains the OIDC identity in the Subject Alternative Name (SAN)

4. **Provenance Predicate Generation**: The action constructs a SLSA provenance predicate in in-toto Statement format containing:
   - `builder.id`: Identifies the build platform (e.g., `https://github.com/actions/attest-build-provenance@v2.2.0`)
   - `buildType`: The SLSA build type identifier
   - `invocation.configSource`: The git ref and repository of the workflow
   - `invocation.parameters`: Build inputs and environment
   - `invocation.environment`: Runner environment details (GitHub-hosted runner identification)
   - `metadata.buildStartedOn`, `buildFinishedOn`: Timestamps
   - `materials`: List of source materials (git commit SHA, ref)
   - `resolvedDependencies`: Any resolved dependencies

5. **DSSE Envelope Creation**: The provenance predicate is wrapped in an in-toto Statement (`_type: https://in-toto.io/Statement/v1`, `predicateType: https://slsa.dev/provenance/v1`), then wrapped in a DSSE envelope with `payloadType: application/vnd.in-toto+json`.

6. **Signing**: The DSSE envelope is signed with the ephemeral private key. The signature is included in the DSSE envelope's `signatures` array.

7. **Transparency Log Upload**: The signed attestation is uploaded to a Rekor transparency log instance:
   - Public repos → `rekor.sigstore.dev`
   - Private repos → GitHub private Rekor instance
   - This creates an immutable, append-only record of the signing event

8. **GitHub Attestations API Upload**: The complete attestation (Sigstore Bundle including DSSE envelope + certificate chain + tlog entry) is uploaded to the GitHub Attestations API and associated with the repository.

### Action Inputs

| Input | Type | Description |
|-------|------|-------------|
| `subject-path` | string | Path to a single artifact file on the runner |
| `subject-name` | string | Container image name (e.g., `ghcr.io/user/app`) — exclude tags |
| `subject-digest` | string | SHA-256 digest of the container image |
| `subject-checksums` | string | Path to a checksums file (goreleaser/sha256sum format) |
| `base64-subjects` | string | Base64-encoded SHA-256 digest for generic artifacts |
| `push-to-registry` | bool | Whether to push attestation to OCI registry |
| `github-token` | string | GitHub token for API auth (defaults to `GITHUB_TOKEN`) |

### Action Outputs

| Output | Description |
|--------|-------------|
| `bundle-path` | Filesystem path to the Sigstore Bundle JSON file |
| `attestation-id` | GitHub attestation ID for API references |
| `attestation-url` | GitHub attestation URL for human access |

### Required Permissions

| Permission | Purpose | Required |
|------------|---------|----------|
| `id-token: write` | OIDC token for Sigstore Fulcio certificate | **Yes** |
| `attestations: write` | Persist attestation to GitHub Attestations API | **Yes** |
| `contents: read` | Access repository content (for file-based subjects) | Conditional |
| `packages: write` | Push attestation to container registry | Conditional |
| `actions: read` | Read workflow run information for provenance | Recommended |

### Subject Limits
- Maximum **1024 subjects** per single attestation call
- For larger artifact sets, batch into multiple attestation calls

---

## 2. SLSA Level Achieved (SLSA v1.0 Level 3)

### SLSA v1.0 Build Level Hierarchy

SLSA v1.0 defines Build Levels 0-3 (v0.1 used 1-4; v1.0 removed Source track aspects):

| Level | Name | Key Requirement |
|-------|------|----------------|
| **L0** | None | No requirements — dev/test builds |
| **L1** | Documented | Provenance exists showing build platform, process, top-level inputs. Producer follows consistent process and distributes provenance. |
| **L2** | Hosted | All of L1 + dedicated infrastructure (not individual workstation), provenance tied to infrastructure via digital signature, downstream verification validates provenance authenticity. |
| **L3** | Hardened | All of L2 + build platform prevents runs from influencing each other, signing secrets inaccessible to user-defined build steps. |

### What `actions/attest-build-provenance` Achieves

**SLSA v1.0 Build Level 3** when used on GitHub-hosted runners.

### Why L3 (Not Just L2)

The critical L3 differentiators that GitHub-hosted runners + this action satisfy:

1. **Isolated builds**: GitHub-hosted runners provide VM-level isolation between workflow runs, even within the same project. One run cannot access another run's environment, filesystem, or network namespace.

2. **Non-falsifiable provenance**: The signing key (ephemeral keypair) and the Fulcio-issued certificate are generated and managed by the platform infrastructure — NOT by user-defined build steps. A compromised build step cannot:
   - Access the private signing key
   - Forge the provenance signature
   - Tamper with the certificate chain
   - Without exploiting the GitHub Actions platform itself (significantly harder than L2)

3. **Platform-controlled builder identity**: The `builder.id` in the provenance is a verified, platform-controlled value (`https://github.com/actions/attest-build-provenance@<version>`), not something the user can set arbitrarily.

### L2 vs L3: Practical Difference

- **L2**: Prevents tampering AFTER the build through digital signatures. An adversary who compromises the build process can forge provenance, but cannot modify already-published provenance. Deters unsophisticated adversaries.
- **L3**: Prevents tampering DURING the build. Even an insider threat, compromised credentials, or malicious tenant cannot forge provenance without exploiting the build platform itself. Requires a "difficult exploit of the build process" to defeat.

### Verification Requirement

SLSA v1.0 emphasizes that provenance is only useful if verified downstream. The recommended verification pattern:

```bash
gh attestation verify <artifact> --repo <owner/repo>
```

Or with cosign:
```bash
cosign verify-attestation \
  --type slsaprovenance \
  --certificate-identity-regexp 'https://github.com/<owner>/<repo>/.github/workflows/.+' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  <image-ref>
```

---

## 3. Using a GitHub App Identity for Signing with Cosign (Instead of OIDC)

### Why Use GitHub App Keys Instead of OIDC

- Self-hosted runners may not support OIDC token issuance properly
- You want a stable identity tied to the GitHub App rather than per-workflow ephemeral identity
- You need to sign outside of GitHub Actions context
- You want to avoid publishing identity information to the public Rekor transparency log
- You need deterministic key identity for policy enforcement

### Method: Import GitHub App Private Key into Cosign Format

**Step 1: Obtain the GitHub App Private Key**

The GitHub App private key is a PEM file (RSA PKCS#1 or ECDSA) downloaded from GitHub App settings. It looks like:

```
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF...(base64 content)...
-----END RSA PRIVATE KEY-----
```

**Step 2: Import into Cosign Format**

Cosign only accepts RSA and ECDSA PEM keys for import. Note: Cosign only supports RSA PKCS#1.5 padded keys.

```bash
cosign import-key-pair --key github-app.private-key.pem
Enter password for private key: [set a cosign encryption password]
Enter password for private key again: [confirm]
Private key written to import-cosign.key
Public key written to import-cosign.pub
```

This creates two files:
- `import-cosign.key` — Cosign-encrypted private key (add to GitHub Secrets as `COSIGN_PRIVATE_KEY`)
- `import-cosign.pub` — Public key (distribute to verifiers)

**Step 3: Store in GitHub Secrets**

```bash
gh secret set COSIGN_PRIVATE_KEY < import-cosign.key
gh secret set COSIGN_PASSWORD --body "your-password"
```

Distribute `import-cosign.pub` to consumers via repository, documentation, or a well-known URL.

**Step 4: Sign in GitHub Actions Workflow**

```yaml
name: Build and Sign with GitHub App Key
on:
  push:
    branches: ["main"]

permissions:
  contents: read
  packages: write

jobs:
  build-and-sign:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build artifact
        run: |
          mkdir -p dist
          go build -o dist/myapp ./cmd/myapp

      - name: Install cosign
        uses: sigstore/cosign-installer@v3

      - name: Sign the blob with GitHub App key
        env:
          COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}
        run: |
          echo "${{ secrets.COSIGN_PRIVATE_KEY }}" > /tmp/cosign.key
          chmod 600 /tmp/cosign.key

          # Sign the binary blob
          cosign sign-blob \
            --key /tmp/cosign.key \
            --output-signature dist/myapp.sig \
            --output-certificate dist/myapp.pem \
            dist/myapp

          rm -f /tmp/cosign.key

      - name: Sign container image with GitHub App key
        env:
          COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}
        run: |
          echo "${{ secrets.COSIGN_PRIVATE_KEY }}" > /tmp/cosign.key
          chmod 600 /tmp/cosign.key

          # Sign using image digest (NOT tag)
          cosign sign \
            --key /tmp/cosign.key \
            --tlog-upload=false \
            ghcr.io/${{ github.repository }}@${{ github.sha }}

          rm -f /tmp/cosign.key

      - name: Create and sign SLSA provenance attestation
        env:
          COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}
        run: |
          echo "${{ secrets.COSIGN_PRIVATE_KEY }}" > /tmp/cosign.key
          chmod 600 /tmp/cosign.key

          # Create a SLSA provenance predicate manually
          cat > /tmp/provenance.json <<'EOF'
          {
            "_type": "https://in-toto.io/Statement/v1",
            "subject": [{
              "name": "myapp",
              "digest": {"sha256": "$(sha256sum dist/myapp | cut -d' ' -f1)"}
            }],
            "predicateType": "https://slsa.dev/provenance/v1",
            "predicate": {
              "builder": {"id": "https://github.com/my-org/my-repo/.github/workflows/build.yml"},
              "buildType": "https://github.com/my-org/my-repo/build@v1",
              "invocation": {
                "configSource": {
                  "uri": "git+https://github.com/my-org/my-repo.git",
                  "digest": {"sha1": "${{ github.sha }}"},
                  "entryPoint": ".github/workflows/build.yml"
                },
                "parameters": {},
                "environment": {
                  "github_workflow": "build.yml",
                  "github_actor": "${{ github.actor }}",
                  "github_ref": "${{ github.ref }}"
                }
              },
              "materials": [{
                "uri": "git+https://github.com/my-org/my-repo.git",
                "digest": {"sha1": "${{ github.sha }}"}
              }]
            }
          }
          EOF

          # Sign the attestation
          cosign attest \
            --key /tmp/cosign.key \
            --predicate /tmp/provenance.json \
            --tlog-upload=false \
            ghcr.io/${{ github.repository }}@${{ github.sha }}

          rm -f /tmp/cosign.key
```

**Step 5: Verify with the Public Key**

```bash
# Verify a signed blob
cosign verify-blob \
  --key cosign.pub \
  --signature dist/myapp.sig \
  --certificate dist/myapp.pem \
  dist/myapp

# Verify a signed container image
cosign verify \
  --key cosign.pub \
  --insecure-ignore-tlog \
  ghcr.io/my-org/my-repo@sha256:abc123...

# Verify an attestation on a container image
cosign verify-attestation \
  --key cosign.pub \
  --type slsaprovenance \
  --insecure-ignore-tlog \
  ghcr.io/my-org/my-repo@sha256:abc123...
```

### Key Trade-off: GitHub App Key vs OIDC Keyless

| Aspect | OIDC Keyless | GitHub App Key |
|--------|-------------|----------------|
| Key management | Automatic (ephemeral) | Manual (persistent) |
| Identity in cert | Workflow-specific OIDC identity | App identity only |
| Transparency log | Required (public by default) | Optional (`--tlog-upload=false`) |
| Self-hosted runners | Not supported (no OIDC) | Supported |
| SLSA level achievable | L3 (on GitHub-hosted) | L2 at best (no platform isolation guarantee) |
| Revocation | Certificate expires in 10min | Must rotate key manually |
| Privacy | Identity published to Rekor | Private if tlog skipped |

### Alternative: Use KMS for GitHub App Key

Instead of storing the private key in GitHub Secrets, store it in a KMS:

```bash
# Sign using a KMS-stored key (no import needed)
cosign sign --key awskms://arn:aws:kms:us-east-1:123456:key/abcd \
  ghcr.io/my-org/my-app@sha256:abc123
```

---

## 4. DSSE (Dead Simple Signing Envelope) Attestation Format — Full Structure

### Specification

DSSE v1.0 is defined in the [secure-systems-lab/dsse](https://github.com/secure-systems-lab/dsse) repository. It is a minimal JSON format for signing arbitrary data.

### Envelope Structure

```json
{
  "payload": "<Base64-encoded JSON in-toto Statement>",
  "payloadType": "application/vnd.in-toto+json",
  "signatures": [
    {
      "keyid": "<hint identifying the signing key, often empty string>",
      "sig": "<Base64-encoded signature bytes>"
    }
  ]
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `payload` | string (base64) | SHOULD | Base64-encoded serialized payload data (the in-toto Statement JSON) |
| `payloadType` | string | MUST | MIME type of the payload. For in-toto: `application/vnd.in-toto+json`. The `payloadType` is signed along with the payload. |
| `signatures` | array | MUST | Array of signature objects. DSSE spec allows multiple; Sigstore Bundle restricts to exactly one. |
| `signatures[].keyid` | string | SHOULD | Hint indicating which key was used. Often empty string `""` in Sigstore context (key identified via certificate chain instead). |
| `signatures[].sig` | string (base64) | MUST | Base64-encoded raw signature bytes. |

### Full Example with SLSA Provenance Payload

Decoded DSSE envelope with a real SLSA provenance attestation:

```json
{
  "payloadType": "application/vnd.in-toto+json",
  "signatures": [
    {
      "sig": "MEUCIE1FVy2z7JiDTAlOCjgWjpy0Psc/8wKhLyUYDU8+PorNAiEAocQ4ps8gBGD4d1ixw3LFV83hWNubDUvQvZBFIhC53qw=",
      "keyid": ""
    }
  ],
  "payload": "eyJfdHlwZSI6Imh0dHBzOi8vaW4tdG90by5pby9TdGF0ZW1lbnQvdjEiLCJzdWJqZWN0IjpbeyJuYW1lIjoiZ2hjci5pby9vd25lci9yZXBvL2FwcCIsImRpZ2VzdCI6eyJzaGEyNTYiOiJhYmMxMjM0NTY3ODkwZGVmMTIzNDU2Nzg5MGFiYzEyMzQ1Njc4OTBkZWYxMjM0NTY3ODkwYWJjMTIzNDU2Nzg5MGRlZjEyMzQ1Njc4OTAifX1dLCJwcmVkaWNhdGVUeXBlIjoiaHR0cHM6Ly9zbHNhLmRldi9wcm92ZW5hbmNlL3YxIiwicHJlZGljYXRlIjp7ImJ1aWxkZXIiOnsiaWQiOiJodHRwczovL2dpdGh1Yi5jb20vYWN0aW9ucy9hdHRlc3QtYnVpbGQtcHJvdmVuYW5jZUB2Mi4yLjAifSwiYnVpbGRUeXBlIjoiY3VzdG9tIiwiaW52b2NhdGlvbiI6eyJjb25maWdTb3VyY2UiOnsidXJpIjoiZ2l0K2h0dHBzOi8vZ2l0aHViLmNvbS9vd25lci9yZXBvLmdpdCIsImRpZ2VzdCI6eyJzaGExIjoiYWJjMTIzNDU2Nzg5MGFiYzEyMzQ1Njc4OTBkZWYxMjM0NTY3ODkwIn0sImVudHJ5UG9pbnQiOiIuZ2l0aHViL3dvcmtmbG93cy9idWlsZC55bWwifSwicGFyYW1ldGVycyI6e30sImVudmlyb25tZW50Ijp7ImdpdGh1Yl93b3JrZmxvdyI6ImJ1aWxkLnltbCIsImdpdGh1Yl9hY3RvciI6ImRldm9wcyIsImdpdGh1Yl9yZWYiOiJyZWZzL2hlYWRzL21haW4ifX0sIm1hdGVyaWFscyI6W3sidXJpIjoiZ2l0K2h0dHBzOi8vZ2l0aHViLmNvbS9vd25lci9yZXBvLmdpdCIsImRpZ2VzdCI6eyJzaGExIjoiYWJjMTIzNDU2Nzg5MGFiYzEyMzQ1Njc4OTBkZWYxMjM0NTY3ODkwIn19XX19"
}
```

Decoded payload (the in-toto Statement):

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "ghcr.io/owner/repo/app",
      "digest": {
        "sha256": "abc1234567890def1234567890abc1234567890def1234567890abc1234567890def1234567890abc1234567890"
      }
    }
  ],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "builder": {
      "id": "https://github.com/actions/attest-build-provenance@v2.2.0"
    },
    "buildType": "custom",
    "invocation": {
      "configSource": {
        "uri": "git+https://github.com/owner/repo.git",
        "digest": {
          "sha1": "abc1234567890abc1234567890def1234567890"
        },
        "entryPoint": ".github/workflows/build.yml"
      },
      "parameters": {},
      "environment": {
        "github_workflow": "build.yml",
        "github_actor": "devops",
        "github_ref": "refs/heads/main"
      }
    },
    "materials": [
      {
        "uri": "git+https://github.com/owner/repo.git",
        "digest": {
          "sha1": "abc1234567890abc1234567890def1234567890"
        }
      }
    ]
  }
}
```

### In-Toto Statement Structure (Inside DSSE Payload)

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "<optional human-readable name>",
      "digest": {
        "sha256": "<hex-encoded SHA-256 digest of the artifact>"
      }
    }
  ],
  "predicateType": "<URI identifying the predicate type>",
  "predicate": {
    "<predicate-specific fields>"
  }
}
```

Common `predicateType` values:
- `https://slsa.dev/provenance/v1` — SLSA build provenance
- `https://slsa.dev/provenance/v0.2` — SLSA provenance v0.2 (older format)
- `https://spdx.dev/Document` — SBOM attestation
- `https://vuln.dev/attestation/sbom/v1` — Vulnerability SBOM

---

## 5. Sigstore Bundle Format (DSSE Envelope Inside It)

### Complete Bundle Structure

The Sigstore Bundle (media type `application/vnd.dev.sigstore.bundle.v0.3+json`) wraps the DSSE envelope with verification material:

```json
{
  "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
  "verificationMaterial": {
    "x509CertificateChain": {
      "certificates": [
        {
          "rawBytes": "<Base64(DER-encoded X.509 certificate)>"
        }
      ]
    },
    "tlogEntries": [
      {
        "logIndex": "125680200",
        "logId": {
          "keyId": "wNI9atQGlz+VWfO6LRygH4QUfY/8W4RFwiT5i5WRgB0="
        },
        "kindVersion": {
          "kind": "dsse",
          "version": "0.0.1"
        },
        "integratedTime": "1724870676",
        "inclusionPromise": {
          "signedEntryTimestamp": "MEYCIQCAKWrmj0LZ77rfiMXEat9gCCJxX4pgQfZqNc+tvF7gaAIhAJFtyypsWCbLDJ+NAMzPoY1AkQ1inhhQ3pZC5PaBCI8C"
        },
        "inclusionProof": {
          "rootHash": "<hex root hash>",
          "treeSize": 125680201,
          "logIndex": 125680200,
          "hashes": ["<hex hash 1>", "<hex hash 2>"]
        }
      }
    ],
    "timestampVerificationData": {
      "rfc3161Timestamps": [
        {
          "signedTimestamp": "<Base64(RFC3161 timestamp token)>"
        }
      ]
    }
  },
  "dsseEnvelope": {
    "payload": "<Base64(JSON_IN_TOTO_STATEMENT)>",
    "payloadType": "application/vnd.in-toto+json",
    "signatures": [
      {
        "keyid": "",
        "sig": "<Base64(SIGNATURE)>"
      }
    ]
  }
}
```

### Verification Material Components

1. **x509CertificateChain**: The Fulcio-issued short-lived certificate chain. Contains the signing certificate and any intermediate CAs. The leaf certificate contains the OIDC identity in the SAN.

2. **tlogEntries**: Rekor transparency log entries proving the signing event was recorded. Each entry contains:
   - `logIndex`: Position in the log
   - `logId`: Identifier for which Rekor instance (public-good or private)
   - `kindVersion`: `dsse/0.0.1` for DSSE-signed attestations, `hashedrekord/0.0.1` for simple signatures
   - `integratedTime`: Unix timestamp when the entry was integrated
   - `inclusionPromise` (Signed Entry Timestamp): Cryptographic proof from the log that the entry was accepted
   - `inclusionProof`: Merkle tree proof (optional but recommended)

3. **timestampVerificationData**: RFC3161 timestamps from a trusted TSA. Required when using short-lived Fulcio certificates to prove the signature was created during the certificate's validity window.

### Relationship to Transparency Log

When `actions/attest-build-provenance` signs an attestation:
1. The DSSE envelope is created and signed locally
2. The envelope hash is sent to Rekor, which returns a tlog entry with a Signed Entry Timestamp (SET)
3. The SET is included in the bundle as `inclusionPromise`
4. The full bundle (envelope + cert chain + tlog entry) is uploaded to GitHub Attestations API

For verification:
- The tlog entry proves the attestation existed at a specific point in time (integratedTime)
- The SET proves the log server accepted the entry
- The inclusion proof allows verifying the entry is still in the log (detects log tampering)
- The certificate chain proves the signing identity
- The DSSE signature proves the envelope wasn't tampered with

---

## 6. Offline Verification Using Cosign

### Method A: Verify Blob Signature Offline

```bash
# Transfer these files to air-gapped machine:
# - ~/.sigstore/          (trust root)
# - artifact.bin         (the blob)
# - artifact.bin.sig     (the signature)
# - artifact.bin.pem     (the certificate, if keyless)
# - OR artifact.bundle   (Sigstore bundle containing all above)

# Key-based verification (simplest for offline)
cosign verify-blob \
  --key cosign.pub \
  --signature artifact.bin.sig \
  artifact.bin

# Keyless verification (with bundle, offline)
cosign verify-blob \
  --bundle artifact.bundle \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity "https://github.com/owner/repo/.github/workflows/build.yml@refs/heads/main" \
  --offline=true \
  --new-bundle-format=false \
  --trusted-root ~/.sigstore/root/tuf-repo-cdn.sigstore.dev/targets/trusted_root.json \
  artifact.bin
```

### Method B: Verify Blob Attestation Offline

```bash
# Verify that a signed attestation (e.g., SLSA provenance) is valid for a blob
cosign verify-blob-attestation \
  --key cosign.pub \
  --bundle provenance.bundle \
  --insecure-ignore-tlog \
  artifact.bin

# With digest instead of blob file
cosign verify-blob-attestation \
  --key cosign.pub \
  --bundle provenance.bundle \
  --digest sha256:abc123def456... \
  --insecure-ignore-tlog

# Keyless with certificate identity verification
cosign verify-blob-attestation \
  --bundle provenance.bundle \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity "https://github.com/owner/repo/.github/workflows/build.yml@refs/heads/main" 
  --insecure-ignore-tlog \
  artifact.bin
```

### Method C: Verify Container Image Attestation Offline

```bash
# Save image locally first
docker pull ghcr.io/owner/repo/app:sha256-abc123
docker save ghcr.io/owner/repo/app@sha256:abc123... -o image.tar

# Verify attestation on local image
cosign verify-attestation \
  --key cosign.pub \
  --type slsaprovenance \
  --insecure-ignore-tlog \
  --local-image image.tar

# Keyless verification on local image
cosign verify-attestation \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity "https://github.com/owner/repo/.github/workflows/release.yml@refs/heads/main" \
  --type slsaprovenance \
  --offline=true \
  --new-bundle-format=false \
  --trusted-root ~/.sigstore/root/tuf-repo-cdn.sigstore.dev/targets/trusted_root.json \
  --local-image image.tar
```

### Complete Offline Verification Workflow (Air-Gapped)

**Low-side machine (connected):**

```bash
# 1. Initialize cosign trust root (silent, writes to ~/.sigstore)
cosign init

# 2. Save artifacts for transfer
mkdir -p ~/xfer/verify
cp -r ~/.sigstore ~/xfer/verify/
cp artifact.bin ~/xfer/verify/
cp artifact.bundle ~/xfer/verify/

# 3. Transfer ~/xfer/verify/ to high-side via sneakernet
```

**High-side machine (air-gapped):**

```bash
# 1. Place files
mkdir -p ~/.sigstore
cp -r xfer/verify/.sigstore/* ~/.sigstore/

# 2. Verify
cosign verify-blob \
  --bundle xfer/verify/artifact.bundle \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity "https://github.com/owner/repo/.github/workflows/build.yml@refs/heads/main" \
  --offline=true \
  --new-bundle-format=false \
  --trusted-root ~/.sigstore/root/tuf-repo-cdn.sigstore.dev/targets/trusted_root.json \
  xfer/verify/artifact.bin
```

**Directory structure on high-side:**

```
~/.sigstore/
  └── root/
      └── tuf-repo-cdn.sigstore.dev/
          └── targets/
              └── trusted_root.json

xfer/
  └── verify/
      ├── artifact.bin
      └── artifact.bundle
```

### Key Offline Flags

| Flag | Purpose |
|------|---------|
| `--offline=true` | Skip all network calls (Rekor, Fulcio, TUF updates) |
| `--new-bundle-format=false` | Required for Cosign v3 (offline support for new protobuf format not yet released); does not exist in v2 |
| `--trusted-root <path>` | Path to local TUF trusted_root.json for certificate verification |
| `--local-image <path>` | Path to local image tarball instead of registry reference |
| `--insecure-ignore-tlog` | Skip Rekor transparency log verification (for key-based signing where tlog was skipped) |
| `--private-infrastructure` | Skip tlog verification for privately deployed Rekor |

### `cosign verify-blob-attestation` Full Flag Reference

| Flag | Description |
|------|-------------|
| `--key string` | Path to public key, KMS URI, or Kubernetes Secret reference |
| `--bundle string` | Path to Sigstore bundle file |
| `--signature string` | Path to signature file or base64-encoded signature |
| `--certificate string` | Path to X.509 certificate (verified against Fulcio roots if no --certificate-chain) |
| `--certificate-chain string` | Path to CA certificate chain in PEM (intermediate → root order) |
| `--ca-roots string` | Path to CA root bundle PEM (conflicts with --certificate-chain) |
| `--ca-intermediates string` | Path to intermediate CA certs PEM (use with --ca-roots) |
| `--digest string` | Hex-encoded digest for in-toto subject verification (instead of providing blob file) |
| `--digestAlg string` | Digest algorithm for in-toto subject verification |
| `--certificate-oidc-issuer string` | Expected OIDC issuer in the certificate |
| `--certificate-identity string` | Expected identity in the certificate (exact match) |
| `--certificate-identity-regexp string` | Regex pattern for certificate identity matching |
| `--certificate-github-workflow-name string` | Expected GitHub workflow name claim |
| `--certificate-github-workflow-ref string` | Expected GitHub workflow ref claim |
| `--certificate-github-workflow-repository string` | Expected GitHub repository claim |
| `--rekor-url string` | Rekor server URL (default: `https://rekor.sigstore.dev`) |
| `--sct string` | Path to detached Signed Certificate Timestamp (RFC6962) |
| `--insecure-ignore-tlog` | Skip tlog verification (for artifacts not uploaded to Rekor) |
| `--insecure-ignore-sct` | Skip embedded SCT verification in certificate |
| `--private-infrastructure` | Skip tlog for private Rekor deployments |
| `--new-bundle-format` | Expect new protobuf bundle format (default: true in v3) |
| `--max-workers int` | Max parallel verification workers (default: 10) |
| `--output-file string` | Write output to file |
| `-t, --timeout duration` | Command timeout (default: 3m0s) |
| `-d, --verbose` | Debug output |

---

## 7. Relationship Between SLSA Provenance and Sigstore Transparency Log

### Data Flow

```
[GitHub Actions Workflow]
       │
       ├─(1)─ Request OIDC token from GitHub OIDC provider
       │
       ├─(2)─ Send OIDC token to Fulcio CA
       │         └─→ Receives short-lived X.509 certificate
       │
       ├─(3)─ Generate ephemeral keypair
       │
       ├─(4)─ Build SLSA provenance predicate
       │
       ├─(5)─ Wrap in in-toto Statement → DSSE Envelope
       │
       ├─(6)─ Sign DSSE envelope with ephemeral private key
       │
       ├─(7)─ Send envelope hash to Rekor tlog
       │         └─→ Receives tlog entry with Signed Entry Timestamp
       │
       ├─(8)─ Assemble Sigstore Bundle:
       │         ├─ dsseEnvelope (signed attestation)
       │         ├─ x509CertificateChain (Fulcio cert + intermediates)
       │         └─ tlogEntries (Rekor entry with SET)
       │
       └─(9)─ Upload bundle to GitHub Attestations API
```

### What the Transparency Log Proves

1. **Existence**: The attestation existed at `integratedTime` (Unix timestamp)
2. **Immutability**: The entry cannot be modified or deleted (append-only log)
3. **Consistency**: Inclusion proof allows detecting if the log was tampered with after the fact
4. **Binding**: The tlog entry hash is computed over the DSSE envelope, binding the log entry to the specific attestation content

### Privacy Implications

For **public repositories** using the public-good Sigstore instance:
- The Fulcio certificate (containing OIDC identity: repo name, workflow path, actor, ref) is published to the public Rekor log at `rekor.sigstore.dev`
- Anyone can search the log and discover build metadata
- This is by design — it enables public verification

For **private repositories** using GitHub's private Sigstore instance:
- The tlog entry is stored in GitHub's private Rekor
- Not publicly searchable
- Verification requires access to the private Rekor or the complete bundle

For **key-based signing** with `--tlog-upload=false`:
- No tlog entry is created
- The attestation is only as trustworthy as the key management
- Cannot be publicly verified (no tlog proof of existence)
- Must use `--insecure-ignore-tlog=true` during verification

---

## 8. Limitations and Caveats

### Self-Hosted Runner Requirements

- **OIDC tokens are NOT reliably available on self-hosted runners**. The `id-token: write` permission requires the GitHub Actions OIDC provider, which is only guaranteed on GitHub-hosted runners.
- Without OIDC, you cannot use the keyless signing flow. You must use key-based signing (GitHub App key or cosign-generated keypair).
- Key-based signing on self-hosted runners achieves at best **SLSA L2** (not L3), because:
  - The signing key is accessible to user-defined build steps
   - There is no platform-level isolation guarantee for the signing material
   - Self-hosted runners may not enforce run-to-run isolation

### Permissions

- `id-token: write` is **NOT granted** to PRs from forks by default (intentional security restriction)
- `attestations: write` is only available on GitHub Enterprise Cloud for private/internal repos (public repos available on all current plans)
- Legacy Bronze/Silver/Gold plans do not support artifact attestations

### Fork PR Limitations

- Pull requests from forks cannot generate attestations (no `id-token: write`)
- This is a security feature — fork authors should not be able to generate trusted provenance for the target repository

### Subject Identification Caveats

- `subject-name` must use **fully-qualified image names** (e.g., `ghcr.io/user/app`, NOT `user/app`)
- `subject-name` must **exclude tags** — use only the digest to identify the specific image
- For Docker Hub, use `index.docker.io/user/app` (not `docker.io`)
- Maximum 1024 subjects per attestation call

### Cosign Version Compatibility

- **Cosign v2.x**: Standard verification commands work. `--new-bundle-format` flag does not exist.
- **Cosign v3.x** (released October 2025): Offline verification requires `--new-bundle-format=false` because offline support for the new protobuf bundle specification has not landed yet.
- `--type slsaprovenance` is only supported in `verify-attestation` and `verify-blob-attestation`, NOT in `verify` or `verify-blob`.

### Inconsistent Warning Behavior

- `cosign verify` emits a warning when `--insecure-ignore-tlog` is used
- `cosign verify-attestation`, `cosign verify-blob`, and `cosign verify-blob-attestation` do NOT emit this warning
- This is a known inconsistency (sigstore/cosign#2839)

### GitHub Private Sigstore vs Public Good

| Aspect | Public Good | GitHub Private |
|--------|------------|----------------|
| Available for | Public repos | Private/Internal repos (Enterprise Cloud) |
| Fulcio instance | `fulcio.sigstore.dev` | GitHub private Fulcio |
| Rekor instance | `rekor.sigstore.dev` | GitHub private Rekor |
| TUF root | `tuf-repo-cdn.sigstore.dev` | GitHub private TUF |
| Public verification | Yes | No (requires bundle) |
| Privacy | Identity published to public log | Private |

### Certificate Identity Format

The certificate identity in the SAN follows this format for GitHub Actions:

```
https://github.com/<owner>/<repo>/.github/workflows/<workflow-file>@refs/<ref-type>/<ref-name>
```

Example:
```
https://github.com/acme/webapp/.github/workflows/release.yml@refs/tags/v1.2.3
```

Use `--certificate-identity-regexp` with a regex pattern to match across branches/tags:
```bash
--certificate-identity-regexp 'https://github.com/acme/webapp/.github/workflows/.+'
```

### Deprecation Notes

- The `actions/attest-build-provenance` action v4+ is a thin wrapper around `@actions/attest`. New implementations should use `actions/attest` directly.
- Older OID values for GitHub workflow names in Fulcio certificates are deprecated: `https://github.com/...` format has replaced the older numeric OID `1.3.6.1.4.1.57264.1.5` (deprecated).

---

## Source URLs

1. https://github.com/actions/attest-build-provenance — Official action repository
2. https://kansas1295.github.io/attest-build-provenance/ — Action documentation site
3. https://deepwiki.com/actions/attest-build-provenance/2.2-workflow-integration — DeepWiki workflow integration analysis
4. https://github.com/in-toto/attestation/blob/main/spec/v1/envelope.md — DSSE/in-toto envelope specification
5. https://docs.sigstore.dev/about/bundle/ — Sigstore Bundle format specification
6. https://dsse.io/introduction/ — DSSE introduction and online decoder
7. https://some-natalie.dev/blog/cosign-disconnected/ — Offline cosign verification guide
8. https://docs.sigstore.dev/cosign/key_management/signing_with_self-managed_keys/ — Cosign self-managed key signing
9. https://docs.sigstore.dev/cosign/key_management/import-keypair/ — Cosign keypair import documentation
10. https://github.com/sigstore/cosign/blob/main/doc/cosign_verify-blob-attestation.md — cosign verify-blob-attestation reference
11. https://docs.github.com/actions/security-guides/using-artifact-attestations-and-reusable-workflows-to-achieve-slsa-v1-build-level-3 — GitHub SLSA L3 guide
12. https://slsa.dev/spec/v1.0/levels — SLSA v1.0 level definitions
13. https://slsa.dev/spec/v1.0/requirements — SLSA v1.0 normative requirements
14. https://slsa.dev/spec/v1.0/whats-new — SLSA v1.0 changes from v0.1
15. https://docs.sigstore.dev/cosign/verifying/verify/ — Cosign verification documentation
16. https://docs.sigstore.dev/cosign/verifying/attestation/ — Cosign attestation verification
17. https://how2.sh/posts/how-to-add-slsa-build-provenance-in-github-actions/ — SLSA provenance tutorial
18. https://blog.sigstore.dev/cosign-2-0-released/ — Cosign 2.0 release notes
19. https://github.com/sigstore/cosign/issues/2839 — Inconsistent tlog warning behavior
20. https://github.com/sigstore/cosign/issues/3529 — OIDC provider discussion
21. https://github.com/sigstore/fulcio/blob/main/docs/oid-info.md — Fulcio OID information (deprecated OIDs)
22. https://github.com/slsa-framework/slsa-github-generator/blob/main/internal/builders/generic/README.md — SLSA generic builder docs
