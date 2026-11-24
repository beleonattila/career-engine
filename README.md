# career-engine

An agent project for running a job search: collect positions, score them against a personal
profile, and generate tailored CVs and cover letters. Built for Claude Code; works with any agent
that reads `AGENTS.md` (Codex, Cursor, Copilot, …).

Everything personal lives in `user/`, which this repo ignores; it is its own local git repo.
The engine (`engine/`, `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.agents/`) is generic.

## First run

Needs: [Claude Code](https://claude.com/claude-code) or another coding agent, Python 3.11+ (stdlib only), git, and a
XeLaTeX install with `latexmk` (MiKTeX or TeX Live) for the CVs. Built and tested on Windows.

1. Clone, then from the repo root make your personal folder:

   ```
   python engine/tools/init_user.py
   ```

   It copies the starter template (`engine/templates/user/`) to `user/`, makes `user/` its own git
   repo, and installs the pre-commit guard (`git config core.hooksPath engine/hooks`) that refuses a
   commit putting personal content into the engine.

2. Fill in your profile. The README inside your new `user/` folder lists the files in order. The easy way: open your agent
   in this folder, drop your old CV into `user/personal_data/`, and ask it to interview you and fill
   the `user/profile/` files from it. Put your name on the **Name:** line of
   `user/profile/snapshot.md`.

3. Edit `user/settings.toml` (geography, thresholds) and `user/profile/search_terms.toml` +
   `search_terms.md` (what to search for). The values shipped are examples.

4. Check it: `python engine/tools/doctor.py` must end with 0 fail.

5. Use the commands: `/search-positions` → `/inbox` → `/cv`, and `/dashboard`. In Claude Code they
   are slash commands; other agents find them as skills in `.agents/skills/`, or you name the skill
   file in `engine/skills/`.
   `engine/docs/CHEATSHEET.txt` has the one-page guide.

**Domain:** only one domain pack ships, `engine/packs/life_science/` (job boards, ATS seeds and term
synonyms for life science). For another field, copy that folder, edit it, and point `search.pack`
in `user/settings.toml` at it.

## Docs

- `AGENTS.md` — session instructions (Claude Code loads them through `CLAUDE.md`)
- `engine/docs/ARCHITECTURE.md` — layout and tools
- `engine/docs/PIPELINE.md` — how collect → score → produce fits together
