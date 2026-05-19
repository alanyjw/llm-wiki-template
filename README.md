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

1. **Use this template** on GitHub (or clone it) into your own repo.
2. **Install prerequisites:**
   - [Obsidian](https://obsidian.md) — recommended for browsing the vault.
   - Node.js — required to install and run `qmd`.
   - [`qmd`](https://github.com/tobi/qmd) — the retrieval engine, required for
     search. Install it globally: `npm install -g @tobilu/qmd`.
   - Python 3 — for the lint and index scripts (stdlib only, no install).
3. **Make it yours:** open `CLAUDE.md` and rewrite the **"About the Vault
   Owner"** section with your own profile.
4. **Clear the examples:** the vault ships one example page per type and one
   sample raw note, each marked as a template stub. Delete them when ready.
5. **Start ingesting:** drop a source into `raw/`, then ask your LLM to
   "ingest" it. It will follow the workflows in `CLAUDE.md`.

## Toolchain

- **`qmd`** — indexes the markdown corpus for keyword + semantic search.
- **`.claude/scripts/wiki-lint.py`** — vault-specific markdown lint.
- **`.claude/scripts/regenerate-index.py`** — reconciles `wiki/index.md`.
- **`.github/workflows/wiki-lint.yml`** — CI that runs the lint on every push.

## Included skills

Three Claude Code skills for recurring upkeep: `weekly-reread`,
`weekly-digest`, and `bookmark-process`. See `.claude/skills/`.

## License

MIT — see [LICENSE](./LICENSE).
