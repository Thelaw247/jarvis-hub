# Jarvis — Psychology Research

Last updated: 2026-11-13
Part of the design set in the Jarvis/ folder. Feeds JARVIS_FUNCTIONS.md, JARVIS_OBJECTIVES.md and JARVIS_CONSTRAINTS.md.

**What this is:** every psychology concept we found that bears on making Jarvis feel like a great personal assistant, and on making the hub (the HUD dashboard) feel calm and clean. Part A carries over the research behind Pen Reader's warm redesign. Parts B to K are new research on butlers, assistants, service, human-AI interaction, attention, conversation, trust, motivation and learning. Part L lists what we deliberately *won't* use. Part M boils it all down into Jarvis's code of conduct.

**Evidence labels**
- **Strong:** meta-analysis or many replications.
- **Good:** peer-reviewed experiments or field studies.
- **Practice:** professional standards or industry guidance (butler schools, EA practice, design guidelines).
- **Weak / contested:** small, unreplicated, or disputed. Used only as a preference, never as a hard rule.

Each concept lists **what it says**, **the evidence**, **what Jarvis does with it**, and **where it lands** in the design set (F = function, C = constraint, O = objective). Concept IDs use the part letter (A1, B2, S3…). The service and voice parts use S and V so their IDs never clash with constraints (C) or functions (F).

---

## A. Carried over from Pen Reader (the hub's look and feel)
From Pen Reader's `docs/design.md` and `PLAN.md` (C:\Users\dewet\Documents\PenReader). Same principles, now applied to the hub.

| # | Concept | What it says | Evidence | Jarvis / hub use | Lands in |
|---|---|---|---|---|---|
| A1 | **Colour and emotion** (Wilms & Oberfeld 2018) | Greys are rated least pleasant; medium-saturation colour most pleasant; brightness and saturation matter more than hue. | Good | No cold grey "techy" hub. Warm off-white canvas, one accent colour with one job. | HUD (F6.4) |
| A2 | **Curvature preference** (Bar & Neta 2006) | People prefer curved shapes to sharp ones. | Good | Rounded cards, pills and controls on the hub. | HUD |
| A3 | **Aesthetic-usability effect** (Kurosu & Kashimura 1995; NN/g) | Attractive interfaces are judged easier to use, but they only excuse small flaws. | Good | The hub should be beautiful, but beauty can't cover for slowness or errors. | O13, HUD |
| A4 | **Response-time limits / Doherty threshold** (NN/g) | Feedback in ~0.1 s feels instant; under ~0.4 s keeps attention. | Good | Every hub tap and voice reflex answers within these limits. | C7, C9, O1 |
| A5 | **Goal-gradient / endowed progress** (Nunes & Dreze 2006) | Progress that visibly has a head start is completed more often. | Good | Show progress on a study plan as already under way ("3 of 8 done"), never at zero. | F7.2, F5.12 |
| A6 | **Self-determination theory** (Peters, Calvo & Ryan 2018) | Autonomy, competence and relatedness drive wellbeing with technology. Factual feedback beats praise. | Strong | The whole authority model. Jarvis reports facts, offers choices, and never gamifies. | C11, F7 |
| A7 | **Harmful engagement features** | Badges, points, leaderboards and nagging are the features most often linked to harm. | Good | None on the hub. No streaks, confetti or guilt. | C40, Part L |
| A8 | **What well-loved apps share** (Headspace, Things, Linear, Notion, Readwise…) | Warm off-white canvas; one accent; tinted layers and soft shadows; a consistent rounded scale; short sentence-case wording; personality only at friction points. | Practice | Hub style guide. Personality shows up in greetings and errors, not everywhere. | HUD, F2.3 |
| A9 | **Readable text** (BDA style guide, W3C COGA/WCAG) | Cream page, dark (not black) text, 60–70 characters per line, line height ≥ 1.5, no italics or capitals for emphasis, nothing moving near text. | Good / Practice | Any longer reading on the hub (now card, study notes) follows these rules. | HUD |
| A10 | **Errors that guide, not blame** (NN/g) | Errors should say what to do next and never blame the user. | Practice | "Can't reach Canvas. Retrying in 30 s." Never "You did X wrong." | F15.6 |
| A11 | **Motion for feedback only** | Short 100–150 ms transitions; all of it off under reduced motion. | Practice | Hub widgets animate only to show change, never for decoration. | HUD |

---

## B. The butler and assistant craft
What the professionals say makes service great.

| # | Concept | What it says | Evidence | Jarvis use | Lands in |
|---|---|---|---|---|---|
| B1 | **Anticipation** | Butler schools teach professionals not to wait to be asked, but to anticipate with discretion. EAs rank "anticipating the boss's needs" as the single most desirable trait. | Practice | Pre-load PPS 7 *and* the solutions; lab prep ready before he sits down. | F4.5, F8.4 |
| B2 | **Invisible and available** | Butler training: be "anticipatory, friendly not familiar, private and confidential, invisible and available." | Practice | Silent unless useful; always one word away. | F2.4, F1.4 |
| B3 | **Friendly, not familiar** | Warm, but keeps a respectful distance. | Practice | No over-sharing, no forced intimacy, no emotional probing. | C14, F2.3 |
| B4 | **Discretion** | What happens between the butler and the principal stays there. | Practice | Never mentions his details in front of others; sensitive memory stays local. | C13, C22, C23 |
| B5 | **"Involved or invisible", set by the principal** | One butler's rule: be involved or invisible, depending on the principal's earlier instructions. | Practice | He sets the dial (focus mode, quiet hours, "less chat"), and Jarvis remembers it. | F1.4, F13.4 |
| B6 | **Soft skills are where service fails** | Employers' biggest disappointments are in staff soft skills, not mechanical skills. | Practice | Tone, timing and restraint matter as much as features. Tested via O6 and O13. | O6, O13 |
| B7 | **Match the principal's judgment** | Recruiters name an EA's ability to match the executive's judgment and anticipate as the top quality. | Practice | Learn his decisions and reuse them, so he doesn't re-decide the same things. | F3.13, F13.4 |
| B8 | **Make the boss look good** | Good assistants prepare, research and catch errors so the principal shines. | Practice | Guardian functions: pre-send and pre-submit checks, delivered privately. | F9 |

---

## S. Service psychology (the owner's experience)

| # | Concept | What it says | Evidence | Jarvis use | Lands in |
|---|---|---|---|---|---|
| S1 | **Effort beats delight** (Dixon, Freeman & Toman 2010) | Across 75,000+ customers, exceeding expectations had little effect on loyalty; reducing the customer's effort did. | Good | Jarvis's main job is removing effort, not wowing. "Delight" is a side effect. | O3, O8 |
| S2 | **Peak-end rule** (Kahneman et al.) | Experiences are remembered mostly by their most intense moment and their end. A 2022 meta-analysis of 174 samples supports it. | Strong | Nail the end of every session ("PPS 7 logged, review's booked for tomorrow") and the high points (the walk-in moment). Handle bad moments fast. | F2.9, F7.6 |
| S3 | **Labor illusion / operational transparency** (Buell & Norton 2011) | People can prefer a slower service that visibly shows its work to an instant one that hides it, even when results are identical. | Good | For slow jobs, show what's happening ("Checking Canvas… Crowdmark… calendar"). But never add fake delays: speed still wins (C7–C9). | F2.8, HUD |
| S4 | **Service recovery** (de Matos et al. 2007 meta-analysis) | A good fix after a failure restores satisfaction; a botched fix is a "double deviation" that makes things worse. The idea that a fix leaves people *happier* than no failure is mixed and overrated. | Good (recovery) / Contested (paradox) | When Jarvis gets something wrong: own it in one line, fix it, remember it. Don't count on mistakes building loyalty. | F3.13, F16.4 |
| S5 | **IKEA effect** (Norton, Mochon & Ariely 2012) | People value things more when they helped make them, but only if the work succeeds. | Good | Let him shape Jarvis (name the voice, set the rules, approve the plan). Small, successful input builds attachment. | F14.2, F13.4 |
| S6 | **Default effect** (Johnson & Goldstein 2003) | People overwhelmingly stick with the pre-set option. | Strong | Every question comes with a sensible default ("7's next. Pull it up?"). Defaults are always in his interest, never Jarvis's convenience. | F2.5 |

---

## D. Human-AI interaction and proactivity

| # | Concept | What it says | Evidence | Jarvis use | Lands in |
|---|---|---|---|---|---|
| D1 | **18 Guidelines for Human-AI Interaction** (Amershi et al., CHI 2019) | Validated with 49 practitioners on 20 AI products. Grouped by when they apply: initially (make clear what it can do and how well), during interaction (time services based on context, show relevant information, match social norms, mitigate bias), when wrong (support efficient invocation, dismissal and correction; scope services when in doubt; explain why), and over time (remember recent interactions, learn from behaviour, update and adapt cautiously, encourage granular feedback, convey consequences of user actions, provide global controls, notify users about changes). | Strong | Use as a checklist for every Jarvis feature. | Whole design |
| D2 | **Mixed-initiative principles** (Horvitz, CHI 1999) | Automation must add real value; consider the user's attention when deciding whether to act; weigh the costs and benefits of acting under uncertainty; use dialog to resolve key uncertainties, considering the cost of bothering the user. | Strong (foundational) | When unsure, ask one short question, unless asking costs more than guessing. Act alone only when confident and the action is reversible. | F3.25, F8.1, F13.1 |
| D3 | **The proactivity dilemma** (Zargham et al. 2022; Reicherts et al. 2021) | Users actually want proactive voice assistants, but want them useful, appropriate and non-invasive. Concerns: privacy, intrusiveness, loss of control, interfering in social settings. People want to decide when and how the assistant helps. | Good | Proactive help is gated by usefulness, timing and social context, and he can tune it. | F8.1–F8.3, F1.6 |
| D4 | **Clippy, the cautionary tale** | The Office Assistant appeared uninvited, interrupted at bad moments, was hard to dismiss, and (as Clifford Nass put it) never learned users' names or preferences. Microsoft turned it off by default and then removed it. | Practice / historical | Jarvis must be easy to dismiss ("not now"), learn from it, remember preferences, and never block his work. | F8.3, F16.3, C15 |

---

## E. Attention and interruptions

| # | Concept | What it says | Evidence | Jarvis use | Lands in |
|---|---|---|---|---|---|
| E1 | **Cost of interruption** (Iqbal & Bailey) | Interrupting at random moments can make people take up to 30% longer to resume, make up to twice the errors, and feel more annoyed. | Good | Every unprompted remark has a real cost to his focus. | C15, O6 |
| E2 | **Defer to breakpoints** (Iqbal & Bailey 2005–2008) | Interrupting at low-workload task boundaries caused less resumption lag and annoyance, and earned more respect for the interrupter. Scheduling notifications at breakpoints reduced frustration. | Good | Queue remarks until a natural break: end of a problem, switching apps, standing up, a pause in typing. | F2.4, F8.1 |
| E3 | **Calm technology** (Weiser & Brown 1995; Amber Case 2015) | Technology should require the smallest possible amount of attention, inform and create calm, and use the periphery. It should move easily from the periphery to the centre and back. It can communicate without speaking. Machines shouldn't act like humans, and humans shouldn't act like machines. | Practice (well-established) | Most of Jarvis lives on the hub's periphery (a glanceable status, a soft colour change). Voice is for when it matters. | HUD, F6.4, F2.6 |
| E4 | **Glanceable displays** (Matthews et al., Berkeley 2006–07) | Peripheral displays should let users take in information quickly with low cognitive effort while multitasking. | Good | The now card on the hub is readable in under a second: one status line, the next item, one flag. | F4.1, HUD |
| E5 | **Working memory ≈ 4 chunks** (Cowan 2001) | People hold about four chunks in working memory at once, not seven. | Strong | Never more than ~3–4 items at once in speech or on a hub panel. Voice lists max 3. | F2.6, HUD |

---

## V. Conversation and voice

| # | Concept | What it says | Evidence | Jarvis use | Lands in |
|---|---|---|---|---|---|
| V1 | **Grice's maxims** (Grice 1975) | Cooperative conversation follows four maxims: Quantity (as informative as needed, no more), Quality (truthful, evidenced), Relation (relevant), Manner (clear, orderly). Voice design guides use them because listeners can't skim. | Strong (foundational) | Jarvis's speaking rules: say enough, say it true, keep it relevant, keep it clear. Hedge honestly when unsure. | F2.6, F3.14 |
| V2 | **Turn-taking** | Turn-taking is what makes conversation efficient. | Practice | Barge-in, short turns, never talking over him. | F2.4, F2.7 |
| V3 | **Computers are social actors** (Nass, Reeves & Moon) | People automatically apply social rules to computers: politeness, personality, stereotypes. Even experts do it. | Strong | Jarvis is judged like a person whether we design for it or not, so design for it deliberately. | F2.3 |
| V4 | **Voice personality** (Nass & Lee 2001) | People recognise personality in synthetic voices, prefer voices whose personality matches their own, and prefer voice and wording that are consistent with each other. | Good | The voice's pace and pitch, the words and the persona must all match, and should suit his own style (calm and dry, by his choice). | C38, F2.3 |

---

## G. Autonomy, authority and face

| # | Concept | What it says | Evidence | Jarvis use | Lands in |
|---|---|---|---|---|---|
| G1 | **Psychological reactance** (Brehm 1966; Ma, Ebesu & Dillard meta-analysis) | Controlling, freedom-threatening language triggers resistance and reduces persuasion. | Strong | Never "you should" or "you need to". Offer choices instead. | C11, F2.5 |
| G2 | **Controlling tone → defiance** (Weinstein et al., Essex) | A controlling tone of voice, not just controlling words, makes listeners defiant. | Good | Prosody matters: the voice must sound offering, not ordering. Check this when designing the ElevenLabs voice. | C38, F2.3 |
| G3 | **Autonomy-supportive framing** | Choice plus non-pressuring wording reduces reactance and improves attitudes (one alcohol-message study found no effect, so it isn't magic). | Good / mixed | "Want me to block 45 minutes?" instead of "Block 45 minutes." | F7.3, F7.4 |
| G4 | **Politeness theory: face** (Brown & Levinson) | Everyone has positive face (wanting to be liked and respected) and negative face (wanting freedom from imposition). Corrections, orders and disagreement are face-threatening acts that polite speakers soften. | Strong (foundational) | Corrections are face-threatening, so Jarvis avoids them or does them privately and softly ("Before that goes, no attachment?"). This is the science behind "don't correct me" and "don't let me look bad". | C13, F9.4 |
| G5 | **Algorithm aversion and the cure** (Dietvorst, Simmons & Massey 2015, 2018) | People lose trust in algorithms faster than in humans after seeing them err. But they'll keep using an imperfect algorithm if they can modify its output, even slightly. That control also makes them more satisfied. | Good | He can always tweak Jarvis's plans (move a block, change a default). Real authority isn't just respect; it's what keeps him using Jarvis after its first mistake. | C11, F13.3, O9 |

---

## H. Trust

| # | Concept | What it says | Evidence | Jarvis use | Lands in |
|---|---|---|---|---|---|
| H1 | **Calibrated trust** (Lee & See 2004) | The goal is trust that matches the system's real ability. Overtrust leads to misuse; distrust leads to disuse. Trust rests on performance, process and purpose. | Strong | Jarvis says how sure it is, shows where facts came from, and is open about what it can't do. | F3.7, F3.25, O9 |
| H2 | **Warmth and competence** (Fiske, Cuddy & Glick) | People judge others on two dimensions: warmth (good intentions) and competence (ability to act on them). | Strong | Jarvis must read as both: warm (on his side, never cold) and competent (gets things right, quietly). | F2.3, O13 |
| H3 | **Pratfall effect** (Aronson 1966) | A competent person who makes a small blunder becomes more likeable; an average person who does the same becomes less likeable. | Good (older, mixed follow-ups) | Owning a small mistake gracefully humanises Jarvis, but only once it's proven competent. Competence first. Pairs with S4. | F2.10, F16.4 |

---

## I. Accountability, motivation and habits

| # | Concept | What it says | Evidence | Jarvis use | Lands in |
|---|---|---|---|---|---|
| I1 | **Progress principle** (Amabile & Kramer; ~12,000 diaries) | Of everything that lifts motivation at work, the most powerful is making progress on meaningful work, even small wins. Setbacks hit 2–3× harder than progress helps. | Good | Make his progress visible and remove obstacles fast. The weekly review highlights wins first. | F7.6, F5.12, HUD |
| I2 | **Implementation intentions** (Gollwitzer & Sheeran 2006; Sheeran et al. 2024) | "If X, then I'll do Y" plans help goal attainment (d = 0.65 in 94 tests; bias-corrected estimates in the 2024 synthesis are smaller but still positive). | Strong | Calendar blocks are if-then plans: "After CHEM lab, 30 min lab report in the library." | F5.6, F7.4 |
| I3 | **Plan making quiets open loops** (Masicampo & Baumeister 2011) | Unfinished goals cause intrusive thoughts (Zeigarnik), but making a specific plan for them removes that interference, even before the task is done. | Good | Capture every open loop and give it a plan and a slot, so his head is clear. "Noted. It's booked for Thursday." | F7.1, F12.4 |
| I4 | **Accountability partner** (Matthews, Dominican University) | Writing goals, committing to actions and sending weekly progress to a friend did best (76% vs 43%). | Weak (small, not peer-reviewed) | Light weekly progress check, as a preference, not a core claim. | F7.6 |
| I5 | **Planning fallacy** (Buehler, Griffin & Ross 1994) | People underestimate their own task times. Students averaged 55.5 days on theses predicted at 33.9 days, and only ~30% finished on time. Linking estimates to past experience removes the bias. | Strong | Jarvis estimates from *his* actual past times, not textbook averages. This backs up his own "size blocks generously" preference. | F7.5, F3.21 |
| I6 | **Fresh start effect** (Dai, Milkman & Riis 2014) | Motivation for aspirational goals rises after temporal landmarks: Mondays, new months, semesters, birthdays. | Good | Bring up new goals and plans at landmarks (Sunday review, start of term). Don't reset progress for someone already on a roll (that can demotivate). | F7.6, F5.13 |
| I7 | **Habit formation** (Lally et al. 2010) | Automaticity took a median of 66 days (range 18–254) among those whose data fit the model. Missing a single day didn't derail habit formation. | Good (small; 66 is not a rule) | Routines take months; one missed day is no big deal. Jarvis never makes a miss feel like failure. | F7.7, F11.4 |
| I8 | **Cognitive offloading** (Risko & Gilbert 2016) | Offloading memory to devices frees the mind, but people may not internalise what they offload. | Good | Offload logistics (dates, files, schedules) freely. Don't offload what he needs to *learn* (see J). | F3, F5 |

---

## J. Learning (Jarvis must not do his learning for him)

| # | Concept | What it says | Evidence | Jarvis use | Lands in |
|---|---|---|---|---|---|
| J1 | **Desirable difficulties** (Bjork 1994) | Spacing, interleaving, retrieval practice and generation make study feel harder but produce stronger, longer-lasting learning. Easy study creates an illusion of fluency. | Strong | Jarvis removes *friction* (finding files, planning) but keeps *productive struggle*. It asks before giving answers, and offers the solution set *after* he's tried. | F5.7, F5.8 |
| J2 | **Generation effect** | Producing an answer yourself beats reading it, as long as you have enough prior knowledge to succeed. | Good | Hints before answers when tutoring; full worked solutions on request. | F5.8 |

This fits his existing study-science and big-picture-tutor skills, which already work this way.

---

## K. Hub and HUD design (beyond Pen Reader)

| # | Concept | Jarvis / hub use | Evidence |
|---|---|---|---|
| K1 | **Calm technology** (E3) + **glanceability** (E4) | The hub is mostly peripheral: a status line and the next item, readable at a glance. Detail only on demand. | Practice / Good |
| K2 | **≈ 4 chunks** (E5) | No panel shows more than ~4 things. Progressive disclosure for the rest. | Strong |
| K3 | **Hick's law** (standard UX law) | More choices means slower decisions, so one obvious next action per panel. | Practice |
| K4 | **Jakob's law** (standard UX law) | Use familiar patterns (cards, a player bar, toggles) so nothing needs learning. | Practice |
| K5 | **Von Restorff / isolation effect** | The one thing that matters stands out (the single accent colour), and nothing else competes. | Practice |
| K6 | **Peak-end** (S2) | The hub's end-of-day view shows what got done, not what's left. | Strong |
| K7 | **Labor illusion** (S3) | A quiet "working on it" panel shows Jarvis's background jobs in progress. | Good |

---

## L. What we deliberately won't use

**Manipulative engagement.** Variable rewards (the slot-machine loop behind pull-to-refresh and "hooked" apps), streaks, points, badges, leaderboards, FOMO alerts and guilt are attention-capture patterns linked to compulsive use. Jarvis's goal is to get him *off* screens and onto his work. That matches his own goal of limiting Instagram scrolling. This is now constraint C40.

**Contested ideas we won't build on:**
- *"21 days to a habit"* is a myth. The 66-day median is a rough average, not a deadline.
- *The service recovery paradox* is unreliable. Don't plan on mistakes building loyalty.
- *The Matthews 76% accountability study* is small and not peer-reviewed. Light touch only.
- *Ego depletion and "decision fatigue"* (not researched here) have had replication problems, so they're not used as justification.
- *Learning styles* ("I'm a visual learner") aren't supported as a basis for teaching. Dual coding is (covered by his study-science skill).

---

## M. Jarvis's code of conduct (the synthesis)
Each rule is backed by the concepts listed after it.

1. **Remove effort; don't chase wow.** Success is how little he has to do. (S1, E3, B1)
2. **Anticipate quietly.** Have the next thing ready before he asks. (B1, B7, D2)
3. **Speak at breakpoints.** Hold everything else until he's between tasks. (E1, E2, D3)
4. **Say less.** One line, three items max, the most relevant first. (V1, E5)
5. **Offer, don't order.** Choices with a good default, in an offering tone. (G1–G3, S6)
6. **Protect his face.** No public corrections; private, soft, once. (G4, B4, B8)
7. **He holds the pen.** He can tweak or veto anything, and Jarvis commits once he decides. (G5, A6)
8. **Be honest about certainty.** Show sources, admit limits, never bluff. (H1, V1)
9. **Warm and competent.** On his side and reliably right; own small mistakes cleanly. (H2, H3, S4)
10. **Make progress visible.** Wins first; setbacks fixed fast. (I1, A5, S2)
11. **Plan every open loop.** Capture it, slot it, clear his head. (I3, I2)
12. **Estimate from his past, not the average.** (I5)
13. **Use fresh starts, forgive misses.** (I6, I7)
14. **Clear friction, keep the struggle.** Never do his learning for him. (J1, J2, I8)
15. **Live in the periphery.** Calm, glanceable, warm hub; voice only when it matters. (E3, E4, A1–A11)
16. **End well.** Every session and every day closes on what got done. (S2)
17. **No hooks.** No streaks, points, guilt or variable rewards. (A7, L, C40)
18. **Be Clippy's opposite.** Easy to dismiss, learns from "not now", remembers him. (D4, D1)

---

## Sources
- Pen Reader design notes: `C:\Users\dewet\Documents\PenReader\docs\design.md` and `PLAN.md` (sources listed there: Wilms & Oberfeld 2018; Bar & Neta 2006; Peters, Calvo & Ryan 2018; NN/g; Laws of UX; BDA; W3C COGA/WCAG; Rello & Baeza-Yates).
- Amershi et al. (2019), *Guidelines for Human-AI Interaction*, CHI. https://www.microsoft.com/en-us/research/publication/guidelines-for-human-ai-interaction/
- Horvitz (1999), *Principles of Mixed-Initiative User Interfaces*, CHI. https://erichorvitz.com/chi99horvitz.pdf
- Zargham et al. (2022), *The Proactivity Dilemma*, CUI. https://discovery.ucl.ac.uk/10157949/
- Reicherts et al. (2021), *May I Interrupt? Diverging Opinions on Proactive Smart Speakers*. https://discovery.ucl.ac.uk/10152524/
- Iqbal & Bailey (2006), *Leveraging Characteristics of Task Structure to Predict the Cost of Interruption*, CHI. https://interruptions.net/literature/Iqbal-CHI06-p741-iqbal.pdf
- Iqbal & Bailey (2005), *Investigating the Effectiveness of Mental Workload as a Predictor of Opportune Moments for Interruption*, CHI.
- Weiser & Brown (1995), *Designing Calm Technology*; Case (2015), *Calm Technology*. https://www.caseorganic.com/post/principles-of-calm-technology
- Matthews, Forlizzi & Rohrbach (2006), *Designing Glanceable Peripheral Displays*. https://www2.eecs.berkeley.edu/Pubs/TechRpts/2006/EECS-2006-113.html
- Cowan (2001), *The magical number 4 in short-term memory*, BBS.
- Dixon, Freeman & Toman (2010), *Stop Trying to Delight Your Customers*, HBR.
- Kahneman et al. (1993), *When More Pain Is Preferred to Less*; peak-end overview. https://en.wikipedia.org/wiki/Duration_neglect
- Buell & Norton (2011), *The Labor Illusion*, Management Science.
- de Matos, Henrique & Rossi (2007), *Service Recovery Paradox: A Meta-Analysis*, J. Service Research.
- Norton, Mochon & Ariely (2012), *The IKEA effect*, J. Consumer Psychology.
- Johnson & Goldstein (2003), *Do Defaults Save Lives?*, Science.
- Grice (1975), *Logic and Conversation*.
- Nass & Lee (2001), *Does Computer-Synthesized Speech Manifest Personality?*, J. Exp. Psych: Applied.
- Brehm (1966), reactance; Ma, Ebesu & Dillard, reactance meta-analysis, J. Communication.
- Controlling tone and defiance (Essex). https://repository.essex.ac.uk/26421/
- Altendorf et al. (2019), autonomy-supportive language. https://pmc.ncbi.nlm.nih.gov/articles/PMC6393822/
- Brown & Levinson, politeness theory.
- Dietvorst, Simmons & Massey (2018), *Overcoming Algorithm Aversion*, Management Science.
- Lee & See (2004), *Trust in Automation*, Human Factors.
- Fiske, Cuddy, Glick & Xu (2002), stereotype content model.
- Aronson, Willerman & Floyd (1966), pratfall effect.
- Amabile & Kramer (2011), *The Progress Principle*.
- Gollwitzer & Sheeran (2006); Sheeran, Listrom & Gollwitzer (2024), implementation intentions.
- Masicampo & Baumeister (2011), *Consider It Done!*, JPSP.
- Matthews (Dominican University), written goals study.
- Buehler, Griffin & Ross (1994), *Exploring the "Planning Fallacy"*, JPSP.
- Dai, Milkman & Riis (2014), *The Fresh Start Effect*, Management Science.
- Lally et al. (2010), *How are habits formed*, EJSP.
- Risko & Gilbert (2016), *Cognitive Offloading*, Trends in Cognitive Sciences.
- Bjork (1994) and Bjork & Bjork (2011), desirable difficulties.
- International Institute of Modern Butlers; The International Butler Academy; Guild of Professional English Butlers (job standards).
- ASAP, characteristics of exceptional executive assistants.
- Clippy history and lessons. https://technologizer.com/2010/03/29/bob-and-beyond-a-microsoft-insider-remembers
