#!/usr/bin/env python3
"""FM007 — date_updated freshness gate (CI-only, git-aware).

Fails if a synthesis page's non-frontmatter body changed in this commit/PR
but its `date_updated` frontmatter field was not bumped.

Synthesis pages in scope: wiki/insights/, wiki/topics/, wiki/plans/,
wiki/projects/. Only files with `date_updated` present in both the old and
new versions are checked — missing `date_updated` is a separate FM006 concern.

Stdlib-only. Requires git on PATH.

Usage:
  python3 .claude/scripts/check-date-updated.py --base <sha>
  python3 .claude/scripts/check-date-updated.py --base <sha> --gh-annotations
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SYNTHESIS_PREFIXES = (
    "wiki/insights/",
    "wiki/topics/",
    "wiki/plans/",
    "wiki/projects/",
)


def get_changed_files(base: str) -> list[str]:
    """Return repo-relative paths of files Modified between base and HEAD."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=M", base, "HEAD", "--"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [f for f in result.stdout.splitlines() if f]


def extract_frontmatter_and_body(text: str) -> tuple[dict[str, str], str]:
    """Return (fm_dict, body) where body is everything after the closing ---.

    Returns ({}, full_text) if no frontmatter block is found.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_idx: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i + 1
            break
    if end_idx is None:
        return {}, text

    fm_lines = lines[1 : end_idx - 1]
    body = "".join(lines[end_idx:])

    fm: dict[str, str] = {}
    for line in fm_lines:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip("\"'")
    return fm, body


def strip_recent_updates_callout(body: str) -> str:
    """Remove the leading `> **Recent updates**` blockquote from a body.

    The callout is metadata *about* updates, not page content — rolling old
    entries off (RU004 discipline) must not require a `date_updated` bump.
    """
    lines = body.splitlines(keepends=True)
    header_re = re.compile(r"^\s*>\s*\*\*Recent updates\*\*", re.IGNORECASE)
    start = None
    for i, line in enumerate(lines):
        if header_re.match(line):
            start = i
            break
        if re.match(r"^#\s+", line):
            return body  # callout must precede H1; none found
        if line.strip():
            return body  # hit non-blank, non-callout content first
    if start is None:
        return body
    end = start + 1
    while end < len(lines) and lines[end].lstrip().startswith(">"):
        end += 1
    return "".join(lines[:start] + lines[end:])


def get_file_at_ref(ref: str, path: str) -> str | None:
    """Return file content at git ref, or None if the file did not exist there."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description="FM007 date_updated freshness gate")
    parser.add_argument("--base", required=True, help="Base git SHA to diff against")
    parser.add_argument(
        "--gh-annotations",
        action="store_true",
        help="Emit GitHub Actions annotation syntax",
    )
    args = parser.parse_args()

    try:
        changed = get_changed_files(args.base)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: git diff failed: {e.stderr.strip()}", file=sys.stderr)
        return 2

    errors: list[tuple[str, str]] = []

    for filepath in changed:
        if not filepath.endswith(".md"):
            continue
        if not any(filepath.startswith(p) for p in SYNTHESIS_PREFIXES):
            continue

        try:
            current_text = Path(filepath).read_text(encoding="utf-8")
        except FileNotFoundError:
            continue

        old_text = get_file_at_ref(args.base, filepath)
        if old_text is None:
            continue  # file was added, not modified — new pages don't need a bump

        current_fm, current_body = extract_frontmatter_and_body(current_text)
        old_fm, old_body = extract_frontmatter_and_body(old_text)

        current_body = strip_recent_updates_callout(current_body)
        old_body = strip_recent_updates_callout(old_body)

        if current_body.strip() == old_body.strip():
            continue  # frontmatter-only or callout-only change — no bump required

        current_date = current_fm.get("date_updated", "").strip().strip("\"'")
        old_date = old_fm.get("date_updated", "").strip().strip("\"'")

        # Only fire when date_updated is present in both versions but unchanged.
        if current_date and old_date and current_date == old_date:
            errors.append(
                (
                    filepath,
                    f"Body changed but `date_updated` not bumped (still `{current_date}`)",
                )
            )

    for filepath, msg in errors:
        if args.gh_annotations:
            safe_msg = re.sub(r"[\r\n]", " ", msg).replace("::", ":")
            print(f"::error file={filepath},line=1,col=1,title=FM007::{safe_msg}")
        else:
            print(f"ERROR {filepath}:1:1  FM007  {msg}")

    if errors:
        print(
            f"\n{len(errors)} FM007 error(s): bump `date_updated` when editing a synthesis page body.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
