# CLAUDE.md — Extended Reference

This file holds material that was compressed out of `CLAUDE.md` (which has a hard 300-line budget) but is worth keeping. **`CLAUDE.md` is canonical for day-to-day work.** Reach here when you need:

1. the full YAML frontmatter shape for a page you're about to create,
2. the reasoning and worked examples behind the authoring-voice rules,
3. the convention for writing a design spec before a non-trivial skill,
4. the operational distinction between `daily-briefing`, `weekly-digest`, and `weekly-reread`,
5. the *why* behind individual lint rule codes,
6. the Recent-Updates discipline beyond what the format gate checks,
7. the one-line purpose of each shipped skill.

When `CLAUDE.md` grows past its budget, detail moves here — not the other way round. Nothing in this file overrides the schema.

---

## 1. Full YAML Frontmatter Per Page Type

`CLAUDE.md` carries a compact required/recommended-keys table. The full YAML shape per page type follows. Dates are ISO `YYYY-MM-DD`. A bare four-digit year used as a *tag* must be quoted (`tags: [work, "2026"]`) — unquoted it parses as an integer and fails Layer 1 rule `OFM087`. Dates in `date_*` fields are genuine YAML dates and stay unquoted.

### Source Summary (`wiki/sources/`)

Filed after ingesting a raw note. One source page per ingested note, or per batch of tightly-related notes.

```yaml
---
type: source
title: "Source title"
raw_sources:
  - "raw/notes-import/Original Note Name.md"
date_ingested: 2026-04-16
date_original: 2022-03-15  # from the note's frontmatter or content
tags: [work, leadership, meeting]
---
```

Body: key takeaways, structured summary, notable quotes or data points. At least one body wikilink back to the raw file (see the Provenance Principle) — frontmatter YAML isn't clickable in Obsidian.

### Entity Page (`wiki/entities/`)

A person, organization, project, or place that appears across multiple sources.

```yaml
---
type: entity
entity_type: person | organization | project | place
title: "Entity Name"
aliases: ["Nick Name", "Abbreviation"]
first_seen: 2026-04-16
source_count: 5
tags: [work, leadership]
---
```

Body: who or what this is, key facts, role, relationship to the vault owner, timeline of appearances, cross-references.

### Topic Page (`wiki/topics/`)

A concept, theme, or subject spanning multiple sources.

```yaml
---
type: topic
title: "Topic Name"
source_count: 12
tags: [craft, personal]
---
```

Body: definition and overview, key ideas, how the topic appears across sources, how it evolved over time, related topics.

### Insight Page (`wiki/insights/`)

A synthesized observation, pattern, or analysis emerging from multiple sources. This is the only page type that carries an explicit `confidence` claim — set it honestly; `low` is a legitimate and useful value.

```yaml
---
type: insight
title: "Insight Title"
derived_from:
  - "wiki/topics/some-topic.md"
  - "wiki/sources/some-source.md"
date_created: 2026-04-16
confidence: high | medium | low
tags: [craft, personal]
---
```

Body: the insight itself, supporting evidence with links, implications, open questions.

### Plan Page (`wiki/plans/`)

Goals, action items, personal planning documents.

```yaml
---
type: plan
title: "Plan Title"
status: active | completed | paused | abandoned
timeframe: "Q2 2026"
date_created: 2026-04-16
date_updated: 2026-04-16
tags: [goal-setting, career]
---
```

Body: objective, context, action items (checkboxes), progress notes, related insights.

### Project Page (`wiki/projects/`)

An active multi-stakeholder project. Projects differ from plans (personal goals) and from entity pages (which describe *what a thing is*, not the live work around it). A project page is the living decision log — it accumulates stakeholder positions, decisions, open questions and action items across many meetings over months or years.

```yaml
---
type: project
title: "Project Name"
status: active | shipped | paused | sunset
stakeholders: ["Person A", "Person B"]   # wikilink-able entities
date_started: 2025-05-29
date_updated: 2026-04-24
tags: [work, project]
---
```

Body structure:

- **Vision & origin** — whose burden, why, when it started.
- **Scope** — current surfaces / journeys / phases.
- **Stakeholder positions** — one sub-section per key stakeholder, capturing their distinctive voice: what they care about, verbatim quotes, recurring frames. Update in place as positions evolve; don't append a new section per meeting.
- **Decisions log** — chronological, `[YYYY-MM-DD] Decision — who`. Newest at the bottom.
- **Open questions** — unresolved items, each tagged with who raised it.
- **Action items** — checkbox style, owner named if known.
- **Related sources** — wikilinks in date order. Raw wikilinks (`raw/meetings/...`, `raw/notes-import/...`) are permitted here; this is the documented `PROV001` exception.
- **Related wiki** — entities / topics / insights this project intersects.

### Overview (`wiki/overview.md`)

The top-level synthesis of the vault owner's life, updated as the wiki grows.

```yaml
---
type: overview
date_updated: 2026-04-16
---
```

Sections mirror the vault owner's actual domains — for the shipped example profile: Work, Craft, Personal Growth, Side Projects, Goals, Open Questions. Rewrite the section list to match the profile in `CLAUDE.md` §About the Vault Owner.

### Special pages — no required-key schema

`index`, `log`, `log-archive`, `glossary`, `backlog`, the notes-import manifest and `reflections-log` are registered in `wiki-lint.py`'s `REQUIRED_KEYS_BY_TYPE` with an **empty** key list. That is deliberate, and it is not the same as being unregistered: an unregistered type trips `FM003` (warning) and skips the schema check silently, while an empty registration says "this type is known and requires nothing." They are also exempt from the Recent-Updates callout (`RU001`) and allow-listed in `--report orphans`.

`wiki/reflections-log.md` — the append-only first-person layer — carries only:

```yaml
---
type: reflections-log
title: "Reflections Log"
date_updated: 2026-04-16
---
```

The page documents its own entry format (`### YYYY-MM-DD — short handle`, then a `**Type:**` line drawn from reaction / decision / self-observation / open question / revisit, and a `**Trigger:**` line linking the `wiki/sources/` page — one hop, same as everywhere else; a backticked raw path only while no source page exists yet). Two disciplines are worth restating because they are the ones that erode:

- **It is append-only.** An entry records what you thought on a date. When your view changes, add a new `revisit` entry naming the old handle — never edit the original into agreement with the present. A log that quietly updates itself preserves none of the wrongness, and the wrongness is the only way to see how your judgment moved.
- **It does not merge into `insights/`.** An insight page may cite an entry here as the origin of a hunch. It must not paraphrase first-person material into a third-person assertion — "I felt overwhelmed by this" is not evidence for a claim, and dressing it as one weakens both pages.

It rotates on `wiki/log.md`'s rhythm (~250KB or year-end) into `wiki/log/YYYY-reflections-archive.md` with `type: log-archive`, `year:` and `date_range:`. `regenerate-index.py` never touches it — the script walks only `wiki/{entities,topics,sources,insights,plans,projects}` — so it creates no index drift and never appears in `wiki/index.md`.

---

## 2. Wiki Authoring Voice — Full Rules + Examples

`CLAUDE.md` states each rule in one line. Each is restated below with the reasoning and a worked example.

### 2.1 Your own domain's vocabulary leads. Imported frameworks follow.

When a synthesis page contrasts the vault owner's existing working vocabulary with an imported framework's vocabulary (a management book, a design methodology, an operations playbook), the translation table's **left column is the owner's language; the right column is the imported term.** Body prose introduces each concept in native form first, then names the imported register.

**Reason:** the owner's primary working context is their own organization's language. The imported vocabulary is the second register, not the first. A wiki that leads with the imported term forces a translation step every time the page is read, and quietly teaches the owner to speak in someone else's idiom to their own team.

**Never invent a new term when a domain-native one already exists.** If the team already calls it "the handover doc", don't rename it "the transition artifact" because a book used that phrase.

Worked example (a design team's page on decision-making):

| Our language | Imported term (source) |
|---|---|
| "the one-pager" | Design brief (design-thinking literature) |
| "who's holding the pen" | Directly Responsible Individual (Apple, via Rands) |
| "the walkthrough" | Design critique |

The prose above that table reads *"Every project has someone holding the pen — one person accountable for the shape of the thing. The management literature calls this a DRI."* Not the reverse.

### 2.2 Translation tables need a "why hold both registers" paragraph

A bare two-column table tells the reader the words map, but not *when to use which*. Add a one-paragraph framing alongside any such table: **which audiences hear which register, and what each register carries that the other undersells.**

Continuing the example above: *"Use 'holding the pen' with the team — it's concrete, it names an action, and nobody has to look it up. Use 'DRI' when writing for leadership or when citing the source, because it's the term that travels outside this building. 'Holding the pen' undersells the accountability; 'DRI' undersells the craft ownership. Hold both."*

Without that paragraph the table is decorative. With it, the reader knows when to switch.

### 2.3 Tactical adds must be grounded in actual context, not abstract

When importing a tactical practice (a hiring protocol, a review cadence, an interview question, a retro format), name the actual surface it applies to:

- **Team or tier** — e.g. *"the two senior ICs, not the whole team"*
- **Timing anchor** — e.g. *"at the Q3 planning session"*
- **Adaptation of the generic prompt to your context** — e.g. rewriting the generic *"If you were CEO, what would you change?"* to *"If you owned the design system budget next quarter, what would you cut first?"*

A bullet that reads as a generic LinkedIn tip has not earned its place in the wiki. The test: could this sentence appear unchanged in any other person's wiki? If yes, it's not grounded yet.

### 2.4 Retroactive "already done" closures cite specific provenance

If a backlog item or open question is being closed because the work was already completed earlier, the log entry or closure note must name **what** was done, **when**, and **at what scope** — e.g. *"closed by the 2026-04-18 table-pipe sweep, which fixed 68 wikilinks across 14 files"* — not just *"confirmed already done."*

A future reader, or a future Claude run, needs the receipt to trust the closure. An unsourced closure is indistinguishable from a wrong one, and it is the single easiest way for a wiki to start lying to its owner.

### 2.5 Voice is not the same as craft

The `tighten-prose` skill runs a clarity pass over prose — clutter, jargon, the missing "I". It is deliberately **voice-agnostic**: it makes writing clearer without making it sound like a different person. Don't reach for it to change register, and don't treat a tightened draft as a licence to drop the grounding rules above. Clear abstract writing is still abstract writing.

---

## 3. Skill Design-Spec Pointers

Most skills carry their full design inside their own `SKILL.md` — trigger phrases in the frontmatter `description`, numbered steps, a Rules section, a Caps table, a Common-mistakes list, and an iteration log. That is sufficient for a skill that is a linear procedure.

**Write a separate design spec first** when a skill has any of:

- a **state machine** or resumable progress (a batch drain that must survive interruption),
- **companion scripts** whose interface must be agreed before either side is written,
- **external state** outside the working tree (a git ref, a manifest file, an external corpus),
- **subagent orchestration** (dispatching fresh contexts, worktrees, parallel drafters),
- an **irreversible or expensive** step (bulk file moves, paid API calls, force pushes).

`batch-ingest`, `source-sync`, and `auto-review` in this template are all in that category. **They ship without specs.** Their design is folded into their `SKILL.md` files instead, because the template is a starting point rather than a running system with a decision history to preserve. Treat that as a gap you fill, not as the pattern to copy: the first time you materially change one of those skills, write the spec then.

**What belongs in a design spec:**

- **Problem statement** — what breaks today if the workflow is hand-run.
- **State model** — exactly what is persisted, where it lives, and what happens on a crash mid-run.
- **Chunking and limits** — batch sizes, token budgets, how many files may be touched per unit of work.
- **Failure modes** — for each, the detection signal and the recovery action. This is the section that pays for the doc.
- **Idempotency** — what happens if the skill is invoked twice on the same input.
- **Rollback** — how a bad run is undone.
- **Out of scope** — the adjacent things the skill deliberately does not do, and which skill owns them instead.

**Where specs live:** `docs/specs/YYYY-MM-DD-<slug>.md`, one file per design, dated by the day the design was settled. **This directory does not exist yet — create it when you write your first spec.** Link the spec from the skill's `SKILL.md` under a `## Design` heading so the two never drift apart silently. The spec is a historical record of the decision, not a living document — when the design changes, add to the skill's iteration log and write a new dated spec rather than editing the old one into a lie.

---

## 4. Daily-Briefing vs Weekly-Digest vs Weekly-Reread

`CLAUDE.md` lists all three skills but doesn't frame the operational relationship. They are deliberately complementary, and confusing them is a common failure mode.

| Skill | Direction | Horizon | Reads | Writes |
|---|---|---|---|---|
| `daily-briefing` | Forward | Today | Newest weekly plan in `raw/captures/weekly/`, active `wiki/plans/` + `wiki/projects/`, yesterday's briefing, reading queue (+ calendar *only* if you wire one in) | `raw/briefings/YYYY-MM-DD.md` |
| `weekly-digest` | Forward | The coming week, over the *wiki* | `wiki/log.md`, `git log`, per-page Recent-Updates callouts | `raw/briefings/weekly-digest-YYYY-MM-DD.md` |
| `weekly-reread` | Backward | The past 7 days, over *raw notes* | `raw/` notes from the window | Proposals to promote into `wiki/` |

- **`daily-briefing` is forward and shallow.** This week's top priorities, what's *new or changed* since yesterday's briefing, carryovers, and today's read from the rolling queue. Trigger: *"brief me" / "what's today"* — first thing in a working session. Delta-first: if nothing changed since yesterday, it should say so in a line, not re-render the same list. **It is vault-only by default** — it reads no external service. A calendar or issue tracker is an explicit optional extension point documented at the end of its `SKILL.md`: fill in one `CALENDAR_SOURCE` line and the briefing gains a `## Calendar` section; leave it blank and everything else still works. Don't assume a calendar row exists in a briefing you didn't configure.
- **`weekly-digest` is forward and wiki-internal.** It summarises what changed in the *synthesis layer* and budgets reading time against it. It never edits a wiki page. Trigger: *"weekly digest" / "what's new in the wiki"* — Sunday evening or Monday morning, before the re-read.
- **`weekly-reread` is backward and raw-facing.** A re-read across the past 7 days of raw notes: list new entries, surface 3-5 live fragments, ask case-contrast questions, propose promotions to `wiki/`. Trigger: *"weekly reread" / "weekly drill"* — end of week, before the new one starts.

**The failure mode:** running `daily-briefing` on a Sunday evening hands you Sunday's (mostly empty) to-do list instead of harvesting the week's notes. Running `weekly-digest` when you meant `weekly-reread` gives you a summary of what the LLM already wrote, when what you wanted was the raw material it hasn't processed yet.

The pair of weeklies is intentional: one harvests what just happened (`weekly-reread`, raw → wiki), the other reports what the wiki became (`weekly-digest`, wiki → you). Both should fire weekly. Three distinct rhythms, three distinct inputs.

---

## 5. Wiki Lint Pipeline — Extended Rationale

`CLAUDE.md` lists the rules and their IDs. The *why* behind the ones that are easy to misread or dismiss:

- **`WIKI001` (error) table-pipe-in-wikilink.** `[[X|Y]]` inside a markdown table cell breaks the table, because the `|` is read as a column separator and the row silently gains a column. The inner pipe must be `\|`-escaped. This is invisible in a diff review and obvious in rendered Obsidian, which is exactly why it needs a machine gate.
- **`WIKI002` (error) broken-wikilink.** Resolution is Obsidian-fuzzy, so it handles this vault's two mixed conventions: wiki-implicit (`[[sources/foo]]`) and vault-absolute (`[[raw/notes-import/foo]]`). A link that resolves in your editor but not in the linter usually means a filename case or hyphenation mismatch.
- **`WIKI003` (error) broken-wikilink-anchor.** The `#anchor` of a wikilink must resolve to a real heading (or glossary term) in the target file. Anchors rot faster than links, because renaming a heading is a low-ceremony edit that nobody thinks of as a breaking change.
- **`FM001` (error) missing frontmatter** and **`FM004` (error) missing a required key for a registered type.** `source` requires `raw_sources`; `plan` and `project` require `status`; `insight` requires `confidence`; `entity` requires `entity_type`. These are the keys other tooling reads — the index regenerator, the digest skill, retrieval scoping. A missing key doesn't degrade gracefully; it makes the page invisible to the machinery, which is why these two are the errors in the FM family.
- **`FM002` (warning) missing `type:`** and **`FM003` (warning) unknown `type:`.** Both short-circuit the rest of the schema check — the linter can't know which keys to require, so it says so and moves on rather than guessing. They are warnings, not errors: a page can legitimately carry a type this template doesn't ship a schema for (you may add your own), and `wiki-lint.py` exits 0 when only warnings fired. **Don't read a green run as "the type is recognised."** If you invent a page type, register it in `REQUIRED_KEYS_BY_TYPE` or every one of its pages will sail past the schema gate untested.
- **`FM005` (error) raw_sources path resolution.** Every path in a source page's `raw_sources:` must resolve on disk. This catches typos and post-rename drift — e.g. a corpus re-import that changes a filename prefix will leave every source page pointing at the old name. **Do not dismiss `FM005` as cosmetic.** It is a silent provenance break: the page still reads fine, but the trail back to the receipt is gone.
- **`RU001` (error) Recent-updates callout missing.** The only hard gate in the RU family: an in-scope synthesis page (`insight` / `topic` / `plan` / `project`) with no callout at all fails CI.
- **`RU002` / `RU003` (warnings) callout quality.** `RU002` flags a callout with no dated entry; `RU003` flags a callout whose newest entry predates the page's `date_updated` — prose changed but the trail didn't. Both are warnings, so **CI will not stop you landing a stale callout.** That makes them the wiki's most-ignored signal and the fastest way for the trail to start lying: `FM007` forces the `date_updated` bump, and nothing forces the matching callout entry. Sweep RU002/RU003 warnings by hand at the end of every ingest. See §6.
- **`RU004` (warning) more than 3 entries.** Older entries roll off; the full history already lives in `wiki/log.md` and in git. A callout-only trim doesn't require a `date_updated` bump — `FM007` strips the callout before comparing bodies.
- **`FM006` (warning) recommended keys.** `date_ingested`, `source_count`, `tags` and friends. Warnings, not errors, because a page can be genuinely useful before every count is filled in. They do degrade retrieval quality over time, so sweep them periodically.
- **`PROV001` (warning) inline-raw-link discipline.** `entities/`, `topics/`, `insights/`, `plans/` should cite via `[[wiki/sources/...]]` (one hop), not `[[raw/...]]` directly. `projects/` pages are exempt in their *Related sources* section, because raw meeting notes legitimately need to surface there when no source page exists yet — but **creating the source page is the preferred fix**, not leaving the raw link.
- **`WIKI007` (warning) anchor-prose source-count mismatch.** Topic pages that use the "<N> sources anchor this page" convention must keep N consistent with the frontmatter `source_count`. Prose numbers drift; this catches it.
- **`FM007` (CI-only) body changed without `date_updated` bump.** Lives in `check-date-updated.py` rather than `wiki-lint.py` because it needs git history — it diffs against the PR base or the previous push, which is meaningless in a local working-tree run. Scope: insights / topics / plans / projects.
- **`IO001`** is an internal I/O diagnostic (unreadable or undecodable file). If it fires, something is wrong with the file itself, not with its content.

**No per-file carve-outs.** Every file under `wiki/` goes through Layer 1, including the rolling pages (`log.md`, `backlog.md`, `glossary.md`). The `ignores` array in `.obsidian-linter.jsonc` excludes whole non-wiki trees only (`raw/`, `assets/`, `templates/`, `prompts/`, plus `node_modules/`, `.obsidian/`, `.git/`), and the documented Layer-1 command passes an explicit `"wiki/**/*.md"` glob anyway. Earlier versions of this template carved the three rolling pages out to dodge a vendor `OFM901` auto-fix crash; that is fixed in the pinned `1.1.0` (upstream issue #28 — the `Fix.deleteCount` sentinel is now handled gracefully), so the carve-out is gone. If you hit a genuine vendor false positive on a rolling page, disable the *rule* in the `rules` block with a comment, rather than silently dropping a file from the gate.

**Runner: `npx` locally, `bunx` in CI, never `--bun`.** The documented local command is `npx markdownlint-obsidian-cli@1.1.0 "wiki/**/*.md" --vault-root wiki`. `npx` ships with Node, which is already a prerequisite for `qmd`, so Layer 1 needs nothing extra installed — Bun is *not* a prerequisite of this template. `.github/workflows/wiki-lint.yml` runs the same pinned version through `bunx` because the runner installs Bun anyway; the output is identical, so use whichever you have. What neither runner tolerates is the `--bun` flag: the vendor's transitive `markdown-flavor-detection` dependency publishes no `src/` directory, so `--bun` resolves that package's `bun` export condition to a file that isn't in the tarball and the run dies with `Cannot find module 'markdown-flavor-detection/node'`. That is a vendor packaging bug, not a config problem. **Never write a `bunx`-only Layer 1 command into a skill.** An LLM following one on a Bun-less machine has to choose between aborting the ingest and silently skipping the gate, and it will pick the second — which is exactly the state the gate exists to prevent.

**Advisory reports** (never gate CI — invoke with `--report <name>`):

- **`orphans`** — synthesis pages with no inbound wikilinks. The special pages (overview / index / glossary / log / backlog / reflections-log / log archives / the notes-import manifest) are allow-listed.
- **`symmetry`** — cross-reference symmetry: if source S references `[[entities/X]]`, entity X's "Appears in" should reference S. Advisory rather than a gate, because entity pages curate their appearances and some asymmetry is deliberate.
- **`cross-links`** (`WIKI008`) — source-to-topic cross-link completeness across the vault. Recently-ingested sources are checked more strictly than old ones.
- **`tags`**, **`glossary-coverage`**, **`schema`**, **`duplicates`** — taxonomy drift, undefined in-house terms, frontmatter shape outliers, and near-identical pages.
- **`stale`** — the pruning surface, and the one report that can never become a gate. Four signals: **A** a `plan`/`project` still claiming `status: active` whose own date is older than `active_days`; **B** self-set alarms in the prose ("re-check Nov 2026", "revisit 2027-01-15") now due; **C** insight/topic pages aging past `synthesis_days`, informational only, since a stable page may simply be correct; **D** in-scope pages carrying no usable date — listed rather than skipped, so that `A=0` reads as *unassessed* rather than *clean*. Every other check here is keyed to content, so a clean tree stays clean; staleness is keyed to wall-clock time, and a hard gate on it would redden CI on a day nobody touched the repo. Thresholds are per-instance via `stale_thresholds`. Alarms inside append-only logs are skipped: the entry records what was said on a date, so an alarm written there could never be silenced.

**Baseline discipline.** Clear each layer to zero once, then treat any new error as a hard failure. A lint layer with a permanently non-zero baseline stops being read.

---

## 6. Recent-Updates Discipline — Beyond the Format Gate

`CLAUDE.md` shows the format and the good/bad examples. The deeper point: **the one-line delta is a quality bar, not a checkbox.**

- The hard gate (`RU001`) only checks that the callout *exists*. Whether it carries a date at all is `RU002`, and whether that date keeps up with `date_updated` is `RU003` — both warnings, so neither fails CI. Nothing anywhere checks whether the line is informative. *"Updated"* passes every gate and fails the purpose entirely.
- The delta line does double duty: a future Claude run uses it to decide whether to re-read the page before editing it, and the vault owner uses it to decide whether to spend attention on it this week. Both readers are deciding *re-read or skip* from that one line alone.
- **On creation:** the callout is exactly one line — `**YYYY-MM-DD** — Created.` Nothing more.
- **On every subsequent update:** add a new top entry. If there are now four, prune the oldest. The history isn't lost — it's in `wiki/log.md` and in git.
- **Write the delta as a noun phrase naming what is now in the page**, not a verb phrase describing what you did to it. *"Added the three-tier escalation model with worked examples"* tells the reader what they'd gain by re-reading. *"Refactored structure"* tells them nothing they can act on.
- **A callout-only trim is not a content change.** `FM007` strips the callout before comparing bodies, so rolling an old entry off doesn't force a `date_updated` bump.
- If you genuinely can't write a specific delta, that's a signal the edit was too small to be worth an entry — or that you don't actually know what you changed. Both are worth stopping for.

---

## 7. Skill Catalog — One Line Each

`CLAUDE.md` groups the eleven shipped skills by rhythm and lists their trigger phrases only; the authoritative triggers always live in each skill's own `SKILL.md` frontmatter `description`. The purposes are here.

**Rhythms**

- **`daily-briefing`** — *"brief me" / "what's today".* Delta-first, actionable briefing for today: this week's top priorities, next-actions that are new or changed since yesterday, carryovers, and today's read from the rolling queue. Writes `raw/briefings/YYYY-MM-DD.md`. Vault-only unless you wire in the optional calendar extension point.
- **`weekly-digest`** — *"weekly digest" / "what's new in the wiki".* Forward-looking summary of wiki changes since the last digest, with a time-budgeted Read-First plan. Maintains `raw/briefings/reading-queue.md`, which `daily-briefing` reads from.
- **`weekly-reread`** — *"weekly reread" / "weekly drill".* Backward re-read over the past 7 days of raw notes: lists new entries, surfaces 3-5 live fragments, asks case-contrast questions, proposes promotions into `wiki/`.

**Getting things in**

- **`bookmark-process`** — *"process bookmark 3".* Per-item actuator for `raw/bookmarks.md`: fetch the URL, propose light vs deep treatment, write the output, strike the checkbox, commit. One bookmark per invocation.
- **`source-sync`** — *"sync <corpus>" / "pull new transcripts".* Imports an external corpus into `raw/` with content-based dedup and drift detection. Copy-new-only plus report-drift by default; replacing a drifted file is an explicit follow-on.
- **`batch-ingest`** — *"drain the import backlog".* Drains `raw/notes-import/` in chunks, each handled by a fresh subagent in a disposable git worktree, with resume state in `wiki/notes-import-manifest.md`.
- **`storm-research`** — *"STORM research on <X>" / "research <X> from 5 angles".* Multi-perspective scan → contradiction map → synthesis → peer review, written to `raw/research/`. Reasoning-driven, not web-fetch-driven.

**Keeping it honest**

- **`auto-review`** — *"review before commit" / "did I fabricate anything".* Dispatches a fresh read-only subagent to review a staged wiki diff for fabrication, weak provenance, over-promotion and weak deltas. The judgment layer above the mechanical gates — it does not replace them.
- **`backlog`** — *"park this" / "sweep the backlog" / "what's still open".* Capture-and-sweep for `wiki/backlog.md`; the cross-session memory for deferred wiki work.
- **`tighten-prose`** — *"tighten this" / "cut the clutter".* Voice-agnostic craft pass on any prose: cuts clutter and jargon without flattening voice, and finds the missing "I".
- **`design-principles`** — *"extract design principles from <X>" / "design review of <artifact>".* Mines technical sources into a catalog page, then applies that catalog as a severity-tagged review checklist against a design artifact.

**Keep this list and `CLAUDE.md`'s grouped list in step with `.claude/skills/`.** A catalog that names a skill you deleted is worse than no catalog: the LLM will try to invoke it, fail, and improvise the workflow by hand — which is the exact failure the skills exist to prevent.
