# M3 — Iterative Development: Top-Band Preparation Checklist

**Assessment:** Milestone 3 Progress Meeting (5% of total grade)
**Format:** 15–20 minute Milestone Review Session with DoC + RCA tutors
**Due:** 5 June 2026
**Clinic hours:** 1–2 June 2026 (use these for last-chance feedback before the session)

---

## How to use this checklist

Work through all five criteria sections before the session. Every checkbox should be ticked — or you should have an explicit reason why it does not apply. The "Top-band summary" at the bottom lists the highest-leverage moves if time is short.

---

## Criterion 1 — Sprint Planning

> **Top-band descriptor:** "Clear evidence of agile and user-centred development in presentation of sprint's planning, AND the current sprint's planning is also clearly framed in the wider user journey."

### Checklist

- [ ] Maintain a visible, up-to-date project board (GitHub Projects, Jira, Trello, or equivalent) with columns for Backlog / In Progress / Done and sprint dates clearly labelled.
- [ ] Every task on the board for this sprint traces back to a specific, written user story in the format "As a `<user type>`, I want `<action>`, so I can `<benefit>`." — no task should exist without a parent user story.
- [ ] Prepare a slide or board view showing the sprint backlog for the *current* sprint (M3 sprint), explicitly naming the user story each ticket addresses.
- [ ] Show a user journey map (or service blueprint excerpt) on screen and annotate which sprint tasks correspond to which step of that journey — tutors must be able to see the sprint in its journey context, not in isolation.
- [ ] Document sprint velocity: what was planned vs. completed in the previous sprint, and what was carried over or de-scoped, with a one-line rationale for each change.
- [ ] Demonstrate that sprint prioritisation decisions were driven by user feedback from M2 testing — explicitly name the insight that caused each priority change.
- [ ] Be ready to explain, live in the session, how today's sprint goals move a specific user persona one step further along their journey.

### Common pitfalls (drop to lower band)

- Having a project board but tasks defined as engineering tickets ("implement login API") with no connection to a user need.
- Showing sprint tasks as a flat list with no reference to the user journey — tutors cannot see the wider context.
- Sprint priorities that appear arbitrary or driven by technical convenience rather than user insight.

### Evidence / artifact

A project board screenshot or live URL showing sprint tasks linked to user stories, plus a single slide placing the current sprint within the full user journey map.

---

## Criterion 2 — Digital Touchpoint (Designed for Real People)

> **Top-band descriptor:** "An engaging application, rich with meaningful and usable context-relevant interactions."

### Checklist

- [ ] The live application (not a Figma prototype) is runnable in a lab-machine browser or on a loanable device — verify this before the session day.
- [ ] At least two distinct interactions are demonstrably context-relevant: they reflect a real behaviour, pain point, or workflow step that you discovered in field research with your specific stakeholder group (not a generic CRUD interaction).
- [ ] Multi-user functionality is visible in the demo: show two concurrent sessions, a real-time update, a shared state, or a collaboration feature — whichever is most natural for your problem domain.
- [ ] The interface uses real, realistic data (names, content, quantities) drawn from your context — not "User 1 / Item A" placeholders — so the scenario reads as believable to tutors who know nothing about your project.
- [ ] Prepare a 3–5 minute live demo walkthrough that narrates a specific user persona completing a meaningful task end-to-end, including any database state that persists across the session.
- [ ] Identify and be ready to articulate one interaction that was redesigned specifically because of user feedback received since M2 — this demonstrates the "designed for real people" loop is active.
- [ ] Confirm CI/CD is live: a push to main triggers a build and deploys to your CloudStack VM or equivalent — be able to show a recent pipeline run during the session.

### Common pitfalls (drop to lower band)

- Demoing a static interface or Figma walk-through instead of the running application.
- Interactions that are context-specific in appearance but generic in behaviour (e.g., a chat box that looks themed but has no project-domain logic).
- No visible multi-user or real-time element — the application looks single-player.

### Evidence / artifact

Live deployed application URL + a recent CI/CD pipeline success log (screenshot or browser tab open during the session).

---

## Criterion 3 — How Have Real People Interacted with the Digital Touchpoint

> **Top-band descriptor:** "Rich multidimensional feedback and application of clear/specific customised HCD data gathering methods in sessions with users."

### Checklist

- [ ] Conduct at least one in-person or live-video user testing session with your deployed application (not a mock-up) before 5 June — recruit participants who are genuine representatives of your persona, not teammates or housemates.
- [ ] Design a customised HCD data-gathering method for this round of testing — for example: a tailored think-aloud protocol with context-specific probes, a Testing Plan Canvas, a task-observation sheet mapped to specific journey steps, or a reaction card set built around your domain vocabulary.
- [ ] Capture at minimum two data modalities: e.g., verbal comments (recorded or transcribed) plus behavioural observations (noted by a second team member watching task completion), or verbal plus a quick post-task emotional rating mapped to specific interactions.
- [ ] Curate 3–5 direct user quotes or short video/audio excerpts that are specific to interactions in your application — not general impressions of the concept.
- [ ] Present the feedback as analysed insight, not raw transcript: cluster findings by theme, annotate which application interaction each theme relates to, and state what the finding implies for the next sprint.
- [ ] Show evidence that the testing session was structured (a brief session guide, consent note, or prompt card) — this demonstrates "customised HCD methods" rather than an ad-hoc conversation.
- [ ] If remote testing was necessary, use a synchronous tool (Zoom with screen-share, Lookback, Maze with verbal commentary) — asynchronous survey responses alone will not reach the top band.

### Common pitfalls (drop to lower band)

- Feedback collected only via WhatsApp message, email, or a Google Form — this is static/high-level and explicitly named in the bottom band.
- Rich feedback presented without structure or connection to specific application interactions ("they liked it overall" is not multidimensional).
- No evidence of a designed method — the session looks like a friendly chat rather than a planned HCD activity.

### Evidence / artifact

A session guide or Testing Plan Canvas + 3–5 labelled excerpts (quotes/clips) mapped to specific application screens or interactions, plus a brief affinity-mapped or themed synthesis slide.

---

## Criterion 4 — Quality of Feedback and Validation of the Idea

> **Top-band descriptor:** "Feedback provides a clear direction for the digital touchpoint towards being useful and helpful for a wide range of stakeholder groups."

### Checklist

- [ ] For each key piece of feedback received, state explicitly: (a) which interaction or feature it addresses, (b) what change it implies, and (c) which user story or persona it relates to — so the feedback is demonstrably actionable.
- [ ] Show that at least one concrete design or implementation change between M2 and M3 was directly caused by feedback — present the before/after side by side and name the user whose comment drove the change.
- [ ] Extend feedback analysis beyond the primary user persona: identify at least one implication for a secondary stakeholder group (e.g., an admin, a service provider, or a third-party beneficiary in your context).
- [ ] Avoid framing feedback only around aesthetics (colour, font, layout) — surface at least two pieces of feedback that concern functional interactions, task flows, or unmet needs in context.
- [ ] Synthesise feedback into a ranked priority list for the next sprint (M4), explicitly ordered by user impact — show this in your sprint planning view (links Criterion 1 and Criterion 4).
- [ ] If any feedback contradicted your assumptions, present it honestly and explain how it changed your direction — tutors reward intellectual honesty over cherry-picked positives.

### Common pitfalls (drop to lower band)

- Feedback that is entirely positive with no actionable direction — this signals superficial engagement rather than deep discussion.
- Feedback only from the primary user with no consideration of the wider stakeholder ecosystem.
- Detailed feedback presented but with no connection to how the touchpoint will evolve — the "validation of the idea" component is missing.

### Evidence / artifact

A one-page or one-slide feedback synthesis showing: raw insight → design implication → sprint action, covering at least two stakeholder groups.

---

## Criterion 5 — Thin Slicing Development

> **Top-band descriptor:** "Clear evidence of distinct thin slices in ongoing development and refinement of specific interactions."

### What a thin slice is

A thin slice is a **vertical cut through the full stack** that delivers one working interaction end-to-end. It must touch:

- **Front-end:** a UI component the user can interact with (button, form, real-time display, etc.)
- **Back-end:** a route or service that processes the interaction and applies business/domain logic
- **Database:** a read or write that persists or retrieves state for that specific interaction

**Example:** "A user posts a message in the shared channel" is a thin slice — it has a UI input (FE), a POST /messages endpoint (BE), and an INSERT into the messages table (DB). By contrast, building an entire database schema without any UI, or styling ten screens with no backend, is skewed development — the explicit failure mode named in the bottom band.

### Checklist

- [ ] Identify and name at least **three distinct thin slices** delivered or refined in this sprint — give each a one-line description stating the FE component, BE route/service, and DB table/collection involved.
- [ ] For each thin slice, show a before/after comparison (M2 state vs. M3 state) to evidence *refinement* of a specific interaction, not just feature accumulation.
- [ ] Present thin slices in order of user journey priority (mapped back to user stories) — not in order of technical implementation convenience.
- [ ] Demonstrate at least one slice live in the session that was refined based on user feedback from testing (links Criterion 3 → Criterion 5): run the actual app, perform the interaction, and narrate what changed and why.
- [ ] Show your git commit history or CI/CD pipeline logs to evidence that all team members contributed across the stack — this visibly counters the "skewed development" failure mode.
- [ ] Confirm that no thin slice is purely cosmetic: each must include a backend state change or retrieval — a restyled button with no backend change is not a thin slice.
- [ ] In your sprint board, label each ticket with its layer (FE / BE / DB) so the vertical balance is visible at a glance to tutors.

### Common pitfalls (drop to lower band)

- Building many features shallowly (lots of screens, no backend) or building deep backend infrastructure with no user-facing interaction — both are skewed development.
- Presenting a single thin slice as evidence of thin slicing — the top band requires *distinct* (plural) slices showing *ongoing* development.
- Prioritising feature count ("we built eight things") over interaction quality ("we refined this one interaction until it works well for users").

### Evidence / artifact

A sprint board screenshot with FE/BE/DB labels per ticket + a commit graph showing cross-layer contributions + a live demo of at least one refined thin slice during the session.

---

## Timeline & Logistics

| Date | Action |
|------|--------|
| Now – 30 May | Conduct user testing sessions with deployed app; gather and synthesise feedback |
| 30 May – 1 June | Close this sprint's development; finalise thin slices; update sprint board |
| **1–2 June** | **Clinic hours — bring your board, testing excerpts, and demo for tutor feedback before M3** |
| 3–4 June | Prepare and rehearse the 15–20 min session; ensure live demo runs on lab machine |
| **5 June** | **M3 Milestone Review Session** |

**Session preparation checklist:**

- [ ] Rehearse the full 15–20 minute flow at least once with the whole team, timed.
- [ ] Assign speaking roles: who presents sprint planning, who runs the live demo, who presents user feedback, who explains thin slicing.
- [ ] Test the deployed app on a machine you did not develop on (simulates lab-machine conditions).
- [ ] Have all evidence tabs open and ready: project board, CI/CD pipeline, user feedback excerpts, git log.
- [ ] Prepare one backup slide or screenshot of each live element in case of network failure during the session.

---

## Top-Band Summary — Highest-Leverage Moves

1. **Link every sprint task to a user story AND to a step in the user journey map.** This single action simultaneously satisfies Criterion 1 (sprint planning framed in wider user journey) and signals to tutors that your development is genuinely user-centred. Without this, even a working application will drop Criterion 1 to the third band.

2. **Run a live, in-person user testing session with the deployed application and a designed HCD method before 1 June.** The jump from band 3 to band 4 on Criterion 3 is specifically gated on "customised HCD data gathering methods" — a think-aloud with a Testing Plan Canvas, task observation sheet, or domain-specific probe set distinguishes you from teams who ran a chat and called it user research.

3. **Demonstrate a before/after refinement of a specific thin slice, driven by user feedback.** This single demonstration ties together Criteria 3, 4, and 5 in one moment: it shows rich feedback (C3), actionable validation (C4), and thin-slice refinement rather than feature accumulation (C5). It is the single highest-leverage moment in the session.

4. **Show multi-user / real-time functionality in the live demo with realistic, context-specific data.** An application that demonstrably has two concurrent users interacting in a domain-specific scenario immediately signals "engaging, rich with meaningful and usable context-relevant interactions" — the exact top-band language for Criterion 2.

5. **Use clinic hours on 1–2 June to get tutor eyes on your draft session.** Tutors at clinic can tell you in 10 minutes whether your evidence of agile + HCD integration is reading as top-band or third-band — this is free calibration before the graded session.
