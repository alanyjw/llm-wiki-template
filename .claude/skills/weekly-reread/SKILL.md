---
name: weekly-reread
description: Use when the user says "weekly reread", "weekly drill", "let's do the re-read", "weekly review drill", or starts a weekly review session in this vault. Runs the weekly review drill over the past 7 days of raw notes — lists new entries, classifies tagged captures, surfaces 3-5 live fragments, asks case-contrast questions, and proposes promotions to wiki/. Backward-looking — distinct from forward-looking daily workflows.
---

# Weekly Re-Read

Run the weekly review drill over the past 7 days of raw notes. Target cadence: once a week, ~20 minutes. Surfaces what's alive, classifies tagged captures into proper files, and proposes wiki promotions.

## When to use

- The user says "weekly reread", "weekly drill", "let's do the re-read", "weekly review drill", "weekly review"
- Start of a weekly review session in this vault
- **Skip** if a re-read entry has already been logged in `wiki/log.md` for this ISO week — offer to extend rather than duplicate

## Steps

### 1. List

List all notes added to `raw/` in the past 7 days. Cover:
- `raw/meetings/`
- `raw/captures/daily/`
- `raw/web-clippings/`

**Skip** `raw/notes-import/` and `raw/books/` (immutable historical imports).

Use `find raw/ -type f -name '*.md' -newermt '7 days ago'` or equivalent. Group by folder.

### 2. Classify tagged captures

Scan `raw/captures/daily/*.md` from the past 7 days for inline classification tags — entries that look like `[meeting-alice]`, `[meeting-bob]`, or similar `[category-subject]` patterns.

For each tagged cluster of entries, **propose** a split into a proper:
- `raw/meetings/YYYY-MM-DD - Title.md`

**Wait for the user's confirmation** before creating files. Don't auto-create. Untagged captures stay in `raw/captures/`.

### 3. Surface fragments

Pick 3-5 fragments that look alive. Bias toward:
- Verbatim one-liners (especially the user's own phrasing)
- Surprising decisions or reversals
- Emotional responses in brackets (`[felt sharp]`, `[uneasy]`)
- Open threads / dangling questions
- Dangling `[[wikilinks]]` to pages that don't exist yet

If the week was sparse (0-2 raw notes), skip step 1 and ask the user what's been live in their head instead.
If the week was dense (10+ raw notes), narrow to the top 5 richest fragments — don't try to cover everything.

### 4. Case-contrast

For each fragment, ask the user ONE case-contrast question:

> "How is this like [wiki case A] but not like [wiki case B]?"

Pull cases from `wiki/sources/` or `wiki/insights/`. Use `qmd query` (lex + vec) on the `wiki` collection to find adjacent cases — don't pick from memory alone.

One question per fragment. Wait for the user's answer before moving to the next.

### 5. Promote

After the user answers, flag any fragment that should be promoted to:
- `wiki/sources/` (if it's a citable source summary)
- A new entity or topic page (if it's a recurring subject)
- An insight (if it's a synthesized pattern)

**Bias toward few.** One good insight beats three thin ones. Don't promote every fragment.

If the user approves promotions, follow the standard Ingest workflow (CLAUDE.md §Workflows.1) for each: create page, update index, update entities/topics, update glossary if new acronyms, append to `wiki/log.md`, run `qmd update && qmd embed`.

### 6. Log

Append a brief entry to `wiki/log.md`:

```
[YYYY-MM-DD] Weekly re-read — N fragments reviewed; split A into raw/meetings/X; promoted Z to wiki/insights/...
```

Match the entry's facts 1:1 to what was actually done in the session.

## Rules

- **Don't auto-create files in step 2.** Always propose-and-wait. Tag format is `[category-subject]` (e.g. `[meeting-alice]`, `[meeting-bob-1on1]`).
- **One case-contrast question at a time.** Don't bulk-ask all 5 — the conversation is the drill.
- **Bias toward few promotions.** Better to promote one fragment well than five thinly.
- **Don't ingest the bookmarks file.** `raw/bookmarks.md` is a queue, not a wiki input (CLAUDE.md §Layer Rules).
- **Skip immutable folders.** `raw/notes-import/` and `raw/books/` are historical — they don't appear in the past-7-days list.
- **Single commit at end.** If the session creates wiki pages or splits raw files, stage specific paths and commit with a `wiki:` or `raw:` prefix. Never push.

## Caps (avoid noise)

| Section | Max items |
|---|---|
| Step 1 (list) | all (it's the inventory) |
| Step 3 (fragments) | 5 |
| Step 4 (questions) | 1 per fragment, asked sequentially |
| Step 5 (promotions) | 2-3 max per session |

## Common mistakes

- **Auto-creating split files in step 2.** Always propose first; the user confirms each.
- **Bulk-asking all case-contrast questions at once.** The drill is conversational — one fragment, one question, one answer, then the next.
- **Promoting every interesting fragment.** Most fragments stay raw. Promote the ones that pass the case-contrast test cleanly.
- **Reading from `raw/notes-import/` or `raw/books/`.** Those are immutable historical sources, not "this week's notes".
- **Skipping the log entry.** Step 6 is non-optional — without it, the next re-read can't tell what's already been processed.

## Iteration log

- **v1** — initial version as `prompts/weekly-reread.md`.
- **v2** — added step 2 (classify tagged captures). Supports mobile-first capture strategy where mobile captures dump to daily notes with inline `[category-subject]` tags, then get split into proper `raw/meetings/` files during the re-read. Keeps capture friction zero on mobile.
- **v3** — promoted from `prompts/weekly-reread.md` to a project skill at `.claude/skills/weekly-reread/SKILL.md`. Adds trigger phrases, propose-don't-create discipline in step 2, caps, and "common mistakes" section.
