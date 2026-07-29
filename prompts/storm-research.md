# STORM Research — 4-Prompt Multi-Perspective Workflow

A reusable research workflow adapted from Stanford OVAL's **STORM** (*Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking*, NAACL 2024). Instead of asking one question and getting the majority view, you run five expert personas, map where they disagree, synthesise, then make the model peer-review its own work. Stanford's paper measured multi-perspective output as ~25% more organised and ~10% broader than single-prompt research.

**How to use:** paste the four prompts into the *same* conversation, in order — each builds on the last. ~5 minutes end to end. Fill the `[BRACKETED]` placeholders.

> **In Claude Code, use the `storm-research` skill instead** — say *"STORM research on <topic>"* and it runs all four phases in one pass, adapts the personas to the topic, grounds them in your wiki via qmd, and files the result to `raw/research/`. This file is the portable paste-anywhere copy (any chat UI, or Stanford's hosted tool); the prompt wording is kept in sync here.

- Live tool (no setup): <https://storm.genie.stanford.edu/>
- Code (MIT): <https://github.com/stanford-oval/storm>

---

## Prompt 1 — Multi-Perspective Scan

*Five experts see five different things. This is the heart of the method.*

```text
I need to research [YOUR TOPIC].

Simulate 5 different expert perspectives on this topic:

1. THE PRACTITIONER — works with this daily.
   What do they know that academics miss? What practical realities are usually ignored?
2. THE ACADEMIC — has studied this for years.
   What does the peer-reviewed evidence actually say? Where does it contradict popular belief?
3. THE SKEPTIC — thinks the mainstream view is wrong.
   What is the strongest counterargument? What evidence do proponents conveniently ignore?
4. THE ECONOMIST — follows the money.
   Who profits from the current narrative? What financial incentives shape the research?
5. THE HISTORIAN — has seen similar patterns before.
   What historical parallels exist? What can we learn from how those played out?

For each perspective give me:
- Their core position in 2 sentences
- The strongest evidence supporting their view
- The one thing they would tell me that no other perspective would
```

## Prompt 2 — Contradiction Map

*The fights between the voices are where real understanding lives.*

```text
Based on the 5 perspectives above, map the contradictions:

1. Where do two or more perspectives directly contradict each other?
   List each conflict with the specific claims that clash.
2. Which perspective has the strongest evidence? Which the weakest? Why?
3. What single question, if answered, would resolve the biggest contradiction?
4. What does EVERY perspective agree on? (Likely true — even opponents confirm it.)
5. What topic did NONE of the perspectives address?
   (The blind spot in the whole field — often the most valuable finding.)
```

## Prompt 3 — Synthesis

*Pull everything into a briefing no single expert could write.*

```text
Synthesize everything from the 5 perspectives and the contradiction map into a research briefing:

1. ONE-PARAGRAPH SUMMARY — brief a decision-maker who has 60 seconds and needs nuance,
   not just the headline.
2. THE 5 KEY FINDINGS — most important things I now know, ranked by reliability.
   For each, note which perspectives support it and which challenge it.
3. THE HIDDEN CONNECTION — one non-obvious link between findings that only shows up
   when you look at all 5 perspectives together.
4. THE ACTIONABLE INSIGHT — based on all the evidence, what should someone in [YOUR ROLE]
   actually DO differently? Be specific.
5. THE FRONTIER QUESTION — the one question that, if answered, would change how we
   understand this topic.
```

## Prompt 4 — Peer Review

*STORM's known weakness is that it doesn't self-critique (source bias, fact misassociation). This is the step most people skip — and the one that matters.*

```text
Now peer-review your own research briefing:

1. CONFIDENCE SCORES — rate each of the 5 key findings 1-10 for reliability. Explain each score.
2. WEAKEST LINK — which claim are you least confident in? What specific info would verify it?
3. BIAS CHECK — which perspective is overrepresented in your synthesis? Did one voice dominate?
4. MISSING PERSPECTIVE — is there a 6th angle that would change the conclusions?
5. OVERALL GRADE — if a reviewer graded this briefing, what grade would they give,
   and what would they tell me to fix?
```

---

## When to run it

Anything where the majority view isn't enough and the cost of a blind spot is real:

- **Before a major technical decision** — vendor choice, architecture bet, a new tool for the team. The skeptic surfaces what could go wrong; the economist exposes the incentive behind the hype.
- **Before writing a report, proposal, or talk** — covers the angles the audience would otherwise raise as objections.
- **Before learning a new domain** — the practitioner says what to learn first; the skeptic says what's overhyped; you skip the noise.
- **People and leadership questions** — swap the five personas for fitting ones (e.g. the frontline practitioner, the brand-new joiner, the burned-out team lead, the skeptic, the org historian who has watched three reorgs) when the topic is people, not tech.

The personas are a default, not a law — replace any of the five with the perspectives that actually matter for the question.

**What this method is not.** STORM produces structured *reasoning*, not sourced research. Nothing it emits is a citation. Treat the confidence scores from Prompt 4 as a to-verify list: the low-confidence claims are the ones worth checking against live sources before you act on them.

## Iteration log

- **v1** — initial version. Four prompts, run in one conversation, adapted from the STORM paper's multi-perspective question-asking loop plus an added peer-review pass (the paper's documented gap).
- **v2** — promoted to the `storm-research` project skill for in-vault runs (persona adaptation + qmd grounding + a filed artifact). This file stays as the portable copy; the prompt wording is single-sourced here, so refine it here first and mirror into the skill.
