#!/usr/bin/env python3
"""Unit tests for .claude/scripts/check-date-updated.py (the FM007 gate).

FM007 is the one lint gate that cannot be evaluated from a working tree alone:
it diffs against a base SHA, so it only ever runs in CI. That makes it the gate
most likely to be wrong without anyone noticing — its behaviour is invisible on
the machine where the page was written.

The case that motivated this suite: editing the SAME page TWICE IN ONE DAY. The
first commit sets date_updated to today; the second changes the body again and
there is no later value to bump to. The gate red-lined correct work, and the
only ways out were to falsify a future date or ignore the build.

Each case builds a throwaway git repo and shells out to the real entrypoint, so
the git plumbing (diff --diff-filter=M, git show <ref>:<path>) is exercised for
real rather than mocked.

Stdlib only, no network. Run:

    python3 .claude/scripts/test_check_date_updated.py -v
"""

import datetime
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-date-updated.py"

PAGE = "wiki/projects/example.md"

# Git identity is passed explicitly on every call so the suite never depends on
# ambient config, and gpgsign is forced off so a developer's signing setup
# cannot turn this red for a reason unrelated to dates.
GIT_ID = [
    "-c", "user.name=ci",
    "-c", "user.email=ci@example.com",
    "-c", "commit.gpgsign=false",
    "-c", "init.defaultBranch=main",
]


def page(date_updated: str, body: str) -> str:
    return (
        "---\n"
        "type: project\n"
        'title: "Example"\n'
        "status: active\n"
        f"date_updated: {date_updated}\n"
        "---\n"
        "\n"
        "> **Recent updates** (most recent first):\n"
        "> - **2026-01-01** — Created.\n"
        "\n"
        "# Example\n"
        "\n"
        f"{body}\n"
    )


def iso(offset_days: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=offset_days)).isoformat()


class FM007Test(unittest.TestCase):
    def run_gate(self, before: str, after: str, path: str = PAGE):
        """Commit `before`, write `after`, run the gate. Returns (code, output)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git = lambda *a: subprocess.run(
                ["git", *GIT_ID, *a], cwd=root, capture_output=True, text=True, check=True
            )
            git("init", "-q")
            p = root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            if before is None:
                # New-file case: base commit must exist but not contain the page.
                (root / "seed.txt").write_text("seed\n", encoding="utf-8")
                git("add", "-A")
                git("commit", "-qm", "base")
            else:
                p.write_text(before, encoding="utf-8")
                git("add", "-A")
                git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD").stdout.strip()
            p.write_text(after, encoding="utf-8")
            git("add", "-A")
            git("commit", "-qm", "change")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--base", base],
                cwd=root, capture_output=True, text=True,
            )
            return proc.returncode, proc.stdout + proc.stderr

    # ---- the bug this suite exists for ----

    def test_same_day_second_edit_passes(self):
        """Two edits on one day: the date is already correct, nothing to bump."""
        today = iso(0)
        code, out = self.run_gate(page(today, "first"), page(today, "second"))
        self.assertEqual(code, 0, out)
        self.assertNotIn("FM007", out)

    def test_yesterday_passes_for_timezone_skew(self):
        """CI runs UTC, authors do not — a UTC-behind author is a day back."""
        d = iso(-1)
        code, out = self.run_gate(page(d, "first"), page(d, "second"))
        self.assertEqual(code, 0, out)

    def test_tomorrow_passes_for_timezone_skew(self):
        """A UTC-ahead author (e.g. UTC+8 in the evening) is a day forward."""
        d = iso(1)
        code, out = self.run_gate(page(d, "first"), page(d, "second"))
        self.assertEqual(code, 0, out)

    # ---- what must STILL fail (the gate's whole purpose) ----

    def test_stale_date_still_fails(self):
        code, out = self.run_gate(page("2026-01-05", "first"), page("2026-01-05", "second"))
        self.assertEqual(code, 1, out)
        self.assertIn("FM007", out)

    def test_two_days_ago_still_fails(self):
        """The allowance is a timezone allowance, not general slack."""
        d = iso(-2)
        code, out = self.run_gate(page(d, "first"), page(d, "second"))
        self.assertEqual(code, 1, out)

    def test_unparseable_date_still_fails(self):
        """No exemption for a value the gate cannot read."""
        code, out = self.run_gate(page("last Tuesday", "first"), page("last Tuesday", "second"))
        self.assertEqual(code, 1, out)

    def test_impossible_date_still_fails(self):
        code, out = self.run_gate(page("2026-02-30", "first"), page("2026-02-30", "second"))
        self.assertEqual(code, 1, out)

    # ---- pre-existing behaviour that must not regress ----

    def test_bumped_date_passes(self):
        code, out = self.run_gate(page("2026-01-05", "first"), page("2026-01-06", "second"))
        self.assertEqual(code, 0, out)

    def test_callout_only_change_passes(self):
        """Rolling an old callout entry off must not demand a bump (RU004)."""
        before = page("2026-01-05", "body")
        after = before.replace("> - **2026-01-01** — Created.", "> - **2026-01-02** — Edited.")
        self.assertNotEqual(before, after)
        code, out = self.run_gate(before, after)
        self.assertEqual(code, 0, out)

    def test_new_page_passes(self):
        code, out = self.run_gate(None, page("2026-01-05", "body"))
        self.assertEqual(code, 0, out)

    def test_non_synthesis_path_ignored(self):
        """Sources are out of scope — only insights/topics/plans/projects."""
        code, out = self.run_gate(
            page("2026-01-05", "first"), page("2026-01-05", "second"),
            path="wiki/sources/example.md",
        )
        self.assertEqual(code, 0, out)


class IsCurrentUnitTest(unittest.TestCase):
    """Direct tests of the helper, pinned to a fixed 'today' so they never drift."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cdu", SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.today = datetime.date(2026, 8, 12)

    def test_boundaries(self):
        f = lambda s: self.mod.is_current(s, today=self.today)
        self.assertTrue(f("2026-08-12"))   # today
        self.assertTrue(f("2026-08-11"))   # -1, tz allowance
        self.assertTrue(f("2026-08-13"))   # +1, tz allowance
        self.assertFalse(f("2026-08-10"))  # -2
        self.assertFalse(f("2026-08-14"))  # +2
        self.assertFalse(f(""))
        self.assertFalse(f("2026-8-12"))   # not zero-padded ISO
        self.assertFalse(f("2026-13-01"))  # impossible month


if __name__ == "__main__":
    unittest.main(verbosity=2)
