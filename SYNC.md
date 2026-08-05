# Syncing with the template

For anyone running a private wiki built from this template. The toolchain —
linters, CI gates, privacy scanners — lives upstream and is meant to be
*inherited*, not copy-pasted per instance. Your notes never move. Only the
tooling does.

Sync is one-directional by default: **down**. The upstream is public and every
instance is private, so a change flowing up is a publication event and gets the
full gate in section 5. A change flowing down is just a file.

Nothing here has to be remembered. `.github/workflows/template-drift.yml` runs
weekly and files one issue titled `template drift` when a shared file diverges.
You read the issue; you do not schedule anything.

## 1. Adopt the toolchain

Do this once, in the instance repo, on a clean tree.

1. Add the upstream and make it read-only. Three commands, in this order — the
   push URL must be disabled *before* anything fetches, so `git push template`
   is never a live path from a private vault to a public repo:

   ```
   git remote add template https://github.com/<org>/llm-wiki-template.git
   git remote set-url --push template DISABLED_public_repo
   git fetch --no-tags template
   ```

2. Take the mechanism itself. Nothing below works until these three files exist
   locally — a fresh instance has none of them:

   ```
   git checkout template/main -- .claude/scripts/template-drift.py \
     .github/workflows/template-drift.yml SYNC.md
   git commit -- .claude/scripts/template-drift.py \
     .github/workflows/template-drift.yml SYNC.md
   ```

   These three are themselves on the watch list, so future upstream changes to
   the sync mechanism arrive as drift like anything else.

3. Confirm the push URL. `git remote -v` must show `DISABLED_public_repo` on the
   push line. Every `pushurl` value must equal that string exactly — the guard
   reads them all, because git pushes to all of them. The drift script exits `2`
   if it does not, and the workflow fails the job on `2`.

4. Point CI at the same URL: **Settings → Secrets and variables → Actions →
   Variables → New variable**, name `TEMPLATE_REMOTE_URL`, value the HTTPS clone
   URL from step 1. There is no default; the job fails with an instruction if
   you skip this. No file is ever edited to change the URL.

5. Enable Issues (**Settings → General → Features → Issues**), then run it once:
   **Actions → template-drift → Run workflow**. A green run means adoption
   worked. Expect the first run to *report drift and file the issue* — that is
   success, not failure. "No actionable drift" comes later, once you have taken
   what section 3 lists.

Two silent GitHub behaviours to know: scheduled workflows are auto-disabled
after 60 days of repo inactivity, and never run in a fork unless you enable
them. Weeks of silence is not the same as weeks of no drift — check the Actions
tab before believing it.

## 2. What is shared and what is yours

The rows below mirror the `WATCH` list in `.claude/scripts/template-drift.py`.
**That list is authoritative**, not this table — run
`python3 .claude/scripts/template-drift.py --json` to print the live set, and
fix this table if the two ever disagree.

| Path | Owner | When it drifts |
|---|---|---|
| `.claude/scripts/template-drift.py` | upstream | Take upstream. This is how a new watched path — or a fix to this mechanism — reaches you. |
| `.github/workflows/template-drift.yml` | upstream | Take upstream. |
| `SYNC.md` | upstream | Take upstream — this document. |
| `.claude/scripts/wiki-lint.py` | upstream | Take upstream (section 3). Local rules belong in the config file, not here. |
| `.claude/scripts/wiki-lint.config.json` | **you** | Never reported as `DIFFERS`. Checked for presence only — your carve-outs are yours. |
| `.claude/scripts/regenerate-index.py` | upstream | Take upstream, then run it once — `--check` is a separate CI gate. |
| `.claude/scripts/check-date-updated.py` | upstream | Take upstream. |
| `.claude/scripts/qmd-refresh-hook.sh` | upstream | Take upstream. |
| `.claude/scripts/bump-markdownlint-obsidian.sh` | upstream | Take upstream — this is how a linter version bump reaches you. |
| `.github/workflows/wiki-lint.yml` | upstream | Take upstream. One known exception: the `npx` note in section 5. |
| `.github/workflows/gitleaks.yml` | upstream | Take upstream — gitleaks version + checksum bumps arrive here. |
| `.gitleaks.toml` | upstream | Take upstream. It must never hold a real name; that is why it is shareable. |
| `.obsidian-linter.jsonc` | upstream | Take upstream. Per-vault rule disables are a fork (section 4). |
| `templates/capture.md` | upstream | Take upstream, unless your capture shape genuinely differs — then fork it. |
| `templates/meeting.md` | upstream | Same. |
| `templates/video.md` | upstream | Same. |

Five things look shared and are not. Each is excluded for a reason:

- **`CLAUDE.md`** — 192 lines differ from one live instance. That is a rewrite of
  the vault's subject matter, not drift.
- **`README.md`** — 121 lines differ, same reason. It describes your wiki.
- **`wiki/`** — your notes. The entire point. Never synced in either direction.
- **`.claude/skills/`** — 1,900+ lines of domain prose injected into every
  session. Inheriting someone else's domain would poison yours.
- **`.claude/scripts/denylist.txt`** — gitignored by design. Publishing the list
  of names you are protecting publishes the names.

Genuinely useful edits to these still exist. They go up by hand, as section 5.

One caveat on `wiki-lint.config.json`, the file that keeps `wiki-lint.py`
byte-identical to upstream. Registering a page type under `extra_page_types`
with an empty required-key list means pages declaring that `type:` skip `FM004`
and `RU001` — the linter dispatches on the declared type, and nothing checks
that a page under `wiki/insights/` actually declares `type: insight`. This is
not new (the built-in `log` and `index` types work the same way), but it does
mean **a new type name is a reviewed change, not a config tweak**. The knob
cannot weaken an *existing* type: `extra_page_types` is union-only, so naming
`source` there can add required keys and never drop one.

## 3. Taking an upstream change

The drift issue names the paths and buckets each one. Three buckets are
actionable — `DIFFERS` (content diverged), `ABSENT HERE` (upstream added a file
you never took), `GONE UPSTREAM` (upstream retired it). `IN SYNC` and `IGNORED`
need nothing. Take the actionable ones one at a time.

1. Fetch: `git fetch --no-tags template`
2. Stage the upstream version: `git checkout template/main -- <path>`
3. Read what you just took: `git diff --cached`. Do not skip this. You are
   pulling code from a public repo into a private vault.
4. Run the three CI gates locally:

   ```
   npx -y markdownlint-obsidian-cli@1.1.0 "wiki/**/*.md" --vault-root wiki
   python3 .claude/scripts/wiki-lint.py wiki/
   python3 .claude/scripts/regenerate-index.py --check
   ```

   On layer 1, **any output means failure** — the vendor CLI exits 0 even while
   printing violations and has no flag to change that, so reading `$?` gives a
   false pass. Silence is the pass. CI gates it by parsing
   `--output-formatter json`. Layers 2 and 3 exit non-zero on their own.

5. Commit the path explicitly — `git commit -- <path>` — so a concurrent job's
   staged work is not swept into your commit.

A new upstream lint rule can red-line pages that passed yesterday. That is the
gate doing its job. Fix the pages, or fork the rule (section 4). Do not loosen
the linter in place — the next sync overwrites it and the drift check will keep
reopening the issue.

## 4. Forking a file permanently

Sometimes an instance genuinely needs its own version. Say so once, in writing,
in two places.

1. Add the path to `.template-sync-ignore`, one per line, **with the reason on
   the same line after a `#`**. A bare path is a mystery in six months:

   ```
   .obsidian-linter.jsonc   # OFM087 off: this vault's tags are numeric years
   ```

2. Note the same reason inside the forked file itself, near the top. The drift
   check goes quiet on that path, so the file is now the only place anyone will
   look.

3. Re-run `python3 .claude/scripts/template-drift.py`. The path should move to
   the `IGNORED` bucket, with your reason printed beside it. If the report ends
   with a `NOTE: ... path(s) not on the watch list (typo?)`, you misspelled the
   path and are ignoring nothing.

Forking is a real cost: you stop receiving upstream fixes for that file forever,
silently. Prefer fixing your content over forking a rule. For `wiki-lint.py`
specifically there is a cheaper move — put the carve-out in
`.claude/scripts/wiki-lint.config.json`, which is yours and is never
content-compared.

## 5. Sending a change upstream

**Manual only. There is no automation here and there will not be.** The upstream
is public; every instance is private. An automated push up would be a scripted
data-exfiltration path from a vault full of real names, employers, home paths
and document ids — and a public push is irreversible.

So: copy files by hand, into a scratch checkout of the upstream, and scrub
before anything moves.

1. Scrub gate — run this over the exact files you intend to copy, and read every
   hit. Swap `yourname` / `yourhandle` / `youremployer` for your own real terms;
   the last two alternations catch home paths and addresses as written:

   ```
   grep -rniE "yourname|yourhandle|youremployer|/(Users|home)/[a-z]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}" <paths>
   ```

   The home-path alternation is written as a character class on purpose. A
   literal example path here would be reported by `leak-scan.py`, which scans
   the tree this file ships in — same discipline as `RELEASING.md` section 1.

2. Anything the grep finds must be genericized before the copy, not after.
   "After" means it is already in a commit object.
3. Copy the scrubbed files into the upstream checkout. Files only — never a
   cherry-pick, because a commit carries your message, branch name and author
   identity with it.
4. Run the full release gate from `RELEASING.md` section 1 (`gitleaks` **and**
   `leak-scan.py`). The grep above is a first pass, not the gate.
5. Open the PR from the upstream checkout.

**Known backflow owed upstream.** The instances run
`npx -y markdownlint-obsidian-cli@1.1.0` for Layer 1; the upstream still runs
`bunx`. The instances are right — `bunx` fails to resolve that CLI under
bun >= 1.3.14. Until that lands upstream, `.github/workflows/wiki-lint.yml` will
show as drifted on every instance that already fixed it. Do not "resolve" that
drift by taking the broken upstream version.

## 6. Adding a new shared file

The shared set is defined in exactly one place: the `WATCH` list in
`.claude/scripts/template-drift.py`, upstream. To share a new file, add its path
to `WATCH` there and ship the file in the same change. Instances inherit the new
path automatically the next time they take `template-drift.py` itself — which
the check flags, because that script watches itself. No instance edits anything,
and no one has to be told. The one ordering rule: land the file before or with
the `WATCH` entry, never after, or every instance gets a drift issue for a path
that does not exist yet.
