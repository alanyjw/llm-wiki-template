#!/usr/bin/env python3
"""Unit tests for .claude/scripts/wiki-lint.py.

Scope, deliberately narrow: WIKI002's attachment exemption and the
`attachment_extensions` config knob that controls it. This suite is not a
general test of the linter — it exists because that exemption is the one lint
rule whose behaviour DIFFERS between a developer's disk and CI, which is
precisely the shape of bug a human cannot catch by running the tool locally.

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

import json
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
