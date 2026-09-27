import json, re
from pathlib import Path

ROOT = Path(r"C:\Users\russe\agent-zero")
OUT = Path(r"C:\Users\russe\agent-zero\chat-corpus-staging")
OUT.mkdir(exist_ok=True)

LITERALS = [
    "N/9cZCrv2i95v3sQO+g3Xpabp6aMcu1qjm14XLcnd4o59hkf9qOPonSzCK+Y3Nmk",
    "X8q9z6nZ-txaUqS2dvf0vaXP9zBrxP0h",
    "super-secret-jwt-token-with-at-least-32-characters-long",
]
EXCLUDE_KW = ["unfcu", "docintel"]
CATS = ["jwt", "github_token", "sk_key", "env_kv", "json_kv", "bearer", "lan_ip", "email", "literal", "userpath", "container"]

insts = sorted([d for d in ROOT.iterdir() if d.is_dir() and (d / "usr" / "chats").exists()])
alias = {d.name: "instance-%d" % (i + 1) for i, d in enumerate(insts)}
inst_names = sorted(alias.keys(), key=len, reverse=True)
inst_res = [(re.escape(n), alias[n]) for n in inst_names]

def scrub(text):
    counts = {}
    def rep(pat, repl, name):
        nonlocal text
        text, n = re.subn(pat, repl, text)
        if n:
            counts[name] = counts.get(name, 0) + n
    rep(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}", "[REDACTED-JWT]", "jwt")
    rep(r"(?i)gh[pousr]_[A-Za-z0-9]{16,}", "[REDACTED-GITHUB]", "github_token")
    rep(r"(?i)\bsk-[A-Za-z0-9]{16,}", "[REDACTED-KEY]", "sk_key")
    rep(r"(?mi)^([A-Za-z_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|APIKEY|AUTH_KEY|PRIVATE_KEY|REFRESH|_KEY|_SECRET)\w*=)\S.{3,}$", r"\1[REDACTED]", "env_kv")
    rep(r"(?i)([\"'](?:[A-Za-z0-9_\-]*(?:password|passwd|secret|token|api_key|apikey|auth_key|private_key)[A-Za-z0-9_\-]*)[\"']\s*[:=]\s*[\"'])([^\"'\n]{4,})([\"'])", r"\1[REDACTED]\3", "json_kv")
    rep(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{16,}", "Bearer [REDACTED]", "bearer")
    rep(r"\b(?:172\.(?:1[6-9]|2\d|3[01])|10|192\.168)\.\d{1,3}\.\d{1,3}\b", "[LAN-IP]", "lan_ip")
    rep(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", "[EMAIL]", "email")
    rep(r"[A-Z]:(?:\\\\+|/)Users(?:\\\\+|/)russe", "[USERDIR]", "userpath")
    rep(r"a0-inst-[A-Za-z0-9\-]+", "[A0-INSTANCE]", "container")
    rep(r"pmoves-agent-zero-[a-z0-9]+", "[CONTAINER]", "container")
    for pat, a in inst_res:
        rep(pat, a, "container")
    for lit in LITERALS:
        rep(re.escape(lit), "[REDACTED-LITERAL]", "literal")
    return text, counts

rows = []
totals = {}
for inst in insts:
    a = alias[inst.name]
    (OUT / a).mkdir(exist_ok=True)
    (OUT / (a + "-excluded")).mkdir(exist_ok=True)
    for chat in sorted((inst / "usr" / "chats").iterdir()):
        if not chat.is_dir():
            continue
        msgs = sorted(chat.glob("messages/*.txt"), key=lambda p: int(p.stem) if p.stem.isdigit() else 10**9)
        if not msgs:
            continue
        title = ""
        try:
            cj = json.loads((chat / "chat.json").read_text(encoding="utf-8", errors="replace"))
            title = str(cj.get("title") or cj.get("name") or "")
        except Exception:
            pass
        title_red, tcounts = scrub(title)
        allc = dict(tcounts)
        blob = []
        low_all = ""
        for mm in msgs:
            try:
                raw = mm.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            red, c = scrub(raw)
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

with (OUT / "findings.csv").open("w", encoding="utf-8") as f:
    cols = ["instance_alias", "chat", "title", "messages", "excluded", "reason"] + CATS
    f.write(",".join(cols) + "\n")
    for r in rows:
        vals = [str(r[c]).replace(",", " ") for c in cols]
        f.write(",".join(vals) + "\n")

lines = ["# Chat Corpus Scrub Findings", "", "Generated for operator review. NOTHING is published.", "", "## Instance alias map (local only)", ""]
for n, a in alias.items():
    lines.append("- %s -> %s" % (n, a))
lines += ["", "## Totals across all chats", ""]
for c in CATS:
    lines.append("- %s: %d" % (c, totals.get(c, 0)))
ex = [r for r in rows if r["excluded"]]
lines += ["", "## Excluded (customer-suspect) chats: %d" % len(ex), ""]
for r in ex:
    lines.append("- %s / %s / %s (%s)" % (r["instance_alias"], r["chat"], r["title"], r["reason"]))
lines += ["", "## Chats: %d | Messages: %d" % (len(rows), sum(r["messages"] for r in rows)), "", "Review findings.csv, then publish only the redacted JSONL dirs."]
(OUT / "findings.md").write_text("\n".join(lines), encoding="utf-8")
print("CHATS=%d MESSAGES=%d EXCLUDED=%d" % (len(rows), sum(r["messages"] for r in rows), len(ex)))
print("TOTALS:", json.dumps(totals))
print("STAGING:", str(OUT))
