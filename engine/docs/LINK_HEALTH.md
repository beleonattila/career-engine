# Link health — why a 200 is not proof

*Moved from `engine/docs/LINK_HEALTH.md` on migration; wording unchanged.*

Run `python engine/tools/link_check.py` (report-only) from the repo root; add `--apply` to write.
It checks every open lead scoring 50 or above on **either** `career_fit` or `skill_match` —
the same rule the dashboard uses to decide what to show.

**The measurement that forced this tool, 2026-08-16.** A plain "does the URL return 200?" sweep
called 50 open leads healthy. Re-checking properly found **20 of them dead — 40%**. The vault had
been ranking, planning around and reporting leads that no longer existed.

Two failure modes, both invisible to a naive check:

1. **LinkedIn `ad-library/job/detail/<id>` returns HTTP 200 for expired postings.** Of 24 LinkedIn
   leads that all returned 200, **16 were dead**. The canonical `linkedin.com/jobs/view/<id>` page
   is the one that tells the truth — it redirects with `trk=expired_jd_redirect` or renders "No
   longer accepting applications". Roughly half this vault's leads are LinkedIn URLs, so this
   single surface accounted for most of the rot. `link_check.py` always re-checks them there.
2. **A stored URL that was never a posting.** Search pages (`careers.astrazeneca.com/search-jobs`)
   and programme boards (`elegance.dtu.dk/recruitment`) cannot confirm or deny anything. These get
   `url_status: unresolved`, never `dead` — see the inbox-eval edge case for portal sources.
3. **A JS-rendered listings page that renders empty to an automated fetch.** This is the mirror
   image of failure 1: there, a dead posting returns 200; here, a live board returns *"We
   currently have no jobs available"* while roles are open. On 2026-08-16 an automated fetch of
   `career.gubra.dk/available-positions` reported zero openings; a real browser showed **six**.
   The empty state is the app shell, not the data. **Never conclude "no openings" from an
   automated fetch of a careers board** — that conclusion always needs a browser, exactly as a
   404 does. Modern ATS hosts (Emply, Teamtailor, Greenhouse embeds) are all prone to this.

**A 404 is not proof either** (CLAUDE.md link hygiene). The tool reports a bare 404 as
`DEAD_UNCONFIRMED` and refuses to archive it; confirm in a real browser first (§Browser pass),
then record it with `--browser dead`, or pass `--trust-404` to accept every bare 404 at once.

## Browser pass

The verdicts `link_check.py` cannot settle by fetching (`UNVERIFIED`, `DEAD_UNCONFIRMED`, and
every LinkedIn lead that is not explicitly dead) are settled by eye in the **built-in browser pane**
of the Claude desktop app (tools `mcp__Claude_Browser__*`). The pane keeps a persistent sign-in,
the same one `/linkedin` uses (`engine/skills/linkedin-profile-edit.md` §Start a session). That
matters: LinkedIn shows its expiry banner only to a signed-in viewer.

**Measured 2026-10-12, in the signed-in pane:** a 2-month-old lead showed *"No longer accepting
applications"* and no Apply button; a 5-day-old lead showed an **Apply** button and no banner. Both
had been `UNVERIFIED` to the tool. The pane sees what no fetch, and no logged-out browser, can.

1. `python engine/tools/link_check.py` (report only). Work the `DEAD_UNCONFIRMED`, `UNVERIFIED`
   and LinkedIn rows of `user/workspace/logs/link_check_latest.tsv`, highest `best_score` first.
2. For each, open the URL in the pane (`preview_start` with the url once, then `navigate` on the
   same `tabId`). For LinkedIn use the canonical `linkedin.com/jobs/view/<id>` form. Wait ~2.5 s,
   then read with `javascript_tool`:
   - **dead:** a phrase from `GONE_MARKERS` in `link_check.py` (on LinkedIn: *"No longer
     accepting applications"*), or the posting is gone and the page redirects to a search or home;
   - **live:** the posting renders with an **Apply / Easy Apply** button (or the ATS's apply form)
     and no gone-marker;
   - **neither** (sign-in wall, captcha, an empty careers board): leave it `UNVERIFIED`. A pane
     not signed in to LinkedIn proves nothing about a LinkedIn lead.
3. Record each verdict, one lead per call. This writes exactly what an automatic verdict writes
   (fields, Notes line, the move to `closed/`), with "browser pane: <why>" as the reason:

   ```
   python engine/tools/link_check.py --browser dead --only <file-stem> --why "<what the page showed>"
   python engine/tools/link_check.py --browser live --only <file-stem> --why "<what the page showed>"
   ```

   `--only` must match exactly one lead. Active applications are never retired.
4. Keep a human pace on LinkedIn (a few seconds a page, as the tool's `--linkedin-delay` does), and
   batch big passes across sessions. If a site approval is declined, stop and say so.

**Three LinkedIn states, not two** (first full pass, 2026-10-12: 71 leads → 51 live, 8 dead,
12 paused):
- *"No longer accepting applications"* in the job header (the text above "About the job") → dead.
  Read the header, not the whole page: the sidebar lists other jobs.
- *"Not currently accepting applications"* → **paused, not dead**. The employer has stopped
  applications on LinkedIn for now and may reopen them. Leave it `UNVERIFIED` and check the
  employer's own careers page. It is not in `GONE_MARKERS`, on purpose.
- Neither, with an Apply / Easy Apply button → live.

When the header also says *"Responses managed off LinkedIn"*, the closure is LinkedIn's listing.
The employer's own call can outlive it, so check the employer's site before retiring a high-fit
lead.

**Doing a whole pass.** One page at a time costs two tool calls a lead. Faster: from any open
`linkedin.com` page, load each `jobs/view/<id>` into a hidden **same-origin iframe**, wait ~3 s,
read `contentDocument.body.innerText`, then remove the frame. Limits learned the hard way:
- `javascript_tool` stops at **45 s**, so do 4–5 leads per call and return the results each time.
  Never keep results only in page memory.
- **Reload the page before every batch.** The tab's renderer crashed twice after 30–40 frames,
  losing everything held in the page.
- Keep the pass's tab in front: background tabs throttle timers, and the batch overruns.

A careers board an automated fetch saw as empty (failure 3) goes the same way. Open the board in
the pane, let it render, and count the roles before concluding anything. Only HTTP 410, an explicit "no longer available" message, or LinkedIn's expiry
redirect count as `DEAD` outright.

**⚠️ Correction, 2026-08-16 (later the same day): the canonical LinkedIn page does not tell the
truth to a bot either.** The user found the Genmab computational-protein-design role marked
*"No longer accepting applications"* in a browser, on a lead `link_check.py` had stamped
`url_status: working` that morning. Measured directly: the fetched canonical page was 233KB of
full job description, carried **no expiry text at all**, did not redirect, and had no
`validThrough` or job-state field. It was indistinguishable from three other LinkedIn leads.
**LinkedIn gates the expiry banner behind authentication, so it never reaches an
unauthenticated fetch** — not even a real logged-out browser, which was tested separately and
showed neither an expiry marker nor an apply affordance on live and dead postings alike. Note
the banner wording matches the marker list already in the tool; the marker was never at fault. The `expired_jd_redirect` form of expiry *is* catchable, and is how the 16 above were
found, but it is only one of at least two presentations.

`link_check.py` no longer reports any LinkedIn lead as `ALIVE`: it resolves to `DEAD` on an
explicit signal, otherwise `UNVERIFIED`, meaning *open it in a logged-in browser*. **The 7 open
LinkedIn leads at fit ≥ 50 currently stamped `working` are unproven** and need a browser pass
(§Browser pass below: the desktop app's browser pane, signed in to LinkedIn).

Nothing is deleted. `--apply` stamps `status: expired` / `expired_on` / `url_status: dead`, adds a
dated Notes line recording *how* it was verified, and moves the file `open/` → `closed/` — the same
contract as `expire_sweep.py`, so the record survives for `dedup_check.py` and the miss telemetry.
Leads that are `applied`/`sent`/`interviewing`/`offer` are never touched.

Report lands in `user/workspace/logs/link_check_latest.tsv`.

**The third failure mode: a lead nothing can retire (measured 2026-08-29).** Link rot is not the only
way the open set overstates itself. `biohub_computational-biologist-cellxstate_2026-06` was found
sitting in `user/workspace/positions/open/` at **83 days old**, and no tool in the vault could have removed it:

- `expire_sweep.py` skipped it — it has `deadline: null`, and the sweep correctly never expires a
  null deadline. Worse, it skipped it with a bare `continue` *before counting it*, so the lead was
  not merely un-retired but **invisible**.
- `link_check.py` would have flagged it, but its stamp was stale: `url_status: working`,
  `url_checked: 2026-08-16` — written by the version of the tool superseded **that same day** by the
  correction above. The current tool cannot emit `working` for a LinkedIn lead at all.

The scale, on 85 open leads: **66 (78%) have `deadline: null`** — so the deadline sweep structurally
cannot police most of the vault — **35 of those are over 60 days old**, 13 are 83+ days, **7 carried
the impossible `working` verdict** (corrected to `unverified` on 2026-08-29), and **26 of 37 LinkedIn
leads were still stored in the ad-library form** the canonical-URL rule forbids.

**Resolution — age retirement at 45 days (the user's decision, 2026-08-29).** Rather than carry an
accurate-but-unmanageable open set, `expire_sweep.py` now retires deadline-less leads older than
**45 days on age alone**. This is a deliberate override of the expiry rule above: **none of these
postings was confirmed removed and some are certainly still live.** The trade was chosen knowingly —
a smaller, colder active set beats a large one nobody can verify.

Safeguards, so it stays reversible:
- nothing is deleted; records move `open/` → `closed/` exactly as a deadline expiry does;
- every age-retirement is stamped **`expired_reason: stale_no_deadline`** — a deadline expiry has no
  such field, so the whole set is one `grep -l` away from being restored;
- each record gets a dated Notes line stating it was retired on age and **not** confirmed dead;
- `--keep-stale` disables it for a run; `--stale-days N` retunes the threshold for one run, and
  `thresholds.stale_days` in `user/settings.toml` sets it for good.

**First run: 39 leads retired, `user/workspace/positions/open/` 85 → 46.** The cost is concentrated in the best
records — `hzdr_postdoc-generative-ai-denovo-protein-design` (career_fit **95**),
`latent-labs_computational-protein-designer` (**93**), `flagship-fl106` (**90**),
`meso-scale-diagnostics` (**90**), `servier-symphogen` (**90**), `dsm-firmenich` (**88**, **85**).
If any of those matter, revive them from `closed/` and verify the link rather than letting the
sweep decide.

**Bug found and fixed in the same pass: the On-direction tile was never shown-filtered.** It counted
every record scoring ≥75 across the whole vault, including expired and closed leads — reading **125**
while only **79** were visible anywhere on the page. It survived unnoticed because it drifted
slowly; the 39-lead retirement made it obvious when the tile did not move at all. `positive` is now
shown-filtered like every other tile, with the lifetime figure kept as `positive_all` and surfaced in
the footer note.
