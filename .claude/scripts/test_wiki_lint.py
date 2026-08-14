#!/usr/bin/env python3
"""Unit tests for .claude/scripts/wiki-lint.py.

Not a general test of the linter. It covers the two things whose behaviour a
human cannot check by reading the tool or running it once:

  1. WIKI002's attachment exemption — the one lint rule that behaves DIFFERENTLY
     on a developer's disk (attachments present) than in CI (gitignored, absent).
  2. `--report stale` — the one report keyed to WALL-CLOCK TIME rather than to
     content, so its output changes on days nobody edited anything, and its
     "review is a noun, not an alarm" exclusion is a judgement call that a later
     well-meaning edit could easily undo.

Each case shells out to the real entrypoint rather than importing it. Two
reasons, both load-bearing:

  1. `apply_config()` rebinds module globals. In-process cases would leak each
     other's config, and a REPLACE knob leaking into the next case is exactly
     the kind of false green this file is meant to prevent.
  2. Config is read from disk and resolved against `--vault-root`. A subprocess
     exercises that path for real, including the exit-2 failure mode.

Stdlib only, no fixtures on disk, no network. Run:

    python3 .claude/scripts/test_wiki_lint.py -v
"""

import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "wiki-lint.py"
CONFIG_RELPATH = Path(".claude/scripts/wiki-lint.config.json")

# Only the wikilink gate runs, so a fixture page needs no frontmatter and an
# unrelated rule can never turn one of these cases red for the wrong reason.
CHECK = "broken-wikilink"


class AttachmentExemptionTest(unittest.TestCase):
    """WIKI002 must not flag links to files .gitignore keeps out of the repo."""

    def run_lint(self, body: str, config: dict | None = None, files: list[str] | None = None):
        """Lint a one-page vault. Returns (exit_code, combined_output)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wiki" / "sources").mkdir(parents=True)
            (root / "wiki" / "sources" / "page.md").write_text(body, encoding="utf-8")
            # A second page so a *valid* wikilink exists to contrast against.
            (root / "wiki" / "sources" / "real-page.md").write_text("# Real\n", encoding="utf-8")
            for extra in files or []:
                p = root / extra
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"")
            if config is not None:
                cfg = root / CONFIG_RELPATH
                cfg.parent.mkdir(parents=True, exist_ok=True)
                cfg.write_text(json.dumps(config), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--check", CHECK,
                    "--vault-root", str(root),
                    str(root / "wiki"),
                ],
                capture_output=True, text=True,
            )
            return proc.returncode, proc.stdout + proc.stderr

    # ---- the exemption itself ----

    def test_unresolvable_image_embed_is_not_flagged(self):
        """The CI-only failure this whole change exists for."""
        code, out = self.run_lint("Slide: ![[IMG_9355.jpeg]]\n")
        self.assertEqual(code, 0, out)
        self.assertNotIn("WIKI002", out)

    def test_unresolvable_image_plain_link_is_not_flagged(self):
        """`!` sits OUTSIDE WIKILINK_RE, so embed and plain link are one case."""
        code, out = self.run_lint("See [[diagram.png]]\n")
        self.assertEqual(code, 0, out)
        self.assertNotIn("WIKI002", out)

    def test_long_extension_is_recognised(self):
        """`.numbers` is 7 chars — resolve_wikilink's own extension regex caps at
        4 and reads it as no extension at all, so the exemption must not lean on
        that regex."""
        code, out = self.run_lint("Budget: [[forecast.numbers]]\n")
        self.assertEqual(code, 0, out)
        self.assertNotIn("WIKI002", out)

    def test_pdf_and_video_are_exempt(self):
        code, out = self.run_lint("[[handout.pdf]] and [[clip.mp4]]\n")
        self.assertEqual(code, 0, out)
        self.assertNotIn("WIKI002", out)

    def test_extension_match_is_case_insensitive(self):
        code, out = self.run_lint("[[PHOTO.JPG]]\n")
        self.assertEqual(code, 0, out)
        self.assertNotIn("WIKI002", out)

    # ---- what must STILL be caught (regression guards) ----

    def test_missing_markdown_page_is_still_flagged(self):
        code, out = self.run_lint("See [[sources/no-such-page]]\n")
        self.assertEqual(code, 1, out)
        self.assertIn("WIKI002", out)

    def test_unresolvable_tracked_file_type_is_still_flagged(self):
        """`.py` / `.json` / `.yml` files ARE committed, so a broken link to one
        is a real finding. The exemption is about untracked types only."""
        code, out = self.run_lint("See [[scripts/gone.py]]\n")
        self.assertEqual(code, 1, out)
        self.assertIn("WIKI002", out)

    def test_valid_link_still_resolves(self):
        code, out = self.run_lint("See [[sources/real-page]]\n")
        self.assertEqual(code, 0, out)
        self.assertNotIn("WIKI002", out)

    def test_present_attachment_still_resolves(self):
        """The skip is reached only after resolution fails, so a committed
        attachment takes the ordinary path and stays unaffected."""
        code, out = self.run_lint(
            "![[assets/kept.png]]\n", files=["assets/kept.png"]
        )
        self.assertEqual(code, 0, out)
        self.assertNotIn("WIKI002", out)

    # ---- the config knob ----

    def test_empty_list_restores_the_check(self):
        """The setting for an instance that COMMITS its attachments."""
        code, out = self.run_lint(
            "![[IMG_9355.jpeg]]\n", config={"attachment_extensions": []}
        )
        self.assertEqual(code, 1, out)
        self.assertIn("WIKI002", out)

    def test_config_replaces_rather_than_merges(self):
        """REPLACE semantics: a list naming only `png` must leave `jpeg` checked.
        Merge semantics would silently keep every built-in extension exempt and
        make the knob undoable — the bug this asserts against."""
        code, out = self.run_lint(
            "![[IMG_9355.jpeg]]\n", config={"attachment_extensions": ["png"]}
        )
        self.assertEqual(code, 1, out)
        self.assertIn("WIKI002", out)

    def test_config_values_normalise(self):
        """Leading dots and case are accepted, so a plausible hand-edit works."""
        code, out = self.run_lint(
            "![[IMG_9355.jpeg]]\n", config={"attachment_extensions": [".JPEG"]}
        )
        self.assertEqual(code, 0, out)
        self.assertNotIn("WIKI002", out)

    def test_wrong_type_is_fatal(self):
        """Config errors exit 2 and never fall back to defaults silently."""
        code, out = self.run_lint(
            "![[IMG_9355.jpeg]]\n", config={"attachment_extensions": "png"}
        )
        self.assertEqual(code, 2, out)
        self.assertIn("attachment_extensions", out)

    def test_unknown_key_is_still_fatal(self):
        """Guards the validation path the new key was registered in."""
        code, out = self.run_lint(
            "See [[sources/real-page]]\n", config={"attachmnet_extensions": []}
        )
        self.assertEqual(code, 2, out)
        self.assertIn("unknown key", out)


#: A fixed "today" for the boundary-exact cases, injected via WIKI_LINT_TODAY.
#: Freezing the clock is what makes an exactly-90-days-old fixture assertable:
#: the test writes the file and a separate linter process judges it, so on a
#: real clock midnight can fall between the two and turn 90 into 91.
FROZEN = datetime.date(2027, 6, 15)
FROZEN_DEC = datetime.date(2027, 12, 10)   # for the year-rollover case


class StaleReportTest(unittest.TestCase):
    """`--report stale` — the pruning-visibility report.

    Advisory by design: it must ALWAYS exit 0, on every signal and not just the
    first. Every other check here fires on content, so a clean tree stays clean;
    staleness fires on wall-clock time, so gating on it would turn CI red on a
    day nobody touched the repo.
    """

    def run_report(self, pages: dict, config: dict | None = None, today=None):
        """pages maps repo-relative path -> file text. Returns (code, output)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in pages.items():
                f = root / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(text, encoding="utf-8")
            (root / "wiki").mkdir(exist_ok=True)
            if config is not None:
                cfg = root / CONFIG_RELPATH
                cfg.parent.mkdir(parents=True, exist_ok=True)
                cfg.write_text(json.dumps(config), encoding="utf-8")
            env = dict(os.environ)
            if today is not None:
                env["WIKI_LINT_TODAY"] = today.isoformat()
            else:
                env.pop("WIKI_LINT_TODAY", None)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--report", "stale", "--vault-root", str(root)],
                capture_output=True, text=True, env=env,
            )
            return proc.returncode, proc.stdout + proc.stderr

    def assertCounts(self, out, a, b, c, d=0):
        """Assert the whole summary line, total included.

        Never assert a bare "A=1": it is a prefix of A=1, A=10, A=11… so a
        multi-page fixture would go silently green. Pinning all four buckets
        also catches a page MOVING between them, which a single count cannot,
        and pinning the total catches a bucket dropping out of the sum.
        """
        self.assertIn(f"Total: {a + b + c + d}  (A={a} B={b} C={c} D={d})", out)

    @staticmethod
    def page(ptype, days_old=None, status=None, body="body",
             date_key="date_updated", anchor=None, raw_date=None, title='"T"'):
        fm = [f"type: {ptype}", f"title: {title}"]
        if raw_date is not None:
            fm.append(f"{date_key}: {raw_date}")
        elif days_old is not None:
            base = anchor or datetime.date.today()
            fm.append(f"{date_key}: {(base - datetime.timedelta(days=days_old)).isoformat()}")
        if status:
            fm.append(f"status: {status}")
        return "---\n" + "\n".join(fm) + "\n---\n\n# T\n\n" + body + "\n"

    # ---- STALE-A: the status/date contradiction ----

    def test_active_page_past_threshold_is_reported(self):
        """Both types, because a port that dropped one would still pass a
        project-only fixture — and `plan` is the one nobody writes a test for."""
        for ptype, folder in (("project", "projects"), ("plan", "plans")):
            with self.subTest(ptype=ptype):
                rel = f"wiki/{folder}/p.md"
                code, out = self.run_report({rel: self.page(ptype, 200, "active")})
                self.assertEqual(code, 0, out)          # advisory: never gates
                self.assertCounts(out, 1, 0, 0)
                # The detail line is the entire product a human reads: age,
                # which date key was believed, and its value all have to be there.
                when = (datetime.date.today() - datetime.timedelta(days=200)).isoformat()
                self.assertIn(f"200d  {rel}  ({ptype}, status: active, date_updated {when})", out)

    def test_active_page_within_threshold_is_not_reported(self):
        code, out = self.run_report({"wiki/projects/p.md": self.page("project", 10, "active")})
        self.assertEqual(code, 0, out)
        self.assertCounts(out, 0, 0, 0)

    def test_completed_project_is_never_stale(self):
        """Only `active` is a claim the date can contradict."""
        code, out = self.run_report({"wiki/projects/p.md": self.page("project", 900, "completed")})
        self.assertEqual(code, 0, out)
        self.assertCounts(out, 0, 0, 0)

    def test_active_threshold_boundary_is_exclusive(self):
        """Exactly 90 days is silent, 91 fires — pins `>` against `>=`."""
        for days, expected in ((90, 0), (91, 1)):
            with self.subTest(days=days):
                page = self.page("project", days, "active", anchor=FROZEN)
                code, out = self.run_report({"wiki/projects/p.md": page}, today=FROZEN)
                self.assertCounts(out, expected, 0, 0)

    def test_stalest_page_is_listed_first(self):
        pages = {
            "wiki/projects/old.md": self.page("project", 900, "active"),
            "wiki/projects/new.md": self.page("project", 200, "active"),
        }
        code, out = self.run_report(pages)
        self.assertCounts(out, 2, 0, 0)
        self.assertLess(out.index("wiki/projects/old.md"), out.index("wiki/projects/new.md"))

    def test_frontmatter_quoting_and_case_are_normalised(self):
        """`type: "project"` and `status: "Active"` are ordinary hand-written YAML."""
        page = self.page("project", 200, '"Active"', title='"T"').replace(
            "type: project", 'type: "project"'
        )
        code, out = self.run_report({"wiki/projects/p.md": page})
        self.assertCounts(out, 1, 0, 0)

    # ---- STALE-B: expired self-set alarms ----

    def test_due_alarm_rings(self):
        body = "We should re-check Jan 2020 whether this still holds."
        code, out = self.run_report({"wiki/topics/t.md": self.page("topic", 1, body=body)})
        self.assertEqual(code, 0, out)
        self.assertCounts(out, 0, 1, 0)
        # Located and quoted: a reader jumps from this line, so an off-by-one
        # in the line number or a mangled snippet is a real defect.
        self.assertIn("wiki/topics/t.md:9  → re-check Jan 2020", out)

    def test_alarm_grammar_variants_all_ring(self):
        """The include-rule and the exclude-rule sit one token apart; pinning
        only the negative half leaves the positive half free to shrink."""
        for body in (
            "We should review again Jan 2020.",
            "- **Revisit:** Nov 2020",
            "Re-check by 2020-03-01",
            "Re-check 2020-01-15 whether this still holds.",
            "revisit in Jan 2020",
            "re-check by the Mar 2021",
            "revisit January 2020",
            "Re-check Jan. 2020",
            "Revisit — Nov 2020",
            "Re-check after Dec 2020",
            "Revisit this again in Nov 2020",
        ):
            with self.subTest(body=body):
                code, out = self.run_report({"wiki/topics/t.md": self.page("topic", 1, body=body)})
                self.assertCounts(out, 0, 1, 0)

    def test_iso_alarms_are_compared_by_day(self):
        """ISO is the only date format this template mandates, so B has to
        match it — and to the day, not the month.

        The today-exact case is the one that matters: an alarm set FOR today is
        due today, so the comparison is `<=`. Only a same-day fixture can tell
        `<=` from `<`, which is why the clock is frozen here.
        """
        for raw, expected in (("2027-06-14", 1), ("2027-06-15", 1), ("2027-06-16", 0)):
            with self.subTest(raw=raw):
                body = f"Re-check {raw} whether this still holds."
                page = self.page("topic", 1, body=body, anchor=FROZEN)
                code, out = self.run_report({"wiki/topics/t.md": page}, today=FROZEN)
                self.assertCounts(out, 0, expected, 0)

    def test_month_alarm_is_due_once_the_month_begins(self):
        """The documented rule: "Nov 2026" rings on Nov 1, not Nov 30."""
        for anchor, month, expected in (
            (FROZEN, "Jun 2027", 1),        # the current month — due
            (FROZEN, "Jul 2027", 0),        # next month — not yet
            (FROZEN_DEC, "Dec 2027", 1),    # same, across the year boundary
            (FROZEN_DEC, "Jan 2028", 0),
        ):
            with self.subTest(month=month, today=anchor):
                page = self.page("topic", 1, body=f"Revisit {month}.", anchor=anchor)
                code, out = self.run_report({"wiki/topics/t.md": page}, today=anchor)
                self.assertCounts(out, 0, expected, 0)

    def test_future_alarm_stays_silent(self):
        body = "Revisit Dec 2099 once the migration lands."
        code, out = self.run_report({"wiki/topics/t.md": self.page("topic", 1, body=body)})
        self.assertEqual(code, 0, out)
        self.assertCounts(out, 0, 0, 0)

    def test_phrases_that_must_never_ring(self):
        """Each is a distinct way the heuristic over-reaches. A report that
        cries wolf on ordinary prose stops being read, which costs more than
        the alarms it would have surfaced."""
        for body in (
            # A historical title: "review" as a noun, records the past.
            "See the Architecture Review Mar 2021 for the original decision.",
            # Past tense: the alarm already rang and the work is done.
            "We revisited Mar 2021 and confirmed the call.",
            "Rechecked Jan 2020 — still true.",
            "The team revisits Mar 2021 numbers.",
            # A word that merely STARTS with a month abbreviation.
            "Revisit Marketing 2026 spend with the team.",
            "Re-check Maybe 2026 as a name.",
            # Documentation of the syntax, not an alarm written in it.
            "An inline `re-check Jan 2020` mention.",
        ):
            with self.subTest(body=body):
                code, out = self.run_report({"wiki/topics/t.md": self.page("topic", 1, body=body)})
                self.assertCounts(out, 0, 0, 0)

    def test_alarm_inside_a_code_fence_is_ignored(self):
        body = "```\nre-check Jan 2020\n```"
        code, out = self.run_report({"wiki/topics/t.md": self.page("topic", 1, body=body)})
        self.assertEqual(code, 0, out)
        self.assertCounts(out, 0, 0, 0)

    def test_alarms_ring_outside_the_synthesis_folders(self):
        """B is vault-wide on purpose — an alarm in an entity page is still an
        alarm. Pins the scope against a narrowing to SYNTH_FOLDERS."""
        body = "We should re-check Jan 2020 whether this still holds."
        page = "---\ntype: entity\ntitle: \"E\"\nentity_type: person\n---\n\n# E\n\n" + body + "\n"
        code, out = self.run_report({"wiki/entities/e.md": page})
        self.assertCounts(out, 0, 1, 0)

    def test_alarms_in_append_only_logs_are_skipped(self):
        """A log entry records what was said on a date. An alarm inside one
        can never be silenced, so ringing it forever is noise with no fix."""
        body = "Decided to revisit Jan 2020 after the migration."
        log = "---\ntype: log\ntitle: \"Log\"\n---\n\n# Log\n\n" + body + "\n"
        for rel in ("wiki/log.md", "wiki/log/2019-archive.md", "wiki/reflections-log.md"):
            with self.subTest(rel=rel):
                code, out = self.run_report({rel: log})
                self.assertCounts(out, 0, 0, 0)

    # ---- STALE-C ----

    def test_aging_synthesis_is_reported(self):
        for ptype, folder in (("insight", "insights"), ("topic", "topics")):
            with self.subTest(ptype=ptype):
                rel = f"wiki/{folder}/x.md"
                code, out = self.run_report({rel: self.page(ptype, 500)})
                self.assertEqual(code, 0, out)
                self.assertCounts(out, 0, 0, 1)
                when = (datetime.date.today() - datetime.timedelta(days=500)).isoformat()
                self.assertIn(f"500d  {rel}  (date_updated {when})", out)

    def test_oldest_synthesis_page_is_listed_first(self):
        pages = {
            "wiki/insights/old.md": self.page("insight", 900),
            "wiki/insights/new.md": self.page("insight", 500),
        }
        code, out = self.run_report(pages)
        self.assertCounts(out, 0, 0, 2)
        self.assertLess(out.index("wiki/insights/old.md"), out.index("wiki/insights/new.md"))

    def test_aging_uses_its_own_threshold_not_the_active_one(self):
        """200 days trips A for a project but must NOT trip C for an insight."""
        code, out = self.run_report({"wiki/insights/i.md": self.page("insight", 200)})
        self.assertCounts(out, 0, 0, 0)

    def test_synthesis_threshold_boundary_is_exclusive(self):
        for days, expected in ((365, 0), (366, 1)):
            with self.subTest(days=days):
                page = self.page("insight", days, anchor=FROZEN)
                code, out = self.run_report({"wiki/insights/i.md": page}, today=FROZEN)
                self.assertCounts(out, 0, 0, expected)

    def test_synthesis_falls_back_to_date_created(self):
        """`date_updated` is not even a recommended key for insight/topic, so
        keying on it alone is silent on the schema's own canonical shape."""
        page = self.page("insight", 500, date_key="date_created")
        code, out = self.run_report({"wiki/insights/i.md": page})
        self.assertCounts(out, 0, 0, 1)
        self.assertIn("(date_created ", out)

    def test_project_falls_back_to_date_started(self):
        page = self.page("project", 200, "active", date_key="date_started")
        code, out = self.run_report({"wiki/projects/p.md": page})
        self.assertCounts(out, 1, 0, 0)
        self.assertIn("(project, status: active, date_started ", out)

    # ---- STALE-D: in scope, but no usable date ----

    def test_page_with_no_date_is_counted_not_dropped(self):
        """The whole point of D: silence here would make A=0 read as clean
        when it means unassessed, and a page with no freshness evidence is the
        one most likely to be stale."""
        page = self.page("project", None, "active")
        code, out = self.run_report({"wiki/projects/p.md": page})
        self.assertEqual(code, 0, out)
        self.assertCounts(out, 0, 0, 0, 1)
        self.assertIn("wiki/projects/p.md  (project, no date key)", out)

    def test_unparseable_date_is_counted_with_its_value(self):
        page = self.page("project", None, "active", raw_date="2026-13-45")
        code, out = self.run_report({"wiki/projects/p.md": page})
        self.assertCounts(out, 0, 0, 0, 1)
        self.assertIn("unparseable date_updated: '2026-13-45'", out)

    def test_future_date_is_counted_not_treated_as_fresh(self):
        """A year typo would otherwise hide a stale page permanently."""
        page = self.page("project", None, "active", raw_date="2099-01-01")
        code, out = self.run_report({"wiki/projects/p.md": page})
        self.assertCounts(out, 0, 0, 0, 1)
        self.assertIn("date_updated is in the future: 2099-01-01", out)

    def test_malformed_key_falls_back_before_giving_up(self):
        """A broken `date_updated` next to a good `date_created` is judgeable."""
        page = (
            '---\ntype: insight\ntitle: "T"\ndate_updated: not-a-date\n'
            f"date_created: {(datetime.date.today() - datetime.timedelta(days=500)).isoformat()}\n"
            "---\n\n# T\n\nbody\n"
        )
        code, out = self.run_report({"wiki/insights/i.md": page})
        self.assertCounts(out, 0, 0, 1, 0)

    def test_out_of_scope_page_with_no_date_is_not_counted(self):
        """D covers only pages the report would otherwise have judged."""
        code, out = self.run_report({"wiki/projects/p.md": self.page("project", None, "completed")})
        self.assertCounts(out, 0, 0, 0, 0)

    # ---- config ----

    def test_active_threshold_is_configurable(self):
        pages = {"wiki/projects/p.md": self.page("project", 30, "active")}
        code, out = self.run_report(pages)
        self.assertCounts(out, 0, 0, 0)
        code, out = self.run_report(pages, config={"stale_thresholds": {"active_days": 7}})
        self.assertEqual(code, 0, out)
        self.assertCounts(out, 1, 0, 0)

    def test_synthesis_threshold_is_configurable(self):
        """Half the knob's surface — untested, it can become a no-op silently."""
        pages = {"wiki/insights/i.md": self.page("insight", 200)}
        code, out = self.run_report(pages)
        self.assertCounts(out, 0, 0, 0)
        code, out = self.run_report(pages, config={"stale_thresholds": {"synthesis_days": 100}})
        self.assertEqual(code, 0, out)
        self.assertCounts(out, 0, 0, 1)

    def test_partial_threshold_config_keeps_the_other_default(self):
        pages = {"wiki/insights/i.md": self.page("insight", 500)}
        code, out = self.run_report(pages, config={"stale_thresholds": {"active_days": 7}})
        self.assertCounts(out, 0, 0, 1)

    def test_bad_threshold_is_fatal(self):
        code, out = self.run_report(
            {"wiki/projects/p.md": self.page("project", 30, "active")},
            config={"stale_thresholds": {"active_days": 0}},
        )
        self.assertEqual(code, 2, out)
        self.assertIn("positive integer", out)

    def test_boolean_threshold_is_fatal(self):
        """bool subclasses int — `true` must not silently mean 1 day.

        Asserts the MESSAGE, not just the exit code: argparse rejects an
        unknown --report value with 2 as well, so a code-only assertion here
        passes against a build that has no stale report at all.
        """
        code, out = self.run_report(
            {"wiki/projects/p.md": self.page("project", 30, "active")},
            config={"stale_thresholds": {"active_days": True}},
        )
        self.assertEqual(code, 2, out)
        self.assertIn("positive integer", out)

    def test_unknown_threshold_key_is_fatal(self):
        code, out = self.run_report(
            {"wiki/projects/p.md": self.page("project", 30, "active")},
            config={"stale_thresholds": {"activedays": 7}},
        )
        self.assertEqual(code, 2, out)
        self.assertIn("unknown key", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
