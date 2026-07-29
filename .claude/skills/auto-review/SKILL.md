---
name: auto-review
description: Use before committing any wiki change — as the pre-commit content-review step of an ingest / lint / edit pass, or directly when the vault owner says "auto-review", "AR this", "review before commit", "fresh-eyes review", "did I fabricate anything". Dispatches a FRESH read-only subagent to review the pending wiki diff — staged and unstaged — against the wiki's content invariants (fabrication, provenance substance, over-promotion, Recent-Updates delta quality, voice, duplication) — the judgment layer above the mechanical CI gates — returns severity-tagged findings, the main agent fixes CRITICAL/HIGH, then re-reviews in a new context until a round is clean (max 3 rounds). Adapted from Peter Steinberger's "AutoReview". Content review only — does NOT replace the CI gates (markdownlint-obsidian + wiki-lint.py + index drift), which run after.
---

# Auto Review

A fresh-context review of a wiki diff **before commit**. The session that wrote the pages cannot review them with fresh eyes — as Peter Steinberger put it in his Microsoft Build talk on agent loops, *"look at the code with fresh eyes: good luck with that; context doesn't work that way."* So the reviewer is a **separate subagent with its own context**, the maker (this session) stays away from the checker, and the loop runs until clean or it hits a hard stop.

This is the **content / judgment** layer. It sits *above* the mechanical CI gates (markdownlint-obsidian + `wiki-lint.py` + the index-drift check, plus `check-date-updated.py` in CI), which catch structure, links, and frontmatter keys. AutoReview catches what they cannot: a fabricated claim, a weak Recent-Updates delta, an over-promoted entity, a voice slip, a duplicate of an existing page. **It does not replace the gates** — the gates still run after.

## When to use

- As the pre-commit step of any ingest / lint / edit pass. Run it once the pass's wiki writes are complete — i.e. after the index regen, CLAUDE.md §Workflows → Ingest step 9 — and **before** the Wiki Lint Pipeline (§Workflows.6) and the commit. This skill *is* Ingest step 10.
- Directly, on demand: "auto-review", "AR this", "review before commit", "fresh-eyes review", "did I fabricate anything?"
- **Skip** when the only changes are to `raw/` (immutable source — nothing to synthesis-review), a mechanical index regen, or a callout-only trim. Say so in one line rather than spinning up a subagent for nothing.

## Steps

### 1. Scope the diff

Gather exactly what changed this pass — nothing else:

```bash
git diff --stat HEAD            # staged + unstaged vs HEAD
git status --short              # catch untracked NEW wiki pages
```

Build the review set = changed/new files under `wiki/` **plus** any raw file a source page was synthesised from (`raw/web-clippings/…`, `raw/books/…`, `raw/meetings/…`, `raw/notes-import/…`). The reviewer needs the raw in context to check fidelity — without it, dimension 1 below degrades into a vibe check.

Exclude from the set: pure-`raw/` edits (immutable, nothing to review), `wiki/index.md` (mechanically regenerated), and the Layer-1 carve-outs (`backlog.md`, `glossary.md`, `log.md`) for *structure* — but still review their **content** if you authored prose there this pass.

If the set is empty → report "nothing to review" and stop.

### 2. Dispatch a FRESH reviewer subagent

Spawn **one read-only subagent** (`Explore` or `general-purpose`) per round — a new context each time. Pass it: (a) the review set as file paths, (b) the raw source(s) for fidelity-checking, (c) the **review contract** below verbatim. The subagent reads the files itself and returns findings; it does **not** edit. Keeping the checker in a separate context is the whole point — do not "review" in this session.

**Review contract (paste into the subagent prompt):**

> You are a fresh-eyes reviewer for an Obsidian knowledge wiki — an LLM-maintained second brain owned by one person, where `raw/` holds immutable sources and `wiki/` holds synthesis. Review ONLY the listed files. Return findings as a list, each tagged `CRITICAL` / `HIGH` / `MEDIUM` / `LOW`, with `file:line` and a one-line fix. If a dimension is clean, say so. Do not edit anything.
>
> **Check these (the mechanical CI gates already cover links / frontmatter-keys / index — do NOT duplicate them):**
>
> 1. **Fabrication / accuracy (CRITICAL).** Every specific in a source page — number, date, name, quote — must trace to the raw source provided. Flag invented specifics, quotes that aren't verbatim, and synthesis that contradicts the raw. Classic failure mode: a claim lifted from a source's blurb, subtitle, thumbnail caption, or promotional summary, written up as though the source itself said it.
> 2. **Provenance substance (HIGH).** Source pages: a real *body* wikilink back to `[[raw/...]]`, not just the `raw_sources:` frontmatter (frontmatter isn't clickable in Obsidian). Synthesis pages: claims cite `[[wiki/sources/...]]`, not raw. Is the page citing the *right* source, or a convenient one?
> 3. **Over-promotion (HIGH).** A new entity or topic minted for a passing mention? An entity created off a single source without that source being about it (second-source gate)? Flag it — the fix is usually a line on an existing page, not a new page.
> 4. **Recent-Updates delta quality (HIGH).** On insight / topic / plan / project pages: is the top delta line specific enough that the owner can decide whether to re-read? "Updated" / "Minor edits" / "Refactor" = fail; name what actually changed. Judge the *wording* only. Whether the callout exists, is dated, is ordered newest-first and holds at most 3 entries is format, not judgment — `RU001`-`RU004` in `wiki-lint.py` and the CLAUDE.md callout spec own that.
> 5. **Voice (MEDIUM).** The vault's native vocabulary leads; imported framework terms follow — in a translation table the left column is the native term, the right column the imported one, and body prose introduces the concept natively before naming the imported register. Any translation table carries a "why hold both registers" paragraph (which audience hears which register, what each carries that the other undersells) — a bare two-column table is decorative. Tactical additions name a concrete surface (which team, which cadence, which timing anchor); a bullet that reads as a generic tip has not earned its place. Flag only violations of conventions actually documented in CLAUDE.md or the vault's style notes — e.g. if the vault has adopted "no comma before *but*", flag the comma; do not invent style rules that aren't written down.
> 6. **Duplication / contradiction (MEDIUM).** Does a new page duplicate or contradict content that should have updated an existing page instead?
> 7. **Glossary discipline (MEDIUM).** A newly-named acronym or framework in synthesis prose → a one-liner added to the right split file: `wiki/glossary/frameworks.md` for frameworks / methodologies / acronyms, `wiki/glossary/vernacular.md` for the vault's in-house terms. Never `wiki/glossary.md` directly (thin landing page).
> 8. **Cross-referencing (LOW).** Entities and topics mentioned are wikilinked; the source page links to the entities/topics it contains; those pages link back.
>
> **Do NOT flag:** broken wikilinks or anchors, missing required frontmatter keys, index drift, Recent-updates callout presence / dating / ordering / entry count, markdownlint nits (the gates and the callout spec own these); `raw/` files being unpolished (raw is immutable); `wiki/projects/` "Related sources" linking raw (explicitly allowed); stylistic preferences not in the documented voice rules.

### 3. Triage + fix

- **CRITICAL** (fabrication, a claim the raw doesn't support) → fix before any commit, always.
- **HIGH** (provenance, over-promotion, weak delta) → fix before commit.
- **MEDIUM** → fix if cheap; otherwise surface to the vault owner with the finding.
- **LOW** → note in the report; fix opportunistically.

Apply fixes in **this** session (the maker fixes; the checker only finds).

### 4. Re-review in a new context (loop, with a hard stop)

After fixing, **dispatch a new subagent** — fresh context again — over the changed set. Repeat until a round returns **no new CRITICAL/HIGH**, or you hit **3 rounds**, whichever comes first.

The hard stop is deliberate. Every serious write-up on agent loops converges on the same three controls: a **max-iteration count**, **no-progress detection**, and a **budget ceiling**. The loop is the expensive part of an agent, and an unbounded review loop will happily spend a whole context window relitigating MEDIUMs. If round 3 still has open CRITICAL/HIGH, **stop and escalate to the vault owner** — don't keep burning rounds.

### 5. Hand back to the CI gates

AutoReview clean is not done. Run the mechanical gates next (CLAUDE.md §Workflows.6 Wiki Lint Pipeline):

```bash
npx markdownlint-obsidian-cli@1.1.0 "wiki/**/*.md" --vault-root wiki   # bunx works too; never --bun
python3 .claude/scripts/wiki-lint.py wiki/
python3 .claude/scripts/regenerate-index.py --check
```

Then commit. AutoReview is the content floor; the gates are the structural floor — both must pass. If the diff can't be made clean, abort the pass rather than landing a half-state.

## Rules

- **Fresh context per round, always.** Reviewing in the authoring session defeats the purpose. One subagent per round, read-only.
- **Content layer only.** Never re-implement the CI gates here; never skip them after. They are complementary, not redundant.
- **The maker fixes, the checker finds.** The subagent returns findings and edits nothing; this session applies the fixes. Keeps the diff attributable.
- **Hard stop at 3 rounds.** No progress, or round cap → escalate, don't loop.
- **CRITICAL fabrication is non-negotiable.** Never commit a claim the raw source doesn't support, even if everything else is clean.
- **Tune, don't suppress.** If the reviewer false-positives on a real vault convention (a carve-out, an allowed raw-link), add that convention to the "Do NOT flag" list in the contract — *explain the agent the conditions* — rather than dropping the whole dimension.
- **Never push from this skill.** It reviews and fixes; committing and pushing belong to the calling workflow.

## Common mistakes

- **Reviewing in-session.** The most tempting and most useless — same context, no fresh eyes. Always spawn the subagent.
- **Treating it as a replacement for the CI gates.** It's the layer above; the gates still run after.
- **Dispatching the reviewer without the raw source.** Fidelity-checking with no receipt to check against turns dimension 1 into a plausibility judgement, which is exactly the failure it exists to catch.
- **Looping past the hard stop.** Three rounds, then escalate.
- **Over-flagging mechanical nits.** Broken links / missing keys / index drift belong to the gates; if the reviewer keeps surfacing them, tighten the "Do NOT flag" list instead of ignoring the round.
- **Letting the checker edit.** It finds; the maker fixes.
- **Running it on a pure-`raw/` diff.** Nothing to synthesis-review — say so in one line and skip.

## Iteration log

- **v1** — initial version, adapted from Peter Steinberger's "AutoReview" (from his Microsoft Build talk: *"if you take two ideas, take AutoReview and Crabbox"*), ported from a code repo to this wiki vault. Steinberger's mechanism is one line in the agent instructions — the agent self-reviews in a fresh context, over many rounds, before commit or PR. The vault adaptation keeps the three load-bearing pieces — **fresh context** (a separate subagent), **multiple rounds** (with a hard stop), **tuned invariants** (an explicit "Do NOT flag" list so the reviewer doesn't fight real conventions) — and re-points the review dimensions from "bugs / security" to the vault's content floor: fabrication, provenance, over-promotion, delta quality, voice, duplication, glossary discipline, cross-referencing. Positioned explicitly as the content layer *above* the mechanical CI gates, not a replacement, and wired into the Ingest workflow as the content-review step that runs before those gates.
