#!/bin/sh
# qmd-refresh-hook.sh — refresh the qmd index after remote content arrives.
#
# Called by .git/hooks/post-merge (git pull / merge) and .git/hooks/post-rewrite
# (git rebase — the fetch+rebase flow used after a rejected push). Those hook
# files are thin wrappers; this script is the committed source of truth.
#
# Hooks are machine-local (git does not sync .git/hooks), so NOTHING installs
# this for you — the script ships dormant until you run the snippet below once
# per machine/clone. Do it now if you have not:
#
#   chmod +x .claude/scripts/qmd-refresh-hook.sh
#   for h in post-merge post-rewrite; do
#     printf '#!/bin/sh\nexec "$(git rev-parse --show-toplevel)/.claude/scripts/qmd-refresh-hook.sh" "$@"\n' > .git/hooks/$h
#     chmod +x .git/hooks/$h
#   done
#
# Verify: `ls -l .git/hooks/post-merge .git/hooks/post-rewrite` shows both as
# executable, and a pull that touches raw/ or wiki/ appends a line to
# $TMPDIR/qmd-embed.log.
#
# Why this exists: if you sync the vault across machines (or a scheduled agent
# pushes to the remote), a `git pull` can drop dozens of new markdown files into
# raw/ and wiki/ without qmd noticing. Retrieval then silently answers from a
# stale index. This hook closes that window.
#
# Behaviour:
#   - Skips entirely unless the pulled/rebased range touched raw/ or wiki/
#     (the qmd-indexed folders; .claude/, docs/, templates/ churn is ignored).
#   - Runs `qmd update` synchronously — sub-second, keeps lex search correct
#     immediately after the pull.
#   - Runs `qmd embed` in the background under a lock — embed can take minutes
#     on a big pull and must never block the pull itself. If an embed is
#     already running, this batch is skipped; the next refresh (or any wiki
#     workflow's own `qmd update && qmd embed`) picks the content up.
#   - Always exits 0. A hook that fails the pull is worse than a stale index.

set -u

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

# --- Locate the qmd binary -------------------------------------------------
# Git hooks run in a NON-INTERACTIVE shell: your shell rc is not sourced, so
# nvm is not on PATH and a bare `qmd` often resolves to nothing even though it
# works fine in your terminal. Resolution order:
#   1. $QMD_BIN — set this to an absolute path if the fallbacks miss.
#   2. `command -v qmd` — works for a system-wide Node (Homebrew, nodejs.org
#      installer, Volta shim).
#   3. The nvm layout for the Node line pinned in .nvmrc.
QMD="${QMD_BIN:-}"

if [ -z "$QMD" ]; then
  QMD="$(command -v qmd 2>/dev/null)" || QMD=""
fi

if [ -z "$QMD" ] && [ -r "$REPO_ROOT/.nvmrc" ]; then
  NODE_LINE="$(tr -d ' \t\r\n' < "$REPO_ROOT/.nvmrc" | sed 's/^v//')"
  # One glob covers both a bare major ("22" -> v22.11.0) and a full pin
  # ("22.11.0" -> v22.11.0).
  #
  # Glob expansion is LEXICOGRAPHIC, not version-ordered: with both v22.9.0 and
  # v22.11.0 installed, `v22*` yields "v22.11.0 v22.9.0", so a naive
  # last-assignment-wins loop picks the OLDER line. That is invisible until qmd
  # is installed on only one of them. `sort -V` orders them numerically; the
  # comparison is done pairwise so paths containing spaces still survive (the
  # loop variable stays quoted, unlike a $(...) candidate list).
  for candidate in "$HOME/.nvm/versions/node/v$NODE_LINE"*/bin/qmd; do
    [ -x "$candidate" ] || continue
    if [ -z "$QMD" ]; then
      QMD="$candidate"
      continue
    fi
    newer="$(printf '%s\n%s\n' "$QMD" "$candidate" | sort -V 2>/dev/null | tail -n 1)"
    # If `sort -V` is unavailable, keep what we already have rather than
    # blanking QMD on an empty result.
    [ -n "$newer" ] && [ -x "$newer" ] && QMD="$newer"
  done
fi

if [ -z "$QMD" ] || [ ! -x "$QMD" ]; then
  echo "qmd-refresh-hook: qmd not found — set QMD_BIN to its absolute path" >&2
  exit 0
fi

LOCKDIR="${TMPDIR:-/tmp}/qmd-embed.lock"
LOG="${TMPDIR:-/tmp}/qmd-embed.log"

# post-rewrite fires for both rebase and `commit --amend`; only rebase brings
# in remote content. post-merge passes a squash flag, never "amend".
case "${1:-}" in
  amend) exit 0 ;;
esac

# Only refresh when the incoming range touched indexed folders. ORIG_HEAD is
# set by both merge and rebase; if it is missing (fresh clone), do nothing.
git diff --name-only ORIG_HEAD..HEAD 2>/dev/null | grep -qE '^(raw|wiki)/' || exit 0

"$QMD" update

# mkdir is the portable atomic lock (macOS has no flock). Skip if an embed is
# already running — the stale lock is cleaned by the trap in the subshell.
if mkdir "$LOCKDIR" 2>/dev/null; then
  (
    trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] qmd embed (post-pull refresh) starting" >>"$LOG"
    "$QMD" embed >>"$LOG" 2>&1
    rc=$?
    # Capture $? into rc BEFORE building the log line. Word expansion runs
    # left-to-right, so an inline `[$(date ...)] ... (exit $?)` would run date
    # first and report DATE's status — always 0. Since the embed is backgrounded
    # with all other output discarded, this line is the only visibility into
    # whether it worked, and an always-green log is worse than none.
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] qmd embed done (exit $rc)" >>"$LOG"
  ) </dev/null >/dev/null 2>&1 &
else
  echo "qmd-refresh-hook: embed already running — skipping (next refresh catches up)" >&2
fi

exit 0
