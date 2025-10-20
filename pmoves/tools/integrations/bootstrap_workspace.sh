#!/usr/bin/env bash
set -euo pipefail

BASE_DIR=${1:-integrations-workspace}

WGER_URL=${WGER_URL:-https://github.com/POWERFULMOVES/Pmoves-Health-wger.git}
FIREFLY_URL=${FIREFLY_URL:-https://github.com/POWERFULMOVES/pmoves-firefly-iii.git}
OPEN_NOTEBOOK_URL=${OPEN_NOTEBOOK_URL:-https://github.com/POWERFULMOVES/Pmoves-open-notebook.git}
JELLYFIN_URL=${JELLYFIN_URL:-https://github.com/POWERFULMOVES/PMOVES-jellyfin.git}

here=$(cd "$(dirname "$0")" && pwd)
kit_sh="$here/apply_pr_kit.sh"

mkdir -p "$BASE_DIR"
cd "$BASE_DIR"

clone_if_missing(){
  local url="$1"; local dir="$2";
  if [[ -d "$dir/.git" ]]; then
    echo "✔ Repo exists: $dir"
  else
    echo "→ Cloning $url into $dir"; git clone "$url" "$dir"
  fi
}

clone_if_missing "$WGER_URL" Pmoves-Health-wger
clone_if_missing "$FIREFLY_URL" PMOVES-Firefly-iii
clone_if_missing "$OPEN_NOTEBOOK_URL" Pmoves-open-notebook
clone_if_missing "$JELLYFIN_URL" PMOVES-jellyfin

echo "\n→ Applying PR kits"
"$kit_sh" --kit wger --repo "$(pwd)/Pmoves-Health-wger"
"$kit_sh" --kit firefly --repo "$(pwd)/PMOVES-Firefly-iii"
"$kit_sh" --kit open-notebook --repo "$(pwd)/Pmoves-open-notebook"
"$kit_sh" --kit jellyfin --repo "$(pwd)/PMOVES-jellyfin"

cat <<EOS

All branches created: chore/pmoves-net+ghcr
Next steps (run in each repo folder):
  git push -u origin chore/pmoves-net+ghcr
  Open a PR on GitHub (title: "chore: PMOVES integration — pmoves-net compose + GHCR publish")

After merges, in PMOVES repo run:
  make -C pmoves up-external

EOS
