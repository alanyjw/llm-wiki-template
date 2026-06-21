# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# LLM Wiki — Your Second Brain

This file is the schema. It tells the LLM how the wiki is structured, what the conventions are, and what workflows to follow. The LLM and the vault owner co-evolve this over time.

**This is not a code repo in the conventional sense.** It is an Obsidian vault committed to git. There is no app to build or runtime to launch — the "code" is the markdown corpus plus a small toolchain for indexing (`qmd`) and linting (`markdownlint-obsidian` + `.claude/scripts/wiki-lint.py`). There is no `package.json`, build step, or test suite: `qmd` is installed globally via npm (`npm install -g @tobilu/qmd` — see the README) and the lint/index scripts are Python stdlib only.

## Credits

This system is inspired by and builds upon Andrej Karpathy's "LLM wiki" idea —
a knowledge base **compiled and maintained by an LLM** rather than re-derived on
every query. Retrieval is powered by [`qmd`](https://github.com/tobi/qmd), a
local markdown search engine by Tobi ("tobi/qmd"). See the README for setup.

## Philosophy

The LLM writes and maintains the wiki. The vault owner curates sources, directs analysis, and asks questions. The wiki is a persistent, compounding artifact — knowledge is compiled once and kept current, not re-derived on every query.

## Architecture

```
your-wiki/
├── raw/                    # Layer 1: Immutable sources
│   ├── notes-import/       # notes exported from your previous note-taking app (read-only)
│   ├── books/              # book transcripts or summaries you add
│   ├── claude-chats/       # Extracted wikis from Claude Chat projects
│   ├── meetings/           # Meeting minutes — YYYY-MM-DD - Title.md (one file per meeting)
│   ├── captures/           # Miscellaneous daily / weekly captures
│   │   ├── daily/          # YYYY-MM-DD - Daily.md (rolling)
│   │   └── weekly/         # Weekly Work Plan markdown drafts
│   ├── briefings/          # Compiled weekly digests / re-reads (output of /weekly-digest, /weekly-reread)
│   ├── projects/           # Project-specific working notes / ideation dumps
│   ├── web-clippings/      # Articles, long-form essays, and video notes (video-*.md) clipped/captured from the web
│   └── bookmarks.md        # Rolling inbox of saved URLs (X / YouTube / web) — queue, not capture
├── assets/                 # Images, videos, attachments (flat directory)
├── wiki/                   # Layer 2: LLM-maintained knowledge base
│   ├── index.md            # Master catalog — the LLM reads this first
│   ├── log.md              # Chronological record of operations — rolling buffer (current year, recent months)
│   ├── log/                 # Archived log entries by year (YYYY-archive.md); rotates when log.md grows beyond ~250KB
│   ├── overview.md         # High-level synthesis of the vault owner's life
│   ├── glossary.md         # Thin landing page → points at the two split files below
│   ├── glossary/            # Split source-of-truth files:
│   │   ├── frameworks.md   #   - framework / acronym / methodology terms — reference as [[glossary/frameworks#TERM]]
│   │   └── vernacular.md   #   - your domain's in-house terms / jargon — reference as [[glossary/vernacular#TERM]]
│   ├── backlog.md          # Persistent queue of deferred wiki work (synthesis to absorb later, stub pages, etc.)
│   ├── entities/           # People, organizations, projects, places
│   ├── topics/             # Concepts, themes, recurring subjects
│   ├── sources/            # One summary page per ingested raw source
│   ├── insights/           # Synthesized observations, patterns, analyses
│   ├── plans/              # Personal goals, action items, life planning
│   └── projects/           # Active multi-stakeholder projects
├── templates/              # Obsidian note templates (capture / meeting / video)
├── prompts/                # Reusable LLM prompts (paste-into-LLM blocks)
├── .claude/
│   ├── skills/             # Project skills (weekly-reread, weekly-digest, bookmark-process)
│   └── scripts/            # wiki-lint.py (Layer-2 lint) + regenerate-index.py (index reconciler) + util scripts
├── .github/workflows/      # CI: wiki-lint runs on PR/push to wiki/
├── .obsidian-linter.jsonc  # Layer-1 lint config (markdownlint-obsidian)
├── CLAUDE.md               # This file — the schema
└── .obsidian/              # Obsidian configuration
```

## Layer Rules

### raw/ — Immutable Sources
- **Never modify** files in `raw/`. They are the source of truth.
- **raw/notes-import/** — notes exported from your previous note-taking app (read-only). Image references converted to `![[wikilinks]]`.
- **raw/books/** — book transcripts or summaries you add.
- **raw/claude-chats/** — Extracted knowledge wikis from Claude Chat projects. Use the prompt at `prompts/summarize-claude-chat.md` to generate these.
- **raw/bookmarks.md** — rolling inbox of URLs saved via iOS Share Sheet (Twitter/X, YouTube, articles). **Bookmark ≠ capture.** This is a queue, not a wiki input. Most entries will decay; weekly re-read picks 1-3 that still pull and processes them into `raw/captures/daily/` (light) or `raw/web-clippings/` (deep). Don't ingest the bookmarks file itself into the wiki.
- **raw/web-clippings/** — articles, long-form essays, and **video notes** (filename prefix: `video-*`, e.g. `video-some-talk-title.md`). Videos are conceptually "articles in video form" so they share the folder. Template: `templates/video.md`. Video is re-watchable, so capture-after-watching with timestamps is the pattern.
- When ingesting, read from raw but write only to wiki.

### assets/ — Attachments
- All images, videos, and files live here (flat, no subdirectories).
- Obsidian is configured to use `assets/` as the attachment folder.
- Reference images in wiki pages using Obsidian wikilinks: `![[filename.jpg]]`

### templates/ — Note Templates
- Obsidian markdown templates for capture modes: `capture.md`, `meeting.md`, `video.md`.
- Used by the Templater plugin (or core Templates plugin).
- Thin by design — filename carries date/title/speaker; the body is pure structure.

### prompts/ — Reusable LLM Prompts
- One file per prompt. Paste-into-LLM blocks for ad-hoc workflows that haven't been promoted to skills.
- Recurring vault workflows (weekly re-read, etc.) live as project skills under `.claude/skills/` — invoke them by trigger phrase rather than paste.
- When invoking a prompt file, paste the block between the `---` dividers.
- Tune prompt files over time; each has an iteration log at the bottom.

### wiki/ — The Knowledge Base
- **The LLM owns this layer entirely.** It creates, updates, and maintains all pages.
- The vault owner reads and browses; the LLM writes.
- Every page must have YAML frontmatter (see Page Types below).
- Every page must use `[[wikilinks]]` for cross-references to other wiki pages.
- When a wiki page references a raw source, link it as: `[[raw/notes-import/Note Title]]`
- **Glossary maintenance (write-it-down discipline):** whenever a new acronym or in-house term is introduced in a plan / insight / source / topic page, add a one-liner entry to the appropriate split file in the same pass:
  - Framework / methodology / acronym terms → `wiki/glossary/frameworks.md`. Reference elsewhere as `[[glossary/frameworks#TERM]]`.
  - Your domain's in-house terms (roles, events, organization-specific language) → `wiki/glossary/vernacular.md`. Reference elsewhere as `[[glossary/vernacular#TERM]]`.
  - **Never edit `wiki/glossary.md` directly** for new entries — it's now a thin landing page that just points at the two split files. Source of truth is the split files.
  - If uncertain of an expansion, add the entry with "(Expansion TBD — confirm with vault owner)" so it's surfaced for resolution rather than silently skipped.
  - Obsidian renders `[[glossary/frameworks#TERM]]` (and `[[glossary/vernacular#TERM]]`) as inline hover-previews.

## Page Types

### Source Summary (`wiki/sources/`)
Filed after ingesting a raw note. One source page per ingested note (or batch of related notes).

```yaml
---
type: source
title: "Source title"
raw_sources:
  - "raw/notes-import/Original Note Name.md"
date_ingested: 2026-04-16
date_original: 2022-03-15  # from the note's frontmatter or content
tags: [work, leadership, meeting]
---
```

Body: Key takeaways, structured summary, notable quotes or data points.

### Entity Page (`wiki/entities/`)
A page about a person, organization, project, or place that appears across multiple sources.

```yaml
---
type: entity
entity_type: person | organization | project | place
title: "Entity Name"
aliases: ["Nick Name", "Abbreviation"]
first_seen: 2026-04-16
source_count: 5
tags: [work, leadership]
---
```

Body: Who/what this is, key facts, role, relationship to the vault owner, timeline of appearances, cross-references.

### Topic Page (`wiki/topics/`)
A concept, theme, or subject that spans multiple sources.

```yaml
---
type: topic
title: "Topic Name"
source_count: 12
tags: [craft, personal-growth]
---
```

Body: Definition/overview, key ideas, how this topic appears across sources, evolution over time, related topics.

### Insight Page (`wiki/insights/`)
A synthesized observation, pattern, or analysis that emerges from multiple sources.

```yaml
---
type: insight
title: "Insight Title"
derived_from:
  - "wiki/topics/some-topic.md"
  - "wiki/sources/some-source.md"
date_created: 2026-04-16
confidence: high | medium | low
tags: [pattern, life-planning]
---
```

Body: The insight itself, supporting evidence with links, implications, open questions.

### Plan Page (`wiki/plans/`)
Goals, action items, life planning documents.

```yaml
---
type: plan
title: "Plan Title"
status: active | completed | paused | abandoned
timeframe: "Q2 2026"
date_created: 2026-04-16
date_updated: 2026-04-16
tags: [goals, career]
---
```

Body: Objective, context, action items (with checkboxes), progress notes, related insights.

### Project Page (`wiki/projects/`)
An active multi-stakeholder project the vault owner is working on. Projects differ from plans (which are personal goals) and from entity pages (which describe *what a thing is*, not the live work around it). A project page is the living decision log for that project — it accumulates stakeholder positions, decisions, open questions, and action items across many meetings over months/years.

```yaml
---
type: project
title: "Project Name"
status: active | shipped | paused | sunset
stakeholders: ["Person A", "Person B", ...]   # wikilink-able entities
date_started: 2025-05-29
date_updated: 2026-04-24
tags: [work, project]
---
```

Body structure:
- **Vision & origin** — who's burden / why / when it started.
- **Scope** — current product surfaces / journeys / phases.
- **Stakeholder positions** — one sub-section per key stakeholder, capturing their distinctive voice (what they care about, verbatim quotes, recurring frames). Update in place as positions evolve.
- **Decisions log** — chronological, `[YYYY-MM-DD] Decision — who`. Newest at bottom.
- **Open questions** — unresolved items, each tagged with who raised it.
- **Action items** — checkbox-style, owner if known.
- **Related sources** — wikilinks to raw meeting notes (`raw/notes-import/...`, `raw/meetings/...`) in date order.
- **Related wiki** — entities / topics / insights that this project intersects.

### Overview (`wiki/overview.md`)
The top-level synthesis of the vault owner's life, updated as the wiki grows. Sections might include: Work, Personal Growth, Side Projects, Goals, Open Questions.

```yaml
---
type: overview
date_updated: 2026-04-16
---
```

## Per-Page "Recent Updates" Callout (synthesis pages only)

**Why.** The vault owner can't always tell what's new in a synthesis page they haven't seen for a while. The wiki/log is comprehensive but page-by-page resolution is poor. The callout solves this.

**Scope.** Apply ONLY to:
- `wiki/insights/*.md`
- `wiki/topics/*.md`
- `wiki/plans/*.md`
- `wiki/projects/*.md`

**Do NOT apply** to: `wiki/sources/*.md` (rarely updated; date_ingested in frontmatter is enough), `wiki/entities/*.md` (high-churn but mostly tiny edits), or any of the special pages (overview, index, glossary, log, backlog — they have their own change-tracking patterns).

**Format.** A markdown blockquote placed *immediately after the closing `---` of the frontmatter*, before the H1, with up to 3 entries (most recent first). When a 4th update lands, the oldest rolls off:

```markdown
---
type: insight
title: "..."
...
---

> **Recent updates** (most recent first):
> - **2026-04-28** — one-line description of what changed
> - **2026-04-21** — older update
> - **2026-04-17** — even older update

# Insight Title
```

**Discipline going forward.** Every time you update an in-scope page, add a new top entry to its callout (and prune the oldest if you're now past 3). The one-line delta should be specific enough that the vault owner, glancing at it, knows what to re-read or skip. Examples:
- Good: *"Added section on retrieval-practice techniques with 3 worked examples"*
- Bad: *"Updated"* / *"Minor edits"* / *"Refactor"*

**On creation** of a new in-scope page, the callout starts with a single line: `**YYYY-MM-DD** — Created.`

## Naming Conventions

- **File names**: Lowercase, hyphens for spaces. `leadership-training.md`, `my-manager.md`
- **Entity files**: Named after the entity. `company-name.md`, `scaling-up.md`
- **Source files**: Named descriptively. `team-offsite-nov-2023.md`, `design-review-q1.md`
- **Topic files**: Named after the concept. `systems-thinking.md`, `product-strategy.md`
- **Insight files**: Named after the observation. `pattern-leadership-pipeline.md`
- **Plan files**: Named after the goal. `q2-2026-goals.md`
- **Project files**: Named after the project. `design-system-refresh.md`

## Retrieval: qmd (primary) + direct reads (secondary)

The vault is indexed by the `qmd` MCP server. **Use `qmd query` first for discovery**, then fall back to `Read` / `Glob` / `Grep` for specific files once you know the target.

### Collections

Layer 2 (synthesis):
- **`wiki`** — the LLM-maintained knowledge base (entities, topics, sources, insights, plans, overview, index, log). Use this for almost every query about what the vault owner already knows.

Layer 1 (raw sources):
- **`notes-import`** — legacy notes exported from your previous note-taking app (read-only).
- **`books`** — full book transcripts in `raw/books/`.
- **`web-articles`** — articles / video notes from `raw/web-clippings/`.
- **`meetings`** — meeting minutes from `raw/meetings/`.
- **`captures`** — daily / weekly captures from `raw/captures/`.
- **`briefings`** — compiled weekly digests / re-reads from `raw/briefings/`.
- **`claude-chats`** — extracted Claude Chat wikis from `raw/claude-chats/`.
- **`projects`** — project-specific working notes from `raw/projects/` (not to be confused with `wiki/projects/`, which lives in the `wiki` collection).

All collections are queryable via `qmd query` with `collection: '<name>'` scoping. The only raw surface NOT in qmd is `raw/bookmarks.md` (a rolling inbox, intentionally excluded).

### How to query

Use the `qmd query` tool. It takes a list of sub-queries plus an `intent` string.

- Always pass an `intent` string describing what you're really looking for — it disambiguates and improves snippets.
- Combine sub-queries for better recall:
  - `type:'lex'` — BM25 keyword search (exact terms, entity names, tags)
  - `type:'vec'` — semantic vector search (meaning, theme, vibe)
  - `type:'hyde'` — write what the answer would look like, search for it
- Default pattern for a real question: one `lex` + one `vec` sub-query in a single `query` call, then `get` / `multi_get` for the hits that look promising.
- Scope with `collection` when you know which layer to hit (e.g. `collection: 'wiki'` for synthesis, `collection: 'books'` for a quote hunt).
- Use `minScore: 0.5` to drop low-confidence noise.

### Retrieval hierarchy

1. **`qmd query`** — find candidate pages across all collections. Scope with `collection: 'wiki'` for synthesis-only, or omit for full-corpus search.
2. **`qmd get` / `qmd multi_get`** — pull the full text of promising hits (supports globs like `entities/*.md` and line offsets like `file.md:100`).
3. **`Read` / `Glob` / `Grep`** — for `raw/bookmarks.md` (the only non-indexed raw surface), for exact-path reads, or when qmd misses.
4. **`wiki/index.md`** — use as a map when you want to see the shape of the wiki, not as the primary discovery tool.

### Keeping the index fresh

The MCP exposes read-only tools (`query`, `get`, `multi_get`, `status`). Re-indexing happens through the `qmd` CLI via Bash:

- `qmd update` — re-index collections (picks up new/changed/deleted files).
- `qmd embed` — (re)generate vector embeddings so `vec` and `hyde` queries see the new content.
- `qmd status` — sanity-check counts/health before and after.

Any workflow that **writes or deletes files in an indexed folder** (Ingest, Batch Ingest, Lint cleanup, new meeting / capture / briefing file) must end with `qmd update && qmd embed`. Without embed, `lex` queries find the new pages but `vec`/`hyde` queries won't.

## Project Skills (`.claude/skills/`)

Recurring vault workflows are implemented as project skills. Invoke by trigger phrase — they encapsulate multi-step routines that would otherwise drift if hand-run each time. The catalog is the source of truth; this list is a map.

- **weekly-reread** — "weekly reread" / "weekly drill". Backward re-read over the past 7 days of raw notes. Surfaces fragments and proposes promotions to `wiki/`.
- **weekly-digest** — "weekly digest" / "what's new in the wiki". Forward-looking summary of wiki changes since the last digest, with a tiered Read-First plan and per-page word counts. Writes to `raw/briefings/weekly-digest-YYYY-MM-DD.md`.
- **bookmark-process** — "process bookmark <N>". Per-item actuator for `raw/bookmarks.md` — fetches the URL, proposes light vs deep treatment, writes the output, strikes the checkbox, commits locally.

When in doubt about whether a routine has a skill, check `.claude/skills/`. Don't hand-run a workflow that already has a skill — invoke the skill so its discipline (logging, committing, index refresh) is preserved.

## Workflows

### 1. Ingest

When the vault owner says "ingest [source]" or drops a new note:

1. **Read** the raw source completely.
2. **Discuss** key takeaways with the vault owner (brief, 3-5 bullet points).
3. **Check for existing coverage** — run `qmd query` (lex + vec) on the `wiki` collection for the key entities, topics, and ideas in the source, so you update existing pages instead of creating duplicates.
4. **Create** a source summary page in `wiki/sources/`.
5. **Update** the index — add the new source page (or just run the index regenerator at step 12; see *Index regeneration* below).
6. **Update or create** entity pages for every person, org, or project mentioned.
7. **Update or create** topic pages for major themes.
8. **Update or create** insight pages if new patterns emerge.
9. **Update** `wiki/overview.md` if the source changes the big picture.
10. **Update the appropriate glossary split file** — `wiki/glossary/frameworks.md` for framework / acronym / methodology terms, `wiki/glossary/vernacular.md` for your domain's in-house terms. Never edit `wiki/glossary.md` directly (thin landing page). Flag uncertain expansions as "(Expansion TBD — confirm with vault owner)" rather than guessing.
11. **Append** to `wiki/log.md`. (Rolling buffer — see *Log rotation* below; never write to `wiki/log/YYYY-archive.md` directly.)
12. **Regenerate the index** — run `python3 .claude/scripts/regenerate-index.py` (see *Index regeneration* below), then `qmd update && qmd embed` so future queries see the new/changed pages.

A single ingest may touch 5-15 wiki pages. That's expected.

### Index regeneration

`wiki/index.md` is the master catalog. Its per-section counts and membership are mechanically reconciled — do not hand-maintain counts.

- **Tool**: `python3 .claude/scripts/regenerate-index.py` (rewrite) or `--check` (drift check, exit 1 on drift).
- **What it does**: walks `wiki/{entities,topics,sources,insights,plans,projects}/**/*.md`; fixes per-section counts and `total_pages`; appends pages missing from the index (flagged `NEW - describe`); drops orphan entries whose file was deleted; preserves editorial one-line descriptions, section order, and the hand-curated `## Overview` + `## Raw Source Inventory` sections verbatim.
- **After running**: if any entry is flagged `NEW - describe`, replace that placeholder with a real one-line description (the script can't write descriptions — frontmatter has no description field).
- **`total_sources_ingested` / `total_raw_sources`** in the index frontmatter are NOT derived — keep updating those by hand.
- **CI**: `regenerate-index.py --check` gates the build via `.github/workflows/wiki-lint.yml`. A wiki commit that leaves the index drifted will fail CI.

### Log rotation

`wiki/log.md` is the rolling buffer for the **current year's recent entries**. When it grows beyond ~250KB (or at year-end), older entries are archived per year to `wiki/log/YYYY-archive.md`. The active log keeps a pointer to the archive in its intro callout.

- **Active log frontmatter**: `type: log`
- **Archive frontmatter**: `type: log-archive` + `year: YYYY` + `date_range: YYYY-MM-DD → YYYY-MM-DD`
- **Ordering**: newest-first within each file, separated by `---`
- **Rotation script**: ad-hoc Python; cutoff date is per-rotation.
- **Self-references in archives** must use the archive's own filename (`[[log/2026-archive#...]]`), not `[[log#...]]`, since rotation moves the anchor target.

### 2. Batch Ingest

For processing many related notes at once (e.g., "ingest all meeting notes from Q1"):

1. Read all specified sources.
2. Run one `qmd query` on the `wiki` collection for the cluster's core entities/topics to anchor the batch against existing pages.
3. Create one source summary per source (or group tightly related ones).
4. Batch-update entities, topics, and insights.
5. Batch-update the glossary split files (`wiki/glossary/frameworks.md` and/or `wiki/glossary/vernacular.md`) with any new acronyms / in-house terms surfaced across the batch.
6. Single log entry for the batch.
7. Run `python3 .claude/scripts/regenerate-index.py` once at the end of the batch, then `qmd update && qmd embed` (not per file).

### 3. Query

When the vault owner asks a question:

1. **`qmd query`** on the `wiki` collection first with an `intent` and a `lex` + `vec` pair derived from the question. Add `books` or `web-articles` if the question clearly reaches into those.
2. **`qmd get` / `qmd multi_get`** the top hits (and follow wikilinks) to load full context. Only fall back to `Read` / `Glob` when qmd misses or the target is outside indexed collections.
3. **Synthesize** an answer with `[[wikilinks]]` to sources.
4. **If the answer is valuable**, offer to file it as an insight or topic page.

### 4. Lint

When the vault owner says "lint" or periodically:

- Use `qmd query` (`vec` especially) to surface near-duplicate pages and concepts that drifted into multiple files.
- Look for contradictions between pages.
- Find orphan pages (no inbound links) — combine `Grep` for `[[page-name]]` references with `qmd query` to spot pages that no one semantically points at either.
- Find concepts mentioned but lacking their own page (`qmd query` with `lex` hits scattered across sources with no entity/topic page).
- Check for stale claims superseded by newer sources.
- **Glossary coverage pass**: scan recently-modified plans / insights / sources / topics for acronyms and in-house terms that lack an entry in either glossary split file (`wiki/glossary/frameworks.md` or `wiki/glossary/vernacular.md`). Add missing one-liners to the right split file. Resolve any lingering "(Expansion TBD — confirm with vault owner)" entries if the vault owner has since clarified them.
- Suggest new questions to investigate.
- Suggest sources that might fill knowledge gaps.
- If the lint pass creates, merges, or deletes pages, finish with `python3 .claude/scripts/regenerate-index.py` (reconcile the catalog) then `qmd update && qmd embed` (refresh retrieval).

### 5. Plan

When the vault owner asks to plan or reflect on goals:

1. Read existing plans in `wiki/plans/`.
2. Read relevant insights and topic pages.
3. Synthesize a plan page with concrete actions.
4. Cross-reference with existing wiki knowledge.

### 6. Wiki Lint Pipeline

The wiki has a two-layer markdown lint that gates CI on every PR/push touching `wiki/`. Run both locally before committing wiki changes.

**Layer 1 — `markdownlint-obsidian` (vendor).** Catches Obsidian-flavored markdown rules (frontmatter / tags / callouts / embeds) plus standard markdownlint. Config is `.obsidian-linter.jsonc`. Run:

```
bunx --bun markdownlint-obsidian-cli@1.1.0 "wiki/**/*.md" --vault-root wiki
```

**Layer 2 — `.claude/scripts/wiki-lint.py` (vault-specific, stdlib-only).** Checks the vendor tool can't do correctly today.

*Hard gates (errors — fail CI):*
- `WIKI001` table-pipe-in-wikilink — `[[X|Y]]` inside a table cell breaks the table; the inner `|` must be `\|` escaped.
- `WIKI002` broken-wikilink — Obsidian-fuzzy resolution that handles this vault's mixed `[[sources/foo]]` (wiki-implicit) and `[[raw/notes-import/foo]]` (vault-absolute) link conventions.
- `WIKI003` broken-wikilink-anchor — the `#anchor` of a wikilink must resolve to a real heading or glossary term in the target.
- `FM001`–`FM004` per-type required frontmatter — `source` requires `raw_sources`; `plan`/`project` require `status`; `insight` requires `confidence`; etc. (see Page Types).
- `FM005` raw_sources paths must resolve — every path in a source page's `raw_sources:` must point to a file that exists on disk (catches typos and post-rename drift).
- `RU001`–`RU003` Recent-updates callout discipline — in-scope synthesis pages (insights/topics/plans/projects) must carry the callout immediately after frontmatter, with at least one dated entry whose date is ≥ `date_updated`.

*Soft gates (warnings — don't fail CI):*
- `FM006` recommended frontmatter keys (`date_ingested`, `source_count`, …).
- `RU004` Recent-updates callout holds more than 3 entries (older ones should roll off — history lives in `wiki/log.md` + git).
- `PROV001` direct `[[raw/...]]` link inside a synthesis page (the one-hop provenance rule; `projects/` is exempt for its "Related sources" section).
- `WIKI007` anchor-prose source-count mismatch on topic pages that use the "<N> sources anchor this page" convention.

*Advisory (opt-in, never gates — `--report <name>`):* `orphans`, `symmetry`, `cross-links`, `tags`, `glossary-coverage`, `schema`, `duplicates`.

```
python3 .claude/scripts/wiki-lint.py wiki/
python3 .claude/scripts/wiki-lint.py wiki/ --gh-annotations   # CI form
python3 .claude/scripts/wiki-lint.py --check table-pipe wiki/ # single rule
python3 .claude/scripts/wiki-lint.py --report orphans         # advisory
```

**Gate 2b — `check-date-updated.py` (FM007, CI-only, git-aware).** Fails if a synthesis page's *body* changed in a commit/PR but `date_updated` was not bumped (scope: insights/topics/plans/projects). It needs git history, so it only runs in CI — it diffs against the PR base or the previous push. The Recent-updates callout is stripped before comparison, so a callout-only trim doesn't force a `date_updated` bump.

**CI** (`.github/workflows/wiki-lint.yml`) runs on push to `main` and on PRs whenever `wiki/**`, `.obsidian-linter.jsonc`, or any of the three scripts change. Four gates: Layer 1 (markdownlint-obsidian), Layer 2 (`wiki-lint.py`), Gate 2b (`check-date-updated.py`, FM007), and the index drift check (`regenerate-index.py --check`). Any new error — or a drifted `wiki/index.md` — fails CI.

**Carve-outs.** `backlog.md`, `glossary.md`, and `log.md` are ignored by Layer 1 due to a vendor `OFM901` auto-fix bug (see comment in `.obsidian-linter.jsonc`).

**Toolchain maintenance.** `.claude/scripts/bump-markdownlint-obsidian.sh` pins/bumps the vendor CLI version and surfaces follow-up steps. Node is pinned in `.nvmrc`; run `nvm use` before `qmd`/`bunx` work if your shell is on the wrong version.

## Cross-Referencing Rules

- Every entity mentioned in a page should be a `[[wikilink]]` if it has a page.
- Every topic discussed should link to its topic page.
- Source summaries should link to the entities and topics they contain.
- Entity pages should link back to source summaries where they appear.
- Use the `related` section at the bottom of pages for lateral connections.

### Provenance Principle (raw-link discipline)

The wiki is only as trustworthy as the trail back to its sources. Every claim should be **one hop** from a raw note.

- **Source pages (`wiki/sources/`) — MANDATORY raw-links.**
  - Every source page MUST have at least one entry in `raw_sources:` frontmatter pointing at the originating raw file (e.g. `raw/notes-import/Original Note.md`, `raw/meetings/2026-04-22 - Sync.md`).
  - For direct quotes or specific claims in the body, inline-cite with `[[raw/.../Note Title]]` so the reader can open the receipt.
  - If a source page has no resolvable raw file (e.g. synthesis-of-many notes that should be an insight, not a source), reclassify it.
- **Synthesis pages (`wiki/entities/`, `wiki/topics/`, `wiki/insights/`, `wiki/plans/`, `wiki/projects/`) — link to wiki source pages, not raw.**
  - These pages should cite `[[wiki/sources/...]]` (or its short form), which then carries the raw-link. This keeps synthesis pages readable and decouples them from raw-folder reorganization.
  - Exception: project pages have a "Related sources" section that may link directly to raw meeting notes when no source page exists yet — but creating the source page is the preferred fix.
- **Why one hop, not zero:** raw-linking every synthesis claim turns pages into citation soup and breaks on raw rename. Raw-linking only at the source-page layer means provenance is auditable in one click without polluting synthesis prose.
- **Lint trigger:** any source page missing `raw_sources:` is a defect — fix or reclassify.

## Wiki Authoring Voice

Three rules that govern *how* synthesis pages are written, on top of the structural rules above. Apply to ingests, plan / insight / project updates, and any pass that produces new wiki prose.

- **Your native vocabulary leads. Imported terms follow.** When a synthesis page contrasts your existing domain vocabulary with imported framework vocabulary (Rabois, Maxwell, Heifetz, Christensen, etc.), the translation table's **left column is your language; the right column is the imported term.** Body prose introduces concepts in your native form first, then names the imported register. Reason: your primary working context is the native register; the imported vocabulary is the second register, not the first. Never invent a new term when a domain-native one already exists.
- **Translation tables need a "why hold both registers" paragraph.** A bare two-column table tells the reader the words map but doesn't say when to use which. Add a one-paragraph framing alongside any such table: *which audiences hear which register, and what each register carries that the other undersells.* Without it the table is decorative.
- **Tactical adds must be grounded in your actual context, not abstract.** When importing a tactical practice (hiring protocol, review cadence, interview question, etc.), name the actual surface it applies to: team / tier, timing anchor, and an adaptation of generic prompts to your context. A bullet that reads as a generic LinkedIn tip has not earned its place in the wiki.
- **Retroactive "already done" closures cite specific provenance.** If a backlog item or open question is being closed because the work was already completed earlier, the log entry / closure note must name *what* was done, *when*, and *its scope* — not just *"confirmed already done."* A future reader (or a future Claude run) needs the receipt to trust the closure.

## Tags Taxonomy

Use these tag categories consistently:

- **Domain**: `work`, `career`, `personal`, `family`, `tech`, `finance`
- **Activity**: `meeting`, `training`, `conference`, `project`
- **Role**: `leadership`, `management`, `craft`
- **Type**: `1-on-1`, `brainstorm`, `retrospective`, `goal-setting`
- **Time**: `"2026"`, `q1-2026`, etc. (only when temporal context matters). **A bare year must be quoted** in the `tags:` array (`tags: [work, "2026"]`) — YAML parses an unquoted `2026` as an integer, which fails Layer 1 lint rule `OFM087` (frontmatter tags must be strings).

## Image Handling

- Raw notes reference images as `![](Files/filename.jpg)` — legacy format.
- Wiki pages reference images as `![[filename.jpg]]` — Obsidian native.
- All images live in `assets/` (flat directory).
- When creating wiki pages that reference images from raw sources, convert the path.
- The LLM can read image files directly for additional context.

## About the Vault Owner

_This section gives the LLM the context it needs to synthesize well: who you
are, what you do, the domains your notes span, and the people / organizations /
projects that recur. The richer this is, the sharper the wiki's synthesis.
**Replace the example below with your own profile.**_

**Example (replace this):**

The vault owner is a product designer at a mid-size SaaS company. Their notes
span four domains:

- **Work** — design reviews, product specs, 1-on-1s, team rituals.
- **Craft** — books, talks, and articles on design and product thinking.
- **Personal growth** — habits, goals, reflections.
- **Side projects** — a personal note-taking app, open-source contributions.

Recurring people: their manager, two close collaborators, a mentor. Recurring
projects: the company's design-system refresh; a personal app.
