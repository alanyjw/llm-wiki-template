---
name: design-principles
description: Use when the vault owner says "extract design principles from <source>", "mine <X> for design principles", "what can I learn from <X> for system design", "design review of <artifact>", "review this system design", "run the design principles against <doc>", "principles review of <X>", "extract design principles from these <N> sources", or "curate / dedup / section the design-principles catalog". Two modes — *extract* mines one source (or a named batch of sources, via parallel drafters then central dedup then one confirmation) for transferable system-design principles into the wiki catalog page `wiki/topics/system-design-principles.md`; *review* applies the catalog as a checklist against any design artifact (a spec, a proposal, a `wiki/projects/` page, or pasted text), producing a severity-tagged findings report. A *curate* maintenance sub-mode merges near-duplicates, renumbers, and sections the catalog by domain. Catalog-grounded — it answers "what does my accumulated reading say about this design", not "what would a generic reviewer say".
---

# Design Principles

Two-mode skill that turns accumulated technical reading into a compounding
design-review lens. *Extract* mode mines a technical source — one at a time, or
a named batch — for transferable principles and files them as structured entries
in `wiki/topics/system-design-principles.md`. *Review* mode reads the catalog
(whole, or filtered to relevant domains) and applies it to any design artifact,
emitting a severity-tagged findings report. A *curate* maintenance sub-mode keeps
the growing catalog tractable — merges near-duplicates, renumbers, and sections
by domain.

The catalog is one page. Every mode touches the same page. Review reads it whole
by default; past roughly 100 entries it may filter to the domains the artifact
actually reaches (the catalog is sectioned by `## Domain:` headers — see
*Curate*). Whole-read is the right call while the catalog is small; once it
isn't, scope the read.

## When to use

**Extract mode** — the vault owner says:

- "extract design principles from <source>"
- "mine <X> for design principles"
- "add design principles from <X>"
- "what design principles can I draw from <X>"
- "extract design principles from these <N> sources" / names several clippings at once → **batch extract** (see Mode 1)

**Review mode** — the vault owner says:

- "design review of <artifact>"
- "review this system design"
- "run the design principles against <doc>"
- "principles review of <X>"

**Curate sub-mode** — the vault owner says:

- "curate the design-principles catalog"
- "dedup the catalog" / "merge the duplicate principles"
- "section the catalog by domain"

**Distinct from generic review.** This skill is catalog-grounded. It does not ask
"is this design any good" in the abstract — it asks *what does my accumulated
reading say about this design*. Generic engineering critique (data flow, edge
cases, test coverage, performance modeling that the catalog doesn't reach) and
scope critique ("is this ambitious enough?") are out of scope; say so in the
report's closing frame rather than improvising them.

**Refuse / re-route** when:

- The vault owner says "process all sources" / "every clipping" with no list — refuse, ask them to name the set. Batch extract works on an **explicit, bounded list of named sources**, not an unbounded sweep of the corpus.
- The catalog page is missing — tell them, don't auto-create. Seeding is a one-off setup step, not something a run does silently.
- The source has no design substance (a personal essay, a meeting note, a book of narrative history) — say so, don't fabricate principles.

## Mode dispatch

Pick the mode from the trigger phrase:

- One source named → **extract** (single).
- Several sources named, or "these N clippings" → **extract** (batch).
- An artifact to judge → **review**.
- "curate / dedup / section the catalog" → **curate**.

If the skill is invoked bare, ask one disambiguating question:

> "Extract design principles from a source (or batch), review an artifact, or curate the catalog?"

Then proceed. Never guess.

## Mode 1 — Extract

### Steps

1. **Resolve the source.** Accept any of: a `raw/web-clippings/` path; a slug
   (resolve to the file); "the last clipping" (most-recently-modified file in
   `raw/web-clippings/`); a `raw/books/` path; a `raw/notes-import/` path;
   pasted content. If ambiguous, ask one question; don't guess.

2. **Read the source fully.** No truncation — technical clippings rarely exceed
   sensible limits, and a principle extracted from a summary is a principle
   extracted from someone else's compression.

3. **Substance check.** If the source carries no design substance (narrative
   essay, meeting minutes, personal reflection), state so plainly and stop.
   **Never fabricate principles** from a source that doesn't contain them.

4. **Draft 5-12 candidate principles.** Each must be:
   - **Transferable** — applies beyond the source's specific tech, framework, or domain.
   - **Actionable** — a future design could honor or violate it.
   - **Atomic** — one idea per principle, not a paragraph of related ideas.

5. **Dedup against the catalog.** Read `wiki/topics/system-design-principles.md`.
   For each candidate:
   - Overlaps an existing entry → propose **merge** (add the new source to the existing entry's `Source:` list) or **drop**; the vault owner picks.
   - Novel → keep.

6. **Present candidates.** Numbered list, each entry showing the proposed title
   plus Principle / Applies when / Tags. The vault owner keeps, edits, or drops
   per entry. **No write before they confirm.**

7. **Append confirmed entries.** Read the catalog's max `P-NNN`, increment per
   entry, append as **H3** blocks (`### P-NNN · <title>`) under the right
   `## Domain:` H2, in `P-NNN` order within that domain. The nesting is
   load-bearing — review mode's by-domain scoping reads a `## Domain:` section
   and everything under it, so an entry written at H2 ends the section it was
   meant to sit inside and drops out of every scoped read. If a confirmed entry
   belongs to no existing domain, open a new `## Domain:` H2 for it rather than
   leaving it flat.

8. **Update the Recent-updates callout** at the top of the catalog page. Add a
   new top entry like `**YYYY-MM-DD** — Extracted P-NNN..P-MMM from <source>`.
   Roll the oldest off if the callout exceeds 3 entries.

9. **Update frontmatter.** Increment `source_count` if this is a novel source.
   Bump `date_updated` to today — the CI gate `FM007` fails a body change with a
   stale `date_updated`, and it only runs in CI, so it won't catch you locally.

10. **Reindex.** Run `qmd update && qmd embed` so the catalog's new content is
    searchable (`wiki` collection). Without `embed`, `lex` finds the new entries
    and `vec`/`hyde` silently miss them.

11. **Lint gate.** Run the three local CI gates before committing. If any error,
    fix it; if it cannot be fixed cleanly, abort the run rather than commit a
    half-state:
    1. **Layer 1 — `markdownlint-obsidian`**: `npx markdownlint-obsidian-cli@1.1.0 "wiki/**/*.md" --vault-root wiki`. Catches nested-list indent (`MD007`), spaces after list markers (`MD030`), spaces after blockquote `>` (`MD027`), and frontmatter tag format (`OFM087` — a bare year must be quoted). `bunx` works identically if you have Bun; **never add `--bun`** — the transitive `markdown-flavor-detection` dependency ships no `src/`, so `--bun` resolves its `bun` export condition to an unpublished file and the run dies.
    2. **Layer 2 — `wiki-lint.py`**: `python3 .claude/scripts/wiki-lint.py wiki/`. Catches table-pipe-in-wikilink, broken wikilinks including `#anchor` resolution, and per-type frontmatter schema — `type: topic` hard-requires `title`; `source_count` and `tags` are recommended keys the soft `FM006` warning tracks, so never invent a count to silence it. The rules this skill trips most:
       - `RU001`/`RU002`/`RU003` — the Recent-updates callout must exist, carry a dated entry, and have a newest date not older than `date_updated`. Steps 8 and 9 write exactly what these police, so do them together.
       - `WIKI007` — anchor-prose source-count mismatch on topic pages. If step 9 bumps `source_count`, the prose sentence on the catalog page that states the count has to move with it, or frontmatter and prose disagree.
       - `PROV001` — direct `[[raw/...]]` links in a synthesis page. The catalog is a topic page, so `Source:` must point at `[[sources/...]]` or be plain-text attribution, never at raw.
    3. **Index drift**: `python3 .claude/scripts/regenerate-index.py --check`. An extract run appends to an existing page, so this normally passes untouched; it fails if the catalog page is being created for the first time, or if a source page was created alongside. Fix by running the script without `--check` and replacing its `NEW - describe` placeholder with a real one-line description.

12. **Log + commit.**
    - Append to `wiki/log.md` (newest-first, after the top `---`): `## [YYYY-MM-DD] design-principles | extract from <source> — N added (P-NNN..P-MMM), M merged`.
    - Stage only the catalog plus `wiki/log.md` (and `wiki/index.md` if `source_count` changed the count). Commit message: `wiki: extract design principles from <source> (P-NNN..P-MMM)`.
    - **Never push.**

### Batch extract (multiple named sources)

When several sources are named at once ("extract from these 6 clippings"), run
the same pipeline fanned out, with a **single** confirmation gate and a
**single** append — never N separate confirmations or N commits. This is the
right pattern for draining a backlog of unmined clippings.

1. **Resolve the set.** An explicit, bounded list of named sources (paths,
   slugs, "the last 6 clippings"). Not an unbounded "all sources" sweep — see
   *Refuse / re-route*. Substance-check each; drop any with no design substance
   and say which.

2. **Fan out drafters.** Launch one drafter subagent per source (in parallel),
   each producing that source's 5-12 candidate principles per the single-source
   rules (steps 3-4). Drafters draft only — they do not read each other's output
   and they do not write.

3. **Central dedup — two passes.** Collect all drafts. Dedup (a) **against the
   catalog** (step 5, run once over the merged set) and (b) **across sources** —
   two sources in one batch often surface the same principle; merge those into a
   single candidate carrying both `Source:` links rather than two near-identical
   entries. The cross-source pass is what stops a batch from inflating the
   catalog.

4. **One consolidated confirmation.** Present the full deduped candidate set in a
   single numbered list, grouped by source, with merges flagged. The vault owner
   keeps, edits, or drops per entry. **No write before they confirm** — the gate
   holds for batches exactly as for single runs.

5. **Single append, single reindex, single commit.** Assign `P-NNN` across the
   whole confirmed set in one monotonic run, append once, update the callout once
   (`Batch extract from N sources: P-NNN..P-MMM (K new) + J merges`), bump
   `source_count` by the count of *novel* sources, run `qmd update && qmd embed`
   once, run the three lint gates once, log once, commit once.

**Caps for batch:** keep a run to a sane set (roughly 3-8 sources). Beyond that,
split into multiple batch runs — the consolidated confirmation becomes unreadable
and a too-large append is impossible to review in one pass.

### Edge cases

- **All candidates duplicate existing entries** → report "nothing new". Offer to strengthen existing entries by adding the source to their `Source:` list. If declined, stop with no commit.
- **Source already in the catalog** (some entry's `Source:` already points at it) → warn before extracting; re-mining needs an explicit confirm.
- **Catalog missing or empty** → say so and stop. Don't auto-create — seeding is a setup step.

## Mode 1b — Curate (maintenance)

A periodic maintenance pass that keeps the catalog tractable as it grows.
Triggered explicitly ("curate / dedup / section the catalog"), never auto-run.

The trigger point matters more than it looks. Append-only growth gives no natural
stopping signal — no run ever ends with the catalog feeling too long, because each
run only ever adds a handful of entries to a page nobody reads end to end. So a
"revisit at roughly 50 entries" rule is a reminder to go and count, not a threshold
you will feel arrive. Check the entry count deliberately rather than waiting for
the catalog to complain.

### Steps

1. **Read the full catalog.** Note the current max `P-NNN`, the entry count, and
   which entries already sit as H3s under a `## Domain:` H2 versus which are
   still flat or mis-levelled at H2.

2. **Detect near-duplicates.** Two signals, and you need both:
   (a) run `python3 .claude/scripts/wiki-lint.py wiki/ --report duplicates` —
   lexical Jaccard near-dup pairs, catalog-wide and page-level, so treat it as a
   pointer rather than a verdict; and
   (b) read for *semantic* overlap within and across domains. The canonical case
   is a cluster of performance-budget principles extracted months apart from
   different sources, each phrased differently, all saying "set a number and
   defend it" — lexical similarity is low, semantic overlap is total.
   Produce a candidate merge list: pairs and clusters that say the same thing.

3. **Propose merges.** For each cluster: which `P-NNN` survives, which fold in,
   and the consolidated `Source:` list (the union of the merged entries' sources
   — merges *strengthen* provenance, they never drop a source). **No edit before
   confirmation** — the same hard gate as extract.

4. **Merge and renumber.** Fold confirmed duplicates into the surviving entry
   (union the sources, keep the sharpest wording). Renumbering is
   **append-stable**: prefer keeping IDs and leaving a one-line
   `*(merged into P-NNN YYYY-MM-DD)*` tombstone over re-sequencing the whole
   catalog, so existing review reports and log references don't rot. Full
   re-sequence only on an explicit request.

5. **Section by domain.** Put every entry at H3 under exactly one
   `## Domain: <name>` H2, ordered within a domain by `P-NNN`. Demote any entry
   still sitting at H2 — at that level it isn't inside a domain section at all,
   it *ends* one. Finish the job: a half-sectioned catalog is worse than a flat
   one, because review mode scoping silently misses whatever is still loose.
   This nesting is what lets review mode load a subset.

6. **Update the callout and frontmatter.** Recent-updates top entry:
   `**YYYY-MM-DD** — Curate: merged K pairs, sectioned into D domains`.
   `source_count` is unchanged by a curate pass (no new sources). Bump
   `date_updated`.

7. **Reindex, lint, log, commit.** As extract steps 10-12: `qmd update && qmd
   embed`, the three lint gates, one log line (`design-principles | curate — K
   merges, D domains`), one commit (`wiki: curate design-principles catalog — K
   merges, D domains`). **Never push.**

### Curate edge cases

- **No real duplicates** → say so; sectioning alone may still be worth doing. Don't manufacture merges to justify the run.
- **Ambiguous merge** (two entries overlap but each carries a distinct clause) → keep both, don't force. Note the near-overlap in the report and leave the call to the vault owner.

## Mode 2 — Review

### Steps

1. **Resolve the artifact.** Accept a file path (a spec or design doc anywhere in
   the repo, `raw/projects/*.md`, `wiki/projects/*.md`, any markdown design doc)
   or pasted text. Normalize to text. If ambiguous, ask one question.

2. **Read the catalog — whole, or by domain.** `wiki/topics/system-design-principles.md`.
   Default is whole-read. Optionally scope: if the artifact's domain is obvious
   (a responsive-CSS spec, a backend-reliability proposal) and the catalog is
   large, read only the relevant `## Domain:` sections — but **state the scope in
   the report** ("reviewed against Data and State Architecture plus Performance
   and Latency; skipped Interfaces and Reliability as out-of-domain") so a missed
   cross-domain principle is visible rather than silent. When in doubt, read
   whole.

3. **Read the artifact in full.**

4. **Filter by relevance.** For each in-scope catalog principle, use its
   `Applies when:` field as the relevance filter. Drop principles that don't
   apply — they do not appear in the report at all. Keep the report focused.

5. **Verdict per relevant principle.** One of:
   - **Honored** — the artifact's design honors the principle. Cite the artifact passage that shows it.
   - **Violated** — the artifact's design contradicts the principle. Cite the conflict.
   - **Gap** — the principle applies but the artifact is silent on it. Surface the missing decision.

6. **Severity per non-Honored finding:**
   - **Critical** — violation of a foundational principle that is hard to retrofit (P-001, source-of-truth inversion, is day-one or never).
   - **High** — violation that is fixable but expensive once shipped.
   - **Medium** — violation that is cheap to fix during design.
   - **Note** — gap or commentary, no action required.

   *Honored* findings carry no severity — they are encouragement, and they belong
   at the bottom of the table.

7. **Recommendation per non-Honored finding.** A concrete, artifact-specific
   action. Not "consider local-first" but *"the Mutations section should specify
   whether writes go to a local queue before the server — as written it implies a
   synchronous server round-trip on every keystroke."* Every recommendation cites
   an artifact passage.

8. **Emit the report inline.** Two parts:
   - **Summary table:** `Principle | Verdict | Severity`, one row per relevant principle, severity-ordered (Critical → Note), Honored rows at the bottom.
   - **Detailed findings:** one block per non-Honored finding, severity-ordered. Each block carries the principle ID and title, the verdict, the severity, the artifact passage being judged (one or two short pull-quotes, no more), and the recommendation.

9. **Closing frame.** Restate that this is the catalog-grounded lens: the findings
   are bounded by what has been extracted so far, and a clean report means "no
   catalogued principle is violated", not "this design is good". Name what the
   review did *not* cover — generic architecture critique, test strategy,
   performance modeling beyond the catalog, and whether the scope is the right
   scope.

10. **Offer to persist.** Ask whether to save the report to
    `raw/projects/{artifact-slug}-design-review-{YYYY-MM-DD}.md`. Default: yes
    for on-disk spec and `wiki/projects/*` artifacts (their reviews deserve
    receipts); ask for pasted-text artifacts, since the artifact itself isn't on
    disk to point back at.

11. **If persisted:** append to `wiki/log.md` and commit. The catalog was not
    touched, so the commit covers the report file plus `wiki/log.md` only.
    Message: `raw: design-principles review of <artifact> → raw/projects/{slug}-design-review-{date}.md`.
    Run `qmd update && qmd embed` — `raw/projects/` is an indexed collection
    (`projects`). **Never push.**

### Edge cases

- **Catalog too short to be useful** (fewer than roughly 10 principles, or still only the shipped seed entries) → run the review anyway, but say plainly in the report that the lens is thin: a clean result mostly means the catalog hasn't been fed yet. Recommend extracting from a few more technical sources first.
- **No principles apply** (everything filters to N/A) → say so plainly. Don't fabricate findings. The honest read is that the catalog's coverage doesn't yet reach this artifact's domain — which is itself a useful signal about what to read next.
- **Artifact carries no design substance** (accidentally pointed at a meeting note) → say so and stop. Don't review.
- **Artifact references the catalog itself** → decline. Self-review is out of scope.

## Shared rules (all modes)

- **Wikilink hygiene.** A new `Source:` wikilink must point at a file that exists. Verify before writing; if the target is missing, ask. A broken wikilink is a hard lint failure (`WIKI002`), not a cosmetic one.
- **Provenance.** Every principle carries at least one `Source:`. No source-less principles. Prefer `[[sources/<slug>]]` over raw links — the catalog is a synthesis page and `PROV001` flags `[[raw/...]]`.
- **Voice.** Catalog prose is third-person and instructional; it's a reference. Principles state, they don't suggest. Review reports use the register you'd use with a peer engineer — direct, specific, no hedge-words.
- **No fabrication.** Extract refuses when the source lacks design substance. Review refuses to invent verdicts that aren't grounded in the artifact text.

## Catalog schema (reference)

```markdown
## Domain: <name>

### P-NNN · <short memorable title — 8 words or fewer>

**Principle:** <one paragraph, 60 words or fewer, transferable beyond the
source's specific tech, actionable, atomic.>

**Applies when:** <semicolon-separated clauses; the filter review mode uses.>

**Source:** [[sources/<slug>]]

**Tags:** <2-5 lowercase-hyphen topical tags, comma-separated.>
```

- **Heading levels:** domains are H2 (`## Domain: <name>`), entries are H3 (`### P-NNN · …`) beneath them. An entry written at H2 terminates its domain section and disappears from any by-domain read.
- **ID:** `P-NNN`, monotonic, zero-padded to three digits. Read the catalog's max and increment.
- **Source:** can hold several wikilinks after a merge — that union is the strengthening signal.
- **Tags** here are the catalog's own topical vocabulary (`architecture`, `latency`, `api-design`, …). They are *not* the vault's frontmatter tag taxonomy in CLAUDE.md — that one governs the page's YAML, this one governs entries inside the page. Don't conflate them.

## Caps

| Item | Cap |
|---|---|
| Sources per extract run | 1 (single) · roughly 3-8 (batch; split beyond) |
| Candidate principles surfaced per source | 5-12 |
| Confirmation gates per run (single or batch) | 1 |
| Commits per run (single, batch, or curate) | 1 |
| Files touched per extract run | 3 or fewer (catalog + log + occasionally index) |
| Files touched per review run (persisted) | 2 or fewer (report + log) |
| Artifacts per review run | 1 |

## Common mistakes

- **Fabricating principles** when the source has no design substance — refuse the run instead.
- **Restating existing entries** as "new" principles — extract step 5 dedups *before* the write, not after.
- **Auto-appending without confirmation** — extract step 6 is a hard gate, for batches as much as for singles.
- **Running N confirmations for a batch of N sources.** The whole point of the batch path is one gate, one append, one commit. N gates is just the single path run N times, and it loses the cross-source dedup.
- **Skipping the cross-source dedup pass** in a batch. Deduping only against the catalog lets two sources in the same batch each contribute their own version of the same principle — the catalog inflates and the duplicate is invisible until the next curate pass.
- **Generic recommendations** ("consider X") in review reports — every recommendation must cite an artifact passage and propose a concrete change.
- **Reporting principles that filtered to N/A.** The `Applies when:` filter exists so the report is short. A review that lists every catalog entry with "not applicable" is noise.
- **Scoping the catalog read without saying so.** If review mode read three domains out of six, the report says which three. A silent scope makes a missed cross-domain violation look like a clean bill of health.
- **Editing the catalog by hand** to add a principle — go through the skill so dedup, ID assignment, callout rotation, and the qmd reindex all happen.
- **Writing an entry at H2.** Entries are `### P-NNN`, domains are `## Domain:`. An entry at H2 closes the domain section above it, so every by-domain read silently loses it *and* everything after it in that domain.
- **Forgetting to bump `date_updated`** on the catalog page. `FM007` runs in CI only, so a stale date passes locally and fails the PR.
- **Bumping `source_count` without touching the prose that states it.** The catalog page says its own count in words; move both together or `WIKI007` flags the disagreement.
- **Adding `--bun` to the Layer 1 command.** It looks like a speedup and is a hard crash — see step 11.
- **Skipping `qmd embed` after the append** — `lex` still finds the new entries, which masks the bug; `vec` and `hyde` silently miss them.
- **Pushing the commit.** Never push from this skill.

## Iteration log

- **v1** — initial version. Two modes (`extract` / `review`) sharing one catalog
  page `wiki/topics/system-design-principles.md`. Catalog schema: `P-NNN` IDs
  with `Principle / Applies when / Source / Tags`. Seeded with a handful of
  principles drawn from public technical writing as worked examples of the
  format. Review mode positioned as a catalog-grounded lens rather than generic
  engineering critique. Deferred: the `curate` sub-mode (revisit when the catalog
  passes roughly 50 entries) and auto-chaining from `bookmark-process`.
- **v2** — encoded the growth patterns a one-source-at-a-time design leaves out.
  (1) **Batch extract** — multiple named sources via parallel drafters, then a
  central two-pass dedup (against the catalog *and* across sources), then one
  consolidated confirmation, then a single append and commit. Draining a backlog
  of unmined clippings as N separate single-source runs costs N confirmations and
  N commits, and — worse — lets two clippings in the same backlog each contribute
  their own phrasing of the same principle, because nothing ever compares them to
  each other. The cross-source dedup pass is the part that only the batch path
  can do. The 1-source hard cap lifted to a roughly 3-8 batch range; "process all
  sources" with no list is still refused.
  (2) **Curate sub-mode** (Mode 1b) — a catalog that only ever grows never signals
  that it needs pruning, so "revisit past roughly 50 entries" has to be a
  deliberate check rather than a felt threshold. Detect near-dups (lexical
  `--report duplicates` plus a semantic read), gate merges on confirmation,
  renumber append-stably with tombstones, union provenance on merge, and finish
  the by-domain sectioning.
  (3) **Review scoping** — optional by-domain catalog read once the catalog is
  large, with the scope stated in the report so skipped domains are visible
  rather than silent.
