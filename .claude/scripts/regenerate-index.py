#!/usr/bin/env python3
"""Reconcile wiki/index.md against the filesystem.

The wiki index is a catalog of every wiki page. Its per-section counts and
membership drift whenever a page is added/removed without a matching manual
edit. This script reconciles it:

- Filesystem + frontmatter drive: which pages exist, their titles, the
  per-section counts, and `total_pages`.
- Editorial one-line descriptions are PRESERVED by harvesting them from the
  current index.md (frontmatter carries no description field).
- New pages (on disk, absent from the index) are appended to their section,
  flagged `NEW - describe` so the description gap is visible.
- Orphan entries (in the index, file deleted) are dropped and reported.
- Hand-curated sections (Overview, Raw Source Inventory) are preserved verbatim.
- `total_sources_ingested` / `total_raw_sources` are preserved as-is — they are
  not derivable from wiki frontmatter.
- `date_updated` is bumped only when the catalog body actually changes, so the
  script is idempotent (safe to run in CI as a drift check).

Usage:
  python3 .claude/scripts/regenerate-index.py            # rewrite index.md
  python3 .claude/scripts/regenerate-index.py --check     # exit 1 if drift, no write
"""

import re
import sys
from datetime import date
from pathlib import Path

VAULT = Path(__file__).resolve().parents[2]
WIKI = VAULT / "wiki"
INDEX = WIKI / "index.md"

# Catalog sections, in the order they appear in the index, mapped to their dir.
SECTIONS = [
    ("Entities", "entities"),
    ("Topics", "topics"),
    ("Sources", "sources"),
    ("Insights", "insights"),
    ("Plans", "plans"),
    ("Projects", "projects"),
]

TODAY = date.today().isoformat()
NEW_MARKER = " — NEW - describe (auto-flagged by regenerate-index.py)"

# slug, optional |title, then everything after ]] captured verbatim as the tail
# (the tail may be " — desc", " (parenthetical) — desc", or empty).
ENTRY_RE = re.compile(r"^- \[\[([^\]|]+)(?:\|([^\]]+))?\]\](.*)$")

def read_frontmatter_title(path: Path) -> str:
    """Return the `title:` value from a page's frontmatter, unquoted."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return path.stem
    for line in m.group(1).splitlines():
        tm = re.match(r"\s*title:\s*(.+?)\s*$", line)
        if tm:
            val = tm.group(1).strip()
            if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
                val = val[1:-1]
            return val
    return path.stem

def parse_index():
    """Parse the current index into (frontmatter_lines, intro, blocks).

    blocks is an ordered list of either:
      ("static", raw_text)               — verbatim block (Overview, Raw Inventory, etc.)
      ("catalog", section_name, entries) — entries is list of (slug, title, desc)
    """
    text = INDEX.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not fm_match:
        raise SystemExit("index.md has no frontmatter")
    fm_lines = fm_match.group(1).splitlines()
    body = text[fm_match.end():]

    lines = body.splitlines()
    # Split into chunks at H2 headers.
    section_names = {name for name, _ in SECTIONS}
    blocks = []
    intro_lines = []
    i = 0
    # Intro = everything before the first '## '
    while i < len(lines) and not lines[i].startswith("## "):
        intro_lines.append(lines[i])
        i += 1
    intro = "\n".join(intro_lines)

    while i < len(lines):
        header = lines[i]
        h2_match = re.match(r"^## (.+?)(?:\s*\((.*?)\))?\s*$", header)
        sec_name = h2_match.group(1).strip() if h2_match else None
        # Collect until next H2.
        chunk = [lines[i]]
        i += 1
        while i < len(lines) and not lines[i].startswith("## "):
            chunk.append(lines[i])
            i += 1

        if sec_name in section_names:
            entries = []
            has_trailing_rule = False  # a '---' divider after the entries (preserved)
            for ln in chunk[1:]:
                em = ENTRY_RE.match(ln)
                if em:
                    slug = em.group(1).strip()
                    title = (em.group(2) or "").strip()
                    tail = em.group(3)  # verbatim — preserves dash style + parentheticals
                    entries.append((slug, title, tail))
                elif ln.strip() == "---":
                    has_trailing_rule = True
            blocks.append(("catalog", sec_name, entries, has_trailing_rule))
        else:
            blocks.append(("static", "\n".join(chunk)))

    return fm_lines, intro, blocks

def reconcile():
    fm_lines, intro, blocks = parse_index()

    report = []
    total_pages = 0

    # Build new catalog section data keyed by section name.
    new_catalog = {}
    for sec_name, sec_dir in SECTIONS:
        disk_files = sorted((WIKI / sec_dir).rglob("*.md"))
        disk_slugs = {}
        for f in disk_files:
            slug = str(f.relative_to(WIKI)).replace("\\", "/")[:-3]  # drop .md
            disk_slugs[slug] = f

        # Existing entries for this section, in index order.
        existing = []
        for blk in blocks:
            if blk[0] == "catalog" and blk[1] == sec_name:
                existing = blk[2]
                break
        existing_slugs = {e[0] for e in existing}

        # Existing entries pass through verbatim (slug, title, tail) — only their
        # continued existence on disk is checked. New pages are appended.
        kept, orphans, added = [], [], []
        for slug, title, tail in existing:
            if slug in disk_slugs:
                kept.append((slug, title, tail))
            else:
                orphans.append(slug)

        for slug in sorted(disk_slugs):
            if slug not in existing_slugs:
                fm_title = read_frontmatter_title(disk_slugs[slug])
                added.append((slug, fm_title, NEW_MARKER))

        new_entries = kept + added
        new_catalog[sec_name] = new_entries
        total_pages += len(new_entries)

        if orphans or added or len(existing) != len(new_entries):
            report.append(
                f"  {sec_name}: {len(existing)} -> {len(new_entries)}"
                + (f" | +{len(added)} new" if added else "")
                + (f" | -{len(orphans)} orphan" if orphans else "")
            )
            for slug in added:
                report.append(f"      + {slug[0]}")
            for slug in orphans:
                report.append(f"      - {slug} (orphan, dropped)")

    # Render the new body.
    out = [intro.strip(), ""]
    for blk in blocks:
        if blk[0] == "static":
            out.append(blk[1].rstrip())
            out.append("")
        else:
            sec_name = blk[1]
            has_trailing_rule = blk[3]
            entries = new_catalog[sec_name]
            out.append(f"## {sec_name} ({len(entries)})")
            for slug, title, tail in entries:
                link = f"[[{slug}|{title}]]" if title else f"[[{slug}]]"
                out.append(f"- {link}{tail}")
            if has_trailing_rule:
                out.append("")
                out.append("---")
            out.append("")
    new_body = "\n".join(out).rstrip() + "\n"

    # Frontmatter: update total_pages, conditionally bump date_updated.
    old_body = INDEX.read_text(encoding="utf-8")
    old_fm_match = re.match(r"^---\n(.*?)\n---\n", old_body, re.DOTALL)
    old_body_only = old_body[old_fm_match.end():]
    body_changed = new_body.strip() != old_body_only.strip()

    new_fm = []
    for line in fm_lines:
        if line.startswith("total_pages:"):
            new_fm.append(f"total_pages: {total_pages}")
        elif line.startswith("date_updated:") and body_changed:
            new_fm.append(f"date_updated: {TODAY}")
        else:
            new_fm.append(line)
    # Ensure total_pages is present.
    if not any(l.startswith("total_pages:") for l in new_fm):
        new_fm.append(f"total_pages: {total_pages}")

    new_index = "---\n" + "\n".join(new_fm) + "\n---\n\n" + new_body

    return new_index, old_body, body_changed, report, total_pages

def main():
    check_only = "--check" in sys.argv
    new_index, old_index, body_changed, report, total_pages = reconcile()

    drift = new_index != old_index
    print(f"Catalog total_pages: {total_pages}")
    if report:
        print("Drift detected:")
        print("\n".join(report))
    else:
        print("No catalog drift.")

    if check_only:
        if drift:
            print("\n--check: index.md is OUT OF DATE. Run without --check to fix.")
            sys.exit(1)
        print("--check: index.md is up to date.")
        sys.exit(0)

    if drift:
        INDEX.write_text(new_index, encoding="utf-8")
        print(f"\nRewrote {INDEX.relative_to(VAULT)}")
    else:
        print("\nNo changes written (already current).")

if __name__ == "__main__":
    main()
