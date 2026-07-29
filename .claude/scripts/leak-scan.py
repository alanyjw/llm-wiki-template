#!/usr/bin/env python3
"""leak-scan.py - privacy gate for publishing a sanitized copy of a private vault.

Run this before every public push of a vault built from this template. It scans
a tree - worktree *and* git history - for personal data and machine-local
artifacts, and exits non-zero unless the tree is clean AND the gate is
configured.

Why the mechanism ships when the denylist cannot
------------------------------------------------
A denylist enumerates real people, employers, handles and home paths, so it can
never live in a public repo. The *mechanism* has no such problem. This script is
the mechanism only: it loads its denylist at runtime from
`.claude/scripts/denylist.txt`, which is gitignored. Copy
`denylist.example.txt` to `denylist.txt`, fill it in, and the gate becomes
runnable. Without that file the name-based checks are DISABLED and the script
exits non-zero, so an unconfigured gate can never be mistaken for a passing one.

What it checks
--------------
1. Denylist names - requires `denylist.txt`.
   * `[words]`      bare proper nouns, matched CASE-SENSITIVELY on word
                    boundaries, so `Mark`, `Will` and `Grace` do not fire on the
                    ordinary English words. A denylist that false-positives on
                    every third file gets ignored, which is the same as not
                    having one.
   * `[substrings]` full names, employers, handles, paths and side-repo names,
                    matched case-INSENSITIVELY as substrings - distinctive
                    enough that a substring hit is almost always real.
2. Structural and regex checks - always on, no personal data required.
   Absolute home paths, email addresses, long hex blobs, API-key-shaped tokens,
   private-key headers, document/calendar URLs carrying an id, machine-local
   artifacts, stray binaries under `assets/`, and a per-directory ceiling on
   content files.
3. Git history, not just the worktree. A name committed and later deleted is
   still readable in the commit that introduced it, and public forever once
   pushed. Blobs reachable from any ref but absent from HEAD are scanned
   separately, together with commit author names, emails, subjects, bodies and
   ref names. Outside a git repo the history pass is skipped with a warning.

Scope
-----
By default only the SHIPPING SET is scanned - `git ls-files --cached --others
--exclude-standard`, i.e. what a push would actually publish. Machine-local
junk that is already gitignored (`.qmd/`, `__pycache__/`, `node_modules/`)
therefore cannot red-line the gate forever. `--all-files` scans everything.

Deliberate exemptions live next to the checks they belong to, each with the
reason in a comment - a gate that cries wolf is a gate you learn to ignore.

Usage
-----
  python3 .claude/scripts/leak-scan.py                     # scan this repo
  python3 .claude/scripts/leak-scan.py ../public-repo      # assembled tree
  python3 .claude/scripts/leak-scan.py ../public-repo --expect-single-commit
  python3 .claude/scripts/leak-scan.py --all-files --no-history

Exit codes
----------
  0  clean, and the gate was configured
  1  findings - leaks and/or structural problems
  2  bad invocation - missing directory, malformed denylist
  3  no denylist.txt AND nothing else fired - name checks were DISABLED

Checked in that order, so they are NOT independent: an unconfigured run that
also has findings exits 1, never 3, because "do not publish" is the more urgent
fact. The missing-denylist banner prints in both cases. Wrapper scripts should
branch on `!= 0` ("do not publish"), never on `== 3` ("unconfigured") - the
first run on a fresh clone is usually the case where those two diverge.

Python 3 standard library only. Deliberately one self-contained file so it can
be copied into a private vault's toolchain without dragging a package along.
"""

import argparse
import re
import subprocess
import sys
from collections import namedtuple
from functools import lru_cache
from pathlib import Path

# --- Configuration -----------------------------------------------------------

DENYLIST_REL = ".claude/scripts/denylist.txt"
EXAMPLE_REL = ".claude/scripts/denylist.example.txt"

# Never opened at all: its entire content is the search terms themselves.
NEVER_SCAN = frozenset({DENYLIST_REL})

# Exempt from the built-in regex checks only - the example file's fake home
# path is intentional. Still checked against the denylist, so real names pasted
# into the wrong file are caught. (This script is NOT exempt: a home path in a
# comment here would be reported, which is the behaviour you want.)
REGEX_EXEMPT = frozenset({DENYLIST_REL, EXAMPLE_REL})

# Skipped when walking with --all-files (outside a git repo, or on request).
WALK_SKIP_DIRS = frozenset({".git", "node_modules"})

# Present in the shipping set => the tree is not publishable.
FORBIDDEN_PATHS = (
    ".claude/settings.local.json",
    ".claude/worktrees",
    ".claude/scheduled_tasks.lock",
    ".qmd",
    "__pycache__",
    DENYLIST_REL,
)

# Content directories carry the "one stub per page type, not fifty real notes"
# assertion. An *exact* expected count breaks the moment the template grows a
# second example page, so the durable form is a ceiling plus a printed census
# you eyeball - counting files is what catches the "I forgot that folder
# existed" mistake a text scan never will.
WIKI_CONTENT_DIRS = frozenset({
    "wiki/entities", "wiki/topics", "wiki/sources",
    "wiki/insights", "wiki/plans", "wiki/projects",
})

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_BLOB_BYTES = 1 * 1024 * 1024
BLOB_BATCH = 128
DEFAULT_HISTORY_LIMIT = 20000
DEFAULT_MAX_CONTENT_FILES = 5

# --- Built-in checks (no personal data required, therefore shippable) --------

# `uses: owner/repo@<40 hex>  # v5` - a SHA-pinned GitHub Action. Pinning an
# action to a commit SHA is a supply-chain best practice and the SHA is public,
# so a bare long-hex rule flags every hardened workflow in the repo. Captured
# here so those SHAs can be exempted from long-hex on that same line.
ACTION_PIN_RE = re.compile(
    r"uses:\s*[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+@([0-9a-fA-F]{40})\b")

PLACEHOLDER_RE = re.compile(
    r"(?i)your[_-]?|example|placeholder|redacted|changeme|xxxx|dummy|fake")

BUILTIN_CHECKS = (
    ("home-path", re.compile(r"/(?:Users|home)/([A-Za-z0-9._-]{2,})")),
    ("email", re.compile(
        r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.([A-Za-z]{2,24}))\b")),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("api-token", re.compile(r"\b(?:sk|pk)-(?:ant-)?[A-Za-z0-9_-]{20,}")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("google-api-key", re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")),
    ("jwt", re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+")),
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("secret-assignment", re.compile(
        r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*"
        r"['\"]?([A-Za-z0-9_\-]{16,})")),
    ("doc-url", re.compile(
        r"(?:docs|drive)\.google\.com/[A-Za-z0-9/_-]*?/d/([A-Za-z0-9_-]{20,})")),
    ("calendar-url", re.compile(
        r"calendar\.google\.com/[^\s)\"']*(?:cid|src)=[A-Za-z0-9%._@-]{16,}")),
    ("long-hex", re.compile(r"\b[0-9a-fA-F]{32,}\b")),
)

# Service accounts and shared dirs - a home path naming one of these leaks
# nothing about a person.
EXEMPT_HOME_USERS = frozenset({
    "runner", "root", "ubuntu", "user", "shared", "vscode", "node",
    "admin", "ci", "git", "linuxbrew", "docker", "home",
})

EXEMPT_EMAIL_DOMAINS = frozenset({
    "example.com", "example.org", "example.net",
    "noreply.github.com", "users.noreply.github.com", "localhost",
})

EXEMPT_EMAIL_LOCALS = frozenset({"noreply", "no-reply", "donotreply"})

# `sprite@2x.png` parses as an address unless file extensions are excluded.
FILE_EXTENSIONS = frozenset({
    "png", "jpg", "jpeg", "gif", "webp", "svg", "pdf", "md", "txt", "py",
    "sh", "js", "ts", "json", "yml", "yaml", "html", "css", "toml", "lock",
})

# Values worth masking in output: a CI log should not reprint the secret.
SECRET_KINDS = frozenset({
    "aws-key", "api-token", "github-token", "slack-token", "google-api-key",
    "jwt", "private-key", "secret-assignment",
})

Denylist = namedtuple("Denylist", "words substrings")
Finding = namedtuple("Finding", "where line kind value count")

EMPTY_DENYLIST = Denylist((), ())


# --- Denylist loading --------------------------------------------------------

def load_denylist(path):
    """Parse a denylist file into a Denylist. Raises ValueError on bad syntax.

    Format: `#` full-line comments, `[words]` / `[substrings]` section headers,
    one term per line. Inline comments are NOT supported - a `#` mid-line is
    part of the term, because handles and paths legitimately contain one.
    """
    words, subs, section = [], [], None
    warnings = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            if section not in ("words", "substrings"):
                raise ValueError(
                    f"{path}:{lineno}: unknown section [{section}] "
                    f"- expected [words] or [substrings]")
            continue
        if section is None:
            raise ValueError(
                f"{path}:{lineno}: term {line!r} appears before any "
                f"[words] / [substrings] section header")
        if len(line) < 2:
            raise ValueError(
                f"{path}:{lineno}: term {line!r} is too short - a one-character "
                f"term matches everything and makes the gate useless")
        if section == "words":
            if any(ch.isspace() for ch in line):
                warnings.append(
                    f"{path}:{lineno}: {line!r} contains whitespace; multi-word "
                    f"terms belong in [substrings]")
            words.append(line)
        else:
            subs.append(line)
    # dict.fromkeys dedups while preserving first-seen order.
    return Denylist(tuple(dict.fromkeys(words)), tuple(dict.fromkeys(subs))), tuple(warnings)


@lru_cache(maxsize=512)
def word_pattern(term):
    """Case-SENSITIVE, boundary-anchored matcher for a bare proper noun.

    Lookarounds rather than \\b so terms that start or end in punctuation
    (`O'Brien`, `Acme.`) still anchor correctly.
    """
    return re.compile(
        r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])")


# --- Text scanning -----------------------------------------------------------

def builtin_hits(line):
    """Yield (kind, value) for built-in regex checks on one line."""
    pinned = frozenset(m.group(1).lower() for m in ACTION_PIN_RE.finditer(line))
    for kind, pattern in BUILTIN_CHECKS:
        for match in pattern.finditer(line):
            if is_exempt(kind, match, pinned):
                continue
            yield kind, match.group(0)


def is_exempt(kind, match, pinned):
    """True when a built-in regex hit is a known-legitimate pattern.

    Every exemption here is a false positive the naive rule produced on a real
    repo. Add to it only with the reason written down.
    """
    value = match.group(0)
    if kind == "long-hex":
        low = value.lower()
        # Git's all-zero null SHA - what a pre-push hook passes to mean "no
        # such ref". 40 hex characters, and not a secret. Plus SHA-pinned
        # GitHub Actions appearing on this same line.
        return set(low) == {"0"} or low in pinned
    if kind == "home-path":
        return match.group(1).lower() in EXEMPT_HOME_USERS
    if kind == "email":
        local, domain, tld = match.group(1), match.group(2), match.group(3)
        return (domain.lower() in EXEMPT_EMAIL_DOMAINS
                or local.lower() in EXEMPT_EMAIL_LOCALS
                or tld.lower() in FILE_EXTENSIONS)
    if kind == "secret-assignment":
        return bool(PLACEHOLDER_RE.search(match.group(1)))
    return False


def scan_line(line, denylist, use_regex):
    """Yield (kind, value) findings for one line of text."""
    for term in denylist.words:
        if word_pattern(term).search(line):
            yield "denylist-name", term
    low = line.lower()
    for term in denylist.substrings:
        if term.lower() in low:
            yield "denylist-term", term
    if use_regex:
        yield from builtin_hits(line)


def scan_text(text, where, denylist, use_regex=True):
    """Return a tuple of Findings for a whole document.

    One Finding per (kind, value) pair per document, carrying the first line it
    appeared on and an occurrence count - repeating the same name forty times
    buries the other findings.
    """
    seen = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        for kind, value in scan_line(line, denylist, use_regex):
            key = (kind, value)
            first, count = seen.get(key, (lineno, 0))
            seen[key] = (first, count + 1)
    return tuple(
        Finding(where, first, kind, value, count)
        for (kind, value), (first, count) in seen.items())


def read_text_file(path):
    """Return decoded text, or None for binary / oversized / unreadable files."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def scan_files(root, rel_paths, denylist):
    """Scan a set of repo-relative paths. Returns (findings, skipped)."""
    findings, skipped = [], []
    for rel in sorted(rel_paths):
        if rel in NEVER_SCAN:
            continue
        text = read_text_file(root / rel)
        if text is None:
            skipped.append(rel)
            continue
        findings.extend(
            scan_text(text, rel, denylist, use_regex=rel not in REGEX_EXEMPT))
    return tuple(findings), tuple(skipped)


# --- File selection ----------------------------------------------------------

def run_git(root, args, stdin_data=None, binary=False):
    """Run a git command, returning stdout (str or bytes) or None on failure."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            input=stdin_data, capture_output=True, check=False)
    except (OSError, ValueError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")


def is_git_repo(root):
    out = run_git(root, ["rev-parse", "--is-inside-work-tree"])
    return out is not None and out.strip() == "true"


def shipping_set(root):
    """Repo-relative paths git would actually publish, or None outside a repo."""
    out = run_git(
        root, ["ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        binary=True)
    if out is None:
        return None
    rels = (chunk.decode("utf-8", "replace") for chunk in out.split(b"\0") if chunk)
    return frozenset(rel for rel in rels if (root / rel).is_file())


def walk_all_files(root):
    """Every file on disk under root, minus .git and node_modules."""
    return frozenset(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and not any(part in WALK_SKIP_DIRS for part in p.parts))


# --- Git history -------------------------------------------------------------

def head_blob_shas(root):
    """Blob SHAs in the HEAD tree - these are covered by the worktree scan."""
    out = run_git(root, ["ls-tree", "-r", "HEAD"])
    if not out:
        return frozenset()
    shas = []
    for line in out.splitlines():
        meta, _, _path = line.partition("\t")
        parts = meta.split()
        if len(parts) >= 3 and parts[1] == "blob":
            shas.append(parts[2])
    return frozenset(shas)


def reachable_objects(root):
    """((sha, path), ...) for every object reachable from any ref."""
    out = run_git(root, ["rev-list", "--objects", "--all"])
    if out is None:
        return ()
    seen = {}
    for line in out.splitlines():
        sha, _, path = line.partition(" ")
        if path and sha not in seen:
            seen[sha] = path
    return tuple(seen.items())


def batch_check(root, shas):
    """{sha: (type, size)} for a list of SHAs."""
    if not shas:
        return {}
    payload = ("\n".join(shas) + "\n").encode("utf-8")
    out = run_git(root, ["cat-file", "--batch-check"], stdin_data=payload)
    if out is None:
        return {}
    info = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2].isdigit():
            info[parts[0]] = (parts[1], int(parts[2]))
    return info


def parse_batch(buf):
    """Yield (sha, data) from `git cat-file --batch` output."""
    pos = 0
    while pos < len(buf):
        nl = buf.find(b"\n", pos)
        if nl == -1:
            return
        header = buf[pos:nl].decode("utf-8", "replace").split()
        pos = nl + 1
        if len(header) < 3 or not header[2].isdigit():
            continue  # "missing" / malformed record
        size = int(header[2])
        yield header[0], buf[pos:pos + size]
        pos += size + 1


def read_blobs(root, shas):
    """Yield (sha, text) for readable, non-binary blobs, in batches."""
    for start in range(0, len(shas), BLOB_BATCH):
        chunk = shas[start:start + BLOB_BATCH]
        payload = ("\n".join(chunk) + "\n").encode("utf-8")
        out = run_git(root, ["cat-file", "--batch"], stdin_data=payload,
                      binary=True)
        if out is None:
            continue
        for sha, data in parse_batch(out):
            if b"\x00" in data[:8192]:
                continue
            yield sha, data.decode("utf-8", errors="replace")


def scan_commit_metadata(root, denylist):
    """Author/committer names, emails, subjects, bodies and ref names."""
    findings = []
    log = run_git(root, ["log", "--all", "--format=%H%x1f%an%x1f%ae%x1f%cn"
                         "%x1f%ce%x1f%s%x1f%b%x1e"])
    if log:
        for record in log.split("\x1e"):
            fields = record.strip("\n").split("\x1f")
            if len(fields) < 7:
                continue
            sha = fields[0].strip()
            text = "\n".join(fields[1:])
            findings.extend(
                scan_text(text, f"(commit {sha[:7]})", denylist))
    refs = run_git(root, ["for-each-ref", "--format=%(refname)"])
    if refs:
        findings.extend(scan_text(refs, "(ref names)", denylist))
    return tuple(findings)


def scan_history(root, denylist, limit):
    """Scan history-only blobs plus commit metadata.

    Returns (findings, problems, stats). Blobs present in HEAD are skipped -
    the worktree pass already covered that content, so what remains is exactly
    the dangerous case: something committed, then deleted, and still public.
    """
    objects = reachable_objects(root)
    if not objects:
        return (), (), {"blobs": 0, "skipped_large": 0, "paths": 0}

    head = head_blob_shas(root)
    candidates = tuple((sha, path) for sha, path in objects if sha not in head)
    info = batch_check(root, [sha for sha, _ in candidates])

    blob_paths, oversized = {}, 0
    for sha, path in candidates:
        kind, size = info.get(sha, (None, 0))
        if kind != "blob":
            continue
        if size > MAX_BLOB_BYTES:
            oversized += 1
            continue
        blob_paths[sha] = path

    problems = []
    shas = sorted(blob_paths)
    if len(shas) > limit:
        problems.append(
            f"history scan truncated at {limit} of {len(shas)} blobs "
            f"(raise --history-limit, or assemble the public tree as a single "
            f"squashed commit)")
        shas = shas[:limit]
    if oversized:
        problems.append(
            f"{oversized} history blob(s) over {MAX_BLOB_BYTES // 1024}KB were "
            f"not scanned - inspect them by hand")

    findings = []
    for sha, text in read_blobs(root, shas):
        where = f"{blob_paths.get(sha, '?')}@{sha[:7]}"
        findings.extend(scan_text(text, where, denylist))

    # Path names leak too: a deleted `raw/<employer>-offsite/` folder is a leak
    # even if every file inside it was scrubbed.
    path_text = "\n".join(sorted({path for _sha, path in candidates}))
    findings.extend(
        scan_text(path_text, "(history paths)", denylist, use_regex=False))
    findings.extend(scan_commit_metadata(root, denylist))

    stats = {"blobs": len(shas), "skipped_large": oversized,
             "paths": len(candidates)}
    return tuple(findings), tuple(problems), stats


# --- Structural checks -------------------------------------------------------

def content_census(rel_paths):
    """{directory: file count} for everything under raw/ and wiki/."""
    census = {}
    for rel in rel_paths:
        parent = str(Path(rel).parent)
        if parent.split("/")[0] not in ("raw", "wiki"):
            continue
        census[parent] = census.get(parent, 0) + 1
    return census


def check_structure(root, rel_paths, in_repo, opts):
    """Return a tuple of structural problem strings (empty == clean).

    `rel_paths` here is always the shipping set when one exists, even under
    --all-files: a gitignored `.qmd/` or `denylist.txt` sitting in your working
    copy is correct, and flagging it would red-line the gate forever.
    """
    problems = []

    for forbidden in FORBIDDEN_PATHS:
        hit = any(rel == forbidden or rel.startswith(forbidden + "/")
                  or f"/{forbidden}/" in f"/{rel}"
                  for rel in rel_paths)
        if hit:
            problems.append(f"forbidden artifact in the shipping set: {forbidden}")
        elif not in_repo and (root / forbidden).exists():
            problems.append(f"forbidden artifact present on disk: {forbidden}")

    stray_assets = sorted(
        rel for rel in rel_paths
        if rel.startswith("assets/") and Path(rel).name != ".gitkeep")
    if stray_assets:
        problems.append(
            f"assets/ ships {len(stray_assets)} file(s) a text gate cannot read "
            f"(e.g. {stray_assets[0]}) - screenshots and PDFs leak silently")

    census = content_census(rel_paths)
    for directory, count in sorted(census.items()):
        capped = directory.startswith("raw/") or directory in WIKI_CONTENT_DIRS
        if capped and count > opts.max_content_files:
            problems.append(
                f"{directory}: {count} files, ceiling {opts.max_content_files} "
                f"- publish stubs, not the real corpus")

    if opts.expect_single_commit and in_repo:
        out = run_git(root, ["rev-list", "--count", "--all"])
        count = int(out.strip()) if out and out.strip().isdigit() else -1
        if count != 1:
            problems.append(
                f"git history has {count} commit(s), expected exactly 1 "
                f"- assemble the public tree as a fresh single squashed commit")

    return tuple(problems)


# --- Reporting ---------------------------------------------------------------

def preview(kind, value):
    """Render a finding's value without reprinting a whole secret into CI logs."""
    if kind in SECRET_KINDS:
        return f"{value[:4]}...[{len(value)} chars, masked]"
    if len(value) > 40:
        return f"{value[:24]}...[{len(value)} chars]"
    return value


def print_findings(label, findings):
    for finding in sorted(findings, key=lambda f: (f.where, f.line)):
        times = f" (x{finding.count})" if finding.count > 1 else ""
        print(f"{label:7s} {finding.where}:{finding.line}: "
              f"[{finding.kind}] {preview(finding.kind, finding.value)!r}{times}")


def print_census(census, ceiling):
    if not census:
        return
    print("\n--- content census (eyeball this: a folder you forgot is a leak) ---")
    for directory, count in sorted(census.items()):
        capped = directory.startswith("raw/") or directory in WIKI_CONTENT_DIRS
        flag = "  <-- over ceiling" if capped and count > ceiling else ""
        print(f"        {directory}: {count}{flag}")


# --- Entry point -------------------------------------------------------------

def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="leak-scan.py",
        description="Privacy gate: scan a tree and its git history for personal "
                    "data before publishing it.")
    parser.add_argument(
        "root", nargs="?", default=None,
        help="directory to scan (default: the repo this script lives in)")
    parser.add_argument(
        "--denylist", default=None,
        help=f"path to the denylist (default: <root>/{DENYLIST_REL}, falling "
             f"back to the one beside this script)")
    parser.add_argument(
        "--all-files", action="store_true",
        help="scan every file on disk, not just the git shipping set")
    parser.add_argument(
        "--no-history", action="store_true",
        help="skip the git history pass (worktree only - you are choosing to "
             "trust that nothing sensitive was ever committed and deleted)")
    parser.add_argument(
        "--history-limit", type=int, default=DEFAULT_HISTORY_LIMIT,
        help=f"max history blobs to scan (default {DEFAULT_HISTORY_LIMIT})")
    parser.add_argument(
        "--expect-single-commit", action="store_true",
        help="assert the tree has exactly one commit (release-assembly check)")
    parser.add_argument(
        "--max-content-files", type=int, default=DEFAULT_MAX_CONTENT_FILES,
        help=f"per-directory ceiling for raw/ and wiki content dirs "
             f"(default {DEFAULT_MAX_CONTENT_FILES})")
    return parser.parse_args(argv)


def is_unedited(denylist, example_path):
    """True when denylist.txt is still the shipped example, terms and all.

    An unedited copy protects nothing, so it is reported as unconfigured rather
    than left to fire on its own placeholder names.
    """
    if not example_path.exists():
        return False
    try:
        example, _warnings = load_denylist(example_path)
    except (ValueError, OSError):
        return False
    return denylist == example


def resolve_denylist_path(root, opts):
    if opts.denylist:
        return Path(opts.denylist).expanduser()
    candidate = root / DENYLIST_REL
    if candidate.exists():
        return candidate
    return Path(__file__).resolve().parent / "denylist.txt"


def main(argv=None):
    opts = parse_args(sys.argv[1:] if argv is None else argv)

    default_root = Path(__file__).resolve().parents[2]
    root = Path(opts.root).expanduser().resolve() if opts.root else default_root
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    denylist_path = resolve_denylist_path(root, opts)
    denylist, configured, reason = EMPTY_DENYLIST, False, "none"
    if denylist_path.exists():
        try:
            denylist, warnings = load_denylist(denylist_path)
        except (ValueError, OSError) as exc:
            print(f"malformed denylist: {exc}", file=sys.stderr)
            return 2
        for warning in warnings:
            print(f"WARN    {warning}")
        if is_unedited(denylist, root / EXAMPLE_REL):
            denylist, reason = EMPTY_DENYLIST, "unedited"
        else:
            configured = True
    if not configured:
        detail = ("is still an unedited copy of the example - it names nobody "
                  "real" if reason == "unedited"
                  else "was not found")
        print("=" * 72)
        print(f"WARNING: {denylist_path} {detail}.")
        print("         NAME CHECKS ARE DISABLED. Structural checks still ran.")
        print(f"           cp {EXAMPLE_REL} {DENYLIST_REL}")
        print("         then fill in real names, employers, handles and paths.")
        print("=" * 72)

    in_repo = is_git_repo(root)
    shipping = shipping_set(root) if in_repo else None
    if shipping is None:
        rel_paths = walk_all_files(root)
        print("INFO    not a git repo - scanning every file on disk")
    else:
        rel_paths = walk_all_files(root) if opts.all_files else shipping

    print(f"INFO    scanning {len(rel_paths)} file(s) under {root}")
    if configured:
        print(f"INFO    denylist: {len(denylist.words)} word term(s), "
              f"{len(denylist.substrings)} substring term(s) "
              f"from {denylist_path}")

    findings, skipped = scan_files(root, rel_paths, denylist)

    history_findings, history_problems = (), ()
    if opts.no_history:
        print("WARN    history scan skipped (--no-history): a name committed "
              "then deleted would not be caught")
    elif not in_repo:
        print("WARN    not a git repo - history scan skipped")
    else:
        history_findings, history_problems, stats = scan_history(
            root, denylist, opts.history_limit)
        print(f"INFO    history: {stats['blobs']} blob(s) not in HEAD scanned, "
              f"{stats['paths']} reachable object path(s) checked")

    structural_set = shipping if shipping is not None else rel_paths
    problems = check_structure(
        root, structural_set, in_repo, opts) + history_problems

    print()
    print_findings("LEAK", findings)
    print_findings("HISTORY", history_findings)
    for problem in problems:
        print(f"STRUCT  {problem}")
    if skipped:
        print(f"INFO    {len(skipped)} binary/oversized file(s) not text-scanned "
              f"- review them by hand")

    print_census(content_census(structural_set), opts.max_content_files)

    total = len(findings) + len(history_findings)
    print()
    if total or problems:
        print(f"FAIL - {len(findings)} worktree finding(s), "
              f"{len(history_findings)} history finding(s), "
              f"{len(problems)} structural problem(s). Do not publish.")
        return 1
    if not configured:
        print("FAIL - structure is clean, but the name checks never ran. "
              "Configure the denylist and re-run.")
        return 3
    print("PASS - no findings, structure clean, name checks configured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
