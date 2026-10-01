# career-engine

A Claude Code project for running a job search: collect positions, score them against a personal
profile, and generate tailored CVs and cover letters.

**Status: private.** Everything personal lives in `user/` (gitignored, its own local repo);
`python engine/tools/doctor.py --share` finds no personal terms left in the engine. Onboarding for
a new user comes next.

**Once per clone:** `git config core.hooksPath engine/hooks` — installs the pre-commit guard that
refuses a commit putting personal content into the engine.

- `CLAUDE.md` — session instructions
- `engine/docs/ARCHITECTURE.md` — layout and tools
- `engine/docs/PIPELINE.md` — how collect → score → produce fits together
