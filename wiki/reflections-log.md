---
type: reflections-log
title: "Reflections Log"
date_updated: 2020-01-01
---

# Reflections Log

**A dated, first-person record of what actually struck you** — the reactions, realizations, decisions and unresolved questions that landed while you were reading a book, sitting in a meeting, or walking away from a design review. Reverse-chronological, newest first.

This is the layer a second brain quietly loses. Synthesis pages can always be rebuilt from the raw sources — re-read the transcript and the topic page comes back. Your own reaction to it cannot. Nobody else recorded that you read one paragraph of a book three times and changed how you run your week because of it. If it isn't written down within a day or two, it's gone.

Distinct from [[log]] (a record of wiki *operations* — what was ingested, what was regenerated) and from [[insights/example-insight|insight pages]] (third-person claims defended by evidence). Individual source pages still carry their own reflections in place; this page is the **aggregated first-person layer**, so the interior thread is browsable end to end instead of scattered across fifty source summaries.

## What belongs here

- **What struck you** — a line, a slide, a throwaway remark in a 1-on-1 that landed harder than the thing it was attached to.
- **Decisions and turns** — the moment you changed your mind, dropped an approach, or committed to a new one, captured while the reasoning is still warm.
- **Self-observations** — something you noticed about how you work, decide, or react. Usually uncomfortable. Usually the most valuable entry on the page.
- **Open questions you're wrestling with** — a tension you can't yet resolve, written down so that future-you can see how long you carried it.
- **Revisits** — a look back at an earlier entry that turned out right, wrong, or premature.

## What does not belong here

- **General teaching or content** from a book, talk or meeting — that stays in `wiki/sources/`.
- **What someone else realized.** Their experience is source material; only your own interior response goes here.
- **Third-person synthesis** — patterns across multiple sources belong in `wiki/insights/`.
- **Task-shaped follow-ups.** "Email the vendor" is not a reflection. Park it in [[backlog]] or a plan page.

## Reflections vs insights

The same material often produces both. Write both — they do different jobs and are read at different times.

| | This page | `wiki/insights/` |
|---|---|---|
| Voice | First person — *I noticed, I decided* | Third person — *the pattern is* |
| Claim | What it did to you | What appears to be true |
| Evidence | Your own words, on a date | Multiple sources, cited |
| Confidence field | Not applicable | Required (high / medium / low) |
| Edited later | No — append a new entry instead | Yes — kept current, with a Recent-updates callout |
| Read when | Re-reading your own trajectory | Answering a question |

An insight page that quietly absorbs your first-person voice stops being falsifiable — "I felt overwhelmed by this" is not evidence for a claim, and dressing it as one weakens both. Keep them apart and each stays honest. An insight page may **cite** an entry here as the origin of a hunch; it should not paraphrase it into an assertion.

## Entry format

Newest first. One H3 per entry, dated, with a short handle so the heading is scannable in Obsidian's outline.

```markdown
### YYYY-MM-DD — short handle

**Type:** reaction | decision | self-observation | open question | revisit
**Trigger:** [[sources/the-source-page]]

> Your own words at the time, verbatim, if you captured them.

One or two paragraphs in your own voice. What struck you, what you decided,
what you are still holding. Written to be re-read in a year, so name the
situation concretely enough that future-you can reconstruct it.
```

**Trigger discipline.** Link the **source page**, not the raw file — the same one-hop provenance rule the rest of `wiki/` follows. If the trigger was a capture that hasn't been ingested yet and has no source page, write the raw path in backticks (`` `raw/captures/daily/2020-01-01 - Daily.md` ``) rather than as a wikilink, and link the source page properly once it exists.

**Append-only.** Entries are dated records of what you thought *then*. Don't rewrite one because you now think differently — write a new `revisit` entry that references the old handle. The value of this page is that it preserves your wrongness, which is the only way to see how your judgment moved.

## How entries get here

The **Ingest** workflow routes here: after the source page is written, if the raw source carries genuine first-person interior content — your own reaction, a decision you made, a question you're now holding — add an entry to this page in the same pass. Don't let it dissolve into the source summary's neutral prose, and don't wait for a separate ritual. The weekly re-read is a safety net for what the ingest missed, not the primary path.

This page lives under `wiki/`, so `qmd` indexes it with everything else. Semantic (`vec`) search is unusually good at surfacing it — first-person entries rarely share keywords with the question that needs them, but they cluster hard by meaning.

## Rotation and size discipline

Same rhythm as [[log]]. This file is the current rolling buffer. At roughly 250KB, or at year-end, move the older entries into `wiki/log/YYYY-reflections-archive.md` with `type: log-archive`, a `year:` key and a `date_range:` key. Keep newest-first ordering inside each file, and rewrite any self-referencing anchors in the archive to point at the archive's own filename, since rotation moves the target.

Rotate on the calendar rather than on feel. A reflections log that grows to a thousand entries in one file stops being re-read, and a log nobody re-reads is a diary, not a second brain.

---

## Entries

### 2020-01-01 — (example — delete this once you write your first real entry) Re-reading felt like working

**Type:** self-observation
**Trigger:** [[sources/example-source|Notes on "Make It Stick"]]

> "I have re-read these notes four times this month and I could not have told you three things from them."

The uncomfortable part wasn't the finding — it was recognizing my own study habit in the description of the *weakest* method. I have been re-reading for years and counting the time as work, because re-reading produces the feeling of fluency: the text goes down easily the fourth time, and I read that ease as knowing. It was never knowing. It was familiarity wearing knowing's clothes.

What I'm changing this week: close the file and write down what I remember before I re-open it, every time. I expect to hate the first few attempts, and that reaction is the point — the difficulty is the signal that something is actually being retrieved rather than recognized.

Still open: whether this transfers to learning by building. Reading a codebase has the same fluency trap, but "close the file and recall it" is a strange instruction when the file is right there and I can just look. Noting it here rather than resolving it. The third-person version of the finding lives in [[insights/example-insight]] — that page argues the claim from evidence; this entry records what it cost me to accept it.

## Related

- [[log]] — wiki operations history; this page deliberately doesn't duplicate it
- [[index]] — master catalog
- [[backlog]] — deferred wiki work, including reflections that deserve promotion to an insight
- [[insights/example-insight]] — the third-person counterpart to the example entry above
