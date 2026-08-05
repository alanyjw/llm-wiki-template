#!/usr/bin/env python3
"""Report what the upstream template has that this instance does not.

WHY THIS IS REPORT-ONLY. Instances share NO git ancestry with the template —
they were copied, not forked — so no merge base exists and `git merge` has
nothing to three-way against. Every shared file carries exactly one upstream
commit, which collapses a synthesized 3-way merge into a two-file diff:
attempting it on wiki-lint.py produces 9 conflict hunks and a result that
fails `ast.parse`. So this never merges, rebases, checks out, or writes. It
reads upstream blobs with `git show <ref>:<path>` and prints; taking a change
stays a deliberate human copy, informed by this report.

Buckets are exhaustive over the watch list (the 2x2 on here/upstream):
  IN SYNC        both present, identical bytes
  DIFFERS        both present, bytes differ — upstream's last-touched date is
                 printed, the only direction signal available with no merge base
  ABSENT HERE    upstream has it, this instance does not — the "take it" case
  GONE UPSTREAM  upstream does not have it (retired, or not shared yet)
  IGNORED        listed in .template-sync-ignore — a deliberate local fork
A path falling out of every bucket is a silent skip — the exact failure this
design exists to prevent — so the reconciliation line is checked, and exits 2.

Push guard: upstream is PUBLIC, instances are PRIVATE. Refuses to run unless
the remote's push URL has been explicitly disabled.

Usage:
  python3 .claude/scripts/template-drift.py            # human report
  python3 .claude/scripts/template-drift.py --json     # machine-readable (CI)
  python3 .claude/scripts/template-drift.py --quiet    # summary counts only
Env: TEMPLATE_REMOTE (default: template) | TEMPLATE_REF (default: <remote>/main)
Exit: 0 no actionable drift (or is-upstream) | 1 drift | 2 misconfigured
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

def _repo_root():
    """The repo under inspection is the one you are STANDING IN.

    Resolving this from __file__ instead made an absolute-path invocation from
    another repo silently audit the template — and because the template is its
    own upstream, that self-detected and exited 0. A clean bill of health for a
    repo it never opened. Returns None outside a git repo; main() bails."""
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return Path(p.stdout.decode("utf-8", "replace").strip()) if p.returncode == 0 else None

VAULT = _repo_root()
SCRIPT_REPO = Path(__file__).resolve().parents[2]

# The only string that counts as "push disabled". Exact match, every value.
PUSH_SENTINEL = "DISABLED_public_repo"

# Upstream-owned. When upstream starts sharing a new file it adds the path here
# and every instance picks it up the next time it takes this script. That
# inheritance is the scalability mechanism: one upstream edit, not N.
#
# The first three are this mechanism's own files. A sync tool that does not
# watch itself cannot propagate itself — it would be the one thing every
# instance had to port by hand, which is the exact cost this exists to remove.
WATCH = [
    ".claude/scripts/template-drift.py",
    ".github/workflows/template-drift.yml",
    "SYNC.md",
    ".claude/scripts/wiki-lint.py",
    ".claude/scripts/wiki-lint.config.json",
    ".claude/scripts/regenerate-index.py",
    ".claude/scripts/check-date-updated.py",
    ".claude/scripts/qmd-refresh-hook.sh",
    ".claude/scripts/bump-markdownlint-obsidian.sh",
    ".github/workflows/wiki-lint.yml",
    ".github/workflows/gitleaks.yml",
    ".gitleaks.toml",
    ".obsidian-linter.jsonc",
    "templates/capture.md",
    "templates/meeting.md",
    "templates/video.md",
]

# Per-instance config, NOT shared content — each instance legitimately carries
# its own carve-outs. Presence still matters (missing = never adopted the
# mechanism), but a content diff is pure noise, so these never report DIFFERS.
PRESENCE_ONLY = {".claude/scripts/wiki-lint.config.json"}

# Self-detection when no template remote is configured — the normal state
# inside the upstream repo itself. Slug only: no URL, no owner.
UPSTREAM_SLUG = "llm-wiki-template"

IGNORE_FILE = ".template-sync-ignore"
BUCKETS = ["DIFFERS", "ABSENT HERE", "GONE UPSTREAM", "IGNORED", "IN SYNC"]
ACTIONABLE = {"DIFFERS", "ABSENT HERE", "GONE UPSTREAM"}

def git(*args, binary=False):
    """Run git in VAULT. Returns (exit_code, output). Never raises."""
    p = subprocess.run(["git", "-C", str(VAULT), *args],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    out = p.stdout if binary else p.stdout.decode("utf-8", "replace").strip()
    return p.returncode, out

def blob_sha1(data: bytes) -> str:
    """Git's blob object hash — computed locally so both sides use one rule."""
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()

def norm_url(url: str) -> str:
    u = url.strip().rstrip("/")
    return u[:-4] if u.endswith(".git") else u

def slug(url: str) -> str:
    return norm_url(url).rsplit("/", 1)[-1].rsplit(":", 1)[-1]

def load_ignore():
    """Parse .template-sync-ignore -> {path: reason}. '#' starts a comment.

    An instance that forks a shared file must say so here AND in the file
    itself; that pairing is what makes the fork survive the next reader."""
    f = VAULT / IGNORE_FILE
    if not f.is_file():
        return {}
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        body, _, reason = line.partition("#")
        if body.strip():
            out[body.strip()] = reason.strip()
    return out

def classify(ref, path, ignored):
    """Bucket exactly one watched path. Returns (bucket, detail)."""
    if path in ignored:
        return "IGNORED", ignored[path] or "local fork (no reason recorded)"

    code, up_bytes = git("show", f"{ref}:{path}", binary=True)
    local = VAULT / path
    here = local.is_file()
    if code != 0:
        return "GONE UPSTREAM", "present here" if here else "not shared upstream"
    if not here:
        # A directory or broken symlink sitting on the path is NOT the same as
        # nothing being there: `git checkout <ref> -- <path>` will fail for that
        # reader, so the report must not prescribe it silently.
        if local.exists() or local.is_symlink():
            return "ABSENT HERE", "BLOCKED: a directory or bad symlink occupies this path"
        return "ABSENT HERE", "upstream has it"
    if path in PRESENCE_ONLY:
        return "IN SYNC", "presence-only (content is per-instance by design)"
    if blob_sha1(local.read_bytes()) == blob_sha1(up_bytes):
        return "IN SYNC", ""
    _, when = git("log", "-1", "--format=%ad", "--date=short", ref, "--", path)
    return "DIFFERS", f"upstream last touched {when or 'unknown'}"

def bail(as_json, status, message, code):
    """Terminate early with a status both humans and CI can read."""
    if as_json:
        print(json.dumps({"status": status, "message": message, "exit": code}, indent=2))
    else:
        print(message)
    sys.exit(code)

def main():
    as_json = "--json" in sys.argv[1:]
    quiet = "--quiet" in sys.argv[1:]
    remote = os.environ.get("TEMPLATE_REMOTE", "template")

    if VAULT is None:
        bail(as_json, "not-a-repo",
             "REFUSING TO RUN: not inside a git repository.\n"
             "  cd to the root of the instance you want to check, then re-run.\n", 2)

    _, origin = git("config", "--get", "remote.origin.url")
    rc, remote_url = git("config", "--get", f"remote.{remote}.url")
    remote_url = remote_url if rc == 0 else ""

    # Self-detection — this script ships in the template, so it must no-op there.
    # With a template remote configured, compare URLs; without one (the normal
    # state upstream) fall back to the repo slug.
    same = norm_url(origin) == norm_url(remote_url) if remote_url else \
        slug(origin) == UPSTREAM_SLUG
    if origin and same:
        bail(as_json, "is-upstream", "this IS the upstream — nothing to compare", 0)

    if not remote_url:
        bail(as_json, "no-remote",
             f"REFUSING TO RUN: no '{remote}' remote configured. Add it, then\n"
             f"  disable push (upstream is public, this instance is not):\n\n"
             f"    git remote add {remote} <upstream-url>\n"
             f"    git remote set-url --push {remote} DISABLED_public_repo\n", 2)

    # PUSH GUARD. Upstream is public; this repo is private and holds real data.
    # `git remote add` writes no pushurl entry — push silently defaults to the
    # fetch URL — so requiring an explicit DISABLED pushurl fails closed.
    #
    # Two ways this guard was defeated before it was tightened, both verified by
    # actually completing a push:
    #   1. A substring test (`"DISABLED" not in pushurl`) passed any genuinely
    #      pushable URL that merely CONTAINED the word — `.../DISABLED-repo.git`
    #      sailed through. Hence an exact match against one sentinel.
    #   2. `pushurl` is MULTI-VALUED. `git remote set-url --push --add` appends,
    #      `--get` returns only the first, and `git push` delivers to EVERY
    #      value. A pair [real-url, sentinel] therefore read as disabled while
    #      git pushed to the real URL. Hence --get-all, and every value checked.
    rc, raw = git("config", "--get-all", f"remote.{remote}.pushurl")
    urls = [u.strip() for u in raw.splitlines() if u.strip()] if rc == 0 else []
    if not urls or any(u != PUSH_SENTINEL for u in urls):
        have = ", ".join(urls) if urls else "<unset, defaults to the fetch URL>"
        bail(as_json, "push-not-disabled",
             f"REFUSING TO RUN: push to '{remote}' is not disabled.\n"
             f"  remote.{remote}.pushurl = {have}\n"
             f"  '{remote}' is a PUBLIC repo and this instance is private.\n"
             f"  Every pushurl value must be exactly '{PUSH_SENTINEL}'.\n"
             f"  Disable push explicitly, then re-run:\n\n"
             f"    git remote set-url --push {remote} {PUSH_SENTINEL}\n", 2)

    ref = os.environ.get("TEMPLATE_REF", f"{remote}/main")
    if git("rev-parse", "--verify", "--quiet", ref)[0] != 0:
        bail(as_json, "no-ref",
             f"REFUSING TO RUN: ref '{ref}' does not resolve.\n"
             f"  Fetch it first:  git fetch {remote}\n"
             f"  Or override:     TEMPLATE_REF=<ref> {sys.argv[0]}\n", 2)

    # This script never fetches. Without the ref's date on screen, a report
    # built from a months-stale ref reads exactly like a current one.
    _, ref_date = git("log", "-1", "--format=%ad", "--date=short", ref)

    ignored = load_ignore()
    rows = [(p, *classify(ref, p, ignored)) for p in WATCH]
    counts = {b: sum(1 for r in rows if r[1] == b) for b in BUCKETS}
    accounted = sum(counts.values())
    reconciled = accounted == len(WATCH) == len(set(WATCH))
    stray = sorted(set(ignored) - set(WATCH))
    drift = any(counts[b] for b in ACTIONABLE)
    code = 2 if not reconciled else (1 if drift else 0)

    if as_json:
        print(json.dumps({
            "status": "ok" if reconciled else "reconciliation-failed",
            "ref": ref, "ref_date": ref_date, "remote": remote,
            "inspecting": str(VAULT), "watched": len(WATCH),
            "accounted": accounted, "reconciled": reconciled, "drift": drift,
            "counts": counts, "ignore_entries_not_watched": stray, "exit": code,
            "files": [{"path": p, "bucket": b, "detail": d} for p, b, d in rows],
        }, indent=2))
        sys.exit(code)

    print(f"Template drift — worktree vs {ref} "
          f"(fetched through {ref_date or 'unknown'})")
    if VAULT != SCRIPT_REPO:
        print(f"NOTE: inspecting {VAULT}, using the watch list from {SCRIPT_REPO}")
    print(f"watched {len(WATCH)}, accounted {accounted}")
    if quiet:
        print("  " + "  ".join(f"{b}={counts[b]}" for b in BUCKETS))
    else:
        for bucket in BUCKETS:
            hits = [(p, d) for p, b, d in rows if b == bucket]
            if hits:
                print(f"\n{bucket} ({len(hits)})")
                for path, detail in hits:
                    print(f"  {path:<46}{detail}".rstrip())
        if stray:
            print(f"\nNOTE: {IGNORE_FILE} lists path(s) not on the watch list "
                  f"(typo?): {', '.join(stray)}")

    if not reconciled:
        print(f"\nRECONCILIATION FAILED: watched {len(WATCH)} ({len(set(WATCH))} uniq), "
              f"accounted {accounted} — path duplicated, or fell out of every bucket.")
    sys.exit(code)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 — deliberate catch-all, see below
        # An uncaught exception exits 1, which is this script's "drift found"
        # code. CI would then file the traceback as a legitimate drift report.
        # Crashes belong in the misconfigured branch, which fails the job.
        import traceback
        traceback.print_exc()
        print("\nCRASHED — reporting as misconfigured (2), not as drift (1).",
              file=sys.stderr)
        sys.exit(2)
