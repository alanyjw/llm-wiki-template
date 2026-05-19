#!/usr/bin/env python3
"""Layer 2 of the wiki-lint pipeline.

Three checks the vendor tool (markdownlint-obsidian) can't do correctly today:

1. table-pipe-in-wikilink — Obsidian renderer quirk: [[X|Y]] inside a
   markdown table cell breaks the table because the inner `|` is parsed
   as a column separator. The vendor tool's parser is too "correct" to
   flag this, but Obsidian renders it broken. Fix: \\| escape.

2. broken-wikilink (Obsidian-fuzzy resolution) — vendor tool uses
   path-based resolution from --vault-root, which can't handle this
   vault's mixed [[sources/foo]] (wiki-implicit) + [[raw/notes-import/foo]]
   (vault-absolute) link conventions. Reimplements Obsidian's name-fuzzy
   resolution (path suffix-match against vault file index).

3. frontmatter-schema (per-type required fields) — per CLAUDE.md:
   - source: requires raw_sources (provenance principle)
   - plan:   requires status
   - project: requires status
   - insight: requires confidence

Output:
- Human-readable to stdout (file:line:col CODE message)
- GitHub Actions annotations to stdout when --gh-annotations is passed
  (::error/::warning syntax that GH renders on the diff)

Exit codes:
- 0 = clean (no errors; warnings allowed)
- 1 = errors found
- 2 = script failure (e.g. vault not found)

Usage:
  python3 .claude/scripts/wiki-lint.py wiki/
  python3 .claude/scripts/wiki-lint.py wiki/ --gh-annotations
  python3 .claude/scripts/wiki-lint.py --check table-pipe wiki/
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------- Models ----------

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

# Per-type required frontmatter keys, per CLAUDE.md schemas.
REQUIRED_KEYS_BY_TYPE: dict[str, list[str]] = {
    "source": ["title", "raw_sources"],
    "entity": ["title", "entity_type"],
    "topic": ["title"],
    "insight": ["title", "confidence"],
    "plan": ["title", "status"],
    "project": ["title", "status"],
    # Special pages — minimal requirements
    "overview": [],
    "index": [],
    "log": [],
    "log-archive": [],
    "glossary": [],
    "glossary-split": [],
    "manifest": [],
    "backlog": [],
    "digest": [],
}

CHECK_TABLE_PIPE = "table-pipe"
CHECK_BROKEN_WIKILINK = "broken-wikilink"
CHECK_FRONTMATTER = "frontmatter-schema"
ALL_CHECKS = [CHECK_TABLE_PIPE, CHECK_BROKEN_WIKILINK, CHECK_FRONTMATTER]


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
            or "foo.png" or "raw/notes-import/2020-01-01-sample-note".
    Returns: list of matching paths (0 = broken, 1 = unique, 2+ = ambiguous).
    """
    needle = target.strip().replace("\\", "/")
    if not needle:
        return []
    # If no extension, assume .md. Use a tight extension regex so version-y
    # filenames like "Project 4.1 Meeting" aren't misread as having an extension.
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


# ---------- Markdown structure helpers ----------


CODE_FENCE_RE = re.compile(r"^(\s*)(```|~~~)")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
WIKILINK_RE = re.compile(r"\[\[([^\[\]\n]+?)\]\]")


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
    """Flag wikilinks whose target can't be resolved via Obsidian-fuzzy match.

    Skips:
    - wikilinks in code blocks
    - wikilinks in frontmatter (raw_sources strings — those are validated
      separately in check_frontmatter_schema)
    - external URLs (these aren't wikilinks anyway)
    - empty targets
    """
    for lineno, line, in_code, in_fm in iter_lines_with_context(text):
        if in_code or in_fm:
            continue
        # Skip inline code spans — find them and blank them out
        scrubbed = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line)
        for m in WIKILINK_RE.finditer(scrubbed):
            inner = m.group(1)
            # Strip embed marker handled by callers via leading `!` — we
            # don't currently distinguish; both linked and embedded targets
            # need to resolve.
            # Drop alias — Obsidian treats both `|` and `\|` as the alias
            # separator (`\|` is the table-cell-escaped form). Split on the
            # first occurrence of either.
            target_part = re.split(r"\\?\|", inner, maxsplit=1)[0]
            # Drop anchor
            target = target_part.split("#", 1)[0].strip()
            if not target:
                continue
            # Skip URLs (rare in wikilinks but possible)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            matches = resolve_wikilink(target, vault_root, index)
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
            # Anchor check (only for unique resolved file)
            anchor = ""
            if "#" in target_part:
                # Anchor may be followed by an alias inside the same wikilink
                # (e.g. [[file#anchor|alias]]); we only want the part before `|`.
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
    """Check whether an anchor matches any heading in the target file.

    Obsidian normalizes headings by stripping markdown formatting and
    matching loosely. We do exact match first, then a permissive match
    (case-insensitive, punctuation-stripped).
    """
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
        # No frontmatter at all — flag if file is in a synthesis folder
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
        # Unknown type — warn but don't fail
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
        # Top-level key: `key: value` or `key:` (then list/block follows)
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if m:
            current_key = m.group(1)
            value = m.group(2).strip()
            fm[current_key] = value
        elif current_key and line.startswith(" "):
            # Continuation (list item, multiline) — preserve presence
            if not fm.get(current_key):
                fm[current_key] = line.strip()
    return fm, 1


# ---------- Output ----------


def emit_default(findings: list[Finding]) -> None:
    for f in findings:
        prefix = "ERROR" if f.severity == SEVERITY_ERROR else "WARN "
        print(f"{prefix} {f.file}:{f.line}:{f.col}  {f.code}  {f.message}")


def emit_gh_annotations(findings: list[Finding]) -> None:
    for f in findings:
        kind = "error" if f.severity == SEVERITY_ERROR else "warning"
        # Strip ::, %, \r, \n from message to avoid breaking GH parser
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
    parser.add_argument("--gh-annotations", action="store_true", help="Emit GitHub Actions annotation syntax")
    parser.add_argument("--vault-root", default=".", help="Vault root for wikilink resolution")
    args = parser.parse_args()

    enabled_checks = set(args.check or ALL_CHECKS)
    vault_root = Path(args.vault_root).resolve()
    if not vault_root.exists():
        print(f"ERROR: vault-root not found: {vault_root}", file=sys.stderr)
        return 2

    # Build vault file index once (for wikilink resolution)
    index: dict[str, list[Path]] = {}
    if CHECK_BROKEN_WIKILINK in enabled_checks:
        index = build_vault_index(vault_root)

    # Collect target files
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

    # Output
    if args.gh_annotations:
        emit_gh_annotations(findings)
    else:
        emit_default(findings)
    emit_summary(findings)

    errors = sum(1 for f in findings if f.severity == SEVERITY_ERROR)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
