In docs/phase2-network-policies-design.md around lines 187 to 191, the
protocol/port line for tensorzero-gateway is inconsistent (says "HTTP (TCP
3000)" while the service is exposed on host port 3030). Update the protocol/port
line to reflect the externally accessible port by changing it to "HTTP (TCP
3030)" or explicitly note "HTTP (container TCP 3000, host TCP 3030)" so the
documentation accurately represents the host mapping.

In docs/phase2-network-policies-design.md around lines 211 to 213, the docker
bridge option com.docker.network.bridge.enable_icc: "false" disables
inter-container communication and will block required traffic between services
on the api-tier (e.g., agent-zero → archon); remove this setting from the
api-tier network or move it into the specific network definitions that require
strict isolation so only truly isolated networks have enable_icc set to "false",
and update any examples and notes to clarify which networks remain isolated
versus which allow intra-tier container communication.

In pmoves/docker-compose.yml.backup-20251206-220500 lines 1-20: this backup file
contains default credential patterns and should not be committed; remove the
backup from the repository (e.g., git rm --cached
pmoves/docker-compose.yml.backup-20251206-220500 and commit), add a rule to
.gitignore to exclude backup files (e.g., add *.backup-* or pmoves/*.backup-*),
and store backups outside the repo or in a secure location; if any secrets were
ever exposed from this file, rotate those credentials immediately.


🧹 Nitpick comments (11)
docs/phase2-security-hardening-plan.md (3)
83-88: Add language specifier to code block and consider relative paths.

The TAC prompt code block lacks a language specifier (flagged by markdownlint). Also, the absolute path /home/pmoves/PMOVES.AI/ in TAC prompts may break in different environments.

-```
+```text
 Update /home/pmoves/PMOVES.AI/pmoves/services/archon/Dockerfile to remove
-insecure ARG defaults for secrets (lines 49-79). Replace with secure pattern
+insecure ARG defaults for secrets. Replace with secure pattern
 that enforces runtime-only configuration. Follow the migration plan in
-/home/pmoves/PMOVES.AI/docs/phase2-buildkit-secrets-migration-plan.md
+docs/phase2-buildkit-secrets-migration-plan.md

---

`105-122`: **Add language specifier to code block.**

Per markdownlint MD040, fenced code blocks should have a language specified.



```diff
-```
+```text
 Branch: main
161-167: Add language specifier to ASCII diagram.

-```
+```text
 External → API Tier → Application Tier → Data Tier
.claude/test-self-hosting.sh (3)
62-72: Hardcoded absolute path reduces portability.

The path /home/pmoves/PMOVES.AI/ is hardcoded. Consider using a relative path or environment variable for portability across different environments.

+# Determine script directory for relative paths
+SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
+REPO_ROOT="$(dirname "$SCRIPT_DIR")"
+
 # Test 5: Check Claude Code hooks directory
 echo "5. Checking Claude Code hooks..."
-if [ -f "/home/pmoves/PMOVES.AI/.claude/hooks/post-tool.sh" ]; then
+if [ -f "$REPO_ROOT/.claude/hooks/post-tool.sh" ]; then
     echo "   ✅ Post-tool hook exists"
-    if [ -x "/home/pmoves/PMOVES.AI/.claude/hooks/post-tool.sh" ]; then
+    if [ -x "$REPO_ROOT/.claude/hooks/post-tool.sh" ]; then
         echo "   ✅ Post-tool hook is executable"
     else
         echo "   ⚠️  Post-tool hook not executable (will fix)"
-        chmod +x "/home/pmoves/PMOVES.AI/.claude/hooks/post-tool.sh"
+        chmod +x "$REPO_ROOT/.claude/hooks/post-tool.sh"
     fi
 else
     echo "   ❌ Post-tool hook not found"
 fi
29-35: Add timeout to curl commands to prevent indefinite hangs.

The curl commands lack timeouts, which could cause the script to hang if services are unresponsive.

 # Test 2: Hi-RAG v2 health
 echo "2. Testing Hi-RAG v2 API..."
-HIRAG_HEALTH=$(curl -s http://localhost:8086/)
+HIRAG_HEALTH=$(curl -s --connect-timeout 5 --max-time 10 http://localhost:8086/)
 if echo "$HIRAG_HEALTH" | grep -q '"ok":true'; then
     echo "   ✅ Hi-RAG v2 is healthy"
48-58: Add timeout to POST request and improve error handling.

 # Test 4: Query Hi-RAG v2 (best-effort)
 echo "4. Testing Hi-RAG v2 query..."
-QUERY_RESULT=$(curl -s -X POST http://localhost:8086/hirag/query \
+QUERY_RESULT=$(curl -s --connect-timeout 5 --max-time 30 -X POST http://localhost:8086/hirag/query \
   -H "Content-Type: application/json" \
   -d '{"query": "test", "top_k": 5, "rerank": false}')
docs/phase2-network-policies-design.md (1)
700-712: Consider tightening external egress rules for API tier.

The current namespaceSelector: {} in egress allows traffic to all namespaces, which is overly permissive. For external LLM providers, consider using explicit CIDR blocks or removing the namespace selector and relying on the implicit external access when no to selector matches internal pods.

     # Allow external (for LLM providers)
+    # Note: Traffic to IPs outside the cluster is allowed by default when
+    # no podSelector/namespaceSelector matches. Consider adding explicit
+    # ipBlock rules for known LLM provider endpoints in production.
     - to:
-        - namespaceSelector: {}
+        - ipBlock:
+            cidr: 0.0.0.0/0
+            except:
+              - 10.0.0.0/8
+              - 172.16.0.0/12
+              - 192.168.0.0/16
docs/phase2-buildkit-secrets-migration-plan.md (1)
280-340: ⚠️ Minor: Fix markdown code block language specification.

The markdown code block (line 282-340) showing example DOCKER_SECURITY_PATTERNS.md is missing a language specifier. Static analysis flagged this as MD040.

Change:

- ```markdown
+ ```md
  # Docker Security Patterns for PMOVES.AI
  ...
- ```
+ ```
Alternatively, consider whether this should be a plain markdown rendering rather than a code block, since it's demonstrating markdown syntax itself.

docs/phase2-branch-protection-guide.md (3)
24-24: Minor: Fix missing language specifications in code blocks.

Three code blocks are missing language specifiers (markdownlint MD040):

Line 24-26: URL block should specify text or uri

- ```
+ ```text
  https://github.com/POWERFULMOVES/PMOVES.AI/settings/branches
- ```
+ ```
Line 31-34: Branch name pattern should specify language:

- ```
+ ```text
  main
- ```
+ ```
Line 135-138: Error message output should specify text:

- ```
+ ```text
  ! [remote rejected] main -> main (protected branch hook declined)
  error: failed to push some refs to 'github.com:POWERFULMOVES/PMOVES.AI.git'
- ```
+ ```
Also applies to: 31-31, 135-135

39-86: Minor: Use proper markdown heading syntax instead of emphasis.

Several subsections use bold emphasis (**text**) instead of proper H3 headings (###). This violates markdownlint MD036 and reduces document semantic clarity. Examples:

Line 41: **✅ Require a pull request before merging** → should be ### ✅ Require a pull request before merging
Line 49: **✅ Require status checks to pass before merging** → should be ### ✅ Require status checks to pass before merging
Line 59, 63, 72, 83: Similar pattern

This is a minor readability issue but worth fixing for consistency with markdown best practices.

1-7: Status metadata is accurate but update needed for PR context.

The document correctly states "Ready to implement (15-minute task)" and "HIGH priority". However, once implemented, this document should be updated with:

Actual implementation timestamp
Completion status
Reference to related PR/issue that completed it
This supports audit trail and change management practices.