---
name: source-sync
description: Use when the vault owner says "sync <corpus>", "pull new books", "import new transcripts", "any new <X>?", or after an external tool finishes producing a batch on disk. Diffs an external corpus directory against its destination under raw/, classifies every item (genuinely new / already-imported / naming-inconsistent / content-drifted), imports the new ones verbatim — copying, or extracting where the payload is embedded in a container — reports drift for a per-case decision, runs qmd update && qmd embed, appends ONE batch entry to wiki/log.md, and commits locally. Default mode is IMPORT-NEW-ONLY plus REPORT-DRIFT; replacing a drifted file, renaming a legacy file, and any destructive action require explicit per-case confirmation. Configurable per corpus. The wiki-side ingest (source pages, entity/topic updates) is a separate per-source operation and is NOT part of this skill.
---

# Source Sync

One skill for every "an external tool keeps producing files on disk, and `raw/` needs to stay current with it" job — book exports, transcription output, downloaded course media, scraped archives. The vault owner names a **corpus** (a source directory plus a destination folder under `raw/`); the skill works out the delta, imports what is genuinely new, and reports what has drifted so the vault owner decides case by case.

The value is in the classification, not the copy. A naive `cp -n` gets three things wrong every time: it trusts filenames, it cannot see that an already-imported file has since been re-produced (better *or* worse), and it silently drops items the external tool has not finished writing.

**Out of scope:** the wiki-side ingest. This skill lands raw material in `raw/` and stops. Creating `wiki/sources/*.md`, updating entity / topic / insight pages, and glossary one-liners are a deliberate per-source reading pass (CLAUDE.md §Workflows.1) — never automatic, never batched in with a sync.

## When to use

- The vault owner says "sync books", "sync transcripts", "pull new courses", "import new <corpus>", "any new <X>?"
- An external producer has just finished a run and its output directory has grown.
- The vault owner asks "has anything I already imported been updated?" / "check for drift".
- **Skip** if the corpus's `source_dir` is unreachable — surface the path problem, never silently no-op and report "nothing new".
- **One corpus per invocation.** Two corpora means two runs and two commits.

## Corpus config

Each corpus is defined once. Keep the definitions in the **Corpus registry** section at the bottom of this file (or a sibling `corpora.yml` that you create if you prefer a data file — none ships with the template). If the named corpus is not registered, ask for the fields — do not guess a destination or a naming convention.

```yaml
name: <corpus-name>              # what the vault owner calls it out loud
source_dir: "<CORPUS_ROOT>"      # absolute path to the external producer's output dir
item_shape: directory | file     # is one item a directory, or a single file?
payload_glob: "*.md"             # what inside the item is the thing worth importing
dest_dir: "raw/<folder>/"        # destination under raw/ (must be an existing raw folder)
dest_name: "{item}--{payload}.md"  # filename convention at the destination
identity_key: "^[A-Z0-9]{10}-"   # regex for a stable ID in the item name; null if none
qmd_collection: <collection>     # which qmd collection dest_dir belongs to; null if unindexed
completion_signal: "<rule>"      # how you know the producer has FINISHED this item
extract_cmd: null                # null = plain copy; else a command template (see below)
generate_cmd: null               # optional, expensive: produce a payload that does not exist
drift_metric: bytes | sections | none
drift_floor: 1024                # below this, drift is noise
```

Field notes that are easy to get wrong:

| Field | Why it matters |
|---|---|
| `payload_glob` | Producers scatter support files next to the payload (sidecar subtitles, JSON metadata, logs, page dumps, posters, `.part` markers). Exactly one file class is the body worth importing. Everything else is skipped, never copied. |
| `identity_key` | A stable ID in the item's name lets you match src to dst across renames. When there is no ID, matching **must** fall back to content comparison, never to filename similarity alone. |
| `completion_signal` | Most producers write the payload **last**. "No payload yet" therefore means *either* still running *or* dead, and those look identical from the outside. Name the positive signal (payload present, a completion line in the newest log, absence of `.part` / `.tmp` markers). |
| `extract_cmd` | Set when the payload is *inside* a container rather than beside it. Templated on `{payload}` and `{out}`. |
| `generate_cmd` | Set when a payload can be *manufactured* from the item at real wall-clock cost (speech-to-text over media, OCR over scans). Always opt-in per item — see step 5c. |
| `drift_metric` | `bytes` for single-document items; `sections` for assembled multi-part items (count the parts on both sides); `none` for corpora the producer never revisits. |

### Worked example — an e-book export directory

A tool exports one directory per book, each holding the extracted markdown plus its own working files.

```yaml
name: books
source_dir: "<EBOOK_EXPORT_DIR>/out"
item_shape: directory
payload_glob: "*.md"
dest_dir: "raw/books/"
dest_name: "{item}--{payload}.md"          # e.g. A1B2C3D4E5-on-writing-well--On Writing Well.md
identity_key: "^[A-Z0-9]{10}-"             # store ID prefix on the folder name
qmd_collection: books
completion_signal: "a *.md exists in the item dir; if none, read the newest logs/*.log for a completion line"
extract_cmd: null
generate_cmd: null
drift_metric: bytes
drift_floor: 1024
```

Support files to skip: `content.json`, `metadata.json`, `data/`, `pages/`, `logs/`, `front-matter/`, `debug/`, `images/`, verification logs, `.DS_Store`.

### Worked example — a speech-to-text output directory

A transcription pipeline writes a flat directory of sibling files per job: `{name}.txt` (clean prose), plus `.srt` / `.vtt` / `.json` / `.tsv` timestamped variants.

```yaml
name: transcripts
source_dir: "<TRANSCRIBE_DIR>/output"
item_shape: file
payload_glob: "*.txt"                      # the timestamped siblings stay put
dest_dir: "ASK"                            # non-deterministic: raw/meetings/ OR raw/web-clippings/
dest_name: "ASK"                           # "{YYYY-MM-DD} - {Title}.md" or "video-{slug}.md"
identity_key: null                         # no stable ID — dedup by content
qmd_collection: "meetings or web-articles, per item"
completion_signal: "the .txt exists and is non-empty"
extract_cmd: null
generate_cmd: "<transcribe command> --output_dir <TRANSCRIBE_DIR>/output '{media}'"
drift_metric: none
drift_floor: 0
```

This corpus has a **non-deterministic destination**: the same output directory feeds two different raw folders. Filename hints suggest; the vault owner decides (step 3).

It also hits the **embedded-destination** case hardest. A transcript for a video clipping does not land as a standalone file — it gets pasted into the body of an existing `raw/web-clippings/video-{slug}.md`, under frontmatter and a `## Transcript` heading. So the same output is byte-identical to nothing at the destination while already being fully imported. Match it by name reference, per step 2 bucket 2, before anything else.

### Worked example — a downloaded course directory

A downloader writes one directory per course, one media file per lesson (`NNN-Lesson Title.mp4`). The English transcript is **embedded inside the container**, not written as a sidecar — the sidecars on disk are translations only.

```yaml
name: courses
source_dir: "<COURSE_DOWNLOAD_DIR>/downloads"
item_shape: directory
payload_glob: "*.mp4"
dest_dir: "raw/web-clippings/"
dest_name: "video-course-{slug}.md"        # ONE assembled file per course, lessons as sections
identity_key: null                         # match by slug similarity, confirm before minting
qmd_collection: web-articles
completion_signal: "no .part / .ytdl markers in the item dir"
extract_cmd: "ffmpeg -v error -y -i '{payload}' -map 0:s:m:language:eng -f srt '{out}'"
generate_cmd: "<transcribe command> '{payload}'"   # for lessons with no embedded caption track
drift_metric: sections                     # lesson count vs '## NNN -' sections in the dest file
drift_floor: 1
```

**Do not go hunting for a sidecar that does not exist.** When a downloader embeds one language and sidecars the rest, no amount of globbing will find the embedded one — extraction is the only path. Verify the claim once with a container probe, then encode it in `completion_signal` so the next run does not re-litigate it.

## Steps

### 1. Inventory the source

Walk `source_dir`. For each entry:

- **Skip** anything that is not an item per `item_shape`, plus the corpus's known support files and in-progress markers.
- Locate the payload via `payload_glob`. Record the payload path, byte size, and mtime.
- If `identity_key` is set, extract the ID from the item name. Capture the remaining slug too.
- **An item with no payload is not automatically dead** — classify it (step 1a).

**Item shape tells you nothing about liveness.** Sibling contents vary wildly between generations of the same producer; a bare-ID directory can hold a complete item and a richly-populated one can be a corpse. The `completion_signal` is the only evidence.

**Ground-truth the listing.** If your shell commands route through a wrapper that summarizes or compresses output, build the inventory with Python (or bypass the wrapper). Such wrappers have been observed returning *fabricated* file entries for directories they were asked to list — including files of exactly the shape the model expected to find.

### 1a. No payload? Distinguish in-flight from abandoned

Producers write the payload last, so mid-run and dead are indistinguishable from the outside. Read the item's own progress evidence before classifying:

| Signal | State | Action |
|---|---|---|
| Producer's log holds a completion line, but no payload | **Anomaly** | Surface it. Never silently skip. |
| No completion line, log mtime **recent** | **In flight** | Report as running; re-check at step 4. |
| No completion line, log mtime **stale**, or no log at all | **Abandoned** | Skip — and say so in the report. |

```python
import glob, os, time

def classify_no_payload(item_dir, log_glob="logs/*.log",
                        done_marker="Export complete.", stale_after_s=1800):
    logs = sorted(glob.glob(os.path.join(item_dir, log_glob)), key=os.path.getmtime)
    if not logs:
        return "abandoned"
    newest = logs[-1]
    if done_marker in open(newest, encoding="utf-8", errors="replace").read():
        return "complete-but-payload-missing"      # anomaly - surface, do not skip
    return "in-flight" if time.time() - os.path.getmtime(newest) < stale_after_s else "abandoned"
```

If the producer keeps no logs, substitute an equivalent positive signal: absence of `.part` / `.tmp` / lock files, a manifest whose declared item count is satisfied, or a payload whose size has stopped changing across two reads a minute apart.

### 1b. Probe the container when the payload is embedded (`extract_cmd` set)

When `extract_cmd` is set, `payload_glob` matches the **container**, not the thing you want. "The payload exists" is therefore never evidence that the payload is *extractable* — a media file always exists; the caption track inside it may not. **Probe every container for the target stream during inventory**, before the report:

```bash
# does this container carry the target subtitle stream at all?
ffprobe -v error -select_streams s -show_entries stream_tags=language -of csv=p=0 "<payload>"
```

Record the result per part. Parts whose container lacks the target stream are **generation candidates**, not failures — the underlying content is present (spoken audio with no caption track), it simply has to be manufactured (step 5c) rather than extracted. They belong in the **NEEDS GENERATION** bucket at step 3, while the vault owner is still deciding what to approve.

Doing this at import time instead is a step too late: the approval has already been given, and the only thing left is to record the gap in the assembled file's "Missing parts" section (step 5b). That section is the backstop, not the mechanism. Probe first.

Because `payload_glob` always matches for such a corpus, the "items with no payload" condition of step 1a never fires for it — the probe is the *only* thing that can populate NEEDS GENERATION here.

### 2. Classify each item against the destination

First match wins:

1. **`already-imported (id match)`** — `identity_key` matches a destination file. Do not skip yet: compute drift (step 2b).
2. **`already-imported (embedded)`** — the payload is not a standalone file at the destination; it was **wrapped into** one. A destination file references this payload **by name**, either in frontmatter (`transcript_source:`, `source_file:`) or in a body attribution line (`**Source:** ... {name}.<ext>`) under the content heading. Grep the destination folder for the payload's basename. Split the match two ways:

   - **Body present** — more than ~50 lines of content beyond the attribution preamble → **already imported**. Skip.
   - **Preamble only** — the heading and the attribution line with nothing under them → a **stub**. Report it as a generation / backfill candidate (step 5c). **Surface, do not action** — filling a stub is a per-item operation, not a bulk sync.

   **The size pre-filter and `diff` in bucket 3 cannot see this case.** The destination wraps the payload in frontmatter and a header, so it is never byte-identical, and `identity_key` is typically `null` for exactly the corpora that hit it. Without this bucket the item falls straight through to `new` and gets re-imported as a second, duplicate file sitting next to the copy already living inside the destination — silently, and precisely the failure this skill exists to prevent.
3. **`already-imported (content match)`** — no ID, but a destination file is byte-identical. Cheap pre-filter on size, confirm with `diff`:

   ```bash
   find "<dest_dir>" -name '*.md' -size <N>c      # exact-size candidates
   diff -q "<payload>" "<candidate>"              # confirm
   ```

   **This is the case filename matching always misses.** The same item routinely lands under a completely different destination name — a machine-generated job name on one side, a human-readable dated title on the other, byte-identical bodies.
4. **`naming-inconsistent`** — a destination file clearly holds this item but under the legacy / pre-convention name (title matches, ID prefix absent). Report as FYI. **Do not rename** — renaming changes paths, breaks wikilinks, and needs `git mv` to keep history. Rename only on an explicit follow-on request.
5. **`new`** — no match by ID, by embedded reference, by content, or by title. Import candidate.

Near-identical-but-not-equal (sizes differ by a handful of bytes) is *drift*, not a new item. Route it to step 2b.

### 2b. Drift detection

External producers re-run over the same items. A re-production can be **fuller** (good), **structurally broken** (bad), or **truncated to a stub** (worst, and the easiest to mistake for an upgrade). Both directions of delta matter.

For `drift_metric: bytes`, `delta = src_size - dst_size`:

| Bucket | Condition | Default |
|---|---|---|
| **[STUB]** critical | `dst_size < src_size * 0.10` | Strongly recommend REPLACE. A destination that is a tiny fraction of the source is almost always a failed earlier import (a table-of-contents-only stub against a full body). |
| **[SRC-LARGER]** gain | `delta >= +drift_floor` | Recommend REPLACE after one sanity check. Usually a fuller re-extraction. Low risk — but confirm it is fuller, not merely padded. |
| **[DST-LARGER]** | `delta <= -drift_floor` | **INVESTIGATE. Both verdicts are possible.** Either the destination is the older *fuller* extraction (keep it), or the destination is *structurally broken* — real content tail-dumped under one section while the rest are stubs — and the smaller source is correct. Same delta direction, opposite conclusions. |
| **[TRIVIAL]** | `abs(delta) < drift_floor` | Defer indefinitely. Whitespace, line endings, encoding noise. Report as a single tally line, never per file. |

For `drift_metric: sections`, `delta = source_part_count - destination_section_count`:

| Bucket | Condition | Default |
|---|---|---|
| **[MORE-PARTS]** | `delta > 0` | Recommend RE-BUILD — new parts arrived since the first import (a multi-part item that finished downloading after import). |
| **[IN-SYNC]** | `delta == 0` | Skip. |
| **[FEWER-PARTS]** | `delta < 0` | INVESTIGATE. Usually a partly-deleted source or a re-release with fewer parts. **Never auto-shrink an imported file.** |

**Investigation patterns** — run at least one before recommending anything on a [DST-LARGER] or [FEWER-PARTS] case:

1. **Per-section word-fraction test (the reliable discriminator).** For each `## ` section, compute its share of the document's total words. A healthy long document's largest section is roughly 10-17%. **Broken** looks like one section — typically an index, notes, or appendix — holding well over 40% in the destination but not in the source: the whole body has been tail-dumped under stub sections. Adopt this over line-gap heuristics, which false-positive on documents with legitimately long index tails.
2. **Heading sequence comparison.** `grep -n '^## ' src dst`. Identical headings in identical order on both sides means the delta lives in prose volume, not structure.
3. **Content-position spot check.** Read the same offset (say line 40 of the body) in both files. If the source has narrative where the destination has sidebars, boilerplate, or promotional fragments, the source is correct.
4. **Placeholder-marker proliferation.** Repeated `[BLANK_PAGE]`-style markers, or `Notes 2` through `Notes 10` with nothing between them, indicate a skeleton, not an extraction.
5. **Word count is not quality.** A scrambled file padded with front-matter and marketing bulk can be larger than a clean, correctly-ordered extraction.

**Adjudicated cases.** Once a drift case is decided, record it so the next run does not re-investigate — it *will* keep flagging otherwise. Append entries under the corpus's heading in the **Adjudicated cases** section at the bottom of this file, one line each:

```
- <item id or name> - KEEP-DST | REPLACED (YYYY-MM-DD). Delta at decision: <+/-N>. Evidence: <the test that decided it, in one clause>.
```

**A verdict can expire.** Producers ship new generations. When an item previously adjudicated KEEP-DST reappears as [SRC-LARGER] with a meaningful delta, that is a *new* generation — re-investigate rather than trusting the old verdict. This has happened in the field: a keep-destination decision was correct for months, then a later export shipped genuinely fuller content plus a section the destination lacked, and the right answer flipped.

### 3. Report and propose

Surface everything in one block. Every item in the inventory appears in exactly one bucket — nothing is silently dropped.

- **NEW (will import)** — count plus per item: name, payload size, derived destination filename.
- **DRIFT [STUB] / [SRC-LARGER] / [DST-LARGER]** — count plus per item: src size, dst size, delta, investigation findings, a recommendation. Skip items already in the adjudicated list.
- **DRIFT [TRIVIAL]** — one tally line.
- **ALREADY IMPORTED (content match under a different name)** — count plus `src -> dst` per item.
- **ALREADY IMPORTED (embedded in a destination file)** — count plus `src -> dst` per item.
- **STUB (embedded reference, no body — FYI, no action)** — count plus `src -> dst`. These are generation / backfill candidates for a separate per-item run.
- **NAMING-INCONSISTENT (FYI, no action)** — count plus side-by-side sizes.
- **IN FLIGHT** — name each, with the age of its newest progress evidence. State plainly that these get re-checked before the run ends.
- **ABANDONED** — count only. Never report an item as abandoned without having read its completion signal.
- **ANOMALY** — completion signalled but no payload. Needs the vault owner's eyes.
- **NEEDS GENERATION** — items with no payload, plus the parts whose container failed the step-1b probe, that `generate_cmd` could produce — with the wall-clock estimate (step 5c).

If `NEW == 0` and no non-trivial drift: report "nothing new, no drift" and stop. **No commit.**

Otherwise **wait for the vault owner's go-ahead** before any write. They may approve a whole bucket, approve individual items, defer in-flight items until the producer finishes, or ask for more investigation on a [DST-LARGER] case.

**When the destination is non-deterministic** (one source directory feeding several raw folders), confirm per item before copying:

1. **Category** — which raw folder, or skip.
2. **Date** — `YYYY-MM-DD`. If the vault owner cannot recall, use `XXXX-XX-XX` as a placeholder. **Never guess, and never substitute file mtime** — mtime is when the file was *processed*, not when the event happened.
3. **Title** — usually the source name minus machine noise (`Copy of ` prefixes, bracketed job IDs, duplicated series prefixes).

Filename heuristics may *suggest* a category. They must never *decide* one: a training recording, a conference talk, and a long internal meeting are indistinguishable by filename, and the failure is silent.

### 4. Re-scan for late completions (mandatory)

Before importing anything, re-walk `source_dir` and re-run step 1a on every item that was `in-flight` or payload-less. Any item that now has a payload is a **new item** — verify completion, fold it into the NEW bucket, and tell the vault owner it landed mid-run.

This is not a nicety. In the field, an opening scan classified a large item as abandoned and its payload landed **26 seconds later**; only the re-scan caught it. No time threshold can catch a completion that happens during your run — only a second look can.

### 5. Import

#### 5a. Copy (`extract_cmd: null`)

```bash
cp "<source_dir>/<item>/<payload>" "<dest_dir>/<dest_name>"
```

**Verbatim. `raw/` is immutable, and immutability starts at the door.** No frontmatter wrapping, no header injection, no reflowing, no encoding cleanup, no "while I'm here" tidying. Metadata gets added at wiki-ingest time, in `wiki/`, where it belongs.

For an approved drift replacement, overwrite in place — the destination path was fixed at first import and does not change.

Copy only the payload. Support files, timestamped sibling formats, metadata JSON, posters, and logs stay in the source directory (the timestamped transcript variants in particular are worth keeping there for moment-finding via grep — they are just not vault material).

#### 5b. Extract (`extract_cmd` set)

Run the templated command per payload, **normalize the output**, then assemble.

**Extractors emit their native intermediate format, not prose.** A caption / subtitle extraction lands as numbered cues with timestamp lines, and rolling captions repeat each line across consecutive cues. Landing that raw into `raw/` is the payload rendered unreadable — and unsearchable, because qmd indexes `1` and `00:00:01,000 --> 00:00:04,000` alongside the words. `raw/` is immutable, so the mess is permanent. Normalize before writing:

- Drop sequence indices (a line that is only digits) and timestamp lines (anything containing `-->`).
- Join the surviving lines of each cue, then **collapse consecutive duplicate cues** — a real artifact of rolling captions, not a transcription error.
- Collapse whitespace runs, then re-wrap after sentence-ending punctuation (`.` `!` `?`) so the body reads as sentences rather than one unbroken line.

```python
import re

def clean_cues(raw: str) -> str:
    """Cue format -> flowing text: drop indices/timestamps, collapse repeated
    cues, wrap after sentence-ending punctuation."""
    cues = []
    for block in re.split(r'\n\s*\n', raw.strip()):
        lines = [s for s in (l.strip() for l in block.splitlines())
                 if s and not re.match(r'^\d+$', s) and '-->' not in s]
        if lines:
            cues.append(' '.join(lines))
    deduped = [c for i, c in enumerate(cues) if i == 0 or c != cues[i - 1]]
    text = re.sub(r'\s+', ' ', ' '.join(deduped)).strip()
    return re.sub(r'([.!?]) ', r'\1\n', text)
```

An extraction is **not** a verbatim copy — it produces a new file, so it carries a minimal provenance header naming the tool, the source path, and the date, and stating plainly what the body is: *verbatim captions, lightly cleaned (sequence indices and timestamps stripped, consecutive duplicate cues collapsed)*. Keep the header to three or four lines; it is a receipt, not a summary — and that one clause is what tells a future reader the body was touched, and exactly how far.

Assembled multi-part items get one destination file with the parts as `## NNN - Title` sections. Make the assembly **idempotent** (overwrite the whole destination file) so that a [MORE-PARTS] re-build is the same command run again, with no merge logic to get wrong.

Any part whose payload cannot be extracted goes into a trailing "Missing parts" section in the assembled file, named. **A part that cannot be extracted is a flag, not a deletion** — dropping it silently makes the gap invisible forever.

#### 5c. Generate (`generate_cmd` set) — opt-in, background, cost stated first

Some items have no payload and never will, but one can be manufactured from the item itself (speech-to-text over media, OCR over scans). This costs real wall-clock time, so it is **opt-in per item** and never bundled into a bulk approval.

**Pre-flight before asking** — a broken dependency should not waste a confirmation:

- **Exercise the dependency, do not merely locate it.** Run `<tool> --version` and check the exit code. `which <tool>` passes happily on a binary that dies at load time from a stale shared-library version — this exact failure has burned a run.
- Check for an output-name collision, and ask before overwriting.
- Check free disk. Media plus intermediates eats gigabytes.

Then state, in one block: what will be processed, the wall-clock estimate (express it as a fraction of item duration for media — measure it once on your hardware and write the rule into the corpus config), where the input lands, where the output lands. **Wait for a yes.**

Run it in the background (`run_in_background: true`) and report the job ID. **Do not poll** — the runtime notifies on completion. A synchronous run blocks the conversation for tens of minutes.

Two environment traps worth pre-empting, because both kill a job *before* any real work happens and both produce confusing errors:

- **Stale environment variables that point at deleted paths.** TLS CA-bundle and certificate variables left behind by uninstalled security tooling make a model or dependency download fail with a path error that has nothing to do with the task. Run the job with those variables explicitly unset; the fallback (the bundled CA set) works regardless.
- **Library search paths.** Prefixing `PATH` gets you the *binary* of a keg-only / non-default toolchain install, but not the shared libraries a dependency loads at runtime via rpath. Set the fallback library path to the same install's `lib` directory too, or you get a wall of load warnings and a silently degraded code path.

**Do not hardcode the payload extension.** Fetch and download tools pick the best available format per source — `.mp4` on one item, `.webm` or `.m4a` on the next. Resolve the actual filename after the download returns and use that.

**If the generator does not label speakers** (most speech-to-text runs without diarization) and the source is a conversation rather than a monologue, write a one-line caveat into the destination file above the body:

```markdown
> **Speaker-attribution caveat.** This transcript carries no speaker labels; every turn boundary is inferred. Treat attributions as probable, not established.
```

That block is the whole point of this rule: it makes any downstream misattribution self-disclosing instead of silently authoritative. Skip it for a single-speaker source — no boundaries, nothing to get wrong.

Sanity-check that the generated payload is non-empty before landing it. A source with no audio track yields an empty transcript without erroring.

**Reclaim disk at the end of the run.** After step 8's commit has landed, name the media this run downloaded — filename plus size — and **offer to delete it**. Rules for the offer:

- **Default is keep.** Only delete on an explicit yes. Holding the original lets the vault owner re-generate later with different settings (a larger model, speaker diarization), and if the source URL was recorded, re-downloading is cheap anyway.
- **Only the files this run produced.** Never bulk-sweep the producer's input directory — it may hold hand-placed files this skill did not download and must not touch.
- **Never offer to delete the generated payloads.** Those are the substance.

This is a one-line offer at the very end, not a blocking step. Skip it and the input directory grows unbounded and unmentioned — in the field it reached roughly 10 GB before anyone noticed.

### 6. Refresh the index

```bash
qmd update && qmd embed
```

Run this whenever the destination sits in an indexed collection — which is every raw folder **registered as a qmd collection**. Check CLAUDE.md §Retrieval for the current list, because not every folder under `raw/` is registered by default: `raw/bookmarks.md` is deliberately excluded, and a folder the vault has only recently started using (`raw/research/`, say) may never have been registered at all. Skip this step only for a corpus whose `qmd_collection` is `null`.

If the destination folder turns out not to be on that list, that is a signal to register it — `qmd collection add <name> ./raw/<folder>` — not to leave the corpus permanently unindexed. Declaring a `qmd_collection` for an unregistered folder and running the refresh is a silent no-op for that folder: the command succeeds and indexes nothing.

`embed` is not optional. Without it, `lex` queries find the new content — which is exactly what masks the bug — while `vec` and `hyde` queries silently miss it. Replacements report as updated plus an orphaned content hash cleaned; that is the expected pattern, not an error.

### 7. Append ONE entry to `wiki/log.md`

**One entry for the whole batch.** Not one per file. The log is the cross-session memory of what has already been synced; a run that imports twelve items is one operation.

Newest at top:

```markdown
---

## [YYYY-MM-DD] sync | N new <corpus> items from <producer>

- **Trigger**: the vault owner: *"<exact phrase>"*.
- **Method**: diffed `<source_dir>` against `<dest_dir>`; matched by <id prefix | content diff>. N new, M already-imported, K naming-inconsistent, J drift candidates.
- **Imported (N)**:
  - `<dest_dir>/<file>` (size, and part count if assembled)
  - ...
- **Replaced (R)** *(only if drift replacements were approved)*:
  - `<file>`: dst_size -> src_size (delta +/-N) - <the test that decided it>
- **Held back**: items the vault owner declined or deferred, and why.
- **qmd**: <collection> X -> X+N, embedded.
- **FYI, not actioned**: naming-inconsistent files; trivial drift tally; items needing generation; in-flight items to re-check next run.
- **Wiki ingest (not actioned)**: new items are ingest candidates - `wiki/sources/*.md` plus entity/topic pages are a separate per-source reading pass.
```

If a replacement substantively changed an item whose `wiki/sources/` page was written from the old version, name that page in the FYI line as a re-ingest candidate. Do not re-ingest it here.

### 8. Commit

Stage only the affected raw files plus the log:

```bash
git add <dest_dir>/<affected-files> wiki/log.md
git commit -m "raw: sync N <corpus> items (<short summary>)"
```

**Never push.** If both new imports and drift replacements were approved in one session, prefer **separate commits per category** — "what arrived" and "what changed under us" are different events and a future reader needs to tell them apart.

## Rules

- **The source is read-only.** Never modify, move, or delete anything under `source_dir`. The producer owns it.
- **Default mode is IMPORT-NEW-ONLY plus REPORT-DRIFT.** Three follow-ons are never automatic and each needs an explicit request: replacing a drifted destination file, renaming a legacy destination file, and the wiki-side ingest.
- **Dedup by content, not by filename.** With no `identity_key`, a size pre-filter plus `diff` is mandatory before declaring anything new — and a grep for the payload's basename across the destination folder, because a payload already embedded inside a destination file will never be byte-identical to it.
- **Copies are verbatim.** `raw/` is immutable; nothing is reformatted on the way in. Extractions and assemblies are generated files: their output is normalized (step 5b) and they carry a short provenance header saying so — that is the only exception.
- **When the payload is embedded, probe the container during inventory.** An unextractable part must reach the report as a generation candidate, not surface mid-import after approval.
- **Never classify a payload-less item as abandoned without reading its completion signal.** The producer writes the payload last.
- **The step-4 re-scan is mandatory.** A producer can finish mid-run.
- **[DST-LARGER] drift is never auto-resolved.** Investigate first; both verdicts are live.
- **Generation is opt-in per item, with the cost stated before the ask, and always in the background.**
- **`qmd update && qmd embed` after any write** to an indexed collection.
- **One log entry per batch. One commit per category. Stage specific paths. Never push.**
- **Do not ingest into `wiki/`.** Raw material is queryable via qmd as-is; synthesis is a separate deliberate pass.

## Caps

| Item | Cap |
|---|---|
| Corpora per invocation | 1 |
| Items imported per run | unlimited — the natural unit is "what is new since the last sync" |
| Items generated per run | opt-in per item; state cost each time |
| Diff samples surfaced per investigation | 10 lines per file |
| Content preview per item when confirming a non-deterministic destination | first 5-10 lines plus last 3 lines — enough for the vault owner to identify the item without pasting the body |
| Background jobs | 1 at a time unless the vault owner asks for parallelism |
| Files touched per commit | imported/replaced raw files plus `wiki/log.md` — no wiki entity / topic / source pages |

## Common mistakes

- **Trusting filenames over content.** The single most expensive error. A machine-named job output and a human-named destination file can be byte-identical; a filename match can be two different items with the same title. Size pre-filter plus `diff` decides, nothing else.
- **Missing a payload already embedded inside a destination file.** The destination wraps it in frontmatter and a header, so no size or `diff` check will ever match, and the item is re-imported as a silent duplicate. Grep the destination folder for the payload's basename first (step 2, bucket 2).
- **Landing an extractor's native output unprocessed.** Sequence indices, `-->` timestamp lines and duplicated rolling-caption cues make the body unreadable and pollute the qmd index — permanently, because `raw/` is immutable. Normalize, then write.
- **Silently replacing a drifted file.** A replacement destroys the previously imported version. Every replacement is a per-case decision by the vault owner, with the deciding evidence recorded in the log entry.
- **Treating a truncated stub re-extraction as an upgrade.** "Newer" is not "better". A producer can re-emit an item as a table-of-contents skeleton or a scrambled tail-dump. Run the per-section word-fraction test before believing a delta.
- **Forgetting `qmd embed`.** `lex` keeps working, which is precisely why this bug survives — `vec` and `hyde` queries silently miss everything imported since.
- **Per-file log entries instead of one batch entry.** Twelve log entries for one sync buries the log and still fails to say what the *run* did.
- **Calling a payload-less item abandoned.** It is probably still being written. Read the completion signal, then re-scan at step 4.
- **Inferring liveness from item shape.** Sibling contents vary between producer generations; no shape is diagnostic in either direction.
- **Skipping the re-scan** because the opening scan "was only a few minutes ago". Twenty-six seconds was enough to lose an item once.
- **Auto-routing by filename heuristic** when the destination is non-deterministic. Heuristics suggest; the vault owner decides.
- **Guessing a date from file mtime.** That is the processing date, not the event date. Use `XXXX-XX-XX` and let the vault owner fix it later.
- **Hunting for a sidecar file that does not exist.** When a producer embeds one language in the container and sidecars only the others, extraction is the only path. And if your shell wrapper "finds" the sidecar you were hoping for, verify with Python before believing it.
- **Copying support files** — metadata JSON, logs, page dumps, posters, timestamped sibling formats, in-progress markers. Only the payload crosses into `raw/`.
- **Adding frontmatter to a verbatim copy.** Wrap with metadata at wiki-ingest time.
- **Hardcoding a downloaded file's extension.** Resolve it after the download returns.
- **Pre-flight that locates a dependency instead of exercising it.** A broken binary passes `which` and fails at load.
- **Polling a background job.** Wait for the completion notification; `sleep` loops burn the conversation.
- **Dropping a part that could not be extracted** instead of listing it in a "Missing parts" section. A named gap can be filled later; an invisible one cannot.
- **Discovering an unextractable part at import time.** Probing the container is an inventory step. Found after approval, the gap can only be recorded; found before, it can be acted on in the same run.
- **Leaving the producer's input directory to grow.** Offer deletion of this run's downloads at the end — keep by default, this run's files only, never a bulk sweep.
- **Re-investigating an adjudicated case every run.** Record the verdict — but re-open it when a later generation flips the delta direction.
- **Treating sub-threshold drift as actionable.** It is whitespace and encoding noise.
- **Running the wiki ingest in the same pass.** Substantive reading is not a sync operation. Surface ingest candidates in the log entry and stop.
- **Pushing the commit.** Never push from this skill.

## Corpus registry

Register each corpus here (one heading per corpus, holding the YAML block from *Corpus config*). Nothing is registered by default — the three blocks under *Corpus config* are worked examples to copy and adapt, not live configuration. If the vault owner names an unregistered corpus, ask for the fields, run the sync, then write the resulting config into this section so the next run is one word.

## Adjudicated cases

One subsection per corpus. Append a line per decided drift case, in the format given in step 2b. Keep the evidence clause short enough to read at a glance and specific enough to defend the verdict a year later.

**Empty by design** — entries accumulate as drift cases are decided. Nothing to backfill here on a fresh vault.

## Iteration log

- **v1** — initial version. Collapses four corpus-specific sync skills (an e-book export sync, a transcription-output sync, a course-download sync, and a per-item transcript generator) into one configurable skill, because all four were the same workflow with different nouns: diff an external producer's directory against `raw/`, classify every item, import the new ones verbatim, report drift for a per-case decision, refresh qmd, log once, commit. The differences that looked corpus-specific turned out to be four config fields — payload glob, identity key, extract command, drift metric. Carried forward intact from the four originals: the payload-written-last liveness classifier plus mandatory re-scan (which recovered an item that completed 26 seconds after the opening scan); content-based dedup (a job-named output that already lived under a human-named destination file, byte-identical, which filename matching missed); the four-bucket byte-drift model with the per-section word-fraction discriminator for the destination-larger case (where the same delta direction supports opposite verdicts); the adjudicated-cases ledger plus its expiry rule (a keep-destination verdict was later invalidated by a fuller producer generation); the embedded-payload extraction path with its "the sidecar does not exist" warning, its cue-cleaning normalization (indices and timestamps stripped, consecutive duplicate cues collapsed, re-wrapped on sentence punctuation), and its inventory-time container probe that routes unextractable parts into NEEDS GENERATION *before* the approval rather than after; the embedded-destination match that stops a payload already wrapped inside a destination file from being re-imported as a silent duplicate; and the opt-in, cost-stated, background-only generation path with its pre-flight, environment, and speaker-attribution guards plus its closing disk-reclamation offer.
