# docs/visualisations/

Long-form explanations, diagrams, comparisons, and decision briefs are written
here as **self-contained HTML files** rather than printed into the terminal as
ASCII art or a wall of prose.

## The convention

```
docs/visualisations/YYYY-MM-DD-topic-slug.html
```

- **Date-prefixed** so the folder sorts chronologically and you can tell at a
  glance whether a brief predates a decision.
- **Slug** is lowercase with hyphens, describing the artifact, not the request:
  `2026-05-14-cost-review-deepdive.html`, not `2026-05-14-my-question.html`.
- One file per artifact. Regenerating a brief means a new dated file, not an
  in-place overwrite — the old one is the record of what you believed then.

## When to write one instead of answering inline

Reach for a visualisation when the answer contains any of:

- a diagram — hierarchies, ladders, migration paths, system topologies, tier
  breakdowns, before/after states
- a structured comparison across three or more options
- a decision brief someone will re-read later, or forward to another person
- a multi-section synthesis long enough that scrolling the terminal loses the
  shape of it

Short prose answers stay inline. A visualisation for a two-sentence reply is
overhead, and the folder loses its signal if everything lands in it.

## Why files, not terminal output

**They are durable.** Terminal scrollback is gone at the end of the session.
A committed HTML file is still there in six months, next to the git history that
explains why it was written.

**They are linkable.** A wiki page, a plan, or a commit message can point at
`docs/visualisations/2026-05-14-cost-review-deepdive.html`. Terminal output
cannot be cited.

**They read properly for visual and spatial thinkers.** ASCII boxes and arrows
collapse the moment the terminal wraps them, and nesting depth is almost
impossible to follow in monospace. Real layout — coloured tiers, boxes with
borders, arrows drawn in CSS, a table that stays a table — carries the structure
that the ASCII version only gestures at.

**They cost nothing structurally.** `docs/**/*.html` sits outside the
`wiki/**/*.md` lint glob and outside the qmd `**/*.md` index glob, so a
visualisation never trips CI, never drifts `wiki/index.md`, and never pollutes
retrieval results.

## Rule: self-contained, always

Every file must render correctly with no network access, opened straight from
disk by double-clicking it.

- Inline all CSS in a `<style>` block. No external stylesheet links.
- Inline any JavaScript. No CDN `<script src="...">`.
- No web fonts. Use a system font stack.
- Embed images as `data:` URIs, or draw the diagram in HTML/CSS instead.

The reason is the same reason the vault is plain markdown in git: an artifact
that depends on someone else's server is an artifact that will be broken the
day you actually need it. A CDN link also leaks a request every time the file is
opened, which is the wrong default for a brief written out of a private vault.
