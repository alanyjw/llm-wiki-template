# LLM Wiki — A Second-Brain Template

A starter template for a **second brain that an LLM writes and maintains for
you**. You curate sources and ask questions; the LLM compiles and keeps a
knowledge base current. Knowledge is compiled once, not re-derived on every
query.

It is an [Obsidian](https://obsidian.md) vault committed to git — there is no
app to build. The "code" is a markdown corpus plus a small toolchain for
indexing and linting.

## Credits

Inspired by and built upon Andrej Karpathy's "LLM wiki" idea. Retrieval is
powered by [`qmd`](https://github.com/tobi/qmd), a local markdown search engine
by Tobi ("tobi/qmd").

## The idea: two layers

- **`raw/`** — immutable sources. Notes you import, books, articles, meeting
  minutes, talks you attended. Never edited. One folder, `raw/authored/`, holds
  your *own* output — talks you gave, docs and posts you published — so the wiki
  can synthesize your trajectory as a practitioner, not only your reading.
- **`wiki/`** — the LLM-maintained knowledge base. Entities, topics, sources,
  insights, plans, projects — all written and cross-linked by the LLM. Plus
  `wiki/reflections-log.md`, an append-only first-person layer for what actually
  struck you: the one thing a second brain can never reconstruct from sources.

The LLM ingests from `raw/`, synthesizes into `wiki/`, and keeps everything
cross-referenced. `CLAUDE.md` is the schema that tells the LLM exactly how — it
is kept under 300 lines on purpose; the longer-form reference lives in
[`docs/CLAUDE-MD-EXTENDED.md`](./docs/CLAUDE-MD-EXTENDED.md).

## Quickstart

**New to this / not a coder? Follow [`SETUP.md`](./SETUP.md)** — a step-by-step,
no-experience-assumed walkthrough.

The short version:

1. **Get the files:** use this template on GitHub, clone it, or download the ZIP
   and unzip it.
2. **Install prerequisites:**
   - [Obsidian](https://obsidian.md) — recommended for browsing the vault, plus
     its **Templater** plugin pointed at `templates/`, without which the capture
     templates are inert text (`SETUP.md` step 2).
   - Node.js (LTS, from [nodejs.org](https://nodejs.org)) — needed to run `qmd`,
     and its bundled `npx` is what fetches the Layer 1 lint CLI on demand.
   - [`qmd`](https://github.com/tobi/qmd) — the retrieval engine. Install
     globally: `npm install -g @tobilu/qmd`.
   - Python 3 — for the lint and index scripts (stdlib only, no install).

   Nothing else. The vendor lint CLI (`markdownlint-obsidian-cli`) is never
   installed — `npx markdownlint-obsidian-cli@1.1.0 …` fetches the pinned version
   each run. CI uses `bunx` for the same command; if you happen to have
   [Bun](https://bun.sh), it works locally too, but it is not a prerequisite.
3. **Run `./setup.sh`** — registers your notes folders with `qmd` and builds the
   search index. The `qmd` MCP server is pre-wired in `.mcp.json`, so Claude
   Code connects to it automatically when you open the folder.
4. **Make it yours:** open `CLAUDE.md` and rewrite the **"About the Vault
   Owner"** section with your own profile.
5. **Clear the examples:** the vault ships one example page per type and one
   sample raw note, each marked as a template stub. Delete them when ready.
6. **Start ingesting:** drop a source into `raw/`, then ask your LLM to
   "ingest" it. It will follow the workflows in `CLAUDE.md`.

## Toolchain

- **`setup.sh`** — one-time bootstrap: runs `qmd init`, registers every notes
  folder as a collection, and builds the index. Re-runnable.
- **`.mcp.json`** — registers the `qmd` MCP server so Claude Code wires up
  retrieval automatically on open.
- **`qmd`** — indexes the markdown corpus for keyword + semantic search.
- **`.nvmrc`** — Node LTS line (`22`) for `qmd` and for the `npx`-fetched lint CLI.
  `nvm use` if you use nvm; not required if you installed Node LTS from nodejs.org.

Every script in `.claude/scripts/` is Python 3 or POSIX `sh`, stdlib only:

- **`wiki-lint.py`** — vault-specific markdown lint: wikilinks and anchors,
  frontmatter schema per page type, provenance, recent-updates discipline. CI gate.
- **`regenerate-index.py`** — reconciles `wiki/index.md` counts and membership.
  `--check` is a CI gate for index drift.
- **`check-date-updated.py`** — CI-only `FM007` gate: a synthesis page whose body
  changed must bump `date_updated`. Needs git history, so it runs only in CI.
- **`ingest-coverage.py`** — reports which notes in `raw/` no `wiki/sources/` page
  claims via `raw_sources:`. A work queue, not a gate (`--fail-on-unmapped` opts in).
- **`leak-scan.py`** — release-time privacy gate: scans a tree's worktree, git
  history and structure for personal data. See [`RELEASING.md`](./RELEASING.md).
- **`qmd-refresh-hook.sh`** — re-indexes after a `git pull` or rebase brings in
  remote notes, so retrieval never answers from a stale index. Git hooks are
  machine-local, so **nothing installs this for you** — run the one-time snippet
  in `SETUP.md` once per clone.
- **`bump-markdownlint-obsidian.sh`** — pins/bumps the vendor lint CLI.

Two GitHub Actions workflows:

- **`wiki-lint.yml`** — runs every lint gate on each push and PR touching `wiki/`.
- **`auto-merge-briefings.yml`** — **opt-in, inert by default.** Squash-merges PRs
  from an automated session that touch nothing but `raw/briefings/`. Enable by
  setting the repository variable `ENABLE_BRIEFING_AUTOMERGE` to `true`; delete
  the file to disable it for good.

## Included skills

Eleven Claude Code skills, in `.claude/skills/`. Invoke by trigger phrase — each
one encapsulates a multi-step routine that would otherwise drift if hand-run.

**Rhythms**

- **`daily-briefing`** — "brief me". Today's delta-first, actionable briefing.
- **`weekly-digest`** — "what's new in the wiki". Wiki changes plus a budgeted read plan.
- **`weekly-reread`** — "weekly reread". Backward pass over the last 7 days of raw notes.

**Getting things in**

- **`bookmark-process`** — "process bookmark 3". Fetch, light-or-deep, write, strike, commit.
- **`source-sync`** — imports an external corpus into `raw/`, with dedup and drift detection.
- **`batch-ingest`** — drains `raw/notes-import/` via subagents in disposable worktrees.
- **`storm-research`** — scan → contradiction map → synthesis → peer review, to `raw/research/`.

**Keeping it honest**

- **`auto-review`** — fresh-context subagent review of a staged wiki diff before commit.
- **`backlog`** — capture and sweep the deferred-work queue in `wiki/backlog.md`.
- **`tighten-prose`** — voice-agnostic clarity pass on any prose.
- **`design-principles`** — mines sources into a catalog, then reviews artifacts against it.

## Publishing a sanitized copy

Publishing a scrubbed copy of a private vault — the way this template was
produced — is its own discipline: read [`RELEASING.md`](./RELEASING.md) first.
It covers the runnable privacy gate (`leak-scan.py`), how to write its denylist,
and why git history and commit authorship leak even after a squash.

## License

MIT — see [LICENSE](./LICENSE).
