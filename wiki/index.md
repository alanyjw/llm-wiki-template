---
type: index
date_updated: 2026-07-29
total_pages: 7
total_sources_ingested: 1
total_raw_sources: 1
---

# Wiki Index

Master catalog of all wiki pages. The LLM reads this first when answering
queries.

## Overview
- [[overview|Overview]] — High-level synthesis of the vault owner's life and work.
- [[glossary|Glossary]] — landing page for the framework and vernacular term lists.
- [[backlog|Backlog]] — evergreen wiki-maintenance queue.

## Entities (1)
- [[entities/example-entity|Sam Carter]] — Example entity page (template stub).

## Topics (2)
- [[topics/example-topic|Spaced Repetition]] — Example topic page (template stub).
- [[topics/system-design-principles|System Design Principles]] — Catalog of transferable system-design principles; the lens behind the `design-principles` skill.

## Sources (1)
- [[sources/example-source|Notes on "Make It Stick"]] — Example source summary (template stub).

## Insights (1)
- [[insights/example-insight|Retrieval beats re-reading]] — Example insight page (template stub).

## Plans (1)
- [[plans/example-plan|Learn a New Language in 2026]] — Example plan page (template stub).

## Projects (1)
- [[projects/example-project|Personal Note-Taking App]] — Example project page (template stub).

## Raw Source Inventory

Layer-1 raw collections under `raw/`. Counts grow as you ingest:

- `raw/notes-import/` — notes exported from your previous note-taking app.
- `raw/authored/` — your own output: talks given, docs and posts published.
- `raw/books/` — book transcripts or summaries.
- `raw/web-clippings/` — articles, essays, and video notes.
- `raw/meetings/` — meeting minutes.
- `raw/captures/` — daily and weekly captures.
- `raw/briefings/` — daily briefings, weekly digests, and the rolling reading queue.
- `raw/claude-chats/` — extracted Claude Chat project wikis.
- `raw/projects/` — project-specific working notes.
- `raw/research/` — multi-perspective research briefings from `storm-research`.

Eleven `.gitkeep` files, one per folder (`captures/` splits into `daily/` and
`weekly/`). Hand-curated — `regenerate-index.py` preserves this section rather
than deriving it, so it goes stale the moment a folder is added. `RELEASING.md`
section 5 pairs re-checking it with `find raw -name .gitkeep | wc -l`.
