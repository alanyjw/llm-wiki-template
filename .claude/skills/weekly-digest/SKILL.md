---
name: weekly-digest
description: Use when the user says "weekly digest", "digest the week", "what's new in the wiki", "wiki digest", or "weekly wiki". Compiles a one-screen forward-looking summary of wiki changes since the last digest — new sources/topics/insights/plans/projects, updated synthesis pages, surfaced follow-ups from log.md, a Read-First top-3 with deterministic scoring + user-confirmable swap, and a tiered Reading-plan checklist (Tier 1 deep / Tier 2 skim / Tier 3 on-demand) with per-page word-counts + minutes + suggested calendar blocks so the user can budget reading time. Sources: wiki/log.md headers + git log --since for wiki/ + wiki/index.md frontmatter + per-page Recent-Updates callouts + wc -w of every linked page. Writes raw/briefings/weekly-digest-YYYY-MM-DD.md. Forward prep ("what's new in the wiki this week, which pages should I read first, how much time should I block out") — distinct from /weekly-reread (backward raw-notes processing).
---

# Weekly Digest

Compose a one-screen summary of what's new and what's changed in `wiki/` since the last digest. Forward prep before reading. Self-paced; the user invokes when they want to catch up. Pairs with /weekly-reread (backward raw-notes processing).

## When to use

- The user says "weekly digest", "digest the week", "what's new in the wiki", "wiki digest", "weekly wiki"
- Sunday evening or Monday morning, before /weekly-reread
- **Skip / refresh** if a `weekly digest` entry exists in `wiki/log.md` dated within the last 6 days — offer to overwrite the file in place and append a "weekly digest (refresh)" log entry. Don't duplicate.

## Steps

### 1. Anchor the window

- `now` = current datetime (use the user's local timezone if known; fall back to UTC).
- `window_start` = date of the most recent `## [YYYY-MM-DD] weekly digest | …` header in `wiki/log.md`. **If none, fall back to `now - 7 days`.**
- `window_end` = `now` (date only).
- `digest_date` = `window_start` (used in the filename — the digest IS anchored on its window-start, not on Monday).

Echo the resolved window + filename back to the user before any other reads. (Catches date-math drift early.)

### 2. Parse `wiki/log.md` headers

Read `wiki/log.md`. Match headers with regex `^## \[(\d{4}-\d{2}-\d{2})\] ([^|]+) \| (.+)$`. Filter to entries where `date >= window_start`.

Group by op-type into four buckets:

| Bucket | Op-types |
|---|---|
| **New content** | `ingest`, `deep ingest`, `batch ingest`, `wiki-ingest`, `copy`, `bookmark` |
| **Synthesis** | `insight`, `topic promotion`, `plan revision pass`, `convention + backfill` |
| **Hygiene** | `lint`, `rename`, `replace`, `deep-pass + lint` |
| **Misc** | anything else |

For each entry, capture: date, op-type, short-title, and (lazily, only if needed for follow-ups) the bullet body between the `## [...]` header and the next `---` divider.

### 3. Cross-check with git log

Run:

```bash
git log --since="<window_start>" --name-status --pretty=format:"%h|%ad|%s" --date=short -- wiki/
```

Bucket touched files by directory:
- `wiki/sources/` (new vs. modified — `A` vs. `M` from `--name-status`)
- `wiki/insights/`
- `wiki/topics/`
- `wiki/entities/`
- `wiki/plans/`
- `wiki/projects/`

**Reconcile against step 2.** Any file change with no matching log entry → flag as `undocumented` and surface in the *Open questions* section. (Rare but worth catching.)

### 4. Read `wiki/index.md` frontmatter delta

Read `wiki/index.md` frontmatter. Capture current `total_pages`, `total_sources_ingested`, `total_raw_sources`.

**Compute deltas vs. last digest.** Look up the previous digest file (`raw/briefings/weekly-digest-*.md` sorted by date, second-newest if refresh path else newest-before-now); read its `baseline_total_pages` / `baseline_total_sources` from frontmatter. Render the deltas in the *Stats* line as `+N pages, +N sources`.

If no previous digest exists, omit the deltas (just render absolute counts).

### 5. Compute "Read first" top-3

Score every page touched in the window (set assembled from steps 2 + 3) by:

- **+2** per distinct log entry mentioning it (page name appears in the entry body, or page was added/modified in the commit that produced the entry)
- **+3** if the page was the *primary subject* of an op-type ∈ {`insight`, `topic promotion`, `plan revision pass`, `convention + backfill`} (synthesis weight)
- **+1** per cross-reference *into* it from another in-window page (cheap grep: `grep -l "<basename-no-ext>" wiki/**/*.md` filtered to the in-window touched set)
- **Tie-break**: H2 section count of the page (`grep -c "^## " <file>`)

Take top 3. Echo each with a one-line rationale (e.g. *"3 log mentions, synthesis op, +2 cross-refs"*).

**Ask the user**: *"Confirm these picks, or swap?"* — wait for answer before rendering. (One question, conversational, like /weekly-reread step 4.)

### 6. Compute the reading plan (tiered checklist with time estimates)

Assemble the **distinct set of all pages wikilinked in the digest body** (Read-First 3 + sources + insights + topics + plans + projects + updated-synthesis). Dedupe — a page that appears in multiple sections is counted once.

For each page, compute:

```bash
wc -w wiki/<path>.md
```

Bucket each page into one of three tiers:

| Tier | Definition | Reading speed |
|---|---|---|
| **Tier 1 — Must read deep** | Read-First 3 + any insight or plan tagged as a load-bearing growth-edge / keystone for the week. Cap at ~6 pages. | **200 wpm** (own dense synthesis, read with intent to act) |
| **Tier 2 — Skim for frameworks** | All source pages (books / articles / videos) in the digest. These are reference menus to mark sections in, not deep reads. | **300 wpm** (skim pace; you partly know the territory) |
| **Tier 3 — Reference, on-demand** | Remaining insights, topics, plans, projects, updated-synthesis pages. Already-drafted docs to re-read when the related work session comes up — not digest priorities. | **200 wpm** |

Compute per-page minutes: `ceil(words / wpm)`. Compute per-tier subtotals. Compute grand total in hours-and-minutes.

Compute the three suggested calendar blocks:
- **Minimum to stay current**: Tier 1 only.
- **Comprehensive**: Tier 1 + Tier 2.
- **Full coverage**: all three tiers.

Render as a checklist (see file template). No interactive question — the user can swap pages between tiers later if their sense disagrees, but the deterministic tiering is the default.

### 7. Render the digest

Write to `raw/briefings/weekly-digest-<digest_date>.md` using the template below. Inline-echo the same content to the user.

If the file already exists (refresh path) → overwrite in place.

### 8. Log + commit + push

Append to `wiki/log.md`:

```markdown
## [YYYY-MM-DD] weekly digest | window <window_start> → <window_end>, N new / N updated / top-3 picked

- **Window**: <start> → <end>
- **New pages**: N (sources X, insights Y, topics Z, plans W, projects V)
- **Updated synthesis pages**: N
- **Read-first picks**: [[<page1>]], [[<page2>]], [[<page3>]]
- **Follow-ups surfaced**: N
- **File**: [[raw/briefings/weekly-digest-<date>]]
```

If refresh path: title becomes `weekly digest (refresh)` and add a *Refresh reason* bullet (e.g. "new ingests landed since the original digest").

Stage only: `raw/briefings/weekly-digest-<date>.md` + `wiki/log.md`. Single commit `chore: weekly digest <date>` (or `chore: weekly digest <date> — refresh`). **Push immediately** to `origin/main`.

**No `qmd update` / `qmd embed`** — `raw/briefings/` is outside indexed collections.

## File template

```markdown
---
type: digest
subtype: weekly
window_start: YYYY-MM-DD
window_end: YYYY-MM-DD
date_drafted: YYYY-MM-DD
baseline_total_pages: <int>
baseline_total_sources: <int>
sources:
  - "wiki/log.md headers since <window_start>"
  - "git log --since=<window_start> -- wiki/"
  - "wiki/index.md frontmatter"
---

# Weekly Digest — <window_start> → <window_end>

**Stats**: +N pages · +N sources · M log entries · K updated synthesis pages

## Read first
1. [[<page>]] — <one-line why>
2. [[<page>]] — <one-line why>
3. [[<page>]] — <one-line why>

## What's new
- **Sources** (N): [[…]], [[…]], … *(cap 5; "+K more" if over)*
- **Topics** (N): …
- **Insights** (N): …
- **Plans** (N): …
- **Projects** (N): …

## What was updated *(synthesis pages only)*
- [[<page>]] — <delta from page's Recent-Updates callout, top entry>
- … *(cap 5)*

## Follow-ups surfaced from log
- <date> · <op-type> · <follow-up extracted from log entry's "Follow-ups" / "qmd status: pending" / "Backlog impact" bullets>
- … *(cap 5)*

## Open questions
- <undocumented file changes from step 3 reconcile, parse misses, or anything that flagged as odd>
- … *(cap 3)*

## Reading plan

**Total budget**: ~<TOTAL_WORDS> words across <N> unique linked pages → **~<H>h <M>m for full read-through**. Tiered to match leverage:

### Tier 1 — Must read deep (~<MIN> min @ 200 wpm)
*One-line framing: highest-leverage synthesis pages of the week + load-bearing growth-edge insight + the new keystone source if any.*
- [ ] [[<page>]] (<Nk> words, ~<min> min)
- … (cap ~6)

### Tier 2 — Skim for frameworks (~<MIN> min @ 300 wpm)
*Source pages — read as menus, mark sections to return to. Partly known territory.*
- [ ] [[<page>]] (<Nk>, ~<min> min)
- …

### Tier 3 — Reference, on-demand (~<MIN> min @ 200 wpm)
*Read only when the related work session comes up — already-drafted docs, not digest priorities.*
- [ ] [[<page>]] (<Nk>, ~<min> min)
- …

### Suggested calendar blocks
- **Minimum to stay current** (~<T1> min): Tier 1 only.
- **Comprehensive** (~<T1+T2> min): Tier 1 + Tier 2.
- **Full coverage** (~<T1+T2+T3> min): all three tiers; Tier 3 best paired with the work it serves.
```

## Rules

- **Read-only of `wiki/`.** The skill writes only to `raw/briefings/weekly-digest-*.md` and appends to `wiki/log.md`. Never edits a wiki page.
- **One-screen non-negotiable.** Hard caps below; if the week was busy, compress; never sprawl. "+K more" is the escape hatch.
- **Don't duplicate /weekly-reread.** That skill processes `raw/` notes. This one summarises `wiki/` changes. Zero overlap of scope.
- **Cite wikilinks** for every page reference. Enables Obsidian backlinks → discoverable from any digest.
- **No silent failures.** If `wiki/log.md` parse misses entries vs git log → render the discrepancy in *Open questions*, don't drop it.
- **Skip-or-refresh is binary.** Never produce two digests for overlapping windows.
- **Single commit + push at end.** Stage only the two specific files.
- **No `qmd update / embed`** — `raw/briefings/` not indexed.
- **Don't pick Read-First from memory.** Score deterministically from the in-window data; the user can swap if their sense disagrees.

## Caps (one-screen budget)

| Section | Max items |
|---|---|
| Read first | 3 (always exactly 3 unless window had < 3 changes total) |
| What's new — per category | 5 (then "+K more") |
| What was updated | 5 |
| Follow-ups surfaced | 5 |
| Open questions | 3 |
| Reading plan — Tier 1 | ~6 (Read-First 3 + 1-3 keystone insights/plans) |
| Reading plan — Tier 2 | all source pages in the digest body |
| Reading plan — Tier 3 | everything else linked, deduped |

If a section is empty, write `- (none)` rather than dropping the heading. The Reading plan section is **never empty** — every digest has linked pages.

## Common mistakes

- **Window from "last 7 days" instead of "since last digest entry".** The roll-back-to-last-log-entry approach is resilient to missed weeks; calendar-week math drifts.
- **Listing every touched file.** That's the git log; the digest *synthesises*. Cap and "+K more".
- **Picking Read-First from memory.** Score deterministically from in-window data; ask the user to swap if their sense disagrees.
- **Editing wiki pages from this skill.** Read-only of `wiki/`. The only writes are `raw/briefings/` and `wiki/log.md` append.
- **Confusing with /weekly-reread.** Re-read processes `raw/` notes (backward, raw inputs). Digest summarises `wiki/` changes (forward prep, synthesised outputs).
- **Forgetting the `baseline_*` fields in frontmatter.** Without them, next week's index-delta computation has no reference point.
- **Forgetting to push.** Push after the commit, not just commit.
- **Silently dropping "undocumented" file changes.** If git log shows a file change that wasn't logged, surface it in *Open questions* — that's a wiki-hygiene signal, not noise.
- **Estimating reading time without `wc -w`.** Don't guess. The wc-based per-page minutes are the only useful number — the user blocks calendar time against them.
- **One reading speed for everything.** Tier 1 (own dense synthesis, intent-to-act) and Tier 3 (already-drafted reference) are at 200 wpm; Tier 2 (sources, partly-known territory, skim) is at 300 wpm. Mixing them collapses the tiering's signal.
- **Putting everything into Tier 1 because "it all matters".** If everything is must-read, nothing is. Cap Tier 1 at ~6 and trust the on-demand reading of Tier 3.

## Iteration log

- **v1** — initial version. Window resolves from `wiki/log.md`'s last `weekly digest` header (resilient to missed weeks). Output to `raw/briefings/weekly-digest-*.md`. Read-First scoring is deterministic + user-confirmable. Single commit + push, no qmd embed.
- **v2** — added the **Reading plan** section as Step 6 + file template. Deterministic word-counts (`wc -w`) per linked page, three-tier bucketing (deep / skim / on-demand), tier-appropriate WPM (200 / 300 / 200), checkbox checklist with per-page minutes + per-tier subtotals + three suggested calendar blocks (minimum / comprehensive / full).
