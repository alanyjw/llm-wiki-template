---
type: topic
title: "System Design Principles"
source_count: 0
date_updated: 2020-01-01
tags: [tech, craft]
---

> **Recent updates** (most recent first):
> - **2020-01-01** — Created. Seeded with five worked-example principles (P-001..P-005) across three domains.

# System Design Principles

The catalog behind the `design-principles` skill. One page, append-only, and the
single place where transferable design lessons from your technical reading
accumulate. *Extract* mode mines a source and files entries here. *Review* mode
reads this page and applies it as a checklist against a design artifact. *Curate*
mode merges near-duplicates and keeps the sectioning honest.

The value is compounding: a principle you extracted from an article a year ago
shows up as a finding in next week's design review, without you remembering the
article.

## Entry format

Every principle is one H3 block, nested under a `## Domain:` H2, with a fixed
four-field shape:

```markdown
### P-NNN · <short memorable title — 8 words or fewer>

**Principle:** <one paragraph, 60 words or fewer. Transferable beyond the
source's specific tech. Actionable — a future design could honor or violate it.
Atomic — one idea, not a paragraph of related ideas.>

**Applies when:** <semicolon-separated clauses; this is the relevance filter
review mode uses to decide whether the principle is in scope for an artifact.>

**Source:** [[sources/<slug>]]

**Tags:** <2-5 lowercase-hyphen topical tags, comma-separated.>
```

Field notes:

- **`P-NNN`** — monotonic, zero-padded to three digits. Extract mode reads the
  current maximum and increments. IDs are stable: a merge leaves a tombstone
  rather than re-sequencing, so old review reports keep resolving.
- **`Applies when:`** — the load-bearing field. A principle with a vague
  applies-when either matches every artifact (noise) or none (dead weight).
  Write it as conditions an artifact can be tested against.
- **`Source:`** — prefer a `[[sources/<slug>]]` wikilink to the wiki source page,
  which carries the raw link (the one-hop provenance rule in CLAUDE.md). Never
  link `[[raw/...]]` from this page — it is a synthesis page and the lint gate
  flags direct raw links (`PROV001`). If the source has not been ingested to a
  source page yet, either create the source page or fall back to a plain-text
  attribution naming author, title, and URL. After a merge, `Source:` holds
  several links — that union is the strengthening signal, and merges never drop
  a source.
- **Domain sections** — every entry is an H3 under exactly one `## Domain: <name>`
  H2, ordered by `P-NNN` within each domain. The nesting is what lets review mode
  load a subset of the catalog once it outgrows a comfortable whole-read: reading
  the `## Domain: Performance and Latency` section returns its principles and
  nothing else.

`source_count: 0` above is deliberate: it counts *ingested* sources with wiki
source pages, and the seed entries below cite public writing in plain text
rather than pages in this vault. Extract mode bumps it as real sources land —
and rewrites this sentence when it does, so the prose and the frontmatter never
disagree.

## Domain: Data and State Architecture

### P-001 · Local state is the source of truth

**Principle:** Treat the client's local store as the primary read and write
surface, and the server as a synchronizing peer. Reads never wait on the
network; writes land locally and reconcile afterward. This inverts every data
path in the system, so it is a day-one decision — retrofitting it means
rewriting the application.

**Applies when:** designing an interactive application; a latency target under
roughly 100ms is claimed; offline or flaky-network use is plausible; the spec
describes reads as fetches.

**Source:** Public write-ups on local-first and sync-engine architecture — Ink &
Switch, "Local-first software" (inkandswitch.com/local-first).

**Tags:** architecture, latency, sync, data-model

### P-002 · Make the invalid state unrepresentable

**Principle:** Encode constraints in the data model rather than enforcing them
in the code that touches it. If two fields can never both be set, model them as
one variant with two cases. Validation scattered across call sites drifts as
call sites multiply; a shape that cannot hold a bad value cannot drift.

**Applies when:** designing a schema, API payload, or config format; the spec
contains rules of the form "if X is set then Y must be null"; the same
validation appears in more than one place.

**Source:** Common to type-driven design writing; see Yaron Minsky's "Effective
ML" talks for the canonical framing.

**Tags:** data-model, correctness, api-design

## Domain: Performance and Latency

### P-003 · Budget the interaction, not the average

**Principle:** Set an explicit numeric budget for the slowest common
interaction, not for an average. A healthy median hides the tail users actually
remember. Write the number into the design doc, so a later regression is a
broken contract rather than a matter of taste, and so performance work has a
stopping rule.

**Applies when:** any user-facing system; the spec claims something will be
"fast" or "responsive" without a number; there is no agreed definition of a
performance regression.

**Source:** Web-performance budget practice; see the RAIL model and Core Web
Vitals thresholds (web.dev) for concrete starting numbers.

**Tags:** performance, budgets, measurement

## Domain: Interfaces and Reliability

### P-004 · Every abstraction earns its layer

**Principle:** A layer must hide more complexity than the interface it adds.
Count what a caller has to know to use it correctly; if that is most of what the
layer wraps, delete the layer and expose the underlying thing. A thin
pass-through costs indirection at every read and buys nothing back.

**Applies when:** a design introduces a wrapper, adapter, service, or module
boundary; the justification is "for flexibility" or "in case we swap it later";
the proposed interface mirrors the thing it wraps method-for-method.

**Source:** John Ousterhout, *A Philosophy of Software Design* — deep modules
versus shallow ones.

**Tags:** modularity, interfaces, complexity

### P-005 · Failure modes are part of the interface

**Principle:** Specify what a component does when its dependency is slow,
absent, or wrong: timeouts, retry policy, fallback behavior, and what the caller
observes in each case. A design that describes only the happy path has not
removed those decisions, it has deferred them to whoever is on call at 3am.

**Applies when:** the design contains a network hop, external dependency,
background job, or queue; the spec has no degradation or error section; a
timeout value is unstated.

**Source:** Michael Nygard, *Release It!* — stability patterns and antipatterns.

**Tags:** reliability, error-handling, api-design

## Related

- [[projects/example-project|Personal Note-Taking App]] — the shape of artifact
  *review* mode reads this catalog against: a design doc with a data model, a
  sync question, and open decisions.
- The `design-principles` skill at `.claude/skills/design-principles/SKILL.md`
  is the only thing that should write to this page. Hand-editing skips dedup,
  ID assignment, callout rotation, and the qmd reindex.
