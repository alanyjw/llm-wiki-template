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
  minutes. Never edited.
- **`wiki/`** — the LLM-maintained knowledge base. Entities, topics, sources,
  insights, plans, projects — all written and cross-linked by the LLM.

The LLM ingests from `raw/`, synthesizes into `wiki/`, and keeps everything
cross-referenced. `CLAUDE.md` is the schema that tells the LLM exactly how.

## Quickstart

**New to this / not a coder? Follow [`SETUP.md`](./SETUP.md)** — a step-by-step,
no-experience-assumed walkthrough.

The short version:

1. **Get the files:** use this template on GitHub, clone it, or download the ZIP
   and unzip it.
2. **Install prerequisites:**
   - [Obsidian](https://obsidian.md) — recommended for browsing the vault.
   - Node.js (LTS, from [nodejs.org](https://nodejs.org)) — needed to run `qmd`.
   - [`qmd`](https://github.com/tobi/qmd) — the retrieval engine. Install
     globally: `npm install -g @tobilu/qmd`.
   - Python 3 — for the lint and index scripts (stdlib only, no install).
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
- **`.claude/scripts/wiki-lint.py`** — vault-specific markdown lint (wikilinks, frontmatter schema, provenance, recent-updates discipline).
- **`.claude/scripts/check-date-updated.py`** — CI-only FM007 gate: a synthesis page whose body changed must bump `date_updated`.
- **`.claude/scripts/regenerate-index.py`** — reconciles `wiki/index.md`.
- **`.claude/scripts/bump-markdownlint-obsidian.sh`** — pins/bumps the vendor lint CLI.
- **`.github/workflows/wiki-lint.yml`** — CI that runs all lint gates on every push.
- **`.nvmrc`** — Node LTS line (`22`) for `qmd` / `bunx`. `nvm use` if you use nvm;
  not required if you installed Node LTS from nodejs.org.

## Included skills

Three Claude Code skills for recurring upkeep: `weekly-reread`,
`weekly-digest`, and `bookmark-process`. See `.claude/skills/`.

## License

MIT — see [LICENSE](./LICENSE).
