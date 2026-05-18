# M2 Concept Development — Top-Band Preparation Checklist

**Milestone:** M2 — Concept Development (5%)
**Format:** Milestone Review Session (15–20 min progress meeting, DoC + RCA tutors)
**Due:** Friday 29 May 2026
**Clinic hours (use these):** Tuesday 26 May and Wednesday 27 May

> Goal: walk into the room with meaningful, interlinked mock-ups that have been
> stress-tested with real people in interactive sessions, plus a live CD-deployed
> walking skeleton that prototypes a core context-relevant interaction.

---

## Criterion 1 — Visual Representation of the Digital Touchpoint (mock-ups for real people)

**Top-band descriptor:** _"Meaningful mock-ups with clear interlinked core interaction."_

### Actions

- [ ] Produce a set of paper (or low-fi digital) mock-ups covering every screen/state
  involved in the single most critical user interaction (e.g. the moment two users
  interact in real time) — not a general site-map or landing page only.
- [ ] Draw explicit navigation arrows / interaction links between screens so the
  flow of the core interaction is visually self-evident without verbal explanation.
- [ ] Annotate each screen with the user goal it serves, referenced back to your
  persona(s) and "How Might We" statement from M1.
- [ ] Prepare at least one alternative design variant for the core interaction screen
  (divergent thinking) to show deliberate design choice, not guessing.
- [ ] Photograph / scan all paper artifacts at high resolution and organise them into
  a shareable folder (Miro board, Figma file, or PDF) before the session.
- [ ] Do a 5-minute internal walk-through: can a team member who did not draw the
  mock-ups narrate the user journey solely from the visual? Fix any gaps.

### Common pitfalls that drop a band

- Showing a generic site-map or a list of screens with no interaction arrows — this
  lands in band 2 ("generic, abstract, or unfocused site-map").
- Mock-ups exist but there is no clear central interaction — tutors see a collection
  of screens rather than a coherent touchpoint.
- Static wireframes only (no indication of what happens when a user taps/clicks).

### Evidence / artifact

A physically or digitally shareable set of annotated, interlinked mock-up screens
(paper photos, Miro board, or Figma prototype link) shown live in the session.

---

## Criterion 2 — How Have Real People Interacted with the Paper Mock-up?

**Top-band descriptor:** _"Rich multidimensional and interactive feedback, presented via relevant excerpts."_

### Actions

- [ ] Recruit a minimum of 3 real participants from your target stakeholder group
  (not teammates, not family unless they are genuinely representative users).
- [ ] Run structured paper-prototype walkthroughs: give each participant a task
  ("pretend this is the app — can you [core task]?") rather than asking them to
  comment on visuals passively.
- [ ] Use a "think-aloud" protocol: ask participants to narrate what they expect to
  happen at each step and record their spoken responses (audio or written notes).
- [ ] Capture at least two dimensions of feedback per session: e.g. task completion
  behaviour (what they actually did), verbal reaction (what they said), and
  emotional response (confusion, delight, hesitation).
- [ ] Document feedback as direct, attributed quotes and annotated photographs of
  the interaction moment — not paraphrased summaries.
- [ ] Curate 3–5 of the most revealing excerpts (quote + photo or sketch) into a
  one-page synthesis ready to show in the session.
- [ ] Note any unexpected use patterns or workarounds participants invented — these
  are top-band signals.

### Common pitfalls that drop a band

- Emailing a screenshot and asking for written comments (email/WhatsApp/survey) —
  this is explicitly band 2 ("only static or high-level feedback").
- Running the session but presenting feedback as a generic list ("users liked X,
  disliked Y") without excerpts — lands in band 3 ("lacking clarity or focus in
  its presentation").
- Using only one participant or only teammates.

### Evidence / artifact

A curated excerpts document or slide: 3–5 direct quotes with context, plus photos
or sketches of the live interaction moments, ready to show tutors in the session.

---

## Criterion 3 — Quality of Feedback and Validation of the Concept

**Top-band descriptor:** _"Deep discussion with users about how the digital touchpoint would work in reality. Might lead to interaction with additional stakeholder groups."_

### Actions

- [ ] Design your testing sessions around scenario-based questions about reality of
  use: "When would you actually open this?", "What would stop you using this?",
  "Who else in your workplace/life would need to see this?".
- [ ] Push past surface aesthetics: if a participant comments on font or colour,
  redirect — "if the visuals were exactly what you wanted, would this workflow
  actually solve your problem?".
- [ ] For each participant session, write a one-paragraph "so what?" synthesis
  immediately after: what does this tell us about whether the concept works in
  their real context?
- [ ] Identify at least one concrete design change the feedback demands (not
  cosmetic) and be ready to articulate it in the session: "User X showed us that
  our assumed flow breaks at step 3, so we are redesigning Y."
- [ ] If the feedback surfaces a second stakeholder group you had not originally
  considered, plan and conduct (even a brief) interaction with that group before
  29 May — this is the explicit top-band differentiator ("might lead to interaction
  with additional stakeholder groups").
- [ ] Prepare a Testing Plan Canvas (Playbook tool) that records: hypothesis tested,
  method used, participants, key findings, and design implications.

### Common pitfalls that drop a band

- Feedback that is only about layout/font/colour ("superficial engagement") — band 2.
- Good depth of discussion but no clear link back to context of use or design
  decisions — band 3 ("detailed discussion but lacking focus or context of use").
- Validating with only one stakeholder type when your touchpoint clearly affects
  multiple groups.

### Evidence / artifact

A completed Testing Plan Canvas plus a "feedback-to-decision" trace: a visible
record showing which specific user insight drove which specific design change in the mock-ups.

---

## Criterion 4 — Preparing the Development Process for the Digital Touchpoint

**Top-band descriptor:** _"Functioning CD system."_
_(Progressive criterion — each band builds on the previous: Git repo → CI build → public deployment → CD.)_

### CI/CD Pipeline Checklist

- [ ] **Git repository:** Public or tutor-accessible repo on GitHub/GitLab; all four
  team members have committed at least once (verify with `git log --all --oneline`).
- [ ] **Branch protection:** `main` branch requires a passing CI check before merge
  (set in repo Settings > Branches).
- [ ] **CI build:** A CI workflow file (e.g. `.github/workflows/ci.yml`) runs on
  every push and pull request to `main`; the build must:
  - [ ] Install dependencies.
  - [ ] Run at least one automated test (unit or integration — even a smoke test
    that hits the app's root route counts; zero tests = no CI credit).
  - [ ] Fail the build if the test fails (verify by deliberately breaking a test
    and checking the CI status turns red).
- [ ] **Public deployment target:** The app is accessible at a stable public URL —
  either a DoC CloudStack VM (`<name>.doc.ic.ac.uk`) or an equivalent public host
  (Render, Railway, Fly.io, etc.). The URL must load in a lab browser without VPN.
- [ ] **CD trigger:** Every successful merge to `main` automatically redeploys to
  the public URL without any manual step. Implement via:
  - GitHub Actions deploy job (runs after the CI job passes), **or**
  - A webhook from the repo to the CloudStack VM that pulls and restarts the server.
- [ ] **Smoke verification:** After a test CD run, confirm the live URL serves the
  updated version (e.g. increment a visible version number in the UI and check it
  appears on the public URL within 5 minutes of merge).
- [ ] **Document the pipeline:** Add a one-paragraph description of the CI/CD setup
  to the repo README — tutors should be able to verify the pipeline exists without
  asking.

### Common pitfalls that drop a band

- CI workflow file exists but no tests run (build always passes) — still only band 2.
- App is deployed manually each time (no automated trigger on push/merge) — band 3
  ("full public deployment" but not CD).
- The public URL requires Imperial VPN — tutors cannot verify it independently.
- Only one team member has commit history — raises questions about integration.

### Evidence / artifact

- Live public URL shown in the session, loading the current build.
- CI/CD status badge in the repo README showing the last build passed.
- GitHub Actions (or equivalent) run log showing: test step passed → deploy step
  triggered → deployment confirmed.

---

## Criterion 5 — Preparing a Walking Skeleton for the Digital Touchpoint

**Top-band descriptor:** _"Current state prototypes a core context-relevant interaction of your digital touchpoint."_

### Actions

- [ ] Identify the single most distinctive interaction of your touchpoint — the one
  thing no generic app (todo, map, login, hello-world) does. This is your walking
  skeleton target.
- [ ] Implement that interaction end-to-end (even crudely): front-end UI action →
  back-end logic → database write/read → response visible to a second user in
  real time. All four layers must be connected, not mocked.
- [ ] Ensure the interaction is context-specific: e.g. if your app connects food
  bank volunteers with coordinators, the skeleton should show a coordinator
  posting a shift and a volunteer claiming it — not a generic CRUD form.
- [ ] Verify multi-user behaviour: open the app in two browser tabs (or two
  devices) and confirm the core interaction works between them.
- [ ] Confirm the database persists state: restart the server and confirm the data
  is still there (no in-memory-only storage).
- [ ] Record a 60-second screen capture of the working skeleton interaction to use
  as a fallback if a live demo fails during the session.

### Common pitfalls that drop a band

- The app loads a page and displays static content, or only has a login screen —
  band 2 ("generic hello-world / todo / login app").
- The skeleton has a context-specific UI but no back-end or database connected —
  band 3 ("context-specific but lacks any context-relevant interaction").
- The demo only works locally — if it is not the deployed CD version, it does not
  count as evidence of criterion 4 either.

### Evidence / artifact

Live demo of the deployed skeleton performing the core context-relevant interaction
with at least two user roles or two clients visible simultaneously. Back up with the
screen capture if needed.

---

## Timeline and Logistics

| Date | Action |
|---|---|
| **Now → Tue 20 May** | Finalise and photograph mock-ups; recruit user testing participants. |
| **Mon 19 – Fri 23 May** | Conduct all paper prototype testing sessions; write up excerpts and Testing Plan Canvas. |
| **Mon 19 – Wed 21 May** | Wire up CI pipeline; write and pass at least one automated test. |
| **Thu 22 – Sun 25 May** | Implement core context-relevant interaction in the walking skeleton; connect all layers (FE + BE + DB). |
| **Mon 26 May (clinic)** | Use clinic hours to get tutor feedback on mock-ups and CD setup — fix gaps before the deadline. |
| **Tue 27 May (clinic)** | Final CD smoke test; rehearse the 15-minute session narrative (each criterion needs ~2 min coverage). |
| **Wed 28 May** | Full dry run of the session. Confirm public URL is live and stable. Prepare the excerpts slide. |
| **Fri 29 May** | M2 Milestone Review Session. |

**Session structure to aim for (15 min):**
1. Mock-ups walkthrough with interaction links explained (3 min)
2. User testing highlights — play excerpts, show photos (4 min)
3. Feedback-to-decision trace: what changed and why (2 min)
4. CD demo: merge a trivial commit live (or show run log) + public URL (3 min)
5. Walking skeleton live demo (3 min)

---

## Top-Band Summary — Highest-Leverage Moves

1. **Run interactive paper prototype sessions, not surveys.** The gap between band 2
   and band 4 on criteria 2 and 3 is entirely about whether users physically
   interacted with the mock-up in real time. Do this first — it takes the most
   calendar time to organise.

2. **Close the feedback loop visibly.** The single strongest signal of top-band
   quality is being able to say "User X told us Y, so we changed the mock-up from
   A to B." Prepare this trace before the session.

3. **Make CD fully automated — zero manual steps.** Tutors know the difference
   between "we pushed and redeployed manually" and a genuine CD trigger. The
   automated deploy step in GitHub Actions is one YAML block; do it properly.

4. **The walking skeleton must do something your problem uniquely requires.** If a
   tutor could mistake your skeleton for a generic CRUD tutorial, it is not
   context-relevant enough. Name the interaction after your users' actual task.

5. **Use clinic hours on 26–27 May as a rehearsal, not a rescue.** Come with
   something already working and use the time to polish presentation and get
   early feedback — not to fix a broken pipeline the day before.
