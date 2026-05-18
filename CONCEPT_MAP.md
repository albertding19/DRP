# DRP 2026 — Requirements Concept Map

> "Designing for Real People" — Imperial DoC × RCA Service Design. Spring–Summer 2026.
> Build a **digital touchpoint** that solves a **real-world problem** for **real people**,
> developed through **Human-Centred Design** and **agile iterations**.

```
                          ┌─────────────────────────────┐
                          │   DRP PROJECT (the "what")  │
                          │  Digital touchpoint solving  │
                          │  a real problem for real    │
                          │  people in a chosen context  │
                          └──────────────┬──────────────┘
            ┌───────────────┬────────────┼────────────┬───────────────┐
            ▼               ▼            ▼            ▼               ▼
      THE PRODUCT      METHODOLOGY    PROCESS      ASSESSMENT     DELIVERABLES
   (digital touchpoint)   (HCD)     (4 iterations)   (100%)      (producibles)
```

---

## 1. THE PRODUCT — Digital Touchpoint

A multi-user web **or** mobile application. Free choice of language/framework.
**8 mandatory technical requirements:**

1. Solves a **clearly identified real-world problem**; designed *with representative users (not yourself)*.
2. **Multi-user** with **rich user interactions** (messaging, scoreboards, collaboration…).
3. Supports **real-time user interactions**.
4. Uses a **database** for **persistent internal state**.
5. **Continuous Integration (CI)** + **Continuous Deployment (CD)** — integrate all members' changes.
6. Runs on a lab-machine browser (or a loanable mobile device).
7. Any plug-ins must be freely available with install instructions.
8. No college/copyright rule violations; tolerates malicious/unexpected input gracefully.

*Suggested (treat as requirements if first app):* deploy on **DoC CloudStack VM**; use a **CSG PostgreSQL DB**.
The touchpoint is **one node in a wider experience** — not the starting point.

---

## 2. METHODOLOGY — Human-Centred Design

**Double Diamond** (UK Design Council 2005): Discover → Define → Develop → Deliver.
HCD is **embedded in milestone marking** (no separate HCD submission).
Key methods (used + documented in portfolio): AEIOU field research, **User Personas**,
**Stakeholder Maps**, **User Journey Maps** (before/after), Service Blueprints,
prototyping techniques, **Testing Plan Canvas**, **Cover Story** mock-up.
Evidence must be **qualitative & first-hand** ("real people, not numbers").

---

## 3. PROCESS — 4 Agile Iterations

| # | Iteration              | Focus                                                        |
|---|------------------------|--------------------------------------------------------------|
| 1 | Project Inception      | Context, problem, target audience, evidence, "How Might We?" |
| 2 | Concept Development    | Mock-ups + walking skeleton; user-tested; Git + CI/CD set-up |
| 3 | Iterative Development  | Context-relevant touchpoint; sprint planning; **thin slicing** |
| 4 | More Iterative Dev     | Fuller UX; wider impact (impact asset); **quantitative eval** |

Cross-cutting: agile sprint planning driven by **user stories**; thin slicing (don't
skew Front-End/Back-End/DB); continuous deployment evidence.

---

## 4. ASSESSMENT — 100%

| Component                          | Weight | Notes                                         |
|------------------------------------|--------|-----------------------------------------------|
| Milestone Assessments (×4)         | 20%    | 5% each — M1–M4                               |
| Law Case Study TRA                 | 10%    | 2 Jun, 10:00–12:00 — copyright/IP/data law    |
| Final Demonstration & Presentation | 50%    | 20-min integrated demo + 5-min panel feedback |
| Project Documentation              | 20%    | Leaflet 10% / Legal 10% / HCD Portfolio 80%   |

**M1 = pre-recorded 3-min elevator pitch.** M2–M4 = 15–20 min progress meetings.
Final presentation: all members speak equally — intro, touchpoint demo,
language/framework justification, system architecture overview, conclusion/evaluation.

---

## 5. DELIVERABLES — Documentation Producibles (due 19 Jun, 19:00)

- **Project Pitch Leaflet** (10%, 1×A4) — logo, name, value prop, screen-shot, key user journey.
- **Copyright/Legal Issues Report** (10%, 1×A4) — third-party resource/license table + legal discussion.
- **HCD Techniques Portfolio** (80%, multi-page) — visual record of HCD methods, reflections, touchpoint evolution.

---

## 6. KEY DATES (2026)

| Date          | Event                                            |
|---------------|--------------------------------------------------|
| 19 Mar        | Form group (max 4 students)                      |
| 20 Mar        | HCD Workshop                                     |
| 18–21 May     | Clinic hours                                     |
| **22 May**    | **M1 — Elevator Pitch (5%)**                     |
| **29 May**    | **M2 — Progress Meeting (5%)**                   |
| **2 Jun**     | **Law Case-Study TRA (10%)**                     |
| **5 Jun**     | **M3 — Progress Meeting (5%)**                   |
| **12 Jun**    | **M4 — Progress Meeting (5%)**                   |
| **16–17 Jun** | **Final Demonstrations & Presentations (50%)**   |
| **19 Jun**    | **Project Documentation deadline, 19:00 (20%)**  |

---

## RUBRIC SIGNALS — what "excellent" looks like

- **Context:** rich, with tangible access to *diverse* stakeholder groups (not just team/friends).
- **People:** well-defined personas that *drive the narrative*.
- **Evidence:** strong qualitative data via interactive HCD, linked to referenced third-party stats.
- **Touchpoint:** engaging, rich with *meaningful, usable, context-relevant* interactions.
- **Feedback:** rich, multidimensional, gathered with customised HCD methods; visibly steers design.
- **Engineering:** functioning CD system; clear thin-slicing across iterations; agile framed in user journey.
- **Impact:** compelling vision incl. wider positive consequences; meaningful quantitative metric with cross-iteration comparison.
```
```
