import json, subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\russe\agent-zero")
OUT = Path(r"C:\Users\russe\agent-zero\chat-corpus-staging")
PROV = OUT.parent / "chat-corpus-gate-reports"  # provenance artifacts live OUTSIDE the scanned tree
REPO = Path(r"C:\Users\russe\Documents\GitHub\PMOVES.AI")
GL = REPO / "pmoves" / "tools" / "a0" / "bin" / "gitleaks.exe"
TOML = REPO / "pmoves" / "chat-corpus" / "gitleaks.toml"
EXCLUDE_KW = ["unfcu", "docintel"]
# Burned-secret literals are NOT committed (CodeQL: clear-text secrets in
# source). They load from a local, gitignored burn-list file maintained beside
# the staging corpus - the same pattern gitleaks uses for baselines.
# Source provenance: pmoves/chat-corpus/ITERATIONS.md incident findings.
BURN_LIST = Path(r"C:\Users\russe\agent-zero\chat-corpus-staging\burn-literals.local")
LITERALS = [line for line in (BURN_LIST.read_text(encoding="utf-8", errors="replace").splitlines() if BURN_LIST.exists() else []) if line.strip()]
PLACEHOLDER = {
    "pmoves-jwt-escaped": "[REDACTED-JWT]",
    "jwt": "[REDACTED-JWT]",
    "pmoves-lan-ip": "[REDACTED-IP]",
    "pmoves-postgres-url": "[REDACTED-DB]",
    "github-pat": "[REDACTED-GH]",
    "curl-auth-header": "[REDACTED-AUTH]",
}
CATS = ["jwt", "env", "lan_ip", "dburl", "upstream", "literal"]

def placeholder(rule):
    return PLACEHOLDER.get(rule, "[REDACTED:%s]" % rule)

def gitleaks(source, report):
    if report.exists():
        report.unlink()
    subprocess.run(
        [str(GL), "detect", "--source", str(source), "--no-git",
         "--config", str(TOML), "--report-format", "json",
         "--report-path", str(report), "--no-banner"],
        capture_output=True, text=True)
    data = []
    if report.exists() and report.stat().st_size:
        try:
            data = json.loads(report.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            data = []
    return data

insts = sorted([d for d in ROOT.iterdir() if d.is_dir() and (d / "usr" / "chats").exists()])
alias = {d.name: "instance-%d" % (i + 1) for i, d in enumerate(insts)}

# GLOBAL secret table: unique secrets across ALL instances, longest first.
# Path-form-agnostic: gitleaks File paths vary (abs/rel) between runs, so we
# never key findings by path — every discovered secret applies everywhere.
raw_counts = {}
secrets = {}
for inst in insts:
    rep = OUT / ("gl-raw-%s.json" % alias[inst.name])
    data = gitleaks(inst / "usr" / "chats", rep)
    for f in data:
        raw_counts[f["RuleID"]] = raw_counts.get(f["RuleID"], 0) + 1
        sec = f.get("Secret", "")
        if sec and len(sec) >= 4:
            secrets[sec] = f["RuleID"]
    rep.unlink()
ordered = sorted(secrets.items(), key=lambda kv: -len(kv[0]))
print("UNIQUE_SECRETS=%d" % len(ordered))

def redact(text):
    counts = {}
    for sec, rule in ordered:
        if sec in text:
            n = text.count(sec)
            text = text.replace(sec, placeholder(rule))
            counts[rule] = counts.get(rule, 0) + n
    for lit in LITERALS:
        if lit in text:
            n = text.count(lit)
            text = text.replace(lit, "[REDACTED-LITERAL]")
            counts["literal"] = counts.get("literal", 0) + n
    return text, counts

OUT.mkdir(exist_ok=True)
for pat_ in ("gl-gate*.json", "findings.*", "run-manifest.json"):
    for st in OUT.rglob(pat_):
        st.unlink()

rows = []
totals = {}
for inst in insts:
    a = alias[inst.name]
    (OUT / a).mkdir(exist_ok=True)
    (OUT / (a + "-excluded")).mkdir(exist_ok=True)
    for chat in sorted((inst / "usr" / "chats").iterdir()):
        if not chat.is_dir():
            continue
        msgs = sorted(chat.glob("messages/*.txt"), key=lambda p: int(p.stem) if p.stem.isdigit() else 10 ** 9)
        if not msgs:
            continue
        title = ""
        try:
            cj = json.loads((chat / "chat.json").read_text(encoding="utf-8", errors="replace"))
            title = str(cj.get("title") or cj.get("name") or "")
        except Exception:
            pass
        title_red, _ = redact(title)
        allc = {}
        blob = []
        low_all = ""
        for mm in msgs:
            try:
                raw = mm.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            red, c = redact(raw)
            for k, v in c.items():
                allc[k] = allc.get(k, 0) + v
            low_all += red.lower()[:4000] + "\n"
            blob.append(json.dumps({"chat": chat.name, "title": title_red, "msg": int(mm.stem) if mm.stem.isdigit() else 0, "text": red}, ensure_ascii=False))
        reason = [k for k in EXCLUDE_KW if k in low_all or k in title_red.lower()]
        dest = OUT / (a + "-excluded") if reason else OUT / a
        (dest / (chat.name + ".jsonl")).write_text("\n".join(blob), encoding="utf-8")
        for k, v in allc.items():
            totals[k] = totals.get(k, 0) + v
        rows.append({"instance_alias": a, "chat": chat.name, "title": title_red[:60], "messages": len(blob), "excluded": bool(reason), "reason": ";".join(reason), **{c: allc.get(c, 0) for c in CATS}})

# ITERATE-TO-ZERO: gate-time findings can exist only in JSON-escaped forms the
# raw scan cannot see. Replace them in-place and re-gate until the upstream
# engine certifies zero (max 3 rounds; every replacement is logged).
import hashlib, datetime

def _redact_report(path):
    if not path.exists():
        return
    try:
        rows_ = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        for r_ in rows_:
            if r_.get("Secret"):
                r_["Secret"] = hashlib.sha256(r_["Secret"].encode()).hexdigest()[:8] + "..."
            if r_.get("Match"):
                m_ = r_["Match"]
                r_["Match"] = "[len:%d sha8:%s]" % (len(m_), hashlib.sha256(m_.encode()).hexdigest()[:8])
        path.write_text(json.dumps(rows_, indent=1), encoding="utf-8")
    except Exception:
        pass

gate_history = []
rounds = 0
while True:
    rounds += 1
    PROV.mkdir(exist_ok=True)
    rep2 = PROV / ("gl-gate-r%d.json" % rounds)
    gate = gitleaks(OUT, rep2)
    _redact_report(rep2)
    gate_history.append({"round": rounds, "findings": len(gate), "report": rep2.name})
    if not gate or rounds >= 3:
        break
    jsonls = list(OUT.rglob("*.jsonl"))
    for g in gate:
        sec = g.get("Secret", "")
        if not sec:
            continue
        ph = placeholder(g["RuleID"])
        for jf in jsonls:
            t = jf.read_text(encoding="utf-8", errors="replace")
            if sec in t:
                jf.write_text(t.replace(sec, ph), encoding="utf-8")
if "rep2" not in dir() or not locals().get("rep2"):
    rep2 = PROV / "gl-gate.json"
if not (OUT / "gl-gate.json").exists() or True:
    gate = gitleaks(OUT, PROV / "gl-gate.json")
PROV.mkdir(exist_ok=True)
_redact_report(PROV / "gl-gate.json")
gate_n = len(gate)

def _sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

_manifest = {
    "timestamp": datetime.datetime.now().isoformat(),
    "engine_version": subprocess.run([str(GL), "version"], capture_output=True, text=True).stdout.strip(),
    "engine_sha256": _sha256_file(GL),
    "config_sha256": _sha256_file(TOML),
    "burnlist_sha256": _sha256_file(BURN_LIST) if BURN_LIST.exists() else None,
    "unique_secrets": len(ordered),
    "raw_counts": raw_counts,
    "gate_rounds": gate_history,
    "gate_final_findings": gate_n,
    "chats": len(rows),
    "messages": sum(r["messages"] for r in rows),
    "excluded": sum(1 for r in rows if r["excluded"]),
}
(PROV / "run-manifest.json").write_text(json.dumps(_manifest, indent=2), encoding="utf-8")

with (PROV / "findings.csv").open("w", encoding="utf-8") as f:
    cols = ["instance_alias", "chat", "title", "messages", "excluded", "reason"] + CATS
    f.write(",".join(cols) + "\n")
    for r in rows:
        f.write(",".join(str(r.get(c, 0)).replace(",", " ") for c in cols) + "\n")

lines = ["# Chat Corpus Scrub Findings", "",
         "Detection: gitleaks v8.30.1 (upstream ruleset + pmoves/chat-corpus/gitleaks.toml).",
         "Redaction: global exact-secret replacement, longest-first, keyed by upstream RuleID.",
         "ACCEPTANCE GATE: second gitleaks pass over staged output must report 0 findings.", "",
         "## Raw findings by rule", ""]
for k, v in sorted(raw_counts.items(), key=lambda kv: -kv[1]):
    lines.append("- %s: %d" % (k, v))
lines += ["", "## GATE: %d findings | rounds=%s" % (gate_n, gate_history), "",
          "GATE_RESULT=" + ("PASS" if gate_n == 0 else "FAIL"), "",
          "## Chats: %d | Messages: %d | Excluded: %d" % (len(rows), sum(r["messages"] for r in rows), len([r for r in rows if r["excluded"]])), "",
          "Review this file + findings.csv. Only redacted JSONL dirs are publishable."]
(PROV / "findings.md").write_text("\n".join(lines), encoding="utf-8")
# gate reports retained for provenance (see run-manifest.json)

print("RAW_RULE_COUNTS:", json.dumps(raw_counts))
print("CHATS=%d MESSAGES=%d EXCLUDED=%d" % (len(rows), sum(r["messages"] for r in rows), len([r for r in rows if r["excluded"]])))
print("GATE_FINDINGS=%d -> %s" % (gate_n, "PASS" if gate_n == 0 else "FAIL"))
for g in gate[:8]:
    print("  residual:", g["RuleID"], g["File"].split("chat-corpus-staging")[-1], "line", g["StartLine"], repr(g.get("Secret", ""))[:60])
print("STAGING:", str(OUT))


