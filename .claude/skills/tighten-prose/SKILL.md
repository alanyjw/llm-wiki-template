---
name: tighten-prose
description: Use when the vault owner says "tighten this", "cut the clutter", "de-jargonize this", "Zinsser this", "make this sound like a person", "find the missing I", "is every word doing useful work", "review this writing", or wants a draft / message / wiki page / plan / project page edited for clarity, simplicity, brevity, and humanity. Voice-agnostic craft pass grounded in William Zinsser's *On Writing Well* — returns a tightened version plus a severity-tagged findings report, cuts clutter without flattening the author's voice, and finds the missing "I". Prose only — it neither imposes a voice nor strips one, and it does not review code or system designs.
---

# Tighten Prose

A single-mode editing pass that reads a piece of prose and returns **(a) a tightened version** and **(b) a severity-tagged findings report**, judged against the craft principles in William Zinsser's *On Writing Well*.

Zinsser's four articles of faith for nonfiction — **clarity, simplicity, brevity, humanity** — are the spine. The job is to strip every sentence to its cleanest components *without losing the author's voice*, and to find the missing "I" so the prose reads like a person talking, not an institution issuing a notice.

**This is craft, not identity.** The skill must not impose a voice on writing that doesn't have one, and it must not strip the voice out of writing that does. See *The voice boundary* below — it is the load-bearing rule of this skill.

## When to use

The vault owner says, of any draft / message / page:

- "tighten this" · "cut the clutter" · "trim this down"
- "de-jargonize this" · "Zinsser this" · "make this sound like a person"
- "find the missing I" · "is every word doing useful work?"
- "review this writing" · "is this too wordy / too institutional?"

**Applies to** — anything the vault owner writes: team messages, 1-on-1 follow-ups, project updates and announcements, conference talk notes, **wiki synthesis prose**, **plans**, **project pages**, a reply they are about to send. Clutter-cutting is the same move everywhere; a wiki page and a team message both get it.

**Do not use** for:

- **Code, specs, config.** This skill judges prose. Point the owner at a code review or refactoring workflow instead.
- **System-design critique** (data flow, scope, architecture, sequencing). That is a design review — a different judgment, on a different object. This skill has no opinion about whether the plan is right, only about whether the sentences are clean.
- **Generating new prose from scratch.** This skill edits prose that already exists. It is not a drafting tool, and "tighten" is not license to rewrite the piece into something the author didn't say.
- **Immutable `raw/` sources.** Never edit a source file; tighten a copy or a draft.

## The voice boundary (load-bearing)

Zinsser: *"Most first drafts can be cut by 50 percent without losing any information or losing the author's voice."* The whole skill lives or dies on that last clause.

**Clutter is not voice.** Cut freely: "in order to", "at this point in time", padded verb phrases, stacked qualifiers, institutional fog. What must survive the cut is everything that is doing *voice* work rather than *filler* work. These commonly look like clutter to a mechanical tightener and are not:

| Looks like clutter | Is actually voice |
|---|---|
| A concrete scene before the point ("I still remember the week we shipped the first version…") | The **signature opener**. That is the lead, not windup. |
| A self-deprecating aside in parentheses | The author being a person. Cutting it makes the piece correct and cold. |
| A recurring construction — a "not X, but Y" contrast, a repeated refrain, a habitual sign-off | The author's rhythm. Repetition on purpose is not redundancy. |
| In-house vernacular the reader shares | Shared shorthand is speed. (Jargon the reader does **not** share is clutter — cut that.) |
| A plainly-stated feeling, a thank-you, a forward commitment at the close | The warmth. It is usually the reason the message works. |
| A very short sentence, or a word echoed once for emphasis | A deliberate beat. Flag only if it reads as an accident. |

**How to know what the author's voice is**, in order of authority:

1. Documented style notes or a voice profile committed in the vault, if one exists.
2. The owner's other writing on the same surface — `qmd query` the `wiki` or `captures` collections for prior messages and drafts of the same kind.
3. The draft in front of you. Traits that recur three times in one draft are choices, not accidents.

If you can't tell whether a passage is voice or filler, **ask one question before cutting.**

**On conflict — a cut would tighten the sentence but erase a voice trait — the voice wins.** Flag the tension as a *Note*; do not silently flatten it. Default to preserving warmth. A correct tighten can make a message *more* like the author, never less.

**Two registers, two settings of this dial:**

- **Personal prose** — anything the owner will send, say, or publish under their own name. The boundary binds hardest here. Preserve the traits above; cut only the clutter no voice claims.
- **Neutral prose** — wiki synthesis, a plan, a project page, an institutional notice. Here the risk runs the other way: do not *manufacture* a personality. A wiki page doesn't need signature moves or a warm sign-off; it needs clutter cut, verbs made active, and meaning made plain. "Find the missing I" on a neutral page means *name who did what*, not *inject charm*.

If the register is ambiguous, ask which one it is before cutting.

## The Zinsser checklist

Run every relevant item over the artifact. Each finding names the item, quotes the offending passage, and proposes the concrete fix. Grouped by Zinsser's four articles.

### Brevity & Simplicity — cut the clutter

| Item | The tell | The fix |
|---|---|---|
| **Throat-clearing** | "I just wanted to…", "it should be noted that", "at this point in time", "I might add" | Delete. Start at the real first sentence. |
| **Padded verbs** | "managed to complete the implementation of", "conduct a series of" | One active verb: "built", "tested". |
| **Qualifier whittle** | "a bit", "sort of", "fairly", "more or less", "reasonably", "essentially", "kind of", "really", "very" | Cut. *"Every little qualifier whittles away some fraction of the reader's trust."* |
| **Prepositional padding** | "in order to", "with respect to", "in the event that", "going forward", "for the purpose of" | "to", "about", "if", "next", "to". |
| **Concept nouns** | "the implementation of X", "the matter of conducting Y" | Turn the noun back into a verb: "implementing X", "doing Y". |
| **Said-it-twice** | "completely finished", "end result", "advance planning", "any questions whatsoever" | Keep one word. |

### Clarity — active verbs, plain meaning

| Item | The tell | The fix |
|---|---|---|
| **Passive voice** | "the migration will be handled by the platform team" | "the platform team handles the migration." |
| **Decorative modifiers** | adverbs/adjectives that repeat the verb/noun ("blared loudly", "yellow daffodils") | Cut the modifier; let the verb/noun carry it. |
| **Muddy meaning** | you can't tell what the sentence claims | *"Clear thinking becomes clear writing."* Ask "what am I trying to say?" then say it. |

### De-jargonize — journalese & fad words

| Item | The tell | The fix |
|---|---|---|
| **Institutional fog** | "utilize", "leverage", "circle back", "going forward", "as per" | "use", "use", "follow up", "next", "from". |
| **Fad words** | "prioritize", "impact" as a verb, "robust", "synergy", "actionable" | Plain equivalents. *"The race in writing is not to the swift but to the original."* |

### Humanity — the missing "I" (highest leverage)

| Item | The tell | The fix |
|---|---|---|
| **The missing "I"** | reads like a department issuing a notice; nobody can be visualized doing anything | Put a human back in the sentence — name who decided, who built it, who is asking. *"Just because people work for an institution, they don't have to write like one."* On personal prose, the author's own voice traits define *which* "I". |
| **Warmth survived?** | the cut left it correct but cold | *"The reader has to feel that the writer is feeling good."* Keep the human register. |

### Structure — the lead, the ending, think small

| Item | The tell | The fix |
|---|---|---|
| **Weak lead** | the first sentence is windup | *"The most important sentence in any article is the first one."* Start where the human appears. |
| **Trailing ending** | "in summary", "to wrap up", "please feel free to let me know if you have any questions whatsoever" | *"When you're ready to stop, stop."* Land on the forward commitment. |
| **Five thoughts, not one** | the piece tries to do everything | *"Think small."* One provocative thought; cut or split the rest. |

### Sound — read it aloud

Read the tightened draft aloud (in your head is fine). Readers *hear* what they read. An occasional short sentence carries a punch. Flag rhythm clashes and unintended immediate word-echoes ("the tracker tracks tracked items") as *Notes* — and check them against the voice boundary first, since a repeated word can be the author's beat rather than an accident.

## Procedure

1. **Resolve the artifact.** A file path (a message draft, a `wiki/**` page, a `raw/captures/**` note, a plan, a project page) or pasted text. If it is a `raw/` *source*, refuse to edit it — offer to tighten a copy. If ambiguous, ask one question.

2. **Classify the register.** Is this **personal prose** (something the owner will send, say, or publish under their own name) or **neutral prose** (wiki synthesis, a plan, an institutional message)? This sets how *The voice boundary* binds in each direction — preserve traits on the first, don't invent them on the second. If unclear, ask.

3. **Read the artifact in full.**

4. **Run the checklist.** Walk every relevant item. Skip items that don't apply — they don't appear in the report.

5. **Severity-tag each finding** (rubric below).

6. **Produce the tightened version.** Apply every Medium-and-below fix directly. For Critical/High findings that change meaning or touch voice, apply the cut but call it out so the owner can veto. Target Zinsser's rule of thumb — *most first drafts cut 50% without losing information or voice* — but never at the cost of a voice trait.

7. **Read it aloud.** Catch rhythm clashes and echoes. Adjust.

8. **Emit the report** (format below): the tightened version first, then the findings.

9. **Offer to apply / persist.**
   - Pasted text → return inline; offer nothing further.
   - A file → ask before writing. On yes, edit the file. **Never touch `raw/` sources.** If the file is a `wiki/**` synthesis page, follow the normal wiki discipline: add a Recent-updates entry and bump `date_updated` (insights / topics / plans / projects), then run all three local lint gates exactly as CLAUDE.md §Wiki Lint Pipeline specifies them (that section is the authority — copy the commands from there rather than from memory, and note in particular that Layer 1 is `npx markdownlint-obsidian-cli@...` (`bunx` works too, but Bun is not a prerequisite) and **never** `--bun`, which dies on a vendor packaging bug). Finish with `qmd update && qmd embed` so retrieval sees the edited text.
   - If it is a draft mid-conversation (not yet a file), hand the tightened version back into the conversation rather than writing a file.

## Severity rubric

- **Critical** — the missing "I" / institutional fog that makes the whole piece read like a notice, or meaning so muddy the reader gets lost. Needs re-voicing, not a tweak.
- **High** — clutter or passive constructions heavy enough to bury the message; a windup lead that hides the point.
- **Medium** — qualifiers, padded phrases, concept nouns, jargon words, decorative modifiers. Cheap, apply directly.
- **Note** — sound / rhythm, an optional cut, or a **voice-conflict flag** (a tightening the voice boundary forbids). No action without the owner's call.

## Output format

**1 — Tightened version.** The edited prose, ready to use.

**2 — Findings.** Severity-ordered (Critical → Note). Each: `[Severity] Item — "offending passage" → fix`. Group trivial Medium cuts into one line if there are many ("Cut 6 qualifiers: *fairly, more or less, reasonably…*"). Keep it scannable.

**3 — One-line verdict.** What the piece needed most (e.g. *"Mostly a clutter problem — cut ~40%, the 'I' was already present"* or *"Clutter was minor; the real fix was the missing 'I' — it read like a notice"*).

## Common mistakes

- **Flattening the voice.** The #1 failure. A tighter sentence that erased the author's signature opener or their self-deprecating aside is a *worse* draft. Clutter is not voice — re-read *The voice boundary*.
- **Inventing a voice on neutral prose.** The mirror failure. A wiki page or a plan doesn't need charm, emoji, or a warm sign-off bolted on in the name of "humanity". On neutral prose, "find the missing I" means name the actor, not manufacture a personality.
- **Silent rewrite, no diagnosis.** The owner asked for a *review*. Always emit the severity-tagged findings, not just a quieter draft — the named findings are the teaching value and what separates this from a generic "make it better".
- **Skipping the humanity pass.** Cutting clutter is the easy half; finding the missing "I" is the half a generic tighten skips and the half that matters most for a message a team will actually read.
- **Tightening into terseness.** Zinsser is warm, not clipped. Brevity serves humanity; it doesn't replace it.
- **Rewriting the argument instead of the sentences.** If the piece is wrong, say so in one Note and stop. Re-arguing the point under cover of an edit is out of scope.
- **Editing a `raw/` source.** Immutable. Tighten a copy.
- **Editing a wiki page without the wiki discipline.** A prose edit is still a page update: Recent-updates entry, `date_updated` bump, lint gates, `qmd update && qmd embed`.

## Provenance

The principles are drawn from William Zinsser, *On Writing Well* (30th-anniversary ed.) — chiefly Part I (Principles: simplicity, clutter, style, the audience, words, usage) and Part IV (Attitudes: the sound of your voice, enjoyment/fear/confidence, the tyranny of the final product). Quoted lines above are Zinsser's. If the vault has ingested the book as a `wiki/sources/` page, that page's key-principles section is the authority for item-level questions; if not, the book itself is.

## Iteration log

- **v1** — initial version. Single review/tighten mode, Zinsser-grounded checklist embedded inline (four articles: clarity, simplicity, brevity, humanity). Voice-agnostic; the load-bearing rule is *The voice boundary* (cut clutter, never voice; on conflict the voice wins). Built after a baseline test showed that a generic "tighten this" prompt already cuts clutter well but skips three things: the missing-"I" humanity pass, the severity-tagged diagnosis, and voice preservation. Scope deliberately covers wiki synthesis, plans, and project pages as well as personal messages — clutter is clutter everywhere. Deferred: a `--report-only` flag (findings without the rewrite); auto-chaining from a drafting workflow (left as a pointer rather than a wired step, so the owner keeps the decision to tighten).
- **v2** — made the register split explicit in both directions. The original framed the boundary as "don't strip the voice"; v2 adds the mirror failure — "don't invent one on neutral prose" — as a checklist register, a *Common mistakes* entry, and a step-2 classification that binds the rest of the pass.
