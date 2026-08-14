#!/usr/bin/env python3
"""Layer 2 of the wiki-lint pipeline.

Checks the vendor tool (markdownlint-obsidian) can't do correctly today:

1. WIKI001 — table-pipe-in-wikilink. Obsidian renderer quirk: [[X|Y]]
   inside a markdown table cell breaks the table because the inner `|`
   is parsed as a column separator. Fix: \\| escape.

2. WIKI002 — broken wikilink (Obsidian-fuzzy resolution). Vendor tool
   uses path-based resolution from --vault-root, which can't handle
   this vault's mixed [[sources/foo]] (wiki-implicit) + [[raw/notes-import/foo]]
   (vault-absolute) link conventions. Reimplements Obsidian's name-fuzzy
   resolution (path suffix-match against vault file index). Links to
   attachment file types (see ATTACHMENT_EXTENSIONS) are exempt: `assets/*`
   is gitignored, so those targets are absent from every clone and the check
   could only ever report which machine ran it.

3. WIKI003 — broken wikilink anchor. The #anchor part of a wikilink
   must resolve to an actual heading or glossary term in the target file.

4. FM001/FM002/FM003/FM004 — frontmatter schema:
   - source: title, raw_sources, date_ingested, date_original
   - entity: title, entity_type, first_seen, source_count
   - topic: title, source_count
   - insight: title, confidence, date_created
   - plan: title, status, date_created, date_updated
   - project: title, status, date_started, date_updated
   - overview: date_updated

5. FM005 — raw_sources path resolution. Every path in a source page's
   `raw_sources:` list must point to an actual file on disk.

6. RU001 — Recent-updates callout discipline. In-scope synthesis pages
   (insights / topics / plans / projects) must have a `> **Recent
   updates** (most recent first):` callout immediately after frontmatter,
   with at least one dated entry. Latest entry's date must be ≥
   `date_updated`. RU004 (warning) — callout must hold at most 3 dated
   entries; older entries roll off (history lives in wiki/log.md + git).

7. PROV001 (warning) — inline raw-link discipline. Synthesis pages
   (entities / topics / insights / plans) should cite via wiki source
   pages, not link directly to `raw/`. Exception: project pages'
   "Related sources" section may link to raw.

8. WIKI007 (warning) — anchor-prose source-count consistency.
   On topic pages that use the "<N> sources anchor this page" prose
   convention, the spelled-out number must match `source_count:`
   in frontmatter AND the bullet count under `## Sources`. Catches
   the case where a new source is added and frontmatter + bullets are
   bumped but the prose count is forgotten.

9. WIKI008 (advisory; `--report cross-links` only) — cross-link
   completeness (source → topic). When a source page's tracked H2
   section (`## Related wiki`, `## Cross-references`, `## Related sources`,
   `## Related`, `## See also`) wikilinks `[[topics/T]]`, T's body must
   mention the source back. Surfaces the case where a new source's
   tracked-section links to a topic but the topic page does not enumerate
   the source — but it ALSO surfaces many wiki-convention-OK cases (a
   source can name a topic as related without the topic having to
   reciprocate). Run on demand:
       python3 .claude/scripts/wiki-lint.py --report cross-links
   Recommended during ingest review for new sources; not a default gate.

Reports (separate flags, not run by default). Two reasons they stay out of CI:
they are judgement calls rather than contract violations, AND `symmetry` /
`duplicates` are O(N^2) walks over the page set — around 30s on a mid-size vault,
which is real money to pay on every push for output nobody reads per-commit.

- `--report symmetry`          — cross-reference symmetry analysis (advisory)
- `--report orphans`           — orphan page detection (advisory)
- `--report tags`              — off-taxonomy tag frequency report (advisory)
- `--report glossary-coverage` — bold terms with no glossary entry/link (Q2, advisory)
- `--report schema`            — per-type body-structure adherence (Q4, advisory)
- `--report duplicates`        — near-duplicate pages by lexical similarity (Q5, advisory)
- `--report stale`             — pages the vault's own data says went stale (advisory)

Output:
- Human-readable to stdout (file:line:col CODE message)
- GitHub Actions annotations to stdout when --gh-annotations is passed

Per-instance config (OPTIONAL):
This file is meant to be byte-identical across every wiki instance so upstream
fixes arrive by plain checkout rather than hand-merge. The handful of values
that genuinely differ per instance therefore live OUTSIDE it, in an optional
JSON file at `<vault-root>/.claude/scripts/wiki-lint.config.json`. Absent
config = these built-in defaults, exactly; a fresh clone lints with zero setup.
Malformed config = exit 2 with a message, never a silent fall back to defaults.
See `load_config` / `apply_config` for the knobs and their merge-vs-replace
semantics.

Exit codes:
- 0 = clean (no errors; warnings allowed)
- 1 = errors found
- 2 = script failure (e.g. vault not found, or bad wiki-lint.config.json)

Usage:
  python3 .claude/scripts/wiki-lint.py wiki/
  python3 .claude/scripts/wiki-lint.py wiki/ --gh-annotations
  python3 .claude/scripts/wiki-lint.py --check table-pipe wiki/
  python3 .claude/scripts/wiki-lint.py --report orphans
  python3 .claude/scripts/wiki-lint.py --report symmetry
  python3 .claude/scripts/wiki-lint.py --report tags
  python3 .claude/scripts/wiki-lint.py --report glossary-coverage
  python3 .claude/scripts/wiki-lint.py --report schema
  python3 .claude/scripts/wiki-lint.py --report duplicates
  python3 .claude/scripts/wiki-lint.py --report stale
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

# ---------- Models ----------

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

# Per-type required frontmatter keys, per CLAUDE.md schemas.
# REQUIRED_KEYS_BY_TYPE   — missing field = ERROR (CI fails). Hard contract.
# RECOMMENDED_KEYS_BY_TYPE — missing field = WARNING. Quality signal, not gate.
REQUIRED_KEYS_BY_TYPE: dict[str, list[str]] = {
    "source": ["title", "raw_sources"],
    "entity": ["title", "entity_type"],
    "topic": ["title"],
    "insight": ["title", "confidence"],
    "plan": ["title", "status"],
    "project": ["title", "status"],
    "overview": [],
    # Special pages — minimal requirements
    "index": [],
    "log": [],
    "log-archive": [],
    "glossary": [],
    "glossary-split": [],
    "backlog": [],
    "digest": [],
    "manifest": [],
    "reflections-log": [],
}

RECOMMENDED_KEYS_BY_TYPE: dict[str, list[str]] = {
    "source": ["date_ingested", "date_original"],
    "entity": ["first_seen", "source_count"],
    "topic": ["source_count"],
    "insight": ["date_created"],
    "plan": ["date_created", "date_updated"],
    "project": ["date_started", "date_updated"],
    "overview": ["date_updated"],
}

# Pages where Recent-updates callout is required (in-scope per CLAUDE.md).
RECENT_UPDATES_TYPES = {"insight", "topic", "plan", "project"}
RECENT_UPDATES_MAX_ENTRIES = 3  # RU004: older entries roll off (history is in wiki/log.md + git)

# Synthesis-page folders that should NOT contain direct `[[raw/...]]` links
# (the one-hop-to-raw provenance rule). Project pages are excluded — they
# legitimately link to raw meeting notes from "Related sources".
NO_DIRECT_RAW_FOLDERS = ("/wiki/entities/", "/wiki/topics/", "/wiki/insights/", "/wiki/plans/")

CHECK_TABLE_PIPE = "table-pipe"
CHECK_BROKEN_WIKILINK = "broken-wikilink"
CHECK_FRONTMATTER = "frontmatter-schema"
CHECK_RAW_SOURCES = "raw-sources-paths"
CHECK_RECENT_UPDATES = "recent-updates"
CHECK_PROVENANCE = "provenance"
CHECK_ANCHOR_PROSE = "anchor-prose-count"
# WIKI008 / cross-link-completeness lives behind `--report cross-links` only —
# it surfaces a mix of real drift and convention-OK asymmetries and would be
# too noisy as a default gate. See module docstring §9.
ALL_CHECKS = [
    CHECK_TABLE_PIPE,
    CHECK_BROKEN_WIKILINK,
    CHECK_FRONTMATTER,
    CHECK_RAW_SOURCES,
    CHECK_RECENT_UPDATES,
    CHECK_PROVENANCE,
    CHECK_ANCHOR_PROSE,
]

# WIKI007 — anchor-prose source-count parsing.
# Spelled-out cardinal numbers (English) up to 30 + digit form.
WORD_TO_INT: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "twenty-one": 21, "twenty-two": 22,
    "twenty-three": 23, "twenty-four": 24, "twenty-five": 25,
    "twenty-six": 26, "twenty-seven": 27, "twenty-eight": 28,
    "twenty-nine": 29, "thirty": 30,
}

# Matches "<N> sources anchor this page" — N is either a digit run or a word.
# Case-insensitive so "Eight sources" and "eight sources" both match.
ANCHOR_PROSE_RE = re.compile(
    r"\b([A-Za-z][A-Za-z-]*|\d+)\s+sources?\s+anchor(?:s)?\s+this\s+page\b",
    re.IGNORECASE,
)

REPORT_SYMMETRY = "symmetry"
REPORT_ORPHANS = "orphans"
REPORT_CROSS_LINKS = "cross-links"
REPORT_TAGS = "tags"
REPORT_GLOSSARY = "glossary-coverage"  # Q2
REPORT_SCHEMA = "schema"               # Q4
REPORT_DUPLICATES = "duplicates"       # Q5
REPORT_STALE = "stale"                 # pruning-visibility report

# Thresholds for `--report stale`, in days. Deliberately generous: this report
# exists to make pruning VISIBLE, not to nag. A page tripping STALE-A is making
# a claim about itself (`status: active`) that its own date contradicts.
# Per-instance via `stale_thresholds` in wiki-lint.config.json — a vault worked
# daily and one worked monthly do not share a definition of "stale".
STALE_ACTIVE_DAYS = 90       # active plan/project untouched for a quarter
STALE_SYNTHESIS_DAYS = 365   # insight/topic untouched for a year (informational)

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# Self-set alarms a corpus writes and nothing rings, e.g. "Re-check Nov 2026",
# "revisit 2027-01-15". The date may be ISO or "Mon YYYY"; label punctuation
# (`**Revisit:**`, `Revisit —`) and up to three connectives ("in", "by",
# "after", "this again in") may sit between the verb and the date.
#
# Two exclusions are deliberate, and they are the same judgement made twice:
#
# - Bare "review" is out. Wikis use it as a NOUN in historical page titles
#   ("Architecture Review Mar 2021"), which records the past rather than
#   setting an alarm for the future. "review again" stays in — the adverb is
#   what turns it back into an alarm.
# - Past-tense and third-person forms are out (revisited / rechecked /
#   revisits). "We revisited Mar 2021 and confirmed the call" records an alarm
#   that already rang; matching it rings forever on work that is finished.
#
# Quarters ("revisit in Q1 2027") are out of scope on purpose: a quarter is a
# per-instance convention, not a date, and guessing its start month would be a
# fabrication in a report whose whole value is that its dates are real.
RECHECK_RE = re.compile(
    r"\b(?:re-?check(?:ing)?|revisit(?:ing)?|review again)\b[\s,:*—–-]*"
    r"(?:\b(?:at|in|by|on|around|this|again|after|before|next|come|from)\b\s*){0,3}"
    r"(?:\bthe\b\s*)?"
    r"(?:"
    #   "Mar 2027" / "March 2027" / "Mar. 2027". The \b closes the month token,
    #   so "Marketing 2027" and "Maybe 2027" are not read as dates.
    r"(?P<mon>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?"
    r"|Dec(?:ember)?)\b\.?\s+(?P<year>20\d{2})"
    #   "2027-01-15" — the only date format this template mandates anywhere
    #   (frontmatter, Recent-updates, decisions logs), so it has to match here.
    r"|(?P<iso>20\d{2}-\d{2}-\d{2})"
    r")",
    re.IGNORECASE,
)

# Inline code spans, stripped before alarm-matching: `re-check Jan 2020` inside
# backticks documents the syntax rather than setting an alarm in it.
INLINE_CODE_RE = re.compile(r"`[^`]*`")

# Append-only chronological records, skipped by STALE-B. An alarm written into
# a log entry cannot be silenced by editing it — the entry records what was
# said on a date — so it would ring forever with no legal way to fix it.
STALE_B_SKIP_PREFIXES = ("wiki/log/",)
STALE_B_SKIP_FILES = ("wiki/log.md", "wiki/reflections-log.md")

# Frontmatter date keys STALE-A / STALE-C consult, in order. `date_updated` is
# only RECOMMENDED for these types (soft FM006), never required, so keying on
# it alone leaves schema-legal pages silently unassessed.
STALE_DATE_KEYS_BY_TYPE = {
    "plan": ("date_updated", "date_created"),
    "project": ("date_updated", "date_started"),
    "insight": ("date_updated", "date_created"),
    "topic": ("date_updated", "date_created"),
}
ALL_REPORTS = [
    REPORT_SYMMETRY, REPORT_ORPHANS, REPORT_CROSS_LINKS, REPORT_TAGS,
    REPORT_GLOSSARY, REPORT_SCHEMA, REPORT_DUPLICATES, REPORT_STALE,
]

# Synthesis folders for the advisory body/coverage/dupe reports.
SYNTH_FOLDERS = ("insights", "topics", "plans", "projects", "sources")

# Canonical H2 sections per page type (CLAUDE.md body schemas). Soft / advisory.
EXPECTED_H2_BY_TYPE: dict[str, list[str]] = {
    "project": ["Vision & origin", "Scope", "Stakeholder positions",
                "Decisions log", "Open questions", "Action items", "Related"],
}

# Common bold labels / words that are NOT glossary-term candidates (Q2 noise floor).
_NON_TERM_BOLD = {
    "why", "what", "how", "fix", "note", "important", "scope", "status", "goal",
    "ask", "tldr", "tl;dr", "summary", "context", "trigger", "target page",
    "what to add", "why it matters", "why deferred", "source trigger", "hold condition",
    "recent updates", "v2-fix", "v3-fix", "new", "open questions", "action items",
}
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "her", "his", "are", "was",
    "has", "have", "not", "but", "all", "its", "into", "they", "their", "which",
    "wiki", "page", "source", "note", "2026", "2025", "2024",
}

# Tag taxonomy per CLAUDE.md. Time tags (bare 4-digit years, q<N>-YYYY) are
# open-ended and detected by pattern rather than enumerated here.
TAG_TAXONOMY: dict[str, set[str]] = {
    "domain": {"work", "career", "personal", "family", "tech", "finance"},
    "activity": {"meeting", "training", "conference", "project"},
    "role": {"leadership", "management", "craft"},
    "type": {"1-on-1", "brainstorm", "retrospective", "goal-setting"},
}
_KNOWN_TAGS: set[str] = {t for tags in TAG_TAXONOMY.values() for t in tags}
_TIME_TAG_RE = re.compile(r"^(q[1-4]-\d{4}|\d{4})$")

# Orphan-report allow-list: pages that are intentional entry points and so have
# no inbound wikilinks by design. Hoisted out of report_orphans() so it can be
# replaced per instance (glossary split filenames and root pages are named
# differently in every wiki). Advisory report only — never gates CI.
ORPHAN_ALLOWLIST: set[str] = {
    "wiki/overview.md",
    "wiki/index.md",
    "wiki/glossary.md",
    "wiki/glossary/frameworks.md",
    "wiki/glossary/vernacular.md",
    "wiki/log.md",
    "wiki/backlog.md",
    "wiki/reflections-log.md",
    "wiki/notes-import-manifest.md",
}

# Extensions of files that live in the attachments folder, which .gitignore
# excludes (`assets/*`). WIKI002 cannot judge a link to one of these: the byte
# it would resolve against is deliberately absent from every clone, so on CI
# EVERY such link reports broken while on the author's disk EVERY one passes.
# That is not a lint result, it is a report of which machine ran the linter — so
# an unresolvable link to one of these is skipped rather than flagged.
#
# The cost is real and bounded: a mistyped attachment name goes uncaught. The
# alternative costs more — the check as written fails only in CI, where it looks
# like a broken link and gets "fixed" by deleting a correct link.
#
# An instance that TRACKS its attachments should set `attachment_extensions` to
# [] in wiki-lint.config.json; there the files are present in CI and the check
# is meaningful. Kept as data, not a regex, so config can replace it wholesale.
ATTACHMENT_EXTENSIONS = {
    # images
    "png", "jpg", "jpeg", "gif", "bmp", "svg", "webp", "heic", "heif", "avif", "tiff",
    # audio / video
    "mp3", "wav", "m4a", "ogg", "flac", "aac", "mp4", "mov", "mkv", "webm", "avi",
    # documents an attachments folder collects
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "pages", "numbers", "key",
}


# ---------- Optional per-instance config ----------
#
# wiki-lint.py gates CI in every wiki instance, and it is only takeable by plain
# checkout if all copies are byte-identical. So the values that genuinely differ
# per instance are lifted out of this file into an OPTIONAL JSON file at
# <vault-root>/.claude/scripts/wiki-lint.config.json.
#
# Three rules this obeys:
#   1. Config absent  -> the built-in defaults above, byte-for-byte identical
#      behaviour. A fresh clone of the template lints with zero setup.
#   2. Config malformed / unreadable / has an unknown key -> exit 2 with a
#      clear message. It NEVER silently falls back to defaults: a linter that
#      quietly stops enforcing is worse than no linter, and a typo'd key that
#      does nothing is exactly that failure.
#   3. Merge-vs-replace is decided per knob and justified at the point of use in
#      apply_config(). Getting that backwards is the bug that silently switches
#      a rule off, so it is spelled out rather than left to the reader.
#
# What deliberately has NO config key, so it cannot be weakened from config:
#   ALL_CHECKS / --check          (the gate set itself)
#   RECENT_UPDATES_TYPES          (RU001 scope — emptying it would kill RU001)
#   RECENT_UPDATES_MAX_ENTRIES    (RU004 threshold)
#   NO_DIRECT_RAW_FOLDERS         (PROV001 scope)
#   RECOMMENDED_KEYS_BY_TYPE      (FM006 keys)
#   SYNTH_FOLDERS                 (which folders the reports walk)
#   severities                    (no way to demote an error to a warning)
# and REQUIRED_KEYS_BY_TYPE is union-only (see apply_config), so no config value
# can shorten a built-in type's required-key list and thereby dodge FM004.
# ATTACHMENT_EXTENSIONS is settable, and note which direction that cuts: the
# built-in value is the PERMISSIVE one, so config can only ever tighten WIKI002
# here, never loosen it.

CONFIG_RELPATH = ".claude/scripts/wiki-lint.config.json"

# Top-level keys the config may set. Anything else (except `_`-prefixed comment
# keys) is a hard error — an unrecognised key is almost always a typo, and a
# typo that silently does nothing is the exact failure mode this guards.
_CONFIG_KEYS = frozenset({
    "extra_page_types",
    "extra_stopwords",
    "extra_non_term_bold",
    "tag_taxonomy",
    "orphan_allowlist",
    "expected_h2_by_type",
    "attachment_extensions",
    "stale_thresholds",
})


class ConfigError(Exception):
    """Unreadable / malformed / unsafe config. Always fatal, never swallowed."""


def _cfg_str_list(where: str, value: object) -> list[str]:
    """Validate `value` is a JSON array of non-empty strings."""
    if not isinstance(value, list):
        raise ConfigError(
            f"`{where}` must be an array of strings, got {type(value).__name__}"
        )
    out: list[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(
                f"`{where}[{i}]` must be a non-empty string, got {item!r}"
            )
        out.append(item.strip())
    return out


def _cfg_str_list_map(where: str, value: object) -> dict[str, list[str]]:
    """Validate `value` is a JSON object mapping strings -> arrays of strings."""
    if not isinstance(value, dict):
        raise ConfigError(
            f"`{where}` must be an object of string-arrays, got {type(value).__name__}"
        )
    out: dict[str, list[str]] = {}
    for k, v in value.items():
        if not isinstance(k, str) or not k.strip():
            raise ConfigError(f"`{where}` has a non-string or empty key: {k!r}")
        out[k.strip()] = _cfg_str_list(f"{where}.{k}", v)
    return out


def load_config(vault_root: Path) -> dict | None:
    """Read <vault-root>/.claude/scripts/wiki-lint.config.json, or None if absent.

    Resolved against the VAULT ROOT — the same `--vault-root` the linter already
    uses for wikilink resolution and raw_sources checks — and never against
    __file__, because CI invokes this script by path from the repo root and a
    shared copy could live anywhere on disk.

    Raises ConfigError on anything malformed. Callers must not catch-and-default.
    """
    cfg_path = vault_root / CONFIG_RELPATH
    # `is_file()` is False for a DIRECTORY and for a BROKEN SYMLINK, so gating on
    # it returned None for both and silently fell back to built-in defaults —
    # the one behaviour this docstring promises never happens. Test existence
    # instead and let read_text() raise: IsADirectoryError and FileNotFoundError
    # are both OSError, so both surface as a loud ConfigError.
    if not cfg_path.exists() and not cfg_path.is_symlink():
        return None
    # Messages carry no path: main() already prefixes CONFIG_RELPATH, and
    # printing it twice made every failure read as if two files were at fault.
    try:
        raw = cfg_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ConfigError(f"could not be read: {e}") from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(
            f"must contain a JSON object at the top level, "
            f"got {type(data).__name__}"
        )
    unknown = sorted(k for k in data if not k.startswith("_") and k not in _CONFIG_KEYS)
    if unknown:
        raise ConfigError(
            f"has unknown key(s): {', '.join(unknown)}. "
            f"Known keys: {', '.join(sorted(_CONFIG_KEYS))} "
            "(keys starting with `_` are treated as comments and ignored)"
        )
    return data


def apply_config(data: dict) -> None:
    """Fold a validated config into the module-level defaults.

    Rebinds module globals rather than threading a settings object through every
    check — deliberately the smallest possible diff against a 1,600-line file
    that three repos gate CI on. Called once, from main(), before any check or
    report runs.
    """
    global REQUIRED_KEYS_BY_TYPE, _STOPWORDS, _NON_TERM_BOLD
    global TAG_TAXONOMY, _KNOWN_TAGS, ORPHAN_ALLOWLIST, EXPECTED_H2_BY_TYPE
    global ATTACHMENT_EXTENSIONS, STALE_ACTIVE_DAYS, STALE_SYNTHESIS_DAYS

    # MERGE (union-only). New `type:` values are registered so they stop tripping
    # FM003 — instances name their special pages differently (one calls its
    # journal `reflections-log`, the next calls it `field-notes-log`). Merge
    # rather than replace because the six synthesis schemas are the SHARED
    # contract, not an instance's business. And the per-type key lists union
    # rather than overwrite: config can only ever ADD a required key, never drop
    # one, which makes FM004 non-weakenable from config by construction.
    if "extra_page_types" in data:
        extra = _cfg_str_list_map("extra_page_types", data["extra_page_types"])
        merged = dict(REQUIRED_KEYS_BY_TYPE)
        for ptype, keys in extra.items():
            base = merged.get(ptype, [])
            # Order-preserving union: built-ins first, then config-only additions.
            merged[ptype] = base + [k for k in keys if k not in base]
        REQUIRED_KEYS_BY_TYPE = merged

    # MERGE. Noise floors for the advisory duplicate / glossary-coverage reports.
    # The built-ins ("the", "and", "recent updates") are language- and
    # schema-level noise that is wrong in no instance; an instance only ever
    # needs to ADD its own org names and house vocabulary. Replacing would
    # silently re-admit English stopwords as duplicate-detection signal, which
    # would quietly wreck the report instead of failing visibly.
    if "extra_stopwords" in data:
        _STOPWORDS = _STOPWORDS | {
            w.lower() for w in _cfg_str_list("extra_stopwords", data["extra_stopwords"])
        }
    if "extra_non_term_bold" in data:
        _NON_TERM_BOLD = _NON_TERM_BOLD | {
            w.lower()
            for w in _cfg_str_list("extra_non_term_bold", data["extra_non_term_bold"])
        }

    # REPLACE. The tag taxonomy is a CLOSED vocabulary — `--report tags` flags
    # everything outside it — and it is wholly instance-specific (one wiki's
    # domains are career/family/finance, the next one's are logistics/fleet/safety).
    # Merging would union in the defaults, so every instance would silently
    # accept the template's tags as on-taxonomy and the report would stop
    # catching drift. Replace is the only semantics that keeps it a real gate.
    # Lowercased on load because report_tags compares against lowercased tags.
    if "tag_taxonomy" in data:
        taxonomy = _cfg_str_list_map("tag_taxonomy", data["tag_taxonomy"])
        TAG_TAXONOMY = {k: {t.lower() for t in v} for k, v in taxonomy.items()}
        _KNOWN_TAGS = {t for tags in TAG_TAXONOMY.values() for t in tags}

    # REPLACE. The orphan allow-list is a list of THIS instance's entry-point
    # pages, named by path. Merging would keep template paths that do not exist
    # here (dead weight) and, worse, permanently whitelist a filename this
    # instance may genuinely want flagged as an orphan. A whitelist you cannot
    # shrink is not a whitelist.
    if "orphan_allowlist" in data:
        ORPHAN_ALLOWLIST = set(
            _cfg_str_list("orphan_allowlist", data["orphan_allowlist"])
        )

    # REPLACE. Canonical H2 sections per page type are a whole body-schema
    # contract copied from each instance's own CLAUDE.md, not an additive list —
    # merging two instances' section lists would demand sections from both and
    # report every page as non-conforming.
    if "expected_h2_by_type" in data:
        EXPECTED_H2_BY_TYPE = _cfg_str_list_map(
            "expected_h2_by_type", data["expected_h2_by_type"]
        )

    # REPLACE, and the one knob whose useful setting is the EMPTY list. It names
    # the file types this instance keeps out of git; merging would make that
    # unsayable, because an instance that tracks its attachments could never
    # shrink the list back and WIKI002 would stay switched off for images
    # forever. Replace lets `[]` mean "my attachments are committed, check them".
    if "attachment_extensions" in data:
        ATTACHMENT_EXTENSIONS = {
            e.lstrip(".").lower()
            for e in _cfg_str_list("attachment_extensions", data["attachment_extensions"])
        }

    # REPLACE, per key. `--report stale` is advisory and never gates CI, so these
    # are a reporting preference rather than a rule — a vault worked daily and
    # one worked monthly genuinely disagree about when `status: active` starts
    # to look like a lie. Each key is optional; an absent one keeps its built-in.
    if "stale_thresholds" in data:
        th = data["stale_thresholds"]
        if not isinstance(th, dict):
            raise ConfigError(
                f"`stale_thresholds` must be an object, got {type(th).__name__}"
            )
        unknown = sorted(k for k in th if k not in ("active_days", "synthesis_days"))
        if unknown:
            raise ConfigError(
                f"`stale_thresholds` has unknown key(s): {', '.join(unknown)}. "
                "Known keys: active_days, synthesis_days"
            )
        for key in ("active_days", "synthesis_days"):
            if key not in th:
                continue
            v = th[key]
            # bool is a subclass of int, so `true` would otherwise read as 1 —
            # a typo silently becoming a one-day threshold is the worst outcome.
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ConfigError(
                    f"`stale_thresholds.{key}` must be a positive integer number "
                    f"of days, got {v!r}"
                )
            if key == "active_days":
                STALE_ACTIVE_DAYS = v
            else:
                STALE_SYNTHESIS_DAYS = v


@dataclass
class Finding:
    file: str
    line: int
    col: int
    code: str
    severity: str
    message: str


# ---------- Vault file index (for fuzzy wikilink resolution) ----------


def build_vault_index(vault_root: Path) -> dict[str, list[Path]]:
    """Walk the entire vault and index files for Obsidian-fuzzy resolution.

    Obsidian's resolution rule: a wikilink target X resolves to a file
    whose path *ends with* `X.md` (or `X` if X already has an extension),
    where the match aligns on a path-segment boundary.

    Index keys are normalized: lowercase, forward-slash separators.
    """
    index: dict[str, list[Path]] = {}
    skip_dirs = {".git", ".obsidian", "node_modules", ".lint-tmp", ".cache"}
    for root, dirs, files in os.walk(vault_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            p = Path(root) / name
            try:
                rel = p.relative_to(vault_root)
            except ValueError:
                continue
            key = str(rel).replace(os.sep, "/").lower()
            index.setdefault(key, []).append(p)
            # Also index by basename for bare [[X]] resolution
            basename = name.lower()
            index.setdefault(basename, []).append(p)
    return index


def resolve_wikilink(target: str, vault_root: Path, index: dict[str, list[Path]]) -> list[Path]:
    """Return list of vault files matching a wikilink target.

    target: the part before any `#anchor` or `|alias`, e.g. "sources/foo"
            or "foo.png" or "raw/notes-import/Some Note Title".
    Returns: list of matching paths (0 = broken, 1 = unique, 2+ = ambiguous).
    """
    needle = target.strip().replace("\\", "/")
    if not needle:
        return []
    # If no extension, assume .md. Use a tight extension regex so version-y
    # filenames like "Project 4.1 Review" aren't misread as having an extension.
    last_segment = needle.rsplit("/", 1)[-1]
    has_ext = bool(re.search(r"\.[A-Za-z][A-Za-z0-9]{1,4}$", last_segment))
    candidates_keys = []
    if has_ext:
        candidates_keys.append(needle.lower())
    else:
        candidates_keys.append(f"{needle.lower()}.md")

    seen: set[Path] = set()
    matches: list[Path] = []

    # Tier 1: exact path match (relative to vault root)
    for key in candidates_keys:
        for p in index.get(key, []):
            if p not in seen:
                seen.add(p)
                matches.append(p)

    # Tier 2: path suffix match — any path whose relative form ends with needle
    if not matches:
        for key in candidates_keys:
            for indexed_key, paths in index.items():
                if indexed_key.endswith("/" + key):
                    for p in paths:
                        if p not in seen:
                            seen.add(p)
                            matches.append(p)

    # Tier 3: basename match (Obsidian fuzzy)
    if not matches:
        last_segment = candidates_keys[0].rsplit("/", 1)[-1]
        for p in index.get(last_segment, []):
            if p not in seen:
                seen.add(p)
                matches.append(p)

    return matches


def _is_attachment_target(target: str) -> bool:
    """True if a wikilink target names a file type kept out of git.

    Deliberately does NOT reuse resolve_wikilink's extension regex, which caps an
    extension at four characters and so reads `.numbers` as no extension at all.
    Here the extension is whatever follows the final dot of the last path
    segment; a leading-dot name (`.gitignore`) has none.
    """
    last_segment = target.rsplit("/", 1)[-1]
    dot = last_segment.rfind(".")
    if dot <= 0:
        return False
    return last_segment[dot + 1:].lower() in ATTACHMENT_EXTENSIONS


# ---------- Markdown structure helpers ----------


CODE_FENCE_RE = re.compile(r"^(\s*)(```|~~~)")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
WIKILINK_RE = re.compile(r"\[\[([^\[\]\n]+?)\]\]")
DATE_PREFIX_RE = re.compile(r"^\s*[->\s*]*\**\s*(\d{4}-\d{2}-\d{2})")
ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def iter_lines_with_context(text: str):
    """Yield (lineno, line, in_code_block, in_frontmatter) for each line."""
    in_code = False
    fence = None
    in_frontmatter = False
    fm_seen = False
    for i, line in enumerate(text.splitlines(), start=1):
        # Frontmatter: --- on line 1 opens, next --- closes
        if i == 1 and line.strip() == "---":
            in_frontmatter = True
            fm_seen = True
            yield i, line, False, in_frontmatter
            continue
        if in_frontmatter and line.strip() == "---":
            yield i, line, False, in_frontmatter
            in_frontmatter = False
            continue
        if in_frontmatter:
            yield i, line, False, in_frontmatter
            continue
        # Code fences
        m = CODE_FENCE_RE.match(line)
        if m:
            mark = m.group(2)
            if not in_code:
                in_code = True
                fence = mark
            elif mark == fence:
                in_code = False
                fence = None
            yield i, line, True, False
            continue
        yield i, line, in_code, False


# ---------- Checks ----------


def check_table_pipe(path: Path, text: str, findings: list[Finding]) -> None:
    """Flag [[X|Y]] inside a markdown table cell where the inner `|` is unescaped.

    A line is "in a table" if it starts with `|` (possibly with leading
    whitespace) and contains another `|`. Inside such a line, find any
    `[[X|Y]]` pattern where the alias separator is a bare `|` (not `\\|`).
    """
    for lineno, line, in_code, in_fm in iter_lines_with_context(text):
        if in_code or in_fm:
            continue
        if not TABLE_ROW_RE.match(line):
            continue
        for m in WIKILINK_RE.finditer(line):
            inner = m.group(1)
            # Only piped wikilinks have an inner `|`. We're looking for
            # an unescaped pipe — i.e. a `|` not preceded by `\`.
            for pipe_match in re.finditer(r"(?<!\\)\|", inner):
                col = m.start() + 1 + 2 + pipe_match.start()  # 2 = len("[[")
                findings.append(
                    Finding(
                        file=str(path),
                        line=lineno,
                        col=col,
                        code="WIKI001",
                        severity=SEVERITY_ERROR,
                        message=(
                            "Unescaped `|` inside wikilink in table cell — "
                            "Obsidian renders this as broken table. "
                            "Use `\\|` to escape."
                        ),
                    )
                )
                break  # one finding per wikilink is enough


def check_broken_wikilinks(
    path: Path,
    text: str,
    vault_root: Path,
    index: dict[str, list[Path]],
    findings: list[Finding],
) -> None:
    """Flag wikilinks whose target can't be resolved via Obsidian-fuzzy match."""
    for lineno, line, in_code, in_fm in iter_lines_with_context(text):
        if in_code or in_fm:
            continue
        # Skip inline code spans — find them and blank them out
        scrubbed = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line)
        for m in WIKILINK_RE.finditer(scrubbed):
            inner = m.group(1)
            target_part = re.split(r"\\?\|", inner, maxsplit=1)[0]
            target = target_part.split("#", 1)[0].strip()
            if not target:
                continue
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            matches = resolve_wikilink(target, vault_root, index)
            if not matches and _is_attachment_target(target):
                # Untracked by design — see ATTACHMENT_EXTENSIONS. Note this is
                # reached only when resolution ALREADY failed, so a link that
                # does resolve keeps every downstream check unchanged.
                continue
            if not matches:
                col = m.start() + 1
                findings.append(
                    Finding(
                        file=str(path),
                        line=lineno,
                        col=col,
                        code="WIKI002",
                        severity=SEVERITY_ERROR,
                        message=f"Broken wikilink: target `{target}` not found in vault",
                    )
                )
                continue
            anchor = ""
            if "#" in target_part:
                raw_anchor = target_part.split("#", 1)[1]
                anchor = re.split(r"\\?\|", raw_anchor, maxsplit=1)[0].strip()
            if anchor and len(matches) == 1:
                target_file = matches[0]
                if target_file.suffix == ".md":
                    try:
                        target_text = target_file.read_text(encoding="utf-8")
                    except Exception:
                        continue
                    if not _anchor_exists(target_text, anchor):
                        col = m.start() + 1
                        findings.append(
                            Finding(
                                file=str(path),
                                line=lineno,
                                col=col,
                                code="WIKI003",
                                severity=SEVERITY_ERROR,
                                message=(
                                    f"Broken wikilink anchor: `#{anchor}` "
                                    f"not found in `{target}`"
                                ),
                            )
                        )


def _anchor_exists(target_text: str, anchor: str) -> bool:
    """Check whether an anchor matches any heading in the target file."""
    needle = anchor.strip().lower()
    needle_compact = re.sub(r"[^a-z0-9]+", "", needle)
    for line in target_text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not m:
            continue
        heading = m.group(2).strip().lower()
        if heading == needle:
            return True
        heading_compact = re.sub(r"[^a-z0-9]+", "", heading)
        if heading_compact == needle_compact and needle_compact:
            return True
    return False


def check_frontmatter_schema(path: Path, text: str, findings: list[Finding]) -> None:
    """Verify per-type required frontmatter keys."""
    fm = _extract_frontmatter(text)
    if fm is None:
        rel = str(path).replace(os.sep, "/")
        if any(seg in rel for seg in ("/wiki/sources/", "/wiki/insights/", "/wiki/topics/", "/wiki/plans/", "/wiki/projects/", "/wiki/entities/")):
            findings.append(
                Finding(
                    file=str(path),
                    line=1,
                    col=1,
                    code="FM001",
                    severity=SEVERITY_ERROR,
                    message="Missing frontmatter (required for synthesis pages)",
                )
            )
        return
    fm_dict, fm_lineno = fm
    page_type = fm_dict.get("type", "").strip()
    if not page_type:
        findings.append(
            Finding(
                file=str(path),
                line=fm_lineno,
                col=1,
                code="FM002",
                severity=SEVERITY_WARNING,
                message="Missing `type:` field in frontmatter",
            )
        )
        return
    required = REQUIRED_KEYS_BY_TYPE.get(page_type)
    if required is None:
        findings.append(
            Finding(
                file=str(path),
                line=fm_lineno,
                col=1,
                code="FM003",
                severity=SEVERITY_WARNING,
                message=f"Unknown frontmatter `type: {page_type}` (no schema registered)",
            )
        )
        return
    for key in required:
        if not fm_dict.get(key):
            findings.append(
                Finding(
                    file=str(path),
                    line=fm_lineno,
                    col=1,
                    code="FM004",
                    severity=SEVERITY_ERROR,
                    message=f"Frontmatter `type: {page_type}` requires `{key}`",
                )
            )
    recommended = RECOMMENDED_KEYS_BY_TYPE.get(page_type, [])
    for key in recommended:
        if not fm_dict.get(key):
            findings.append(
                Finding(
                    file=str(path),
                    line=fm_lineno,
                    col=1,
                    code="FM006",
                    severity=SEVERITY_WARNING,
                    message=f"Frontmatter `type: {page_type}` recommends `{key}`",
                )
            )


def check_raw_sources_paths(
    path: Path,
    text: str,
    vault_root: Path,
    findings: list[Finding],
) -> None:
    """For source pages, verify each `raw_sources:` path resolves to an actual file."""
    fm = _extract_frontmatter(text)
    if fm is None:
        return
    fm_dict, fm_lineno = fm
    if fm_dict.get("type", "").strip() != "source":
        return
    # Pull the raw_sources block (list-formatted) directly from text
    paths = _extract_list_field(text, "raw_sources")
    if not paths:
        return  # FM004 already catches missing raw_sources
    for raw_path, lineno in paths:
        # Skip non-repo paths: absolute paths, home-relative, URLs. The FM005
        # contract is in-repo provenance; external references are out of scope.
        if raw_path.startswith(("/", "~", "http://", "https://", "file://")):
            continue
        candidate = (vault_root / raw_path).resolve()
        if not candidate.exists():
            findings.append(
                Finding(
                    file=str(path),
                    line=lineno,
                    col=1,
                    code="FM005",
                    severity=SEVERITY_ERROR,
                    message=f"raw_sources path does not exist: `{raw_path}`",
                )
            )


def check_recent_updates_callout(path: Path, text: str, findings: list[Finding]) -> None:
    """Verify in-scope synthesis pages have a Recent updates callout."""
    fm = _extract_frontmatter(text)
    if fm is None:
        return
    fm_dict, _ = fm
    page_type = fm_dict.get("type", "").strip()
    if page_type not in RECENT_UPDATES_TYPES:
        return
    # Find frontmatter close, then scan for the callout in next ~20 non-empty lines
    lines = text.splitlines()
    fm_close = None
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=2):
            if line.strip() == "---":
                fm_close = i
                break
    if fm_close is None:
        return  # Malformed — FM001 will fire
    callout_re = re.compile(r"^\s*>\s*\*\*Recent updates\*\*", re.IGNORECASE)
    callout_found = False
    callout_line = None
    # Allow up to 20 lines between fm-close and the callout (whitespace + comments tolerated)
    for i in range(fm_close, min(fm_close + 20, len(lines))):
        line = lines[i] if i < len(lines) else ""
        if callout_re.match(line):
            callout_found = True
            callout_line = i + 1
            break
        # Stop scanning when we hit the H1 — callout must come before H1
        if re.match(r"^#\s+", line):
            break
    if not callout_found:
        findings.append(
            Finding(
                file=str(path),
                line=fm_close + 1,
                col=1,
                code="RU001",
                severity=SEVERITY_ERROR,
                message=(
                    f"`type: {page_type}` page is missing the `> **Recent updates** "
                    f"(most recent first):` callout (must appear after frontmatter, before H1)"
                ),
            )
        )
        return
    # Validate latest entry date >= date_updated (if both present)
    fm_date_raw = fm_dict.get("date_updated", "").strip().strip("\"'")
    if not fm_date_raw or not ISO_DATE_RE.match(fm_date_raw):
        return  # No date_updated to compare; FM004 may handle it
    fm_date = fm_date_raw[:10]
    # Collect dates from callout entries (whole contiguous blockquote)
    entry_dates: list[str] = []
    if callout_line is None:
        return
    for i in range(callout_line, len(lines)):
        line = lines[i] if i < len(lines) else ""
        if line.strip() == "" or not line.lstrip().startswith(">"):
            break
        m = DATE_PREFIX_RE.match(line)
        if m:
            entry_dates.append(m.group(1))
    if len(entry_dates) > RECENT_UPDATES_MAX_ENTRIES:
        findings.append(
            Finding(
                file=str(path),
                line=callout_line,
                col=1,
                code="RU004",
                severity=SEVERITY_WARNING,
                message=(
                    f"Recent updates callout has {len(entry_dates)} entries "
                    f"(max {RECENT_UPDATES_MAX_ENTRIES} — older entries roll off; "
                    f"history lives in wiki/log.md and git)"
                ),
            )
        )
    if not entry_dates:
        findings.append(
            Finding(
                file=str(path),
                line=callout_line,
                col=1,
                code="RU002",
                severity=SEVERITY_WARNING,
                message="Recent updates callout has no dated entries",
            )
        )
        return
    latest = max(entry_dates)
    if latest < fm_date:
        findings.append(
            Finding(
                file=str(path),
                line=callout_line,
                col=1,
                code="RU003",
                severity=SEVERITY_WARNING,
                message=(
                    f"Recent updates latest entry `{latest}` is older than "
                    f"frontmatter `date_updated: {fm_date}`"
                ),
            )
        )


def check_inline_provenance(path: Path, text: str, findings: list[Finding]) -> None:
    """Warn on direct `[[raw/...]]` links in non-source/non-project synthesis pages.

    CLAUDE.md provenance rule: synthesis pages should cite via wiki source
    pages (one hop). Direct raw-links bypass the abstraction. Project pages
    are exempt — their "Related sources" section legitimately links to raw.
    """
    rel = str(path).replace(os.sep, "/")
    if not any(seg in rel for seg in NO_DIRECT_RAW_FOLDERS):
        return
    for lineno, line, in_code, in_fm in iter_lines_with_context(text):
        if in_code or in_fm:
            continue
        scrubbed = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line)
        for m in WIKILINK_RE.finditer(scrubbed):
            inner = m.group(1)
            target_part = re.split(r"\\?\|", inner, maxsplit=1)[0]
            target = target_part.split("#", 1)[0].strip()
            if target.startswith("raw/"):
                findings.append(
                    Finding(
                        file=str(path),
                        line=lineno,
                        col=m.start() + 1,
                        code="PROV001",
                        severity=SEVERITY_WARNING,
                        message=(
                            f"Direct raw-link `{target}` in synthesis page — "
                            f"prefer linking via wiki/sources/ (one-hop provenance rule)"
                        ),
                    )
                )


def _parse_count_token(token: str) -> int | None:
    """Parse a count token (digit run or English number-word) to int.

    Handles "8", "Eight", "EIGHT", "twenty-one". Returns None if not parseable.
    """
    token = token.strip().lower()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    return WORD_TO_INT.get(token)


def _count_sources_bullets(text: str) -> int | None:
    """Count top-level bullet items under a `## Sources` H2 heading.

    Returns the count, or None if the page has no `## Sources` section.
    Stops counting at the next H2 (or higher) heading. Only counts lines
    that start with `- ` at the very beginning (no leading whitespace) —
    nested bullets and continuation lines are excluded.
    """
    lines = text.splitlines()
    in_sources = False
    count = 0
    for line in lines:
        if re.match(r"^##\s+Sources\s*$", line, re.IGNORECASE):
            in_sources = True
            continue
        if in_sources:
            # Stop at next H1 / H2 (sibling/parent heading)
            if re.match(r"^#{1,2}\s+\S", line):
                break
            # Only count top-level bullets (no leading whitespace before `-`)
            if re.match(r"^-\s+\S", line):
                count += 1
    return count if in_sources else None


def check_anchor_prose_count(path: Path, text: str, findings: list[Finding]) -> None:
    """WIKI007 — Topic pages: prose `<N> sources anchor this page` must match
    frontmatter `source_count:` AND the bullet count under `## Sources`.

    Only fires on topic pages that actually use the "<N> sources anchor" prose
    convention. Pages that don't use this phrasing are silently skipped.
    """
    fm = _extract_frontmatter(text)
    if fm is None:
        return
    fm_dict, _ = fm
    if fm_dict.get("type", "").strip() != "topic":
        return
    fm_count_raw = fm_dict.get("source_count", "").strip().strip("\"'")
    if not fm_count_raw or not fm_count_raw.isdigit():
        return  # FM006 already warns on missing source_count for topics
    fm_count = int(fm_count_raw)

    lines = text.splitlines()
    # Find frontmatter close
    fm_close = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=2):
            if line.strip() == "---":
                fm_close = i
                break
    if not fm_close:
        return

    # Scan first ~80 body lines for the anchor-prose pattern. Skip blockquotes
    # (Recent updates callout often mentions counts) and code fences.
    prose_count: int | None = None
    prose_lineno: int | None = None
    in_code = False
    fence: str | None = None
    for i in range(fm_close, min(fm_close + 80, len(lines))):
        line = lines[i] if i < len(lines) else ""
        m_fence = CODE_FENCE_RE.match(line)
        if m_fence:
            mark = m_fence.group(2)
            if not in_code:
                in_code = True
                fence = mark
            elif mark == fence:
                in_code = False
                fence = None
            continue
        if in_code:
            continue
        if line.lstrip().startswith(">"):
            continue  # blockquote (e.g. Recent updates)
        m = ANCHOR_PROSE_RE.search(line)
        if m:
            parsed = _parse_count_token(m.group(1))
            if parsed is not None:
                prose_count = parsed
                prose_lineno = i + 1
                break

    if prose_count is None:
        return  # Page doesn't use this convention — out of scope

    bullets = _count_sources_bullets(text)

    counts: dict[str, int] = {
        "frontmatter source_count": fm_count,
        "prose": prose_count,
    }
    if bullets is not None:
        counts["## Sources bullets"] = bullets

    if len(set(counts.values())) > 1:
        parts = ", ".join(f"{k}={v}" for k, v in counts.items())
        findings.append(
            Finding(
                file=str(path),
                line=prose_lineno or 1,
                col=1,
                code="WIKI007",
                severity=SEVERITY_WARNING,
                message=(
                    f"Source-count mismatch on topic page: {parts}. "
                    f"Update the prose / frontmatter / Sources bullets to agree."
                ),
            )
        )


TRACKED_SECTION_NAMES: set[str] = {
    "related wiki",
    "cross-references",
    "cross references",
    "related sources",
    "related",
    "see also",
}

# WIKI008 recency window. Source pages with `date_ingested` older than this
# are skipped in the default check (run `--report cross-links` for the full
# audit). 30 days is wide enough to catch a Kissane-class drift within a
# typical edit window without re-flagging the legacy backlog every CI run.
WIKI008_RECENT_DAYS = 30


def check_cross_link_completeness(
    vault_root: Path,
    findings: list[Finding],
    *,
    apply_recency_filter: bool = True,
) -> None:
    """WIKI008 — Source-to-topic cross-link completeness (vault-wide).

    Scope: only checks outbound `[[topics/T]]` wikilinks that appear inside a
    *tracked* H2 section of the source page — `## Related wiki`,
    `## Cross-references`, `## Related sources`, `## Related`, or
    `## See also`. The convention is that semantic-relationship links live in
    these sections; mid-prose mentions are casual and not enforced.

    For each tracked-section outbound link `[[topics/T]]` on source S, the
    topic page T's body must reference S anywhere (via `[[sources/S]]` or
    bare `[[S]]`). Asymmetric pairs are flagged on the source page at the
    first offending wikilink site, as warnings.

    Catches the "new source created with topic backlinks in *Related wiki*,
    but the topic page forgot to add the source to its *Sources* /
    *Cross-references*" drift — the Kissane-vs-responsive-web-design case
    from 2026-05-29.
    """
    sources_dir = vault_root / "wiki" / "sources"
    topics_dir = vault_root / "wiki" / "topics"
    if not sources_dir.exists() or not topics_dir.exists():
        return

    # Pre-build: set of all source-page stems (for bare-wikilink matching)
    source_stems: set[str] = set()
    for sp in sources_dir.rglob("*.md"):
        source_stems.add(sp.stem.lower())

    # Build {topic_stem -> set of source-stems that topic body references}
    topic_to_sources: dict[str, set[str]] = {}
    for tp in topics_dir.rglob("*.md"):
        try:
            text = tp.read_text(encoding="utf-8")
        except Exception:
            continue
        mentioned: set[str] = set()
        for lineno, line, in_code, in_fm in iter_lines_with_context(text):
            if in_code or in_fm:
                continue
            scrubbed = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line)
            for m in WIKILINK_RE.finditer(scrubbed):
                inner = m.group(1)
                target_part = re.split(r"\\?\|", inner, maxsplit=1)[0]
                target = target_part.split("#", 1)[0].strip()
                if not target:
                    continue
                # Strip optional trailing .md
                slug = target[:-3] if target.endswith(".md") else target
                if slug.startswith("sources/"):
                    mentioned.add(slug.split("/", 1)[1].lower())
                elif "/" not in slug and slug.lower() in source_stems:
                    mentioned.add(slug.lower())
        topic_to_sources[tp.stem.lower()] = mentioned

    # For each source, find outbound `[[topics/X]]` wikilinks INSIDE tracked
    # H2 sections and verify back-reference. Mid-prose wikilinks are ignored.
    h2_re = re.compile(r"^##\s+(.+?)\s*$")
    higher_heading_re = re.compile(r"^#\s+\S")  # H1 also resets section
    today = date.today()
    cutoff = today - timedelta(days=WIKI008_RECENT_DAYS)
    for sp in sorted(sources_dir.rglob("*.md")):
        try:
            text = sp.read_text(encoding="utf-8")
        except Exception:
            continue
        # Recency filter — skip legacy ingests in default mode.
        if apply_recency_filter:
            fm = _extract_frontmatter(text)
            if fm is None:
                continue
            fm_dict, _ = fm
            di_raw = fm_dict.get("date_ingested", "").strip().strip("\"'")
            if not di_raw or not ISO_DATE_RE.match(di_raw):
                continue  # no usable date — out of scope for default gate
            try:
                di = date.fromisoformat(di_raw[:10])
            except ValueError:
                continue
            if di < cutoff:
                continue  # legacy — run `--report cross-links` for full audit
        src_stem = sp.stem.lower()
        # Track first-occurrence per (source, topic) to keep findings minimal
        seen_pairs: set[tuple[str, str]] = set()
        in_tracked_section = False
        for lineno, line, in_code, in_fm in iter_lines_with_context(text):
            if in_code or in_fm:
                continue
            # Heading boundaries: H1 closes any section; H2 may open a tracked one.
            if higher_heading_re.match(line):
                in_tracked_section = False
                continue
            m_h2 = h2_re.match(line)
            if m_h2:
                heading_text = m_h2.group(1).strip().lower()
                in_tracked_section = heading_text in TRACKED_SECTION_NAMES
                continue
            if not in_tracked_section:
                continue
            scrubbed = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line)
            for m in WIKILINK_RE.finditer(scrubbed):
                inner = m.group(1)
                target_part = re.split(r"\\?\|", inner, maxsplit=1)[0]
                target = target_part.split("#", 1)[0].strip()
                slug = target[:-3] if target.endswith(".md") else target
                if not slug.startswith("topics/"):
                    continue
                topic_stem = slug.split("/", 1)[1].lower()
                if (src_stem, topic_stem) in seen_pairs:
                    continue
                mentioned = topic_to_sources.get(topic_stem, set())
                if src_stem in mentioned:
                    seen_pairs.add((src_stem, topic_stem))
                    continue  # symmetric — good
                # Asymmetric — flag at this wikilink site
                seen_pairs.add((src_stem, topic_stem))
                findings.append(
                    Finding(
                        file=str(sp),
                        line=lineno,
                        col=m.start() + 1,
                        code="WIKI008",
                        severity=SEVERITY_WARNING,
                        message=(
                            f"Source page's tracked-section links to "
                            f"`[[topics/{topic_stem}]]` but the topic page does "
                            f"not mention this source. Add to the topic's "
                            f"`## Sources` or `## Cross-references`."
                        ),
                    )
                )


def _extract_list_field(text: str, field_name: str) -> list[tuple[str, int]]:
    """Extract YAML list values for a top-level frontmatter field.

    Returns list of (value, lineno) tuples. Handles both:
        field:
          - "value1"
          - "value2"
    and inline:
        field: ["value1", "value2"]

    Strips surrounding quotes.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    end = None
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return []
    items: list[tuple[str, int]] = []
    in_field = False
    pattern = re.compile(rf"^{re.escape(field_name)}\s*:\s*(.*)$")
    for i in range(1, end - 1):
        line = lines[i]
        m = pattern.match(line)
        if m:
            tail = m.group(1).strip()
            if tail.startswith("[") and tail.endswith("]"):
                # Inline list
                inner = tail[1:-1]
                for part in inner.split(","):
                    val = part.strip().strip("\"'")
                    if val:
                        items.append((val, i + 1))
                in_field = False
            elif tail:
                # Single scalar value (unusual for list-typed fields but handle)
                items.append((tail.strip("\"'"), i + 1))
                in_field = False
            else:
                in_field = True
            continue
        if in_field:
            stripped = line.lstrip()
            if stripped.startswith("- "):
                val = stripped[2:].strip().strip("\"'")
                if val:
                    items.append((val, i + 1))
            elif line.strip() == "" or line.startswith(" ") or line.startswith("\t"):
                continue  # blank or indented continuation
            else:
                in_field = False  # next top-level field
    return items


def _extract_frontmatter(text: str) -> tuple[dict[str, str], int] | None:
    """Parse YAML frontmatter into a flat dict (string values).

    Stdlib-only — handles the small subset our schemas care about
    (top-level scalar keys + presence of list-keys). For full YAML
    parsing the vendor tool already uses gray-matter; this is just
    enough to check key presence.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return None
    body = lines[1 : end - 1]
    fm: dict[str, str] = {}
    current_key: str | None = None
    for line in body:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if m:
            current_key = m.group(1)
            value = m.group(2).strip()
            fm[current_key] = value
        elif current_key and line.startswith(" "):
            if not fm.get(current_key):
                fm[current_key] = line.strip()
    return fm, 1


# ---------- Reports ----------


def report_orphans(vault_root: Path) -> int:
    """Find synthesis pages with no inbound `[[wikilinks]]` from other wiki pages.

    Allow-list: pages that are intentionally entry points (no inbound links by
    design). Returns count for use as exit hint (always 0 — advisory).
    """
    wiki_root = vault_root / "wiki"
    if not wiki_root.exists():
        print(f"ERROR: wiki/ not found under {vault_root}", file=sys.stderr)
        return 0

    # Allow-list (intentional entry points). Module constant so it is
    # config-replaceable; copied because log archives are appended to it below.
    allow = set(ORPHAN_ALLOWLIST)

    # Build wiki page set
    pages: list[Path] = []
    for p in wiki_root.rglob("*.md"):
        rel = str(p.relative_to(vault_root)).replace(os.sep, "/")
        if "/log/" in rel and rel.endswith("-archive.md"):
            allow.add(rel)
        pages.append(p)

    # Resolve every wikilink in every page to its target wiki/ file
    referenced: set[str] = set()
    index = build_vault_index(vault_root)
    for p in pages:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for lineno, line, in_code, in_fm in iter_lines_with_context(text):
            if in_code or in_fm:
                continue
            scrubbed = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line)
            for m in WIKILINK_RE.finditer(scrubbed):
                inner = m.group(1)
                target_part = re.split(r"\\?\|", inner, maxsplit=1)[0]
                target = target_part.split("#", 1)[0].strip()
                if not target or target.startswith(("http://", "https://", "mailto:")):
                    continue
                for resolved in resolve_wikilink(target, vault_root, index):
                    try:
                        rel = str(resolved.relative_to(vault_root)).replace(os.sep, "/")
                    except ValueError:
                        continue
                    if rel.startswith("wiki/") and resolved != p:
                        referenced.add(rel)

    # Find orphans
    orphans: list[str] = []
    for p in pages:
        rel = str(p.relative_to(vault_root)).replace(os.sep, "/")
        if rel in allow:
            continue
        if rel not in referenced:
            orphans.append(rel)

    print("=== orphan pages (no inbound wikilinks) ===")
    print(f"Total: {len(orphans)}")
    for rel in sorted(orphans):
        print(f"  {rel}")
    return len(orphans)


def _stale_today() -> date:
    """Today — overridable with WIKI_LINT_TODAY=YYYY-MM-DD.

    A test seam, and the only honest way to pin the threshold boundaries. An
    exact-90-day fixture is written by the test process and judged by a separate
    linter process; between the two, midnight can pass and the age becomes 91.
    Freezing the clock is worth more than a boundary assertion that flakes once
    a night. Affects `--report stale` alone, which gates nothing — a malformed
    value is ignored rather than fatal, since no build outcome rides on it.
    """
    raw = os.environ.get("WIKI_LINT_TODAY", "").strip()
    if ISO_DATE_RE.match(raw):
        try:
            y, m, d = (int(x) for x in raw.split("-"))
            return date(y, m, d)
        except ValueError:
            pass
    return date.today()


def report_stale(vault_root: Path) -> int:
    """Surface pages the vault's own data says have gone stale (advisory).

    Deliberately NOT a hard gate. Every other check here is keyed to *content* —
    it fires because a file says something wrong, so a clean tree stays clean.
    Staleness is keyed to *wall-clock time*, so a hard gate would turn CI red on
    a day nobody touched the repo. That is a bad property, and it is why pruning
    is surfaced on demand rather than enforced in CI.

    Four signals, strongest first:

    - STALE-A  status/date contradiction. A `plan`/`project` marked
               `status: active` whose date is older than STALE_ACTIVE_DAYS. An
               "active" page nobody has touched in a quarter is finished, dead,
               or lying — and the page itself is the only thing asserting
               otherwise.
    - STALE-B  an expired self-set alarm. A corpus writes lines like
               "Re-check Nov 2026" and then nothing rings. This rings them.
    - STALE-C  aging synthesis: insight/topic pages untouched for longer than
               STALE_SYNTHESIS_DAYS. Informational — age alone is not rot, and
               a stable page may simply be correct.
    - STALE-D  pages this report could not judge: no date key, an unparseable
               one, or a date in the future. Counted and listed rather than
               skipped, because a page with no freshness evidence is the one
               most likely to be stale, and dropping it silently makes "A=0"
               read as *clean* when it means *unassessed*.

    A/C read `date_updated` and fall back per type (STALE_DATE_KEYS_BY_TYPE) —
    keying on `date_updated` alone would be silent on schema-legal pages, since
    it is only ever a recommended key, never a required one.
    """
    wiki_root = vault_root / "wiki"
    if not wiki_root.exists():
        print(f"ERROR: wiki/ not found under {vault_root}", file=sys.stderr)
        return 0

    today = _stale_today()

    def parse_iso(value: str) -> date | None:
        v = value.strip().strip("\"'")[:10]
        if not ISO_DATE_RE.match(v):
            return None
        try:
            y, m, d = (int(x) for x in v.split("-"))
            return date(y, m, d)
        except ValueError:
            return None

    contradictions: list[tuple[int, str, str, str, str]] = []
    alarms: list[tuple[str, int, str]] = []
    aging: list[tuple[int, str, str, str]] = []
    unjudged: list[tuple[str, str, str]] = []

    for p in sorted(wiki_root.rglob("*.md")):
        rel = str(p.relative_to(vault_root)).replace(os.sep, "/")
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue

        parsed = _extract_frontmatter(text)
        if parsed:
            fm = parsed[0]
            ptype = fm.get("type", "").strip().strip("\"'").lower()
            status = fm.get("status", "").strip().strip("\"'").lower()
            in_scope = (
                (ptype in ("plan", "project") and status == "active")
                or ptype in ("insight", "topic")
            )
            if in_scope:
                # First key that PARSES wins, so a malformed `date_updated`
                # still falls back to `date_created`. The malformed value is
                # kept anyway — if nothing parses, it is the useful reason.
                when: date | None = None
                key = ""
                bad = ""
                for candidate in STALE_DATE_KEYS_BY_TYPE[ptype]:
                    if candidate not in fm:
                        continue
                    raw = fm[candidate].strip()
                    when = parse_iso(raw)
                    if when:
                        key = candidate
                        break
                    if not bad:
                        bad = f"unparseable {candidate}: {raw!r}"
                age = (today - when).days if when else 0
                if when is None:
                    unjudged.append((rel, ptype, bad or "no date key"))
                elif age < 0:
                    unjudged.append(
                        (rel, ptype, f"{key} is in the future: {when.isoformat()}")
                    )
                elif ptype in ("plan", "project"):
                    if age > STALE_ACTIVE_DAYS:
                        contradictions.append((age, rel, ptype, key, when.isoformat()))
                elif age > STALE_SYNTHESIS_DAYS:
                    aging.append((age, rel, key, when.isoformat()))

        # STALE-B — expired self-set re-check dates, anywhere in the body.
        if rel in STALE_B_SKIP_FILES or rel.startswith(STALE_B_SKIP_PREFIXES):
            continue
        for lineno, line, in_code, in_fm in iter_lines_with_context(text):
            if in_code or in_fm:
                continue
            line = INLINE_CODE_RE.sub(" ", line)
            for m in RECHECK_RE.finditer(line):
                if m.group("iso"):
                    due = parse_iso(m.group("iso"))
                    if due is None:      # e.g. 2027-13-45 — matched, not a date
                        continue
                else:
                    # RECHECK_RE is the authority on the key set: `mon` can only
                    # be one of the twelve month tokens, so this cannot KeyError.
                    month = MONTHS[m.group("mon").lower()[:3]]
                    # An alarm named by month is due once that month has BEGUN,
                    # so compare against the first — "Nov 2026" rings on Nov 1.
                    due = date(int(m.group("year")), month, 1)
                if due <= today:
                    alarms.append((rel, lineno, m.group(0).strip()))

    print("=== stale pages (advisory — pruning is a habit this makes visible) ===")
    print()
    print(f"STALE-A  active plan/project not updated in >{STALE_ACTIVE_DAYS}d: {len(contradictions)}")
    for age, rel, ptype, key, when in sorted(contradictions, reverse=True):
        print(f"  {age:>4}d  {rel}  ({ptype}, status: active, {key} {when})")
    print()
    print(f"STALE-B  self-set re-check dates now due: {len(alarms)}")
    for rel, lineno, snippet in sorted(alarms):
        print(f"        {rel}:{lineno}  → {snippet}")
    print()
    print(f"STALE-C  insight/topic not updated in >{STALE_SYNTHESIS_DAYS}d: {len(aging)}")
    for age, rel, key, when in sorted(aging, reverse=True):
        print(f"  {age:>4}d  {rel}  ({key} {when})")
    print()
    print(f"STALE-D  in scope but no usable date — unassessed, not clean: {len(unjudged)}")
    for rel, ptype, why in sorted(unjudged):
        print(f"        {rel}  ({ptype}, {why})")

    total = len(contradictions) + len(alarms) + len(aging) + len(unjudged)
    print()
    print(
        f"Total: {total}  (A={len(contradictions)} B={len(alarms)} "
        f"C={len(aging)} D={len(unjudged)})"
    )
    return total


def report_symmetry(vault_root: Path) -> int:
    """Check that entity pages' Appears-In references the source pages that cite them.

    For each source page S, find every [[entities/X]] reference in S's body.
    Then check entity X's Appears-In contains a link to S. Asymmetric pairs
    are listed (advisory — entities curate Appears-In, so this is hint-only).

    Cost: this reads every source and every entity page and cross-joins them —
    O(N^2) in practice, ~30s on a mid-size vault. That runtime is why it is a
    manual report and not a CI gate.
    """
    wiki_root = vault_root / "wiki"
    sources_dir = wiki_root / "sources"
    entities_dir = wiki_root / "entities"
    if not sources_dir.exists() or not entities_dir.exists():
        print(f"ERROR: sources/ or entities/ not found under {wiki_root}", file=sys.stderr)
        return 0

    # source -> set of entity slugs it references
    src_to_entities: dict[str, set[str]] = {}
    for sp in sources_dir.rglob("*.md"):
        rel = str(sp.relative_to(vault_root)).replace(os.sep, "/")
        try:
            text = sp.read_text(encoding="utf-8")
        except Exception:
            continue
        ents: set[str] = set()
        for lineno, line, in_code, in_fm in iter_lines_with_context(text):
            if in_code or in_fm:
                continue
            scrubbed = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line)
            for m in WIKILINK_RE.finditer(scrubbed):
                inner = m.group(1)
                target_part = re.split(r"\\?\|", inner, maxsplit=1)[0]
                target = target_part.split("#", 1)[0].strip()
                if target.startswith("entities/"):
                    slug = target.split("/", 1)[1]
                    if slug.endswith(".md"):
                        slug = slug[:-3]
                    ents.add(slug)
        if ents:
            src_to_entities[rel] = ents

    # entity -> set of sources referenced by it
    ent_to_sources: dict[str, set[str]] = {}
    src_basenames: dict[str, str] = {}
    for sp in sources_dir.rglob("*.md"):
        rel = str(sp.relative_to(vault_root)).replace(os.sep, "/")
        src_basenames[sp.stem.lower()] = rel
    for ep in entities_dir.rglob("*.md"):
        rel = str(ep.relative_to(vault_root)).replace(os.sep, "/")
        try:
            text = ep.read_text(encoding="utf-8")
        except Exception:
            continue
        srcs: set[str] = set()
        for lineno, line, in_code, in_fm in iter_lines_with_context(text):
            if in_code or in_fm:
                continue
            scrubbed = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line)
            for m in WIKILINK_RE.finditer(scrubbed):
                inner = m.group(1)
                target_part = re.split(r"\\?\|", inner, maxsplit=1)[0]
                target = target_part.split("#", 1)[0].strip()
                if target.startswith("sources/"):
                    slug = target.split("/", 1)[1]
                    if slug.endswith(".md"):
                        slug = slug[:-3]
                    full = src_basenames.get(slug.lower())
                    if full:
                        srcs.add(full)
                elif "/" not in target and target.lower() in src_basenames:
                    srcs.add(src_basenames[target.lower()])
        ent_to_sources[ep.stem] = srcs

    # Asymmetric pairs: source S references entity E, but E doesn't reference S
    asymmetric: list[tuple[str, str]] = []
    for src_rel, ents in src_to_entities.items():
        for ent in ents:
            referenced_srcs = ent_to_sources.get(ent, set())
            if src_rel not in referenced_srcs:
                asymmetric.append((src_rel, ent))

    print("=== cross-reference symmetry (sources → entities) ===")
    print(f"Sources scanned: {len(src_to_entities)}")
    print(f"Asymmetric pairs (entity Appears-In missing source): {len(asymmetric)}")
    by_entity: dict[str, list[str]] = {}
    for src, ent in asymmetric:
        by_entity.setdefault(ent, []).append(src)
    for ent in sorted(by_entity):
        srcs = by_entity[ent]
        if len(srcs) >= 3:
            print(f"  entities/{ent} missing {len(srcs)} sources (showing 3): {sorted(srcs)[:3]}")
        else:
            print(f"  entities/{ent}: {sorted(srcs)}")
    return len(asymmetric)


def report_cross_links(vault_root: Path) -> int:
    """Full vault-wide WIKI008 audit (advisory; no recency filter).

    Rolls up asymmetric source→topic links by source file: shows count + the
    first few offending topics. Useful for the "let's actually fix the
    legacy backlog" project. Default lint flow uses a 30-day recency filter
    on this check; this report shows everything.
    """
    full_findings: list[Finding] = []
    check_cross_link_completeness(
        vault_root, full_findings, apply_recency_filter=False
    )
    by_source: dict[str, list[str]] = {}
    for f in full_findings:
        m = re.search(r"`\[\[topics/([^\]\|#]+)", f.message)
        topic = m.group(1) if m else "?"
        by_source.setdefault(f.file, []).append(topic)
    print("=== source→topic cross-link asymmetries (full vault) ===")
    print(f"Sources with at least one asymmetric link: {len(by_source)}")
    print(f"Total asymmetric pairs: {len(full_findings)}")
    print()
    for src in sorted(by_source):
        topics = by_source[src]
        rel = src
        try:
            rel = str(Path(src).relative_to(vault_root))
        except ValueError:
            pass
        if len(topics) > 3:
            preview = ", ".join(topics[:3])
            print(f"  {rel}: {len(topics)} ({preview}, …)")
        else:
            print(f"  {rel}: {', '.join(topics)}")
    return len(full_findings)


def report_tags(vault_root: Path) -> int:
    """Scan all wiki frontmatter tags and report off-taxonomy tags by frequency.

    Known tags: CLAUDE.md taxonomy (domain / activity / role / type / time).
    Time tags (bare 4-digit years, q<N>-YYYY) are matched by pattern.
    Returns count of distinct off-taxonomy tag strings (advisory; always exits 0).
    """
    wiki_root = vault_root / "wiki"
    if not wiki_root.exists():
        print(f"ERROR: wiki/ not found under {vault_root}", file=sys.stderr)
        return 0

    all_tags: dict[str, int] = {}
    page_count = 0
    tagged_page_count = 0

    for p in sorted(wiki_root.rglob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        page_count += 1
        tag_entries = _extract_list_field(text, "tags")
        if not tag_entries:
            continue
        tagged_page_count += 1
        for tag, _ in tag_entries:
            tag = tag.strip().strip("\"'").lower()
            if tag:
                all_tags[tag] = all_tags.get(tag, 0) + 1

    unknown: dict[str, int] = {
        tag: count
        for tag, count in all_tags.items()
        if tag not in _KNOWN_TAGS and not _TIME_TAG_RE.match(tag)
    }

    print("=== tag taxonomy report ===")
    print(f"Pages scanned: {page_count}")
    print(f"Pages with tags: {tagged_page_count}")
    print(f"Unique tags: {len(all_tags)}  |  off-taxonomy: {len(unknown)}")
    if unknown:
        print()
        print("Off-taxonomy tags (frequency desc, then alpha):")
        for tag in sorted(unknown, key=lambda t: (-unknown[t], t)):
            print(f"  {unknown[tag]:>3}x  {tag}")
    else:
        print()
        print("All tags are on-taxonomy.")
    return len(unknown)


# ---------- Advisory reports: Q2 glossary-coverage / Q4 schema / Q5 duplicates ----------


def _body_after_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1:])
    return text


_BOLD_TERM_RE = re.compile(r"\*\*([A-Z][A-Za-z0-9][A-Za-z0-9 /&'\-]{1,38})\*\*")
_GLOSSARY_ANCHOR_RE = re.compile(r"\[\[glossary/[^#\]]*#([^|\]]+)")


def _norm_term(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().strip(".:,").lower())


def _is_term_like(term: str) -> bool:
    """An ALLCAPS acronym (2-6 letters) or a Title-Case multi-word phrase."""
    if re.fullmatch(r"[A-Z]{2,6}", term):
        return True
    words = term.split()
    if len(words) >= 2 and sum(1 for w in words if w[:1].isupper()) >= 2:
        return True
    return False


def report_glossary_coverage(vault_root: Path) -> int:
    """Q2 — bold-emphasised term-like phrases in synthesis bodies with no matching
    glossary entry or `[[glossary/...]]` link. Heuristic / advisory (always exits 0)."""
    wiki = vault_root / "wiki"
    if not wiki.exists():
        print(f"ERROR: wiki/ not found under {vault_root}", file=sys.stderr)
        return 0

    glossary_terms: set[str] = set()
    for gp in (wiki / "glossary").rglob("*.md"):
        for line in gp.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("### "):
                glossary_terms.add(_norm_term(re.sub(r"\(.*?\)", "", line[4:])))

    counts: dict[str, int] = {}
    pages_for: dict[str, set[str]] = {}
    for folder in SYNTH_FOLDERS:
        for p in sorted((wiki / folder).rglob("*.md")):
            text = p.read_text(encoding="utf-8", errors="replace")
            body = _body_after_frontmatter(text)
            linked = {_norm_term(a) for a in _GLOSSARY_ANCHOR_RE.findall(body)}
            for m in _BOLD_TERM_RE.finditer(body):
                term = m.group(1).strip()
                norm = _norm_term(term)
                if norm in _NON_TERM_BOLD or not _is_term_like(term):
                    continue
                if norm in glossary_terms or norm in linked:
                    continue
                counts[term] = counts.get(term, 0) + 1
                pages_for.setdefault(term, set()).add(str(p.relative_to(wiki)))

    # Only surface terms emphasised on >=2 distinct pages (reduces one-off noise).
    candidates = {t: c for t, c in counts.items() if len(pages_for[t]) >= 2}
    print("=== glossary-coverage report (Q2, advisory) ===")
    print(f"Glossary terms indexed: {len(glossary_terms)}")
    print(f"Un-glossaried bold terms on >=2 pages: {len(candidates)}")
    if candidates:
        print()
        print("Candidate terms to glossary-or-link (freq desc):")
        for t in sorted(candidates, key=lambda x: (-candidates[x], x))[:40]:
            pgs = sorted(pages_for[t])
            print(f"  {candidates[t]:>3}x  {t}  ({len(pgs)} pages, e.g. {pgs[0]})")
    else:
        print("\nNo recurring un-glossaried bold terms.")
    return len(candidates)


def report_schema(vault_root: Path) -> int:
    """Q4 — per-type body-structure adherence (advisory, grandfathered). Currently
    checks project pages against the CLAUDE.md canonical section list."""
    wiki = vault_root / "wiki"
    if not wiki.exists():
        print(f"ERROR: wiki/ not found under {vault_root}", file=sys.stderr)
        return 0

    missing_total = 0
    print("=== schema adherence report (Q4, advisory) ===")
    for ptype, expected in EXPECTED_H2_BY_TYPE.items():
        pages_checked = 0
        for p in sorted((wiki / (ptype + "s")).rglob("*.md")):
            text = p.read_text(encoding="utf-8", errors="replace")
            fm = _extract_frontmatter(text)
            if not fm or fm[0].get("type") != ptype:
                continue
            pages_checked += 1
            h2s = [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]
            missing = [s for s in expected if not any(s.lower() in h.lower() for h in h2s)]
            if missing:
                missing_total += 1
                print(f"  {p.relative_to(wiki)} — missing: {', '.join(missing)}")
        print(f"  ({ptype}: {pages_checked} checked)")
    if missing_total == 0:
        print("  All checked pages carry their canonical sections.")
    return missing_total


def report_duplicates(vault_root: Path, threshold: float = 0.5) -> int:
    """Q5 — near-duplicate page detection via lexical (Jaccard) similarity over
    title + first paragraph. Advisory. (A future upgrade uses qmd vec similarity.)"""
    wiki = vault_root / "wiki"
    if not wiki.exists():
        print(f"ERROR: wiki/ not found under {vault_root}", file=sys.stderr)
        return 0

    pages: list[tuple[str, str, set[str]]] = []
    for folder in SYNTH_FOLDERS + ("entities",):
        for p in sorted((wiki / folder).rglob("*.md")):
            text = p.read_text(encoding="utf-8", errors="replace")
            fm = _extract_frontmatter(text)
            title = (fm[0].get("title", "") if fm else "") or p.stem
            body = _body_after_frontmatter(text)
            para = ""
            for blk in re.split(r"\n\s*\n", body):
                s = blk.strip()
                if s and not s.startswith(("#", ">", "|", "-", "*", "```")):
                    para = s
                    break
            sig = f"{title} {para}".lower()
            tokens = {w for w in re.findall(r"[a-z0-9]{3,}", sig) if w not in _STOPWORDS}
            if len(tokens) >= 5:
                pages.append((str(p.relative_to(wiki)), title.strip(), tokens))

    pairs: list[tuple[float, str, str]] = []
    for i in range(len(pages)):
        ti = pages[i][2]
        for j in range(i + 1, len(pages)):
            tj = pages[j][2]
            inter = len(ti & tj)
            if inter < 4:
                continue
            jac = inter / len(ti | tj)
            if jac >= threshold:
                pairs.append((jac, pages[i][0], pages[j][0]))
    pairs.sort(reverse=True)

    print("=== duplicate-page report (Q5, advisory; lexical) ===")
    print(f"Pages compared: {len(pages)}  |  similar pairs (Jaccard >= {threshold}): {len(pairs)}")
    if pairs:
        print()
        for jac, a, b in pairs[:30]:
            print(f"  {jac:.2f}  {a}  <->  {b}")
    else:
        print("\nNo near-duplicate pairs above threshold.")
    return len(pairs)


# ---------- Output ----------


def emit_default(findings: list[Finding]) -> None:
    for f in findings:
        prefix = "ERROR" if f.severity == SEVERITY_ERROR else "WARN "
        print(f"{prefix} {f.file}:{f.line}:{f.col}  {f.code}  {f.message}")


def emit_gh_annotations(findings: list[Finding]) -> None:
    for f in findings:
        kind = "error" if f.severity == SEVERITY_ERROR else "warning"
        safe_msg = re.sub(r"[\r\n]", " ", f.message).replace("::", ":")
        print(
            f"::{kind} file={f.file},line={f.line},col={f.col},title={f.code}::{safe_msg}"
        )


def emit_summary(findings: list[Finding]) -> None:
    by_code: dict[str, int] = {}
    by_severity: dict[str, int] = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 0}
    for f in findings:
        by_code[f.code] = by_code.get(f.code, 0) + 1
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
    print("", file=sys.stderr)
    print("=== wiki-lint summary ===", file=sys.stderr)
    print(
        f"Total: {len(findings)} "
        f"({by_severity[SEVERITY_ERROR]} errors, "
        f"{by_severity[SEVERITY_WARNING]} warnings)",
        file=sys.stderr,
    )
    if by_code:
        for code in sorted(by_code):
            print(f"  {code}: {by_code[code]}", file=sys.stderr)


# ---------- Main ----------


def main() -> int:
    parser = argparse.ArgumentParser(description="Layer 2 wiki linter")
    parser.add_argument("paths", nargs="*", default=["wiki/"], help="Files or dirs to lint (default: wiki/)")
    parser.add_argument(
        "--check",
        action="append",
        choices=ALL_CHECKS,
        help="Run only specified checks (can repeat)",
    )
    parser.add_argument(
        "--report",
        choices=ALL_REPORTS,
        help="Run an advisory report instead of the lint gates",
    )
    parser.add_argument("--gh-annotations", action="store_true", help="Emit GitHub Actions annotation syntax")
    parser.add_argument("--vault-root", default=".", help="Vault root for wikilink resolution")
    args = parser.parse_args()

    vault_root = Path(args.vault_root).resolve()
    if not vault_root.exists():
        print(f"ERROR: vault-root not found: {vault_root}", file=sys.stderr)
        return 2

    # Optional per-instance config, resolved against the vault root (see
    # load_config). Absent = built-in defaults, silently. Bad = fatal, loudly.
    try:
        cfg = load_config(vault_root)
        if cfg is not None:
            apply_config(cfg)
    except ConfigError as e:
        print(f"ERROR: {CONFIG_RELPATH}: {e}", file=sys.stderr)
        return 2

    if args.report:
        if args.report == REPORT_ORPHANS:
            report_orphans(vault_root)
        elif args.report == REPORT_SYMMETRY:
            report_symmetry(vault_root)
        elif args.report == REPORT_CROSS_LINKS:
            report_cross_links(vault_root)
        elif args.report == REPORT_TAGS:
            report_tags(vault_root)
        elif args.report == REPORT_GLOSSARY:
            report_glossary_coverage(vault_root)
        elif args.report == REPORT_SCHEMA:
            report_schema(vault_root)
        elif args.report == REPORT_DUPLICATES:
            report_duplicates(vault_root)
        elif args.report == REPORT_STALE:
            report_stale(vault_root)
        return 0  # advisory — always exit 0

    enabled_checks = set(args.check or ALL_CHECKS)

    # Build vault file index once (for wikilink resolution)
    index: dict[str, list[Path]] = {}
    if CHECK_BROKEN_WIKILINK in enabled_checks:
        index = build_vault_index(vault_root)

    target_files: list[Path] = []
    for raw_path in args.paths:
        p = Path(raw_path)
        if not p.is_absolute():
            p = vault_root / p
        if p.is_file() and p.suffix == ".md":
            target_files.append(p)
        elif p.is_dir():
            for f in p.rglob("*.md"):
                target_files.append(f)

    findings: list[Finding] = []
    for path in sorted(target_files):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            findings.append(
                Finding(
                    file=str(path),
                    line=1,
                    col=1,
                    code="IO001",
                    severity=SEVERITY_ERROR,
                    message=f"Could not read file: {e}",
                )
            )
            continue
        if CHECK_TABLE_PIPE in enabled_checks:
            check_table_pipe(path, text, findings)
        if CHECK_BROKEN_WIKILINK in enabled_checks:
            check_broken_wikilinks(path, text, vault_root, index, findings)
        if CHECK_FRONTMATTER in enabled_checks:
            check_frontmatter_schema(path, text, findings)
        if CHECK_RAW_SOURCES in enabled_checks:
            check_raw_sources_paths(path, text, vault_root, findings)
        if CHECK_RECENT_UPDATES in enabled_checks:
            check_recent_updates_callout(path, text, findings)
        if CHECK_PROVENANCE in enabled_checks:
            check_inline_provenance(path, text, findings)
        if CHECK_ANCHOR_PROSE in enabled_checks:
            check_anchor_prose_count(path, text, findings)

    # WIKI008 / cross-link-completeness is NOT a default check — run on demand
    # via `--report cross-links` (see report_cross_links).

    if args.gh_annotations:
        emit_gh_annotations(findings)
    else:
        emit_default(findings)
    emit_summary(findings)

    errors = sum(1 for f in findings if f.severity == SEVERITY_ERROR)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
