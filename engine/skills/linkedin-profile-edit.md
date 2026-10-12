---
name: linkedin-profile-edit
cssclasses:
  - skill
recommended_model: Sonnet (medium effort)
description: |
  Edit the LinkedIn profile (or do any LinkedIn task) in the Claude desktop app's built-in browser pane. Trigger on /linkedin, "update LinkedIn", "add an experience", "change a skill", or any LinkedIn task. The pane keeps its own persistent sign-in, which the user enters by hand once. The LinkedIn login form is never automated. Fallbacks: Claude in Chrome, then agent-browser.
---

# linkedin

Edits the live LinkedIn profile from the **built-in browser pane** of the Claude desktop app
(tools `mcp__Claude_Browser__*`). **Recommended model:** Sonnet, medium effort. It edits a live
public profile, so favour reliability over cheapness.

> **Why the built-in browser (switched 2026-10-12).** LinkedIn rejects browsers launched for
> automation: it reads `navigator.webdriver` and blocks programmatic login, and serves headless
> Chrome a blank page. agent-browser worked around that with a headed Chrome, a dedicated profile
> and `--restore` cookie saving, which was several moving parts that broke whenever Chrome moved.
> The built-in pane is a normal signed-in browser to LinkedIn. Verified 2026-10-12: it read every
> section, and edits to plain fields, rich-text fields and a publication all saved and persisted.

---

## Start a session

1. Load the browser tools in one ToolSearch call if they are deferred (query: the
   `mcp__Claude_Browser__` prefix).
2. Read the profile URL from `user/profile/linkedin/LINKEDIN.md` (the `URL:` line). Never guess it.
3. `preview_start` with `url: <profile-url>/` → keep the returned `tabId` for every later call.
4. `get_page_text`. A page titled **"Sign Up | LinkedIn"** or an `authwall` URL means the pane is
   not signed in:
   - `navigate` to `https://www.linkedin.com/login`;
   - call `tabs_context`. If it reports the pane **hidden**, ask the user to bring it back
     (**Ctrl+Shift+B**, or the globe icon in the side panel);
   - ask the user to **sign in by hand** with "Keep me logged in" ticked, and wait for them.
   The sign-in persists across sessions. **Never** type the password or fill the login form.

---

## Reading the profile

The main profile page renders only the top card (headline, location, Open to Work) and the
Activity feed. Read every other section from its own page:

| Section | URL (`<profile-url>` + …) | How to read |
|---|---|---|
| Top card, headline | `/` | `get_page_text` |
| About | `/edit/forms/summary/new/` | JS: `innerText` of `[contenteditable=true]` (this opens the edit form; close it by navigating away) |
| Experience | `/details/experience/` | JS: `document.querySelector('main').innerText` after a ~1.5 s wait |
| Education | `/details/education/` | same |
| Publications | `/details/publications/` | `find` the title; the edit form shows every field |
| Projects | `/details/projects/` | same as Experience |
| Skills | `/details/skills/` | ⚠️ **only the first 10 load here**, whatever you scroll. A full skills audit needs the user or a fallback browser |

Cut page text at `"Who your viewers also viewed"`. Everything after it is sidebar and footer.

**Finding an entry's edit form:** on a `/details/<section>/` page, list the links with
`[...document.querySelectorAll('main a[href*="edit/forms"]')].map(a => [a.getAttribute('aria-label') || a.innerText, a.href])`
and `navigate` to the one you want. Forms seen so far:

- Headline: `<profile-url>/edit/intro/`. The headline is a `contenteditable` DIV; name, country
  and industry are plain inputs.
- About: `<profile-url>/edit/forms/summary/new/`. `contenteditable`, **2,600-character cap**.
- Experience entry: `/details/experience/edit/forms/<id>/`. The description is `contenteditable`;
  there is a **"Notify network"** switch.
- Publication: `/details/publications/edit/forms/<id>/`. All plain inputs: title, publisher, date,
  URL, and a description textarea (2,000 cap).

---

## Editing

**Plain inputs and textareas** (publication fields, names): `find` or `read_page` with
`filter: interactive` for the `ref`, then `form_input`. React registers the value, and the
character counter updates.

**Rich-text fields (headline, About, experience descriptions) are `contenteditable` DIVs.**
`form_input` and typing do not reliably land on them. Use `javascript_tool` with `execCommand`,
which fires the input events React needs:

```js
// whole field (headline, About)
const el = document.querySelector('[contenteditable=true]');
el.focus();
document.execCommand('selectAll', false, null);
document.execCommand('insertText', false, NEW_TEXT);   // "\n\n" between paragraphs
```

```js
// one phrase inside a longer description: select just that text, then type over it
const el = document.querySelector('[contenteditable=true]');
const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
let n; while ((n = w.nextNode())) {
  const i = n.data.indexOf(OLD);
  if (i >= 0) { el.focus(); const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + OLD.length);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    document.execCommand('insertText', false, NEW); break; }
}
```

The headline form holds several fields, so pick the right element (for example, the one whose
`innerText` starts with the old headline) and check afterwards that name and country did not
change.

**Length:** paragraph breaks inflate `innerText`, so `innerText.length` overstates the count.
The truth is LinkedIn's own counter: read it with
`document.body.innerText.match(/[\d,]+\/2,600/)`. Draft to the cap *before* filling: a draft that
fits in a text file can still exceed 2,600.

**Before saving:**
- Experience entries: check the "Notify network" switch is **off** (`[role=switch]`, or a
  checkbox labelled "notify your network"), unless the user wants the change broadcast.
- Show the user the exact new text and get a yes, unless they already approved that text. Edits
  are live and public.

**Saving:** `find` "Save" and click it **by `ref`**, not by coordinate. A coordinate click missed
once and the edit was silently lost. Wait ~3 s before navigating anywhere. **Success signal:**
the URL moves to `/edit/forms/next-action/…` (a "people you may know" or Premium prompt). Ignore
it; never click inside it.

**Verify:** reopen the form (or the `/details/` page) and confirm the new text is there. A save
can fail without an error.

---

## Rules

- **Never** automate the login form, type a password, sign out, or change account settings.
  The sign-in belongs to the user.
- If a site approval is declined or the page is refused, say so and stop. Do not retry.
- **Low velocity.** Batch profile edits into occasional sessions, at a human pace.
- **Reading and editing the profile: automated. Acting socially: by hand.** Posts, comments,
  reactions and connection requests are the user's to do (their preference, and automated social
  actions risk account flags). Draft them here; the user posts them.
- Keep the local snapshot `user/profile/linkedin/LINKEDIN.md` in sync after any live edit, and
  record what was verified live and when.

---

## Fallbacks

**1. Claude in Chrome** (`mcp__claude-in-chrome__*`), if the user has Chrome with the extension.
It acts in their everyday Chrome with its existing LinkedIn sign-in. Load its skill
(`anthropic-skills:chrome-browser`) first. Use it for anything the pane cannot do, such as a full
Skills audit.

**2. agent-browser** (the old route, kept for reference; `.agents/skills/agent-browser/`).
- `%USERPROFILE%\.agent-browser\config.json` needs `"headed": true` and an `executablePath` that
  exists. **It broke on 2026-10-12** because Chrome was no longer at the configured path.
- Dedicated profile `%USERPROFILE%\.agent-browser\profiles\linkedin`, seeded once by a manual login.
- Every command: `agent-browser --session linkedin --restore --profile "<that path>" …`
  (`--restore` is what makes the sign-in survive a relaunch).
- A stale daemon relaunching headless (`HeadlessChrome` UA): kill `agent-browser-win32-x64.exe`
  and any chrome under `Temp\agent-browser-chrome-*`.
- Contenteditable fields: the same `execCommand` JS as above, via `eval -b <base64>`.
- If agent-browser errors: **stop and ask the user. Never retry.** Never `close --all`.

---

## Weekly stats snapshot (visibility-strategy tracking)

Log analytics weekly to `user/workspace/linkedin/linkedin_stats.csv`. Read the numbers live with
`get_page_text` from `https://www.linkedin.com/analytics/profile-views/` and
`…/analytics/search-appearances/`, plus followers and connections from the profile top card.
Then append one dated row:
`date,profile_views_7d,post_impressions_7d,search_appearances_7d,connections,followers,notes`.
Track quality signals (who viewed, relevant search terms), not vanity likes.

---

## Pending TODOs

They live in `user/profile/linkedin/LINKEDIN.md`. Read them there before an editing session.

## Related
[[competencies]] [[soft_skills]]
