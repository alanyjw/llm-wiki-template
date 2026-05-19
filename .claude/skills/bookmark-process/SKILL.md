---
name: bookmark-process
description: Use when the user says "process bookmark <N>", "transcribe bookmark <N>", "ingest bookmark <N>", or pastes a URL drawn from raw/bookmarks.md. Fetches the URL, proposes light vs deep treatment, on confirmation writes the output (inline daily-capture line OR full raw/web-clippings/ file), strikes the checkbox in raw/bookmarks.md, and commits locally. One bookmark per invocation. Per-item actuator — distinct from /weekly-reread which re-skims accumulated raw notes.
---

# Bookmark Process

Process a single bookmark from `raw/bookmarks.md` end-to-end: fetch → propose treatment → write → strike → commit. The user points at one bookmark per invocation by index or pasted URL. The skill does not batch.

## When to use

- The user says "process bookmark <N>", "transcribe bookmark <N>", "ingest bookmark <N>", "do bookmark <N>"
- The user pastes a URL that appears unstruck in `raw/bookmarks.md`
- **Skip / refuse** if asked to "process all bookmarks" — point the user back to the file's own philosophy: *"Process only what still pulls."* Ask them to name one.

## Steps

### 1. Resolve the target

- If the user gave `<N>` → read `raw/bookmarks.md`, build the list of unstruck `- [ ]` entries in document order, pick the Nth (1-based).
- If the user pasted a URL → grep for it in `raw/bookmarks.md`. If matched on a struck line, ask whether to re-process. If not found, ask whether to add it to bookmarks first or process ad-hoc.
- If both are ambiguous → ask one disambiguating question, don't guess.

Capture the source tag (`[x]` / `[yt]` / `[web]`), the URL, and the one-line context the user wrote alongside it.

### 2. Fetch + enrich by source tag

- **`[yt]`**: WebFetch the page metadata, then run `yt-dlp --write-auto-sub --skip-download --sub-lang en --sub-format vtt -o "<tmpdir>/%(id)s" <url>` via Bash to pull auto-captions. If `yt-dlp` is missing or returns no captions, note the limitation and continue with WebFetch metadata only.
- **`[x]`**: WebFetch alone usually fails on x.com (login wall). Run `yt-dlp --write-info-json --skip-download -o "<tmpdir>/%(id)s" <url>` first — yt-dlp supports `twitter.com` / `x.com` and returns structured tweet text, author, attached video info, and (sometimes) thread tweets. If yt-dlp fails entirely, ask the user to paste the tweet or thread text. **Do not fabricate.**
- **`[web]`**: WebFetch only.

Cap fetched content at ~4000 tokens. If a transcript or article exceeds that, keep the first ~2000 + last ~1500 tokens with a `[…elision N tokens…]` marker between.

### 3. Summarise + propose treatment

Write the user a ≤5-bullet summary of what was fetched.

**For `[x]` links, declare the subtype** so they can pick treatment knowingly:
- **single** — one tweet, ≤2 paragraphs, no video, no thread
- **thread** — ≥3 connected tweets by the same author
- **video** — tweet with attached video (transcript pulled if yt-dlp succeeded)
- **outbound** — tweet body is essentially a wrapper around a single outbound URL (article / YT)

For `outbound`, ask the user whether to **redirect** processing to the outbound URL (re-running this skill against it) or to **capture the X framing** (treat as `single`).

Then propose **light** or **deep** with a one-line reason. Heuristics:
- light → ≤3 min skim value, single insight, tweet/short post
- deep → re-readable substance, transcript, multi-thread, long-form essay

**Wait for the user's confirmation** (or override) before writing anything.

### 4a. Light path

Append one line to `raw/captures/daily/YYYY-MM-DD - Daily.md` (today's date):

```
- [HH:mm] [bookmark-{tag}] one-line reaction — <URL>
```

If today's daily file is missing, create it from `templates/capture.md`. Don't disturb existing entries — append at the end of the body.

Skip directly to step 5.

### 4b. Deep path

Branch by source tag:

**`[yt]`** → `raw/web-clippings/video-{creator-slug}-{title-slug}.md`. Use `templates/video.md` as structural reference (the template itself is Templater syntax — copy the *output structure*, not the `<%* ... %>` blocks). Sections:

```markdown
**URL:** <url>
**Creator:** <name>
**Duration:** <hh:mm>
**Date watched:** YYYY-MM-DD

## Key timestamps
- [t=Xs] <highlight from transcript>

## One-liners (verbatim or paraphrased)
- <quote>

## My response / reflection
- <stub — "(to fill)" if no signal yet>

## Open threads
- <stub>

## Transcript (auto-captions)
<truncated to cap; mark elision>
```

If no auto-captions are available (common for X-hosted video and many YT uploads), populate the `## Transcript` section with a "Status: not available" stub. Note that a separate transcription tool can be invoked against this clipping later if the video warrants the effort.

**`[web]`** → `raw/web-clippings/{title-slug}.md` with frontmatter:

```yaml
---
title: "<page title>"
source: <url>
author: <name or "unknown">
published: YYYY-MM-DD
description: <meta description>
tags: ["clippings", <topic tags>]
---
```

Body: full fetched content (truncated at cap), then `## My response` stub.

**`[x]`** → branch by subtype from step 3:
- **single** → `raw/web-clippings/x-{author}-{title-slug}.md`. Frontmatter (title = first ~40 chars of tweet, source = tweet URL — tweet ID lives inside the URL, no separate field needed, author, published, tags). Body: tweet text + `## My reaction` stub. (If the user picked `deep` for a single tweet, flag it: *"Single tweets usually go light — confirm deep?"*)
- **thread** → `raw/web-clippings/x-thread-{author}-{title-slug}.md`. Frontmatter (title = first tweet's first line, author, source = root tweet URL, tweet_count, tags). Body: numbered tweets (`### 1/`, `### 2/`, …) + `## My response` stub.
- **video** → `raw/web-clippings/video-x-{author}-{title-slug}.md`. Use the same structure as the `[yt]` deep template, but with `**URL:** <X tweet URL>` instead of YouTube URL. Embed transcript if pulled.
- **outbound (redirect)** → re-invoke this skill against the outbound URL as a fresh `[yt]` or `[web]` (per its domain). The original `[x]` bookmark still gets struck in step 5, with one inline note in today's daily capture: `[HH:mm] [bookmark-x→redirect] processed as <outbound URL> → see <new clipping path>`. Do not double-write a full clipping for the X wrapper.
- **outbound (capture X framing)** → treat as `single`.

**Slug rules** (filename component): lowercase, hyphens for spaces, drop punctuation, max 60 chars. Source of the title-slug by tag:

| Tag / subtype | Title source |
|---|---|
| `[yt]` | Video title from `yt-dlp` metadata |
| `[web]` | `<title>` tag or first `<h1>` |
| `[x]` single | First ~6 meaningful words of the tweet (drop URLs, mentions, emojis) |
| `[x]` thread | First ~6 meaningful words of the **root** tweet |
| `[x]` video | The descriptive subject of the embedded video, derived from the tweet text. Not the tweet author's framing — the *thing being shown*. |

The full source URL goes in the file's frontmatter / metadata block — it carries the tweet ID and is the canonical reference back to X.

### 5. Strike the checkbox

In `raw/bookmarks.md`, change the target line's `- [ ]` to `- [x]`. Use `Edit` with enough surrounding context that the change is unambiguous to exactly that line. **Do not touch any other line** — no reformatting, no whitespace cleanup.

### 6. (Deep path only) Reindex qmd

Run `qmd update && qmd embed`. The new file lives in the `web-articles` qmd collection (per CLAUDE.md §Retrieval) — without `embed`, `vec`/`hyde` queries will miss it.

### 7. (Deep path only) Append to wiki/log.md

One line, dated:

```
[YYYY-MM-DD] Bookmark deep ingest — {tag} {URL} → raw/web-clippings/{slug}.md
```

### 8. Commit locally

Stage **only** the touched files. Commit with a type-prefixed message.

- Light: `chore: bookmark processed → YYYY-MM-DD daily capture`
- Deep: `raw: ingest {tag} bookmark as web-clipping ({slug})`
- Outbound-redirect (light side): `chore: bookmark redirected → <outbound URL>` (the redirected substance gets its own commit from the recursive invocation)

**Never push.**

## Rules

- **One bookmark per invocation.** "Process all" → refuse, ask the user to name one.
- **`raw/bookmarks.md` is read-only EXCEPT** for striking exactly the target checkbox.
- **Light vs deep is the user's call.** Skill proposes; the user decides. Don't override after they pick.
- **Don't ingest into `wiki/`.** Bookmark-tier content stays in `raw/`. Wiki promotion is a separate `weekly-reread` or full Ingest pass (CLAUDE.md §Workflows.1).
- **No fabrication.** If yt-dlp + WebFetch both fail, ask the user to paste. Never invent tweet/article content.
- **Don't reformat the bookmarks file.** Strike one line, leave the rest exactly as is.

## Caps

| Item | Cap |
|---|---|
| Bookmarks per run | 1 |
| Fetched content per URL | 4000 tokens |
| Summary bullets before light/deep decision | 5 |
| Files touched per run | ≤3 (clipping + bookmarks.md + log.md) for deep; ≤2 (daily capture + bookmarks.md) for light |

## Common mistakes

- Editing other entries in `raw/bookmarks.md` while striking the target one.
- Skipping `qmd update && qmd embed` after deep ingest — `lex` queries still find the new clipping which masks the bug; `vec` / `hyde` silently miss it.
- Picking deep on a 200-word tweet (wastes capture budget).
- Picking light on a 40-min video with a real transcript (loses the substance).
- **Misclassifying X subtype** — treating a video-tweet as `single` (drops transcript), a long thread as `single` (drops 9 of 10 tweets), or an outbound-wrapper as `single` (captures the wrapper instead of the substance).
- **Double-processing on `[x]` outbound redirect** — writing a full clipping for the X wrapper *and* the outbound substance. The wrapper gets the daily-capture redirect note only.
- Pushing the commit. **Never push from this skill.**
- Fabricating tweet content when both yt-dlp and WebFetch fail. Always ask for paste.
- Creating a `wiki/sources/` page from a bookmark. Bookmarks land in `raw/` only — wiki promotion is a separate pass.

## Iteration log

- **v1** — initial version. Per-item actuator complementing `weekly-reread`. Output mode: full process per bookmark workflow (skill picks light vs deep with user as final say). Scope: one bookmark per run, user points at it. YT transcripts via inline `yt-dlp` (auto-captions). `[x]` subtypes (single / thread / video / outbound) detected from yt-dlp info JSON, each routed to a matching deep template; outbound-wrapper offers a redirect path so the X bookmark doesn't double-process the substance.
- **v2** — switched all `[x]` deep filenames (single / thread / video) to `{author}-{title-slug}` for consistency with `[yt]` and `[web]` patterns. Tweet ID preserved inside the URL in frontmatter. Added explicit "Source of the title-slug by tag" table.
- **v3** — added explicit hand-off note for video clippings with stub transcripts: a separate transcription tool can be invoked against any `raw/web-clippings/video-*.md` later.
