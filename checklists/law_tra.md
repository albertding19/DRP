# Law Case Study TRA — Top-Band Revision Checklist

> **Assessment:** Law Case Study TRA (10% of DRP)
> **Date/Time:** Monday 2 June 2026, 10:00–12:00 (2 hours)
> **Format:** Timed Remote Assessment — case-study question(s); likely open-book (verify on module page)
> **Jurisdiction:** UK law is primary (UK GDPR, CDPA 1988, Patents Act 1977, etc.)
> **Related deliverable:** Copyright/Legal Issues Report (10% of Project Documentation, due 19 Jun 19:00)

---

## Timeline & Logistics

| Date | Action |
|------|--------|
| Now → 25 May | Core doctrine revision (all four legal areas) |
| Summer wk 5 (26–30 May) | Law TRA teaching — attend everything; capture examples |
| Summer wk 6 (1 Jun) | Final review; assemble open-book notes/cheat-sheet |
| **2 Jun, 09:30** | Arrive/log in early; confirm platform & permitted materials |
| **2 Jun, 10:00–12:00** | TRA — IRAC structure; budget time per question |
| 2–19 Jun | Use revised knowledge to finalise Copyright/Legal Issues Report |

---

## 1. Copyright and Licensing

### 1a. Copyright Subsistence

- [ ] Define copyright: automatic, unregistered right protecting original works — no registration needed in the UK.
- [ ] Know the threshold: originality means the author's own intellectual creation (post-*Infopaq*); not merely skill and labour.
- [ ] List the categories of protected works under the Copyright, Designs and Patents Act 1988 (CDPA): literary, dramatic, musical, artistic, films, sound recordings, broadcasts, typographical arrangements.
- [ ] Confirm that **software (source code + object code) is a literary work** under CDPA s.3 — and that the same applies to preparatory design material.
- [ ] Know **duration**: literary/artistic/dramatic/musical works — life of author + 70 years. Sound recordings — 70 years from publication. Broadcasts — 50 years.
- [ ] Understand **first ownership**: the author (CDPA s.11(1)), but works made by an employee **in the course of employment** vest in the employer (s.11(2)). Contractor/freelancer works vest in the contractor unless assigned by contract.
- [ ] Distinguish ownership from authorship; know that students generally own their own IP (check Imperial's own IP policy).
- [ ] Identify what **does not attract copyright**: ideas, concepts, methods, algorithms, facts (the idea/expression dichotomy).
- [ ] Know the **restricted acts**: copying, issuing copies to the public, renting/lending, performing/showing/playing in public, communicating to the public, making adaptations.
- [ ] Be able to name relevant **permitted acts / exceptions** in UK law: research & private study (fair dealing), criticism & review (fair dealing with acknowledgment), temporary copies (s.28A), backup copies of computer programs (s.50A), decompilation (s.50B — narrow conditions), observing/studying/testing software (s.50BA).
- [ ] Know that UK permitted acts for software **cannot be overridden by contract** in most cases.

### 1b. Open-Source Licence Families

- [ ] Explain what an open-source licence does: grants permissions beyond the default "all rights reserved" in exchange for conditions.
- [ ] **Permissive licences (MIT, BSD-2-Clause, BSD-3-Clause, Apache 2.0):**
  - [ ] Core obligation: retain the copyright notice and licence text in distributions.
  - [ ] Apache 2.0 extras: patent grant (explicit), NOTICE file requirement, attribution for modified files.
  - [ ] Permissive → can incorporate into proprietary/closed-source products freely.
- [ ] **Copyleft licences (GPL family):**
  - [ ] GPL v2 / GPL v3: any distribution of modified (or combined) work must be under the same GPL; source code must be made available.
  - [ ] AGPL v3: extends GPL to network use — running a modified AGPL program as a web service triggers the copyleft obligation (source must be offered to users).
  - [ ] LGPL v2.1 / v3: weaker copyleft — allows linking a proprietary application against an LGPL library without copyleft infecting the application, provided the library remains replaceable.
- [ ] **Creative Commons licences (for non-code assets):**
  - [ ] CC0 — public domain dedication, no conditions.
  - [ ] CC BY — attribution required.
  - [ ] CC BY-SA — share-alike (copyleft equivalent for content).
  - [ ] CC BY-NC — non-commercial restriction (not open-source compatible).
  - [ ] CC BY-ND — no derivatives permitted.
- [ ] Understand **licence compatibility**: GPL v3 is compatible with Apache 2.0 (both in a v3 project); GPL v2 is NOT compatible with Apache 2.0; AGPL ≠ plain GPL unless the library permits it.
- [ ] Know the **four software freedoms** (FSF definition): use, study, modify, distribute modified versions.
- [ ] Be able to answer: "We are building a web service using library X under licence Y — what are our obligations?"

### 1c. Applying Copyright to DRP-Style Scenarios

- [ ] Identify who owns code written collaboratively in a student team project.
- [ ] Recognise that using a GPL library in a deployed web service without releasing source code is infringement.
- [ ] Recognise that using an image from Google Images does not grant permission — must check the licence.
- [ ] Know that APIs: the interface specification may be copyrighted; the *Lotus v Borland* / *Oracle v Google* line of cases bears on whether function signatures are copyrightable (UK position: typically yes, as literary work, but functionality is not).

---

## 2. Intellectual Property (Broader IP Framework)

### 2a. Types of IP Right — Side-by-Side

- [ ] **Copyright:** automatic; protects expression; duration life + 70 yrs; no registration.
- [ ] **Patents:** registered; protects novel, inventive, industrially applicable *inventions*; duration 20 years from filing; must disclose; expensive.
- [ ] **Trade marks:** registered (or unregistered passing-off); protects brand identifiers (words, logos, sounds); renewable indefinitely if in use; infringement = likelihood of confusion.
- [ ] **Trade secrets / confidential information:** no registration; protected by contract (NDA) and equity; lasts as long as the secret is kept; no expiry.
- [ ] **Design rights:** registered (appearance, up to 25 yrs) vs unregistered (automatic, 10/15 yrs); protects visual appearance of a product.
- [ ] Know which right best protects: source code (copyright), algorithm (trade secret or patent if meets threshold), logo (trademark), new technical invention (patent).

### 2b. Software & Patents

- [ ] UK/EPO position: computer programs "as such" are excluded from patentability (Patents Act 1977 s.1(2); EPC Art 52). But a technical invention *implemented* in software with a technical character *can* be patented.
- [ ] US position is more permissive (Alice Corp test post-2014 more restrictive, but historically broader).
- [ ] Be ready to distinguish a patentable software invention from mere abstract idea.

### 2c. IP Ownership — Employment & Commissioning

- [ ] Employee works created in the course of normal duties → employer owns (CDPA s.11(2); Patents Act s.39).
- [ ] Contractor/freelancer → they own IP unless there is a written assignment.
- [ ] Students → generally own their own IP (Imperial policy for undergrads: student retains; check specifics for your context).
- [ ] Know that an IP assignment clause in a contract transfers ownership outright; a licence does not transfer ownership.
- [ ] "Work for hire" (US concept) — in UK use "IP assignment" instead; the concepts are similar but distinct.

### 2d. Confidential Information

- [ ] Three conditions for protection: the information has the quality of confidence; communicated in circumstances importing confidentiality; unauthorised use causing detriment.
- [ ] NDAs formalise the obligation; breach → damages or injunction.
- [ ] Know the interaction with data protection: confidential personal data may be both a trade secret AND personal data subject to UK GDPR.

---

## 3. Contractual Obligations

### 3a. Contract Formation

- [ ] Elements of a valid contract: offer, acceptance, consideration, intention to create legal relations, capacity.
- [ ] Know that clicking "I agree" on a website / app constitutes valid acceptance (electronic contracts are binding under Electronic Commerce (EC Directive) Regulations 2002 and the Electronic Communications Act 2000).
- [ ] Distinguish bilateral contracts (both parties exchange promises) from unilateral contracts.
- [ ] Know that terms can be express (written/oral) or implied (by statute, custom, or the courts for business efficacy).

### 3b. Key Clauses in Software/Tech Contracts

- [ ] **Scope of work / deliverables:** defines what is being built; ambiguity in software specs leads to disputes.
- [ ] **IP assignment / licence-back clause:** who owns what is built; contractor retains background IP.
- [ ] **Warranties:** seller warrants the software will conform to spec, be fit for purpose; implied terms under Consumer Rights Act 2015 (for consumers) / Sale of Goods Act (goods context).
- [ ] **Limitation of liability clause:** caps a party's liability (e.g., to the contract value). Must satisfy reasonableness test under Unfair Contract Terms Act 1977 (UCTA) for B2B; Consumer Rights Act 2015 for B2C (cannot exclude liability for death/personal injury caused by negligence — UCTA s.2(1)).
- [ ] **Exclusion clause:** excludes certain heads of liability; subject to same tests as limitation clauses.
- [ ] **Indemnity clause:** one party agrees to compensate the other for specific losses (e.g., third-party IP infringement claims).
- [ ] **Confidentiality clause (NDA):** restricts disclosure of confidential information.
- [ ] **SLA (Service Level Agreement):** defines uptime, response time guarantees; breach → service credits.
- [ ] **Termination clause:** grounds for termination (material breach, insolvency, convenience); effect on licences.
- [ ] **Governing law / jurisdiction clause:** specifies which country's law governs and which courts have jurisdiction.
- [ ] **Force majeure clause:** excludes liability for events outside a party's control.

### 3c. Terms of Service / EULAs

- [ ] EULAs are licences (not sales) — the user acquires a right to use software, not ownership of a copy.
- [ ] Shrinkwrap, clickwrap, browsewrap — know the enforceability spectrum (browsewrap weakest; clickwrap generally enforceable).
- [ ] Consumer terms cannot exclude statutory rights (Consumer Rights Act 2015).
- [ ] **Unfair terms** in consumer contracts are unenforceable if they create a significant imbalance to the consumer's detriment (CRA 2015 s.62).
- [ ] Know the interaction: an EULA cannot strip a user of the statutory permitted acts for software (CDPA s.296A).

### 3d. Breach & Remedies

- [ ] Distinguish conditions (breach → right to terminate + damages) from warranties (breach → damages only) from innominate terms (consequences depend on severity).
- [ ] Remedies: damages (expectation/loss of bargain); specific performance (rare in software); injunction.
- [ ] Duty to mitigate loss.

---

## 4. Data Protection

### 4a. The UK GDPR Framework

- [ ] Know the legal instruments: **UK GDPR** (retained EU law post-Brexit, tailored by the **Data Protection Act 2018 (DPA 2018)**). Together they replace the Data Protection Act 1998.
- [ ] Know the **ICO** (Information Commissioner's Office) is the UK supervisory authority.
- [ ] Define **personal data**: any information relating to an identified or identifiable natural person (UK GDPR Art 4(1)). Includes names, email addresses, IP addresses, cookies, location data.
- [ ] Define **special category data** (Art 9): health, biometrics, race/ethnicity, religion, political opinion, sex life/orientation, trade union membership, genetic data — requires explicit consent or another specific condition.

### 4b. The Seven Data Protection Principles (UK GDPR Art 5)

- [ ] **Lawfulness, fairness and transparency** — must have a lawful basis; must tell data subjects what you do with their data.
- [ ] **Purpose limitation** — collected for specified, explicit, legitimate purposes; not further processed incompatibly.
- [ ] **Data minimisation** — adequate, relevant, limited to what is necessary.
- [ ] **Accuracy** — kept accurate; erased or rectified without delay.
- [ ] **Storage limitation** — kept no longer than necessary; define retention periods.
- [ ] **Integrity and confidentiality (security)** — appropriate technical and organisational measures.
- [ ] **Accountability** — the controller is responsible and must be able to demonstrate compliance.
- [ ] Be able to identify which principle is violated in a scenario (e.g., storing data indefinitely = storage limitation breach).

### 4c. Lawful Bases for Processing (Art 6)

- [ ] **Consent** — freely given, specific, informed, unambiguous indication of agreement; easily withdrawable; not bundled; pre-ticked boxes invalid.
- [ ] **Contract** — processing necessary for performance of a contract with the data subject.
- [ ] **Legal obligation** — processing necessary to comply with a legal requirement.
- [ ] **Vital interests** — to protect someone's life (narrow use).
- [ ] **Public task** — processing in the exercise of official authority.
- [ ] **Legitimate interests** — the controller's (or third party's) legitimate interest, not overridden by data subject's rights (requires a three-part balancing test: purpose test, necessity test, balancing test).
- [ ] Know that for special category data, a condition under Art 9 is *also* needed on top of an Art 6 basis.

### 4d. Data Subject Rights

- [ ] **Right to be informed** — privacy notice; transparent information about processing.
- [ ] **Right of access (SAR)** — data subject can request a copy of their personal data; controller has 1 month to respond.
- [ ] **Right to rectification** — correct inaccurate data.
- [ ] **Right to erasure ("right to be forgotten")** — Art 17; applies in specific circumstances (e.g., consent withdrawn, no longer necessary); not absolute.
- [ ] **Right to restrict processing** — Art 18; data can be stored but not further processed.
- [ ] **Right to data portability** — Art 20; structured, commonly used, machine-readable format; applies where basis is consent or contract.
- [ ] **Right to object** — Art 21; object to processing based on legitimate interests or direct marketing.
- [ ] **Rights related to automated decision-making** — Art 22; right not to be subject to solely automated decisions with significant effects; exceptions.

### 4e. Controllers, Processors, and Joint Controllers

- [ ] **Controller**: determines the purposes and means of processing. Bears primary compliance obligations.
- [ ] **Processor**: processes on behalf of a controller; must act on documented controller instructions; must sign a Data Processing Agreement (DPA) with the controller (Art 28).
- [ ] **Joint controllers** (Art 26): two or more controllers jointly determine purposes and means; must agree on respective responsibilities in a transparent arrangement.
- [ ] Be able to classify parties in a scenario: e.g., a startup using AWS → startup is controller, AWS is processor.

### 4f. Privacy by Design and by Default

- [ ] **Privacy by design** (Art 25): data protection principles must be embedded from the outset, not bolted on — relevant to *DRP app development*.
- [ ] **Privacy by default**: only personal data necessary for each purpose should be processed by default (e.g., do not pre-select marketing consent; collect only required fields).
- [ ] Know the link to DPIAs (Data Protection Impact Assessments) — required for high-risk processing (Art 35).

### 4g. Security and Breach Notification

- [ ] Art 32: appropriate technical and organisational measures — e.g., encryption, pseudonymisation, access controls, regular testing.
- [ ] **Personal data breach**: a breach of security leading to accidental or unlawful destruction, loss, alteration, unauthorised disclosure of, or access to, personal data.
- [ ] **Notification to ICO** (Art 33): within **72 hours** of becoming aware, unless unlikely to result in risk to individuals.
- [ ] **Notification to data subjects** (Art 34): required without undue delay if the breach is likely to result in high risk to individuals.
- [ ] Know what information must be included in a breach notification (nature of breach, categories and approximate number of data subjects, likely consequences, measures taken/proposed).

### 4h. International Transfers

- [ ] Transfers of personal data outside the UK require a transfer mechanism: adequacy decision (ICO list), Standard Contractual Clauses (SCCs / International Data Transfer Agreements — IDTAs in UK), Binding Corporate Rules.
- [ ] US: UK–US data bridge (successor to Privacy Shield) allows transfers to certified US organisations.

---

## 5. Case-Study Exam Technique

### Reading and Issue Spotting

- [ ] Read the entire case study once before writing anything — get the full picture.
- [ ] On second read, annotate/highlight legally significant facts (names of parties, type of work, type of contract, data collected, what went wrong).
- [ ] List all the legal issues you can identify before writing — don't dive into one issue and miss another worth marks.
- [ ] Prioritise issues by likely mark weight (major issues first).

### IRAC Method — Apply to Every Issue

- [ ] **I — Issue:** state the precise legal question raised by the facts. ("The issue is whether X constitutes copyright infringement by Y.")
- [ ] **R — Rule:** state the relevant legal rule, principle, or statutory provision accurately. Cite the statute or case name where possible. ("Under CDPA 1988 s.16, the owner of copyright has the exclusive right to copy the work.")
- [ ] **A — Application:** apply the rule to the specific facts of the scenario. Use the facts — don't write in the abstract. ("Here, Z copied the source code without a licence; the code is a literary work under s.3 CDPA; therefore…")
- [ ] **C — Conclusion:** reach a clear, reasoned conclusion. Don't hedge excessively — examiners reward a definite answer with reasoning. ("Therefore, Z has prima facie infringed the copyright in the software.")
- [ ] Repeat IRAC for each distinct legal issue.

### Answer Structure

- [ ] Write a brief introduction identifying the area(s) of law in play and the parties.
- [ ] Use headings for each issue to signpost your answer.
- [ ] Keep each IRAC block focused — do not mix multiple issues in one block.
- [ ] Write a short conclusion summarising findings and any practical recommendations if asked.
- [ ] Use precise legal terminology throughout (e.g., "data controller", "lawful basis", "copyleft", "IP assignment") — this demonstrates mastery.

### Time Management (2 hours)

- [ ] Read the question + plan: ~15 minutes.
- [ ] If multiple questions: divide remaining time proportionally by marks.
- [ ] Single long question: allocate ~10 minutes per major issue; keep track.
- [ ] Leave 10 minutes at the end to review and add missed points.
- [ ] Never spend all time on one issue; a partial answer on all issues beats a perfect answer on one.

### Top-Band Answer Qualities

- [ ] Identifies ALL issues (not just the obvious one).
- [ ] Cites statute/case authority for every rule stated.
- [ ] Applies the law precisely to the facts — does not merely repeat the facts or recite abstract law.
- [ ] Acknowledges counterarguments or ambiguities where they exist ("on the other hand…").
- [ ] Reaches clear, justified conclusions.
- [ ] Written in clear, structured prose — not bullet points (unless bullets are specifically invited).

---

## 6. Open-Book / TRA Logistics

- [ ] **Verify** on the module page / Blackboard/CATE whether the TRA is open-book, and if so, what materials are permitted (personal notes only? textbooks? internet?).
- [ ] Prepare a **condensed one-page cheat-sheet** covering: the 7 GDPR principles (Art 5), the 6 lawful bases (Art 6), data subject rights (Arts 13–22), key CDPA sections (s.3, s.11, s.16, s.50A/B, s.296A), licence families (MIT/Apache/GPL/AGPL/LGPL obligations in one line each), IRAC template, key definitions.
- [ ] Organise notes by legal area with clear headings so you can find information quickly under exam pressure.
- [ ] Prepare a **statute reference card**: key section numbers and what they cover for CDPA, UK GDPR (Article numbers), DPA 2018, UCTA 1977, CRA 2015.
- [ ] If internet is permitted, bookmark: ICO website (guidance on lawful bases, rights, breaches), legislation.gov.uk (CDPA 1988, DPA 2018).
- [ ] Practice navigating your notes quickly — simulate exam conditions (timed, no searching for more than 30 seconds).
- [ ] **Do not rely on open-book access to compensate for lack of understanding** — time pressure means you need to know the framework; notes are for checking details (section numbers, definitions).
- [ ] Log into the TRA platform the evening before to confirm access and test your connection.

---

## 7. Link to the DRP Copyright/Legal Issues Report

> The Copyright/Legal Issues Report is 10% of Project Documentation (due 19 Jun 19:00, 1×A4). Revision for the TRA directly strengthens this report.

- [ ] **Audit all third-party resources** used in your DRP project: libraries/packages (npm, pip, etc.), fonts, icons, images, datasets, APIs, code snippets, frameworks.
- [ ] For each resource, record: resource name, version, licence (e.g., MIT, Apache 2.0, GPL v3), source/URL, and the obligation it imposes on your project (attribution? source disclosure? copyleft propagation?).
- [ ] Identify any **licence conflicts**: e.g., if your project uses a GPL v3 library and you intend to keep source private — this is a conflict; note it and how it is resolved or avoided.
- [ ] Check whether any library is **AGPL** — if so, running it as a web service obliges you to make source available to users; flag this.
- [ ] Confirm all **image/font/icon licences** permit use in the DRP project context (commercial use? attribution required? share-alike?).
- [ ] Use the TRA's copyright/licence knowledge to write the **legal discussion** section of the report: explain *why* each licence choice is legally permissible, and what obligations you have met.
- [ ] Apply data protection principles to document any personal data your DRP app collects (even prototype user-testing data): what basis you relied on, how long data is kept, what security measures are in place.
- [ ] Confirm no college/copyright rule violations (DRP technical requirement #8) — this is checked in the report.
- [ ] Draft the **licence table** (resource / version / licence / obligation) before the TRA so revision reinforces what you have already documented.

---

## Top-Band Summary — Highest-Leverage Revision Moves

1. **Master IRAC.** The case study is applied — you will lose marks for knowing the law but failing to connect it to the facts. Practice writing short IRAC responses from past law scenarios.
2. **Know the 7 GDPR principles and 6 lawful bases cold.** Data protection questions are near-certain; being able to state these without checking notes saves time.
3. **Learn the open-source licence matrix.** Permissive (MIT/Apache) vs weak copyleft (LGPL) vs strong copyleft (GPL) vs network copyleft (AGPL) — obligations in one sentence each. This is both TRA and report content.
4. **IP ownership rules.** Employee vs contractor vs student; the single s.11(2) CDPA rule appears in almost every software IP scenario.
5. **Controller vs processor and the 72-hour breach notification rule.** These two data protection points are highly examinable and require precision.
6. **Attend the Summer week 5–6 Law TRA teaching sessions.** Case studies used in teaching are the closest proxy for the exam question format.
7. **Build your open-book cheat-sheet now** while revising — the act of condensing forces understanding, and the sheet will be useful in the exam.
