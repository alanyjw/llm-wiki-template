# Setup — start here

This guide takes you from "I just downloaded this folder" to "Claude can read
and search my wiki." It assumes **no coding experience**. You'll copy and paste
a few commands into a terminal — that's the hardest part.

There are four things to install (Obsidian, one Obsidian plugin, Node.js, qmd)
and then one script to run. Budget ~20 minutes the first time.

---

## What you're setting up, in plain terms

- **Obsidian** — a free app for reading and editing the notes. Optional but
  recommended; the notes are just text files, so any editor works.
- **Templater** — a free Obsidian plugin. The files in `templates/` are little
  scripts that ask you a question ("Speaker? Talk title?") and then file the new
  note in the right folder with the right name. Templater is what runs them.
  Without it they are inert text and inserting one does nothing.
- **Node.js** — a runtime that the search engine needs. You install it once.
- **qmd** — the search engine. It reads your notes so Claude can find things
  fast instead of opening every file.
- **Claude Code** — where you actually talk to Claude about your wiki.

The notes live in two folders: `raw/` (things you put in — never changed) and
`wiki/` (what Claude writes and maintains). `CLAUDE.md` is the rulebook Claude
follows.

---

## Step 1 — Install Obsidian (optional, recommended)

Download from [obsidian.md](https://obsidian.md) and install it like any app.
Then **Open folder as vault** and pick this folder. You'll be able to browse the
notes with working links and image previews.

You can skip this and use any text editor — nothing here depends on Obsidian.

## Step 2 — Install the Templater plugin

**Don't skip this if you installed Obsidian.** It is the one step whose absence
looks like nothing is broken: you insert a template, nothing happens, and there
is no error message to search for.

In Obsidian, with this folder open as your vault:

1. **Settings** (the gear, bottom-left) → **Community plugins**.
2. If you see *"Community plugins are currently turned off"*, click **Turn on
   community plugins**.
3. Click **Browse**, search for **Templater**, open it, then **Install** →
   **Enable**.
4. Go back to **Settings** → **Templater** (it now appears in the left sidebar
   under *Community plugins*) and set **Template folder location** to
   `templates`.

Test it: open the command palette (`Cmd/Ctrl+P`), run **Templater: Create new
note from template**, and pick `daily-reading`. It should prompt you for a
source and then create a dated note under `raw/captures/daily/`. If it instead
drops a block of `<%* ... %>` text into your note, the plugin isn't enabled.

> `.obsidian/community-plugins.json` records that **Templater** is the plugin
> this vault expects. `.obsidian/templates.json` points Obsidian's *built-in*
> Templates plugin at the same folder, as a fallback for anyone who prefers it —
> it is a different plugin and configures nothing about Templater. Neither file
> installs or configures Templater, and plugin *code* is never committed, so
> step 2.4 above is required, not belt-and-braces.

## Step 3 — Install Node.js

Go to [nodejs.org](https://nodejs.org) and download the **LTS** version (the big
green button). Install it with all the default options.

To check it worked, open the **Terminal** app (on Mac: press `Cmd+Space`, type
"Terminal", hit Enter) and paste:

```
node --version
```

If you see a version number (like `v22.11.0`), you're good.

## Step 4 — Install qmd (the search engine)

In that same Terminal window, paste:

```
npm install -g @tobilu/qmd
```

This downloads the search engine. It may take a minute. To confirm:

```
qmd --version
```

A version number means success.

## Step 5 — Run the setup script

You need to be "in" this folder in the Terminal. The easiest way:

1. Type `cd ` (the letters c, d, then a space) but **don't press Enter yet**.
2. Drag this folder from Finder onto the Terminal window — it pastes the path.
3. Now press Enter.

Then run:

```
./setup.sh
```

This creates the search index and tells qmd about every notes folder. The first
run downloads a small AI model for semantic search, so it can take a few
minutes. When it finishes you'll see **"Setup complete."**

> If you get `permission denied`, run `bash setup.sh` instead.

## Step 6 — Open it in Claude Code

Open this folder in Claude Code. When it asks whether to **trust the project and
its MCP servers**, say **yes** — that's what connects Claude to the search
engine (configured in `.mcp.json`).

Test it: ask Claude something like *"What's in my wiki so far?"* It should search
and answer.

---

## Step 7 — Make it yours

1. Open `CLAUDE.md`, find the **"About the Vault Owner"** section near the
   bottom, and replace the example profile with your own. The better this is,
   the sharper Claude's synthesis.
2. The vault ships one example page per type and one sample note, each marked as
   a stub. Delete them when you're ready for the real thing. The same goes for
   the single example entry in `wiki/reflections-log.md`.
3. Drop a note into `raw/` (or a subfolder) and tell Claude to **"ingest"** it.
   Things you *wrote* — a talk you gave, a post you published — go in
   `raw/authored/`; everything else is something you took in.

---

## Keeping search fresh

qmd indexes your notes once. After you add or change notes, the search index
needs a refresh. Either re-run `./setup.sh`, or run this shorter command from
this folder:

```
qmd update && qmd embed
```

Claude is told to do this automatically after it writes notes — but if you edit
notes by hand, run it yourself.

### Optional: refresh automatically after a `git pull`

Skip this unless you sync the vault across machines, or a scheduled agent pushes
to the remote. If you do, a `git pull` can drop dozens of new notes into `raw/`
and `wiki/` without qmd noticing, and search then answers from a stale index
without telling you.

`.claude/scripts/qmd-refresh-hook.sh` closes that window — but git hooks live in
`.git/`, which git never syncs, so **nothing installs it for you.** Run this once
per machine, from this folder:

```
chmod +x .claude/scripts/qmd-refresh-hook.sh
for h in post-merge post-rewrite; do
  printf '#!/bin/sh\nexec "$(git rev-parse --show-toplevel)/.claude/scripts/qmd-refresh-hook.sh" "$@"\n' > .git/hooks/$h
  chmod +x .git/hooks/$h
done
```

Check it worked with `ls -l .git/hooks/post-merge .git/hooks/post-rewrite` —
both should be listed as executable. After that, a pull that touches `raw/` or
`wiki/` re-indexes on its own and appends a line to `$TMPDIR/qmd-embed.log`.

Git hooks run without your shell's startup files, so if you installed Node
through nvm the hook may not find `qmd`. It prints
`qmd-refresh-hook: qmd not found` and exits harmlessly; fix it by running
`which qmd` and exporting `QMD_BIN=/that/path` in your shell profile. The hook
never fails a pull, whatever goes wrong.

---

## Checking the wiki for mistakes (optional)

Claude runs these before it commits, and GitHub runs them on every push. You
never *have* to run them yourself, but they are safe, read-only, and take a few
seconds:

```
npx markdownlint-obsidian-cli@1.1.0 "wiki/**/*.md" --vault-root wiki
python3 .claude/scripts/wiki-lint.py wiki/
python3 .claude/scripts/regenerate-index.py --check
```

The first needs nothing installed beyond Node.js from Step 3 — `npx` comes with
it and downloads the checker on the fly. Silence means everything passed.

---

## If something goes wrong

- **`command not found: qmd`** — qmd didn't install, or your Terminal can't find
  it. Re-run Step 4. If it still fails, fully quit and reopen Terminal.
- **`command not found: npm`** — Node.js isn't installed. Redo Step 3.
- **`command not found: bunx`** — you copied a lint command written for CI.
  [Bun](https://bun.sh) is not a prerequisite here; swap `bunx` for `npx`, which
  came with Node.js in Step 3 and runs the same pinned version. (Installing Bun
  also works if you'd rather: `npm install -g bun`.)
- **A template inserts `<%* ... %>` instead of asking questions** — Templater
  isn't enabled. Redo Step 2, and confirm **Template folder location** is set to
  `templates`.
- **Claude isn't finding notes** — make sure you opened *this* folder in Claude
  Code, that you said "yes" to trusting MCP servers, and that `./setup.sh`
  finished with "Setup complete." Run `qmd status` to confirm documents are
  indexed.
- **Claude says the qmd tools aren't available** — the Desktop app sometimes
  can't find `qmd` on its own. Find the full path by running `which qmd` in
  Terminal, then in `.mcp.json` replace `"command": "qmd"` with that full path
  (for example `"command": "/usr/local/bin/qmd"`). Reopen the project.

---

For the full design and conventions of the wiki, see `README.md` and `CLAUDE.md`.
