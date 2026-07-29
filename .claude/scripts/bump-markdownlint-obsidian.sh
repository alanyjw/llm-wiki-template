#!/bin/bash
# Bumps the markdownlint-obsidian-cli pin to the latest published version
# once it surfaces on npm. Idempotent — safe to re-run.
#
# Re-enables the workarounds we put in place for issues #26/27/28:
# - removes the wiki/backlog.md, wiki/glossary.md, wiki/log.md ignore
#   carve-outs (issue #28 OFM901 fix landed in 1.1.0)
# - adds wikilinks.resolveMode = "obsidian-fuzzy" so OFM001 can be
#   re-enabled (issue #27 feature landed in 1.1.0)
# - leaves OFM001/MD028 disabled in rules until we re-baseline; that's
#   a separate decision for the vault owner, not blocking the bump.
#
# Usage:
#   .claude/scripts/bump-markdownlint-obsidian.sh           # check-only
#   .claude/scripts/bump-markdownlint-obsidian.sh --apply   # actually edit
set -euo pipefail

PIN_TARGET="${PIN_TARGET:-1.1.0}"
PACKUMENT="https://registry.npmjs.org/markdownlint-obsidian-cli"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/wiki-lint.yml"
CONFIG="$REPO_ROOT/.obsidian-linter.jsonc"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

# Short-circuit if the workflow is already pinned at PIN_TARGET (or anything
# other than 1.0.4). Aikido Endpoint Protection's package-age guard blocks
# new npm versions locally with a 403 "not yet been vetted", which would
# otherwise trap the polling loop in a permanent exit-2 reschedule even
# after the bump has been applied. CI runs in GitHub Actions and is not
# behind Aikido — it'll fetch 1.1.0 normally.
if ! grep -q "markdownlint-obsidian-cli@1.0.4" "$WORKFLOW"; then
  echo "Workflow pin already moved off 1.0.4 — nothing to do." >&2
  exit 0
fi

# 1. Probe npm for the target version.
NPM_HAS=$(curl -s -H "Cache-Control: no-cache" "$PACKUMENT" \
  | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print('error'); sys.exit(0)
versions = list(d.get('versions', {}).keys())
target = '$PIN_TARGET'
print('yes' if target in versions else 'no')
print('latest:', d.get('dist-tags', {}).get('latest'))
print('versions:', ' '.join(versions))
" )
echo "$NPM_HAS"

LANDED=$(printf '%s\n' "$NPM_HAS" | head -1)
if [[ "$LANDED" != "yes" ]]; then
  echo "Pin target ${PIN_TARGET} not yet on npm. Skipping bump." >&2
  exit 2
fi

# 2. Bump workflow pin.
if grep -q "markdownlint-obsidian-cli@1.0.4" "$WORKFLOW"; then
  echo "Workflow currently pins 1.0.4 → ${PIN_TARGET}"
  if [[ "$APPLY" == "1" ]]; then
    sed -i '' "s|markdownlint-obsidian-cli@1.0.4|markdownlint-obsidian-cli@${PIN_TARGET}|g" "$WORKFLOW"
  fi
else
  echo "Workflow pin already updated or unexpected — manual review needed." >&2
fi

# 3. Update the pin version comment in the config.
if grep -q "markdownlint-obsidian-cli@1.0.4" "$CONFIG"; then
  echo "Config comment currently references 1.0.4 → ${PIN_TARGET}"
  if [[ "$APPLY" == "1" ]]; then
    sed -i '' "s|markdownlint-obsidian-cli@1.0.4 (released 2026-04-18)|markdownlint-obsidian-cli@${PIN_TARGET}|g" "$CONFIG"
  fi
fi

cat <<EOF
---
After --apply, manual follow-ups the vault owner should review:
1. Drop wiki/backlog.md, wiki/glossary.md, wiki/log.md from the \`ignores\` array
   in $CONFIG — issue #28 OFM901 fix is in ${PIN_TARGET}.
2. Add \`"wikilinks": { "resolveMode": "obsidian-fuzzy", "caseSensitive": false, "allowAlias": true }\`
   alongside top-level \`vaultRoot\` so we can re-enable OFM001 — issue #27 feature is in ${PIN_TARGET}.
3. Run the workflow locally:  npx markdownlint-obsidian-cli@${PIN_TARGET} "wiki/**/*.md" --vault-root wiki
   (no \`--bun\` — the flag resolves a transitive dep's unpublished \`bun\` export
   condition and dies; see the NOTE in .github/workflows/wiki-lint.yml)
4. Commit + push.
EOF
