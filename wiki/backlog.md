---
type: backlog
title: "Backlog"
date_created: 2020-01-01
date_updated: 2020-01-01
# Tally (append-only, one sentence per change — maintained by the `backlog` skill):
# Seeded 2020-01-01 with one worked example item so the format is unambiguous. Count 0 -> 1.
---

# Backlog

**Purpose.** A persistent queue of *"X should absorb / extend / get-its-own-page later"* pointers — anything surfaced during an op that won't happen this session but shouldn't be forgotten. Synthesis to absorb later, stub pages to create, per-source deeper passes, lint candidates: any deferred wiki work.

**How this works.** Each item names:

- **Target page** — where the update lands
- **What to add** — the specific material, ideally with glossary anchors
- **Why it matters** — the leverage
- **Why deferred** — optional; the gate holding it
- **Source trigger** — when and where the material landed

Items are **not done immediately**. The rule is: when you next edit the target page for any reason, fold in the deferred material. Items can also be batched into one synthesis pass when the queue grows long.

**Clearing discipline.** When an item lands, **delete it here** — don't strikethrough. The backlog reflects *what's still owed*, not history. History lives in `wiki/log.md` and in git.

**Who maintains this.** The `backlog` skill (`.claude/skills/backlog/`) is this file's actuator — invoke it with "track this in the backlog" (capture) or "sweep the backlog" (reconcile + report). It is the only thing that should touch the `## Current Items (N)` count, the frontmatter tally, and `date_updated`. Hand-editing those three is how this file drifts.

**Identifiers.** Numbered items (`### 1.`) are source- or ingest-derived synthesis work. Lettered items (`### A.`) are process / tooling / meta work. Pick the next free identifier consistent with its siblings; never reuse one.

---

## Current Items (1)

### 1. (example — delete once you file your first real item) Promote spaced repetition's sibling theme into its own topic page

- **Target page**: new — `wiki/topics/retrieval-practice.md`
- **What to add**: the retrieval-practice material currently sitting inside [[topics/example-topic]] as a two-sentence aside — the testing effect, why re-reading feels productive but underperforms, and the three worked examples in [[sources/example-source]]. Add a `[[glossary/frameworks#Retrieval practice]]` anchor when the page is written.
- **Why it matters**: retrieval practice is doing real work in two pages already but has nowhere to accumulate. Splitting it gives future ingests a landing site instead of growing the spaced-repetition page sideways.
- **Why deferred**: one source so far. Promote on the second independent source that treats it substantively (single-source rule).
- **Source trigger**: [[sources/example-source]], ingested 2020-01-01.

## Related

- [[log]] — wiki operations history (this backlog deliberately doesn't duplicate it)
- [[index]] — master catalog
- [[glossary]] — term anchors for the items above
