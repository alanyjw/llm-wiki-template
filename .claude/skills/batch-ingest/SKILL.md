---
name: batch-ingest
description: Use when the vault owner says "batch ingest", "ingest notes batch", "run batch ingest", "drain the import backlog", "drain the notes-import backlog", or wants to process un-ingested raw/notes-import/ notes into the wiki. Manually-triggered batch ingestion of a legacy note export — ~100 notes per run (default; override "batch ingest 50"), split into sequential ~20-note chunks, each ingested by a fresh subagent in a disposable git worktree, with a durable manifest at wiki/notes-import-manifest.md so a crashed run resumes instead of restarting.
---

# Batch Ingest — draining a legacy note export

Nearly everyone arrives at this wiki with a backlog: a few hundred to a few
thousand notes exported out of a previous note-taking app (Evernote, Notion,
Bear, Apple Notes, Obsidian — whatever it was) sitting in `raw/notes-import/`,
none of it synthesized. This skill drains that backlog into `wiki/`, one batch at
a time.

**Manually triggered.** Nothing here runs on a schedule. The vault owner decides
when to spend a batch's worth of time and tokens.

Two procedures follow. Run the **Orchestrator procedure** in the main session.
When you are dispatched as a chunk subagent, run only the **Chunk procedure**.

## When to use

- The vault owner says "batch ingest", "ingest notes batch", "run batch ingest",
  "drain the import backlog", "drain the notes-import backlog", "process the
  legacy note export".
- A size override is honored: "batch ingest 50", "do 200 this run".
- **Not the same procedure as CLAUDE.md §Workflows → Batch Ingest**, which shares
  this skill's name but is a different, lighter thing: a handful of related notes
  in one session, no worktrees, no manifest, a single log entry. That one stays
  hand-run in the main session. Reach for *this* skill only when the backlog is
  large enough that one context window can't hold it and a crash halfway through
  would be expensive — the legacy-export case, hundreds to thousands of notes in
  `raw/notes-import/`.
- **Skip** if the manifest shows zero remaining notes — report backlog complete
  and stop.

## Why this shape

Three constraints produced the orchestrator/worker/worktree architecture. Keep
them in mind before "simplifying" any step away.

- **Fresh context per chunk.** Ingest quality degrades badly as a context window
  fills. By note 60 an agent is pattern-matching against its own earlier
  summaries instead of reading the note in front of it, and duplicate pages start
  appearing. A fresh subagent per ~20 notes keeps every chunk at full attention,
  at the cost of losing cross-chunk memory (which the manifest and `qmd` restore).
- **Disposable worktree per chunk.** A chunk touches 5-15 wiki pages. If the
  subagent dies mid-write, or writes something malformed, or the lint gate can't
  be cleaned, the damage must be discardable in one command. Working in a
  detached `git worktree` means a failed chunk is deleted, not un-picked apart —
  and the main tree is never left half-written.
- **Resumable manifest.** A 500-note run takes hours. Crashes, interrupts, and
  "I need my laptop back" all happen. `wiki/notes-import-manifest.md` records
  every note the moment its chunk commits, so the next run recomputes the backlog
  from the ledger and resumes at the exact boundary instead of restarting or
  double-ingesting.

## Configure

| Setting | Default | Notes |
|---|---|---|
| Source folder | `raw/notes-import/` | The legacy export. Read-only |
| Batch size per run | 100 notes | Override by number in the trigger phrase |
| Chunk size | ~20 notes | One fresh subagent per chunk |
| Manifest | `wiki/notes-import-manifest.md` | The durable cursor |
| Receipt folder | `raw/briefings/notes-import/` | One digest receipt per chunk |
| Worktree parent | `.claude/worktrees/` | The repo's existing worktree convention, already gitignored. Must not sit under `wiki/` or `raw/`, or the linter and index walker see the chunk's tree twice |
| Commit message | `wiki: batch ingest chunk <i> (<n> notes)` | Validated verbatim by the orchestrator |

## Orchestrator procedure (main session)

### 1. Pre-flight

- Confirm `qmd` is on PATH and `.claude/scripts/wiki-lint.py` and
  `.claude/scripts/regenerate-index.py` are present. `cd` to the vault root.
- **Stale-worktree sweep.** For each leftover `.claude/worktrees/notes-import-chunk-*`
  worktree from a prior run (`git worktree list`), test whether its `HEAD` is an ancestor of `main`
  (`git merge-base --is-ancestor <worktree HEAD> main`). Ancestor — already
  integrated, or killed before committing — discard with
  `git worktree remove --force`. **Not** an ancestor — it holds a completed,
  un-integrated chunk commit — **do not discard**: stop and tell the vault owner
  to integrate that commit manually or explicitly discard the worktree. Finish
  with `git worktree prune`.
- **Index catch-up.** Run `qmd update && qmd embed` *after* the sweep, so the
  index reflects only committed state.
- **Dirty-tree guard.** The tracked tree must have no uncommitted changes. If
  dirty, abort and ask the vault owner to commit or stash — it's their own work,
  and no step in this skill mutates the main tree outside a worktree. Untracked
  files are tolerated.
- **Record the baseline tip and run ID.** Capture `main`'s commit SHA as the
  *expected tip*, and a *run ID* of `YYYYMMDD-HHMMSS` plus a short random suffix
  (e.g. `20260729-142233-a1b2c3`).

### 2. Compute the batch

The manifest's *Note ledger* is the cursor. Everything on disk that isn't in the
ledger is still queued:

```bash
awk '/^## Note ledger/,0' wiki/notes-import-manifest.md \
  | awk -F'|' '/raw\/notes-import\// { gsub(/[` ]/, "", $2); print $2 }' \
  | LC_ALL=C sort -u > "${TMPDIR:-/tmp}/ni-done.txt"
find raw/notes-import -type f -name '*.md' \
  ! -name '2020-01-01-sample-note.md' \
  | LC_ALL=C sort > "${TMPDIR:-/tmp}/ni-disk.txt"
comm -23 "${TMPDIR:-/tmp}/ni-disk.txt" "${TMPDIR:-/tmp}/ni-done.txt" | head -n 100
```

Replace `100` with the vault owner's override if they gave one. Zero rows means
the backlog is complete — report and exit.

**The `! -name` exclusion is deliberate.** The template ships a placeholder note
at `raw/notes-import/2020-01-01-sample-note.md` purely to show the folder's
shape. Without the exclusion it *is* the entire backlog on a fresh clone, and the
first run triages a demo stub as `source`, writes a real `wiki/sources/` page for
a book nobody read, and records it in the ledger where it can never be re-picked
or reconsidered. Once the real export is dropped in, delete the placeholder and
the exclusion becomes a no-op. If `raw/notes-import/` holds nothing *but* that
placeholder, the backlog is legitimately empty — report that the export hasn't
landed yet and stop, rather than reaching for the one file that's there.

Echo back to the vault owner: total on disk, total already recorded, remaining,
and how many this run will take. Cheap, and it catches a broken manifest before
any worktree exists.

### 3. Chunk

Slice the batch into chunks of ~20 notes, in the order `comm` produced (which is
sorted, so filename-dated exports process roughly chronologically). Keep the
explicit path list for each chunk — the subagent is given paths, never a glob.

### 4. Dispatch sequentially

For each chunk, in order:

- **Verify the tip.** `main` must still equal the expected tip. If it advanced,
  stop non-destructively: remove no worktree, leave integrated chunks standing,
  report that `main` moved.
- **Create the worktree.** `git worktree add --detach
  .claude/worktrees/notes-import-chunk-<i>` from the expected tip.
  `.claude/worktrees/` is gitignored, so the checkout never shows up as
  untracked noise in the main tree.
- **Dispatch** a fresh general-purpose subagent pointed at the worktree, told to
  follow the **Chunk procedure** below for its explicit note list. Include the
  run ID, the chunk index, and all three entries from *Known gotchas* verbatim,
  plus the absolute path of the main checkout (the subagent needs it to read
  `assets/` — gotcha #3). Wait for it to finish (success, error, or timeout).
- **Determine the outcome from the repository, not the reply.** The subagent's
  summary is informational; the commit is the source of truth. Check, in order:
  1. Is the worktree `HEAD` one commit ahead of the expected tip? If yes, that's
     the chunk commit.
  2. If not, **check the object store and `main` before concluding anything** —
     see *Known gotchas #1*. `git cat-file -t <sha the subagent reported>` and
     `git rev-parse main`. The commit frequently exists even when the worktree
     looks untouched.
  3. Only if the commit is in neither place did the chunk truly produce nothing.
- **A chunk commit exists** → validate it (see *Chunk commit validation*). On
  validation failure: do not integrate — stop, preserve the worktree, report. On
  success: re-verify `main` is at the expected tip, then
  `git merge --ff-only <chunk SHA>`. If `main` is *already* at that SHA (the
  gotcha-#1 case), that is the correct end state — nothing to merge. Advance the
  expected tip, remove the worktree, run `qmd update && qmd embed`; if that
  refresh fails after one retry, stop the run. If the re-verify shows `main`
  moved to something *else*, do not force `ff-only` and do not remove the
  worktree: stop non-destructively, preserving the commit for manual integration.
- **No chunk commit anywhere** → `git worktree remove --force` the worktree, stop
  and report. Those notes were never recorded in the manifest, so the next run
  re-picks them.

There is no separate finalize step — each chunk commit already carries
everything that chunk produced. The run ends when the last chunk integrates.

### 5. Report

Give the vault owner a short close-out: chunks integrated, notes processed,
disposition counts (`source` / `fold` / `skip`), remaining backlog, and a pointer
to the receipts in `raw/briefings/notes-import/`. Surface every *uncertain call*
the receipts flagged — that's their spot-check surface.

**Never push.** Landing the batch on a remote is the vault owner's call.

## Chunk procedure (subagent — fresh context window)

You are given a run ID, a chunk index, a list of ~20 note paths, a worktree to
work in, and the path of the main checkout. **Every *write* happens inside the
worktree.** The main checkout is read-only to you — the one thing you read from
it is `assets/` (step 1).

For each note:

1. **Read the note fully — including its embedded images.** Open every
   `![[image.jpg]]` / `![](Files/image.jpg)` reference **with vision**, don't
   just summarize the text around it. Slide photos, screenshots and whiteboard
   captures routinely carry the *bulk* of a note's content; a text-only pass on
   an image-heavy note captures maybe a fifth of it. Extract the image's content
   into the wiki page you write (`raw/` stays immutable).

   **`assets/` is gitignored, so the image binaries are absent from your
   worktree** — a detached `git worktree add` checks out tracked content only,
   and the template tracks nothing under `assets/` but `.gitkeep`. Resolve every
   `![[image.jpg]]` against the **main checkout's** `assets/` instead
   (`<main checkout>/assets/image.jpg`). Reading there is fine; the worktree
   restriction is about writes. See *Known gotchas #3* — without this the step
   above silently degrades into the text-only pass it exists to prevent.
2. **Coverage check.** `qmd query` (one `lex` + one `vec`) on the `wiki`
   collection for the note's key entities and topics, so you update existing
   pages instead of duplicating them. Dedupe against earlier notes in *this*
   chunk from your own working memory — those pages exist on disk but are not yet
   in the `qmd` index.
3. **Triage** to exactly one disposition:
   - **`skip`** — trivial or non-content: under ~200 characters with no
     substantive idea; a pure ephemeral todo with no insight; emoji-only, a
     single bare link, or empty; or an exact/near-exact duplicate of an
     already-ingested note. No wiki write.
   - **`fold`** — a fragment of a theme that already has a strong wiki page,
     where a standalone source page would be near-empty. Update that page; create
     no new source page.
   - **`source`** — substantial standalone content. Create a `wiki/sources/` page
     per the CLAUDE.md §Page Types `source` row (full YAML example:
     `docs/CLAUDE-MD-EXTENDED.md` §1), with full propagation to
     entity / topic / insight pages and the right glossary split file
     (`wiki/glossary/frameworks.md` for frameworks and acronyms,
     `wiki/glossary/vernacular.md` for in-house terms).
   - **Ambiguous** → default to `source` and flag it under *uncertain calls* in
     the receipt.

After all notes in the chunk:

4. **Bump every synthesis page you touched.** Any `wiki/insights/`,
   `wiki/topics/`, `wiki/plans/` or `wiki/projects/` page whose body you changed
   needs both a new top entry in its Recent-updates callout *and* a
   `date_updated` bump. The callout delta must be specific enough that the vault
   owner can decide whether to re-read — "Updated" fails the purpose even though
   it passes the format gate. Missing either one fails CI (`RU001` locally,
   `FM007` in CI).
5. Run `python3 .claude/scripts/regenerate-index.py`, then replace any
   `NEW - describe` placeholder it inserted with a real one-line description.
6. **Lint gate.** Run all three locally-runnable CI gates before committing. If a
   gate errors, fix it; if it can't be fixed cleanly, abort and say so — the
   orchestrator discards the worktree, and the notes get re-picked next run.
   1. **Layer 1 — `markdownlint-obsidian`.**

      ```bash
      mv .git .git.bak
      npx markdownlint-obsidian-cli@1.1.0 "wiki/**/*.md" --vault-root wiki
      mv .git.bak .git
      git status   # confirm the worktree is healthy again
      ```

      The `mv` dance is mandatory in a worktree — see *Known gotchas #2*. Restore
      `.git` even when the linter fails; never leave it moved. This gate catches
      nested-list indent (`MD007`), spaces after list markers (`MD030`), spaces
      after blockquote `>` (`MD027`), and frontmatter format (`OFM087` — tags must
      be strings, including bare years, so `tags: [work, "2019"]`). A recurring
      pitfall in this workflow: italic-wrapped nested lists inside blockquotes
      (`> *    - foo*`) are malformed markdown — write `> *- foo*` or
      `>   - *foo*` instead.

      **Runner.** `npx` ships with Node, which the vault already requires for
      `qmd`, so this needs nothing installed. CI runs the same pinned version
      through `bunx` and the output is identical. **Never add `--bun`** — it
      resolves the transitive `markdown-flavor-detection` dependency to a `bun`
      export condition that ships no source file, and the CLI dies with
      `Cannot find module 'markdown-flavor-detection/node'`.
   2. **Layer 2 — `wiki-lint.py`.** `python3 .claude/scripts/wiki-lint.py wiki/`.
      Catches table-pipe-in-wikilink, broken wikilinks and anchors, per-type
      frontmatter schema (`source` needs `raw_sources`, `plan`/`project` need
      `status`, `insight` needs `confidence`), unresolvable `raw_sources` paths,
      and Recent-updates discipline.
   3. **Index drift.** `python3 .claude/scripts/regenerate-index.py --check` must
      report no drift.

   `check-date-updated.py` (`FM007`) is CI-only — it needs git history you don't
   have in a detached worktree. Step 4 is what keeps it green.
7. **Record the cursor.** Append one row per note to the *Note ledger* table in
   `wiki/notes-import-manifest.md` (`| path | disposition | target | run ID |
   date |`, target empty for `skip`), and one row to the *Chunk log*. Update
   `notes_recorded` / `chunks_recorded` / `date_updated` in the frontmatter.
   Preserve the tables' column count and leading/trailing pipes.
8. **Write the digest receipt** to
   `raw/briefings/notes-import/<run-id>-chunk-<i>.md` — see *Digest receipt*
   below. Do **not** write `wiki/log.md`; the orchestrator's close-out covers the
   run, and concurrent chunk writes to the log are a merge-conflict factory.
9. **Commit — one atomic commit.** Stage **explicitly by path**: the chunk's
   new and modified wiki pages, `wiki/index.md` if `regenerate-index.py` changed
   it, `wiki/notes-import-manifest.md`, and the receipt file. Then
   `git commit -- <those paths>` with the message
   `wiki: batch ingest chunk <i> (<n> notes)`. Never `git add -A`.
10. **Return** a one-line status *including the commit SHA* to the orchestrator.
    The SHA is what makes gotcha #1 recoverable — without it the orchestrator has
    nothing to look up in the object store.

### Digest receipt

`raw/briefings/notes-import/<run-id>-chunk-<i>.md` records:

- **Per note** — path, disposition, target wiki page (for `source` / `fold`).
- **Counts** — pages created, pages updated.
- **Declared write-set** — the complete list of `wiki/` files this chunk created
  or modified, every propagation target included.
- **Uncertain calls** — notes where triage was ambiguous, a duplicate is
  suspected, or an entity match was low-confidence. This is the vault owner's
  spot-check surface; an empty section here on a 20-note chunk is a smell.
- **The chunk commit SHA.**

## Chunk commit validation (orchestrator, before `ff-only`)

Validate the chunk commit from its own contents — never from the subagent's
reply. Accept only if **all** of these hold. Any failure: do not integrate, stop,
preserve the worktree, report.

- **Parent** equals the run's expected tip.
- **Message** matches `wiki: batch ingest chunk <i> (<n> notes)`.
- **Path allowlist** — every path in the receipt's declared write-set is under
  `wiki/` and is not `wiki/log.md`; the only non-`wiki/` path the commit may
  touch is the receipt file.
- **No deletions or renames** — the diff adds and modifies only.
- **Manifest** — the diff adds exactly this chunk's N note rows to
  `wiki/notes-import-manifest.md` and no others, plus one chunk-log row.
- **Receipt present** — exactly one receipt file at the expected path, its note
  list and counts matching the manifest rows.
- **Exact write-set match** — the commit's changed paths equal exactly the
  declared write-set plus the manifest and the receipt. When the chunk changed
  the catalog, `wiki/index.md` is one of the files in the declared write-set.
- **Index consistency** — `regenerate-index.py --check` against the commit's tree
  reports no drift.
- **Target consistency** — every non-`skip` manifest row's target page appears in
  the declared write-set.

## Known gotchas

All three were learned the expensive way. Pass them verbatim into every chunk
subagent prompt.

### 1. The chunk commit can land on `main`, not on the worktree HEAD

**Symptom.** The chunk finishes, reports a SHA, and the worktree looks untouched:
`HEAD` still at the expected tip, ahead-count 0, clean tree. It looks exactly
like "the subagent did nothing".

**Reality.** The commit exists in the object store, and `main` has silently
advanced to it. The cause is gotcha #2's workaround: while `.git` is moved aside
and restored, git can resolve `HEAD` through the shared `main` ref instead of the
detached worktree HEAD, so the commit lands on the branch.

**Why it matters.** "No chunk commit → discard the worktree and stop", taken
literally against the worktree HEAD alone, throws away a complete, valid, already
integrated chunk and aborts the run.

**How to handle it.** Before concluding a chunk produced nothing:

```bash
git cat-file -t <sha the subagent reported>   # does the object exist?
git rev-parse main                            # did main already move to it?
```

If the commit exists, its parent is the expected tip, and it passes the normal
validation above, it is good. `main` already being at it *is* the correct end
state — there's nothing to merge. Advance the expected tip, clean up the
worktree, run `qmd update && qmd embed`, and carry on to the next chunk.

### 2. The markdownlint CLI chokes on a worktree's `.git` pointer file

**Symptom.** The Layer-1 gate fails inside the worktree with a stat/read error
around `.git`, on a tree that lints clean in the main checkout.

**Reality.** In a git worktree, `.git` is a *file* containing a gitdir pointer,
not a directory. The markdownlint CLI walks the tree and chokes trying to `stat`
`.git/**`.

**How to handle it.** Move it aside for the duration of the gate, then put it
back:

```bash
mv .git .git.bak
npx markdownlint-obsidian-cli@1.1.0 "wiki/**/*.md" --vault-root wiki
mv .git.bak .git
git status   # verify the worktree is healthy again
```

Restore `.git` even when the linter exits non-zero — leaving it moved breaks
every subsequent git command in the chunk. And restore it *before* staging or
committing, which is what keeps gotcha #1 from getting worse.

### 3. The worktree has no images — `assets/` is gitignored

**Symptom.** A chunk's `assets/` holds nothing but `.gitkeep`, so every
`![[image.jpg]]` in a note resolves to a missing file. The chunk doesn't error;
it just writes a thinner page and moves on.

**Reality.** The template's `.gitignore` has `assets/*` with `!assets/.gitkeep`,
so no image binary is tracked. `git worktree add` checks out tracked content
only. Every worktree therefore starts with an empty attachment folder, no matter
how many images the main checkout has.

**Why it matters.** Image reading is the highest-value step in the whole chunk
procedure — slide photos and whiteboard shots carry most of the content of an
image-heavy note. Silently losing it costs about four-fifths of those notes, and
nothing in the run reports a problem.

**How to handle it.** Resolve image references against the **main checkout**,
not the worktree:

```bash
ls "<main checkout>/assets/" | head    # the real attachments live here
```

Read `<main checkout>/assets/<file>` with vision. Reading outside the worktree is
allowed and expected; only *writes* are confined to the worktree. If the image
isn't in the main checkout either, say so in the receipt's *uncertain calls* —
don't quietly summarize the surrounding text as if it were the whole note.

## Rules

- **Focus areas are a priority, not a filter.** If the vault owner names themes
  for the run ("focus on the hiring notes", "pull out anything about
  onboarding"), treat those as themes to *guarantee* coverage of — not a
  narrowing of scope. Still run the full ingest on every note in the chunk, still
  give the named themes a strong home (their own topic or insight page if
  warranted), and still surface every other area each note touches. The wiki
  compounds; narrowing to the named themes strands the rest. Broaden by default;
  don't ask.
- **`raw/notes-import/` is immutable.** Read only. Never edit, move, rename, or
  delete a source note — not even to fix a typo or normalize a filename.
- **One fresh subagent per chunk.** Never reuse a subagent across chunks, never
  raise the chunk size to "save dispatches". Context freshness is the whole point.
- **Every write happens inside the worktree.** The main checkout is only ever
  read, merged into, and pruned.
- **The commit is the source of truth**, not the subagent's summary. Validate
  from the repository every time.
- **Sequential chunks only.** Each chunk's `ff-only` merge depends on the
  previous one having landed. Parallel chunks conflict on the manifest and the
  index on every single run.
- **Never `git add -A`.** Stage explicitly by path and commit with
  `git commit -- <paths>` — an unscoped stage sweeps up whatever else is in the
  tree.
- **Never push.** The orchestrator lands chunks on local `main` and stops there.
- **Stop non-destructively.** Whenever something is wrong, preserve the worktree
  and report. Discarding is only correct when there is provably no commit.

## Caps

| Item | Cap |
|---|---|
| Notes per run | 100 (default; vault owner may override) |
| Notes per chunk | ~20 |
| Chunks in flight | 1 (strictly sequential) |
| Wiki pages touched per note | ~5-15 (expected, not a limit) |
| `qmd update && qmd embed` retries per chunk | 1, then stop the run |
| Files outside `wiki/` per chunk commit | 1 (the receipt) |

## Common mistakes

- **Concluding "no commit" from the worktree HEAD alone.** Gotcha #1. Always
  check `git cat-file -t <sha>` and `git rev-parse main` first. This one discards
  finished work.
- **Running the Layer-1 linter without moving `.git` aside.** Gotcha #2. The gate
  fails, the chunk aborts, and 20 notes of good work get discarded for a tooling
  quirk.
- **Leaving `.git.bak` in place** after a linter failure. Every later git command
  in the chunk breaks, and the failure mode looks nothing like its cause.
- **Trusting the subagent's summary over the repository.** Summaries drift,
  overstate, and occasionally describe work that failed to write.
- **Skipping `qmd update && qmd embed` between chunks.** The next chunk's
  coverage check then can't see the previous chunk's pages, and you get duplicate
  entity and topic pages — the exact failure the coverage check exists to prevent.
- **Text-only reading of image-heavy notes.** Slide photos and whiteboard shots
  carry most of the content. Open them with vision — and remember the worktree's
  `assets/` is empty (gotcha #3), so read them from the main checkout. "The image
  wasn't there" is the most common way this step fails silently.
- **Ingesting the shipped `2020-01-01-sample-note.md` placeholder.** On a fresh
  clone it's the whole backlog. Ingesting it writes a source page for a book
  nobody read and burns it into the ledger permanently.
- **Treating the vault owner's focus areas as a filter.** Full ingest every time;
  focus areas just get guaranteed coverage.
- **Writing `wiki/log.md` from a chunk.** Guaranteed conflicts across chunks. The
  receipt plus the orchestrator's close-out is the record.
- **Forgetting the `date_updated` bump or the Recent-updates entry** on a touched
  synthesis page. Green locally, red in CI (`FM007`).
- **Vague Recent-updates deltas** — "Updated", "Minor edits". They pass the format
  gate and defeat the callout's entire purpose.
- **Placing the worktree under `wiki/` or `raw/`.** The linter and the index
  walker then see the chunk's tree twice and produce phantom drift. Use
  `.claude/worktrees/`, which the template already gitignores.
- **Raising the chunk size to finish faster.** Quality falls off a cliff past
  ~20-25 notes in one context, and the failure is silent: plausible-looking pages
  that duplicate or misattribute.
- **Pushing at the end of a run.** Never push from this skill.

## Iteration log

- **v1** — initial version. Orchestrator + chunk-subagent split, ~100 notes per
  run in ~20-note chunks, one disposable detached worktree per chunk, atomic
  chunk commits validated from the repository, durable manifest at
  `wiki/notes-import-manifest.md`, per-chunk digest receipts under
  `raw/briefings/notes-import/`.
- **v2** — added the `.git`-aside workaround for the Layer-1 lint gate after the
  markdownlint CLI was found to choke on a worktree's `.git` pointer file
  (*Known gotchas #2*). Baked into the chunk prompt so it isn't rediscovered each
  run.
- **v3** — added object-store and `main`-ref checks before concluding a chunk
  produced no commit, after the v2 workaround was found to let chunk commits land
  on `main` instead of the detached worktree HEAD (*Known gotchas #1*). Chunks
  now return their commit SHA so the orchestrator has something to look up.
- **v4** — added the explicit synthesis-page `date_updated` + Recent-updates bump
  step (CI's `FM007` is invisible to a local chunk run), path-scoped staging, and
  the "focus areas are a priority, not a filter" rule.
- **v5** — three fixes from a fresh-eyes review of the run in this repo.
  (a) *Known gotchas #3*: `assets/` is gitignored, so chunk worktrees start with
  no image binaries and the vision step was degrading to a text-only pass —
  images now resolve against the main checkout. (b) Worktrees moved to
  `.claude/worktrees/`, the convention the repo already gitignores, instead of a
  second scratch-dir convention outside the repo. (c) The shipped
  `2020-01-01-sample-note.md` placeholder is excluded from the backlog
  computation, so a first run can't ingest the demo stub and burn it into the
  ledger.
