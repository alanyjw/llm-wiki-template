---
name: storm-research
description: Use when the vault owner says "STORM research on <topic>", "run STORM on <X>", "multi-perspective research on <X>", "research <X> from 5 angles", "STORM this", or wants a structured multi-perspective reasoning pass on a topic. Runs the Stanford STORM 4-phase workflow (multi-perspective scan -> contradiction map -> synthesis -> peer review) in one invocation, adapts the personas to the topic, optionally grounds them in the vault via qmd, writes a briefing artifact to raw/research/, and offers an HTML visualisation (perspective cards, contradiction map, confidence bars) to docs/visualisations/. Reasoning-method-driven, not web-fetch-driven — runs with or without web access. The executable form of prompts/storm-research.md.
---

# STORM Research

Run the **STORM** method (Stanford OVAL, *Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking*, NAACL 2024) as a single orchestrated pass. Instead of one prompt giving the majority view, STORM simulates five expert perspectives, maps where they disagree, synthesises, then peer-reviews its own output to catch its known weaknesses (source bias, fact misassociation). Stanford measured multi-perspective output as ~25% more organised and ~10% broader than single-prompt research.

The literal prompt text is in [`prompts/storm-research.md`](../../../prompts/storm-research.md) (the paste-anywhere copy, single source of truth for the wording). This skill *executes* those four phases and adds the things a static block can't: persona adaptation, vault grounding, and filing.

## When to use

- The vault owner says "STORM research on <topic>", "run STORM on <X>", "multi-perspective research on <X>", "research <X> from 5 angles", "STORM this".
- Any topic where the majority view isn't enough and a blind spot would be costly — an architecture or vendor decision, a proposal or report you're about to write, learning a new domain, a people/leadership question.

**What this is and isn't.** STORM is a *reasoning* method, not a web-fetch harness. It produces structured multi-perspective reasoning from the model's knowledge plus whatever the vault already holds — it runs fine with no web access at all. If web tools *are* available, they complement STORM rather than replace it: use them to verify the specific low-confidence claims Phase 4 flags, never to pad the briefing with citations STORM didn't actually reason from.

## Steps

### 1. Resolve topic + actor role

Get the `<topic>`. Note the `[YOUR ROLE]` for Phase 3's actionable insight — default to the vault owner's primary working role (see CLAUDE.md *About the Vault Owner*) unless they name another for this run (e.g. "as a parent", "as a hiring manager", "as the person who has to maintain this").

### 2. Choose the persona set

Five perspectives, adapted to the topic — the personas are a *default, not a law*:

- **Tech / strategy / general** (default): Practitioner · Academic · Skeptic · Economist · Historian.
- **People / leadership / org-change**: swap to voices that actually see different things — e.g. the frontline practitioner, the brand-new joiner (sees the system fresh), the burned-out team lead, the Skeptic, the org historian who has watched three reorgs.
- **Product / customer**: the power user, the churned user, the support rep, the Economist, a competitor's product lead.

Always let the vault owner override or name their own five. **State the chosen five in one line before running**, so they can redirect before you burn the pass.

### 3. Ground in the vault (recommended for vault-relevant topics; offer/skip)

Before simulating, run `qmd query` (one `lex` + one `vec`, collection `wiki` plus any relevant raw collection) for what the vault already holds on the topic. Feed the hits into the personas so they engage **the owner's actual material**, not just generic priors — this is the edge a plain paste into a chatbot can't give. Skip for purely external topics (e.g. researching a vendor the vault has never mentioned) where there is nothing to ground on.

Record which pages were pulled — they go in the artifact's `grounded:` frontmatter.

### 4. Run the four phases — in sequence, one pass

Execute the logic of the four prompts (verbatim wording in `prompts/storm-research.md`):

1. **Multi-perspective scan** — each persona's core position (2 sentences), strongest evidence, and the one thing only they would say.
2. **Contradiction map** — where two or more perspectives clash; strongest/weakest evidence; the single question that resolves the biggest conflict; what *all* agree on (likely true); what *none* addressed (the field's blind spot).
3. **Synthesis** — one-paragraph brief for a decision-maker with 60 seconds; 5 key findings ranked by reliability (with which perspectives support/challenge each); the hidden cross-finding connection; the actionable insight for `[YOUR ROLE]`; the frontier question.
4. **Peer review** *(non-optional)* — confidence scores (1-10) per finding; weakest link + what would verify it; bias check (which voice dominated); missing 6th perspective; overall grade + what to fix. This is the step that catches STORM's documented self-critique gap — never skip it.

### 5. Write the artifact (the defined output)

**Every run produces a briefing artifact** at `raw/research/YYYY-MM-DD-<topic-slug>.md`, built from `templates/storm-briefing.md` — this is the skill's deliverable, not an optional afterthought.

Write the file; **do not dump the whole briefing inline**. A full STORM briefing is a wall of text that's miserable to read in a terminal. Inline, give a **tight digest only**: the 60-second summary, the top finding + its confidence, the single sharpest blind-spot, and the overall grade — then point to the artifact(s). The full thing lives in the file. Structure (the template):

- **Synthesis briefing** (Phase 3) + **Peer-review scorecard** (Phase 4) are the keepers, up top.
- **To verify externally** — the low-confidence claims Phase 4 flagged, as a checklist ready to hand to a web-sourced research pass.
- **Working material** (Phases 1-2: the five perspectives + contradiction map) goes in the appendix.
- Frontmatter records `role`, `personas`, and `grounded` (which wiki pages, or none).

Then run `qmd update && qmd embed` so the briefing is searchable, and commit locally (`research: STORM briefing — <topic>`). **Never push.**

> **One-time setup.** `raw/research/` is not one of the collections `setup.sh` registers. If `qmd collection list` doesn't show `research`, register it once:
>
> ```bash
> qmd collection add research ./raw/research && qmd update && qmd embed
> ```
>
> Until that's done the briefings are still on disk and readable — they just won't come back from `qmd query`.

**Promotion, not fast-path.** A briefing whose conclusion is genuinely reusable gets promoted into `wiki/` via the normal Ingest pass (source/insight discipline, CLAUDE.md §Workflows.1) — offer that as a follow-on; never fast-path a STORM briefing into `wiki/` synthesis without the gates. For a deliberately throwaway pass the vault owner can say "don't save" — honour it (inline only).

### 6. Offer the HTML visualisation

A STORM briefing is structured, comparative, multi-dimensional data — five parallel perspectives, a clash map, confidence-scored findings — which reads far better as a visual than as linear markdown. After the `.md` artifact, **offer to also render an HTML visualisation**. On yes:

- `mkdir -p docs/visualisations` if it doesn't exist yet, then copy `templates/storm-briefing.html` -> `docs/visualisations/YYYY-MM-DD-storm-<topic-slug>.html`. Fill every `{{PLACEHOLDER}}` and the blocks marked "repeat", then delete the guide comments.
- **Self-contained only** — inline `<style>`, no CDN scripts, no external fonts, no chart libraries. The template already renders correctly in both light and dark colour schemes; don't hardcode colours over the CSS variables or you break one of the two.
- The viz components: the 60-second summary as the lead card, **five persona cards** (colour-coded), the **contradiction map** (clash blocks + the agree/blind-spot callouts), **findings as confidence bars** (`c-hi`/`c-mid`/`c-lo` by 8-10 / 5-7 / 1-4 score), the **peer-review scorecard** table, and the **to-verify** checklist. The actionable insight gets the highlighted insight card.
- The `.md` stays the **source of truth** (qmd-indexed, the durable record); the `.html` is the **readable view**. Keep them consistent — the HTML carries the synthesis + scorecard, not new content.
- Commit the HTML in the same commit (or a follow-on): `docs(visualisations): STORM briefing — <topic> (html)`. **Never push.**

## Rules

- **Run all four phases.** Phase 4 (peer review) is the point — it's what makes STORM's output trustworthy rather than five confident simulations. Don't stop at synthesis.
- **Personas adapt to the topic.** Don't force the tech five onto a people question.
- **Ground when the vault has the topic.** qmd-grounding is the difference between "a clever generic briefing" and "engages what the vault owner actually knows."
- **Don't fabricate sources or citations.** STORM simulates *perspectives* from the model's knowledge plus the grounded vault context; it is not a web-sourced report. If a claim needs live external proof, say so and put it on the "to verify externally" list.
- **The artifact is the deliverable.** Every run writes `raw/research/YYYY-MM-DD-<topic-slug>.md` from `templates/storm-briefing.md` by default — inline-only is the opt-out ("don't save"), not the default. A STORM run that leaves nothing on disk is the failure mode this skill exists to avoid.
- **Don't wall-of-text the chat.** The inline reply is a tight digest pointing to the artifact(s), never the full briefing. The readable full view is the HTML; the durable record is the `.md`.
- **Keep wording in sync.** The verbatim prompts live in `prompts/storm-research.md`; if you refine the phrasing, update there too so the paste-anywhere copy doesn't drift from the skill.
- **Commit locally. Never push.**

## Caps

| Item | Cap |
|---|---|
| Topics per run | 1 |
| Personas | 5 (a 6th only when peer-review flags a missing angle worth a second pass) |
| Grounding queries before Phase 1 | 1 `qmd query` call (lex + vec sub-queries) |
| Files touched | 1 (the `raw/research/` briefing) by default; 2 if the HTML viz is rendered (+ `docs/visualisations/`); nothing else unless promoted to wiki later |

## Common mistakes

- **Stopping at the synthesis** and skipping peer review — ships five confident simulations as if they were verified.
- **Using the default tech personas on a people topic** — produces a tin-eared briefing; swap the five.
- **Skipping the qmd grounding** on a vault-relevant topic — wastes the one thing this skill has over pasting the prompts into any chatbot.
- **Treating the output as sourced research** — it's structured reasoning, not citations; don't present simulated claims as externally verified.
- **Fast-pathing a briefing into `wiki/`** without the normal source/insight gates.
- **Treating the artifact as optional** — emitting the briefing inline only and moving on. Every run writes the `raw/research/` file by default; inline-only is the explicit opt-out, not the norm.
- **Dumping the full briefing inline** — a wall of text in the terminal is the exact readability problem the artifact + HTML exist to solve. Inline = tight digest only.
- **Forgetting `qmd update && qmd embed`** (or never registering the `research` collection) — the briefing exists on disk but never comes back from a query, so the next STORM run on a related topic can't ground on it.
- **External deps in the HTML** — no CDN scripts, fonts, or chart libraries. Self-contained inline `<style>` only.
- **Hardcoding colours in the HTML** instead of using the CSS variables — it will look correct in your colour scheme and broken in the other one.
- **Letting the HTML and `.md` drift** — the HTML is a view of the briefing, not a place for new claims.
- **Pushing the commit.**

## Iteration log

- **v1** — initial version. Promoted from `prompts/storm-research.md` (itself distilled from a public write-up of Stanford OVAL's STORM method) after the question came up of whether STORM should be a skill rather than a static prompt block. It should: STORM is a sequential multi-step workflow, and as a skill it runs all four phases in one pass, adapts the personas to the topic, and (the real edge) grounds the five perspectives in the vault via qmd instead of generic priors. Kept the `prompts/` file as the portable paste-anywhere companion (for any chat UI, or Stanford's hosted tool); the prompt wording is single-sourced there.
- **v2** — defined the **artifact**. v1 emitted the briefing inline and only *offered* to file it, with a loose home — flagged as wrong, because a skill should produce a defined output, not evaporate into the chat. Now every run writes `raw/research/YYYY-MM-DD-<topic-slug>.md` from the new `templates/storm-briefing.md` **by default** (inline-only is the opt-out). New `raw/research/` folder + a `research` qmd collection make STORM output a recognisable, searchable artifact type; the synthesis + peer-review scorecard are the keepers, the 5-perspective scan + contradiction map an appendix, plus a "to verify externally" hand-off list. Promotion into `wiki/` stays gated (offer, don't fast-path).
- **v3** — added the **HTML visualisation** + fixed the inline wall-of-text. A STORM run was dumping a large unreadable block inline. Two changes: (1) the inline reply is now a *tight digest* (60-second line + top finding + sharpest blind-spot + grade) pointing to the artifact — never the full briefing; (2) after the `.md`, the skill **offers an HTML visualisation** rendered from the new `templates/storm-briefing.html` into `docs/visualisations/YYYY-MM-DD-storm-<slug>.html` — self-contained, light/dark aware (persona cards, contradiction callouts, confidence bars, scorecard table, verify checklist). The `.md` stays source-of-truth + qmd-indexed; the HTML is the readable view.
