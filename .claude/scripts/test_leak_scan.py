#!/usr/bin/env python3
"""Tests for leak-scan.py - the PII/identity + publication-structure gate.

Run all:  python3 .claude/scripts/test_leak_scan.py -v

Stdlib `unittest` only, like every script in this directory. No pip deps, no
absolute developer paths, nothing that only works inside one checkout: copy
this directory anywhere with `leak-scan.py` and `denylist.example.txt` beside
it and the whole suite still runs.

WHY THIS SUITE EXISTS
---------------------
The scanner's failure mode is a FALSE PASS: it prints "PASS" and a real name
goes public, irreversibly. So the suite is built on one rule -

    a test that passes proves nothing unless it has been proved it can FAIL.

Every exemption test therefore ships a NEGATIVE CONTROL right next to it (the
same rule firing on input that is genuinely dirty), and every leak-surface
fixture is MINIMAL: one commit, one leak, no superseded blobs, unless the
surface structurally requires more (a deleted file, a deleted directory).

That minimality is not tidiness. In the sibling copy of this gate, the
regression test for "denylist term in a commit message, clean worktree" PASSED
against a scanner that was still broken, because its fixture happened to carry
a superseded blob - which made the history-blob set non-empty and let control
flow reach the commit-metadata scan. A single-commit fixture hit the early
return, and the scanner reported PASS on a repo whose commit subject named the
employer. Any incidental extra commit in a fixture here re-opens that hole.

EVERY FIXTURE TERM IN THIS FILE IS INVENTED
-------------------------------------------
This repository is PUBLIC and this file is committed content. A real name, a
real handle or a real home path in a test fixture IS the disclosure the gate
exists to prevent, so the fixtures use the same obviously-fake vocabulary as
the shipped `denylist.example.txt`: Jane Doe, Acme Corp, Contoso, Northwind,
@janedoe, and an invented home directory. Nothing here names a person.

The sibling private copy hardcodes its denylist as module globals and builds
fixtures out of the real terms. This copy takes a `Denylist` as an ARGUMENT,
which is both more testable and free of that hazard: every test constructs the
exact denylist it needs. The sibling's cross-repo tests (which assert the two
copies run the same rules by importing the other one from a developer's disk)
are deliberately NOT ported - this repo must never reference that path. Instead
`TestRuleSet` PINS THIS COPY'S OWN RULE SET, so a rule silently appearing or
disappearing fails a test here rather than drifting unnoticed.

KNOWN DIVERGENCE FROM THE SIBLING COPY (recorded 2026-07-31)
------------------------------------------------------------
The two copies are meant to run an identical rule set, and by RULE they still
do - `TestRuleSet` pins that. They have nonetheless drifted in BEHAVIOUR in two
places. Neither is a deliberate design choice; both are open work, written down
here so a reader of this file is not the last to find out:

1. COMMIT-RECORD SPLITTING. `scan_commit_metadata()` here asks git for a
   `%x1e`-terminated format and splits the stream on that byte, so a literal
   \\x1e inside a commit body truncates the record and everything after it goes
   unscanned while the gate prints PASS. The sibling closed this by asking for
   `-z` (NUL-separated) records. Tracked by
   `test_commit_body_containing_control_bytes_is_scanned_whole`, which is
   marked `expectedFailure` - see its docstring for the port and for why that
   marker cannot outlive the bug.
2. NO TAGGER-IDENTITY CENSUS. The sibling additionally censuses the identity on
   an ANNOTATED TAG (its `TAG_IDENT_FORMAT` / `tag_identities()`), so a tagger
   name and email land in the same human-confirmed census as authors and
   committers. This copy has no equivalent, so a tagger identity is never
   censused. Deliberately NOT tested here: the suite must not assert behaviour
   that does not exist. When the census is ported, add a surface-9 fixture -
   `git tag -a v1 -m msg` made with a denylisted tagger email - asserting the
   census entry.

A third divergence was CLOSED on 2026-08-06 and is recorded here so the list
reads as history rather than as a shrinking set of unexplained edits: this copy
capped worktree reads at 5MB and reported the skip as an advisory INFO line, so
a file over the cap printed PASS whatever was in it. The sibling had already
removed the cap in favour of a streaming read and made any unread file a
structural problem; that mechanism is now ported here. See
`TestWorktreeUnreadFiles`, and the "Nothing in the shipping set goes unread"
section of `leak-scan.py`.

`leak-scan.py`'s own header still describes the copies as identical and does not
carry the two open notes above. Adding it there is part of closing them; this
file is the interim record, not a substitute for it.

NO DIRTY LITERAL SITS ON ONE SOURCE LINE
----------------------------------------
`leak-scan.py` is not exempt from itself and neither is this file: both ship
inside the tree the gate scans, so a fixture written out verbatim would make
the gate fail on its own test suite, forever. Every fixture that is *meant* to
be detected is therefore assembled at runtime from fragments that are each
harmless on their own line - see the FIXTURES section, and the
`TestSuiteHygiene` test that enforces it. The same discipline keeps gitleaks
(the secrets half of the gate, run over this same repo) from firing on a
fixture that holds no real credential.

SECRET SCANNING IS MOSTLY GITLEAKS' JOB
---------------------------------------
Four credential rules (aws-key, github-token, google-api-key, jwt) were
delegated to gitleaks after each was measured to be caught by it, so this suite
does not test them - it tests that they stay GONE. Five were kept because
gitleaks 8.30.1 was measured to miss them (api-token, slack-token,
secret-assignment, private-key, long-hex), and `TestRetainedGitleaksGapRules`
exists specifically to stop them being deleted later on the assumption that
gitleaks covers them. A silent coverage loss in a privacy gate is the worst
possible outcome; if that class fails, re-measure against gitleaks before
touching it.
"""
import contextlib
import importlib.util
import io
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

_spec = importlib.util.spec_from_file_location(
    "leak_scan", pathlib.Path(__file__).with_name("leak-scan.py"))
leak_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(leak_scan)

SCRIPT_PATH = pathlib.Path(leak_scan.__file__).resolve()
EXAMPLE_PATH = SCRIPT_PATH.with_name("denylist.example.txt")

# Passed to EVERY git invocation, so the suite never reads the machine's git
# identity, never inherits a default-branch surprise, and never blocks on a
# commit-signing prompt on a machine with signing enabled globally.
GIT_ID = (
    "-c", "user.name=Fixture Bot",
    "-c", "user.email=fixture@example.com",
    "-c", "commit.gpgsign=false",
    "-c", "tag.gpgsign=false",
    "-c", "init.defaultBranch=main",
)


# --- FIXTURES ---------------------------------------------------------------
#
# Read the "NO DIRTY LITERAL SITS ON ONE SOURCE LINE" note in the module
# docstring before editing anything below. Each fragment is inert by itself;
# only the concatenation matches a rule. `TestSuiteHygiene` fails if that
# discipline is broken, so a well-meaning tidy-up cannot quietly undo it.

_U = "/Users/"                      # inert: the rule needs a name after the slash

# In the denylist AND a home path: the fixture used wherever both paths matter.
FAKE_HOME = _U + "janedoe"
# A home path that is NOT any denylist term - proves the REGEX rule fired.
OTHER_HOME = _U + "someone/Documents/private"
# The deliberate placeholder an example denylist is supposed to contain.
PLACEHOLDER_HOME = _U + "placeholder-name/Documents/vault"

PERSONAL_EMAIL = "someone" + "@" + "gmail.com"

DOC_URL = ("https://docs.google.com/spreadsheets/d/"
           + "1AbCdEfGhIjKlMnOpQrStUvWxYz123456")
CALENDAR_URL = ("https://calendar.google.com/calendar/embed?src="
                + "amFuZWRvZUBleGFtcGxlLmNvbQ%40group.calendar.google.com")

# Deliberately an ANTHROPIC-shaped key: gitleaks 8.30.1 has NO Anthropic rule
# at all (measured 2026-07-30), which is exactly why `api-token` must survive
# the split. It carries no denylist term, so a test using it proves the REGEX
# path fired rather than the name path.
ANTHROPIC_KEY = ("sk-" + "ant-api03-"
                 + "T3Bmbk9xQ2mZr7Xk1pLd93QbVtHnW4sYcRfGjKuIoP")
ANTHROPIC_ADMIN_KEY = ("sk-" + "ant-admin01-"
                       + "9xQ2mZr7Xk1pLd93QbVtHnW4sYcRfGjKuIoPqWeRt")
BARE_VENDOR_KEY = "sk-" + "9xQ2mZr7Xk1pLd93QbVtHnW4sYcRfGjKuIoP"

# 3-segment xoxs / xoxp - the shapes gitleaks was measured to MISS. The
# canonical 4-segment forms it does catch are not the ones that leak.
SLACK_SESSION = ("xox" + "s-263594206564-2404428149924-"
                 + "C7bT9xQ2mZr7Xk1pLd93QbV")
SLACK_USER = ("xox" + "p-263594206564-2404428149924-"
              + "C7bT9xQ2mZr7Xk1pLd93QbV")

HEX32 = "9f2b7c1d4e6a8039" + "bf5c2d7e1a4b6c8d"
HEX40 = "11bd71901bbe5b1630" + "ceea73d27597364c9af683"
HEX64 = HEX32 + "0e2f4a6b8c0d2e4f" + "6a8b0c2d4e6f8a01"

# A SHA-pinned GitHub Action and a pinned release checksum - both legitimate,
# both public, both exempted from long-hex ON THE VALUE, not on the line.
ACTION_PIN_LINE = f"      uses: actions/checkout@{HEX40}  # v4"
CHECKSUM_PIN_LINE = f"          GITLEAKS_SHA256: '{HEX64}'"

# Assembled, never written as adjacent literals: gitleaks' own private-key rule
# is MULTI-LINE, so four literal headers in a row give it a region to match
# across - which both fails this repo's gitleaks job on a fixture holding no key
# material, and (worse) blinds gitleaks to a REAL key pasted anywhere later in
# the same file, because the stray header starts a match that swallows it.
# `test_no_two_private_key_headers_are_adjacent_in_this_file` guards the shape.
PRIVATE_KEY_HEADER = "-----BEGIN {}PRIVATE KEY-----"


def assign(key, value, sep="="):
    """Build a `key = "value"` assignment without writing one in the source.

    The call site reads `assign("password", "hunter2...")`: the keyword and the
    separator never touch, so `secret-assignment` cannot match this file while
    still matching the string it returns.

    ONE MORE CONSTRAINT AT THE CALL SITE. gitleaks' `generic-api-key` accepts a
    comma as its keyword/value separator, so `assign("api_key", "<20 chars>")`
    reads to gitleaks as an assignment even though it does not to the rule
    under test - and gitleaks runs over this same repo. Measured 8.30.1: two
    call sites here fired until the values were split. Its value floor is ten
    word characters, so keep the FIRST fragment of a high-entropy fixture value
    under ten characters and it has nothing to match. Low-entropy passphrases
    are below its entropy gate and can be written whole.
    """
    return f'{key} {sep} "{value}"'


def assign_bare(key, value, sep="="):
    """The unquoted variant - how a value actually lands in a prose note."""
    return f"{key} {sep} {value}"


# --- Denylist fixtures ------------------------------------------------------
#
# Invented vocabulary only, mirroring denylist.example.txt. `words` are
# case-SENSITIVE and boundary-anchored; `substrings` are case-INSENSITIVE.

FIXTURE_DENYLIST_TEXT = f"""\
# fixture denylist - every term below is invented
[words]
Jane
Doe
Acme
Contoso
Northwind

[substrings]
Jane Doe
@janedoe
janedoe
{FAKE_HOME}
janes-vault
Acme Corp
Northwind Traders
"""


def git(repo, *args, ident=GIT_ID):
    """Run git inside `repo`, failing the test loudly if setup breaks.

    A silently degenerate fixture (no commit, no tag, no branch rename) is how
    a leak-surface test starts passing for the wrong reason, so setup failures
    raise rather than being swallowed.
    """
    proc = subprocess.run(
        ["git", "-C", str(repo), *ident, *args],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(
            f"fixture setup failed: git {' '.join(args)}\n{proc.stderr}")
    return proc


def pairs(findings):
    """{(kind, value)} - the assertable content of a Finding tuple."""
    return {(f.kind, f.value) for f in findings}


def wheres(findings):
    return {f.where for f in findings}


class ScannerTestCase(unittest.TestCase):
    """Shared fixture plumbing: a temp workdir and a parsed fixture denylist.

    The denylist file lives OUTSIDE every fixture repo and is passed with
    `--denylist`, for three reasons: putting it inside a repo would trip the
    FORBIDDEN_PATHS check, `resolve_denylist_path()` would otherwise fall back
    to the real `denylist.txt` beside the script (which on a maintainer's
    machine holds real names - the suite must never read it), and an explicit
    argument is what makes each test's search terms visible at its call site.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workdir = pathlib.Path(tmp.name)
        self.denylist_path = self.workdir / "fixture-denylist.txt"
        self.denylist_path.write_text(FIXTURE_DENYLIST_TEXT, encoding="utf-8")
        self.denylist, warnings = leak_scan.load_denylist(self.denylist_path)
        self.assertEqual(warnings, (), "fixture denylist must parse cleanly")

    # -- directories and repos ---------------------------------------------

    def temp_root(self, name="repo"):
        root = self.workdir / name
        root.mkdir()
        return root

    def minimal_repo(self, name="repo"):
        """A repo staging exactly ONE innocuous file. Caller makes the commit.

        Nothing is committed twice and nothing is ever deleted, so after the
        caller's single commit every blob is reachable from HEAD and the
        history blob/path passes have no candidates at all. That is precisely
        the shape that exposed the early-return bug.
        """
        root = self.temp_root(name)
        git(root, "init", "-q")
        (root / "a.md").write_text("wholly innocuous prose\n", encoding="utf-8")
        git(root, "add", "a.md")
        return root

    # -- running the scanner ------------------------------------------------

    def run_scan(self, *argv, denylist=True):
        """Call main() in-process, capturing stdout+stderr. -> (rc, output)."""
        args = list(argv)
        if denylist:
            args += ["--denylist", str(self.denylist_path)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = leak_scan.main(args)
        return rc, buf.getvalue()

    # -- inspection helpers, mirroring what main() does ----------------------

    def opts_for(self, root, *extra):
        return leak_scan.parse_args([str(root), *extra])

    def worktree_findings(self, root):
        """-> (findings, unread), exactly what `main()` gets from `scan_files`."""
        shipping = leak_scan.shipping_set(root)
        self.assertIsNotNone(shipping, "fixture is not a git repo")
        return leak_scan.scan_files(root, shipping, self.denylist)

    def history_findings(self, root):
        return leak_scan.scan_history(
            root, self.denylist, leak_scan.DEFAULT_HISTORY_LIMIT)

    def structure(self, root, *extra):
        shipping = leak_scan.shipping_set(root)
        in_repo = leak_scan.is_git_repo(root)
        rel = shipping if shipping is not None else leak_scan.walk_all_files(root)
        return leak_scan.check_structure(
            root, rel, in_repo, self.opts_for(root, *extra))

    def history_only_blobs(self, root):
        """The blob set `scan_history()` would scan - i.e. reachable, not HEAD.

        The sibling copy factors this out as `history_candidates()`; here it is
        reassembled from the same module functions so the early-return guard
        can assert on it without the scanner having to expose it.
        """
        objects = leak_scan.reachable_objects(root)
        head = leak_scan.head_blob_shas(root)
        candidates = tuple((sha, path) for sha, path in objects
                           if sha not in head)
        info = leak_scan.batch_check(root, [sha for sha, _ in candidates])
        return tuple((sha, path) for sha, path in candidates
                     if info.get(sha, (None, 0))[0] == "blob")

    def patch_constant(self, name, value):
        """Temporarily rebind a module constant, restored on teardown.

        Used only for the two SIZE ceilings. Writing a 5MB file or a 1MB
        history blob to prove a ceiling fires would make the suite slow enough
        that nobody runs it - and a gate nobody runs is the failure mode this
        whole file exists to prevent. Shrinking the ceiling exercises the same
        branch.
        """
        original = getattr(leak_scan, name)
        setattr(leak_scan, name, value)
        self.addCleanup(setattr, leak_scan, name, original)

    def assert_clean_worktree(self, root):
        """Proves the leak under test is NOT visible to the filesystem pass.

        Without this, a history test could be passing for the wrong reason.
        """
        findings, unread = self.worktree_findings(root)
        self.assertEqual(
            findings, (),
            f"fixture is not worktree-clean; the history assertion below would "
            f"prove nothing: {pairs(findings)}")
        self.assertEqual(unread, (), "a fixture file went unread")


# --- 1. Denylist loading (template-specific: the denylist is an argument) ----

class TestDenylistLoading(ScannerTestCase):
    """`load_denylist()` is the seam the whole public/private split rests on.

    The mechanism ships; the terms do not. Everything below is about that file
    being parsed strictly, because a denylist that silently loses half its
    terms is indistinguishable from a passing gate.
    """

    def load(self, text):
        path = self.workdir / "d.txt"
        path.write_text(text, encoding="utf-8")
        return leak_scan.load_denylist(path)

    def test_sections_are_parsed_into_words_and_substrings(self):
        denylist, warnings = self.load(
            "# comment\n[words]\nAcme\n\n[substrings]\nAcme Corp\n")
        self.assertEqual(denylist.words, ("Acme",))
        self.assertEqual(denylist.substrings, ("Acme Corp",))
        self.assertEqual(warnings, ())

    def test_terms_are_deduped_in_first_seen_order(self):
        denylist, _ = self.load("[words]\nAcme\nContoso\nAcme\n")
        self.assertEqual(denylist.words, ("Acme", "Contoso"))

    def test_hash_mid_line_is_part_of_the_term(self):
        # Handles and paths legitimately contain '#', so inline comments are
        # NOT supported - dropping the tail would silently shorten a term.
        denylist, _ = self.load("[substrings]\nteam#alpha\n")
        self.assertEqual(denylist.substrings, ("team#alpha",))

    def test_multi_word_entry_in_words_section_warns(self):
        denylist, warnings = self.load("[words]\nJane Doe\n")
        self.assertEqual(denylist.words, ("Jane Doe",))
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("[substrings]", warnings[0])

    def test_term_before_any_section_header_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.load("Acme\n[words]\nContoso\n")
        self.assertIn("before any", str(ctx.exception))

    def test_unknown_section_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.load("[people]\nAcme\n")
        self.assertIn("unknown section", str(ctx.exception))

    def test_one_character_term_is_rejected(self):
        # A one-character term matches everything, which makes the gate useless
        # while still printing a reassuring "denylist: 12 terms" line.
        with self.assertRaises(ValueError) as ctx:
            self.load("[words]\nA\n")
        self.assertIn("too short", str(ctx.exception))

    def test_malformed_denylist_exits_2_rather_than_scanning_without_it(self):
        # Negative control on the whole loader: a broken denylist must be a bad
        # invocation, never a quiet scan with fewer terms.
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: tidy")
        bad = self.workdir / "bad.txt"
        bad.write_text("Acme\n", encoding="utf-8")
        rc, out = self.run_scan(str(root), "--denylist", str(bad),
                                denylist=False)
        self.assertEqual(rc, 2, out)
        self.assertIn("malformed denylist", out)

    def test_shipped_example_file_parses_and_holds_only_fake_terms(self):
        # The example is the only denylist that ships. If it stops parsing,
        # `is_unedited()` silently returns False and an unedited copy starts
        # counting as a configured gate.
        self.assertTrue(EXAMPLE_PATH.is_file(), EXAMPLE_PATH)
        denylist, _warnings = leak_scan.load_denylist(EXAMPLE_PATH)
        self.assertIn("Jane", denylist.words)
        self.assertIn("Jane Doe", denylist.substrings)
        self.assertGreater(len(denylist.substrings), 5)

    def test_empty_denylist_constant_disables_only_the_name_checks(self):
        text = f"Acme Corp memo, path {OTHER_HOME}\n"
        with_names = pairs(
            leak_scan.scan_text(text, "t", self.denylist))
        without = pairs(
            leak_scan.scan_text(text, "t", leak_scan.EMPTY_DENYLIST))
        self.assertIn(("denylist-term", "Acme Corp"), with_names)
        self.assertEqual({k for k, _ in without}, {"home-path"},
                         "structural regex rules must still run unconfigured")


# --- 2. Text scanning --------------------------------------------------------

class TestScanText(ScannerTestCase):

    def scan(self, text, **kw):
        return pairs(leak_scan.scan_text(text, "t", self.denylist, **kw))

    def test_clean_text_passes(self):
        self.assertEqual(
            leak_scan.scan_text("A generic note about design.", "t",
                                self.denylist),
            ())

    def test_word_term_detected(self):
        self.assertIn(("denylist-name", "Jane"),
                      self.scan("This note was written by Jane today."))

    def test_word_term_respects_boundaries(self):
        # `Doe` must not fire inside `Doesn't`, and `Acme` not inside `Acmes`.
        self.assertEqual(self.scan("Doesn't matter, Acmes aside."), set())

    def test_word_term_is_case_sensitive(self):
        # The whole point of the [words] section: `Will`, `Mark` and `Grace`
        # must not fire on the ordinary English words, so a lowercase
        # occurrence is deliberately NOT a finding - that is the documented
        # trade, and the reason ambiguous terms belong in [substrings].
        # `Contoso` is a [words] term only, so nothing else can mask this.
        self.assertEqual(self.scan("a contoso of a document"), set())
        self.assertIn(("denylist-name", "Contoso"),
                      self.scan("Contoso wrote it"))

    def test_substring_term_is_case_insensitive(self):
        self.assertIn(("denylist-term", "Acme Corp"),
                      self.scan("worked at acme corp for years"))

    def test_substring_term_matches_inside_a_word(self):
        # Substrings are matched loosely on purpose - distinctive enough that a
        # hit is almost always real, which is what catches `[[entities/janedoe]]`.
        self.assertIn(("denylist-term", "janedoe"),
                      self.scan("see [[entities/janedoe]] for details"))

    def test_home_path_substring_term_detected(self):
        self.assertIn(("denylist-term", FAKE_HOME),
                      self.scan(f"path is {FAKE_HOME}/Documents/x"))

    def test_findings_are_deduped_with_an_occurrence_count(self):
        findings = leak_scan.scan_text(
            "Jane\nnope\nJane again\n", "t", self.denylist)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].count, 2)
        self.assertEqual(findings[0].line, 1, "reports the FIRST line seen")
        self.assertEqual(findings[0].where, "t")

    def test_use_regex_false_keeps_the_denylist_only(self):
        # The identity-census and history-path paths both take this branch.
        text = f"Jane Doe <{PERSONAL_EMAIL}>"
        self.assertEqual(
            {k for k, _ in self.scan(text, use_regex=False)},
            {"denylist-name", "denylist-term"})
        self.assertIn("email", {k for k, _ in self.scan(text)})


class TestBuiltinIdentityRules(unittest.TestCase):
    """The four PII rules gitleaks has no equivalent for - this file's job.

    Measured 2026-07-30: gitleaks reported nothing at all on fixtures carrying
    an absolute home path, a real email address, a Google Docs URL with a
    document id, or a Calendar URL carrying an owner address, in either `git`
    or `dir` mode. They can never be delegated away.
    """

    def kinds(self, text):
        return {f.kind
                for f in leak_scan.scan_text(text, "t",
                                             leak_scan.EMPTY_DENYLIST)}

    def test_home_path_detected(self):
        self.assertIn("home-path", self.kinds(f"cd {OTHER_HOME}"))

    def test_email_detected(self):
        self.assertIn("email", self.kinds(f"write to {PERSONAL_EMAIL}"))

    def test_doc_url_detected(self):
        self.assertIn("doc-url", self.kinds(f"sheet: {DOC_URL}"))

    def test_calendar_url_detected(self):
        self.assertIn("calendar-url", self.kinds(f"cal: {CALENDAR_URL}"))


# --- 3. The rule set itself --------------------------------------------------

class TestRuleSet(unittest.TestCase):
    """Pins WHICH rules run, in both directions.

    This copy of the gate has a sibling in a private vault. They are meant to
    run an identical rule set, and they once diverged on exactly the two rules
    whose measurements were sloppiest - each file carrying a comment asserting
    the opposite of the other, with no way for a reader of either to tell which
    was right. Nothing detected it, because each copy passed its own tests.

    The sibling's detector imports this file from a developer's disk. That
    cannot be ported into a public repo, so the equivalent guard here is to pin
    THIS copy's rule set exactly: a rule appearing or disappearing fails a test
    instead of drifting. If you intentionally diverge the copies, put the dated
    reason in both files and update this test - do not just let it drift.
    """

    def test_retained_rule_set_is_exactly_what_was_measured(self):
        self.assertEqual(
            [k for k, _ in leak_scan.BUILTIN_CHECKS],
            ["home-path", "email", "doc-url", "calendar-url",
             "api-token", "slack-token", "secret-assignment",
             "private-key", "long-hex"])

    def test_identity_and_privacy_rules_are_all_present(self):
        self.assertLessEqual(
            {"home-path", "email", "doc-url", "calendar-url"},
            {k for k, _ in leak_scan.BUILTIN_CHECKS})

    def test_delegated_credential_rules_do_not_creep_back(self):
        """The four rules handed to gitleaks must stay gone.

        Not tidiness - two scanners disagreeing about the same credential class
        is how the weaker one's false positives (this file used to flag
        AKIAIOSFODNN7EXAMPLE, the AWS docs placeholder, which gitleaks
        correctly allowlists) get re-introduced and train people to ignore the
        gate. If you genuinely need one back, record why gitleaks is
        insufficient - measured on the sloppy shape, not the canonical one.
        """
        self.assertEqual(
            {"aws-key", "github-token", "google-api-key", "jwt"}
            & {k for k, _ in leak_scan.BUILTIN_CHECKS},
            set())

    def test_secret_kinds_names_only_rules_that_exist(self):
        self.assertLessEqual(
            leak_scan.SECRET_KINDS, {k for k, _ in leak_scan.BUILTIN_CHECKS},
            "SECRET_KINDS names a rule that no longer exists, so its values "
            "would be reprinted in full into CI logs")


class TestRetainedGitleaksGapRules(unittest.TestCase):
    """The five credential rules KEPT because gitleaks 8.30.1 MISSES them.

    Measured 2026-07-30, one minimal git repo per credential class, `gitleaks
    git .` run from inside it, each rule additionally isolated with
    `--enable-rule` so `generic-api-key` could not be mistaken for
    shape-specific coverage.

    MEASURE THE SHAPE THAT LEAKS, NOT THE SHAPE THAT IS EASY TO GENERATE. Two
    rules were deleted on 2026-07-30 and restored the same day, each because
    the fixtures behind the deletion only exercised the case gitleaks already
    handles: high-entropy random values for `secret-assignment`, whose whole
    reason to exist is human-typed low-entropy ones, and canonical 4-segment
    Slack tokens for `slack-token`, whose gap is the 3-segment ones. A fixture
    in the vendor's canonical format answers "does gitleaks parse the format",
    which was never the question.
    """

    def kinds(self, text):
        return {f.kind
                for f in leak_scan.scan_text(text, "t",
                                             leak_scan.EMPTY_DENYLIST)}

    def test_anthropic_key_is_still_caught_here(self):
        # gitleaks 8.30.1 has NO Anthropic rule at all: every sk-ant-* shape
        # missed. A vault written with an AI coding agent is likelier to
        # collect one of these than any other credential, which makes this the
        # highest-value rule in the file. It also caught 0/100 of a bare
        # non-vendor sk-/pk- token in ordinary prose ("the vendor gave us
        # sk-<40>"), which is exactly how a key gets pasted into a note.
        for key in (ANTHROPIC_KEY, ANTHROPIC_ADMIN_KEY, BARE_VENDOR_KEY):
            with self.subTest(key=key[:6]):
                self.assertIn("api-token", self.kinds(f"key: {key}"))

    def test_slack_3_segment_tokens_are_still_caught_here(self):
        # gitleaks covers xoxb / xoxa / xoxr and the canonical 4-segment xoxp,
        # plus xoxs in its 4- and 5-segment hex forms. It MISSES the 3-segment
        # and 2-segment xoxs/xoxp shapes below.
        for token in (SLACK_SESSION, SLACK_USER):
            with self.subTest(token=token[:5]):
                self.assertIn("slack-token",
                              self.kinds(assign_bare("value", token)))

    def test_human_typed_low_entropy_secret_is_still_caught_here(self):
        """gitleaks' `generic-api-key` is entropy-gated; this rule is not.

        Measured catch rate 99/100 on random high-entropy values but only
        31/100 on wordy low-entropy secrets - a passphrase a person actually
        typed into a note. A wiki is human prose, so these are the realistic
        shapes and gitleaks covers almost none of them.
        """
        for line in (assign("password", "correcthorsebatterystaple"),
                     assign("password", "summerhousebythelake", sep=":"),
                     assign("token", "MyDogsNameIsRufus1985"),
                     assign("secret", "thebluedoorattheback"),
                     "The wifi " + assign_bare("password",
                                               "BlueDoor" + "Office2026x")):
            with self.subTest(line=line):
                self.assertIn("secret-assignment", self.kinds(line))

    def test_private_key_header_without_end_marker_is_still_caught_here(self):
        # gitleaks requires the closing END marker AND real base64 material:
        # 100/100 on a full key, 0/100 on a bare header with the body truncated
        # or not yet pasted. A stray header is evidence a key passed through
        # this file, so the header alone must fire.
        for kind in ("RSA ", "OPENSSH ", "", "EC "):
            header = PRIVATE_KEY_HEADER.format(kind)
            with self.subTest(kind=kind.strip() or "generic"):
                self.assertIn("private-key",
                              self.kinds(f"{header}\nMIIBOgIBAAJBAKj3"))

    def test_long_hex_is_still_caught_here(self):
        # No gitleaks equivalent at all: 32-, 40- and 64-char hex all missed.
        # Opaque hex is how session tokens, digests and internal record ids
        # leak out of a wiki.
        for hexed in (HEX32, HEX40, HEX64):
            with self.subTest(length=len(hexed)):
                self.assertIn("long-hex", self.kinds(f"sig {hexed}"))

    def test_exemptions_that_serve_a_retained_rule_are_still_present(self):
        # long-hex survives, so its three anti-cry-wolf exemptions must survive
        # with it, or the gate fires on every SHA-pinned Action and every
        # checksum-verified download. secret-assignment survives, so
        # PLACEHOLDER_RE must too.
        self.assertEqual(self.kinds(ACTION_PIN_LINE), set())
        self.assertEqual(self.kinds(f"remote sha {'0' * 40}"), set())
        self.assertEqual(self.kinds(CHECKSUM_PIN_LINE), set())
        self.assertTrue(hasattr(leak_scan, "PLACEHOLDER_RE"))
        self.assertNotIn("secret-assignment",
                         self.kinds(assign("api_key", "your_api_key_here")))

    def test_no_two_private_key_headers_are_adjacent_in_this_file(self):
        """Guards the assembled fixture shape against a well-meaning tidy-up.

        Spelling the four headers out as adjacent literals is the obvious edit,
        and it costs twice: it fails this repo's gitleaks job on a fixture
        holding no key material, and it blinds gitleaks to a real private key
        anywhere later in this file, because the stray header starts a
        multi-line match that swallows the real key's own BEGIN line. Neither
        symptom shows up in this suite, which is exactly why the shape needs
        its own assertion.
        """
        source = pathlib.Path(__file__).read_text(encoding="utf-8")
        head = "-----BEGIN "
        tail = "PRIVATE KEY" + "-" * 5
        adjacent = re.compile(
            re.escape(head) + r"[A-Z ]*" + re.escape(tail)
            + r"[\s\S]{0,200}?" + re.escape(head) + r"[A-Z ]*" + re.escape(tail))
        self.assertIsNone(
            adjacent.search(source),
            "two literal private-key headers now sit next to each other in "
            "this file - assemble them from PRIVATE_KEY_HEADER instead")


# --- 4. False-positive exemptions, each with a negative control --------------

class TestExemptions(unittest.TestCase):
    """Each exemption is load-bearing: a gate that cries wolf gets ignored.

    Every case here is paired with a NEGATIVE CONTROL on the same rule, so an
    exemption that swallowed the whole check would fail this suite rather than
    passing it quietly.
    """

    def kinds(self, text):
        return {f.kind
                for f in leak_scan.scan_text(text, "t",
                                             leak_scan.EMPTY_DENYLIST)}

    def hex_values(self, text):
        """The long-hex VALUES reported, not just that the kind fired.

        `kinds()` collapses every finding to a label, which cannot tell "the
        exemption is scoped to the pinned value" apart from "the exemption is
        scoped to the whole line". Only the value can.
        """
        return {f.value
                for f in leak_scan.scan_text(text, "t",
                                             leak_scan.EMPTY_DENYLIST)
                if f.kind == "long-hex"}

    def test_sha_pinned_github_action_is_not_a_long_hex_finding(self):
        self.assertEqual(self.kinds(ACTION_PIN_LINE), set())
        # Negative control: the same SHA off a `uses:` line still fires.
        self.assertIn("long-hex", self.kinds(f"blob {HEX40}"))

    def test_git_null_sha_is_not_a_long_hex_finding(self):
        # What a pre-push hook passes to mean "no such ref". 40 hex, no secret.
        self.assertEqual(self.kinds(f"remote sha {'0' * 40}"), set())
        # Negative control: 40 hex that is not all-zero is still a finding.
        self.assertIn("long-hex", self.kinds("remote sha " + "0" * 39 + "1"))

    def test_pinned_release_checksum_is_not_a_long_hex_finding(self):
        # A vendor's published digest is the OPPOSITE of a secret: it proves a
        # downloaded binary was not tampered with. Red-lining it pressures the
        # author into deleting the verification step instead.
        self.assertEqual(self.kinds(CHECKSUM_PIN_LINE), set())
        self.assertEqual(self.kinds(assign_bare("sha256", HEX32, sep=":")), set())
        # Negative controls, both directions. The exemption is per-VALUE on the
        # same line, not per-line: an unrelated blob on a line that merely
        # mentions sha256 still fires, and the same digest with no checksum
        # label still fires.
        self.assertIn("long-hex",
                      self.kinds(f"sha256 checksums for the release: {HEX64}"))
        self.assertIn("long-hex", self.kinds(f"digest {HEX32}"))

        # ...and the two above do NOT actually prove the per-VALUE claim their
        # comment makes. On both of those lines the pin regexes capture NOTHING
        # (`sha256 checksums for the release:` has >12 non-alphanumerics before
        # the digest; `digest` is not a checksum label at all), so `pinned` is
        # EMPTY and they only ever assert that a line no exemption matched still
        # fires. Widening `is_exempt()` from `low in pinned` to `bool(pinned)` -
        # i.e. exempting EVERY long hex on any line that carries a pin - was
        # measured to survive the entire suite.
        #
        # These two close it. Each line carries a genuine pin AND a second,
        # unrelated hex value, so the pin regex matches and `pinned` is
        # non-empty. Per-value scoping reports exactly the unrelated value;
        # per-line scoping reports nothing at all.
        action_pin_plus_stray = (
            f"      uses: actions/checkout@{HEX40}  # audit token {HEX64}")
        checksum_pin_plus_stray = (
            f"          GITLEAKS_SHA256: '{HEX64}'  # session {HEX32}")
        self.assertEqual(
            self.hex_values(action_pin_plus_stray), {HEX64},
            "a stray hex beside a SHA-pinned action must still fire, and the "
            "pinned SHA itself must not - the exemption is per-value")
        self.assertEqual(
            self.hex_values(checksum_pin_plus_stray), {HEX32},
            "a stray hex beside a pinned release checksum must still fire, and "
            "the checksum itself must not - the exemption is per-value")

    def test_noreply_and_example_emails_are_exempt(self):
        for address in ("41898282+github-actions[bot]"
                        + "@users.noreply.github.com",
                        "noreply" + "@anything.dev",
                        "someone" + "@example.com",
                        "sprite" + "@2x.png"):
            with self.subTest(address=address):
                self.assertNotIn("email", self.kinds(f"contact {address}"))
        # Negative control: a real-looking personal address is still a finding.
        self.assertIn("email", self.kinds(f"contact {PERSONAL_EMAIL}"))

    def test_ci_home_paths_are_exempt(self):
        # Service accounts and shared dirs leak nothing about a person, and
        # /home/runner shows up in every CI log snippet.
        for path in ("/home/runner/work/repo", "/home/root/x", _U + "shared/y"):
            with self.subTest(path=path):
                self.assertNotIn("home-path", self.kinds(f"cd {path}"))
        # Negative control: a real user's home path is still a finding.
        self.assertIn("home-path", self.kinds(f"cd {OTHER_HOME}"))

    def test_placeholder_secret_values_are_exempt(self):
        # Every documented fill-me-in value in a template corpus takes this
        # branch; without it the gate red-lines its own documentation.
        for line in (assign("api_key", "your_api_key_here"),
                     assign("secret", "EXAMPLE_VALUE_GOES_HERE", sep=":"),
                     assign("password", "changeme_placeholder")):
            with self.subTest(line=line):
                self.assertNotIn("secret-assignment", self.kinds(line))
        # Negative control: a real-shaped value is still a finding.
        self.assertIn("secret-assignment",
                      self.kinds(assign("api_key",
                                        "8Fq2mZr7" + "Xk1pLd93QbVt")))

    def test_denylist_paths_are_registered_in_the_right_exemption_set(self):
        # denylist.txt is never opened at all; the example is opened but the
        # regex battery is skipped, so real names pasted into it are still
        # caught. The behavioural halves are asserted in TestScanFiles.
        self.assertIn(leak_scan.DENYLIST_REL, leak_scan.NEVER_SCAN)
        self.assertIn(leak_scan.DENYLIST_REL, leak_scan.REGEX_EXEMPT)
        self.assertIn(leak_scan.EXAMPLE_REL, leak_scan.REGEX_EXEMPT)
        self.assertNotIn(leak_scan.EXAMPLE_REL, leak_scan.NEVER_SCAN)


# --- 5. File selection and the worktree pass ---------------------------------

class TestScanFiles(ScannerTestCase):

    def test_walk_skips_the_git_dir(self):
        root = self.temp_root()
        (root / ".git").mkdir()
        (root / ".git" / "leaky.txt").write_text("Jane Doe", encoding="utf-8")
        (root / "clean.md").write_text("nothing here", encoding="utf-8")
        selected = leak_scan.walk_all_files(root)
        self.assertEqual(selected, frozenset({"clean.md"}))
        self.assertEqual(
            leak_scan.scan_files(root, selected, self.denylist), ((), ()))

    def test_finds_leak_in_file(self):
        root = self.temp_root()
        (root / "note.md").write_text("written by Jane Doe", encoding="utf-8")
        findings, skipped = leak_scan.scan_files(
            root, leak_scan.walk_all_files(root), self.denylist)
        self.assertEqual(wheres(findings), {"note.md"})
        self.assertIn(("denylist-term", "Jane Doe"), pairs(findings))
        self.assertEqual(skipped, ())

    def test_never_scan_denylist_file_is_not_opened(self):
        # Its entire content is the search terms themselves: reading it into
        # the report would print the roster of real names into a CI log.
        root = self.temp_root()
        (root / ".claude" / "scripts").mkdir(parents=True)
        (root / leak_scan.DENYLIST_REL).write_text(
            f"[words]\nJane\n[substrings]\n{FAKE_HOME}\n", encoding="utf-8")
        self.assertEqual(
            leak_scan.scan_files(root, leak_scan.walk_all_files(root),
                                 self.denylist),
            ((), ()),
            "denylist.txt must never be read into the scan output")
        # ...but shipping it is a hard structural failure - see
        # TestStructuralChecks.test_forbidden_denylist_in_shipping_set.

    def test_shipping_set_excludes_gitignored_files(self):
        root = self.minimal_repo()
        (root / ".gitignore").write_text("local/\n", encoding="utf-8")
        (root / "local").mkdir()
        (root / "local" / "notes.md").write_text("Jane Doe", encoding="utf-8")
        git(root, "add", ".gitignore")
        git(root, "commit", "-q", "-m", "chore: tidy")
        self.assertNotIn("local/notes.md", leak_scan.shipping_set(root))
        self.assertIn("local/notes.md", leak_scan.walk_all_files(root))

    def test_shipping_set_includes_untracked_files(self):
        """The POSITIVE half of the shipping-set contract.

        The test above only asserts what is EXCLUDED, so dropping `--others
        --exclude-standard` from the `git ls-files` call still passes it - and
        that change silently stops scanning every file written but not yet
        `git add`ed. Those files publish on the next `git add -A && git push`.
        """
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: tidy")
        (root / "draft.md").write_text(
            "the Acme Corp rollout plan\n", encoding="utf-8")

        shipping = leak_scan.shipping_set(root)
        self.assertIn("draft.md", shipping, "untracked file must ship")
        self.assertIn("a.md", shipping, "tracked file must ship too")

        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, f"leak in an unstaged file must not PASS:\n{out}")
        self.assertIn("draft.md", out)

    def test_builtin_regex_checks_run_through_the_real_file_path(self):
        """Pins the regex battery to the `scan_files()` gate, not just to
        `scan_text()` called directly.

        Flipping `use_regex=rel not in REGEX_EXEMPT` to `use_regex=False`
        disables ALL of them - keys, emails, home paths, doc/calendar URLs,
        long hex - for every worktree file. A suite whose other fixtures all
        leak via the denylist stays green through that change, because the
        denylist path is untouched. This fixture contains NO denylist term on
        purpose: the regex rules are the only thing that can catch it.
        """
        body = f"deploy key: {ANTHROPIC_KEY}\nexport path={OTHER_HOME}\n"
        root = self.minimal_repo()
        (root / "runbook.md").write_text(body, encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: tidy")

        self.assertEqual(
            pairs(leak_scan.scan_text(body, "t", self.denylist,
                                      use_regex=False)),
            set(),
            "fixture must be invisible to the denylist rules alone")
        findings, skipped = self.worktree_findings(root)
        self.assertEqual(skipped, ())
        self.assertLessEqual({"api-token", "home-path"},
                             {f.kind for f in findings})

        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, f"regex-only leak must not PASS:\n{out}")
        self.assertIn("api-token", out)

    def test_regex_exempt_file_skips_regex_checks_but_not_the_denylist(self):
        """The other half of the same `use_regex=` argument.

        Inverting the exemption (regex on for every file) makes the gate cry
        wolf on the example denylist's deliberately fake home path, which is
        the whole point of an example denylist.
        """
        root = self.temp_root()
        (root / ".claude" / "scripts").mkdir(parents=True)
        (root / leak_scan.EXAMPLE_REL).write_text(
            f"{PLACEHOLDER_HOME}\nAcme Corp\n", encoding="utf-8")
        findings, skipped = leak_scan.scan_files(
            root, {leak_scan.EXAMPLE_REL}, self.denylist)
        self.assertEqual(skipped, ())
        self.assertNotIn("home-path", {f.kind for f in findings},
                         "the example file's fake home path is intentional")
        # Negative control: the file is exempt from the REGEX rules only.
        self.assertIn(("denylist-term", "Acme Corp"), pairs(findings))

    def test_all_files_flag_reaches_gitignored_files(self):
        """The `--all-files` WIRING, not just `walk_all_files()` as a function.

        The module docstring makes `--all-files` the invocation for a release
        that produces a zip rather than a push, so a no-op flag means a zip
        release ships every gitignored leak.
        """
        root = self.minimal_repo()
        (root / ".gitignore").write_text("local/\n", encoding="utf-8")
        (root / "local").mkdir()
        (root / "local" / "notes.md").write_text(
            "notes from the Northwind Traders offsite\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: tidy")

        # Negative control: the documented DEFAULT is to not read it.
        rc_default, out_default = self.run_scan(str(root))
        self.assertEqual(rc_default, 0, out_default)
        self.assertNotIn("local/notes.md", out_default)

        rc_all, out_all = self.run_scan(str(root), "--all-files")
        self.assertEqual(rc_all, 1,
                         f"--all-files must read gitignored files:\n{out_all}")
        self.assertIn("local/notes.md", out_all)


# --- 6. The regex-exemption asymmetry regression -----------------------------

class TestRegexExemptionSymmetry(ScannerTestCase):
    """REGRESSION (fixed 2026-07-30): the exemption ran in the worktree pass
    only, not in the history-blob pass.

    denylist.txt and denylist.example.txt hold deliberate placeholders - an
    invented home directory, an invented person. The worktree pass exempted
    them from the regex battery; the history pass did not. So the moment either
    file had a second version, the gate reported its own documentation as a
    home-path leak, which is exactly how it started failing on this repo.

    The negative control below is the more important half: a fix that
    over-applied the exemption - disabling the regex battery for every history
    blob - would be far worse than the bug it closed.
    """

    def example_repo_with_two_versions(self):
        root = self.temp_root()
        git(root, "init", "-q")
        (root / ".claude" / "scripts").mkdir(parents=True)
        example = root / leak_scan.EXAMPLE_REL
        # A placeholder home path that is NOT a denylist term, so this fixture
        # asks only about the REGEX exemption.
        example.write_text(PLACEHOLDER_HOME + "\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "docs: add example denylist")
        # The second version supersedes the first, so the original blob is now
        # reachable from history but absent from HEAD - the history-blob pass.
        example.write_text(PLACEHOLDER_HOME + "-2\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "docs: update example denylist")
        return root

    def test_history_blob_of_the_example_file_is_regex_exempt(self):
        root = self.example_repo_with_two_versions()
        self.assertEqual(len(self.history_only_blobs(root)), 1,
                         "fixture needs exactly one superseded blob")
        rc, out = self.run_scan(str(root))
        self.assertNotIn("home-path", out,
                         "the example file's fake home path is intentional in "
                         "history too, not just in the worktree")
        self.assertEqual(rc, 0, out)

    def test_history_blob_exemption_is_scoped_to_the_exempt_files(self):
        """NEGATIVE CONTROL: a real home path in a DELETED file is still caught."""
        root = self.temp_root("neg")
        git(root, "init", "-q")
        (root / "notes.md").write_text(
            f"path was {OTHER_HOME}\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: add notes")
        git(root, "rm", "-q", "-f", "notes.md")
        git(root, "commit", "-q", "-m", "chore: remove notes")

        self.assert_clean_worktree(root)
        rc, out = self.run_scan(str(root))
        self.assertIn("home-path", out,
                      "a real home path in a deleted file must still be caught")
        self.assertEqual(rc, 1, out)

    def test_denylist_terms_still_apply_inside_the_exempt_files(self):
        """The exemption is REGEX-only, in history as in the worktree.

        A real name pasted into the example file is still a leak, and this is
        the assertion that stops the fix widening into "skip these files".
        """
        root = self.temp_root("terms")
        git(root, "init", "-q")
        (root / ".claude" / "scripts").mkdir(parents=True)
        example = root / leak_scan.EXAMPLE_REL
        example.write_text("Acme Corp\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "docs: add example")
        example.write_text("Contoso only\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "docs: scrub example")

        findings, _problems, _stats = self.history_findings(root)
        self.assertIn(("denylist-term", "Acme Corp"), pairs(findings))


# --- 7. The eight leak surfaces ---------------------------------------------

class TestLeakSurfaces(ScannerTestCase):
    """One MINIMAL repo per surface the scanner must cover.

    Each fixture holds exactly one leak, in one place. Where a surface needs
    two commits (a deletion), that is called out - everywhere else a second
    commit would make the history blob pass non-empty and could mask a broken
    code path.
    """

    def assert_reported(self, root, expected_pair, where_pred, why):
        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, f"scanner passed a leaking repo:\n{out}")
        history, problems, _stats = self.history_findings(root)
        worktree, _skipped = self.worktree_findings(root)
        every = (*history, *worktree)
        self.assertIn(expected_pair, pairs(every), out)
        matching = [f for f in every
                    if (f.kind, f.value) == expected_pair and where_pred(f.where)]
        self.assertTrue(
            matching,
            f"expected the finding to come from {why}, got locations "
            f"{[f.where for f in every if (f.kind, f.value) == expected_pair]}")
        return problems

    @staticmethod
    def commit_message_where(where):
        # "(commit 1a2b3c4)" - deliberately NOT "(commit 1a2b3c4 identity)".
        return re.fullmatch(r"\(commit [0-9a-f]{7}\)", where) is not None

    # 1 - commit SUBJECT
    def test_surface_1_denylist_term_in_commit_subject(self):
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "docs: notes from the Acme Corp offsite")
        self.assert_clean_worktree(root)
        self.assert_reported(root, ("denylist-term", "Acme Corp"),
                             self.commit_message_where, "a commit message")

    # 2 - commit BODY
    def test_surface_2_denylist_term_in_commit_body(self):
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: tidy",
            "-m", "reviewed at the Northwind Traders offsite")
        self.assert_clean_worktree(root)
        self.assert_reported(root, ("denylist-term", "Northwind Traders"),
                             self.commit_message_where, "a commit message")

    # 3 - BRANCH / ref name
    def test_surface_3_denylist_term_in_branch_name(self):
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: tidy")
        git(root, "branch", "-m", "feature/janes-vault-migration")
        self.assert_clean_worktree(root)
        self.assert_reported(root, ("denylist-term", "janes-vault"),
                             lambda w: "ref names" in w, "the ref-name pass")

    # 4 - ANNOTATED TAG message: invisible to `git log` (which never prints tag
    #     objects) and to the blob pass (which drops every non-blob). The tag
    #     NAME and the branch name are deliberately clean, so the message is
    #     the only possible source of this finding.
    def test_surface_4_denylist_term_in_annotated_tag_message(self):
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: tidy")
        git(root, "tag", "-a", "v1.0", "-m", "signed off by Jane Doe")
        self.assert_clean_worktree(root)
        self.assert_reported(root, ("denylist-term", "Jane Doe"),
                             lambda w: "tag messages" in w, "the tag-message pass")

    # 5 - committer IDENTITY (the email handle, not the bare name)
    def test_surface_5_denylist_handle_in_committer_identity(self):
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: tidy",
            ident=("-c", "user.name=A",
                   "-c", "user.email=janedoe@example.com",
                   "-c", "commit.gpgsign=false"))
        self.assert_clean_worktree(root)
        self.assert_reported(root, ("denylist-term", "janedoe"),
                             lambda w: "identity" in w, "the identity pass")

    def test_surface_5b_identity_census_is_always_reported(self):
        # The complementary control: the identity SET is printed for a human to
        # confirm even when nothing red-lines. Identities are deliberately not
        # run through the regex rules - every commit carries an email, so the
        # generic rule would fire on a provably clean repo.
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: tidy")
        _f, _p, stats = self.history_findings(root)
        self.assertIn("Fixture Bot <fixture@example.com>", stats["identities"])
        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 0, out)
        self.assertIn("commit identities", out)

    # 6 - DELETED FILE's blob: gone from HEAD, still readable in history.
    #     Structurally needs two commits (add, then remove).
    def test_surface_6_denylist_term_in_deleted_file_blob(self):
        root = self.minimal_repo()
        (root / "secret.md").write_text(
            "meeting notes with Jane Doe\n", encoding="utf-8")
        git(root, "add", "secret.md")
        git(root, "commit", "-q", "-m", "chore: add notes")
        git(root, "rm", "-q", "-f", "secret.md")
        git(root, "commit", "-q", "-m", "chore: remove notes")
        self.assertFalse((root / "secret.md").exists())
        self.assert_clean_worktree(root)
        self.assert_reported(root, ("denylist-term", "Jane Doe"),
                             lambda w: w.startswith("secret.md@"),
                             "the history-blob pass")

    # 7 - DELETED DIRECTORY PATH: the file contents were always clean; the
    #     folder NAME is the leak. Also structurally needs two commits.
    def test_surface_7_denylist_term_in_deleted_directory_path(self):
        root = self.minimal_repo()
        leaky_dir = root / "janes-vault-export"
        leaky_dir.mkdir()
        (leaky_dir / "f.md").write_text(
            "fully scrubbed content\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: add folder")
        git(root, "rm", "-rq", "-f", "janes-vault-export")
        git(root, "commit", "-q", "-m", "chore: remove folder")
        self.assert_clean_worktree(root)
        problems = self.assert_reported(
            root, ("denylist-term", "janes-vault"),
            lambda w: w == "(history paths)", "the history-path pass")
        self.assertEqual(problems, ())

    # 8 - WORKTREE file: the surface everything else was bolted onto.
    def test_surface_8_denylist_term_in_worktree_file(self):
        root = self.minimal_repo()
        (root / "leak.md").write_text(
            "the Acme Corp rollout plan\n", encoding="utf-8")
        git(root, "add", "leak.md")
        git(root, "commit", "-q", "-m", "chore: add plan")
        worktree, skipped = self.worktree_findings(root)
        self.assertIn(("denylist-term", "Acme Corp"), pairs(worktree))
        self.assertIn("leak.md", wheres(worktree))
        self.assertEqual(skipped, ())
        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, out)
        self.assertIn("leak.md", out)


# --- 8. The early-return regression -----------------------------------------

class TestEarlyReturnRegressionCommitMessageOnlyLeak(ScannerTestCase):
    """Regression: a denylist term ONLY in a commit subject, in a repo with a
    single commit and a provably clean worktree, MUST be reported.

    THE BUG: `scan_history()` returned early when there were no history-only
    blobs - i.e. when nothing reachable from a ref was absent from HEAD - with
    the commit-metadata scan sitting AFTER that return. A repo that had never
    deleted a file has no such blob, so the function returned before the commit
    pass ever ran and the scanner printed "PASS" on a repo whose commit subject
    named the employer. That is the exact class of leak this gate exists to
    close: the acronym that rode along in a public commit message for weeks.

    The original regression test for it PASSED against the broken scanner,
    because its fixture happened to contain a superseded blob. Hence the two
    guard assertions below: the worktree finding count must be EXACTLY ZERO,
    and the history-only blob set must be EMPTY. Together they prove the
    finding could only have come from the commit-metadata pass, reached on the
    early-return path. Do not "simplify" this fixture by adding a commit.
    """

    def test_denylist_term_only_in_commit_subject_is_reported(self):
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "docs: notes from the Acme Corp offsite")

        # Guard 1: the worktree is provably clean - EXACTLY zero findings.
        worktree, skipped = self.worktree_findings(root)
        self.assertEqual(len(worktree), 0,
                         f"worktree must contribute no findings: {pairs(worktree)}")
        self.assertEqual(skipped, ())

        # Guard 2: no history-only blobs, so the early-return path is taken.
        self.assertEqual(self.history_only_blobs(root), (),
                         "fixture must have no superseded blobs, or this test "
                         "can pass without the commit-metadata scan running")

        # The assertion the bug broke.
        history, problems, _stats = self.history_findings(root)
        self.assertIn(("denylist-term", "Acme Corp"), pairs(history))
        self.assertTrue(
            any(re.fullmatch(r"\(commit [0-9a-f]{7}\)", f.where)
                for f in history),
            f"finding must be located in a commit message: {wheres(history)}")
        self.assertEqual(problems, ())

        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, f"scanner must not PASS this repo:\n{out}")
        self.assertNotIn("PASS", out)

    def test_ref_pass_also_survives_an_empty_history_blob_set(self):
        # Same shape, different pass: the ref/tag scan sits after the same
        # return, so it needs the same guard.
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: tidy")
        git(root, "tag", "-a", "v1.0", "-m", "approved by Jane Doe")

        worktree, _skipped = self.worktree_findings(root)
        self.assertEqual(len(worktree), 0)
        self.assertEqual(self.history_only_blobs(root), ())

        history, _problems, _stats = self.history_findings(root)
        self.assertIn(("denylist-term", "Jane Doe"), pairs(history))


# --- 9. Structural checks ----------------------------------------------------

class TestStructuralChecks(ScannerTestCase):

    def template_shaped_repo(self, commits=1, files_per_dir=1):
        root = self.temp_root()
        git(root, "init", "-q")
        for name in sorted(leak_scan.WIKI_CONTENT_DIRS):
            (root / name).mkdir(parents=True)
            for n in range(files_per_dir):
                (root / name / f"stub-{n}.md").write_text("x", encoding="utf-8")
        (root / "raw" / "notes-import").mkdir(parents=True)
        (root / "raw" / "notes-import" / "sample.md").write_text(
            "x", encoding="utf-8")
        for n in range(commits):
            (root / f"c{n}.txt").write_text(str(n), encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", f"chore: step {n}")
        return root

    def test_template_shaped_repo_is_structurally_clean(self):
        self.assertEqual(self.structure(self.template_shaped_repo(1)), ())

    def test_forbidden_denylist_in_shipping_set(self):
        root = self.minimal_repo()
        (root / ".claude" / "scripts").mkdir(parents=True)
        (root / leak_scan.DENYLIST_REL).write_text(
            "[words]\nJane\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: tidy")
        problems = self.structure(root)
        self.assertTrue(
            any(leak_scan.DENYLIST_REL in p and "forbidden" in p
                for p in problems), problems)
        # ...and it red-lines the real invocation, not just the helper.
        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, out)

    def test_every_forbidden_path_is_detected_in_the_shipping_set(self):
        # A per-path loop rather than one example, so a path quietly dropped
        # from FORBIDDEN_PATHS fails here.
        for forbidden in leak_scan.FORBIDDEN_PATHS:
            with self.subTest(forbidden=forbidden):
                root = self.temp_root(f"fp-{forbidden.replace('/', '_')}")
                git(root, "init", "-q")
                target = root / forbidden / "x.txt"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x", encoding="utf-8")
                git(root, "add", "-Af")
                git(root, "commit", "-q", "-m", "chore: add")
                problems = self.structure(root)
                self.assertTrue(any(forbidden in p and "forbidden" in p
                                    for p in problems), problems)

    def test_gitignored_caches_are_advisory_not_fatal(self):
        """Running any python script in the target recreates `__pycache__`.

        Mere presence on disk must not red-line the gate forever, or the gate
        becomes something you pass by adding `|| true`.
        """
        root = self.minimal_repo()
        (root / ".gitignore").write_text(".qmd/\n__pycache__/\n", encoding="utf-8")
        git(root, "add", ".gitignore")
        for cache in (".qmd", "__pycache__"):
            (root / cache).mkdir()
            (root / cache / "blob.bin").write_bytes(b"cache\n")
        git(root, "commit", "-q", "-m", "chore: tidy")

        self.assertEqual(self.structure(root), ())
        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 0, out)

    def test_caches_in_the_shipping_set_are_a_hard_failure(self):
        # NEGATIVE CONTROL: proves the advisory branch above is not vacuous.
        root = self.minimal_repo()
        for cache in (".qmd", "__pycache__"):
            (root / cache).mkdir()
            (root / cache / "blob.bin").write_bytes(b"cache\n")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: tidy")
        problems = self.structure(root)
        self.assertTrue(any(".qmd" in p for p in problems), problems)
        self.assertTrue(any("__pycache__" in p for p in problems), problems)

    def test_forbidden_artifact_on_disk_outside_a_repo(self):
        """With no git repo there is no shipping set, so presence on disk is
        the only signal available - a zip-assembled release takes this path.

        The directory is deliberately EMPTY: a forbidden dir containing files
        is caught by the path check above (the walk lists them), so only an
        empty one can prove the `not in_repo` fallback exists at all. An empty
        `.qmd/` left behind by a deleted index is exactly the shape that would
        otherwise ship unnoticed.
        """
        root = self.temp_root("nogit")
        (root / "note.md").write_text("clean prose\n", encoding="utf-8")
        (root / ".qmd").mkdir()
        problems = self.structure(root)
        self.assertTrue(any(".qmd" in p and "on disk" in p for p in problems),
                        problems)
        # NEGATIVE CONTROL: inside a repo the same empty dir is invisible to
        # git and must NOT red-line, or every developer checkout fails.
        repo = self.minimal_repo("nogit-control")
        git(repo, "commit", "-q", "-m", "chore: tidy")
        (repo / ".qmd").mkdir()
        self.assertEqual(self.structure(repo), ())

    def test_stray_assets_file_flagged(self):
        # A screenshot or PDF under assets/ leaks silently: a text gate cannot
        # read it, so it must be reported rather than skipped.
        root = self.minimal_repo()
        (root / "assets").mkdir()
        (root / "assets" / ".gitkeep").write_text("", encoding="utf-8")
        (root / "assets" / "whiteboard.txt").write_text("x", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: tidy")
        self.assertTrue(any("assets/ ships" in p for p in self.structure(root)),
                        self.structure(root))
        # NEGATIVE CONTROL: .gitkeep alone must not trip it, or every fresh
        # clone fails the gate.
        (root / "assets" / "whiteboard.txt").unlink()
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: drop")
        self.assertEqual(self.structure(root), ())

    def test_content_census_counts_every_raw_and_wiki_dir(self):
        # The census is the always-printed control that replaced exact counts:
        # a folder someone forgot is a leak no text scan can see.
        root = self.template_shaped_repo(1)
        census = leak_scan.content_census(leak_scan.shipping_set(root))
        self.assertEqual(census.get("wiki/topics"), 1)
        self.assertEqual(census.get("raw/notes-import"), 1)
        self.assertNotIn(".", census, "root-level files are not content dirs")
        _rc, out = self.run_scan(str(root))
        self.assertIn("content census", out)
        self.assertIn("wiki/topics: 1", out)

    def test_over_ceiling_content_dir_flagged(self):
        # Publish stubs, not the real corpus.
        root = self.template_shaped_repo(1)
        for n in range(leak_scan.DEFAULT_MAX_CONTENT_FILES + 1):
            (root / "wiki" / "topics" / f"real-{n}.md").write_text(
                "x", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: corpus")
        problems = self.structure(root)
        self.assertTrue(
            any("ceiling" in p and "wiki/topics" in p for p in problems),
            problems)
        # NEGATIVE CONTROL: the ceiling is configurable, so a deliberately
        # larger tree can still pass.
        self.assertEqual(self.structure(root, "--max-content-files", "50"), ())

    def test_uncapped_directory_is_counted_but_not_ceilinged(self):
        # NEGATIVE CONTROL for the ceiling's scope: `wiki/glossary` is content
        # but not in WIKI_CONTENT_DIRS, so it is censused, never capped.
        root = self.template_shaped_repo(1)
        (root / "wiki" / "glossary").mkdir(parents=True)
        for n in range(leak_scan.DEFAULT_MAX_CONTENT_FILES + 3):
            (root / "wiki" / "glossary" / f"g-{n}.md").write_text(
                "x", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: glossary")
        self.assertEqual(self.structure(root), ())
        census = leak_scan.content_census(leak_scan.shipping_set(root))
        self.assertEqual(census["wiki/glossary"],
                         leak_scan.DEFAULT_MAX_CONTENT_FILES + 3)

    def test_multi_commit_repo_flagged_only_when_opted_in(self):
        root = self.template_shaped_repo(3)
        self.assertEqual(self.structure(root), (),
                         "a real history must not fail by default")
        opted_in = self.structure(root, "--expect-single-commit")
        self.assertTrue(
            any("commit(s), expected exactly 1" in p for p in opted_in),
            opted_in)

    def test_single_commit_repo_satisfies_the_opt_in(self):
        # NEGATIVE CONTROL: the release-assembly check must pass on the shape
        # it is asking for, or it is just a permanent red line.
        root = self.template_shaped_repo(1)
        self.assertEqual(self.structure(root, "--expect-single-commit"), ())


# --- 10. Template-specific: the gate must never look configured when it is not

class TestUnconfiguredGate(ScannerTestCase):
    """Exit code 3 - the state that does not exist in the private copy.

    The mechanism ships; the denylist cannot. So this copy loads its terms at
    runtime and MUST refuse to look like a passing gate when they are missing:
    an unconfigured run is not a clean run, and the difference is invisible in
    a wrapper script that only checks for zero.
    """

    def clean_repo(self):
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: tidy")
        return root

    def test_missing_denylist_exits_3_with_a_banner(self):
        rc, out = self.run_scan(str(self.clean_repo()),
                                "--denylist", str(self.workdir / "absent.txt"),
                                denylist=False)
        self.assertEqual(rc, 3, out)
        self.assertIn("NAME CHECKS ARE DISABLED", out)
        self.assertIn("was not found", out)
        self.assertNotIn("PASS", out)

    def test_configured_and_clean_exits_0(self):
        # NEGATIVE CONTROL: exit 3 must not be reachable when the gate IS
        # configured, or it is just a second name for "clean".
        rc, out = self.run_scan(str(self.clean_repo()))
        self.assertEqual(rc, 0, out)
        self.assertIn("PASS", out)
        self.assertIn("denylist:", out)

    def test_findings_beat_unconfigured_so_the_exit_is_1_not_3(self):
        """"Do not publish" is the more urgent fact.

        The documented contract is that wrapper scripts branch on `!= 0`, never
        on `== 3` - and the first run on a fresh clone is exactly where those
        two diverge. This also proves the structural and regex halves still run
        with no denylist at all.
        """
        root = self.clean_repo()
        (root / "note.md").write_text(f"cd {OTHER_HOME}\n", encoding="utf-8")
        rc, out = self.run_scan(str(root),
                                "--denylist", str(self.workdir / "absent.txt"),
                                denylist=False)
        self.assertEqual(rc, 1, out)
        self.assertIn("NAME CHECKS ARE DISABLED", out)
        self.assertIn("home-path", out)

    def unedited_repo(self, edit=False):
        """A repo whose denylist.txt is a copy of its own example file."""
        root = self.minimal_repo("unedited")
        (root / ".claude" / "scripts").mkdir(parents=True)
        (root / ".gitignore").write_text(
            leak_scan.DENYLIST_REL + "\n", encoding="utf-8")
        # A synthetic example rather than the shipped one: the shipped file's
        # terms appear inside its own body, so loading it as the live denylist
        # would make it match itself and muddy what this test is asking.
        example = "[words]\nFabrikam\n[substrings]\nFabrikam Ltd\n"
        (root / leak_scan.EXAMPLE_REL).write_text(example, encoding="utf-8")
        (root / leak_scan.DENYLIST_REL).write_text(
            example + ("[words]\nContoso\n" if edit else ""), encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "docs: add example denylist")
        return root

    def test_unedited_copy_of_the_example_counts_as_unconfigured(self):
        # An unedited copy protects nobody, so it must not be mistaken for a
        # configured gate just because the file exists.
        rc, out = self.run_scan(str(self.unedited_repo()), denylist=False)
        self.assertEqual(rc, 3, out)
        self.assertIn("unedited copy of the example", out)
        self.assertIn("NAME CHECKS ARE DISABLED", out)

    def test_edited_denylist_at_the_default_location_is_used(self):
        """NEGATIVE CONTROL, and the `resolve_denylist_path()` happy path.

        One added term flips the same repo from unconfigured to configured,
        and the added term is then actually searched for.
        """
        root = self.unedited_repo(edit=True)
        (root / "note.md").write_text("about Contoso\n", encoding="utf-8")
        rc, out = self.run_scan(str(root), denylist=False)
        self.assertEqual(rc, 1, out)
        self.assertNotIn("NAME CHECKS ARE DISABLED", out)
        self.assertIn("denylist-name", out)
        self.assertIn("Contoso", out)

    def test_resolve_denylist_path_prefers_explicit_then_root_then_script(self):
        root = self.temp_root("resolve")
        explicit = self.opts_for(root, "--denylist", str(self.denylist_path))
        self.assertEqual(leak_scan.resolve_denylist_path(root, explicit),
                         self.denylist_path)

        default = self.opts_for(root)
        # No denylist under the target: falls back to the one beside the
        # script. Asserted as a PATH, never read - on a maintainer's machine
        # that file holds real names.
        self.assertEqual(leak_scan.resolve_denylist_path(root, default),
                         SCRIPT_PATH.parent / "denylist.txt")

        (root / ".claude" / "scripts").mkdir(parents=True)
        in_root = root / leak_scan.DENYLIST_REL
        in_root.write_text("[words]\nContoso\n", encoding="utf-8")
        self.assertEqual(leak_scan.resolve_denylist_path(root, default), in_root)

    def test_default_root_is_the_repo_the_script_lives_in(self):
        """No positional argument scans the tree the script was copied into.

        Run as a real subprocess against a COPY of the script, so the assertion
        is about `parents[2]` resolution rather than about wherever this suite
        happens to be checked out. That also exercises the actual CLI entry
        point and its exit code, which `main(argv)` in-process does not.

        ASSERT ON THE ROOT LINE, NOT ON THE BARE PATH. A plain
        `assertIn(str(tree), out)` passes against a scanner whose `default_root`
        is `Path.cwd()` - measured, the mutation survived. The path shows up in
        the "denylist.txt was not found" banner too, and that banner always
        names the SCRIPT-adjacent path no matter which root was actually
        scanned, so the substring is satisfied by an unrelated line while
        `note.md`, `home-path` and rc=1 all still hold because the temp cwd
        happens to contain the tree. `under <tree>` is emitted only by the
        "INFO scanning N file(s) under <root>" line, which names the root the
        scan really used.

        `tree.resolve()`, not `tree`, and that is not a detail. On macOS the
        temp dir is handed out as `/var/folders/...` while `/var` is a symlink
        to `/private/var`, and the scanner resolves its root - so the path it
        prints is the `/private` one. The old bare-substring assertion was
        therefore satisfied for a SECOND accidental reason on top of the
        banner: the unresolved path is itself a substring of the resolved one.
        """
        tree = self.temp_root("selfscan")
        scripts = tree / ".claude" / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(SCRIPT_PATH, scripts / "leak-scan.py")
        shutil.copy2(EXAMPLE_PATH, scripts / "denylist.example.txt")
        (tree / "note.md").write_text(f"cd {OTHER_HOME}\n", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(scripts / "leak-scan.py")],
            capture_output=True, text=True, cwd=str(self.workdir))
        out = proc.stdout + proc.stderr
        self.assertIn(f"under {tree.resolve()}", out,
                      f"did not scan its own tree:\n{out}")
        self.assertIn("note.md", out)
        self.assertIn("home-path", out)
        self.assertEqual(proc.returncode, 1, out)


# --- 11. Read budgets: degrade loudly, never silently ------------------------

class TestHistoryBudget(ScannerTestCase):
    """A huge or oversized history must red-line, not quietly go unscanned.

    Both branches mutate to a SILENT PASS - the blob is skipped and nothing is
    printed - which is the one outcome this gate must never produce.
    """

    def deleted_blob_repo(self, content, name="big.md"):
        """One blob that lives in history only - added, then removed."""
        root = self.minimal_repo()
        (root / name).write_text(content, encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: add draft")
        git(root, "rm", "-q", "-f", name)
        git(root, "commit", "-q", "-m", "chore: drop draft")
        return root

    def test_truncated_history_red_lines_the_scan(self):
        # Distinct contents on purpose: identical files dedupe to ONE blob and
        # the truncation assertion needs two.
        root = self.minimal_repo()
        for n in range(2):
            (root / f"old-{n}.md").write_text(
                f"innocuous draft {n}\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: add drafts")
        git(root, "rm", "-q", "-f", "old-0.md", "old-1.md")
        git(root, "commit", "-q", "-m", "chore: drop drafts")
        self.assertEqual(len(self.history_only_blobs(root)), 2,
                         "fixture needs 2 history-only blobs")

        # NEGATIVE CONTROL: nothing here leaks, so the default limit passes.
        rc_default, out_default = self.run_scan(str(root))
        self.assertEqual(rc_default, 0, out_default)
        self.assertNotIn("truncated", out_default)

        rc, out = self.run_scan(str(root), "--history-limit", "1")
        self.assertEqual(rc, 1,
                         f"a partly-scanned history must not PASS:\n{out}")
        self.assertIn("truncated", out)
        self.assertIn("1 of 2", out)

    def test_oversized_history_blob_is_red_lined_not_skipped_silently(self):
        root = self.deleted_blob_repo(
            "meeting notes with Jane Doe\n" + "x" * 400 + "\n")
        self.patch_constant("MAX_BLOB_BYTES", 64)

        findings, problems, stats = self.history_findings(root)
        self.assertEqual(stats["skipped_large"], 1)
        self.assertNotIn(
            ("denylist-term", "Jane Doe"), pairs(findings),
            "an over-budget blob is never read, so the red line below is the "
            "only thing between it and a PASS")
        self.assertTrue(any("not scanned" in p for p in problems), problems)

        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1,
                         f"an unscanned history blob must not PASS:\n{out}")
        self.assertIn("not scanned", out)

    def test_history_blob_under_the_budget_is_scanned_and_reported(self):
        # NEGATIVE CONTROL: the size branch must not swallow ordinary blobs.
        root = self.deleted_blob_repo("meeting notes with Jane Doe\n")
        self.patch_constant("MAX_BLOB_BYTES", 64)

        findings, problems, stats = self.history_findings(root)
        self.assertEqual(stats["skipped_large"], 0)
        self.assertEqual(problems, ())
        self.assertIn(("denylist-term", "Jane Doe"), pairs(findings))


class TestWorktreeUnreadFiles(ScannerTestCase):
    """The worktree half of the same rule: nothing in the scan set goes unread.

    This is where it went wrong. The worktree path capped reads at 5MB and
    filed the skip under an INFO line that never reached the exit code, so a
    6MB note with a denylisted name on its last line printed "PASS - no
    findings, structure clean" while the identical text truncated to 4MB
    reported two leaks. The only variable was file size. The history path had
    red-lined its equivalent budget from the start - the two were inconsistent
    and the lenient one was this one.

    A template ships stubs, so nothing inside it trips a 5MB cap and the bug is
    invisible here. Every vault built from it trips it constantly: book
    transcripts, note-app exports and transcription output are routinely multi-MB,
    which made the gate quietest on exactly the files most likely to carry a
    name.
    """

    # Just past the read budget that used to exist. `patch_constant` cannot
    # stand in for this one: the claim under test is that NO read budget skips a
    # real file any more, so the fixture has to be genuinely bigger than the
    # budget that used to exist. About a second to scan - the slowest test in
    # this suite, and the only one that fails if the cap comes back.
    OVER_OLD_CAP = 5 * 1024 * 1024 + 4096

    def big_file_repo(self, last_line, name="transcript.md"):
        """A repo whose shipping set holds one file past the old 5MB cap.

        Left untracked rather than committed: `git ls-files --others` puts it in
        the shipping set either way, and committing 5MB of filler only buys
        zlib time. The interesting content is the LAST line, because a
        truncating read is exactly what misses it.
        """
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: init")
        path = root / name
        with path.open("w", encoding="utf-8") as handle:
            while handle.tell() < self.OVER_OLD_CAP:
                handle.write("wholly innocuous filler prose, repeated\n")
            handle.write(last_line + "\n")
        self.assertGreater(
            path.stat().st_size, 5 * 1024 * 1024,
            "fixture must exceed the budget it exists to disprove")
        return root

    def test_file_past_the_old_5mb_cap_is_streamed_and_scanned(self):
        root = self.big_file_repo("reviewed by Jane Doe")
        findings, unread = self.worktree_findings(root)
        self.assertEqual(unread, (), "a big text file is read, not skipped")
        self.assertIn(("denylist-term", "Jane Doe"), pairs(findings))

        rc, out = self.run_scan(str(root))
        self.assertEqual(
            rc, 1, f"a name on the last line of a big file must not PASS:\n{out}")
        self.assertIn("Jane Doe", out)

    def test_streamed_scan_agrees_with_in_memory_scan(self):
        """Streaming must not change WHAT is found, only how it is read.

        A file handle yields lines with their trailing newline; `scan_text()`
        strips them. Cheap to get wrong at a line boundary, and a silent
        difference between the two entry points is how one of them rots.
        """
        text = ("prose\n" + assign_bare("api_key", ANTHROPIC_KEY, sep="=")
                + "\nmet Jane Doe\n" + FAKE_HOME + "/notes\n")
        path = self.workdir / "sample.md"
        path.write_text(text, encoding="utf-8")

        streamed, reason = leak_scan.scan_file(path, "s", self.denylist)
        self.assertIsNone(reason)
        self.assertEqual(
            {(f.kind, f.value, f.line) for f in streamed},
            {(f.kind, f.value, f.line)
             for f in leak_scan.scan_text(text, "s", self.denylist)})
        self.assertTrue(streamed, "fixture found nothing, so it proves nothing")

    def test_binary_file_in_the_scan_set_red_lines(self):
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: init")
        # A name inside a binary is the honest case: this one is readable as
        # bytes, but a screenshot or a PDF carries it in pixels where no text
        # gate can reach it at all. Either way nobody read the file.
        (root / "export.dat").write_bytes(b"\x00\x01\x02Jane Doe\n")

        _findings, unread = self.worktree_findings(root)
        self.assertEqual(unread, (("export.dat", "binary"),))

        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, f"an unread binary must not PASS:\n{out}")
        self.assertIn("not text-scanned", out)
        self.assertIn("export.dat", out)

    def test_file_over_the_refusal_ceiling_red_lines(self):
        # MAX_FILE_BYTES is no longer a scan budget, but it is still a refusal
        # ceiling for pathological input, and crossing it must red-line rather
        # than repeat the original bug at a larger number.
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: init")
        (root / "huge.md").write_text(
            "wholly innocuous prose, comfortably past eight bytes\n",
            encoding="utf-8")
        self.patch_constant("MAX_FILE_BYTES", 8)

        findings, unread = self.worktree_findings(root)
        self.assertEqual(findings, (), "a refused file is not read at all")
        self.assertIn(("huge.md", "oversize"), unread)

        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, f"a refused file must not PASS:\n{out}")
        self.assertIn("refusal ceiling", out)

    def test_file_under_the_refusal_ceiling_is_scanned(self):
        # NEGATIVE CONTROL: the ceiling must not swallow ordinary files, or the
        # fix would be "always fail", which is the same as having no gate.
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: init")
        (root / "note.md").write_text("met Jane Doe\n", encoding="utf-8")
        self.patch_constant("MAX_FILE_BYTES", 1024)

        findings, unread = self.worktree_findings(root)
        self.assertEqual(unread, ())
        self.assertIn(("denylist-term", "Jane Doe"), pairs(findings))

    def test_vanished_file_is_reported_unreadable_not_silently_dropped(self):
        # A file listed by `git ls-files` and gone by the time it is opened.
        # Asserted at the scan_files() level rather than through main(),
        # because shipping_set() re-checks is_file() and would drop it before
        # the scan - the race it models happens between those two moments.
        # Deliberately not tested via chmod: this suite must never skip, and a
        # permissions fixture is a no-op when the tests run as root.
        root = self.temp_root("gone")
        findings, unread = leak_scan.scan_files(
            root, {"vanished.md"}, self.denylist)
        self.assertEqual(findings, ())
        self.assertEqual(unread, (("vanished.md", "unreadable"),))
        self.assertTrue(
            any("unreadable" in p for p in leak_scan.unread_problems(unread)))


# --- 12. Report rendering: the gate must not leak what it catches -----------

class TestSecretPreviewMasking(ScannerTestCase):
    """`preview()` must not copy a detected secret into stdout.

    Nothing here is about a false negative: the exit code is still 1. It is
    about the gate copying the credential it just caught into terminal
    scrollback and a CI log that is often more public than the repo.
    """

    def test_every_retained_secret_kind_is_masked(self):
        for kind in leak_scan.SECRET_KINDS:
            with self.subTest(kind=kind):
                rendered = leak_scan.preview(kind, "TAILTAILTAILTAILTAIL")
                self.assertIn("masked", rendered)
                self.assertNotIn("TAILTAILTAILTAILTAIL", rendered)

    def test_non_secret_kinds_are_shown_in_full(self):
        # NEGATIVE CONTROL: masking everything makes the report unusable - a
        # denylist hit has to name the term a human must go and remove.
        self.assertEqual(leak_scan.preview("denylist-term", "Acme Corp"),
                         "Acme Corp")
        self.assertEqual(leak_scan.preview("denylist-name", "Jane"), "Jane")

    def test_scan_output_never_contains_the_raw_secret(self):
        root = self.minimal_repo()
        (root / "conf.md").write_text(
            assign_bare("ANTHROPIC_API_KEY", ANTHROPIC_KEY, sep="=") + "\n",
            encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chore: tidy")

        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, out)
        self.assertIn("api-token", out)
        self.assertNotIn(ANTHROPIC_KEY, out,
                         "the gate reprinted the secret it caught")
        self.assertIn("masked", out)


# --- 13. Crash resistance ----------------------------------------------------

class TestCrashResistance(ScannerTestCase):
    """None of these may traceback. A gate that crashes is a gate nobody runs."""

    def test_empty_directory(self):
        rc, out = self.run_scan(str(self.temp_root("empty")))
        self.assertEqual(rc, 0, out)
        self.assertIn("not a git repo", out)
        self.assertNotIn("Traceback", out)

    def test_binary_file_outside_a_repo_does_not_crash_the_walk(self):
        # Crash resistance only - that an unread binary RED-LINES is
        # TestWorktreeUnreadFiles' subject. This assertion was the inverse
        # until 2026-08-06: it pinned the old advisory behaviour (INFO line,
        # exit 0) and carried a note saying that if this copy ever adopted the
        # sibling's structural treatment, this was the assertion to flip. It
        # was flipped, deliberately, when the 5MB read cap came out - an unread
        # file in the shipping set is a silent PASS, which is the one outcome
        # this gate must never produce.
        root = self.temp_root("bin")
        (root / "blob.dat").write_bytes(b"\x00\x01\x02Jane Doe\n")
        _findings, unread = leak_scan.scan_files(
            root, leak_scan.walk_all_files(root), self.denylist)
        self.assertEqual(unread, (("blob.dat", "binary"),))
        rc, out = self.run_scan(str(root))
        self.assertIn("not text-scanned", out)
        self.assertNotIn("Traceback", out)
        self.assertEqual(rc, 1, out)

    def test_nonexistent_path_exits_2(self):
        missing = self.workdir / "nope" / "deeper"
        rc, out = self.run_scan(str(missing))
        self.assertEqual(rc, 2)
        self.assertIn("not a directory", out)

    def test_file_instead_of_directory_exits_2(self):
        target = self.workdir / "note.md"
        target.write_text("x", encoding="utf-8")
        self.assertEqual(self.run_scan(str(target))[0], 2)

    def test_bad_flag_exits_2(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_scan("--no-such-flag")
        self.assertEqual(ctx.exception.code, 2)

    def test_non_git_directory_with_content(self):
        root = self.temp_root("plain")
        (root / "note.md").write_text("clean prose\n", encoding="utf-8")
        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 0, out)
        self.assertIn("history scan skipped", out)

    def test_no_history_flag_skips_the_history_pass_loudly(self):
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "docs: notes from the Acme Corp offsite")
        rc, out = self.run_scan(str(root), "--no-history")
        self.assertIn("history scan skipped", out)
        self.assertEqual(rc, 0, out)
        # NEGATIVE CONTROL: the same repo red-lines with history enabled, so
        # the flag is a deliberate choice and not a no-op.
        self.assertEqual(self.run_scan(str(root))[0], 1)

    def test_repo_with_no_commits(self):
        root = self.temp_root("bare")
        git(root, "init", "-q")
        (root / "note.md").write_text("clean prose\n", encoding="utf-8")
        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Traceback", out)

    def test_commit_body_containing_control_bytes_is_scanned_whole(self):
        """A literal record separator in a commit body must not truncate it.

        This was a real silent-PASS bug, fixed 2026-07-31. `scan_commit_metadata()`
        used to ask git for `...%s%x1f%b%x1e` and split the stream on \\x1e, so a
        body containing that byte split one commit into two records - the second
        too short to parse and therefore dropped, taking everything after the
        control byte with it, unscanned. A commit message is attacker-free but
        not author-free: paste a chunk of terminal output into a body and this
        is reachable by accident. The result was the failure mode this gate must
        never produce - a leak present, unscanned, and reported as PASS.

        Fixed by asking git for NUL-separated records (`git log --all -z`) and
        splitting on NUL, which a commit message cannot contain, so the
        separator is safe by construction.

        This test carried an `expectedFailure` marker while the bug was open.
        That was deliberate: `unittest` reports a passing expectedFailure as an
        UNEXPECTED SUCCESS and `wasSuccessful()` returns False, so the build went
        red the moment the fix landed and stayed red until the marker was
        removed. The stopgap cleared itself rather than rotting into a
        permanently-ignored red test. Keep the test; it is now a regression
        guard, and it fails again if anyone reintroduces an in-format separator.
        """
        root = self.minimal_repo()
        git(root, "commit", "-q", "-m", "chore: tidy",
            "-m", "before \x1e after: Acme Corp offsite")
        history, _p, _s = self.history_findings(root)
        self.assertIn(
            ("denylist-term", "Acme Corp"), pairs(history),
            "everything after the control byte went unscanned - see this "
            "test's docstring; the fix is in scan_commit_metadata(), not here")


# --- 13b. Acknowledged findings ----------------------------------------------

class TestAcceptedFindings(ScannerTestCase):
    """Suppression by location, and the guarantees that keep it honest.

    A gate with no way to record "I read this and it is fine" sits permanently
    red on any repo whose pushed history holds one accepted fact, and a gate
    that always fails is one that gets ignored. So suppression exists - and
    every property below is what stops it becoming a rubber stamp.
    """

    def leaking_repo(self):
        """A repo whose worktree holds one denylist hit, committed."""
        root = self.minimal_repo()
        (root / "note.md").write_text("written by Jane Doe\n", encoding="utf-8")
        git(root, "add", "note.md")
        git(root, "commit", "-qm", "init")
        return root

    def accept(self, root, *fingerprints):
        path = root / leak_scan.ACCEPTED_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# signed off in the fixture\n" + "\n".join(fingerprints) + "\n",
            encoding="utf-8")

    def test_absent_acceptance_file_suppresses_nothing(self):
        """The default is no suppression - the file is opt-in, not opt-out."""
        root = self.leaking_repo()
        self.assertEqual(
            leak_scan.load_accepted(root / leak_scan.ACCEPTED_REL), frozenset())
        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, out)
        self.assertIn("denylist-term", out)

    def test_a_matching_fingerprint_suppresses_the_finding(self):
        root = self.leaking_repo()
        self.accept(root, "note.md:1:denylist-term", "note.md:1:denylist-name")
        _rc, out = self.run_scan(str(root))
        self.assertNotIn("LEAK    note.md", out)

    def test_suppression_is_always_reported(self):
        """Silent suppression is indistinguishable from no finding at all."""
        root = self.leaking_repo()
        self.accept(root, "note.md:1:denylist-term", "note.md:1:denylist-name")
        _rc, out = self.run_scan(str(root))
        self.assertIn("suppressed by", out)
        self.assertIn(leak_scan.ACCEPTED_REL, out)

    def test_stale_entries_are_reported(self):
        """A list that accumulates dead entries drifts into a blanket."""
        root = self.leaking_repo()
        self.accept(root, "gone.md@deadbeef:9:home-path")
        _rc, out = self.run_scan(str(root))
        self.assertIn("stale entry", out)
        self.assertIn("gone.md@deadbeef:9:home-path", out)

    def test_a_fingerprint_does_not_suppress_a_different_kind(self):
        """Accepting one rule on a line must not silence every rule on it."""
        root = self.leaking_repo()
        self.accept(root, "note.md:1:home-path")
        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, out)
        self.assertIn("denylist-term", out)

    def test_a_fingerprint_does_not_suppress_a_different_line(self):
        """Line numbers shift as a file is edited; the acceptance must lapse.

        Failing OPEN here would be the dangerous direction - an edit that moved
        a leak would inherit the sign-off given to whatever used to be there.
        """
        root = self.leaking_repo()
        (root / "note.md").write_text(
            "padding\nwritten by Jane Doe\n", encoding="utf-8")
        self.accept(root, "note.md:1:denylist-term")
        rc, out = self.run_scan(str(root))
        self.assertEqual(rc, 1, out)

    def test_comments_and_blank_lines_are_ignored(self):
        path = self.workdir / "accepted.txt"
        path.write_text(
            "# a comment\n\n  \na.md:1:email\n  b.md:2:home-path  \n",
            encoding="utf-8")
        self.assertEqual(
            leak_scan.load_accepted(path), {"a.md:1:email", "b.md:2:home-path"})

    def test_a_path_containing_a_colon_still_parses(self):
        """`where` is everything before the LAST two colons, not the first."""
        finding = leak_scan.Finding("odd:name.md@abc1234", 7, "email", "x", 1)
        self.assertEqual(
            leak_scan.fingerprint(finding), "odd:name.md@abc1234:7:email")


class TestExemptValues(ScannerTestCase):
    """Suppression by value, for what is public by construction.

    Its companion is the acceptance file. The split matters: a location
    fingerprint for a value that recurs forever needs re-editing every time the
    file changes, and a list re-edited that often stops being read.
    """

    def denylist_with_exempt(self, *values):
        path = self.workdir / "exempt-denylist.txt"
        path.write_text(
            FIXTURE_DENYLIST_TEXT + "\n[exempt]\n" + "\n".join(values) + "\n",
            encoding="utf-8")
        denylist, warnings = leak_scan.load_denylist(path)
        self.assertEqual(warnings, ())
        return denylist

    def kinds(self, denylist, text):
        return {k for k, _v in leak_scan.scan_line(text, denylist, True)}

    def test_an_exempt_value_is_dropped(self):
        """PERSONAL_EMAIL, not an example.com address - the built-in
        EXEMPT_EMAIL_DOMAINS list already silences those, so a fixture using one
        would pass whether or not [exempt] worked at all."""
        line = "contact: " + PERSONAL_EMAIL
        unrelated = "nobody" + "@" + "nowhere.test"
        self.assertIn("email", self.kinds(self.denylist_with_exempt(unrelated), line))
        self.assertNotIn(
            "email", self.kinds(self.denylist_with_exempt(PERSONAL_EMAIL), line))

    def test_matching_is_case_insensitive(self):
        denylist = self.denylist_with_exempt(PERSONAL_EMAIL)
        self.assertNotIn("email", self.kinds(denylist, PERSONAL_EMAIL.upper()))

    def test_exemption_is_exact_not_substring(self):
        """A prefix must not silence a longer, different address."""
        denylist = self.denylist_with_exempt(PERSONAL_EMAIL)
        self.assertIn(
            "email", self.kinds(denylist, PERSONAL_EMAIL + ".attacker" + ".test"))

    def test_exempt_does_not_touch_denylist_terms(self):
        """[exempt] filters the REGEX battery only - names still fire."""
        denylist = self.denylist_with_exempt("Jane Doe")
        self.assertIn("denylist-term", self.kinds(denylist, "by Jane Doe"))

    def test_an_unknown_section_is_still_rejected(self):
        path = self.workdir / "bad.txt"
        path.write_text("[nonsense]\nfoo\n", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            leak_scan.load_denylist(path)
        self.assertIn("[exempt]", str(caught.exception))

    def test_empty_denylist_has_an_empty_exempt_set(self):
        self.assertEqual(leak_scan.EMPTY_DENYLIST.exempt, frozenset())


# --- 14. Suite hygiene -------------------------------------------------------

class TestSuiteHygiene(unittest.TestCase):
    """The gate is not exempt from itself, and neither is its test suite.

    Both files ship inside the tree the gate scans, so a fixture written out
    verbatim would make the gate fail on its own source, permanently - and
    "add an allowlist entry" is the wrong fix, because an allowlist is a hole
    nobody remembers opening. Reshape the fixture instead.
    """

    def scan_own_source(self, path):
        text = path.read_text(encoding="utf-8")
        return leak_scan.scan_text(text, path.name, leak_scan.EMPTY_DENYLIST)

    def test_this_suite_does_not_trip_the_gate_it_tests(self):
        findings = self.scan_own_source(pathlib.Path(__file__).resolve())
        self.assertEqual(
            pairs(findings), set(),
            "a fixture in this file now matches a rule on a single source "
            "line - assemble it from fragments (see the FIXTURES section) "
            "instead, or the gate red-lines its own test suite")

    def test_the_scanner_does_not_trip_the_gate_it_implements(self):
        # The same defect, one file over: an example pasted into a docstring
        # that happens to match a rule. It shipped once already.
        self.assertEqual(pairs(self.scan_own_source(SCRIPT_PATH)), set())


if __name__ == "__main__":
    unittest.main()
