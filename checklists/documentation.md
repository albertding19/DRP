# DRP 2026 — Project Documentation: Top-Band Checklist

**Component weight:** 20% of total module mark
**Hard deadline:** 19 June 2026, 19:00
**Submission:** Portfolio of three producibles (see weights below)

> **Critical framing:** The bulk of the content must be developed *during* the project.
> The submission is a narrative wrapper around evidence you have already collected.
> Do NOT attempt to reconstruct artifacts at the end — they will lack authenticity and graders will notice.

---

## Document 1 — Project Pitch Leaflet (10% of documentation mark)

*One side of A4 maximum. Purpose: generate interest at a tech fair / publicity event.*

---

### Element 1.1 — Project name

> **Top-band descriptor:** "Clearly displays a good choice of project name"

- [ ] Choose a name that is memorable, specific to your problem domain, and distinct from generic product names (avoid names like "Connect", "Helper", "App").
- [ ] Ensure the name hints at the value proposition or the audience without needing explanation.
- [ ] Display the name prominently at the top of the leaflet — it should be the first thing the eye lands on.
- [ ] Test the name with at least one person outside the team: can they guess the rough purpose from the name alone?
- [ ] Confirm the name is consistent across the leaflet, legal report, and HCD portfolio.

**Common pitfall:** A name that is overly generic (e.g. "VolunteerApp") or absent entirely — both drop the team to the lower band immediately.

---

### Element 1.2 — Logo

> **Required element:** A logo must appear on the leaflet.

- [ ] Design a logo that is visually coherent with the product name and colour scheme.
- [ ] Export the logo at sufficient resolution that it is crisp at A4 print size.
- [ ] Place the logo adjacent to the product name so they function as a unit.
- [ ] Ensure the logo is not clip-art or a stock icon used without modification — it should feel designed for this product.
- [ ] Check the logo renders clearly in both colour and greyscale (in case printed black-and-white).

**Common pitfall:** Using a placeholder icon or omitting the logo entirely — the rubric explicitly requires one.

---

### Element 1.3 — Screenshot / mock-up communicating a key user journey

> **Top-band descriptor:** "Well-chosen and emotive screen-shot/mock-up"

- [ ] Select a screenshot or high-fidelity mock-up that shows the *core interaction* of the touchpoint, not a login screen or splash page.
- [ ] Annotate or caption the screenshot to make the user journey legible to someone seeing the product for the first time.
- [ ] Choose an image that is emotionally resonant — the context, the user, or the moment shown should make the *problem's stakes* feel real.
- [ ] Ensure the mock-up reflects the final (or near-final) state of the product, not an early wireframe.
- [ ] Test the screenshot: show it to someone unfamiliar with the project and ask what they think the product does — their answer should be close to correct.
- [ ] Verify the image is high-enough resolution to remain sharp at A4 print dimensions.

**Common pitfall:** Using a generic, abstract, or unfocused screenshot (e.g. a landing page with no data) — this drops the team to the lower band because it fails to communicate a real user journey.

---

### Element 1.4 — Problem statement ("before")

> **Top-band descriptor:** "Clear and concise problem-statement"

- [ ] Write a 2–4 sentence problem statement that describes the *current pain* in concrete, human terms — no jargon.
- [ ] Ground the statement in real evidence from your field research (quote a user if possible, even anonymously).
- [ ] State explicitly *who* is affected and *what the consequence* of the problem is for them.
- [ ] Avoid vague framing such as "people struggle with X" — be specific about the context and the severity.
- [ ] Use a visual separator (e.g. a "before / after" panel or a contrast block) to make the problem statement immediately scannable.

**Common pitfall:** A vague or missing problem statement — one that could apply to any product in any sector — is the single most common reason for dropping a band on this document.

---

### Element 1.5 — Target audience

> **Top-band descriptor:** "Clear and specific target-audience"

- [ ] Name the specific audience segment(s) — role, context, and relevant characteristic (e.g. "food bank project managers in urban volunteer organisations", not just "people who volunteer").
- [ ] Include a one-line description of why this audience in particular experiences the problem.
- [ ] Where space allows, reference the persona names from your HCD portfolio to create continuity across documents.
- [ ] Do not list more than two primary audience groups on the leaflet — keep it scannable.

**Common pitfall:** "Missing or vague target-audience" — stating "anyone who wants to..." or leaving this implicit means the leaflet fails the top-band criterion outright.

---

### Element 1.6 — Solution proposition ("after")

> **Top-band descriptor:** "Clear and specific solution proposed"

- [ ] State in 1–3 sentences *exactly* what the touchpoint does and how it solves the stated problem.
- [ ] Use plain language — no technical stack details on the leaflet.
- [ ] Complete the before/after contrast: if you described the problem in 1.4, this section must close the loop with a matching solution.
- [ ] Include one concrete feature or interaction (the "killer feature") that differentiates your solution from doing nothing or using an existing tool.
- [ ] Include context of use: where/when would someone use this touchpoint in their real workflow?

**Common pitfall:** A solution description so general it could describe any app ("it helps users manage their tasks efficiently") — without specificity, this criterion cannot reach the top band.

---

### Leaflet formatting checklist

- [ ] The entire leaflet fits on one side of A4.
- [ ] All six required elements (name, logo, screenshot, problem, audience, solution) are present.
- [ ] The layout is designed, not just a text document with headers — use columns, call-out boxes, or visual hierarchy.
- [ ] Font sizes are legible at A4 print scale (body text >= 9pt).
- [ ] Proofread by at least one team member who did not write the copy.

---

## Document 2 — Copyright/Legal Issues Report (10% of documentation mark)

*One side of A4 maximum. Audience: a future development team picking up where your group left off.*

---

### Element 2.1 — Complete list of third-party resources and their licenses

> **Top-band descriptor:** "Clear list of all third-party resources & licenses; Resources and their licenses clearly linked"

- [ ] Compile a table with at minimum these columns: **Resource name / description | Type (library, image, font, API, dataset, icon set…) | Source URL | License name | License URL**.
- [ ] Include every dependency in your project: frontend frameworks (React, Vue, etc.), backend libraries, databases/ORMs, CSS frameworks, icon sets, stock images, fonts, third-party APIs, and any copied code snippets.
- [ ] Do not limit the list to packages in your `package.json` or `requirements.txt` — also include images, fonts, and design assets used in the UI.
- [ ] For each resource, verify the license is the correct one for the version you are using (licenses can change between versions).
- [ ] Distinguish clearly between resources under permissive licenses (MIT, Apache 2.0, BSD) and those under copyleft licenses (GPL, AGPL) or restrictive terms (CC-BY-NC, proprietary).
- [ ] Confirm that no resource in the list is used in a way that violates its license terms (e.g. a non-commercial-only asset in a student project that may be publicly demonstrated).

**Common pitfall:** An incomplete list (omitting images, fonts, or indirect dependencies) or listing a resource without linking it to its specific license — graders cannot verify unlinked claims.

---

### Element 2.2 — License legal implications

> **Top-band descriptor:** "License legal implications well-considered"

- [ ] For any GPL or AGPL-licensed component: note that if the product were officially released, the entire codebase would need to be open-sourced under the same license.
- [ ] For any CC-BY or CC-BY-SA asset: note attribution obligations and, for SA, the share-alike requirement for derivative works.
- [ ] For any MIT/Apache 2.0 component: note the permissive conditions (attribution in notices, patent grant for Apache 2.0) and confirm they are met.
- [ ] Summarise in one or two sentences the overall license compatibility of the stack — can all components co-exist in a single released product?

**Common pitfall:** Simply naming a license without explaining what it requires or forbids — a future developer reading "MIT" without context does not know what they must do to comply.

---

### Element 2.3 — Copyright legal implications

> **Top-band descriptor:** "Copyright legal implications well-considered"

- [ ] Note that all original code and design produced by the team is automatically copyright of the authors (no registration needed in the UK).
- [ ] Discuss who holds copyright on work created collaboratively (joint authorship under UK CDPA 1988).
- [ ] If any code was generated by an AI tool (Copilot, ChatGPT, etc.), note the unresolved copyright status of AI-generated code and recommend a policy for a future team.
- [ ] Note any Imperial College / RCA IP policies that may affect ownership of work created in the course of study.
- [ ] State clearly that any third-party copyrighted material reproduced in the UI (images scraped from the web, for example) would need to be replaced with properly licensed alternatives before release.

**Common pitfall:** Conflating copyright with licensing — these are distinct concepts; a future team needs to understand both independently.

---

### Element 2.4 — Wider legal implications

> **Top-band descriptor:** "Wider legal implications well-considered"

- [ ] **Data protection / GDPR:** If the touchpoint handles personal data of EU/UK users, note obligations under UK GDPR and DPA 2018 (lawful basis, privacy notices, data minimisation, right to erasure).
- [ ] **Accessibility:** Note that a publicly released product serving UK public sector clients would be subject to WCAG 2.1 AA requirements under the Public Sector Bodies Accessibility Regulations 2018.
- [ ] **Terms of service of third-party APIs:** Note any API usage limits or restrictions that would affect a commercial or public release (e.g. Google Maps API pricing beyond free tier, OpenAI usage policies).
- [ ] **Sector-specific regulation:** If the product operates in a regulated domain (health, finance, education of minors), name the relevant regulation and its implication (e.g. CQC registration, FCA authorisation, COPPA/GDPR-K).
- [ ] **App store policies:** If the touchpoint were released as a mobile app, note Apple App Store / Google Play review requirements and their content/privacy policy obligations.

**Common pitfall:** Treating this section as a formality — writing only "we would need to comply with GDPR" without specifying what that means in the context of your specific product is firmly in the lower band.

---

### Legal report formatting checklist

- [ ] The report fits on one side of A4.
- [ ] The resource table is genuinely a table (not a prose list), making it easy for a future developer to scan.
- [ ] The legal discussion paragraph is separate from the table and clearly labelled.
- [ ] The document is written for a technical reader who is *not* a lawyer — jargon is defined where used.
- [ ] All URLs in the table are working links (check before submission).

---

## Document 3 — Human Centred Design Techniques Portfolio (80% of documentation mark)

*Multi-page portfolio. Discussion text: one side of A4. Evidence/support material: no strict limit. Use diagrams wherever possible.*

> **NON-NEGOTIABLE: Artifact capture must happen in real time, at each milestone, throughout the project. Artifacts cannot be authentically reconstructed after the fact. Graders are experienced at spotting retrospectively invented evidence.**

### Per-iteration artifact capture reminder

- [ ] **After M1 (22 May):** Export and save all AEIOU notes, stakeholder map draft, persona v1, empathy map, field interview notes/quotes, opportunity statement.
- [ ] **After M2 (29 May):** Save paper/digital mock-ups with user annotations, testing session notes, feedback excerpts, iteration log entry, prototype photos.
- [ ] **After M3 (5 Jun):** Save sprint board screenshot, updated journey map, feedback session artifacts, list of changes made and the feedback that drove each one.
- [ ] **After M4 (12 Jun):** Save final testing plan canvas, cover story mock-up, quantitative evaluation data, impact evidence, final journey map ("after" state).

---

### Criterion 3.1 — People: target audience

> **Top-band descriptor:** "Clear understanding and empathy illustrating the needs/behaviours of the target audience in your chosen context"

- [ ] Include at least two richly developed user personas (name, photo/illustration, demographics, daily routine, goals, frustrations, jobs-to-be-done, a direct quote from a real interview).
- [ ] Show that each persona was derived from primary field research — include the quote or observation that gave rise to each key insight in the persona.
- [ ] Annotate the persona with its implication for the design: "Because Sarah struggles with X, we designed Y."
- [ ] Include an empathy map (think/feel/hear/see/say/do + pain/gain) for at least your primary persona, grounded in interview data.
- [ ] Show how the persona evolved across iterations as you learned more — a side-by-side or versioned persona is excellent evidence.
- [ ] Avoid stock-photo faces if possible; use real participant photos (with consent) or illustrated representations tied to your context.

**Common pitfall:** Generic, demographic-only personas ("Age 25–35, tech-savvy, London-based") with no behavioural insight or connection to field research — this is explicitly the lower band.

---

### Criterion 3.2 — People: stakeholder groups

> **Top-band descriptor:** "Clear understanding of relevant stakeholder groups whose needs and behaviours should be considered in your proposition"

- [ ] Produce a stakeholder map (concentric rings or equivalent) showing all groups — primary users, secondary users, affected parties, enablers, regulators — not just the most obvious group.
- [ ] For each stakeholder ring, write 1–2 sentences describing their relationship to the problem and their stake in the solution.
- [ ] Show at least one non-obvious stakeholder group that your research uncovered — this signals genuine discovery rather than assumption.
- [ ] Demonstrate that the map was updated at least once during the project as understanding deepened.
- [ ] Reference the stakeholder map explicitly in your opportunity statement: "Our solution must work for X and Y, and must not harm Z."

**Common pitfall:** A stakeholder map that only shows the primary user and the development team — this demonstrates low awareness of the wider ecosystem and cannot reach the top band.

---

### Criterion 3.3 — Current/Future State: understanding current state

> **Top-band descriptor:** "Design methods used illustrate clear evidence of understanding the current state"

- [ ] Present your AEIOU field research structured under the five headings (Activities, Environments, Interactions, Objects, Users) with specific observations, not generalisations.
- [ ] Include a "before" user journey map: stages, actions, thoughts/feelings, and emotional highs and lows of the *current* experience — before your touchpoint exists.
- [ ] Show evidence that the team observed or experienced the current state first-hand (field visit photos, observation notes, walk-through diary) rather than relying only on desk research.
- [ ] Include at least one direct quote from a stakeholder that illustrates a pain point in the current state.
- [ ] Reference competitor or analogous solutions briefly — noting what they do and where they fall short — to establish why a new touchpoint is needed.

**Common pitfall:** A current-state section built entirely from desk research (statistics, articles) with no first-hand qualitative evidence — the rubric explicitly values field research and real people, not numbers.

---

### Criterion 3.4 — Current/Future State: insights generating a high-impact future experience

> **Top-band descriptor:** "Insights generated are empathetic and clearly create a high-impact solution (future experience)"

- [ ] Write 3–5 clearly labelled insight statements, each in the form: *"[Stakeholder] needs [unmet need] because [root cause discovered in research], which means [design implication]."*
- [ ] Each insight must trace back to a specific research observation — cite the source (e.g. "interview with participant A, 24 May").
- [ ] Present a "How Might We..." opportunity statement that synthesises the insights and sets the direction for the solution.
- [ ] Include an "after" user journey map showing how the touchpoint transforms the experience — same stages, dramatically improved emotional journey.
- [ ] Annotate the "after" journey to show which feature of the touchpoint addresses which pain point from the "before" journey.

**Common pitfall:** Generic insights ("users want a simpler interface") that could apply to any digital product — insights must be specific to your context and derived from your field research.

---

### Criterion 3.5 — Current/Future State: opportunity statement

> **Top-band descriptor:** "Clear opportunity statement considering the needs of all stakeholder groups"

- [ ] Write a single, polished "How Might We..." opportunity statement that names at least two stakeholder groups and the desired outcome for each.
- [ ] Ensure the statement is ambitious but bounded — not so broad it encompasses everything, not so narrow it excludes creative solutions.
- [ ] Show how the statement evolved from M1 (initial framing) through research to a refined version — the evolution demonstrates genuine learning.
- [ ] Place the final opportunity statement prominently at the transition point between Discover/Define and Develop in your portfolio narrative.

**Common pitfall:** An opportunity statement that only addresses the primary user and ignores how the solution must work for (or avoid harming) secondary stakeholders.

---

### Criterion 3.6 — Testing and Validation: user feedback leading to richer experience

> **Top-band descriptor:** "Clear evidence of user feedback leading to a richer and improved experience"

- [ ] For each of the four iterations, document: who you tested with (role/relationship to problem, not name), what method you used, what you asked/showed, and what you learned.
- [ ] Include a Testing Plan Canvas (or equivalent structured test plan) showing hypothesis, method, participants, and success criteria for at least one iteration.
- [ ] Present feedback excerpts (direct quotes, annotated mock-ups, photos of testing sessions) — raw evidence, not paraphrases.
- [ ] For each piece of feedback, explicitly state the design decision it caused: "User B said she couldn't find the notification bell, so we moved it to [location] in the next iteration."
- [ ] Show at least one instance where feedback caused you to *abandon* a feature or approach, not just refine it — this demonstrates genuine responsiveness, not confirmation-bias testing.
- [ ] Confirm that testing involved real stakeholders (not just teammates or the same friend repeatedly) — diverse participants across iterations strengthens this criterion.

**Common pitfall:** Showing feedback that was "gathered" but then not visibly acted upon — graders look for the *causal chain* from feedback to change, not just proof that sessions happened.

---

### Criterion 3.7 — Testing and Validation: visual representation of touchpoint evolution

> **Top-band descriptor:** "Visual representation of digital touchpoint evolution (from concept, to feature, to a seamless and richer experience) showing authentic builds"

- [ ] Create a visual timeline or storyboard showing the state of the touchpoint at the end of each iteration: M1 concept sketch → M2 walking skeleton → M3 context-relevant build → M4 fuller UX.
- [ ] Each stage must show an *authentic build* — a real screenshot, photo of a paper prototype, or Figma frame — not a retrospectively polished mock-up.
- [ ] Annotate each stage with the key feedback that caused the transition to the next stage.
- [ ] Show the prototyping method used at each stage (paper → low-fi digital → interactive prototype → deployed build) and briefly explain why that fidelity was appropriate at that point.
- [ ] Timestamp or date-label each stage so the progression is clearly chronological.

**Common pitfall:** Presenting a single polished final state with no visible evolution — this makes it impossible to assess whether design thinking drove development or whether the product was designed once and coded without iteration.

---

### Criterion 3.8 — Testing and Validation: insightful reflection on changes

> **Top-band descriptor:** "Insightful reflection on what led to distinct changes in the digital touchpoint"

- [ ] Write a short reflective paragraph (or annotated change log) for each iteration: what assumption was challenged, what you learned that surprised you, and how your thinking shifted.
- [ ] Distinguish between changes driven by user feedback, technical constraints, and team decisions — be honest about the difference.
- [ ] Include at least one reflection on a *mistake* or *wrong turn* and what it taught the team — authentic self-criticism signals genuine engagement with HCD.
- [ ] Avoid generic retrospective language ("we learned a lot from user testing") — name the specific insight and the specific consequence.

**Common pitfall:** Reflections that read as "we did X, then we did Y" (a diary) rather than "we learned Z, which caused us to change from X to Y" (a causal reflection) — the latter is what the top band requires.

---

### Criterion 3.9 — Understanding Impact: better outcome for target audience

> **Top-band descriptor:** "Meaningful evidence clearly showing a better outcome for the target audience"

- [ ] Include quantitative evaluation data collected at M4: a metric that measures the outcome for your primary user (task completion rate, time-on-task, user satisfaction score, error rate, etc.).
- [ ] Compare this metric across at least two iterations to show measurable improvement.
- [ ] Supplement with qualitative evidence: a quote from a user who describes their improved experience in their own words.
- [ ] Produce or reference an "after" journey map showing the improved emotional journey versus the "before" map.
- [ ] Be specific about what "better" means in your context — use the language of your users and stakeholders, not generic UX vocabulary.

**Common pitfall:** Claiming impact without evidence, or presenting a metric with no comparison point — "80% of users liked it" is meaningless without a baseline or comparison.

---

### Criterion 3.10 — Understanding Impact: improved experience for all relevant stakeholder groups

> **Top-band descriptor:** "Meaningful evidence clearly leading to an improved experience for all relevant stakeholder groups"

- [ ] Include your Cover Story mock-up: a fictional magazine/news article headline and paragraph describing the positive future impact of your touchpoint on all stakeholder groups — not just the primary user.
- [ ] Demonstrate (with evidence or reasoned argument) how at least one secondary stakeholder group benefits from the touchpoint.
- [ ] If any stakeholder group is not positively impacted (or could be harmed), acknowledge this and explain mitigation — intellectual honesty scores higher than omission.
- [ ] Reference the wider positive consequences of your solution: social, environmental, or systemic effects beyond the immediate user interaction.

**Common pitfall:** An impact section that only addresses the primary user and ignores the stakeholder map — graders will cross-reference these and the inconsistency will cost marks.

---

### HCD Portfolio formatting checklist

- [ ] The discussion text (narrative, reflections, opportunity statements) is limited to approximately one side of A4 — evidence and support material may extend beyond this.
- [ ] Every section uses a visual (diagram, photo, annotated screenshot, journey map, canvas) — no section should be text-only.
- [ ] The portfolio is structured to follow the Double Diamond: Discover → Define → Develop → Deliver — or a clearly labelled equivalent narrative arc.
- [ ] Artifacts are dated or iteration-labelled so the chronological progression is clear.
- [ ] The portfolio reads as a coherent story of a design journey, not a checklist of completed methods.
- [ ] All participant photos and quotes are used with consent (note consent obtained in the document).
- [ ] The cover story mock-up is present and visually designed (not just a paragraph labelled "cover story").

---

## Timeline & Logistics

| Date | Action |
|------|--------|
| Now (18 May) | Confirm all M1 artifacts are saved and organised. |
| After M2 (29 May) | Export all mock-ups, testing notes, and feedback excerpts. Log iteration changes. |
| After M3 (5 Jun) | Export sprint board, updated journey map, feedback session artifacts. |
| After M4 (12 Jun) | Finalise quantitative metric, cover story mock-up, impact evidence. |
| 13–15 Jun | Draft all three documents. Circulate within team for review. |
| 16–17 Jun | Final Demonstration. Capture final screenshots for leaflet during or immediately after. |
| 18 Jun | Final proofreads. Check all URLs in legal report. Verify A4 formatting for leaflet and legal report. |
| **19 Jun, by 17:00** | **Submit — do not wait until 19:00. Give yourself a 2-hour buffer.** |

**Do not draft any of the three documents solely in the final week.** The leaflet screenshot must show the final product; the legal report requires a complete dependency audit; the HCD portfolio is only as good as the artifacts collected in real time. All three documents should be in near-final draft form by 15 June.

---

## Top-Band Summary — Highest-Leverage Actions

The HCD Portfolio is worth 80% of this 20% component, making it effectively **16% of your total module mark**. Everything else is 2% each. Prioritise accordingly.

**The five moves that most reliably separate top-band from mid-band submissions:**

1. **Capture artifacts in real time at every milestone.** Nothing in this checklist matters if you arrive at 18 June with no evidence from M1–M3. Every testing session, every iteration of a prototype, every insight — photograph, export, and date-label it the day it happens.

2. **Make the feedback-to-change causal chain explicit.** For every design decision, write one sentence naming the feedback that caused it. This is the core of "Testing and Validation" and the most common differentiator between top and middle bands.

3. **Produce a genuine "before / after" journey map pair.** The contrast between the current painful experience and the future improved experience — grounded in real research and real outcomes — is the clearest evidence of HCD done well.

4. **Show diverse stakeholder groups throughout, not just the primary user.** The rubric mentions stakeholders in every criterion section. A portfolio that only discusses the primary user cannot reach the top band on People, Opportunity Statement, or Impact.

5. **Design the leaflet, not just write it.** A single A4 of densely formatted prose will not generate interest at a tech fair. Use visual hierarchy, a strong screenshot, and a before/after contrast panel. A well-designed leaflet is completed in 2–3 hours if you have the right screenshot and a clear problem statement.
