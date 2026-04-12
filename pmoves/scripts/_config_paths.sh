#!/usr/bin/env bash
# Canonical PMOVES config path resolution.
# Sourced by with-env.sh, CI workflows, and make targets.
# Single source-of-truth for host config directory — mirrors
# pmoves/tools/_secrets_common.py:host_config_dir().

pmoves_host_config_dir() {
  if [[ -n "${APPDATA:-}" ]]; then
    echo "${APPDATA}/pmoves"
  else
    echo "${XDG_CONFIG_HOME:-${HOME}/.config}/pmoves"
  fi
}
