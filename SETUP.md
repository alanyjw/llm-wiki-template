# Setup — start here

This guide takes you from "I just downloaded this folder" to "Claude can read
and search my wiki." It assumes **no coding experience**. You'll copy and paste
a few commands into a terminal — that's the hardest part.

There are three things to install (Obsidian, Node.js, qmd) and then one script
to run. Budget ~20 minutes the first time.

---

## What you're setting up, in plain terms

- **Obsidian** — a free app for reading and editing the notes. Optional but
  recommended; the notes are just text files, so any editor works.
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

## Step 2 — Install Node.js

Go to [nodejs.org](https://nodejs.org) and download the **LTS** version (the big
green button). Install it with all the default options.

To check it worked, open the **Terminal** app (on Mac: press `Cmd+Space`, type
"Terminal", hit Enter) and paste:

```
node --version
```

If you see a version number (like `v22.11.0`), you're good.

## Step 3 — Install qmd (the search engine)

In that same Terminal window, paste:

```
npm install -g @tobilu/qmd
```

This downloads the search engine. It may take a minute. To confirm:

```
qmd --version
```

A version number means success.

## Step 4 — Run the setup script

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

## Step 5 — Open it in Claude Code

Open this folder in Claude Code. When it asks whether to **trust the project and
its MCP servers**, say **yes** — that's what connects Claude to the search
engine (configured in `.mcp.json`).

Test it: ask Claude something like *"What's in my wiki so far?"* It should search
and answer.

---

## Step 6 — Make it yours

1. Open `CLAUDE.md`, find the **"About the Vault Owner"** section near the
   bottom, and replace the example profile with your own. The better this is,
   the sharper Claude's synthesis.
2. The vault ships one example page per type and one sample note, each marked as
   a stub. Delete them when you're ready for the real thing.
3. Drop a note into `raw/` (or a subfolder) and tell Claude to **"ingest"** it.

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

---

## If something goes wrong

- **`command not found: qmd`** — qmd didn't install, or your Terminal can't find
  it. Re-run Step 3. If it still fails, fully quit and reopen Terminal.
- **`command not found: npm`** — Node.js isn't installed. Redo Step 2.
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
