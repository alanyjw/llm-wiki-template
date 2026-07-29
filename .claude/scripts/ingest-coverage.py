#!/usr/bin/env python3
"""Ingest-coverage audit: which raw notes have no wiki page yet?

The vault has two layers. `raw/` accumulates immutable sources; `wiki/`
holds the synthesis the LLM writes from them. Nothing in the pipeline
forces those two layers to stay in step — a note can sit in `raw/` for
months, fully captured and never once read into the wiki. Retrieval
still finds it (qmd indexes raw collections), but it is not *compiled*:
no source page, no entity/topic updates, no cross-links.

**Coverage** here means exactly one thing, and deliberately nothing more:

    a raw note is MAPPED if at least one page in wiki/sources/ names it
    in that page's `raw_sources:` frontmatter.

That is the same edge `wiki-lint.py`'s FM005 walks, in the other
direction. FM005 asks "does every claim point at a real file?" (catching
typos and post-rename drift). This asks "does every file have a claim?"
(catching un-ingested notes). Both directions are needed; only one of
them was previously answerable.

Mapping is *not* a quality judgement. A mapped note may have been
ingested thinly; an unmapped note may have been deliberately passed
over. What the report gives you is a work queue and an honest denominator
— "23 of 61 web clippings have never reached the wiki" is a fact worth
knowing before deciding what to read next.

Known caveat — deliberate skips
-------------------------------
The `batch-ingest` skill records a per-note disposition in
`wiki/notes-import-manifest.md`, including notes it reviewed and
deliberately skipped (too thin, duplicate, pure logistics). Those notes
have no source page by design, so this script reports them as UNMAPPED.
When `raw/notes-import/` is in scope, treat the manifest as authoritative
for that folder and this report as the superset.

What is excluded by default
---------------------------
Only `.md` files are audited; `.gitkeep` and other dotfiles are ignored.
Two further exclusions come straight from CLAUDE.md's Layer Rules:

  - `raw/bookmarks.md` — a URL queue, not a wiki input. Never ingested
    directly, so counting it as a coverage gap would be permanent noise.
  - `raw/briefings/` and `raw/research/` — skill outputs (daily-briefing,
    weekly-digest, storm-research). Written by tools, read by humans;
    they are wiki *derivatives*, not inbound sources.

Naming an excluded folder explicitly (`ingest-coverage.py raw/research`)
audits it anyway — the exclusion applies only when the folder is reached
by sweeping something above it. `--include-excluded` overrides all of it.

Matching rules
--------------
`raw_sources:` entries are written by hand and drift in shape, so every
entry is normalized before matching: surrounding quotes/backticks are
stripped, `[[wikilink]]` and `![[embed]]` wrappers unwrapped, `|alias`
and `#anchor` suffixes dropped, backslashes folded to `/`, and a bare
`.md` appended when the target carries no extension. A claim then matches
a raw file if it equals the file's vault-relative path, any path *suffix*
of it on a segment boundary (so `notes-import/foo.md` matches
`raw/notes-import/foo.md`), or — last resort — its basename. Matching is
case-insensitive, like Obsidian's own resolution.

The basename fallback is what makes bare `[[Some Note Title]]` claims
resolve, and it is the one rule that can over-credit: two raw notes with
the same filename in different folders both count as mapped off a single
claim. The summary prints how many files matched by basename alone so you
can spot-check; `--json` carries a `match_kind` per file.

Exit codes
----------
    0  always, by default — including when notes are unmapped
    1  unmapped notes found AND --fail-on-unmapped was passed
    2  script failure (vault root or a requested folder does not exist)

**Why exit 0 on unmapped by default:** an un-ingested note is a backlog
item, not a defect. Every healthy vault has a reading queue, and a gate
that fails CI because you have not yet read something you saved on
Tuesday would train everyone to ignore it. The three real gates
(markdownlint-obsidian, `wiki-lint.py`, `regenerate-index.py --check`)
police the *contract*; this reports the *queue*. `--fail-on-unmapped`
exists for vaults that genuinely want a zero-backlog policy on some
folder — wire it into CI scoped to that folder, never to all of `raw/`.

Usage
-----
    python3 .claude/scripts/ingest-coverage.py
    python3 .claude/scripts/ingest-coverage.py raw/web-clippings
    python3 .claude/scripts/ingest-coverage.py raw/books raw/meetings
    python3 .claude/scripts/ingest-coverage.py --unmapped-only
    python3 .claude/scripts/ingest-coverage.py --json
    python3 .claude/scripts/ingest-coverage.py --verbose
    python3 .claude/scripts/ingest-coverage.py raw/meetings --fail-on-unmapped
    python3 .claude/scripts/ingest-coverage.py --vault-root /path/to/vault
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------- Configuration ----------

DEFAULT_RAW_DIR = "raw"
SOURCES_DIR = "wiki/sources"
MANIFEST_FOLDER = "raw/notes-import"
MANIFEST_PAGE = "wiki/notes-import-manifest.md"

AUDITED_SUFFIXES = {".md"}

# Not ingest inputs, per CLAUDE.md "Layer Rules". Skipped when reached by
# sweeping a parent; audited when named explicitly or with --include-excluded.
EXCLUDED_FILES = ("raw/bookmarks.md",)
EXCLUDED_DIRS = ("raw/briefings", "raw/research")

# Filename convention from CLAUDE.md: video notes live in raw/web-clippings/
# under a `video-` prefix. Labelled in the unmapped list because a video is a
# materially bigger ingest than an article and you may want to queue it apart.
VIDEO_PREFIX = "video-"

MATCH_PATH = "path"
MATCH_BASENAME = "basename"
MATCH_NONE = ""

WIKILINK_WRAPPER_RE = re.compile(r"^!?\[\[(.*)\]\]$", re.DOTALL)
EXTENSION_RE = re.compile(r"\.[A-Za-z][A-Za-z0-9]{1,4}$")


# ---------- Models ----------


@dataclass(frozen=True)
class RawFile:
    """One auditable file under raw/, addressed vault-relative."""

    rel: str      # e.g. "raw/web-clippings/video-some-talk.md"
    group: str    # rollup bucket, e.g. "raw/web-clippings"

    @property
    def label(self) -> str:
        return "video" if Path(self.rel).name.startswith(VIDEO_PREFIX) else ""


@dataclass(frozen=True)
class ClaimIndex:
    """Every `raw_sources:` claim made by every wiki source page."""

    by_key: dict[str, tuple[str, ...]]  # normalized claim key -> source pages
    pages_scanned: int
    claims_parsed: int


@dataclass(frozen=True)
class Coverage:
    """A raw file plus the source pages (if any) that claim it."""

    raw: RawFile
    sources: tuple[str, ...]
    match_kind: str

    @property
    def mapped(self) -> bool:
        return bool(self.sources)


@dataclass(frozen=True)
class FolderStats:
    folder: str
    total: int
    mapped: int

    @property
    def unmapped(self) -> int:
        return self.total - self.mapped

    @property
    def coverage_pct(self) -> float:
        if self.total == 0:
            return 100.0
        return round(self.mapped / self.total * 100, 1)


# ---------- Path helpers ----------


def to_rel(path: Path, vault_root: Path) -> str | None:
    """Vault-relative posix path, or None if the path escapes the vault."""
    try:
        return path.resolve().relative_to(vault_root).as_posix()
    except ValueError:
        return None


def is_within(rel: str, root_rel: str) -> bool:
    """True if `rel` is `root_rel` itself or lives underneath it."""
    return rel == root_rel or rel.startswith(root_rel + "/")


def exclusions_for(root_rel: str, include_excluded: bool) -> tuple[list[str], list[str]]:
    """Exclusions that still apply when sweeping from `root_rel`.

    An exclusion is dropped when the requested root is at or below it —
    asking for `raw/research` explicitly is an opt-in, not an accident.
    """
    if include_excluded:
        return [], []
    files = [f for f in EXCLUDED_FILES if not is_within(root_rel, f)]
    dirs = [d for d in EXCLUDED_DIRS if not is_within(root_rel, d)]
    return files, dirs


def group_for(rel: str, root_rel: str) -> str:
    """Rollup bucket: one directory level below the requested root.

    Sweeping `raw` buckets `raw/captures/daily/x.md` under `raw/captures`;
    sweeping `raw/captures` buckets the same file under `raw/captures/daily`.
    Files sitting directly in the root bucket under the root itself.
    """
    if not is_within(rel, root_rel):
        return root_rel
    remainder = rel[len(root_rel) :].lstrip("/")
    parts = remainder.split("/")
    if len(parts) <= 1:
        return root_rel
    return f"{root_rel}/{parts[0]}"


# ---------- Raw-side collection ----------


def collect_raw_files(
    vault_root: Path,
    roots: list[Path],
    include_excluded: bool,
) -> list[RawFile]:
    """Walk each requested root and return the auditable files, deduped."""
    seen: dict[str, RawFile] = {}
    for root in roots:
        root_rel = to_rel(root, vault_root)
        if root_rel is None:
            continue
        skip_files, skip_dirs = exclusions_for(root_rel, include_excluded)
        candidates = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in candidates:
            if not path.is_file():
                continue
            if path.suffix.lower() not in AUDITED_SUFFIXES:
                continue
            if path.name.startswith("."):
                continue
            rel = to_rel(path, vault_root)
            if rel is None or rel in seen:
                continue
            if rel in skip_files:
                continue
            if any(is_within(rel, d) for d in skip_dirs):
                continue
            seen[rel] = RawFile(rel=rel, group=group_for(rel, root_rel))
    return [seen[rel] for rel in sorted(seen)]


# ---------- Wiki-side claim collection ----------


def extract_frontmatter_block(text: str) -> list[str] | None:
    """Return the frontmatter lines (between the `---` fences), or None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return None


def extract_field_values(fm_lines: list[str], field_name: str) -> list[str]:
    """Pull a frontmatter field's values, list or scalar, quoted or not.

    Handles the three shapes that appear in practice:

        raw_sources:
          - "raw/meetings/2026-01-05 - Kickoff.md"
        raw_sources: ["raw/books/a.md", "raw/books/b.md"]
        raw_sources: raw/books/a.md
    """
    pattern = re.compile(rf"^{re.escape(field_name)}\s*:\s*(.*)$")
    values: list[str] = []
    in_field = False
    for line in fm_lines:
        match = pattern.match(line)
        if match:
            tail = match.group(1).strip()
            if tail.startswith("[") and tail.endswith("]"):
                values.extend(part for part in tail[1:-1].split(",") if part.strip())
                in_field = False
            elif tail:
                values.append(tail)
                in_field = False
            else:
                in_field = True
            continue
        if not in_field:
            continue
        stripped = line.lstrip()
        if stripped.startswith("- "):
            values.append(stripped[2:])
        elif line.strip() == "" or line[:1] in (" ", "\t"):
            continue  # blank line or indented continuation
        else:
            in_field = False  # next top-level key
    return [v for v in (v.strip() for v in values) if v]


def strip_wrappers(value: str) -> str:
    """Unwrap quotes/backticks and `[[wikilink]]` / `![[embed]]` syntax."""
    text = value.strip()
    for _ in range(3):  # e.g. `"[[x]]"` needs quote, then bracket, then settle
        before = text
        if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'`":
            text = text[1:-1].strip()
        wrapped = WIKILINK_WRAPPER_RE.match(text)
        if wrapped:
            text = wrapped.group(1).strip()
        if text == before:
            break
    return text


def normalize_claim(value: str) -> str:
    """Reduce one `raw_sources:` entry to a comparable path-ish string.

    Returns "" for entries that cannot name an in-repo file (URLs,
    absolute paths, home-relative paths) — those are out of scope here,
    the same way FM005 skips them in wiki-lint.
    """
    text = strip_wrappers(value)
    text = re.split(r"\\?\|", text, maxsplit=1)[0]  # drop |alias
    text = text.split("#", 1)[0]                    # drop #anchor
    text = text.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    text = text.strip().rstrip("/")
    if not text:
        return ""
    if text.startswith(("/", "~", "http://", "https://", "file://", "mailto:")):
        return ""
    if not EXTENSION_RE.search(text.rsplit("/", 1)[-1]):
        text += ".md"
    return text.lower()


def collect_claims(vault_root: Path, warnings: list[str]) -> ClaimIndex:
    """Index every `raw_sources:` claim in wiki/sources/ by normalized key."""
    sources_root = vault_root / SOURCES_DIR
    by_key: dict[str, list[str]] = {}
    pages_scanned = 0
    claims_parsed = 0
    if not sources_root.is_dir():
        warnings.append(f"{SOURCES_DIR}/ not found — every raw note will read as unmapped")
        return ClaimIndex(by_key={}, pages_scanned=0, claims_parsed=0)

    for page in sorted(sources_root.rglob("*.md")):
        try:
            text = page.read_text(encoding="utf-8")
        except OSError as exc:
            warnings.append(f"could not read {to_rel(page, vault_root)}: {exc}")
            continue
        pages_scanned += 1
        fm_lines = extract_frontmatter_block(text)
        if fm_lines is None:
            continue
        page_rel = to_rel(page, vault_root) or page.name
        for value in extract_field_values(fm_lines, "raw_sources"):
            key = normalize_claim(value)
            if not key:
                continue
            claims_parsed += 1
            bucket = by_key.setdefault(key, [])
            if page_rel not in bucket:
                bucket.append(page_rel)
    return ClaimIndex(
        by_key={k: tuple(v) for k, v in by_key.items()},
        pages_scanned=pages_scanned,
        claims_parsed=claims_parsed,
    )


# ---------- Matching ----------


def suffix_keys(rel: str) -> list[str]:
    """Path suffixes of `rel`, most specific first, on segment boundaries."""
    parts = rel.lower().split("/")
    return ["/".join(parts[i:]) for i in range(len(parts))]


def match_file(raw: RawFile, claims: ClaimIndex) -> Coverage:
    """Resolve one raw file against the claim index (path first, then basename)."""
    keys = suffix_keys(raw.rel)
    for position, key in enumerate(keys):
        sources = claims.by_key.get(key)
        if not sources:
            continue
        is_basename_only = position == len(keys) - 1 and len(keys) > 1
        kind = MATCH_BASENAME if is_basename_only else MATCH_PATH
        return Coverage(raw=raw, sources=sources, match_kind=kind)
    return Coverage(raw=raw, sources=(), match_kind=MATCH_NONE)


def compute_coverage(files: list[RawFile], claims: ClaimIndex) -> list[Coverage]:
    return [match_file(raw, claims) for raw in files]


def folder_stats(rows: list[Coverage]) -> list[FolderStats]:
    totals: dict[str, int] = {}
    mapped: dict[str, int] = {}
    for row in rows:
        group = row.raw.group
        totals[group] = totals.get(group, 0) + 1
        mapped[group] = mapped.get(group, 0) + (1 if row.mapped else 0)
    return [
        FolderStats(folder=group, total=totals[group], mapped=mapped[group])
        for group in sorted(totals)
    ]


# ---------- Rendering ----------


def render_table(stats: list[FolderStats], overall: FolderStats) -> list[str]:
    width = max([len(s.folder) for s in stats] + [len("TOTAL")])
    header = f"  {'folder'.ljust(width)}  {'total':>6}  {'mapped':>6}  {'unmapped':>8}  {'coverage':>9}"
    lines = [header, "  " + "-" * (len(header) - 2)]
    for s in stats:
        lines.append(
            f"  {s.folder.ljust(width)}  {s.total:>6}  {s.mapped:>6}  "
            f"{s.unmapped:>8}  {s.coverage_pct:>8.1f}%"
        )
    lines.append("  " + "-" * (len(header) - 2))
    lines.append(
        f"  {'TOTAL'.ljust(width)}  {overall.total:>6}  {overall.mapped:>6}  "
        f"{overall.unmapped:>8}  {overall.coverage_pct:>8.1f}%"
    )
    return lines


def render_report(
    rows: list[Coverage],
    claims: ClaimIndex,
    vault_root: Path,
    scope: list[str],
    verbose: bool,
) -> list[str]:
    unmapped = [r for r in rows if not r.mapped]
    mapped = [r for r in rows if r.mapped]
    stats = folder_stats(rows)
    overall = FolderStats(folder="TOTAL", total=len(rows), mapped=len(mapped))

    out = [
        "=== ingest coverage ===",
        f"vault:   {vault_root}",
        f"scope:   {', '.join(scope)}",
        f"scanned: {claims.pages_scanned} source pages, {claims.claims_parsed} raw_sources claims",
        "",
    ]
    if not rows:
        out.append("No raw notes in scope — nothing to audit.")
        return out

    out.extend(render_table(stats, overall))

    if unmapped:
        out.extend(["", f"=== unmapped ({len(unmapped)}) ==="])
        for row in unmapped:
            suffix = f"   [{row.raw.label}]" if row.raw.label else ""
            out.append(f"  {row.raw.rel}{suffix}")

    if verbose and mapped:
        out.extend(["", f"=== mapped ({len(mapped)}) ==="])
        for row in mapped:
            marker = " (basename match)" if row.match_kind == MATCH_BASENAME else ""
            out.append(f"  {row.raw.rel}{marker}")
            for source in row.sources:
                out.append(f"    -> {source}")

    notes = build_notes(rows)
    if notes:
        out.append("")
        out.extend(notes)
    return out


def build_notes(rows: list[Coverage]) -> list[str]:
    """Caveats worth printing only when they actually apply."""
    notes: list[str] = []
    basename_only = sum(1 for r in rows if r.match_kind == MATCH_BASENAME)
    if basename_only:
        notes.append(
            f"note: {basename_only} file(s) matched a raw_sources claim by filename "
            f"alone. Two raw notes sharing a filename both count as mapped off one "
            f"claim — spot-check with --verbose."
        )
    manifest_unmapped = sum(
        1 for r in rows if not r.mapped and is_within(r.raw.rel, MANIFEST_FOLDER)
    )
    if manifest_unmapped:
        notes.append(
            f"note: {manifest_unmapped} unmapped file(s) live under {MANIFEST_FOLDER}/, "
            f"where {MANIFEST_PAGE} records deliberate skips. Check it before "
            f"treating them as a backlog."
        )
    if any(not r.mapped for r in rows):
        notes.append(
            "next: ingest what still matters, and let the rest sit — an unmapped "
            "note is a queue item, not a defect."
        )
    return notes


def build_json(
    rows: list[Coverage],
    claims: ClaimIndex,
    vault_root: Path,
    scope: list[str],
) -> dict:
    stats = folder_stats(rows)
    mapped_count = sum(1 for r in rows if r.mapped)
    overall = FolderStats(folder="TOTAL", total=len(rows), mapped=mapped_count)
    return {
        "vault_root": str(vault_root),
        "scope": scope,
        "source_pages_scanned": claims.pages_scanned,
        "claims_parsed": claims.claims_parsed,
        "totals": {
            "total": overall.total,
            "mapped": overall.mapped,
            "unmapped": overall.unmapped,
            "coverage_pct": overall.coverage_pct,
        },
        "folders": [
            {
                "folder": s.folder,
                "total": s.total,
                "mapped": s.mapped,
                "unmapped": s.unmapped,
                "coverage_pct": s.coverage_pct,
            }
            for s in stats
        ],
        "files": [
            {
                "path": r.raw.rel,
                "folder": r.raw.group,
                "mapped": r.mapped,
                "match_kind": r.match_kind,
                "sources": list(r.sources),
            }
            for r in rows
        ],
        "unmapped": [r.raw.rel for r in rows if not r.mapped],
    }


# ---------- Main ----------


def resolve_roots(vault_root: Path, requested: list[str]) -> tuple[list[Path], list[str]]:
    """Turn positional args into existing paths inside the vault.

    Returns (roots, errors). Errors are fatal (exit 2) — a typo'd folder
    silently reporting 100% coverage is the worst possible failure mode
    for this script.
    """
    raw_args = requested or [DEFAULT_RAW_DIR]
    roots: list[Path] = []
    errors: list[str] = []
    for arg in raw_args:
        path = Path(arg)
        if not path.is_absolute():
            path = vault_root / path
        path = path.resolve()
        if not path.exists():
            errors.append(f"path not found: {arg}")
            continue
        if to_rel(path, vault_root) is None:
            errors.append(f"path is outside the vault: {arg}")
            continue
        roots.append(path)
    return roots, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Report which raw notes have no wiki/sources/ page claiming them "
            "via raw_sources frontmatter."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help=f"Raw folders (or files) to audit. Default: {DEFAULT_RAW_DIR}/",
    )
    parser.add_argument(
        "--vault-root",
        default=".",
        help="Vault root (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the human summary",
    )
    parser.add_argument(
        "--unmapped-only",
        action="store_true",
        help="Print only unmapped paths, one per line (a JSON array with --json)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Also list mapped files and the source pages claiming them",
    )
    parser.add_argument(
        "--include-excluded",
        action="store_true",
        help=(
            "Audit folders normally treated as non-inputs "
            f"({', '.join(EXCLUDED_DIRS)}, {', '.join(EXCLUDED_FILES)})"
        ),
    )
    parser.add_argument(
        "--fail-on-unmapped",
        action="store_true",
        help="Exit 1 when anything is unmapped (opt-in; this is a report by default)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    vault_root = Path(args.vault_root).resolve()
    if not vault_root.is_dir():
        print(f"ERROR: vault-root not found: {vault_root}", file=sys.stderr)
        return 2

    roots, errors = resolve_roots(vault_root, args.paths)
    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        return 2
    if not roots:
        print("ERROR: no auditable paths resolved", file=sys.stderr)
        return 2

    warnings: list[str] = []
    files = collect_raw_files(vault_root, roots, args.include_excluded)
    claims = collect_claims(vault_root, warnings)
    rows = compute_coverage(files, claims)
    scope = [to_rel(root, vault_root) or str(root) for root in roots]

    for warning in warnings:
        print(f"WARN: {warning}", file=sys.stderr)

    unmapped = [r.raw.rel for r in rows if not r.mapped]

    if args.json:
        payload = unmapped if args.unmapped_only else build_json(rows, claims, vault_root, scope)
        print(json.dumps(payload, indent=2))
    elif args.unmapped_only:
        for rel in unmapped:
            print(rel)
    else:
        print("\n".join(render_report(rows, claims, vault_root, scope, args.verbose)))

    if unmapped and args.fail_on_unmapped:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
