#!/usr/bin/env python3
"""Unit tests for wiki-lint.py's novelty gate — NOV001 and FM008.

These two rules exist because of a specific incident, and the incident is the
fixture. On 2026-08-27 a three-book ingest wrote `entities/ivo-zembla.md` as a
first-ever vault mention with `first_seen: 2026-08-27`, and put the claim "first
vault mention — no prior reference to Zembla or Tarrow anywhere in `wiki/`" into
`wiki/log.md`. Both were false: Zembla had been in the vault since 2026-04-28 as
co-author of *The Lattice Firm*, live in seven pages.

Root cause was not a judgement error. `grep -rn "Zembla" wiki/ --include=*.md`
**dies** in zsh — the unquoted `*.md` is glob-expanded before grep runs — so the
command printed nothing, and the empty output was read as "term absent". The
whole page was then built on a search that never ran.

Two auto-review rounds caught it, at a cost of two CRITICAL findings and a
rewrite. A check catches it for free, and — unlike a convention telling the
agent which search tool to reach for — it targets the *claim* rather than the
keystroke, so it fires no matter how the wrong answer was arrived at.

  NOV001 (error, gate)  — prose on a SYNTHESIS page asserts novelty ("first
                          vault mention", "no prior reference", …) about a
                          subject that already appears elsewhere in the vault.
  --report first-seen   — ADVISORY: an entity's `first_seen` post-dates the
                          earliest page already mentioning its title/aliases.

Both scopes were narrowed after running the first draft over the real vault,
and the corrections are the interesting part:

  * `first_seen` was drafted as a hard gate (FM008). It fired on about half
    of a real vault's entity pages, because that vault's `first_seen` records when the entity
    PAGE was created, not the earliest mention. A gate that reddens half an
    untouched tree is not a gate. Demoted to advisory, same reasoning the
    module docstring already gives for `--report stale`.
  * NOV001 originally took "the nearest wikilink on the line" as the claim's
    subject, and reported `Steady Finish` as unfounded from a line whose
    actual claim was about four other books in a different clause. Subjects
    are now confined to the phrase's own clause.
  * NOV001 skips `wiki/log.md` and `wiki/log/*`. A log entry is a dated
    record: "no prior reference to X" was true the day it was written and
    stays in the file after that same ingest creates X.

KNOWN GAP, stated plainly: the Zembla claim that started all this lived in
`wiki/log.md`, which NOV001 now skips — so NOV001 alone would not have caught
it. What would have is `--report first-seen` on the newly minted entity page,
which is why CLAUDE.md's ingest step now calls it. Catching the log half needs
a diff-scoped run (claim vs the vault as it stood at commit time), the shape
`check-date-updated.py` already uses for FM007. Not built yet.

Cases shell out to the real entrypoint, matching test_wiki_lint.py's reasoning:
`apply_config()` rebinds module globals, so in-process cases would leak config
into each other — exactly the false green these files exist to prevent.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "wiki-lint.py"
CHECK = "novelty-claims"


class NoveltyVaultMixin:
    """Builds a throwaway vault and runs the novelty check over it."""

    def run_lint(self, pages: dict[str, str], check: str = CHECK):
        """pages: {relative path under vault root: file body}.

        Returns (exit_code, combined_output).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, body in pages.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body, encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--check", check,
                    "--vault-root", str(root),
                    str(root / "wiki"),
                ],
                capture_output=True, text=True,
            )
            return proc.returncode, proc.stdout + proc.stderr

    def run_report(self, pages: dict[str, str], report: str = "first-seen"):
        """Run an advisory report. Reports always exit 0 — the signal is text."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, body in pages.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body, encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--report", report,
                    "--vault-root", str(root),
                    str(root / "wiki"),
                ],
                capture_output=True, text=True,
            )
            return proc.returncode, proc.stdout + proc.stderr


def entity(title: str, first_seen: str, body: str = "", aliases: list[str] | None = None) -> str:
    alias_line = f"aliases: {json.dumps(aliases)}\n" if aliases else ""
    return (
        "---\n"
        "type: entity\n"
        "entity_type: person\n"
        f'title: "{title}"\n'
        f"{alias_line}"
        f"first_seen: {first_seen}\n"
        "source_count: 1\n"
        "---\n\n"
        f"# {title}\n\n{body}\n"
    )


def source(title: str, date_ingested: str, body: str = "") -> str:
    return (
        "---\n"
        "type: source\n"
        f'title: "{title}"\n'
        "raw_sources:\n"
        '  - "raw/books/x.md"\n'
        f"date_ingested: {date_ingested}\n"
        "---\n\n"
        f"# {title}\n\n{body}\n"
    )


class NoveltyClaimTest(NoveltyVaultMixin, unittest.TestCase):
    """NOV001 — a novelty assertion whose subject is already in the vault."""

    def test_the_gary_zembla_incident(self):
        """The exact shape of the 2026-08-27 miss, end to end."""
        code, out = self.run_lint({
            "wiki/entities/ivo-zembla.md": entity(
                "Ivo Zembla", "2026-08-27",
                "Management theorist and co-author of *Humanocracy*.",
            ),
            "wiki/topics/organizational-design.md": (
                '---\ntype: topic\ntitle: "Organizational Design"\n---\n\n'
                "# Organizational Design\n\n"
                "Added [[entities/ivo-zembla|Ivo Zembla]] — first vault mention.\n"
            ),
            "wiki/sources/book-management-essentials.md": source(
                "Management Essentials", "2026-04-28",
                "### 10. The Lattice Firm — "
                "R.V. Ostrander & Ivo Zembla (1990)\n",
            ),
        })
        self.assertEqual(code, 1, out)
        self.assertIn("NOV001", out)
        self.assertIn("Ivo Zembla", out)

    def test_novelty_claim_with_no_prior_mention_passes(self):
        """The claim is allowed to be TRUE — this is the false-positive guard."""
        code, out = self.run_lint({
            "wiki/entities/newcomer.md": entity("Ada Newcomer", "2026-08-27"),
            "wiki/topics/t.md": (
                '---\ntype: topic\ntitle: "T"\n---\n\n# T\n\n'
                "Added [[entities/newcomer|Ada Newcomer]] — first vault mention.\n"
            ),
            "wiki/sources/unrelated.md": source(
                "Something Else", "2026-04-28", "Nothing to do with anyone.\n"),
        })
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV001", out)

    def test_page_making_the_claim_is_excluded_from_its_own_search(self):
        """The subject naturally appears on the very page asserting novelty;
        counting that as a prior mention would make every claim unprovable."""
        code, out = self.run_lint({
            "wiki/entities/solo.md": entity(
                "Solo Person", "2026-08-27",
                "Solo Person is a first vault mention. Solo Person again.",
            ),
        })
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV001", out)

    def test_all_novelty_phrasings_are_detected(self):
        """Each phrasing the vault has actually used, one page each."""
        for phrase in (
            "first vault mention",
            "no prior reference",
            "first mention in the vault",
            "not previously in the vault",
            "new to the vault",
            "first time in the vault",
        ):
            with self.subTest(phrase=phrase):
                code, out = self.run_lint({
                    "wiki/entities/repeat-guy.md": entity("Repeat Guy", "2026-08-27"),
                    "wiki/topics/t.md": (
                        '---\ntype: topic\ntitle: "T"\n---\n\n# T\n\n'
                        f"[[entities/repeat-guy|Repeat Guy]] — {phrase}.\n"
                    ),
                    "wiki/sources/old.md": source(
                        "Old Source", "2026-01-01", "Repeat Guy said something once.\n"),
                })
                self.assertEqual(code, 1, out)
                self.assertIn("NOV001", out)

    def test_subject_is_taken_from_the_wikilink_on_the_claim_line(self):
        """Subject resolution: the display text of the nearest wikilink."""
        code, out = self.run_lint({
            "wiki/entities/jane-doe.md": entity("Jane Doe", "2026-08-27"),
            "wiki/topics/t.md": (
                '---\ntype: topic\ntitle: "T"\n---\n\n# T\n\n'
                "Created [[entities/jane-doe|Jane Doe]] — first vault mention.\n"
            ),
            "wiki/topics/somewhere.md": (
                "---\ntype: topic\ntitle: \"Somewhere\"\n---\n\n"
                "# Somewhere\n\nJane Doe turned up here months ago.\n"
            ),
        })
        self.assertEqual(code, 1, out)
        self.assertIn("NOV001", out)

    def test_quoted_novelty_claim_is_not_flagged(self):
        """A page DESCRIBING a past false claim (as wiki/log.md now does) must
        not re-trip the gate — this is the self-referential trap."""
        code, out = self.run_report({
            "wiki/entities/ivo-zembla.md": entity("Ivo Zembla", "2026-04-28"),
            "wiki/topics/t.md": (
                '---\ntype: topic\ntitle: "T"\n---\n\n# T\n\n'
                "[[entities/ivo-zembla|Ivo Zembla]] — **not** a first vault "
                "mention: the ingest recorded him as new, which was wrong.\n"
            ),
            "wiki/sources/book-management-essentials.md": source(
                "Management Essentials", "2026-04-28", "Ostrander & Ivo Zembla (1990).\n"),
        })
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV001", out)

    def test_raw_folder_is_not_searched_for_prior_mentions(self):
        """`raw/` is immutable source, not vault synthesis. A name appearing in
        a transcript is not a prior *wiki* mention."""
        code, out = self.run_lint({
            "wiki/entities/booky.md": entity("Booky Author", "2026-08-27"),
            "wiki/topics/t.md": (
                '---\ntype: topic\ntitle: "T"\n---\n\n# T\n\n'
                "[[entities/booky|Booky Author]] — first vault mention.\n"
            ),
            "raw/books/some-book.md": "Booky Author wrote this whole book.\n",
        })
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV001", out)


class FirstSeenTest(NoveltyVaultMixin, unittest.TestCase):
    """`--report first-seen` — ADVISORY, never a gate.

    Drafted as hard gate FM008 and demoted after it fired on about half of a
    real vault's entity pages. Every case here asserts exit 0: the report's contract is to
    inform, never to redden CI. What it must still do is NAME the page, which
    is the half that would have caught the Zembla incident.
    """

    def test_report_never_fails_the_build(self):
        """The demotion itself, pinned. If someone re-promotes this to a gate,
        this is the test that should stop them."""
        code, out = self.run_report({
            "wiki/entities/ivo-zembla.md": entity("Ivo Zembla", "2026-08-27"),
            "wiki/sources/older.md": source("Older", "2026-04-28", "Ivo Zembla.\n"),
        })
        self.assertEqual(code, 0, out)

    def test_first_seen_later_than_an_existing_mention(self):
        """The frontmatter half of the Zembla incident — the report must name it."""
        code, out = self.run_report({
            "wiki/entities/ivo-zembla.md": entity("Ivo Zembla", "2026-08-27"),
            "wiki/sources/book-management-essentials.md": source(
                "Management Essentials", "2026-04-28", "Ostrander & Ivo Zembla (1990).\n"),
        })
        self.assertEqual(code, 0, out)
        self.assertIn("ivo-zembla.md", out)
        self.assertIn("2026-04-28", out)

    def test_first_seen_matching_earliest_mention_passes(self):
        """Same-day is fine: the entity page and its first source arrive in the
        same ingest, which is the normal case, not a defect."""
        code, out = self.run_report({
            "wiki/entities/ivo-zembla.md": entity("Ivo Zembla", "2026-04-28"),
            "wiki/sources/book-management-essentials.md": source(
                "Management Essentials", "2026-04-28", "Ostrander & Ivo Zembla (1990).\n"),
        })
        self.assertEqual(code, 0, out)
        self.assertIn("No entity page has a first_seen later", out)

    def test_first_seen_earlier_than_any_mention_passes(self):
        """Earlier is always fine — first_seen records when the PERSON entered
        the owner's world, which can predate the vault noticing."""
        code, out = self.run_report({
            "wiki/entities/ivo-zembla.md": entity("Ivo Zembla", "2020-01-01"),
            "wiki/sources/book-management-essentials.md": source(
                "Management Essentials", "2026-04-28", "Ostrander & Ivo Zembla (1990).\n"),
        })
        self.assertEqual(code, 0, out)
        self.assertIn("No entity page has a first_seen later", out)

    def test_alias_match_counts_as_a_prior_mention(self):
        """The Zembla material was filed as 'Ostrander & Zembla' — a bare-surname
        alias. Title-only matching would have missed it."""
        code, out = self.run_report({
            "wiki/entities/ivo-zembla.md": entity(
                "Ivo Zembla", "2026-08-27", aliases=["Gary P. Zembla"]),
            "wiki/sources/older.md": source(
                "Older", "2026-04-28", "Work by Gary P. Zembla appears here.\n"),
        })
        self.assertEqual(code, 0, out)
        self.assertIn("ivo-zembla.md", out)

    def test_undated_pages_are_ignored(self):
        """A mention on a page with no usable date cannot bound first_seen —
        listing it would make the rule unsatisfiable."""
        code, out = self.run_report({
            "wiki/entities/ivo-zembla.md": entity("Ivo Zembla", "2026-08-27"),
            "wiki/topics/undated.md": (
                "---\ntype: topic\ntitle: \"Undated\"\n---\n\n"
                "# Undated\n\nIvo Zembla is mentioned but this page has no date.\n"
            ),
        })
        self.assertEqual(code, 0, out)
        self.assertIn("No entity page has a first_seen later", out)

    def test_entity_without_first_seen_is_not_flagged(self):
        """`first_seen` is a RECOMMENDED key (FM006's job), not required."""
        body = (
            "---\ntype: entity\nentity_type: person\n"
            'title: "Ivo Zembla"\nsource_count: 1\n---\n\n# Ivo Zembla\n'
        )
        code, out = self.run_report({
            "wiki/entities/ivo-zembla.md": body,
            "wiki/sources/older.md": source("Older", "2026-04-28", "Ivo Zembla.\n"),
        })
        self.assertEqual(code, 0, out)
        self.assertIn("No entity page has a first_seen later", out)

    def test_short_titles_do_not_substring_match(self):
        """A two-letter entity title must not match inside unrelated words —
        the false-positive risk that would make this rule unusable."""
        code, out = self.run_report({
            "wiki/entities/al.md": entity("Al", "2026-08-27"),
            "wiki/sources/older.md": source(
                "Older", "2026-04-28", "The album was also always alright.\n"),
        })
        self.assertEqual(code, 0, out)
        self.assertIn("No entity page has a first_seen later", out)


class NoveltyGateWiringTest(NoveltyVaultMixin, unittest.TestCase):
    """The gate has to actually be wired into the default run to be a gate."""

    def test_novelty_check_runs_by_default(self):
        """No --check flag: NOV001 must still fire. A rule nobody runs is not
        a gate, and this is exactly how a well-meaning refactor disables one."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, body in {
                "wiki/entities/ivo-zembla.md": entity("Ivo Zembla", "2026-04-28"),
                "wiki/topics/od.md": (
                    '---\ntype: topic\ntitle: "OD"\n---\n\n# OD\n\n'
                    "Added [[entities/ivo-zembla|Ivo Zembla]] — first vault mention.\n"
                ),
                "wiki/sources/book-management-essentials.md": source(
                    "Management Essentials", "2026-04-28", "Ostrander & Ivo Zembla.\n"),
            }.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body, encoding="utf-8")
            # satisfy FM005 so FM008 is the only thing that can redden this run
            raw = root / "raw" / "books" / "x.md"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text("x\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault-root", str(root), str(root / "wiki")],
                capture_output=True, text=True,
            )
            out = proc.stdout + proc.stderr
            self.assertEqual(proc.returncode, 1, out)
            self.assertIn("NOV001", out)

    def test_check_name_is_selectable(self):
        code, out = self.run_lint({
            "wiki/entities/x.md": entity("Someone New", "2026-08-27"),
        })
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
