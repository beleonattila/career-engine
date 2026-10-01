---
name: linkedin-profile-edit
cssclasses:
  - skill
recommended_model: Sonnet (medium effort)
description: |
  Edit the LinkedIn profile (or do any LinkedIn task) via agent-browser. Trigger on /linkedin, "update LinkedIn", "add an experience", "change a skill", or any LinkedIn task. agent-browser drives a HEADED Chrome that reuses the user's already-logged-in Chrome profile (--profile Default). The LinkedIn login form CANNOT be automated (LinkedIn blocks webdriver) — never try; reuse the logged-in profile instead.
---

# linkedin

Drives **agent-browser** to edit the live LinkedIn profile. **Recommended model:** Sonnet,
medium effort — it edits a live profile, so favor reliability over cheapness.

> **Hard-won context (2026-07-06).** LinkedIn actively blocks automated browsers from its
> **login form**: it detects `navigator.webdriver = true` and rejects all programmatic input
> (`fill`, `keyboard inserttext`, click-to-type) even non-headless. It also serves a blank,
> black-screenshot page to headless Chrome (`HeadlessChrome` UA). **So the login form and the
> auth vault do NOT work for LinkedIn — do not attempt either.** The way in is to reuse a
> Chrome profile that is *already* logged in. Full diagnosis in the memory note
> `agent-browser-linkedin-headless-block.md`.

Use `--session linkedin` on **every** command (keeps all commands on the same browser).

---

## One-time setup (already done, verify if broken)

1. `%USERPROFILE%\.agent-browser\config.json` must contain `"headed": true`. The `--headed`
   *flag* is ignored/buggy on this machine, but the *config key* works (makes launches
   non-headless — required, because headless is blocked by LinkedIn).
2. A **dedicated persistent LinkedIn profile** lives at
   `%USERPROFILE%\.agent-browser\profiles\linkedin`. The user logged into LinkedIn there once,
   by hand, in the headed window ("Keep me logged in" checked). It persists across restarts
   and is **independent of their everyday Chrome** — no need to close their main browser. This is
   the standard session; prefer it over `--profile Default` (which forces closing main Chrome).
3. **`--restore` is mandatory on every command.** It saves session cookies via CDP on close
   and restores them on launch — verified 2026-07-06 to survive a full close/relaunch.
   Without it, the login does NOT persist (Chrome doesn't flush the fresh cookie on abrupt
   close). Always launch with `--session linkedin --restore --profile "<path>"`.

To (re)seed the dedicated profile if the session ever expires: launch it headed on the login
page and ask the user to sign in **manually** in the visible window (real keystrokes work;
automated login is blocked). Never type their password or use `auth login`.

```powershell
agent-browser --session linkedin --restore --profile "$env:USERPROFILE\.agent-browser\profiles\linkedin" open https://www.linkedin.com/login
# → tell the user to log in in the visible window, then continue
```

---

## Start each session — reuse the dedicated profile

```powershell
agent-browser --session linkedin --restore --profile "$env:USERPROFILE\.agent-browser\profiles\linkedin" open https://www.linkedin.com/feed/
agent-browser --session linkedin wait --load networkidle
agent-browser --session linkedin screenshot
```

- Screenshot shows his **feed / name** → logged in, proceed.
- Screenshot shows a **login page** → the profile's session expired. Re-seed it (see setup
  above): ask him to log in by hand in the visible window. **Never** automate the login form.

If the first navigation on a fresh launch shows a **black screenshot / `about:blank`**, just
re-run `open <url>` once — the first paint on a cold profile sometimes doesn't settle.

If agent-browser keeps relaunching **headless** (UA shows `HeadlessChrome`), a stale daemon
is being reused: kill the daemon process `agent-browser-win32-x64.exe` and any chrome under
`Temp\agent-browser-chrome-*`, then relaunch.

---

## Interacting — plain fields vs. contenteditable

**Plain fields** (names, single-line inputs, dropdowns) — semantic locators work:

```powershell
agent-browser --session linkedin find role button click --name "Save"
agent-browser --session linkedin find label "First name" fill "<first name>"
```

**Rich-text fields (Headline, About) are `contenteditable` DIVs** — `fill` / `keyboard
inserttext` do **not** land on them (React ignores it). Use `execCommand` via `eval`, which
fires the input events React needs. Open the edit form by direct URL, then run the eval:

- Headline form: `<profile-url>/edit/intro/`
- About form: `<profile-url>/edit/forms/summary/new/`

```powershell
# 1. open the edit form (headline example)
agent-browser --session linkedin open <profile-url>/edit/intro/
agent-browser --session linkedin wait --load networkidle
```

Write the JS to a file, base64-encode it (base64 preserves unicode like `·` and `–`; use
`\n\n` between paragraphs for the About), and run with `eval -b`:

```js
// set_field.js
(function(){
  var el = document.querySelector('[contenteditable=true]');
  if(!el) return JSON.stringify({err:'no field'});
  el.focus();
  document.execCommand('selectAll', false, null);
  var ok = document.execCommand('insertText', false, 'NEW TEXT HERE');
  return JSON.stringify({ok: ok, now: el.textContent, len: el.textContent.length});
})()
```

```bash
b64=$(base64 -w0 set_field.js)
agent-browser --session linkedin eval -b "$b64"     # expect {"ok":true, ...}
```

Then screenshot to confirm the text + character counter, save, and verify it persisted:

```powershell
agent-browser --session linkedin screenshot
agent-browser --session linkedin find role button click --name "Save"
# reopen the edit form and read [contenteditable].textContent to confirm it stuck
```

Edits are **live**. Screenshot before saving and verify after — writes can be flaky
(`webdriver` stays true even headed). If an edit won't land, the browser window is visible —
ask the user to finish that one edit by hand.

---

## Rules

- **Always** use `--session linkedin --restore` on every command (`--restore` is what makes
  the login persist across restarts — verified; without it you get logged out on relaunch).
- **Never** run `agent-browser close` / `close --all` — leave the session for next time.
  (Exception: killing a stale headless daemon during the setup fix above.)
- If agent-browser errors or is unresponsive: **stop and ask the user to restart. Never retry.**
- **Never** automate the LinkedIn login form, type their password, or use the auth vault —
  LinkedIn blocks it. Always reuse the logged-in `--profile Default`.
- Keep local snapshot `user/profile/linkedin/LINKEDIN.md` in sync after any live edit.

---

## Profile URL

`<profile-url>` in the commands on this page is the user's profile URL, recorded in
`user/profile/linkedin/LINKEDIN.md` (the `URL:` line). Read it there; never guess it.

## Pending TODOs

They live in `user/profile/linkedin/LINKEDIN.md` — read them there before an editing session.

---

## Working efficiently

- **Division of labour.** agent-browser is reliable for **reading** — finding posts to
  comment on, reading job listings, reviewing a person's public activity, pulling analytics.
  Use it for scouting + drafting input. Do the **acting** — posting, commenting, connecting —
  **manually** (the user prefers this, and automating actions risks LinkedIn account flags).
- **Reads over screenshots.** Prefer `snapshot -i`, `read`, and `eval` to extract text —
  faster and cheaper. Use screenshots only to visually confirm a write landed.
- **Low velocity.** Keep automated navigation human-paced; LinkedIn watches request velocity.
  Batch profile edits into occasional sessions rather than many small ones.
- **Live oversight (optional).** `agent-browser dashboard start` → open `localhost:4848` to
  watch the viewport in real time while writes happen.

---

## Weekly stats snapshot (visibility-strategy tracking)

Log analytics weekly to `user/workspace/linkedin/linkedin_stats.csv` so the visibility strategy's
metrics show a trend. Read the numbers live, then append one dated row.

```powershell
# from the feed/profile, read the 7-day analytics + counts
agent-browser --session linkedin open <profile-url>/
agent-browser --session linkedin wait --load networkidle
agent-browser --session linkedin eval "document.querySelector('.pvs-header')?document.body.innerText:document.body.innerText"
# then append a row: date,profile_views_7d,post_impressions_7d,search_appearances_7d,connections,followers,notes
```

Fuller analytics (with sources) live at
`https://www.linkedin.com/analytics/profile-views/` and `.../search-appearances/`.
Track quality signals (who viewed, relevant search terms), not vanity likes — per the
visibility strategy. Columns and history are in `user/workspace/linkedin/linkedin_stats.csv`.

---

## Related
[[competencies]] [[soft_skills]]
