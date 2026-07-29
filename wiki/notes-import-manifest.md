---
type: manifest
title: "Notes-Import Ingestion Manifest"
scope: "raw/notes-import/"
date_updated: 2020-01-01  # placeholder — the first chunk overwrites this
notes_recorded: 0
chunks_recorded: 0
---

# Notes-Import Ingestion Manifest

Durable progress ledger for the `batch-ingest` skill, which drains the legacy
note export in `raw/notes-import/` into the wiki a batch at a time.

**This file is the cursor.** A note that appears in the *Note ledger* below has
been dealt with — ingested, folded into an existing page, or deliberately
skipped — and will never be picked up again. A note that does not appear is
still in the backlog. Nothing else tracks progress: not the git log, not
`wiki/log.md`, not the digest receipts. If a run crashes, is interrupted, or is
killed halfway, the next run recomputes the backlog from this file and picks up
exactly where the last committed chunk stopped.

Each chunk commits its own ledger rows as part of its single atomic commit, so
the ledger can never be ahead of the wiki pages it describes.

## Schema

### Chunk log

One row per chunk that was validated and merged into `main`.

| Column | Meaning |
|---|---|
| Run ID | `YYYYMMDD-HHMMSS` plus a short random suffix, assigned by the orchestrator at the start of a run |
| Chunk | 1-based chunk index within that run |
| Notes | How many notes the chunk processed |
| Commit | Short SHA of the chunk's atomic commit |
| Date | Date the chunk was merged (`YYYY-MM-DD`) |

### Note ledger

One row per note, appended by the chunk that handled it.

| Column | Meaning |
|---|---|
| Note | Repo-relative path to the raw note, in backticks |
| Disposition | `source`, `fold`, or `skip` |
| Target | Wiki page the note landed in, in backticks. Empty for `skip` |
| Run ID | The run that handled it |
| Date | `YYYY-MM-DD` |

Disposition meanings:

- **`source`** — substantial standalone content; got its own `wiki/sources/`
  page plus propagation to entity / topic / insight / glossary pages.
- **`fold`** — a fragment of a theme that already had a strong wiki page; that
  page was updated and no new source page was created.
- **`skip`** — trivial or non-content (stub, ephemeral todo, empty, single bare
  link, near-exact duplicate of an already-ingested note). No wiki write.

Example ledger row (illustrative only — do not leave rows like this in the
table below):

```text
| `raw/notes-import/2019-04-02-team-offsite.md` | source | `wiki/sources/team-offsite-apr-2019.md` | 20260729-142233-a1b2c3 | 2026-07-29 |
```

## Computing the remaining backlog

Run from the vault root. Everything under `raw/notes-import/` that is not in the
ledger is still queued:

```bash
awk '/^## Note ledger/,0' wiki/notes-import-manifest.md \
  | awk -F'|' '/raw\/notes-import\// { gsub(/[` ]/, "", $2); print $2 }' \
  | LC_ALL=C sort -u > "${TMPDIR:-/tmp}/ni-done.txt"
find raw/notes-import -type f -name '*.md' \
  ! -name '2020-01-01-sample-note.md' \
  | LC_ALL=C sort > "${TMPDIR:-/tmp}/ni-disk.txt"
comm -23 "${TMPDIR:-/tmp}/ni-disk.txt" "${TMPDIR:-/tmp}/ni-done.txt" | wc -l
```

The first `awk` range starts at the `## Note ledger` heading, so the example row
above and any prose that mentions a path are never mistaken for ledger entries.
Keep the *Note ledger* section last in this file for that reason. The second
`awk` reads the path out of column 2 and strips backticks and spaces, so a row
written without backticks still resolves.

The `! -name` exclusion keeps the template's shipped placeholder note,
`raw/notes-import/2020-01-01-sample-note.md`, out of the backlog. On a fresh
clone it is the *only* file in the folder, so without the exclusion the first run
would ingest a demo stub as real content and record it here permanently. Delete
the placeholder once the real export is in place; the exclusion then does
nothing.

## Lint note

This file passes Layer 2 only because of **two** registrations in
`.claude/scripts/wiki-lint.py`, and both must exist for it to lint clean:

1. `"manifest": []` in `REQUIRED_KEYS_BY_TYPE` — declares `type: manifest` as a
   known page type with no required keys. Without it every run reports `FM003`
   (unknown `type:`) against this file. `FM003` is a warning rather than an
   error, so the exit code stays 0 — which is worse, not better: it rots quietly
   under the vault's zero-warnings convention instead of failing loudly.
2. `"wiki/notes-import-manifest.md"` in the entry-point allow-list near the top
   of the orphan advisory report — without it the manifest is reported as an
   orphan by `wiki-lint.py --report orphans`, since nothing wikilinks to it.

**Land this file and those two script entries in the same commit.** Split across
commits — or if the script edit is reverted — this file starts emitting warnings
the moment it exists, and whoever sees them has no way to tell an intentional
page type from a typo.

The file lives at the `wiki/` root, outside `regenerate-index.py`'s walk of the
six page-type folders, so it never affects the index drift check. It is not a
synthesis page, so the Recent-updates callout rules do not apply — history lives
in the *Chunk log* and in git.

The tables must stay well-formed for Layer 1 (`markdownlint-obsidian`): leading
and trailing pipes on every row, and the same column count as the header.

## Chunk log

| Run ID | Chunk | Notes | Commit | Date |
|---|---|---|---|---|

## Note ledger

| Note | Disposition | Target | Run ID | Date |
|---|---|---|---|---|
