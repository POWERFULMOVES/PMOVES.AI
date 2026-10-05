#!/usr/bin/env python3
"""CLM v0.1-8B eval — parity + cache-scaling rounds.
Run on the Spark runner after vllm (Qwen3-8B pooling, :8090) and clm-serve (:8700) are up.
Spec: plans/CLM_EVAL_SPEC_2026-10-05.md
"""
import json, time
from clm import CLMClient, Choice, Noul

client = CLMClient()
results = {}

# Round 1: parity — typed probes
probes = [
    ("Customer charged twice, no response from support",
     {"urgent": Noul(instructions="Is this urgent?"),
      "team": Choice(instructions="Which team?", criteria={"billing": "charges/invoices", "technical": "bugs/outages"})}),
    ("GPU node offline, agents cannot reach Ollama",
     {"urgent": Noul(instructions="Is this urgent?"),
      "team": Choice(instructions="Which team?", criteria={"billing": "charges", "infra": "nodes/network"})}),
    ("Resident asks about mesh node hosting cost",
     {"urgent": Noul(instructions="Urgent?"),
      "topic": Choice(instructions="Topic?", criteria={"infra": "hosting/network", "finance": "costs/dues"})}),
    ("GroToken pool distribution computed for week 42",
     {"settlement": Noul(instructions="Is this a settlement event?")}),
]
parity = []
for state, questions in probes:
    t0 = time.time()
    r = client.system_one(state=state, questions=questions)
    ms = round((time.time() - t0) * 1000, 1)
    parity.append({"state": state[:60], "latency_ms": ms, "raw": str(r)[:200]})
results["parity"] = parity

# Round 2: cache-scaling — 8 vs 1024 candidates (first call vs cached)
large = {f"tool{i}": f"Tool number {i} for task {i % 20}" for i in range(1024)}
t0 = time.time()
client.system_one(state="pick a tool for file upload", questions={"pick": Choice(instructions="Best tool", criteria=large)})
first_ms = round((time.time() - t0) * 1000, 1)
t0 = time.time()
client.system_one(state="pick a tool for webhook", questions={"pick": Choice(instructions="Best tool", criteria=large)})
cached_ms = round((time.time() - t0) * 1000, 1)
small = {f"opt{i}": f"Option {i}" for i in range(8)}
t0 = time.time()
client.system_one(state="route a support ticket", questions={"pick": Choice(instructions="Best option", criteria=small)})
small_ms = round((time.time() - t0) * 1000, 1)
results["scaling"] = {"first_1024_ms": first_ms, "cached_1024_ms": cached_ms, "small_8_ms": small_ms}

json.dump(results, open("results.json", "w"), indent=2)
print(json.dumps(results, indent=2))
