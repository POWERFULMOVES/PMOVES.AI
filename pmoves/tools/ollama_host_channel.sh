#!/bin/sh
# Ollama host release channel: follow upstream releases on a node's HOST Ollama
# (systemd, not the compose image -- that one is Dependabot's, .github/dependabot.yml),
# gated so an upgrade cannot silently break the shared model store.
#
#   ollama_host_channel.sh resolve            host version vs latest upstream release
#   (VERSION may also arrive as OLLAMA_CHANNEL_VERSION -- how the make targets pass it)
#   ollama_host_channel.sh canary  [VERSION]  A/B the host version against VERSION
#                                             (default: latest) on a COPY of one model
#   ollama_host_channel.sh install VERSION    install VERSION; refuses unless its canary passed
#   ollama_host_channel.sh rollback           print how to restore the store index + old binary
#
# Why a gate (measured on SPARK, 2026-10-15): 0.40.4 rewrites the store to
# manifests-v2 on first use, so pointing it at the live store converts every
# model in place, and whether older versions read the result is unknown. It also
# loaded 7/37 GPU layers where 0.30.0 loaded 18/37. "Follow every release" is the
# policy; this tool makes each step of it reversible and measured.
#
# canary never touches the live store or the host service. It backs up the
# store's manifests (small; blobs are content-addressed and never rewritten),
# copies ONE model to a scratch store beside the live one, and runs the host's
# version and the candidate as containers on that copy, one after the other.
# Verdict PASS needs: the candidate serves the model, its best GPU-layer count is
# within OLLAMA_CANARY_LAYER_MARGIN (default 2) of the baseline's best over
# OLLAMA_CANARY_RUNS samples each (default 2), and the store layout is unchanged.
# OLLAMA_ACCEPT_STORE_MIGRATION=1 turns a layout change into a PASS-with-warning
# for an operator who has decided to cross that line.
#
# install runs upstream's installer pinned to the version (OLLAMA_VERSION=...)
# and needs root; it is for the operator, not for an agent.
set -eu

DOCKER="${DOCKER:-docker}"
MODEL="${OLLAMA_CANARY_MODEL:-qwen3-embedding:4b}"
PORT="${OLLAMA_CANARY_PORT:-11499}"
RUNS="${OLLAMA_CANARY_RUNS:-2}"
MARGIN="${OLLAMA_CANARY_LAYER_MARGIN:-2}"
# Under 'sudo make ... ollama-host-install' HOME is root's and OLLAMA_CHANNEL_STATE
# is dropped, so derive the default from the invoking user: install must find the
# canary report that user's run wrote.
_home="$HOME"
if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
  _home=$(getent passwd "$SUDO_USER" | cut -d: -f6); _home="${_home:-$HOME}"
fi
STATE="${OLLAMA_CHANNEL_STATE:-$_home/.local/state/pmoves/ollama-channel}"
UPSTREAM="${OLLAMA_UPSTREAM_REPO:-ollama/ollama}"

die() { echo "✖ $2" >&2; exit "$1"; }

# need NAME VALUE ERE -- single line, full match, no leading '-', no '..'
need() {
  case "$2" in
    "") die 2 "$1 is required" ;;
    -*|*..*) die 2 "$1 rejected (leading '-' or '..')" ;;
  esac
  [ "$(printf '%s' "$2" | wc -l)" -eq 0 ] || die 2 "$1 rejected (multi-line)"
  printf '%s' "$2" | grep -Eqx -- "$3" || die 2 "$1 rejected (charset/shape)"
}

VER='v?[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(-rc[0-9]{1,3})?'
need OLLAMA_CANARY_MODEL "$MODEL" '[A-Za-z0-9._/-]{1,80}(:[A-Za-z0-9._-]{1,64})?'
need OLLAMA_CANARY_PORT "$PORT" '[0-9]{4,5}'
need OLLAMA_CANARY_RUNS "$RUNS" '[1-9]'
need OLLAMA_CANARY_LAYER_MARGIN "$MARGIN" '[0-9]{1,2}'
need OLLAMA_UPSTREAM_REPO "$UPSTREAM" '[A-Za-z0-9._-]+/[A-Za-z0-9._-]+'

strip_v() { printf '%s' "$1" | sed 's/^v//'; }

host_version() {
  command -v ollama >/dev/null 2>&1 || { echo none; return; }
  ollama --version 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+(-rc[0-9]+)?' | tail -1
}

latest_version() {
  v=$(curl -fsSL --max-time 15 "https://api.github.com/repos/$UPSTREAM/releases/latest" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])') \
    || die 3 "could not resolve the latest $UPSTREAM release"
  need RELEASE "$v" "$VER"
  strip_v "$v"
}

# The store the HOST service uses. Backup, canary and rollback all act on it, so
# a wrong guess is worse than none: OLLAMA_CHANNEL_MODELS wins, then systemd's
# Environment= and EnvironmentFile=, then upstream's default only if it exists.
models_dir() {
  d="${OLLAMA_CHANNEL_MODELS:-}"
  [ -n "$d" ] || d=$(systemctl show ollama -p Environment --value 2>/dev/null | tr ' ' '\n' \
      | sed -n 's/^"\{0,1\}OLLAMA_MODELS=//p' | sed 's/"$//' | tail -1)
  if [ -z "$d" ]; then
    for f in $(systemctl show ollama -p EnvironmentFiles --value 2>/dev/null | sed 's/ (ignore_errors=[a-z]*)//g'); do
      [ -r "$f" ] && d=$(sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}OLLAMA_MODELS=//p' "$f" | tr -d "\"'" | tail -1)
      [ -z "$d" ] || break
    done
  fi
  [ -n "$d" ] || d=/usr/share/ollama/.ollama/models
  [ -d "$d" ] || die 2 "model store not found ($d); set OLLAMA_CHANNEL_MODELS"
  printf '%s' "$d"
}

manifest_path() {  # store, model -> manifest file (library models only)
  name=${2%%:*}; tag=${2#*:}; [ "$tag" = "$2" ] && tag=latest
  case "$name" in */*) ns=$name ;; *) ns="library/$name" ;; esac
  printf '%s/manifests/registry.ollama.ai/%s/%s' "$1" "$ns" "$tag"
}

# Run VERSION against SCRATCH, embed once, print "<layers_on_gpu> <layers_total>".
probe() {
  ver=$1 scratch=$2 name="ollama-canary-$(printf '%s' "$1" | tr . -)"
  "$DOCKER" container rm "$name" >/dev/null 2>&1 || true
  "$DOCKER" run -d --name "$name" --gpus all -p "127.0.0.1:$PORT:11434" \
    -e OLLAMA_NOPRUNE=1 -v "$scratch:/root/.ollama/models" "ollama/ollama:$ver" >/dev/null
  i=0; until curl -fsS --max-time 2 "http://127.0.0.1:$PORT/api/version" >/dev/null 2>&1; do
    i=$((i+1)); [ $i -lt 60 ] || { "$DOCKER" logs --tail 20 "$name" >&2; "$DOCKER" stop "$name" >/dev/null; "$DOCKER" container rm "$name" >/dev/null; die 4 "ollama $ver never answered"; }
    sleep 1
  done
  ok=$(curl -s --max-time 300 "http://127.0.0.1:$PORT/api/embed" \
        -d "{\"model\":\"$MODEL\",\"input\":\"pmoves canary\"}" \
       | python3 -c 'import json,sys
try: print("yes" if json.load(sys.stdin).get("embeddings") else "no")
except Exception: print("no")')
  layers=$("$DOCKER" logs "$name" 2>&1 | grep -Eo 'offloaded [0-9]+/[0-9]+ layers' | tail -1 \
           | grep -Eo '[0-9]+/[0-9]+' | tr / ' ')
  "$DOCKER" stop "$name" >/dev/null; "$DOCKER" container rm "$name" >/dev/null
  [ "$ok" = yes ] || die 4 "ollama $ver could not serve $MODEL from the copied store"
  printf '%s' "${layers:-0 0}"
}

cmd="${1:-}"
case "$cmd" in
resolve)
  echo "host:   $(host_version)  (store: $(models_dir))"
  echo "latest: $(latest_version)  ($UPSTREAM)"
  ;;

canary)
  cand="${2:-${OLLAMA_CHANNEL_VERSION:-}}"
  [ -n "$cand" ] || cand=$(latest_version)
  need VERSION "$cand" "$VER"; cand=$(strip_v "$cand")
  base=$(host_version); [ "$base" != none ] || die 2 "no host ollama to compare against"
  store=$(models_dir); man=$(manifest_path "$store" "$MODEL")
  [ -f "$man" ] || die 2 "$MODEL is not in the host store ($man)"
  mkdir -p "$STATE"
  stamp=$(date -u +%Y%m%dT%H%M%SZ)

  # 1. Back up the store index. Manifests are the part a migration rewrites.
  bak="$STATE/manifests-$base-$stamp.tar.gz"
  tar -C "$store" -czf "$bak" manifests
  echo "→ store index backed up: $bak"

  # 2. Copy ONE model into a scratch store beside the live one (same disk, so the
  #    copy is a fair I/O match), never inside it.
  # Store's parent is often owned by the ollama user; walk up to the first
  # directory we can write (same disk, so the copy is still a fair I/O match).
  root="${OLLAMA_CANARY_DIR:-}"
  if [ -z "$root" ]; then
    for d in "$(dirname "$store")" "$(dirname "$(dirname "$store")")" "$STATE"; do
      [ -w "$d" ] && { root=$d; break; }
    done
  fi
  [ -n "$root" ] && [ -w "$root" ] || die 2 "no writable scratch dir near $store (set OLLAMA_CANARY_DIR)"
  scratch="$root/ollama-canary-$stamp/models"
  rel=${man#"$store"/}
  mkdir -p "$scratch/$(dirname "$rel")" "$scratch/blobs"
  cp "$man" "$scratch/$rel"
  python3 -c 'import json,sys; m=json.load(open(sys.argv[1]))
print("\n".join(x["digest"].replace(":","-") for x in [m["config"]]+m["layers"]))' "$man" \
    | while read -r b; do cp "$store/blobs/$b" "$scratch/blobs/$b"; done
  before=$(ls "$scratch" | sort | tr '\n' ' ')
  cleanup() {
    # The containers write as root; clear the scratch store from inside one.
    "$DOCKER" run --rm --entrypoint find -v "$(dirname "$scratch"):/x" "ollama/ollama:$cand" \
      /x -mindepth 1 -delete >/dev/null 2>&1 || true
    rmdir "$(dirname "$scratch")" 2>/dev/null || true
  }
  trap cleanup EXIT
  trap 'cleanup; exit 130' INT TERM

  # 3. A/B on the copy. GPU layer counts move with free memory at load time
  #    (same version: 18/37 one hour, 7/37 the next on SPARK), so one sample per
  #    side is noise. Take RUNS samples per side, keep each side's best, and
  #    refuse only past MARGIN layers. All baseline runs come first: the
  #    candidate may migrate the copy, and the baseline must not see that.
  b_on=0 b_all=0 c_on=0 c_all=0 b_seen="" c_seen=""
  i=0; while [ $i -lt "$RUNS" ]; do i=$((i+1))
    echo "→ baseline ollama $base on a copy of $MODEL (run $i/$RUNS)"
    out=$(probe "$base" "$scratch"); set -- $out
    b_seen="$b_seen $1/$2"; [ "$1" -gt "$b_on" ] && b_on=$1; b_all=$2
  done
  i=0; while [ $i -lt "$RUNS" ]; do i=$((i+1))
    echo "→ candidate ollama $cand on the same copy (run $i/$RUNS)"
    out=$(probe "$cand" "$scratch"); set -- $out
    c_seen="$c_seen $1/$2"; [ "$1" -gt "$c_on" ] && c_on=$1; c_all=$2
  done
  after=$(ls "$scratch" | sort | tr '\n' ' ')

  verdict=PASS; why=""
  if [ $((c_on + MARGIN)) -lt "$b_on" ]; then
    verdict=REFUSE; why="$why offload regressed beyond the ${MARGIN}-layer margin (best $c_on/$c_all < best $b_on/$b_all);"
  fi
  if [ "$before" != "$after" ]; then
    if [ "${OLLAMA_ACCEPT_STORE_MIGRATION:-}" = 1 ]; then
      why="$why store layout changed [$before] -> [$after] (accepted by operator);"
    else
      verdict=REFUSE; why="$why store layout changed [$before] -> [$after]: $cand would migrate the live store (OLLAMA_ACCEPT_STORE_MIGRATION=1 to accept);"
    fi
  fi
  report="$STATE/canary-$cand.json"
  python3 - "$report" "$verdict" "$base" "$cand" "$MODEL" "$b_on/$b_all" "$c_on/$c_all" "$bak" "${why# }" "${b_seen# }" "${c_seen# }" "$MARGIN" <<'EOF'
import json, sys, datetime
p, verdict, base, cand, model, b, c, bak, why, bs, cs, margin = sys.argv[1:]
json.dump({"verdict": verdict, "baseline": base, "candidate": cand, "model": model,
           "gpu_layers": {"baseline_best": b, "candidate_best": c,
                          "baseline_runs": bs.split(), "candidate_runs": cs.split(),
                          "margin_layers": int(margin)},
           "store_backup": bak,
           "reasons": why, "at": datetime.datetime.now(datetime.timezone.utc).isoformat()},
          open(p, "w"), indent=2)
EOF
  echo "baseline $base:${b_seen} (best $b_on) | candidate $cand:${c_seen} (best $c_on) | margin $MARGIN"
  [ -z "$why" ] || echo "notes: ${why# }"
  echo "$verdict -> $report"
  [ "$verdict" = PASS ] || exit 1
  ;;

install)
  ver="${2:-${OLLAMA_CHANNEL_VERSION:-}}"
  need VERSION "$ver" "$VER"; ver=$(strip_v "$ver")
  report="$STATE/canary-$ver.json"
  [ -f "$report" ] || die 3 "no canary for $ver: run 'make ollama-host-canary VERSION=$ver' first"
  python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["verdict"]=="PASS" else 1)' "$report" \
    || die 3 "canary for $ver did not PASS ($report); refusing"
  [ "$(id -u)" -eq 0 ] || die 3 "install needs root: sudo make -C pmoves ollama-host-install VERSION=$ver"
  before=$(curl -fsS --max-time 5 http://127.0.0.1:11434/api/tags | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))' || echo "?")
  store=$(models_dir); mkdir -p "$STATE"
  bak="$STATE/manifests-$(host_version)-$(date -u +%Y%m%dT%H%M%SZ)-preinstall.tar.gz"
  tar -C "$store" -czf "$bak" manifests
  echo "→ store index backed up right before install: $bak"
  echo "→ installing ollama $ver via upstream installer (models before: $before)"
  curl -fsSL https://ollama.com/install.sh | OLLAMA_VERSION="$ver" sh
  systemctl restart ollama
  i=0; until curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; do
    i=$((i+1)); [ $i -lt 60 ] || die 4 "ollama did not come back after install"; sleep 1; done
  now=$(host_version)
  after=$(curl -fsS --max-time 5 http://127.0.0.1:11434/api/tags | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))' || echo "?")
  [ "$now" = "$ver" ] || die 4 "host reports $now after installing $ver"
  [ "$after" = "$before" ] || die 4 "model count changed $before -> $after; see: $0 rollback"
  echo "✔ host ollama $now, $after models. Re-apply suit variants: make -C pmoves models-suit-ollama CHECK=1"
  ;;

rollback)
  echo "Restore the store index from the newest backup, then pin the old binary:"
  ls -1t "$STATE"/manifests-*.tar.gz 2>/dev/null | head -3 | sed 's/^/  backup: /'
  store=$(models_dir)
  echo "  sudo systemctl stop ollama"
  echo "  # models pulled AFTER a migration exist only in manifests-v2: re-pull them after rollback"
  echo "  sudo find $store/manifests-v2 $store/metadata -delete   # only what a migration created"
  echo "  sudo tar -C $store -xzf <backup>     # manifests only; blobs are untouched"
  echo "  curl -fsSL https://ollama.com/install.sh | sudo OLLAMA_VERSION=<old> sh"
  echo "  # first start with OLLAMA_NOPRUNE=1 so the old binary does not prune v2-only blobs:"
  echo "  sudo systemctl set-environment OLLAMA_NOPRUNE=1 && sudo systemctl start ollama"
  ;;

*)
  sed -n '2,12p' "$0" >&2; exit 2 ;;
esac
