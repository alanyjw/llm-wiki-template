# Releasing

For maintainers who run a **private** wiki from this template and publish a
**sanitized** copy of it back out — the template you are reading was produced
exactly that way. If your vault stays private, ignore this file.

The risk is one-directional: a private vault is full of real names, employer
names, absolute home paths, and document ids, and a public push is irreversible.
Treat a release as a data-exfiltration review, not a version bump.

## 1. The privacy gate is mandatory and runs before every public push

Assemble the public tree in a **separate directory** — never publish by deleting
files out of the private vault and hoping git forgets. Then run the gate over
the assembled tree, and only push when it exits 0.

The gate ships with the template as `.claude/scripts/leak-scan.py`. What does
*not* ship is its denylist: a list of real people, employers, handles and home
paths cannot live in a public repo, because publishing it publishes the very
thing it exists to protect. So the script loads its denylist at runtime from
`.claude/scripts/denylist.txt`, which is gitignored. **The mechanism is public;
the names are yours.**

One-time setup:

```
cp .claude/scripts/denylist.example.txt .claude/scripts/denylist.txt
$EDITOR .claude/scripts/denylist.txt        # fill in real terms — see section 2
```

Then, every release:

```
python3 .claude/scripts/leak-scan.py ../public-repo-dir --expect-single-commit
```

Exit codes: `0` clean and configured · `1` findings · `2` bad invocation or a
malformed denylist · `3` no denylist **and nothing else fired**. An unconfigured
gate is never reported as a pass, and an unedited copy of the example counts as
unconfigured. Only exit 0 means publish.

The codes are checked in that order, so they are not independent: a first run
with no denylist that *also* has findings exits `1`, not `3` — the missing
denylist is reported in the banner, not the exit code. Don't branch a wrapper
script on `3` to mean "unconfigured"; read the banner, or just treat anything
non-zero as "do not publish", which is the only rule that matters.

Useful flags: `--all-files` scans everything on disk instead of just the git
shipping set; `--no-history` skips the history pass (fast, and strictly less
safe); `--max-content-files N` moves the per-directory ceiling; `--denylist
PATH` points at a denylist kept outside the repo entirely.

## 2. What the gate checks, and how to write a denylist that works

The two denylist sections are matched differently, on purpose.

**`[words]` — bare proper nouns.** First names, surnames, short org acronyms.
Matched **case-sensitively on word boundaries**. Case sensitivity is what keeps
a first name like `Mark`, `Will` or `Grace` from firing on the ordinary verbs
and nouns; the word boundary is what keeps a three- or four-letter acronym from
firing inside unrelated longer words. A denylist that false-positives on every
third file gets ignored, which is the same as not having one — so keep this
section tight and push anything ambiguous into the other one.

**`[substrings]` — multi-word terms, paths, handles.** Full names, employer
names, social handles, `/Users/<you>`, and the names of personal side repos your
skills shell out to. Matched **case-insensitively as substrings**: they are
distinctive enough that a substring hit is almost always real. Two entries
everyone forgets — the private vault's own directory name as it appears in
absolute paths, and the mangled form that tooling writes into cache paths.

Everything below needs no personal data, so it is built into the script and
runs even before you configure a denylist:

- **Structured secrets** — cloud access keys, API-key-shaped tokens, JWTs,
  private-key headers, `secret:` / `password:` assignments, and document or
  calendar URLs that embed an id. Personal wikis accumulate these in meeting
  notes without anyone deciding to put them there. Matched values are masked in
  the output, so the gate never reprints a live secret into a CI log.
- **Absolute home paths and email addresses** — `/Users/<name>`, `/home/<name>`,
  and anything address-shaped.
- **Machine-local artifacts** — `.claude/settings.local.json`,
  `.claude/worktrees/`, scheduler locks, `__pycache__/`, `.qmd/`, and
  `denylist.txt` itself. Flagged when they appear in the **shipping set**, not
  merely on disk, so your own working copy never red-lines the gate.
- **Un-scannable binaries** — anything under `assets/` other than `.gitkeep`. A
  text gate cannot read a screenshot.
- **A per-directory ceiling on content files**, plus a printed census of every
  directory under `raw/` and `wiki/`. Counting files catches the "I forgot that
  folder existed" class of mistake that a text scan never will. The census is
  there to be eyeballed — read it every time.

**Git history, not just the worktree.** A file scrubbed in the tip commit is
still fully readable in the commit that introduced it. The script scans every
blob reachable from any ref but absent from HEAD, plus commit subjects, bodies,
author and committer names, author emails, and ref names. Two consequences worth
internalizing: branch names leak, and **squashing does not change your git
identity** — if your commits are authored under a personal address, that address
publishes with them. The safest assembly is still a fresh `git init` with a
**single** squashed commit; `--expect-single-commit` asserts exactly that. If
you must preserve history, assume anything already pushed is public forever.

**Set the publishing identity in the assembly directory before the first
commit.** Global git config is whatever you use for private work, and it is
inherited silently. Set it per-repo, right after `git init`, and never rely on
remembering at commit time:

```
git init
git config user.name  "Your Public Handle"
git config user.email "<id>+<handle>@users.noreply.github.com"   # or a project address
git config --get user.email      # verify BEFORE committing
```

GitHub gives every account a `@users.noreply.github.com` address (Settings →
Emails); using it means no real address ever enters a commit object. Note that
`user.name` and `user.email` set the *author*; the *committer* fields are taken
from the same config unless `GIT_COMMITTER_NAME` / `GIT_COMMITTER_EMAIL` are
exported in your environment, which some tooling does — so verify both after the
commit exists:

```
git log --all --format='%an|%ae|%cn|%ce' | sort -u
```

Anything on that list that you would not print on a business card means the
history has to be rebuilt, not amended. `leak-scan.py` reads exactly these
fields, so a clean gate is the same assertion — but read the list yourself too.

**Documented exemptions.** A gate that cries wolf is a gate you learn to ignore,
so a few known-legitimate patterns are exempted in the script, each with its
reason in a comment beside it. The two that bit this repo first:

- **SHA-pinned GitHub Actions** — `uses: owner/repo@<40 hex>  # v5`. Pinning an
  action to a commit SHA is a supply-chain best practice and the SHA is public,
  but a naive long-hex rule flags every hardened workflow you own.
- **Git's all-zero null SHA** (`0000...0`), which pre-push hooks pass to mean "no
  such ref". Also 40 hex characters, also not a secret.

Others: service-account home paths (`/home/runner`), placeholder emails
(`@example.com`, `noreply@`), `name@ext` strings whose apparent TLD is a file
extension (`sprite@2x.png`), and placeholder secret assignments. Add your own
only with the reason written down next to it.

## 3. Run all CI gates locally before pushing

CI will run these anyway; locally means you find breakage before it is public.

```
npx markdownlint-obsidian-cli@1.1.0 "wiki/**/*.md" --vault-root wiki
python3 .claude/scripts/wiki-lint.py wiki/
python3 .claude/scripts/regenerate-index.py --check
```

`npx` ships with Node, so the first command needs no extra install; CI runs the
identical pinned version through `bunx`. If you use `bunx` locally, note the
missing `--bun` flag — see the comment in `.github/workflows/wiki-lint.yml` for
why re-adding it breaks the lint.

Genericization commonly breaks gate 2: renaming a page or dropping a
domain-specific example leaves `WIKI002` broken wikilinks and `FM005`
unresolvable `raw_sources:` paths behind. Fix those in the public tree, not by
loosening the linter.

## 4. Never commit index artifacts or real `raw/` content

- **`.qmd/`** — the local search index. It is a SQLite database containing the
  full text of every document you indexed, plus absolute paths from your
  machine. Publishing it publishes your entire private vault even if every
  markdown file was scrubbed. It is in `.gitignore`; verify it is actually
  untracked (`git ls-files .qmd/` must print nothing) rather than trusting the
  ignore rule, because a file committed before the rule existed stays tracked.
- **`.claude/scripts/denylist.txt`** — same reasoning, higher stakes. Gitignored;
  confirm with `git ls-files .claude/scripts/denylist.txt` (must print nothing).
  The gate also fails if it ever reaches the shipping set.
- **`assets/`** — screenshots and PDFs are not scanned by a text-based gate.
  Ship the `.gitkeep` and nothing else.
- **`.claude/settings.local.json`** and `.claude/worktrees/` — per-machine
  permission allowlists and scratch worktrees; both leak paths and workflow
  detail.
- **`raw/`** — ship a `.gitkeep` per folder, plus at most one clearly-labelled
  sample note. This template ships exactly that: **11** `.gitkeep` files, one per
  `raw/` subfolder (`authored`, `books`, `briefings`, `captures/daily`,
  `captures/weekly`, `claude-chats`, `meetings`, `notes-import`, `projects`,
  `research`, `web-clippings`), one dated sample under `raw/notes-import/`, and a
  `raw/bookmarks.md` holding a single `example.com` placeholder. Real notes are
  the point of the vault and the last thing that should leave it.

> **That count is load-bearing.** It is a structural assertion about the shipped
> tree, and it goes stale the moment anyone adds a `raw/` subfolder. Verify it
> before every release and update this line if it moved:
>
> ```
> find raw -name .gitkeep | wc -l
> ```
>
> The same applies to the census that `leak-scan.py` prints — a new folder shows
> up there as a row you have never seen before, which is exactly the signal you
> want.

## 5. Release checklist

1. Assemble the public tree in a separate directory, `git init` it, and set
   `user.name` / `user.email` in that repo **before the first commit**
   (section 2). `git config --get user.email` to confirm.
2. Rewrite `CLAUDE.md`'s "About the Vault Owner" back to the neutral example.
3. Run `find raw -name .gitkeep | wc -l` and reconcile it with section 4 — then
   reconcile the same folder list against `wiki/index.md`'s hand-curated
   `## Raw Source Inventory` section and `setup.sh`'s collection registrations.
   All three go stale on the same event (someone adds a `raw/` subfolder) and no
   gate catches any of them.
4. Run the privacy gate. Fix findings. Re-run until it exits 0.
5. Run the CI gates locally.
6. Skim the diff by eye — the gate catches what you told it to catch, and a
   release is where you discover the term you never added to the denylist.
7. Squash to a single commit, then run
   `git log --all --format='%an|%ae|%cn|%ce' | sort -u` and read every line
   before pushing. Author *and* committer, on every commit and every ref.
8. Push. Re-run the gate against the pushed tree once, as a receipt.
