# user/ — your personal folder

Made by `python engine/tools/init_user.py` from `engine/templates/user/`. Everything here is yours:
the engine repo ignores this folder, and it is its own local git repo (personal_data/ and secrets/
are kept out of that too).

Fill in, in this order (or ask Claude Code to interview you and fill them):

1. `profile/snapshot.md` — the short profile loaded every session. Put your name on the **Name:** line.
2. `profile/background.md` — education, experience, publications, your level, handling notes.
3. `profile/competencies.md` and `profile/soft_skills.md` — what you can do, with evidence.
4. `profile/preferences.md` — direction, target roles, and §Scoring (what the career_fit bands mean for you).
5. `settings.toml` — geography, thresholds, the domain pack, the career_fit checks.
6. `profile/search_terms.md` + `profile/search_terms.toml` — what the searches look for (keep the two in step).
7. `profile/cv_template/` — your master CV and cover letter in LaTeX; `profile/writing/` — your voice.
8. `profile/private_terms.txt` — words that must never reach the engine repo.
9. `personal_data/` — drop old CVs, transcripts, papers here (read-only sources, never versioned).

Then run `python engine/tools/doctor.py` from the repo root: it must end with 0 fail.
