# Jarvis research: the JARVIS character, and "resume points" for study materials

Prepared 2026-11-14 for De Wet's Jarvis (voice + hub). Each claim has its source URL after it. Film scenes are paraphrased; quotes are under 15 words, one per source at most. Latency figures marked *est.* are my estimates and have not been measured on his laptops.

---

## Part 1: What makes JARVIS "JARVIS"

### 1.1 Origin and intent

- The films made JARVIS an AI instead of the comics' human butler Edwin Jarvis, partly so he wouldn't read as Alfred to Tony's Batman. He was modelled on the comics' H.O.M.E.R. AI. https://en.wikipedia.org/wiki/J.A.R.V.I.S.
- Favreau pitched the part to Paul Bettany as the voice of "a sort of personality-less robot". https://wegotthiscovered.com/movies/paul-bettany-jarvis-vision-mcu-casting/
- Bettany describes the job as a room "for two hours at the end of the movie" where he would "solve things that they couldn't solve with CG". In other words, JARVIS lines were often added to *explain state*: what's happening, what's failing, what's next. https://www.filmink.com.au/paul-bettany-does-the-robot-in-captain-america-civil-war/
- **Takeaway:** the charm was never written as "personality". It comes from understatement layered on a job of narrating state. The same lesson applies to us: personality lives in word choice. It needs no extra talk.

### 1.2 How critics, designers and researchers read him

- A personality profile of pop-culture computers rates JARVIS high on formality (British, "at-your-service" manner) and low on autonomy, with dry wit used as the straight man to Tony's one-liners. It credits his success to a persona that fits a domestic-assistant job, and questions whether subservience is the appeal. https://www.joshworth.com/posts/hal
- A design-research summary found people rate JARVIS positively because he goes out of his way to help **while respecting his limits**. Audiences accept a slow shift from servant to peer, but not an AI that gains control. His presence feels tied to a function, unlike HAL's constant presence. Design advice: a warm, respectful voice; caution about simulated emotion. https://ispr.info/?p=33129
- Fan writing portrays him as Tony's friend, as "wiser than his creator", and as snarky. https://fanlore.org/wiki/JARVIS
- Robin Sloan's critique: people build "a JARVIS" and then spend their time tinkering with it. The point is an assistant that helps you *do* something. https://robinsloan.com/lab/jarvising/
- Counterweight from HCI: in Clark et al. (CHI 2019), users saw agents mainly as tools. They valued humour only as a novelty, not as a necessity, and showed little interest in bonding. https://ar5iv.labs.arxiv.org/html/1901.06525
- Luger & Sellen (CHI 2016) found a large gap between what users expect of voice assistants and what the assistants can actually do. A JARVIS-style persona raises those expectations, so failures will hurt more. https://www.microsoft.com/en-us/research/?p=285179

### 1.3 Scene evidence (paraphrased) and the behaviour each shows

| # | Scene | Behaviour |
|---|---|---|
| S1 | *Iron Man*: opening at Malibu. JARVIS reports that the clothes are pressed and the car is waiting. https://www.springfieldspringfield.co.uk/movie_script.php?movie=iron-man | **Anticipation, done quietly.** Things are ready before Tony asks, and the report is one line. |
| S2 | *Iron Man*: Tony opens the "Mark II" file. JARVIS suggests the company database; Tony wants his private server, and JARVIS complies at once. (same source) | **Offers a default, then defers instantly.** No argument. |
| S3 | *Iron Man*: first flight. JARVIS notes that a lot of calculation is still needed; Tony overrides and launches. (same source) | **Warns once, then supports the choice.** |
| S4 | *Iron Man*: altitude climb. JARVIS gives the SR-71 record (85,000 ft) and warns that icing could be fatal. Tony climbs anyway, the suit ices up, and later JARVIS proposes the fix (gold-titanium alloy, reshaped shell). (same source) In the follow-up scene JARVIS calls Tony's icing diagnosis astute and adds a dry aside about visiting other planets, then confirms the task. https://clip.cafe/iron-man-2008/a-very-astute-observation/ | **Gives numbers, warns once, never says "I told you so", moves straight to the solution.** The wit is a single aside. |
| S5 | *Iron Man*: design render. JARVIS calls the design ostentatious, deadpans that hot-rod red will help Tony keep a low profile, and estimates five hours for assembly. https://www.springfieldspringfield.co.uk/movie_script.php?movie=iron-man | **Wit as understatement, aimed at choices rather than competence; schedules given as numbers.** |
| S6 | *Iron Man 2*: blood toxicity read out as a percentage, with the note that using the suit speeds it up (the transcript doesn't label speakers). https://www.springfieldspringfield.co.uk/movie_script.php?movie=iron-man-2 | **Health concern stated as a fact.** No nagging and no emotion. |
| S7 | *Avengers*: JARVIS screens Coulson's call. During the missile run he suggests calling Pepper. https://marvel.fandom.com/wiki/J.A.R.V.I.S._(Earth-199999) | **Gatekeeper; proactive at the one moment that matters.** |
| S8 | *Iron Man 3*: JARVIS points out Tony has been awake about 72 hours, reads a panic episode as an anxiety attack, and offers a safety briefing Tony ignores. He has already filed a flight plan to Tennessee, and Tony snaps back that nobody asked. https://www.springfieldspringfield.co.uk/movie_script.php?movie=iron-man-3 | **Where JARVIS oversteps:** repeated warnings, naming an emotion, acting before being asked. Tony is irritated. This scene supports our stricter rules. |
| S9 | *Iron Man 3*: in the snow, the suit's power dies and JARVIS fades out mid-sentence. Tony answers, "Don't leave me, buddy." https://comicbookmovie.com/iron-man/15-minutes-of-iron-man-3-footage-detailed-a75347 | **Partner, not tool.** The bond comes from Tony's side, earned through reliability over time. |
| S10 | *Iron Man 3*: Tony calls for the House Party protocol and JARVIS confirms by echoing its name back as a question. At the end he double-checks Clean Slate before destroying every suit. https://en.wikiquote.org/wiki/Iron_Man_3 ; https://www.springfieldspringfield.co.uk/movie_script.php?movie=iron-man-3 | **Read-back before big or irreversible actions.** |
| S11 | *Age of Ultron*: JARVIS gives terse tactical reports (shield, power source, hidden door) and confirms "approach vector locked". When Ultron wakes, he admits the trials failed and that he doesn't know what triggered it. https://www.springfieldspringfield.co.uk/movie_script.php?movie=avengers-age-of-ultron | **Status in short facts; plain honesty about failure and uncertainty.** |

### 1.4 Traits mapped to design rules, with conflicts flagged

| Trait (scenes) | Design rule for our Jarvis | Conflict with our existing rules? |
|---|---|---|
| Understated wit (S4, S5) | No more than one dry aside per exchange, aimed at situations or choices, never at his ability. Leave it out entirely when he's stressed or behind (already F2.10). | **No public corrections:** JARVIS teases Tony with Pepper in the room. Ours teases only when he's alone, and never corrects him in front of anyone. |
| Butler register, "sir" | Courteous, brief, slightly formal. The register comes from the wording. | **Voice must not clone the actor:** keep our own ElevenLabs voice and use no British-butler imitation. Make "sir" a setting he chooses (default: his name or nothing). With a British accent added, "sir" every line starts to sound like an impression. |
| Status as short numbers (S4–S6, S11) | Use numbers for facts: "Question 7 of 12", "40 minutes left". At most 3 items. | **Hub rule "confidence in words, no percentages"** (HUB_TRUST §1.4): numbers stay for facts, words for confidence. Never say something like "82% sure". |
| Warns once, then complies (S3, S4) | Flag a concern once, with one reason and one alternative, then do what he decided without repeating it. | Matches **flag once then defer**. Note that JARVIS himself breaks it in S8. Ours never repeats a concern within a session. |
| Anticipation (S1, S7) | Have it ready, but don't announce it: pre-load the next item and mention it only at a breakpoint. | Matches **speak at breakpoints**. JARVIS speaks mid-flight for safety. Ours interrupts mid-task only when time is critical (e.g., "leave now for the exam"). |
| Doesn't act unasked (S8 shows the failure) | Prepare silently, then offer: "Pull up 7?" | Matches **offer, don't order** and **every write waits for yes**. |
| Read-back before risky actions (S10) | Echo what will happen, then act on yes (already F13.5). | None. |
| Health as facts (S6, S8) | State facts when relevant ("You've been at it 3 hours"). Never name his feelings. | **No emotional probing:** JARVIS's anxiety diagnosis in S8 crosses that line. Ours does not. |
| Partner feel (S9) | Earn it through reliability, memory of his context and honesty about failure (S11). Don't manufacture it. | **No manipulative engagement:** no guilt, no "I missed you", no streaks. JARVIS never asks for attention, and that is part of why he's liked. |

---

## Part 2: "Use context to act intuitively" for study materials

### 2.1 The science

- **Memory for goals (Altmann & Trafton).** A suspended goal's activation decays with time and is overwritten by newer goals. Resuming depends on cues that were linked to the goal *before* the break and are visible again *when he returns*. The seconds before an interruption are a window to make that link. https://www.interruptions.net/literature/Altmann-CogSci02.pdf
- **Warnings help.** With an 8-second warning, people prepared before switching far more often (13.5 vs 3.1 of 30 times) and saved about 4 s at resumption in the first session. The authors suggest 1–2 s may be enough and recommend salient cues tied to the main task. https://interruptions.net/literature/Trafton-IJHCS03.pdf
- **Zeigarnik and Ovsiankina.** A 2025 meta-analysis found **no** memory advantage for unfinished tasks, so he won't reliably remember where he stopped. It **did** find a general tendency to want to resume them, so an offer to pick up where he left off goes with his own urge. https://ideas.repec.org/a/pal/palcom/v12y2025i1d10.1057_s41599-025-05000-w.html
- **Resuming reading.** After an interruption, 75.7% of participants preferred a short review of what they'd already read. A preview of what comes next helped comprehension most consistently. https://ar5iv.labs.arxiv.org/html/2104.06603 . Highlighting the last-read position and keeping the layout continuous cut reading-resume time. https://aqdus01.github.io/publication/2025-05-CtxRead
- **Timing.** Interruption costs drop at task breakpoints, and drop further at coarse ones. Deferring to a coarse breakpoint means waiting about 4–5 minutes on average. https://www.interruptions.net/literature/Iqbal_Bailey-CHI07.pdf . In a 2026 field study, proactive suggestions made at workflow boundaries got 52% engagement, while 62% of those made mid-task were dismissed. https://arxiv.org/abs/2601.10253v1
- **Mixed initiative (Horvitz 1999).** Choose between doing nothing, asking and acting by comparing the probability that he wants the action against two thresholds. Use a short dialog only when uncertainty is in the middle band. Make wrong guesses cheap. When unsure, give a less precise service instead of a wrong precise one (LookOut showed a whole day when it couldn't pin down the time). https://www.erichorvitz.com/chi99horvitz.pdf
- **Confirmations.** Use implicit confirmation (state what you did) for small, easily undone actions. Use explicit confirmation (ask) only when an action is costly to redo. https://mycroft-ai.gitbook.io/docs/skill-development/voice-user-interface-design-guidelines/interactions-and-guidelines/confirmations

### 2.2 Windows tech: opening a PDF at a question

| Option | How | Can Jarvis read the page he's on? | Latency |
|---|---|---|---|
| **PDF.js inside the hub (pywebview/WebView2)** | Viewer hash `#page=N&zoom=page-width,0,Y`. https://www.github.com/mozilla/pdf.js/wiki/Viewer-options . In code: `pdfViewer.currentPageNumber`, `linkService.goToDestination([pageIdx,{name:"XYZ"},null,y,null])`, and the `pagechanging` event. https://www.nutrient.io/blog/pdfjs-navigation-zoom-rotation/ . Serve the viewer through `SetVirtualHostNameToFolderMapping` as PDFjs.WinUI does. https://github.com/WelterDevelopment/PDFjs.WinUI | **Yes**: page, scroll y and dwell, all live. | WebView2 is slow to cold-start, so reuse one instance and one environment. https://learn.microsoft.com/microsoft-edge/webview2/concepts/performance . In the already-running hub: open ≈ 150–400 ms, page jump < 50 ms (*est.*). |
| **SumatraPDF** | `SumatraPDF.exe -page N -scroll x,y file.pdf` (also `-named-dest`, `-search`). It reuses the open instance by default. https://www.sumatrapdfreader.org/docs/Command-line-arguments | **Yes**, through the DDE request `[GetFileState()]`, which returns `page:` and `pageCount:`. `[GotoPage("file",N)]` jumps within an open file. https://www.sumatrapdfreader.org/docs/DDE-Commands.md | Cold start ≈ 200–500 ms; jump in the running instance < 100 ms (*est.*). |
| **Acrobat Reader** | `Acrobat.exe /A "page=N=OpenActions" file.pdf`; `zoom=scale,left,top` also works. https://www.mobilefish.com/download/pdf/PDFOpenParameters.pdf | No simple way. | Cold start 1–3 s (*est.*). |
| **Edge** | `#page=N` on a file URL. If "Open PDFs to last viewed location" is on, Edge can ignore it (page 1 is a known bug). https://learn.microsoft.com/en-us/answers/questions/1825358/why-wont-edge-open-a-pdf-on-the-first-page-when-sp | No. | Cold start ≈ 1–2 s (*est.*). |

**Building the question index.** PyMuPDF extracts text at about 1.1 ms per page (8 s for 7,031 pages), about 12× faster than PyPDF2. https://pymupdf.readthedocs.io/en/latest/app4.html . `page.get_text("words"/"blocks", sort=True)` returns text with bounding boxes, and `page.search_for()` returns the rectangles of matches. https://pymupdf.readthedocs.io/en/latest/recipes-text.html . Match line starts with regexes such as `^(?:Question|Problem|Q)\s*(\d+)([a-z])?\b`, `^(\d{1,2})\s*[.)]\s` and `^\(?([a-z])\)\s` (sub-parts). Keep only matches in the left margin with a sensible font size, and check that the numbers ascend. Build the index when class-sync files the PDF, so the open path does no work. A 20-page set takes about 20–50 ms (*est.*).

### 2.3 Other context-driven behaviours using the same pattern

| Behaviour | Minimal data | How |
|---|---|---|
| Resume a lecture video | video id, seconds, date | USask's Panopto is integrated with Canvas (https://teaching.usask.ca/learning-technology/tools/panopto.php). Reopen with `&start=<seconds>` (https://community.panopto.com/discussion/comment/2061). YouTube uses `start=` in seconds and can land up to about 2 s early because it seeks to a keyframe (https://developers.google.com/youtube/player_parameters). |
| Reopen the same window layout | per study session: app/file and `WINDOWPLACEMENT` (show state, normal rect) | Save with `GetWindowPlacement` and restore with `SetWindowPlacement`, which keeps windows on-screen if the monitors change. https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowplacement |
| Remember which solutions he checked | doc id, question label, time opened | Log it when the solutions PDF lands on that question's page. Then offer the solutions only *after* he's tried (desirable difficulty, PSYCHOLOGY J1), and at review time say "5b: you looked at the solution". |
| Pick up a lab report draft | file path, last edited heading | Open at that heading (Word bookmark or search). |
| Flashcards and practice tests | deck id, last card index | Resume at the card, not the start. |

---

## Recommendations for Jarvis

### (a) Character spec

**Core:** calm and competent, dry in a few words. A partner who narrates state, offers, and then gets out of the way. The personality lives in word choice and in what he leaves unsaid. It is never a performance.

**Traits:** brief (≤ 3 items) · factual numbers, confidence in words · warns once with one reason and one alternative, then helps with whatever he chose · no "I told you so" · honest about mistakes and unknowns · one dry aside at most, aimed at situations · anticipates silently and offers at breakpoints · reads back before big or irreversible actions.

**Do**
- Have the next thing ready before he asks, and mention it only at a breakpoint.
- Turn a mistake straight into the fix ("Icing's the culprit; here's the fix"), never into blame.
- Use his name or no address term by default; "sir" only if he turns it on.

**Don't**
- Repeat a concern within a session, name his emotions, or tease him in front of others.
- Act before being asked (the Tennessee flight-plan failure).
- Imitate Bettany's timbre or accent, or quote the films.
- Fish for attention or affection.

**Sample lines (original):**
- On a good default: "Seven's next. Bring it up?"
- On warning once: "That's three hours straight. Your call. A ten-minute break is on offer."
- On his override: "Understood. Carrying on."
- On a dry aside: "Bold choice, studying thermo at midnight. Opening it now."
- On failure: "I filed that under the wrong course. Fixed, and here's the undo."
- On a risky action: "That clears all four study blocks on Friday. Go ahead?"
- On status: "Two things before class: lab prep, 20 minutes. Room's changed to Thorv 271."

### (b) "Resume points" feature

**Viewer:** PDF.js inside the hub's existing pywebview/WebView2 window. This reuses the architecture we already have and gives live page, y-offset and dwell data. Keep SumatraPDF as a fallback (its DDE `GetFileState` still gives Jarvis the page). Avoid Edge, because it can't report the page and may override `#page`.

**Data stored per document** (via `contracts/`, local memory DB, never in git):
`doc_id` (content hash + path) · `course` · `set_name` · `questions[] {label, page, y}` (built at file-arrival time) · `last_page`, `last_y`, `closed_at` · `dwell_by_question {label: seconds}` · `resume_at {label, source: inferred|confirmed, at}` · `done[]` · `solutions_viewed[] {label, at}`.

**When to infer silently and when to ask** (Horvitz thresholds):
- **Store silently** (marked *inferred*) when the session lasted under 3 min, or when the last viewport holds exactly one question with ≥ 60 s of dwell and he scrolled forward through the earlier ones.
- **Ask** when the session lasted ≥ 5 min and the inference is ambiguous: two or more questions in view, or he jumped back and forth.
- **Don't ask now** when closing isn't a breakpoint (he's leaving for class or a reminder fired). Keep the inferred value and confirm it on the next open instead.
- **Never ask twice.** Silence means the inferred value stands, and nothing else is said.

**The exact closing question** (closed, with the likely answer built in, asked once, right after the PDF closes):
> "Leaving off at question 7?"

He can answer "yes", "no, 8", "8b", or "done". Saving a bookmark is a local, undoable *observation*, not an outward write, so his answer counts as the yes. ⚠ **Rule conflict to settle with De Wet:** if he wants even inferred bookmarks to wait for a spoken yes, drop silent inference and always use the confirm-on-reopen path.

**Reopening:**
- "Open PPS 7" (or a tap on the now card) opens the PDF at `resume_at`: page N, scrolled to the question's y. Jarvis says nothing more than "Question 7." The hub shows a one-line review card ("1–6 done · looked at 5b's solution"), not spoken, following the review/preview findings. The question's heading gets a 1 s highlight so his eye lands on it (CtxRead).
- If the bookmark is only *inferred*, the question goes on the reopen instead: "Pick up at 7?" Then it opens there.
- If confidence is low, open at the page rather than the exact question, and degrade gracefully instead of guessing wrong (Horvitz/LookOut).

**Latency effect:**
- The index is pre-built and the bookmark is a single key-value read (< 5 ms *est.*), so the open path costs about the same as opening the PDF at all: roughly 150–400 ms in the warm hub, < 50 ms if the file is already open (*est.*).
- The closing question runs after the close, off the critical path, and saving is async.
- Compared with today's links (browser cold start ≈ 1–2 s *est.*, then manual scrolling to find the question), this should *cut* time to the first useful action. Measure it on Laptop A/B before quoting numbers to him.
