#!/usr/bin/env bash
#
# setup.sh — one-time bootstrap for the LLM Wiki template.
#
# Wires up qmd (the local search engine that powers retrieval) so that Claude
# can actually search your vault. Safe to run more than once — it skips work
# that's already done.
#
# Usage:   ./setup.sh
# (If you get "permission denied", run:  bash setup.sh)

set -euo pipefail

# Always operate from the vault root (the folder this script lives in),
# so qmd's project-local index lands in the right place.
cd "$(dirname "$0")"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }

bold "LLM Wiki — setup"
echo

# --- 1. Check prerequisites ---------------------------------------------------

if ! command -v qmd >/dev/null 2>&1; then
  warn "qmd is not installed."
  echo
  echo "  qmd is the search engine that powers this wiki. Install it with:"
  echo
  echo "      npm install -g @tobilu/qmd"
  echo
  echo "  (That needs Node.js — install the LTS version from https://nodejs.org"
  echo "   first if 'npm' is also missing.) Then run ./setup.sh again."
  exit 1
fi
ok "qmd is installed ($(qmd --version 2>/dev/null || echo 'version unknown'))"

# --- 2. Create the project-local index ---------------------------------------

if [ ! -d ".qmd" ]; then
  qmd init >/dev/null
  ok "Created a local search index (.qmd/)"
else
  ok "Local search index already exists (.qmd/)"
fi

# --- 3. Register collections --------------------------------------------------
# name → folder. These names match the collections referenced in CLAUDE.md.
# Folders that don't exist yet are skipped (you can re-run setup.sh later).

add_collection() {
  local name="$1" path="$2"
  if [ ! -d "$path" ]; then
    warn "skip '$name' — folder $path not present yet"
    return
  fi
  if qmd collection list 2>/dev/null | grep -q "^$name "; then
    ok "collection '$name' already registered"
    return
  fi
  qmd collection add "$name" "$path" >/dev/null
  ok "registered collection '$name' → $path"
}

add_collection wiki         ./wiki
add_collection notes-import ./raw/notes-import
add_collection books        ./raw/books
add_collection web-articles ./raw/web-clippings
add_collection meetings     ./raw/meetings
add_collection captures     ./raw/captures
add_collection briefings    ./raw/briefings
add_collection claude-chats ./raw/claude-chats
add_collection projects     ./raw/projects
add_collection research     ./raw/research
add_collection authored     ./raw/authored

# --- 4. Index + embed ---------------------------------------------------------

echo
bold "Indexing your notes (this can take a few minutes the first time)…"
qmd update  >/dev/null && ok "Indexed all collections (keyword search ready)"
qmd embed   >/dev/null && ok "Generated embeddings (semantic search ready)"

# --- 5. Done ------------------------------------------------------------------

echo
bold "Setup complete."
echo
echo "  Search is wired up. The qmd MCP server is registered in .mcp.json, so"
echo "  Claude Code will connect to it automatically when you open this folder."
echo
echo "  Next:"
echo "    1. Open this folder in Claude Code."
echo "    2. If asked to trust the project / its MCP servers, say yes."
echo "    3. Try asking Claude a question about your notes."
echo
echo "  Whenever you add or change notes, re-run:  qmd update && qmd embed"
echo "  (or just ./setup.sh again)."
