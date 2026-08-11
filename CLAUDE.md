# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

# LLM Wiki — Your Second Brain

This file is the schema. **It must stay under 300 lines** — comfortably under, not sitting on the line, or the next convention you add has nowhere to go. When adding new conventions, compress or relocate older ones rather than appending. If a section grows past a paragraph or two, move the detail into a referenced doc (`docs/`, a skill, or a wiki page) and link from here. Material compressed out of this file lives in [`docs/CLAUDE-MD-EXTENDED.md`](docs/CLAUDE-MD-EXTENDED.md) — full YAML examples per page type, authoring-voice rules with worked examples, the skill design-spec convention, the briefing/digest/re-read distinction, and extended lint rationale.

**This is not a code repo.** It is an Obsidian vault committed to git. No app to build, no test suite. The "code" is the markdown corpus plus a toolchain for indexing (`qmd`) and linting (`markdownlint-obsidian` + `.claude/scripts/wiki-lint.py`). **There is no local npm project** — `qmd` (`@tobilu/qmd`) is a **global** install on the Node line pinned in `.nvmrc`; `markdownlint-obsidian` is fetched on demand by `npx` (nothing to install; CI runs the same version through `bunx`); every toolchain script is Python stdlib. If `qmd: command not found`, your shell is on the wrong Node — `nvm use`, then `npm i -g @tobilu/qmd` if still missing.

**Credits.** The "LLM wiki" idea is Andrej Karpathy's — a knowledge base **compiled and maintained by an LLM** rather than re-derived on every query. Retrieval is [`qmd`](https://github.com/tobi/qmd), a local markdown search engine by Tobi ("tobi/qmd"). First-run install: `SETUP.md`. Publishing a sanitized public copy of a private vault: `RELEASING.md`.

## Philosophy

The LLM writes and maintains the wiki. The vault owner curates sources, directs analysis, asks questions. The wiki is a persistent, compounding artifact — knowledge is compiled once and kept current, not re-derived per query.

## Architecture

```
your-wiki/
├── raw/                    # Layer 1: Immutable sources
│   ├── notes-import/       # Notes exported from your previous app (read-only)
│   ├── authored/           # Your OWN output — talks given, docs/posts published
│   ├── books/              # Book transcripts / summaries
│   ├── claude-chats/       # Extracted Claude Chat project wikis
│   ├── meetings/           # YYYY-MM-DD - Title.md
│   ├── captures/{daily,weekly}/
│   ├── briefings/          # Daily briefings, weekly digests, reading-queue.md
│   ├── projects/           # Project-specific working notes
│   ├── web-clippings/      # Articles + video notes (video-*.md)
│   ├── research/           # Multi-perspective research briefings (storm-research output)
│   └── bookmarks.md        # Rolling URL inbox (queue, not capture)
├── assets/                 # Flat attachments dir
├── wiki/                   # Layer 2: LLM-maintained knowledge base
│   ├── index.md            # Master catalog (read first)
│   ├── log.md              # Rolling chronological log; archives in log/YYYY-archive.md
│   ├── overview.md         # High-level synthesis of the vault owner's life
│   ├── glossary.md         # Thin landing page → split files
│   ├── glossary/{frameworks,vernacular}.md
│   ├── backlog.md          # Queue of deferred wiki work
│   ├── reflections-log.md  # First-person dated reflections (append-only)
│   ├── notes-import-manifest.md  # batch-ingest resume state
│   ├── entities/topics/sources/insights/plans/projects/
├── templates/              # capture / meeting / talk / daily-reading / video / storm-briefing
├── prompts/                # Reusable paste-into-LLM blocks
├── docs/                   # CLAUDE-MD-EXTENDED.md + visualisations/
├── .claude/{skills,scripts}/  # Skills + lint / index / coverage / privacy scripts
├── .github/workflows/      # wiki-lint on PR/push + opt-in briefings auto-merge
├── .obsidian/              # Obsidian vault config (attachment folder, plugin intent)
├── .obsidian-linter.jsonc  # Layer-1 lint config
├── .mcp.json               # Registers the qmd MCP server
├── .nvmrc                  # Node line for qmd and the lint CLI
├── setup.sh                # One-time bootstrap (qmd init + collections + index)
└── README.md, SETUP.md, RELEASING.md   # Intro · first-run install · sanitized-publish gate
```

## Layer Rules

### raw/ — Immutable Sources

**Never modify** files in `raw/`. They are the source of truth.

- **raw/notes-import/** — notes exported from your previous note-taking app. Image references converted to `![[wikilinks]]`.
- **raw/authored/** — your **own** output: talks you gave, docs you wrote, posts you published, long-form messages you sent. Every other `raw/` folder is *input*; this one is the record of what you put out, so the wiki can synthesize your trajectory as a practitioner and teacher rather than only your reading. Ships empty.
- **raw/claude-chats/** — extracted Claude Chat project wikis. Generate with `prompts/summarize-claude-chat.md`.
- **raw/web-clippings/** — articles, essays, and **video notes** (filename prefix `video-*`). Video is re-watchable, so capture-after-watching with timestamps. Template: `templates/video.md`.
- **raw/bookmarks.md** — rolling URL inbox. **Bookmark != capture.** A queue, not a wiki input; most entries decay. Never ingested directly; the weekly re-read picks 1-3 that still pull.
- **raw/briefings/**, **raw/research/** — skill outputs (daily-briefing, weekly-digest, storm-research). Written by tools, read by humans. Both ship empty; the first run of the relevant skill creates the files.

Ingest reads from raw, writes only to wiki.

### assets/, templates/, prompts/

`assets/` is a flat attachments directory (Obsidian's configured attachment folder) — reference with `![[filename.jpg]]`. `templates/` holds five thin **Templater** capture templates (`capture`, `meeting`, `talk`, `daily-reading`, `video`): the filename carries date/title, the body is pure structure, and `tp.file.move()` files each new note into the right `raw/` folder — so they are inert text until the Templater plugin is installed and pointed at `templates/` (`SETUP.md` step 2). It also holds `storm-briefing.{md,html}`, output scaffolds the `storm-research` skill fills in — not Templater scripts, never inserted by hand. `prompts/` holds paste-into-LLM blocks for workflows not yet promoted to skills — paste the block between the `---` dividers, and tune the file's iteration log over time.

### wiki/ — The Knowledge Base

The LLM owns this layer entirely. The vault owner reads and browses; the LLM writes. Every page has YAML frontmatter and uses `[[wikilinks]]` for cross-references.

**Glossary discipline:** when a new acronym or in-house term appears in a synthesis page, add a one-liner to the right split file in the same pass:

- Framework / methodology / acronym → `wiki/glossary/frameworks.md` (`[[glossary/frameworks#TERM]]`)
- Your domain's in-house term → `wiki/glossary/vernacular.md` (`[[glossary/vernacular#TERM]]`)
- **Never edit `wiki/glossary.md` directly** — it is a thin landing page pointing at the split files. If unsure of an expansion, write "(Expansion TBD — confirm with vault owner)" rather than guessing.

## Page Types

Every wiki page has frontmatter with at least `type:` + `title:`. Required keys by type (enforced by `wiki-lint.py` FM gates). Full YAML examples: `docs/CLAUDE-MD-EXTENDED.md` §1.

| Type | Folder | Required | Recommended |
|------|--------|----------|-------------|
| source | `wiki/sources/` | `title`, `raw_sources` | `date_ingested`, `date_original`, `tags` |
| entity | `wiki/entities/` | `title`, `entity_type` (person/organization/project/place) | `aliases`, `first_seen`, `source_count`, `tags` |
| topic | `wiki/topics/` | `title` | `source_count`, `tags` |
| insight | `wiki/insights/` | `title`, `confidence` (high/medium/low) | `derived_from`, `date_created`, `tags` |
| plan | `wiki/plans/` | `title`, `status` (active/completed/paused/abandoned) | `timeframe`, `date_created`, `date_updated`, `tags` |
| project | `wiki/projects/` | `title`, `status` (active/shipped/paused/sunset) | `stakeholders`, `date_started`, `date_updated`, `tags` |
| overview | `wiki/overview.md` | `type: overview` | `date_updated` |

**Project page body:** Vision & origin → Scope → Stakeholder positions (one sub-section each, with verbatim quotes) → Decisions log (chronological, `[YYYY-MM-DD] — who`) → Open questions → Action items → Related sources (raw wikilinks ok here) → Related wiki.

**Special pages** — `index`, `log`, `log-archive`, `glossary`, `backlog`, the notes-import manifest, and `reflections-log` (`wiki/reflections-log.md`, the append-only first-person layer) — carry a `type:` but no required-key schema and no Recent-updates callout. `reflections-log` entry format, append-only discipline, and its split from `insights/` are documented on the page itself.

## Recent-Updates Callout

Apply ONLY to `insights/`, `topics/`, `plans/`, `projects/`. Not to sources (frontmatter `date_ingested` is enough), entities (high-churn, tiny edits), or the special pages (overview / index / glossary / log / backlog / reflections-log). Place immediately after frontmatter, before the H1. Up to 3 entries, newest first; older roll off.

```markdown
> **Recent updates** (most recent first):
> - **2026-04-28** — specific one-line description of what changed
> - **2026-04-21** — older update
```

Every update to an in-scope page adds a top entry; the one-line delta must be specific enough that the vault owner can decide whether to re-read. On creation: `**YYYY-MM-DD** — Created.`

The delta line is the *quality bar* — it decides whether the page gets re-read or skipped. Good: *"Added section on retrieval-practice techniques with 3 worked examples"*. Bad: *"Updated"* · *"Minor edits"* · *"Refactor"* — these pass the format gate and fail the purpose.

## Naming Conventions

Lowercase, hyphens for spaces. Entities named after the entity (`my-manager.md`, `acme-corp.md`); sources descriptively (`team-offsite-nov-2023.md`); topics after the concept (`systems-thinking.md`); insights after the observation (`pattern-leadership-pipeline.md`); plans after the goal (`q2-2026-goals.md`); projects after the project (`design-system-refresh.md`).

## Retrieval: qmd (primary) + direct reads (secondary)

Indexed by the `qmd` MCP server (registered in `.mcp.json`, bootstrapped by `./setup.sh`). Use `qmd query` first; fall back to `Read`/`Glob`/`Grep`. If qmd returns nothing, the vault likely was never bootstrapped — point the owner at `SETUP.md` and use direct reads meanwhile.

**Collections:** `wiki` (synthesis) + 10 raw collections registered by `setup.sh` — `notes-import`, `authored`, `books`, `web-articles` (from `raw/web-clippings/`), `meetings`, `captures`, `briefings`, `claude-chats`, `projects` (from `raw/projects/`, not `wiki/projects/`), `research`. Only `raw/bookmarks.md` is deliberately excluded: it is a queue, not a corpus.

**Query pattern:** always pass `intent`; combine sub-queries — `lex` (BM25 keyword), `vec` (semantic), `hyde` (write-the-answer-then-search). Default: one `lex` + one `vec` per question, then `get`/`multi_get`. Scope with `collection` when known. Use `minScore: 0.5` to drop noise.

**Hierarchy:** `qmd query` → `qmd get`/`multi_get` (supports globs like `entities/*.md` and offsets like `file.md:100`) → `Read`/`Glob`/`Grep` → `wiki/index.md` as a map, not a discovery tool.

**Refresh after writes:** any workflow that writes or deletes files in an indexed folder must end with `qmd update && qmd embed`. Without `embed`, `lex` finds the new pages but `vec`/`hyde` silently miss them. `qmd status` sanity-checks counts.

## Project Skills (`.claude/skills/`)

Invoke by trigger phrase. **Don't hand-run a workflow that already has a skill** — invoke the skill so its discipline (logging, index refresh, committing) is preserved. Each skill's own `SKILL.md` frontmatter carries its authoritative triggers; one-line purposes for all eleven are in `docs/CLAUDE-MD-EXTENDED.md` §7.

- **Rhythms** — `daily-briefing` ("brief me"), `weekly-digest` ("what's new in the wiki"), `weekly-reread` ("weekly reread" / "weekly drill").
- **Getting things in** — `bookmark-process` ("process bookmark <N>"), `source-sync` ("sync <corpus>"), `batch-ingest` ("drain the import backlog"), `storm-research` ("STORM research on <X>").
- **Keeping it honest** — `auto-review` ("review before commit" / "did I fabricate anything"), `backlog` ("park this" / "sweep the backlog"), `tighten-prose` ("tighten this"), `design-principles` ("design review of <artifact>").

## Workflows

### Ingest

When the vault owner says "ingest [source]":

1. Read the raw source completely — **including embedded images** (`![[...]]`): slide photos, screenshots and whiteboards often carry the bulk of the content, so read them with vision rather than summarising the captions around them. Extract their text into the source page (raw stays immutable).
2. Discuss 3-5 key takeaways briefly.
3. `qmd query` (lex + vec) on `wiki` for the source's entities/topics/ideas — update existing pages, don't duplicate.
4. Create the source summary in `wiki/sources/`.
5. Update or create entity / topic / insight pages as needed.
6. Update `wiki/overview.md` if the big picture shifts.
7. Update the right glossary split file for new acronyms / in-house terms.
8. Add an entry to `wiki/reflections-log.md` if the source carries first-person interior content — your own reaction, a decision you made, a question you're now holding. Route it there rather than letting it dissolve into the source summary's neutral prose.
9. Append to `wiki/log.md` (rolling buffer — never write archives directly).
10. Run `python3 .claude/scripts/regenerate-index.py`, then `qmd update && qmd embed`.
11. Run the **auto-review** skill (fresh-context content review — catches fabrication, over-promotion and weak deltas the mechanical gates can't), then all CI gates locally before committing (see *Wiki Lint Pipeline*). If it can't be made clean, abort rather than land a half-state.

A single ingest may touch 5-15 wiki pages. That's expected.

### Batch Ingest

For many related notes at once (e.g. "ingest all Q1 meeting notes"):

1. Read all specified sources — **including embedded images**.
2. Run **one** `qmd query` on `wiki` for the cluster's core entities/topics, to anchor the batch against existing pages.
3. One source summary per source (group tightly-related ones if appropriate).
4. Batch-update entities, topics, insights.
5. Batch-update the glossary split files for any new terms surfaced across the batch.
6. One `wiki/reflections-log.md` pass across the batch — one entry per source that carries first-person interior content, not one per file.
7. **Single** log entry for the batch, not one per file.
8. Run `regenerate-index.py` + `qmd update && qmd embed` **once at the end**.
9. Run the **auto-review** skill, then all CI gates locally before committing.

### Query

`qmd query` on `wiki` with `intent` + `lex` + `vec` (add `books` / `web-articles` / `authored` if the question clearly reaches there) → `qmd get`/`multi_get` the top hits and follow wikilinks → synthesize with `[[wikilinks]]` back to source pages → if the answer is valuable, offer to file it as an insight or topic.

### Lint (semantic — "lint")

Use `qmd query` (especially `vec`) to find near-duplicates, contradictions, orphan pages, concepts that deserve their own page, and stale claims superseded by newer sources. Run a glossary-coverage pass over recently-modified synthesis pages and resolve lingering "(Expansion TBD)" entries. Suggest gaps worth new sources. If pages are created, merged or deleted, finish with `regenerate-index.py` + `qmd update && qmd embed`.

### Plan

Read `wiki/plans/` plus the relevant insights and topics, synthesize a plan page with concrete actions, and cross-reference it into existing wiki knowledge.

### Wiki Lint Pipeline (CI gates)

Gates run on every PR/push touching `wiki/`. Run them locally before committing. Extended rationale: `docs/CLAUDE-MD-EXTENDED.md` §5.

**Layer 1 — markdownlint-obsidian** (Obsidian-flavored + standard markdownlint; config `.obsidian-linter.jsonc`):

```
npx markdownlint-obsidian-cli@1.1.0 "wiki/**/*.md" --vault-root wiki
```

**Any output at all means failure.** The CLI exits `0` even while printing violations, and has no `--strict`/`--fail-on` flag — so `&&`-chaining it or trusting `$?` gives a false pass. CI works around this by parsing `--output-formatter json` and failing on any entry (`.github/workflows/wiki-lint.yml`); locally, read the output. Silence is the pass.

`npx` ships with Node, so this needs no extra install. CI runs the identical version through `bunx` and the two produce byte-identical output; use whichever runner you have. If you use `bunx`, do **not** add `--bun`: the transitive `markdown-flavor-detection` dependency ships no `src/`, so `--bun` resolves its `bun` export condition to an unpublished file and the run dies. Plain `bunx` is fine — verified on bun 1.3.14; the `--bun` flag is the whole problem, not the bun version.

Every file under `wiki/` is linted — there are no per-file carve-outs; `.obsidian-linter.jsonc` only ignores whole non-wiki trees (`raw/`, `assets/`, `templates/`, `prompts/`).

**Layer 2 — `.claude/scripts/wiki-lint.py` (stdlib-only).**

*Hard gates (error — these fail CI):*

- `WIKI001` table-pipe-in-wikilink — escape the inner `|` as `\|` inside table cells
- `WIKI002` broken-wikilink (Obsidian-fuzzy name resolution)
- `WIKI003` broken-wikilink-anchor — the `#anchor` must resolve to a real heading
- `FM001` missing frontmatter on a synthesis page
- `FM004` a registered page type is missing one of its required keys (see the Page Types table)
- `FM005` `raw_sources` paths must resolve on disk (catches typos and post-rename drift — silent provenance breaks, not cosmetics)
- `RU001` Recent-updates callout missing on an `insight`/`topic`/`plan`/`project` page
- `IO001` a file under `wiki/` could not be read or decoded (the file itself is broken, not its content)

*Soft gates (warning — reported, but the script still exits 0):* `FM002` missing `type:`; `FM003` unknown `type:` (no schema registered); `FM006` recommended keys; `RU002` callout has no dated entry; `RU003` newest callout entry is older than `date_updated`; `RU004` callout holds more than 3 entries (older roll off — callout-only trims don't need a `date_updated` bump); `PROV001` synthesis should cite `[[wiki/sources/...]]`, not `[[raw/...]]` (`projects/` exempt in its Related sources section); `WIKI007` anchor-prose source-count mismatch on topic pages. Warnings still deserve clearing — they're the ones that quietly rot retrieval — so treat a clean run as zero of both.

*Advisory (opt-in `--report <name>`):* `orphans`, `symmetry`, `cross-links` (`WIKI008`), `tags`, `glossary-coverage`, `schema`, `duplicates`.

```
python3 .claude/scripts/wiki-lint.py wiki/
python3 .claude/scripts/wiki-lint.py wiki/ --gh-annotations   # CI form
python3 .claude/scripts/wiki-lint.py --report orphans         # advisory
```

**Gate 2b — `FM007` (`check-date-updated.py`, CI-only, git-aware).** Fails if a synthesis page's *body* changed but `date_updated` wasn't bumped (scope: insights/topics/plans/projects). Needs git history, so it runs only in CI. The Recent-updates callout is stripped before comparison.

**Gate 3 — index drift:**

```
python3 .claude/scripts/regenerate-index.py --check
```

**The other scripts in `.claude/scripts/`** — none of them gate CI. `ingest-coverage.py` reports which `raw/` notes no `wiki/sources/` page claims via `raw_sources:` (the inverse of `FM005`; exits 0 even when notes are unmapped, `--fail-on-unmapped` opts into a non-zero exit). `leak-scan.py` is the release-time privacy gate — see `RELEASING.md`. `qmd-refresh-hook.sh` re-indexes after a `git pull`/rebase brings in remote notes; git hooks are machine-local, so install it once per clone (`SETUP.md`). `bump-markdownlint-obsidian.sh` pins/bumps the vendor lint CLI and surfaces follow-up steps.

### Index regeneration

`wiki/index.md`'s counts and section membership are mechanically reconciled — don't hand-maintain them. `regenerate-index.py` walks `wiki/{entities,topics,sources,insights,plans,projects}/**/*.md`, fixes counts and `total_pages`, appends new pages flagged `NEW - describe` (replace the placeholder by hand — the script can't write descriptions), drops orphan entries whose file was deleted, and preserves editorial descriptions plus the hand-curated `## Overview` and `## Raw Source Inventory` sections. `total_sources_ingested` / `total_raw_sources` are still by hand.

### Log rotation

`wiki/log.md` is the current-year rolling buffer (`type: log`). At ~250KB or at year-end, archive older entries to `wiki/log/YYYY-archive.md` (`type: log-archive`, `year:`, `date_range:`). Newest-first within each file, entries separated by `---`. Self-references inside an archive use the archive's own filename (`[[log/2026-archive#...]]`), since rotation moves the anchor target. `wiki/reflections-log.md` rotates on the same rhythm and the same rules, into `wiki/log/YYYY-reflections-archive.md`.

### Daily Briefing

"brief me" → invoke the `daily-briefing` skill. It writes `raw/briefings/YYYY-MM-DD.md` with today's delta versus yesterday's briefing, plus today's read pulled from `raw/briefings/reading-queue.md` (created and maintained by `weekly-digest`; absent until the first digest runs, and the briefing skill handles that). Forward-looking and today-only — distinct from `weekly-digest` (forward over the wiki, weekly) and `weekly-reread` (backward over raw notes, weekly). Vault-only by default; a calendar or tracker is an explicit optional extension point in the skill. See `docs/CLAUDE-MD-EXTENDED.md` §4.

If briefings are generated by a scheduled or cloud session that opens a PR per run, `.github/workflows/auto-merge-briefings.yml` can squash-merge exactly that class of PR (head branch under a configured prefix, every changed file under `raw/briefings/`). It ships **inert** — set the repo variable `ENABLE_BRIEFING_AUTOMERGE=true` to switch it on. Note that `raw/briefings/` is outside `wiki-lint.yml`'s path filter, so auto-merged does not imply linted.

## Provenance Principle (raw-link discipline)

The wiki is only as trustworthy as the trail back to its sources. Every claim is **one hop** from a raw note.

- **Source pages (`wiki/sources/`)** — MUST have `raw_sources:` frontmatter pointing at the raw file, AND at least one **body wikilink** back to it (`[[raw/...]]`, typically in the opening paragraph — frontmatter YAML isn't clickable in Obsidian). Inline-cite direct quotes with `[[raw/...]]` so the reader can open the receipt. If no resolvable raw file exists, reclassify the page as an insight.
- **Synthesis pages (entities/topics/insights/plans/projects)** — cite `[[wiki/sources/...]]`, not raw. Exception: a project page's *Related sources* section may link raw when no source page exists yet — but creating the source page is the preferred fix.
- **Why one hop, not zero:** raw-linking every synthesis claim turns pages into citation soup and breaks on raw rename. One hop via source pages stays auditable in a single click without polluting synthesis prose.

## Cross-Referencing Rules

Every entity or topic mentioned gets a `[[wikilink]]` if it has a page. Source pages link to the entities and topics they contain; entity pages link back to the source summaries where they appear. Use a `related` section at the bottom for lateral connections.

## Wiki Authoring Voice

Governs *how* synthesis prose is written. Worked examples: `docs/CLAUDE-MD-EXTENDED.md` §2.

- **Your own domain's vocabulary leads. Imported frameworks follow.** In a translation table, the left column is your language and the right is the imported term. Body prose introduces each concept in native form first. Never invent a new term when a domain-native one already exists.
- **Translation tables need a "why hold both registers" paragraph** — which audiences hear which register, and what each carries that the other undersells. Without it the table is decorative.
- **Tactical adds must be grounded in your actual context, not abstract.** Name the real team / tier, the timing anchor, and adapt generic prompts to your setting. A bullet that reads as a generic LinkedIn tip hasn't earned its place.
- **Retroactive "already done" closures cite specific provenance** — what was done, when, and at what scope (e.g. *"the 2026-04-18 table-pipe sweep, 68 wikilinks across 14 files"*), never just "confirmed already done."

## Tags Taxonomy

- **Domain:** `work`, `career`, `personal`, `family`, `tech`, `finance`
- **Activity:** `meeting`, `training`, `conference`, `project`
- **Role:** `leadership`, `management`, `craft`
- **Type:** `1-on-1`, `brainstorm`, `retrospective`, `goal-setting`
- **Time:** `"2026"`, `q1-2026` (only when temporal context matters). **Bare years must be quoted** — an unquoted `2026` parses as an integer and fails Layer 1 rule `OFM087`.

## Image Handling

All attachments live flat in `assets/`, which **`.gitignore` excludes** — they stay on your disk and never reach the repo. Raw notes may reference them as `![](Files/filename.jpg)` (legacy) or `![[filename.jpg]]`; wiki pages use `![[filename.jpg]]`, converting the path on the way in.

Because the files are absent from every clone, `wiki-lint.py` **skips** attachment links rather than resolving them (`ATTACHMENT_EXTENSIONS`) — otherwise every one of them would pass locally and fail in CI. Two consequences worth knowing: a mistyped attachment name is not caught by any gate, and if you **do** commit your attachments, set `"attachment_extensions": []` in `wiki-lint.config.json` to get the check back.

Read image files directly with vision when ingesting — slides, whiteboards and screenshots usually carry the substance — and write what they say into the page as prose. The link renders the image for a reader in Obsidian; the prose is what makes it retrievable.

## About the Vault Owner

_Who you are, what you do, the domains your notes span, and the people / organizations / projects that recur. The richer this is, the sharper the wiki's synthesis. **Replace the example below with your own profile.**_

**Example (replace this):** the vault owner is a product designer at a mid-size SaaS company, across four domains — **work** (design reviews, product specs, 1-on-1s, team rituals), **craft** (books, talks and articles on design and product thinking, plus the talks and posts they produce themselves, in `raw/authored/`), **personal growth** (habits, goals, reflections) and **side projects** (a note-taking app, open-source contributions). Recurring people: their manager, two close collaborators, a mentor. Recurring projects: the company's design-system refresh; a personal app.
