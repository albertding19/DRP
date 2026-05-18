# M4 — More Iterative Development: Top-Band Checklist
**Milestone 4 | 5% | Due: 12 June 2026 | Format: 15–20 min Milestone Review Session**

> Tutors expect: digital touchpoint shown to real users with high-quality feedback on a **more complete** UX; further agile sprint evidence driven by user stories and thin slicing; **plus** consideration of wider impact and quantitative evaluation of the end-product.

---

## Criterion 1 — Sprint Planning

> **Top-band descriptor:** "As previous [clear evidence of agile *and* user-centred development in presentation of sprint's planning], but current sprint's planning is also clearly framed in the wider user journey."

### Actions

- [ ] Present your project board (GitHub Projects / Jira / Trello) live or as a screenshot showing the sprint's backlog, in-progress, and done columns — each card must be a user story (format: "As a [persona], I want to [action] so that [goal]").
- [ ] For each completed user story in this sprint, draw an explicit link back to a specific step in your **user journey map** (e.g. "This story addresses Julia's 'Wait' stage pain point where she loses track of her queue position").
- [ ] Show a sprint retrospective artefact (even a brief bullet list) from the previous sprint whose outcomes visibly shaped this sprint's backlog.
- [ ] Demonstrate thin slicing: show that each story touches Front-End, Back-End, *and* DB — not just one layer. A simple table (story | FE | BE | DB) is sufficient.
- [ ] Annotate your sprint planning board with the specific persona(s) each story serves; the user journey map should be visible alongside the board in your presentation.
- [ ] Prepare a 1-slide "sprint narrative": opening state of the user journey → stories tackled → resulting UX improvement → next sprint direction. This frames the sprint in the wider journey at a glance.
- [ ] Confirm every member can speak to *why* a story was prioritised (not just *what* it does) — tutors may ask anyone.

### Common pitfalls that drop a band

- Showing a task board whose cards are technical tasks ("fix login bug", "add CSS") rather than user stories — this signals development not driven by user needs.
- Presenting sprint planning in isolation without connecting it to the user journey map or personas — the marker sees agile but not user-centred.
- Describing the previous sprint rather than the *current* sprint's planning.

### Evidence / artefact

A live or screenshotted project board with user-story cards, annotated user journey map, and the 1-slide sprint narrative slide shown during the review session.

---

## Criterion 2 — Digital Touchpoint (Designed for Real People)

> **Top-band descriptor:** "An engaging application, rich with meaningful and usable context-relevant interactions."

### Actions

- [ ] Ensure the app can be demoed live (deployed on DoC CloudStack VM or loanable device) with **real-time multi-user interactions** visible — e.g. two browser windows open simultaneously showing live state changes.
- [ ] Every screen shown must be context-specific to your problem domain — no generic placeholders, lorem-ipsum text, or off-topic UI elements.
- [ ] Demonstrate at least **three distinct context-relevant interactions** (not just navigation): e.g. a live notification, a collaborative action between two user roles, a database-driven personalised view — interactions that only make sense given *your* specific problem context.
- [ ] Show the "before" user journey (documented from early research) next to the "after" — i.e. how the touchpoint transforms the experience at specific pain points identified in your personas.
- [ ] Conduct a brief in-session usability walkthrough: a team member plays the role of your primary persona and narrates thoughts aloud as they complete a core task — this demonstrates the app's engagement in context.
- [ ] Verify that all thin-sliced features from this sprint are integrated and stable: no dead-end screens, broken real-time connections, or missing DB persistence during the demo.
- [ ] If the app has multiple user roles (e.g. admin + end-user), show an interaction that requires both roles simultaneously — this evidences "rich multi-user" design.

### Common pitfalls that drop a band

- Demo that is mostly static or narrated from screenshots rather than a live running app.
- Context-relevant screens but interactions that could belong to any generic CRUD app (e.g. a form submission with no real-time or collaborative element).
- App that works but feels disjointed — tutors distinguish "helpful interactions" (third band) from "rich and engaging" (top band); the difference is depth of feedback loops and contextual responsiveness.

### Evidence / artefact

Live running deployment accessible during the review session; screen recording as backup; annotated before/after user journey map.

---

## Criterion 3 — Quality of Feedback and Validation of the Idea

> **Top-band descriptor:** "Feedback provides a clear direction for the digital touchpoint towards being useful and helpful for a wide range of stakeholder groups."

### Actions

- [ ] Run at least **two structured user testing sessions** with real users (not team members or close friends) from at least **two distinct stakeholder groups** identified in your stakeholder map — document names/roles (with consent) to prove diversity.
- [ ] Use a **customised HCD data-gathering method** in each session rather than a generic survey: e.g. a Think-Aloud protocol, a customised Testing Plan Canvas, a card-sort on features, or a context-walk where the user uses the app in their actual setting.
- [ ] Synthesise feedback into an affinity diagram or themed insight board — show at minimum three distinct themes with representative user quotes, each explicitly connected to a design decision made or queued for the next sprint.
- [ ] For each stakeholder group, state one concrete design direction the feedback implies: "Group A's feedback tells us we need [X]; Group B's tells us we need [Y] — here is how these are prioritised in our next sprint."
- [ ] Include at least one piece of feedback that *surprised* you or *challenged* an assumption — and explain what you changed (or will change) as a result. This signals genuine engagement, not confirmation bias.
- [ ] Prepare 2–3 direct user quote excerpts (verbatim, attributed to a persona-type if needed for anonymity) to present during the review — these carry far more weight than paraphrased summaries.
- [ ] Demonstrate that feedback from M3 has already been acted upon in the M4 sprint — show the closed-loop: M3 feedback → user story → implemented feature.

### Common pitfalls that drop a band

- Feedback collected only via WhatsApp messages, online survey forms, or emoji reactions — these are surface-level and one-dimensional.
- Rich qualitative data collected but presented without a clear design direction — the rubric explicitly penalises "detailed discussion but lacking focus or context of use."
- Testing only with a single stakeholder group, making it impossible to claim usefulness "for a wide range of stakeholder groups."

### Evidence / artefact

Affinity diagram / themed insight board with direct user quotes; Testing Plan Canvas(es); consent record or anonymised participant log; slide showing closed-loop from M3 feedback to M4 feature.

---

## Criterion 4 — Designing for Positive Wider Impact (Impact Asset)

> **Top-band descriptor:** "Compelling vision and impact of the project proposition, including consideration of wider positive consequences."

### Actions

- [ ] Create at least one **impact asset** from the following options — it must be polished enough to stand alone as a communication piece:
  - **Cover Story mock-up:** design a fictional magazine front page (e.g. *WIRED*, *The Guardian*, *Time*) set 5 years in the future where your project has succeeded at scale. Headline, sub-headline, pull-quote from a user, and a product image. This forces you to articulate the *aspiration*.
  - **Future newspaper headline:** a single broadsheet-style headline + 3-sentence article lead set in 2031. More concise than a cover story but equally forward-looking.
  - **Campaign poster:** a public-facing poster for your product as if it were a real service launch — includes value proposition, target audience call-to-action, and visual identity.
  - **Service blueprint at scale:** show how the touchpoint integrates into a wider ecosystem (partner organisations, policy levers, community structures) if adopted broadly.
- [ ] Beyond the asset, articulate **wider positive consequences** explicitly — this is the differentiator between band 3 and band 4. Concretely address at least two of:
  - *Social equity*: does wider adoption reduce a disparity (access, income, disability)?
  - *Environmental*: does the product change behaviours that reduce waste, travel, or consumption?
  - *Economic*: does it create value for underserved groups or reduce systemic cost?
  - *Community / civic*: does it strengthen social fabric, trust, or collective action?
  - *Second-order effects*: what does success unlock that was previously impossible?
- [ ] Ground the wider impact in your existing user research — reference a specific insight or user quote that points toward the broader consequence (avoids the asset feeling invented rather than evidence-based).
- [ ] Quantify the scope of the impact where possible: "Our primary persona group represents ~X people in the UK; if 10% adopted the touchpoint, the effect would be…" — even rough estimates signal rigorous thinking.
- [ ] Prepare a 60–90 second verbal pitch of the impact vision to accompany the asset — tutors will ask you to explain it.

### Common pitfalls that drop a band

- Presenting only the HCD asset (cover story / poster) without verbalising or annotating the *wider positive consequences* — this lands in band 3, not band 4.
- Impact framed only around your direct users ("it will help them") rather than second-order effects on society, environment, or other stakeholder groups.
- Asset that looks visually polished but lacks specificity — generic statements like "this will help millions of people" without any grounding in your research context.

### Evidence / artefact

The impact asset itself (printed A3 or on-screen); a slide or annotation listing 2+ wider positive consequences with research grounding; brief verbal pitch in the review session.

---

## Criterion 5 — Quantitative and Objective Evaluation

> **Top-band descriptor:** "Meaningful metric collected, with good analysis and comparison with iterations across the week."

### Actions

- [ ] Choose a **meaningful primary metric** directly tied to your core interaction — not a vanity metric. Strong options:
  - **Task completion rate** (%): % of users who complete a defined core task without assistance (e.g. "successfully submit a request and receive a confirmation").
  - **Task completion time** (seconds): time-on-task for the same core task across iterations — improvement signals better usability.
  - **Error rate** (count or %): number of wrong turns, failed inputs, or back-navigations per session.
  - **System Usability Scale (SUS)**: standardised 10-question Likert survey; score out of 100; industry benchmarks (>68 = above average) allow external comparison.
  - **Feature engagement depth**: e.g. % of sessions where users reach the core real-time interaction (not just the landing page).
  - **Return rate / session length**: if your app supports ongoing use, track repeat engagement across the week.
- [ ] Collect the metric for **at least two iterations** — e.g. M3 state vs. M4 state — so you can show a *before/after comparison*. This is the single most common reason teams land in band 3 (metric collected but no cross-iteration comparison).
- [ ] For SUS or Likert-based metrics: collect responses from a minimum of **5 participants per iteration** (10+ preferred) and report mean ± standard deviation — do not just report a single score.
- [ ] Present the comparison **visually**: a simple bar chart or line graph showing the metric per iteration is far more convincing than a table of numbers.
- [ ] Analyse *why* the metric changed (or did not change) — connect the change to specific design decisions made between iterations. "SUS rose from 58 to 74 after we redesigned the queue-join flow based on M3 user feedback."
- [ ] If a metric worsened or stayed flat, acknowledge it and hypothesise why — this is evidence of rigorous analysis, not failure.
- [ ] Consider one **secondary metric** as a cross-check: e.g. if your primary is SUS, add task completion time to triangulate (a high SUS score with slow completion time signals users *like* the app but still find it effortful).

### Common pitfalls that drop a band

- Collecting a metric (e.g. a post-session rating) only once, at M4, with no prior data point — comparison across iterations is explicitly required for top band.
- Using a generic metric with no relevance to the core problem: e.g. "number of page views" for an app whose value is in collaborative real-time interaction.
- Reporting a single mean score without variance or sample size — this signals poor statistical literacy.
- Describing the metric without showing the analysis: tutors want to see what the numbers *mean* for your design decisions.

### Evidence / artefact

A results slide with chart(s) showing the metric across at least two iterations; SUS questionnaires or raw task-timing data (available to show if asked); 2–3 sentences of written analysis connecting metric changes to design decisions.

---

## Timeline & Logistics

| Date | Action |
|------|--------|
| **Now → 7 Jun** | Complete this sprint's user-story development; run user testing sessions with diverse stakeholder groups; start collecting quantitative metrics |
| **8–9 Jun** | **Clinic hours** — bring your impact asset draft, metric data, and sprint board for tutor feedback before the milestone |
| **10–11 Jun** | Analyse feedback, finalise impact asset, prepare comparison charts, rehearse the 15–20 min review structure |
| **12 Jun** | **M4 Milestone Review Session** — 15–20 min with DoC + RCA tutors |
| **16–17 Jun** | Final Demonstrations & Presentations (50%) |
| **19 Jun, 19:00** | Project Documentation deadline (HCD Portfolio, Leaflet, Legal Report) |

**Review session structure suggestion (15–20 min):**
1. Sprint planning board + user journey framing (3 min)
2. Live demo of the digital touchpoint (5 min)
3. User feedback synthesis + design direction (3 min)
4. Impact asset + wider consequences (2 min)
5. Quantitative evaluation: metric chart + analysis (2 min)
6. Tutor Q&A (remaining time)

> Use clinic hours (8–9 Jun) to stress-test your impact asset and metric analysis — these two criteria are new to M4 and tutors will probe them hardest.

---

## Top-Band Summary: 5 Highest-Leverage Moves

1. **Frame every sprint story in the user journey.** The single word that separates band 3 from band 4 on sprint planning is "framed" — show your project board *alongside* your user journey map and explicitly point to which journey stage each story addresses. This takes 10 minutes to prepare and is worth the most discriminating marks.

2. **Test with two distinct stakeholder groups and name the design direction each implies.** Generic feedback from homogeneous users cannot "provide a clear direction for a wide range of stakeholder groups." Recruit one primary and one secondary stakeholder type, synthesise separately, and present the two contrasting directions — this is what top-band feedback analysis looks like.

3. **Collect your quantitative metric at M3 *and* M4.** The rubric explicitly requires comparison "across the week." If you only measure at M4, the best you can achieve is band 3. Run even a 5-person SUS at M3's state, then again at M4's state, and plot the delta with an explanation of what caused it.

4. **Build the impact asset around second-order consequences, not just user benefit.** Band 3 impact assets show "compelling vision." Band 4 adds "wider positive consequences" — a sentence about social equity, environmental change, or civic benefit grounded in your user research elevates the asset from a marketing poster to a genuine impact argument.

5. **Demo live with two simultaneous users.** The difference between "meaningful design with helpful context-relevant interactions" (band 3) and "engaging, rich" (band 4) is often visceral rather than analytical — tutors feel it when they see two browser windows reacting to each other in real time. Prepare this scenario in advance and make it the centrepiece of your demo.
