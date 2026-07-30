# Releasing

For maintainers who run a **private** wiki from this template and publish a
**sanitized** copy of it back out — the template you are reading was produced
exactly that way. If your vault stays private, ignore this file.

The risk is one-directional: a private vault is full of real names, employer
names, absolute home paths, and document ids, and a public push is irreversible.
Treat a release as a data-exfiltration review, not a version bump.

## 1. The privacy gate is two scanners, and both are mandatory

Assemble the public tree in a **separate directory** — never publish by deleting
files out of the private vault and hoping git forgets. Then run **both** scanners
over the assembled tree, and only push when both exit 0.

They split the work, and neither one covers the other's half:

| | `gitleaks` | `leak-scan.py` |
|---|---|---|
| Hunts | secrets and credentials | identity, PII, publication structure |
| Rules | ~170 upstream rules with entropy analysis, maintained by people who watch token formats change | your denylist, plus built-ins for home paths, addresses and document ids |
| Reads | diff content and file paths | worktree, unreachable history blobs, **and commit metadata** |
| Ships here | config only (`.gitleaks.toml`) | the script, plus `denylist.example.txt` |

**Why gitleaks alone is not enough.** Measured 2026-07-30 with gitleaks 8.30.1:
it reads diff content and file paths, and nothing else. It never reads commit
subjects, commit bodies, ref names, annotated tag messages, or author/committer
identity. A fixture repo on a branch named `feature/acme-corp-migration`, whose
commit subject and body both named "Acme Corp", whose annotated tag message named
it a third time, and whose author *and* committer were a real-looking
`Name <person@example.com>`, scanned clean: **`1 commits scanned`, 0 findings.**
(That address is written in the IANA reserved `example.com` domain on purpose —
`leak-scan.py` exempts it, and this file is inside the tree `leak-scan.py`
scans, so a plausible-looking address here would fail the gate on its own
documentation forever. The fixture used a domain that was *not* exempt.)

That is not a hypothetical in this repo. This template's own history carried the
source organisation's acronym in a commit-message body — `Genericized (no
<ORG>/personal tokens)`, in an earlier version of `chore(toolchain): sync lint
pipeline with upstream vault` — and a second commit body quoted a real name and a
personal Gmail address inside an example census block. Both were amended away only
because a human read them, and both still sit in this clone's object store
(`git rev-list --all --reflog`, commits `791f710` and `dd1aa9d`). A secrets
scanner would never have flagged one character of either. **That failure is the
entire reason both scanners are required.**

**Why leak-scan.py alone is not enough.** It has stopped hunting provider
credentials as a class. Its hand-rolled AWS, GitHub, Google-API and JWT rules were
deleted on 2026-07-30 in favour of gitleaks, each one only after gitleaks was run
against a fixture holding exactly that credential class and observed to report it.
Four regexes cannot track token formats that vendors change; ~170 maintained ones
can. So skipping gitleaks is not skipping a duplicated check — it is a real hole.
In the same measurement gitleaks caught a Stripe secret key
(`stripe-access-token`) that leak-scan.py has no rule for and never will.

**Five credential rules were kept, each against a measured gitleaks gap**, with
the numbers in a comment beside the rule. Do not delete them on faith, and do not
close the gaps by pasting rules into `.gitleaks.toml` — the whole point of the
split is that credential rules are maintained upstream:

- `private-key` — gitleaks needs base64 key material after the header *and* the
  closing END marker. 100/100 on a full key, **0/100** on a bare
  `-----BEGIN RSA PRIVATE KEY` line (delimiters trimmed here on purpose, see the
  note below). A stray header is still evidence a key passed through that file.
- `secret-assignment` — gitleaks' `generic-api-key` is entropy-gated, so it fails
  exactly where a wiki is weakest: human-chosen secrets. 99/100 on random
  high-entropy values, **31/100** on a memorable passphrase someone typed into a
  note. Re-measured per case on seven realistic human-typed assignments —
  passphrases, memorable words, a name-and-year value, a wifi password written
  into prose — gitleaks reported **six of the seven as nothing at all**, and fired
  only on the one whose value was 20 random characters.
- `api-token` — **0/100** on a bare non-vendor `sk-`/`pk-` token sitting in
  ordinary prose, which is precisely how a key gets pasted into a meeting note.
- `slack-token` — gitleaks covers `xoxb`, `xoxa`, `xoxr`, the canonical
  4-segment `xoxp`, and `xoxs` in its 4- and 5-segment hex forms. Measured per
  shape, it **misses** 3-segment and 2-segment `xoxp` and `xoxs`, and both tools
  miss `xoxe-`. This rule was briefly deleted on the claim "all 5 prefixes, 60/60
  each" — a claim produced by a fixture generator that only ever emitted Slack's
  canonical shape, so it only ever asked a question gitleaks already passes.
- `long-hex` — gitleaks has no long-hex rule at all: **0/100** on a bare 40-char
  hex blob in prose. Opaque hex is how session tokens, digests and internal record
  ids leak. Exempts git's null SHA, SHA-pinned Actions, and a release checksum
  pinned next to a `sha256`-style label (a published digest is the opposite of a
  secret, and red-lining it would pressure you into deleting the verification).

**Why the examples above are written oddly.** `leak-scan.py` is not exempt from
its own rules, and this file ships inside the tree it scans. A verbatim private-key
header, a real-looking address, or an actual `password = "…"` line in this
document would make the release gate fail on its own documentation, permanently —
so each is deliberately written just outside its rule. If you edit this section,
re-run the gate on this repo before committing.

One more gap worth knowing, on gitleaks' side and arguably correct: the canonical
AWS documentation example access key (`AKIA…EXAMPLE`) is allowlisted upstream and
is not reported by either scanner now that `aws-key` is gone. Flagging every
tutorial would train people to ignore the gate; the cost is that a copy-pasted doc
snippet passes silently.

One-time setup:

```
cp .claude/scripts/denylist.example.txt .claude/scripts/denylist.txt
$EDITOR .claude/scripts/denylist.txt        # fill in real terms — see section 2
brew install gitleaks                       # or a pinned release binary:
                                            # github.com/gitleaks/gitleaks/releases
```

Then, every release — in this order, because gitleaks is the fast one and there is
no point scanning structure in a tree that still holds a live key:

```
cd ../public-repo-dir
gitleaks git . --config .gitleaks.toml --redact=80
python3 .claude/scripts/leak-scan.py . --expect-single-commit
```

**Commit the assembled tree first.** `git` mode walks the commit graph, so it is
blind to anything still unstaged or untracked — an uncommitted file scans clean
because it is not there yet, and that reads exactly like a pass. Squash first, then
scan (which is what `--expect-single-commit` is asserting on the other side). If
you want a pre-commit look, `gitleaks dir . --config .gitleaks.toml` covers the
worktree, but expect noise from machine-local files it has no reason to skip.

**Run gitleaks from inside the tree you are scanning** — hence the `cd` above.
Measured 2026-07-30: `git` mode reports repo-relative paths whatever argument you
pass, but `dir` mode given a path argument reports **absolute** ones, and an
absolute path is not merely noise. Any `path` filter in a config that happens to
be a substring of your working directory then matches every file scanned, so a
rule can look like it catches everything while catching nothing on its own merits.
That trap produced a bogus "caught it on all eight fixtures" result during the
evaluation that chose these two tools — the same reason `.gitleaks.toml` carries no
path filters at all.

Exit codes. gitleaks: `0` no findings · `1` findings (`--exit-code` sets this).
leak-scan.py: `0` clean and configured · `1` findings · `2` bad invocation or a
malformed denylist · `3` no denylist **and nothing else fired**. An unconfigured
gate is never reported as a pass, and an unedited copy of the example counts as
unconfigured. Only 0 from *both* means publish.

leak-scan.py's codes are checked in that order, so they are not independent: a
first run with no denylist that *also* has findings exits `1`, not `3` — the
missing denylist is reported in the banner, not the exit code. Don't branch a
wrapper script on `3` to mean "unconfigured"; read the banner, or just treat
anything non-zero from either scanner as "do not publish", which is the only rule
that matters.

Useful leak-scan.py flags: `--all-files` scans everything on disk instead of just
the git shipping set; `--no-history` skips the history pass (fast, and strictly
less safe); `--max-content-files N` moves the per-directory ceiling; `--denylist
PATH` points at a denylist kept outside the repo entirely.

The gate ships with the template as `.claude/scripts/leak-scan.py`. What does
*not* ship is its denylist: a list of real people, employers, handles and home
paths cannot live in a public repo, because publishing it publishes the very
thing it exists to protect. So the script loads its denylist at runtime from
`.claude/scripts/denylist.txt`, which is gitignored. **The mechanism is public;
the names are yours.** `.gitleaks.toml` follows the same rule from the other
direction: it is committed, so it must never contain a real name — its header
says so, and it exists only to configure secret rules.

## 2. What leak-scan.py checks, and how to write a denylist that works

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

- **Identity strings** — absolute home paths (`/Users/<name>`, `/home/<name>`),
  anything address-shaped, and document or calendar URLs that embed an id.
  Personal wikis accumulate these in meeting notes without anyone deciding to put
  them there, and no secrets scanner treats a shared-document id as sensitive —
  gitleaks will not flag one. Matched values are masked in the output, so the gate
  never reprints a live string into a CI log.
- **Credentials — mostly gitleaks' job now.** The AWS, GitHub, Google-API and JWT
  rules are gone (section 1), each removed only after gitleaks was run against a
  fixture holding exactly that credential class and observed to report it. Five
  rules stay, because gitleaks measurably misses them: `api-token`,
  `slack-token`, `secret-assignment`, `private-key`, `long-hex`. Matched values
  are masked in the output, so the gate never reprints a live secret into a log.
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

Both exist only to keep the retained `long-hex` rule usable. They are coupled:
**if you ever delete `long-hex`, delete these two with it**, and if you keep it,
keep them. gitleaks needs neither — measured 2026-07-30, the two SHA-pinned
actions in `.github/workflows/wiki-lint.yml` produce 0 gitleaks findings, because
entropy analysis distinguishes a git SHA from a key and a bare character-class
regex cannot. That contrast is the whole argument for the split.

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
gitleaks git . --config .gitleaks.toml --redact=80
```

The gitleaks line is the same command `.github/workflows/gitleaks.yml` runs, and
it is the one gate here that also runs on the *private* vault every push — a
secret can land in any file, so that workflow deliberately carries no `paths:`
filter. Note what CI cannot do: `leak-scan.py` has no CI job, because its denylist
is gitignored and CI has no copy. The identity half of the gate is yours to run by
hand, every release, from section 1.

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
> Last verified 2026-07-30: **11**, and the eleven folder names above match the
> output exactly. Re-verify anyway — the point of the check is that it is cheap
> and the failure is silent.
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
4. Run **both** halves of the privacy gate, from inside the assembled tree, in
   order — `gitleaks git . --config .gitleaks.toml --redact=80` for secrets, then
   `python3 .claude/scripts/leak-scan.py . --expect-single-commit` for identity and
   structure. Fix findings. Re-run until both exit 0. Neither one alone clears you
   to push: gitleaks cannot see a name in a commit message, and leak-scan.py no
   longer carries provider-token rules (section 1).
5. Run the CI gates locally.
6. Skim the diff by eye — the gate catches what you told it to catch, and a
   release is where you discover the term you never added to the denylist.
7. Squash to a single commit, then run
   `git log --all --format='%an|%ae|%cn|%ce' | sort -u` and read every line
   before pushing. Author *and* committer, on every commit and every ref.
8. Push. Re-run the gate against the pushed tree once, as a receipt.
