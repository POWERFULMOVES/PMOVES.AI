#!/usr/bin/env bash
# pm-theme-banner.sh — render the agent's own theme at launch.
# ===========================================================================
# WHY THIS EXISTS
# ---------------
# Operator, 2026-10-11 (verbatim): "a lot was done howeever not wired includeing
# the themes glyphs and all the customization work that went in which should
# load with claude-pmoves". The work exists: pmoves/config/agent_signatures.yaml
# carries glyph, colour and voice per identity, and
# pmoves/tools/agent_terminal_theme.py renders it (`--agent 5090-claude
# --banner` renders on 5090, measured 2026-10-11). No launcher called it, so the
# customization never reached a session.
#
# THE CONTRACT
# ------------
# pm_theme_banner ROOT AGENT_ID [PYTHON...]
#
#   ALWAYS returns 0 (fail-open: a missing theme costs a banner, not the
#   launch). Writes the banner to stderr so the TUI paints after it. Sets:
#     PM_THEME_OK    1 rendered, 0 not rendered
#     PM_THEME_LINE  one line for stderr, prefixed by the caller
#
# AGENT_ID is the signing-card spelling (PM_IDENT_CIPHER_ID, e.g. 5090-claude),
# which is also the key agent_signatures.yaml uses. PYTHON... is the resolved
# interpreter (pm-python.sh's PM_IDENT_PY array); defaults to `python3`.

pm_theme_banner() {
  local root="$1" agent="${2:-}"
  shift 2 2>/dev/null || shift $#
  PM_THEME_OK=0
  PM_THEME_LINE=""

  if [ -z "$agent" ]; then
    PM_THEME_LINE="theme=SKIP (no signing-card id resolved this session)"
    return 0
  fi
  local tool="$root/pmoves/tools/agent_terminal_theme.py"
  if [ ! -f "$tool" ]; then
    PM_THEME_LINE="theme=SKIP (no $tool)"
    return 0
  fi

  local -a py
  if [ "$#" -gt 0 ]; then py=("$@"); else py=(python3); fi

  local banner
  if banner="$("${py[@]}" "$tool" --agent "$agent" --banner 2>/dev/null)" && [ -n "$banner" ]; then
    printf '%s\n' "$banner" >&2
    PM_THEME_OK=1
    PM_THEME_LINE="theme=rendered for ${agent} (pmoves/config/agent_signatures.yaml)"
  else
    PM_THEME_LINE="theme=UNAVAILABLE for ${agent} -- agent_terminal_theme.py rendered nothing; check agent_signatures.yaml has that id"
  fi
  return 0
}
