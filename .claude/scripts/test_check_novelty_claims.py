#!/usr/bin/env python3
"""Unit tests for .claude/scripts/check-novelty-claims.py (NOV002).

The half of the novelty problem that NOV001 structurally cannot cover.

NOV001 (in wiki-lint.py) is content-keyed: it reads the tree as it stands and
asks "is this claim true now". That works on synthesis pages, whose claims are
supposed to stay true. It is the wrong question for `wiki/log.md`, which is a
dated record — "no prior reference to X" was true the day it was written and
stays in the file after that same ingest creates X. Content-keying the log
produced a real false positive: a line claiming no prior reference to four
books was reported as an unfounded claim about `Steady Finish`.

So NOV001 skips the log. Which left the actual 2026-08-27 incident uncovered,
because the false claim lived exactly there:

    - **Created**: … [[entities/ivo-zembla]] (first vault mention — no prior
      reference to Zembla or Tarrow anywhere in `wiki/`).

NOV002 asks the question the log deserves: **was the claim true at the moment
it was committed?** It diffs against a base SHA, takes only ADDED lines, and
searches the vault *as it stood at base*. That is the same shape FM007 uses in
`check-date-updated.py`, and it resolves both cases at once:

  * the Zembla claim FAILS — `wiki/sources/book-management-essentials.md` held "Gary
    Zembla" at base, so the claim was false when written;
  * the four-books claim PASSES — those pages did not exist at base, so the
    claim was true when written, and stays passing forever after.

Pages created in the same commit need no special-casing: they are absent from
the base tree, so they cannot be found as prior mentions. That falls out of
diff-scoping rather than being a rule anyone has to maintain.

Each case builds a real git repo in a tmpdir. Shelling out to git rather than
faking it is the point — the rule's whole substance is what `git grep <base>`
returns, and a stubbed VCS would test the stub.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-novelty-claims.py"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


class NoveltyDiffMixin:
    """Builds a two-commit repo and runs the check across the pair."""

    def run_check(self, base_files: dict[str, str], head_files: dict[str, str]):
        """base_files -> commit 1; head_files -> commit 2 (added/overwritten).

        Returns (exit_code, combined_output).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q", "-b", "main")
            git(root, "config", "user.email", "t@example.com")
            git(root, "config", "user.name", "T")
            git(root, "config", "commit.gpgsign", "false")

            for rel, body in base_files.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body, encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "base")
            base_sha = git(root, "rev-parse", "HEAD").strip()

            for rel, body in head_files.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body, encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "head")

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--base", base_sha],
                cwd=root, capture_output=True, text=True,
            )
            return proc.returncode, proc.stdout + proc.stderr


LOG_HEAD = "---\ntype: log\n---\n\n# Wiki Log\n\n"


class TheIncidentTest(NoveltyDiffMixin, unittest.TestCase):
    """The 2026-08-27 miss, reproduced end to end."""

    def test_zembla_claim_is_caught(self):
        code, out = self.run_check(
            base_files={
                "wiki/sources/book-management-essentials.md": (
                    "# Management Essentials\n\n"
                    "### 10. The Lattice Firm — "
                    "R.V. Ostrander & Ivo Zembla (1990)\n"
                ),
                "wiki/log.md": LOG_HEAD + "- an earlier entry\n",
            },
            head_files={
                "wiki/entities/ivo-zembla.md": "# Ivo Zembla\n\nManagement theorist.\n",
                "wiki/log.md": LOG_HEAD + (
                    "- **Created**: [[entities/ivo-zembla]] (first vault mention — "
                    "no prior reference to Zembla or Tarrow anywhere in `wiki/`).\n"
                ),
            },
        )
        self.assertEqual(code, 1, out)
        self.assertIn("NOV002", out)
        self.assertIn("book-management-essentials.md", out)

    def test_the_four_books_false_positive_does_not_recur(self):
        """The line that content-keyed NOV001 got wrong. Those pages did not
        exist at base, so the claim was TRUE when written and must pass — now
        and every time CI runs afterwards."""
        code, out = self.run_check(
            base_files={"wiki/log.md": LOG_HEAD + "- older entry\n"},
            head_files={
                "wiki/sources/book-slow-decline.md": "# The Slow Decline\n",
                "wiki/sources/book-daily-ask.md": "# The Daily Ask\n",
                "wiki/log.md": LOG_HEAD + (
                    "- **Method**: checked existing wiki coverage (no prior "
                    "references to *The Slow Decline* / *The Daily Ask*); "
                    "read [[topics/steady-finish]] for landing-page state\n"
                ),
            },
        )
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV002", out)

    def test_subject_from_a_different_clause_is_not_the_claim(self):
        """`steady-finish` sits in a later clause. Even when it DOES exist at
        base, it is not what the claim is about."""
        code, out = self.run_check(
            base_files={
                "wiki/topics/steady-finish.md": "# Steady Finish\n\nA topic.\n",
                "wiki/log.md": LOG_HEAD + "- older\n",
            },
            head_files={
                "wiki/log.md": LOG_HEAD + (
                    "- **Method**: (no prior references to *Brand New Book*); "
                    "read [[topics/steady-finish]] for landing-page state\n"
                ),
            },
        )
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV002", out)


class SubjectExtractionTest(NoveltyDiffMixin, unittest.TestCase):
    def test_grammatical_object_of_the_claim_is_searched(self):
        """"no prior reference to Zembla" — the bare name after "to", with no
        wikilink and no italics, is still the claim's subject."""
        code, out = self.run_check(
            base_files={
                "wiki/sources/old.md": "# Old\n\nWork by Tarrow is cited here.\n",
                "wiki/log.md": LOG_HEAD + "- older\n",
            },
            head_files={
                "wiki/log.md": LOG_HEAD + "- no prior reference to Tarrow in the vault\n",
            },
        )
        self.assertEqual(code, 1, out)
        self.assertIn("NOV002", out)

    def test_bare_wikilink_leaf_is_searched(self):
        code, out = self.run_check(
            base_files={
                "wiki/topics/t.md": "# T\n\nIvo Zembla appears here.\n",
                "wiki/log.md": LOG_HEAD + "- older\n",
            },
            head_files={
                "wiki/log.md": LOG_HEAD + "- [[entities/ivo-zembla]] — first vault mention\n",
            },
        )
        self.assertEqual(code, 1, out)
        self.assertIn("NOV002", out)

    def test_negated_claim_is_not_a_claim(self):
        """A log entry RETRACTING a novelty claim must not re-trip the gate —
        wiki/log.md now contains exactly such a retraction."""
        code, out = self.run_check(
            base_files={
                "wiki/sources/old.md": "# Old\n\nIvo Zembla is here.\n",
                "wiki/log.md": LOG_HEAD + "- older\n",
            },
            head_files={
                "wiki/log.md": LOG_HEAD + (
                    "- [[entities/ivo-zembla]] — **not** a first vault mention: "
                    "the ingest recorded him as new, which was wrong.\n"
                ),
            },
        )
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV002", out)

    def test_word_boundaries_are_respected(self):
        """A short subject must not match inside a longer word."""
        code, out = self.run_check(
            base_files={
                "wiki/topics/t.md": "# T\n\nThe album was always alright.\n",
                "wiki/log.md": LOG_HEAD + "- older\n",
            },
            head_files={
                "wiki/log.md": LOG_HEAD + "- no prior reference to *Al* here\n",
            },
        )
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV002", out)


class DiffScopingTest(NoveltyDiffMixin, unittest.TestCase):
    def test_pages_created_in_the_same_commit_are_not_prior_mentions(self):
        """No exclusion rule needed — a page absent from the base tree cannot
        be found there. This falls out of diff-scoping and is the property that
        makes the whole approach work."""
        code, out = self.run_check(
            base_files={"wiki/log.md": LOG_HEAD + "- older\n"},
            head_files={
                "wiki/entities/newperson.md": "# New Person\n\nNew Person is new.\n",
                "wiki/sources/s.md": "# S\n\nNew Person wrote this.\n",
                "wiki/log.md": LOG_HEAD + (
                    "- [[entities/newperson|New Person]] — first vault mention\n"
                ),
            },
        )
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV002", out)

    def test_unchanged_claims_are_not_rechecked(self):
        """A claim already in the file is not an ADDED line. Re-litigating old
        log entries on every commit is precisely the staleness that forced the
        log out of NOV001."""
        stale_claim = LOG_HEAD + "- [[entities/ivo-zembla]] — first vault mention\n"
        code, out = self.run_check(
            base_files={
                "wiki/sources/old.md": "# Old\n\nIvo Zembla.\n",
                "wiki/log.md": stale_claim,
            },
            head_files={"wiki/log.md": stale_claim + "- an unrelated new entry\n"},
        )
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV002", out)

    def test_claims_outside_wiki_are_ignored(self):
        """`raw/` is immutable source; a transcript is not a vault claim."""
        code, out = self.run_check(
            base_files={
                "wiki/topics/t.md": "# T\n\nIvo Zembla.\n",
                "raw/books/b.md": "# B\n",
            },
            head_files={
                "raw/books/b.md": "# B\n\nfirst vault mention of Ivo Zembla\n",
            },
        )
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOV002", out)

    def test_no_novelty_claims_exits_clean(self):
        code, out = self.run_check(
            base_files={"wiki/log.md": LOG_HEAD + "- older\n"},
            head_files={"wiki/log.md": LOG_HEAD + "- an ordinary entry\n"},
        )
        self.assertEqual(code, 0, out)


class CliTest(NoveltyDiffMixin, unittest.TestCase):
    def test_gh_annotations_flag_emits_workflow_syntax(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q", "-b", "main")
            git(root, "config", "user.email", "t@example.com")
            git(root, "config", "user.name", "T")
            git(root, "config", "commit.gpgsign", "false")
            (root / "wiki").mkdir()
            (root / "wiki" / "old.md").write_text("Ivo Zembla\n", encoding="utf-8")
            (root / "wiki" / "log.md").write_text(LOG_HEAD, encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "base")
            base = git(root, "rev-parse", "HEAD").strip()
            (root / "wiki" / "log.md").write_text(
                LOG_HEAD + "- no prior reference to Ivo Zembla\n", encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "head")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--base", base, "--gh-annotations"],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("::error", proc.stdout)

    def test_bad_base_sha_fails_loudly(self):
        """A gate that cannot resolve its base must NOT exit 0 — a silent pass
        is the failure mode this whole family of rules exists to prevent."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q", "-b", "main")
            git(root, "config", "user.email", "t@example.com")
            git(root, "config", "user.name", "T")
            git(root, "config", "commit.gpgsign", "false")
            (root / "wiki").mkdir()
            (root / "wiki" / "a.md").write_text("x\n", encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "base")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--base", "deadbeef"],
                cwd=root, capture_output=True, text=True,
            )
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
