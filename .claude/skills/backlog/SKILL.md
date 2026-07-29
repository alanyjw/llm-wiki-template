---
name: backlog
description: Use when the vault owner says "track this in the backlog", "park this", "add to backlog", "tend the backlog", "sweep the backlog", "what's still open", "reconcile the backlog", or when work is being deferred mid-session and shouldn't be lost. Two modes — *capture* files a new open item into wiki/backlog.md in the canonical format; *sweep* reconciles existing items against the live wiki (clears what's landed, flags what's stale), optionally discovers un-captured open items from the session, and reports the open set. Keeps the count line + header tally + date_updated in sync, runs the lint gates, and commits locally. The cross-session memory for deferred wiki work.
---

# Backlog

`wiki/backlog.md` is the vault's persistent queue of *"X should absorb / extend / get-its-own-page later"* pointers — the cross-session memory for work surfaced during an op that won't happen now but mustn't be forgotten. This skill is its actuator: **capture** new open items, **sweep** (reconcile + discover + report) the existing ones. It is the only thing that should touch the count line and the header tally.

## Why this exists

Open items leak. They get mentioned in a session, deferred, and lost when the context window closes — unless they're written to a durable, git-committed place. `wiki/backlog.md` is that place (it survives across sessions); this skill keeps it honest. Without tending, the backlog **drifts**: items land but never get cleared (false debt), the count line desyncs from reality, and duplicates accumulate. Sweep mode is the anti-drift pass.

## When to use

- **Capture** — the vault owner says "track this", "park this", "add to backlog", "backlog this"; OR work is being deferred mid-session ("we'll do that later", "out of scope for now", "needs a second source first") and the deferral carries a concrete future action.
- **Sweep** — the vault owner says "tend the backlog", "sweep the backlog", "reconcile the backlog", "what's still open", "clear the backlog", or a scheduled backlog routine fires.
- **Bare invocation** (`/backlog` with no clear intent) → ask one question: *"Capture a new item, or sweep the existing backlog?"* Don't guess.

**Proactive discipline.** Any session that *defers* a concrete piece of wiki work should capture it before moving on — treat "we'll come back to that" as a trigger, not a throwaway. This skill is also schedulable: a periodic sweep (weekly, or alongside the weekly digest) keeps drift from accumulating between manual runs.

## The item schema (match it exactly)

Every backlog item is an H3 block. Identifiers are organic — **numbered `### N.`** for source/ingest-derived synthesis items, **lettered `### X.`** for process / tooling / meta items. Pick the next free identifier consistent with siblings (read the file; don't reuse).

```markdown
### N. <short imperative title>

- **Target page**: <where the update lands — an existing [[wikilink]] or "new — `wiki/.../slug.md`">
- **What to add**: <specific material, ideally with glossary anchors>
- **Why it matters**: <the leverage — why this is worth doing later>
- **Why deferred**: <optional — the gate holding it: single-source rule, stakeholder-pending, premature, etc.>
- **Source trigger**: <when/where the material landed — [[wiki/sources/...]] or a dated capture>
```

## Mode 1 — Capture

1. **Read `wiki/backlog.md`.** Note the `## Current Items (N)` count, the existing identifiers, and the header-note tally (the running prose log in frontmatter — it's a YAML comment, so it never renders in Obsidian's Properties UI).
2. **Dedup.** If the item already exists (same target + same material), say so and stop — don't double-file. If it's a near-match, propose extending the existing item instead.
3. **Draft the item** in the schema above. Be specific: vague items ("improve X") are noise. The *Why it matters* and *Source trigger* are mandatory — an item with no trigger is unmoored.
4. **Confirm with the vault owner** when capturing from an ambiguous deferral (proposed title + target). Skip the confirm when they explicitly said "track this: <clear thing>".
5. **Insert** the item before the `## Related` section, after the last current item.
6. **Reconcile the bookkeeping** (all three, every time):
   - `## Current Items (N)` → increment.
   - Frontmatter header-note tally → append one sentence: `Item <id> added YYYY-MM-DD (<one-line what + why>). Count <old> -> <new>.`
   - `date_updated:` → today.
7. **Lint + commit** (see *Finalize*).

## Mode 2 — Sweep

The anti-drift pass. Three sub-steps; do all unless the vault owner scopes it.

### 2a. Reconcile (clear what's landed)

For each current item: read its **Target page** and check whether the deferred material is now present (the page covers what *What to add* describes).

- **Landed** → the item is owed no longer. **Delete the H3 block** (don't strikethrough — the backlog reflects what's *still* owed; history lives in `wiki/log.md`). Append to the header tally: `Item <id> cleared YYYY-MM-DD (<what landed + where>). Count <old> -> <new>.` Decrement the count.
- **Partially landed** → trim the item to the remaining work (shrink, don't clear); note in the tally `Item <id> trimmed YYYY-MM-DD (...)`.
- **Still open / blocked** → leave it. If the gate is clearly stale (e.g. the blocking source has since been ingested, or a "promote on 2nd source" item now has its second source), surface it to the vault owner as *ripe* — these are the highest-value clears.
- **Stale / duplicate / no-longer-relevant** → propose removal with reasoning; clear only on the vault owner's confirm.

### 2b. Discover (optional — capture what the session leaked)

Scan recent activity for open items not yet in the backlog: the current conversation's deferrals, recent `git log` one-liners with "defer/later/TODO/follow-up", and recent `wiki/log.md` entries that name a "parked" / "deferred" / "hold for" follow-up. File any genuinely-missing ones via Mode 1's schema (no separate confirm needed inside a sweep — list them for the vault owner as you add).

### 2c. Report

Emit a tight status: total open count; the **ripe** items (gates met — recommend clearing/doing); anything blocked and on what; and what was cleared/added this sweep. This is the user-facing value of a sweep.

## Finalize (both modes)

1. **Lint.** `wiki/backlog.md` is a Layer-1 carve-out (vendor `OFM901` auto-fix bug — see `.obsidian-linter.jsonc`), so markdownlint-obsidian gives no useful signal on this file; run Layer 1 only if the sweep touched other wiki pages. Always run **`python3 .claude/scripts/wiki-lint.py wiki/`** (catches broken wikilinks/anchors in the items you wrote) and **`python3 .claude/scripts/regenerate-index.py --check`** (no drift — backlog isn't indexed, but a sweep may have touched other pages). Fix hard errors; abort rather than commit a half-state.
2. **qmd** only if the sweep edited other indexed wiki pages (a pure backlog edit doesn't need it, but run `qmd update && qmd embed` if you cleared an item by *writing* the material into a target page).
3. **Commit** locally, staging only touched files:
   - Capture: `backlog: track <id> — <short title>`
   - Sweep: `backlog: sweep — N cleared, M added, K trimmed (YYYY-MM-DD)`
   - **Never push.** The vault owner pushes.

## Rules

- **This skill owns the count line + header tally.** Never let them drift. Every add/clear/trim updates `## Current Items (N)`, the frontmatter tally sentence, and `date_updated` together.
- **Delete cleared items; don't strikethrough.** The backlog is what's *still owed*. History is in `wiki/log.md`.
- **Capture needs a trigger + a leverage.** No source-less, reason-less items — they become permanent noise.
- **Don't do the work inside capture.** Capture *files* the pointer; the actual synthesis happens later (or in a sweep that chooses to land a ripe item).
- **Don't auto-clear on a guess.** Clear only when the target page genuinely holds the material; when unsure, leave it and flag as ripe-for-review.
- **Reconcile before you report.** A status that counts already-landed items as open is worse than no status.
- **Never push.**

## Caps

| Item | Cap |
|---|---|
| Items captured per `capture` run | typically 1 (a batch is fine if the vault owner lists several) |
| Confirm gate | ambiguous deferrals only; explicit "track this: X" skips it |
| Files touched (capture) | 1 (backlog.md) + nothing else |
| Files touched (sweep) | backlog.md + any target page where a ripe item is landed |

## Common mistakes

- **Letting the count desync.** The `## Current Items (N)` heading and the frontmatter tally must always agree with the actual item count — reconcile both on every change. (This file drifts easily; count corrections belong in its own header tally.)
- **Strikethrough instead of delete** on a cleared item — leaves stale debt that re-reads as open.
- **Filing vague items** ("clean up X", "improve the thing") with no concrete *What to add* — they never get actioned and clog the queue.
- **Capturing the work instead of the pointer** — backlog items are *deferrals*, not done work; if you can do it now in two minutes, do it, don't file it.
- **Clearing an item because it *feels* done** without reading the target page to confirm the material actually landed.
- **Skipping the trigger** — an item with no Source trigger can't be evaluated for ripeness later.
- **Reaching for Layer-1 markdownlint on backlog.md** and reading its silence (or its OFM901 noise) as signal — that file is carved out; `wiki-lint.py` is the gate that matters here.
- **Hand-editing the count line or tally outside this skill** — that is the single most common source of drift.
- **Pushing the commit.**

## Iteration log

- **v1** — initial version. Spun out of a backlog-cleanup session: hand-edits to `wiki/backlog.md` plus an audit finding that the file silently drifts (cleared items left in place, count line desynced) made a dedicated actuator worthwhile. Two modes (*capture* / *sweep*) over the file's existing schema (Target / What to add / Why it matters / Why deferred / Source trigger). Encodes the file's standing disciplines as enforced rules: this skill owns the count line + the append-only header tally; cleared items are *deleted*, not struck; every item needs a trigger + a leverage. Sweep's *reconcile* sub-step is the anti-drift pass (clear-what-landed, flag ripe gates); *discover* sweeps the session for leaked open items; *report* surfaces the ripe set. Schedulable as a periodic routine. Deferred: a `--report ripeness` heuristic that auto-checks each item's gate against the live wiki (e.g. single-source-rule items whose second source has since been ingested) — revisit if reconcile-by-hand proves slow.
