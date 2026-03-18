/**
 * Setup Custom .localhost Domains for P7 LAN-Wide-Web.
 *
 * SECURITY: Only creates redirects for services marked `lanSafe: true`
 * in service-registry.js. Data-layer services (Neo4j, MinIO, Supabase,
 * NATS, etc.) are EXCLUDED to prevent LAN exposure of admin interfaces
 * with default credentials.
 *
 * Creates serverless webapp folders in P7's api directory that redirect
 * to the actual PMOVES service ports.
 */
module.exports = {
  run: [
    {
      method: "log",
      params: {
        raw: true,
        text: "\n\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n  Setting up P7 Custom Domains (LAN-Safe Only)\n\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n\n  Only user-facing services (lanSafe=true) get LWW domains.\n  Admin interfaces (MinIO, Supabase, Neo4j) are excluded.\n"
      }
    },
    // ── agent-zero.pmoves (lanSafe: true) ──
    {
      method: "fs.write",
      params: {
        path: "{{path.resolve(cwd, '..', 'agent-zero.pmoves', 'index.html')}}",
        text: "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"0;url=http://localhost:8081\"><title>Agent Zero</title></head><body><p>Redirecting to <a href=\"http://localhost:8081\">Agent Zero UI</a>...</p></body></html>"
      }
    },
    {
      method: "fs.write",
      params: {
        path: "{{path.resolve(cwd, '..', 'agent-zero.pmoves', 'pinokio.json')}}",
        text: "{\"title\":\"Agent Zero\",\"description\":\"PMOVES Agent Zero orchestrator UI\"}"
      }
    },
    // ── archon.pmoves (lanSafe: true) ──
    {
      method: "fs.write",
      params: {
        path: "{{path.resolve(cwd, '..', 'archon.pmoves', 'index.html')}}",
        text: "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"0;url=http://localhost:3737\"><title>Archon</title></head><body><p>Redirecting to <a href=\"http://localhost:3737\">Archon UI</a>...</p></body></html>"
      }
    },
    {
      method: "fs.write",
      params: {
        path: "{{path.resolve(cwd, '..', 'archon.pmoves', 'pinokio.json')}}",
        text: "{\"title\":\"Archon\",\"description\":\"PMOVES Archon agent service UI\"}"
      }
    },
    // ── tensorzero.pmoves (lanSafe: true) ──
    {
      method: "fs.write",
      params: {
        path: "{{path.resolve(cwd, '..', 'tensorzero.pmoves', 'index.html')}}",
        text: "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"0;url=http://localhost:4000\"><title>TensorZero</title></head><body><p>Redirecting to <a href=\"http://localhost:4000\">TensorZero UI</a>...</p></body></html>"
      }
    },
    {
      method: "fs.write",
      params: {
        path: "{{path.resolve(cwd, '..', 'tensorzero.pmoves', 'pinokio.json')}}",
        text: "{\"title\":\"TensorZero\",\"description\":\"PMOVES LLM gateway dashboard\"}"
      }
    },
    // ── tts.pmoves (lanSafe: true) ──
    {
      method: "fs.write",
      params: {
        path: "{{path.resolve(cwd, '..', 'tts.pmoves', 'index.html')}}",
        text: "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"0;url=http://localhost:7861\"><title>TTS Studio</title></head><body><p>Redirecting to <a href=\"http://localhost:7861\">TTS Studio</a>...</p></body></html>"
      }
    },
    {
      method: "fs.write",
      params: {
        path: "{{path.resolve(cwd, '..', 'tts.pmoves', 'pinokio.json')}}",
        text: "{\"title\":\"TTS Studio\",\"description\":\"PMOVES multi-engine TTS synthesis\"}"
      }
    },
    {
      method: "log",
      params: {
        raw: true,
        text: "\n  EXCLUDED (admin-only, localhost access only):\n    - grafana.pmoves   (port 3000, no auth by default)\n    - minio.pmoves     (port 9001, default creds risk)\n    - supabase.pmoves  (port 54323, database admin)\n    - neo4j.pmoves     (port 7474, graph database)\n\n  To access admin UIs, use localhost directly or SSH tunnel.\n"
      }
    },
    {
      method: "notify",
      params: {
        html: "LAN-safe P7 domains created:<br>agent-zero.pmoves, archon.pmoves,<br>tensorzero.pmoves, tts.pmoves<br><br>Admin UIs excluded for security.",
        type: "success"
      }
    }
  ]
}
