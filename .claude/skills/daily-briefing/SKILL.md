---
name: daily-briefing
description: Use when the vault owner says "brief me", "daily briefing", "what's today", "what's on", "morning briefing", or starts a working day in this vault and needs an actionable to-do list. Compiles a delta briefing — this week's top priorities from the newest weekly plan, next-actions from active wiki/plans/ and wiki/projects/ that are NEW or CHANGED since yesterday's briefing (Monday runs a full sweep), carryovers from yesterday, and today's read from the rolling reading queue. Writes to raw/briefings/YYYY-MM-DD.md and echoes it inline. Vault-only by default; an optional extension point wires in a calendar or task source if you have one. Forward-looking (today only) — distinct from /weekly-reread (backward-looking raw notes) and /weekly-digest (week-scoped wiki changes).
---

# Daily Briefing

Compose the vault owner's actionable view of today, write it to `raw/briefings/YYYY-MM-DD.md`, and echo it inline. One pass per morning. Re-runs overwrite in place.

**Design intent: the briefing is a delta, not an inventory.** Tue-Sun briefings surface only what is *new or changed* since yesterday's briefing; Monday runs the full sweep. A briefing that re-lists the same ten open action items every day trains the reader to skim past it — the target is **20 lines or fewer below the H1**, readable in under two minutes.

Everything the skill needs lives in the vault. No external service is required.

## When to use

- The vault owner says "brief me", "daily briefing", "what's today", "what's on", "morning briefing"
- Start of a working day in the vault
- **Skip** if today's briefing file already exists — offer to *refresh* (overwrite in place) rather than write a duplicate

## Sources (read in this order, skip gracefully on failure)

1. **Yesterday's briefing** — `raw/briefings/YYYY-MM-DD.md` for yesterday's date, or the most recent briefing file if yesterday's is missing. **Read this first**: it is the delta baseline for steps 3 and 4, and it also tells you the date to diff against. Record that date as `baseline_date`.

2. **This week's plan** — the newest file in `raw/captures/weekly/` (sort by the date in the filename). Extract whatever that file designates as this week's priorities — typically a *Priority* / *Goals this week* column in a table, or the top items of a list. If the newest weekly plan does not cover today's week, mark it `(stale — week of YYYY-MM-DD)` and use it anyway. If `raw/captures/weekly/` is empty, fall back to active `wiki/plans/` pages whose `timeframe` frontmatter covers today, and take their top unchecked action items.

3. **Active plans and projects** — `Glob` `wiki/plans/*.md` and `wiki/projects/*.md`, keep those with `status: active`, and collect unchecked `- [ ]` action items whose owner is the vault owner or unspecified.

   Then apply the **delta filter** (Tue-Sun) — keep an item only if it is:
   - **(a) new** — absent from yesterday's briefing, or
   - **(b) changed** — present in yesterday's briefing but reworded or rescoped, or
   - **(c) due** — hard-dated today or inside this week.

   A cheap first pass for (a): `find wiki/plans wiki/projects -name '*.md' -newermt '<baseline_date>'` narrows the set to pages actually touched since the last briefing, the same idiom `/weekly-reread` uses. Then read only those pages closely. Items on untouched pages can still qualify under (c).

   **Monday: skip the filter entirely — full sweep of every open item.** Cap per the table below.

4. **Yesterday's daily capture** — `raw/captures/daily/YYYY-MM-DD - Daily.md` for yesterday's date. Scan for explicit `[todo]` / `[carryover]` markers, "tomorrow" / "carry over" phrases, and unresolved `[?]` questions. These become *Carryovers*. Cap 3.

5. **Reading queue** — `raw/briefings/reading-queue.md`, a simple rolling checklist the vault owner keeps by hand, seeded from the Reading plan of the newest weekly digest:

   ```markdown
   - [ ] [[insights/some-insight]] — why it's queued (~8 min)
   - [ ] [[sources/some-book]] — why it's queued (~12 min)
   ```

   Take the **top unchecked item** as *Today's read*. If the file does not exist, fall back to the Tier 1 checklist of the newest `raw/briefings/weekly-digest-*.md` and take its first unchecked entry. If neither exists, omit the section.

If a source is unreachable (missing file, unreadable, empty), note `(skipped: reason)` in that section and continue. **Never block the briefing on a single source.**

## Output

Write to `raw/briefings/YYYY-MM-DD.md`:

- File missing → create it from the template below.
- File exists → **overwrite in place**. The briefing is a fresh snapshot, not an accreting log.

Briefings live in their own folder, separate from `raw/captures/daily/`. Captures are inbound notes the vault owner writes; briefings are forward-looking todos the skill generates from plans, projects, and the weekly plan. Different lifecycles, different retention.

Echo the same briefing inline in the conversation.

### File template

```markdown
# Briefing — YYYY-MM-DD (Day, ISO week NN)

**Shape of the day**: <one sentence — the day's center of gravity>

## Top 3 priorities (week of YYYY-MM-DD)
1. ...
2. ...
3. ...

## New since yesterday   *(Monday: "Open next-actions — weekly sweep")*
- [[projects/some-project]] — action item *(new)*
- [[plans/some-plan]] — action item *(rescoped: was "...")*

## Carryovers
- ...   *(omit the whole section if none)*

## Today's read (~N min)
- [[some-page]] — <one-line why, taken verbatim from the reading queue>
```

If the optional calendar extension is wired in (see below), a `## Calendar` section goes directly under *Shape of the day*.

## Optional: wiring in a calendar or task source

**The skill works with nothing but the vault.** This section is for vault owners who already have a calendar or an issue tracker reachable from Claude Code — an MCP server, a CLI, or a periodically exported file. Nothing here is provider-specific; fill in the blanks once and the rest of the skill picks it up.

Record whichever hooks you need near the top of this file, or in your own `CLAUDE.md`:

```
CALENDAR_SOURCE: <how to read today's events — an MCP tool call, a CLI command,
                  or a path to an exported agenda file (.ics / .md)>
TASK_SOURCE:     <how to read open tasks assigned to you — an issue-tracker CLI,
                  or a path to an exported task list>
TIMEZONE:        <IANA zone used for the day boundary, e.g. Europe/Berlin>
```

Contract a source must satisfy to be usable here:

- **Read-only.** The briefing never writes back to a calendar or tracker.
- **One call, fast.** If it needs auth, pagination, or more than a couple of seconds, it is too heavy for a morning skill.
- **Degrades to a one-liner.** On any failure, render `(skipped: reason)` and carry on. A dead integration must never cost the vault owner their briefing.
- **Calendar returns**: start time, end time, title, location, attendees. Render as `HH:MM-HH:MM — Title (location) — with [[entity]]`, wikilinking attendees that have `wiki/entities/` pages.
- **Task source returns**: title, due date, link. External tasks **merge into the delta filter** exactly like plan and project items — an unchanged external task is just as suppressible as an unchanged wiki one.

Two boundaries worth keeping:

- **The vault stays authoritative.** An external tracker is one more input, not the spine. If a task matters, it belongs on a `wiki/plans/` or `wiki/projects/` page too.
- **Calendar counts against the line budget.** A 9-meeting day plus a Monday sweep will blow past 20 lines; *Calendar* and *Top 3* keep priority, *New since yesterday* gets trimmed first.

## Rules

- **Delta, not inventory.** Tue-Sun: an unchanged open action item from yesterday's briefing does **not** reappear. It is not lost — it lives on its plan or project page and resurfaces in Monday's full sweep, or sooner if it changes or comes due.
- **20 lines or fewer below the H1.** If the day genuinely overflows (Monday sweeps may), *Top 3* keeps priority and *New since yesterday* is trimmed first.
- **No re-prioritising.** Surface what is already prioritised on the weekly plan and the project pages. Let the vault owner re-rank if they want to.
- **Cite wikilinks.** Every plan or project action item links back to its source page, so the briefing is one click from the page that owns the item.
- **Read-only of `wiki/`.** The briefing never edits a plan, a project, or the log. The only file it writes is `raw/briefings/YYYY-MM-DD.md`.
- **A briefing is not a wiki input.** Don't create a `wiki/sources/` page from a briefing, and don't append briefing contents to `wiki/log.md`. Briefings decay within the day.
- **Don't check items off the reading queue.** The briefing *surfaces* the top queue item; only the vault owner edits `reading-queue.md`. Marking it read on their behalf silently drains the queue.
- **No `qmd update` / `qmd embed`.** Briefings decay fast and would pollute semantic search with yesterday's todos, so the reindex is deliberately skipped here. (If you would rather have briefings searchable, `raw/briefings/` is registered as the `briefings` collection by default — run the reindex yourself and drop this rule.)
- **Single, path-scoped commit at the end.** Stage **only** `raw/briefings/YYYY-MM-DD.md`. Commit message: `chore: daily briefing YYYY-MM-DD`. **Never push.** A bare `git commit -a` sweeps up whatever else was mid-flight in the working tree; always name the path.

## Caps (avoid noise)

| Section | Max items |
|---|---|
| Calendar (if wired in) | all (it's the calendar) |
| Top priorities | 3 |
| New since yesterday (Tue-Sun) | 5 |
| Weekly sweep (Monday) | 8 |
| Carryovers | 3 |
| Today's read | 1 |

If *Top 3* is empty, write `- (none)`. *New since yesterday*, *Carryovers*, and *Today's read* are **omitted entirely** when empty — an empty delta is itself the signal, and a `(none)` line spends budget saying nothing.

## Common mistakes

- **Re-listing unchanged action items every day.** The defining failure this skill exists to prevent. If yesterday's briefing had it, today's does not — unless it changed, came due, or it is Monday.
- **Treating a missing yesterday-briefing as "everything is new".** If yesterday's file is absent, diff against the most recent briefing file instead. Only if no briefing exists in the last 7 days should you run a full sweep — and say so explicitly in *Shape of the day*.
- **Writing to `raw/captures/daily/`.** Briefings live in `raw/briefings/YYYY-MM-DD.md`. Captures are what the vault owner writes; briefings are what the skill generates.
- **Duplicate briefings.** Always check whether `raw/briefings/YYYY-MM-DD.md` exists before writing. Overwrite (refresh in place); never append a second briefing to the same file.
- **Wrong day after midnight.** If the local clock is past 23:00, ask which date is meant before compiling anything.
- **Iterating a roll-up page instead of the real pages.** If the vault has an "active projects" summary page, it is a roll-up and goes stale between edits. Iterate the actual plan and project files.
- **Editing a plan or project page to tick an item off.** The briefing reports; it does not update state. Closing an item is a separate, deliberate edit.
- **Padding empty sections.** Omitted beats `(none)` for the three delta sections. The line budget is the point.
- **Confusing this with the weekly skills.** This is forward-looking and today-scoped. `/weekly-reread` is backward-looking over the past 7 days of raw notes. `/weekly-digest` is week-scoped and covers wiki changes, not todos.
- **Letting an optional integration become a hard dependency.** Any external source that fails must degrade to `(skipped: reason)`, not abort the briefing.
- **Staging more than the briefing file.** Path-scoped commits only.

## Iteration log

- **v1** — initial version, promoted from a paste-into-LLM prompt to a project skill. Sources fixed to the weekly plan, active plans, active projects, and yesterday's daily capture.
- **v2** — split briefings out of `raw/captures/daily/` into their own folder, `raw/briefings/YYYY-MM-DD.md`. Rationale: briefings are generated forward-looking todos, captures are hand-written inbound notes. Different lifecycles, different retention. Added the single path-scoped commit at the end.
- **v3** — **delta-first redesign.** Triggered by the briefing having grown too heavy to read. Changes: (1) Tue-Sun briefings show only new / changed / due next-actions relative to yesterday's briefing, with Monday as the full sweep — this kills the daily re-listing of the same open items; (2) a hard budget of 20 lines or fewer below the H1; (3) the separate plan and project sections merged into one *New since yesterday* section, and an *On your mind* section folded into *Shape of the day*; (4) *Today's read* added from `raw/briefings/reading-queue.md` — the daily drip end of the weekly digest's queue; (5) empty delta sections omitted instead of `(none)`-padded.
- **v4** — de-coupled from external services. The external calendar and spreadsheet inputs of earlier versions became vault-native: this week's plan now comes from `raw/captures/weekly/`, priorities and next-actions from `wiki/plans/` + `wiki/projects/` with `status: active`, and the reading queue falls back to the newest weekly digest's Tier 1 list. Calendar and task integrations moved to an explicit, provider-agnostic extension point with a degrade-gracefully contract.
