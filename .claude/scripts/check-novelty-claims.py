#!/usr/bin/env python3
"""NOV002 — verify novelty claims against the vault as it stood when written.

CI-only, git-aware, diff-scoped. The companion to NOV001 in `wiki-lint.py`,
covering the half NOV001 structurally cannot.

WHY TWO RULES

NOV001 is content-keyed: it reads the tree as it stands and asks "is this
claim true *now*". Correct for synthesis pages, whose claims are meant to stay
true. Wrong for `wiki/log.md`, which is a dated record — "no prior reference
to X" was true the day it was written and stays in the file after that same
ingest creates X. Content-keying the log produced a real false positive: a
line claiming no prior reference to four books was reported as an unfounded
claim about `Steady Finish`, a page named in a different clause entirely.

So NOV001 skips `wiki/log.md`. Which left the incident that started all this
uncovered, because the false claim lived exactly there. On 2026-08-27 a
three-book ingest wrote into the log:

    - **Created**: … [[entities/ivo-zembla]] (first vault mention — no prior
      reference to Zembla or Tarrow anywhere in `wiki/`).

Zembla had been in the vault since 2026-04-28, live in seven pages, as
co-author of *The Lattice Firm*. The cause was not
judgement: `grep -rn "Zembla" wiki/ --include=*.md` **dies** in zsh — the
unquoted `*.md` is glob-expanded before grep runs — so it printed nothing, and
the empty output was read as "term absent from the vault".

WHAT THIS RULE ASKS INSTEAD

Not "is the claim true now" but **"was it true when it was committed"**. Take
only lines ADDED since a base SHA, and search the vault *at that base*. Both
cases then resolve correctly and permanently:

  * the Zembla claim FAILS — `book-management-essentials.md` held "Ivo Zembla" at
    base, so the claim was false the moment it was written;
  * the four-books claim PASSES — those pages did not exist at base, so the
    claim was true when written, and keeps passing on every later run.

Pages created in the same commit need no exclusion rule: they are absent from
the base tree and so cannot be found there. That property falls out of
diff-scoping rather than being a special case anyone has to maintain.

Shape borrowed from `check-date-updated.py` (FM007), the vault's other
CI-only, base-SHA-diffing gate.

Stdlib-only. Requires git on PATH.

Usage:
  python3 .claude/scripts/check-novelty-claims.py --base <sha>
  python3 .claude/scripts/check-novelty-claims.py --base <sha> --gh-annotations
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# Only vault synthesis is in scope. `raw/` is immutable source — a name in a
# book transcript is not a claim the vault is making.
SCOPE_PREFIX = "wiki/"

# Kept deliberately in sync with NOVELTY_PHRASES in wiki-lint.py. Two rules,
# one vocabulary: a phrasing that trips one should trip the other.
NOVELTY_PHRASES = (
    "first vault mention",
    "first mention in the vault",
    "first time in the vault",
    "no prior reference",
    "no prior mention",
    "not previously in the vault",
    "new to the vault",
    "first appearance in the vault",
)

# A log entry may RETRACT a past novelty claim — wiki/log.md now contains
# exactly such a retraction, describing this very incident. Look back this far
# for a negation before treating a phrase hit as an assertion.
NEGATION_WINDOW = 80
NEGATIONS = (
    "not", "n't", "never", "no longer", "wrongly", "falsely",
    "incorrectly", "mistakenly", "erroneously", "wasn", "isn",
)

# Words that can open a capitalised run without being part of a name.
STOPWORDS = {
    "The", "A", "An", "This", "That", "These", "Those", "It", "We", "I",
    "And", "Or", "But", "In", "On", "At", "To", "Of", "For", "From",
}


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check)


def added_lines(base: str) -> list[tuple[str, int, str]]:
    """(path, new-file line number, text) for every line ADDED since base.

    `--unified=0` keeps the hunks tight so the line numbers stay exact; without
    it the context lines have to be counted and skipped by hand.
    """
    proc = run_git(["diff", "--unified=0", base, "HEAD", "--", SCOPE_PREFIX])
    out: list[tuple[str, int, str]] = []
    path: str | None = None
    lineno = 0
    for line in proc.stdout.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            lineno = int(m.group(1)) if m else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if path and path.startswith(SCOPE_PREFIX):
                out.append((path, lineno, line[1:]))
            lineno += 1
    return out


def is_negated(line_lower: str, pos: int) -> bool:
    window = line_lower[max(0, pos - NEGATION_WINDOW):pos]
    return any(neg in window for neg in NEGATIONS)


def clause_around(line: str, pos: int) -> str:
    """The claim's own clause.

    Load-bearing. A real log line reads:

        checked existing coverage (no prior references to *Slow Decline*);
        read [[topics/steady-finish]] for landing-page state

    Taking the whole line pulls `steady-finish` out of a different clause
    and reports it as the unfounded claim — which is what the content-keyed
    rule did before clause-scoping was added.
    """
    starts = [0] + [m.end() for m in re.finditer(r"[;·]", line)]
    ends = [m.start() for m in re.finditer(r"[;·]", line)] + [len(line)]
    for s, e in zip(starts, ends):
        if s <= pos < e:
            return line[s:e]
    return line


def extract_subjects(line: str, pos: int, phrase: str) -> list[str]:
    """What the novelty claim is about, best-effort and clause-confined.

    Four sources, in descending confidence:
      1. the grammatical object — "no prior reference **to** Zembla";
      2. wikilink display text, or the de-slugified leaf of a bare link;
      3. *italicised* spans (how the vault names books and terms);
      4. "quoted" spans.
    """
    clause = clause_around(line, pos)
    subjects: list[str] = []

    tail = line[pos + len(phrase):pos + len(phrase) + 140]
    m = re.match(r"\s*(?:to|of|for)\s+(.+)", tail, re.IGNORECASE)
    if m:
        obj = m.group(1)
        # Stop at the first structural break so we take the object, not the
        # rest of the sentence.
        obj = re.split(r"[;,·)(]|\s+(?:anywhere|in the vault|in `)", obj)[0]
        subjects += [s.strip() for s in re.split(r"\s+or\s+|\s+/\s+", obj)]

    for raw in re.findall(r"\[\[([^\]]+)\]\]", clause):
        target, _, display = raw.partition("|")
        if display.strip():
            subjects.append(display.strip())
        else:
            leaf = target.strip().rstrip("/").split("/")[-1].split("#")[0]
            subjects.append(leaf.replace("-", " ").replace("_", " "))

    subjects += [s.strip() for s in re.findall(r"\*([^*\n]{2,60})\*", clause)]
    subjects += [s.strip() for s in re.findall(r"[“\"]([^”\"\n]{2,60})[”\"]", clause)]

    cleaned: list[str] = []
    for s in subjects:
        s = s.strip(" .`*_—-")
        s = re.sub(r"\s+", " ", s)
        if len(s) < 2 or s in STOPWORDS or s.lower() in {"the vault", "wiki"}:
            continue
        cleaned.append(s)
    return list(dict.fromkeys(cleaned))


def mentioned_at_base(subject: str, base: str) -> list[str]:
    """Files under wiki/ that mentioned `subject` in the tree at `base`.

    `-w` gives word boundaries — without them a two-letter subject matches
    inside longer words and the rule becomes unusable. `-F` keeps a subject
    containing regex metacharacters from being interpreted as a pattern.
    """
    proc = run_git(
        ["grep", "-l", "-i", "-w", "-F", "-e", subject, base, "--", f"{SCOPE_PREFIX}**.md"],
        check=False,
    )
    if proc.returncode not in (0, 1):
        return []
    out = []
    for line in proc.stdout.splitlines():
        # `git grep <rev>` prefixes matches with "<rev>:".
        out.append(line.split(":", 1)[1] if ":" in line else line)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Base git SHA to diff against")
    parser.add_argument(
        "--gh-annotations", action="store_true",
        help="Emit GitHub Actions annotation syntax",
    )
    args = parser.parse_args()

    # A gate that cannot resolve its base must fail loudly. Exiting 0 here
    # would be the same silent-pass failure this rule exists to prevent.
    probe = run_git(["rev-parse", "--verify", f"{args.base}^{{commit}}"], check=False)
    if probe.returncode != 0:
        print(f"ERROR: cannot resolve base ref '{args.base}'", file=sys.stderr)
        return 2

    findings: list[tuple[str, int, str, str, list[str]]] = []
    for path, lineno, line in added_lines(args.base):
        line_lower = line.lower()
        for phrase in NOVELTY_PHRASES:
            pos = line_lower.find(phrase)
            if pos < 0 or is_negated(line_lower, pos):
                continue
            for subject in extract_subjects(line, pos, phrase):
                priors = mentioned_at_base(subject, args.base)
                if priors:
                    findings.append((path, lineno, phrase, subject, priors))
            break

    if not findings:
        # Deliberately does NOT print the rule code: a clean run must be
        # distinguishable from a finding by a plain grep for "NOV002".
        print("No unfounded novelty claims added.")
        return 0

    for path, lineno, phrase, subject, priors in findings:
        shown = ", ".join(priors[:3])
        more = f" (+{len(priors) - 3} more)" if len(priors) > 3 else ""
        msg = (
            f'Novelty claim "{phrase}" about `{subject}`, but it was already in '
            f"the vault at the base commit: {shown}{more}"
        )
        if args.gh_annotations:
            print(f"::error file={path},line={lineno},title=NOV002::{msg}")
        else:
            print(f"ERROR {path}:{lineno}  NOV002  {msg}")

    print(
        f"\n{len(findings)} unfounded novelty claim(s). A search that returns "
        "nothing is only a finding if the search actually ran — re-check with "
        "`qmd query` scoped to the wiki collection before asserting novelty.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
