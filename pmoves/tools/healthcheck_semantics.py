#!/usr/bin/env python3
"""healthcheck_semantics.py - count healthcheck shapes across the compose file.

WHAT THIS DOES AND DOES NOT DO
------------------------------
It COUNTS. It does not validate, and it does not judge meaning.

  * Structure is Docker's job. `docker compose config` is the Compose
    Specification authority and rejects things nothing here can catch --
    `retries: "not-a-number"` is accepted by every YAML parser and refused by
    Docker. It cannot run in CI on this repo, because the compose file declares
    `env_file: env.shared` per service and that file is a secret absent from a
    fresh checkout, which is exactly why `compose_yaml_validate.py` exists and
    stops at parseability.

  * Parsing is `compose_yaml_validate.ComposeLoader`'s job, imported here rather
    than reimplemented. `yaml.safe_load` fails on two tracked files because
    Compose's own `!reset` and `!override` tags are not standard YAML, so a
    second loader would disagree with the gate about what a compose file is.

  * Whether a given probe is MEANINGFUL is a judgement about that service, not
    a property of the file. An earlier version of this tool split probes into
    "liveness-only" and "asserts something real" with a regex over command text
    and reported "92 of 100". That number was withdrawn: a regex is a way to
    find candidates, not a way to decide whether one qualifies.

What is left is arithmetic that holds: how many services declare a probe, how
many declare none, how many are explicitly disabled, and how many share one
byte-identical command after normalising host, port and env interpolation.
A probe reused verbatim across services that share nothing but a template is
checking the template.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def _loader():
    """Reuse the gate's loader, so this tool and the gate agree on 'parses'."""
    path = TOOLS / "compose_yaml_validate.py"
    spec = importlib.util.spec_from_file_location("compose_yaml_validate", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["compose_yaml_validate"] = mod
    spec.loader.exec_module(mod)
    return mod


def normalise(test) -> str:
    s = json.dumps(test)
    s = re.sub(r"\$\{[^}]*\}", "${X}", s)
    s = re.sub(r":\d+", ":PORT", s)
    s = re.sub(r"(https?://)[A-Za-z0-9._-]+", r"\1HOST", s)
    return s


def main() -> int:
    import yaml
    mod = _loader()
    path = TOOLS.parent / "docker-compose.yml"
    doc = yaml.load(path.read_text(encoding="utf-8"), Loader=mod.ComposeLoader)
    services = {k: v for k, v in (doc.get("services") or {}).items()
                if isinstance(v, dict)}

    declared, none_, disabled = {}, [], []
    for name, svc in services.items():
        hc = svc.get("healthcheck")
        if not hc:
            none_.append(name)
            continue
        test = hc.get("test")
        if hc.get("disable") or (isinstance(test, list) and test[:1] == ["NONE"]):
            disabled.append(name)
            continue
        declared[name] = test

    shapes = collections.Counter(normalise(t) for t in declared.values())
    print("services                     : %d" % len(services))
    print("declare a healthcheck        : %d" % (len(declared) + len(disabled)))
    print("declare none                 : %d" % len(none_))
    print("explicitly disabled          : %d  %s" % (len(disabled), disabled or ""))
    print("distinct command shapes      : %d" % len(shapes))
    print()
    print("most-reused shapes:")
    for shape, n in shapes.most_common(5):
        print("  %3dx %s" % (n, shape[:96]))
    print()
    print("NOT reported here: whether any of these mean anything. That is a")
    print("per-service judgement; see the audit doc.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
