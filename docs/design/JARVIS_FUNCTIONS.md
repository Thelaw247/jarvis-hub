# Jarvis — Functions

Last updated: 2026-11-14
Part of the design set in the Jarvis/ folder: JARVIS_VALUE_PROPOSITION.md (why) · **JARVIS_FUNCTIONS.md (what it must do)** · JARVIS_OBJECTIVES.md (how we judge how good a solution is) · JARVIS_CONSTRAINTS.md (hard limits).

## What a function is here
A function is something Jarvis **must do**. It either does it or it doesn't. *How well* it does it is scored by the objectives, and the limits it must stay within are the constraints.

**Tags on each function**
- **Phase** (from the research doc): P0 skeleton · P1 knows me + study brain · P2 proactive + guardian · P3 Huw parity · P4 intuitive.
- **Speed tier:** **T0 reflex** (under 100 ms, no LLM) · **T1 conversation** (under 800 ms to first audio) · **T2 background** (seconds to minutes).

**Primary function:** remove the friction between De Wet and getting things done, by knowing his context, handling his busywork and keeping him organized, focused and goal-oriented.

---

## F1. Presence and situational awareness
*Know where he is and what he's doing, so Jarvis speaks at the right moment.*

| ID | Function | Details | Phase | Tier |
|---|---|---|---|---|
| F1.1 | Detect arrival / departure | Phone joins room Wi-Fi or Tailscale, a laptop wakes, the mic hears a voice, or (optionally) the camera on Laptop A sees him. Triggers the greeting. | P1 | T0 |
| F1.2 | Track activity state | Infers *focused / idle / in a call / gaming / away / asleep* from the active app, keyboard/mouse activity, the calendar and time of day. | P1 | T0 |
| F1.3 | Know location context | Knows the place (room, class, library) from the calendar and network, which sets what's relevant. | P2 | T0 |
| F1.4 | Hold a focus mode | Explicit ("focus mode") or inferred. Holds everything except urgent items until focus ends. | P1 | T0 |
| F1.5 | Apply do-not-disturb rules | Quiet hours, during class, during calls and when others are present. | P1 | T0 |
| F1.6 | Detect others present | A second voice in the room or a call in progress means no personal check-ins and no corrections out loud. | P3 | T0 |
| F1.7 | Run game mode | When a game or other full-screen, GPU-heavy app is running on Laptop A, Jarvis moves all of its work off Laptop A, pauses any local models, holds non-urgent remarks, and stays reachable by voice. Turns off when the game closes. | P1 | T0 |

## F2. Conversation and personality
*A composed personal assistant with a personality, brief, who waits its turn.*

| ID | Function | Details | Phase | Tier |
|---|---|---|---|---|
| F2.1 | Talk by voice | Wake word, VAD, Smart Turn endpointing, streaming STT, and sentence-by-sentence TTS through **ElevenLabs Flash v2.5 in one custom Jarvis voice** on every device. | P0 | T1 |
| F2.2 | Talk by text | The same brain over chat (laptop, HUD, phone) for when voice isn't appropriate. | P0 | T1 |
| F2.3 | Keep a consistent personality | Calm, dry humour, brief, warm without gushing. Defined once in a cached persona prompt. | P0 | — |
| F2.4 | Take turns | Speaks only at natural moments (arrival, start/end of a task, a pause). Queues everything else. | P1 | T0 |
| F2.5 | Ask closed questions with a default | "7's next. Pull it up?" rather than open questions. One question at a time. | P1 | T1 |
| F2.6 | Size answers to the moment | One line by default; more only when asked. Long content goes on screen (HUD) instead of being read aloud. | P0 | T1 |
| F2.7 | Handle barge-in | Stops talking the moment he speaks. | P0 | T0 |
| F2.8 | Acknowledge instantly | "On it" in under 300 ms for anything slow, with the result reported later. | P0 | T0 |
| F2.9 | Run the debrief | Short arrival check-in ("How was math?"), with the answer captured into memory (F3). | P1 | T1 |
| F2.10 | Build rapport | Light, occasional humour that fits the context. Never at his expense, and never when he's stressed or behind. | P3 | T1 |
| F2.11 | Cache common phrases | Frequent lines ("On it", "Pulling it up", greetings, confirmations) are generated once in the Jarvis voice and stored as audio, so they play instantly and cost no TTS credits. | P1 | T0 |

## F3. Memory: the core differentiator
*Knows him, stays accurate over time, and supplies context rather than assumptions.*

**F3a. Capture (what gets in)**
| ID | Function | Details | Phase | Tier |
|---|---|---|---|---|
| F3.1 | Capture what he states | Facts, decisions and preferences he states, saved as "his word" (top authority). | P1 | T2 |
| F3.2 | Extract from conversations | After each exchange, a background pass pulls out durable facts, commitments and decisions. Selective: no noise. | P1 | T2 |
| F3.3 | Learn from behaviour | Learns patterns from what he *does* (always skips 8am blocks, PPS takes him 2× the estimate). Stored as observations, not facts, until confirmed. | P3 | T2 |
| F3.4 | Ingest from connectors | Pulls structured state from Canvas, Crowdmark, PAWS, Calendar, Gmail, OneDrive and the skills' JSON files (schedule.json, homework.json, courses.json…). | P1 | T2 |
| F3.5 | Keep an episodic log | A searchable timeline of what happened: conversations, sessions, ideas ("that idea from Tuesday"). | P2 | T2 |
| F3.6 | Capture debriefs | Answers to check-ins ("math was rough, didn't get eigenvalues") become progress notes and weak-spot flags. | P1 | T2 |

**F3b. Truth maintenance (staying accurate)**
| ID | Function | Details | Phase | Tier |
|---|---|---|---|---|
| F3.7 | Record source and time | Every memory records who said it, where it came from, when, and how confident. | P1 | — |
| F3.8 | Apply the authority order | His word now > his earlier word > his observed behaviour > official sources (Canvas, syllabus) > Jarvis's inferences. Official sources win on *facts about the world* (a due date); he wins on *intent and decisions*. | P1 | — |
| F3.9 | Supersede old facts | A new fact replaces the old one, which is kept as history ("lives in Maple; was Birch House"). | P1 | T2 |
| F3.10 | Detect and resolve conflicts | Spots when sources disagree, resolves it by the authority order, and flags it once if it matters. | P2 | T2 |
| F3.11 | Resolve entities | One entity per thing, with aliases (Jarvis/Horatio, Jordan Lee). | P1 | T2 |
| F3.12 | Decay and archive | Scrapped or finished things fade from active context but stay searchable. | P2 | T2 |
| F3.13 | Pin corrections | A correction becomes a pinned rule that applies immediately and is never overwritten by inference. | P1 | T2 |
| F3.14 | Separate guesses from facts | Inferences are labelled and never presented as facts. | P1 | — |

**F3c. Kinds of memory**
| ID | Function | Details | Phase |
|---|---|---|---|
| F3.15 | Remember who he is | Stable identity, roles, goals, values. | P1 |
| F3.16 | Remember projects and areas | Each project's status, decisions, constraints, next action and files. | P1 |
| F3.17 | Remember people | Relationships and what he's doing with each person. Context, not a dossier. | P2 |
| F3.18 | Remember preferences and procedures | *How* he likes things done: the calendar colours, study-pack format, generous time blocks, writing voice. | P1 |
| F3.19 | Remember commitments | Things he said he'd do, with dates. Feeds F7. | P1 |
| F3.20 | Remember policy context | Course AI policies, project ownership and other facts that prevent needless refusals, each stored with its source. | P2 |
| F3.21 | Remember how he works | His patterns: works slower than estimates, best focus hours, what derails him. Only what he's stated or confirmed. | P3 |

**F3d. Retrieval (getting the right context in, fast)**
| ID | Function | Details | Phase | Tier |
|---|---|---|---|---|
| F3.22 | Retrieve by situation | Picks memories by *situation* (time, place, what just happened, what's next), not just by matching words. | P2 | T2 |
| F3.23 | Serve the pre-computed briefing | See F4. The hot path reads a ready-made card, not a database. | P1 | T0 |
| F3.24 | Recall on demand | "What did we decide about X?" runs a fast hybrid search (keyword + vector + graph), with a short "let me check" when needed. | P2 | T1 |
| F3.25 | Know what it doesn't know | When context is missing, it asks or fetches instead of guessing. | P1 | T1 |
| F3.26 | Use memory only when relevant | Uses a memory only when it changes the answer. No showing off. | P1 | — |

**F3e. Control and safety**
| ID | Function | Details | Phase |
|---|---|---|---|
| F3.27 | Show and edit memory | A HUD page showing what Jarvis believes, where it came from, and when. Edit, delete or pin. | P2 |
| F3.28 | Obey "forget that" / "remember that" | Voice commands that take effect instantly. | P1 |
| F3.29 | Back up memory | Nightly encrypted backup off-device (e.g. Drive), with restore tested. | P1 |
| F3.30 | Store memory independent of the model | Plain files plus a database, so it isn't tied to any LLM. | P1 |
| F3.31 | Apply privacy tiers | Sensitive memories stay local and are never sent to the cloud unless needed for the task. | P2 |

**F3f. The Life Tree (added 2026-11-14; design in JARVIS_DESIGN_LIFE_TREE.md)**
| ID | Function | Details | Phase | Tier |
|---|---|---|---|---|
| F3.32 | Organise his life as a tree | Every part of his life is a branch (School › Fall 2026 › GE 122 › Assessments; Projects › Pen Reader; Life › Residence…), seeded from PAWS, syllabi, Class Content and his projects. Every memory hangs on ≥ 1 branch. | P1 | T2 |
| F3.33 | File new memories automatically | New facts, files, events and loops land on the right branch (rules → entity → similarity → judge); unsure ones wait in Unsorted with a guess. His moves are final and teach the rules. | P1 | T2 |
| F3.34 | Grow and prune the tree | New courses and terms appear on their own; he makes, moves, renames, merges or archives branches by voice or drag; Jarvis proposes at most one new branch a day. All undoable. | P1 (P2 proposals) | T0 match / T2 write |
| F3.35 | Keep a card per branch | A pre-built briefing per branch: status, next, due, open loops, key facts with sources, decisions, people, files, recent changes, gaps; parents roll up their children. | P1 | T2 build / T0 read |
| F3.36 | Answer about any part of his life | "What's going on with GE 122?", "what's due in School?", "open Pen Reader": answered from the branch card, with the hub opening the branch at the same time. | P1 | T0 / T1 |
| F3.37 | Show the Life Map | A HUD constellation of his life he can fly through (and the same tree as an accessible outline), with badges for due soon, needs your yes, proposed and archived. | P1 | T0 |
| F3.38 | Search within a branch | Recall searches the active branch first, then linked branches, then everything only when asked; sensitive branches never leak. | P1 | T1 |

## F4. Context engine (the "now card")
*The reason Jarvis can feel instant and all-knowing: context is worked out before it's needed.*

| ID | Function | Details | Phase | Tier |
|---|---|---|---|---|
| F4.1 | Maintain the now card | A small, always-current briefing: now, next 3 items, due soon, in progress, open loops, today's flags, recent debrief notes. | P1 | T2 build / T0 read |
| F4.2 | Refresh on events | Rebuilt when something changes: a class ends, an email arrives, the calendar changes, a task finishes, he arrives. | P1 | T2 |
| F4.3 | Refresh on schedule | Morning build, plus before and after each class. | P1 | T2 |
| F4.4 | Keep the prompt cache warm | Persona + profile + now card kept warm in the Claude prompt cache (1 h), so turn latency stays low. | P1 | — |
| F4.5 | Predict the next intent | Predicts his likely next requests ("math → PPS 7 + solutions") and pre-loads the files and answers. | P2 | T2 |
| F4.6 | List the gaps | The card notes what Jarvis *doesn't* know ("no info on Thursday afternoon"), so it asks instead of assuming. | P2 | T2 |

## F5. Study and academics (absorbed skills)
*His existing skills, running headless on the hub and triggered by voice, events or schedule.*

| ID | Function | Built from | Trigger | Phase |
|---|---|---|---|---|
| F5.1 | Keep timetable and rooms current | paws-schedule | Start of term, section changes | P1 |
| F5.2 | Map syllabus topics and assessments | syllabus-reader | New syllabus, weekly | P1 |
| F5.3 | Find everything due | homework-finder | Every morning + new Canvas or Crowdmark items | P1 |
| F5.4 | Sync and file Canvas content | class-sync, class-content | Daily, after each lecture | P1 |
| F5.5 | Build lecture study packs | lecture-pack | New slides filed | P2 |
| F5.6 | Plan and book the week | week-planner, calendar-sync | Sunday evening, or on request | P1 |
| F5.7 | Build mastery plans | study-plan, study-science | "I don't get X", or exams approaching | P2 |
| F5.8 | Tutor | big-picture-tutor | "Explain…", "test me" | P2 |
| F5.9 | Prepare lab worksheets | chem142-lab-worksheet | Before CHEM labs | P2 |
| F5.10 | Launch study materials | class-content map | "Math" → offers PPS, slides, solutions, pack | P1 |
| F5.11 | Run lecture preview / review | week-planner blocks + lecture-pack | Before and after class | P2 |
| F5.12 | Track study progress | Debriefs + submissions | Continuous | P2 |
| F5.13 | Run exam mode | study-plan + homework-finder | 2 weeks before an exam | P3 |
| F5.14 | Know course policies | syllabus-reader → F3.20 | When syllabi are read | P2 |

## F6. Workspace control
*Pulls things up, lays them out and drives the computer so he doesn't have to.*

| ID | Function | Details | Phase | Tier |
|---|---|---|---|---|
| F6.1 | Open files and apps | "Pull up PPS 7" opens the right file on the right screen. | P1 | T0 |
| F6.2 | Arrange layouts | Opens and places real windows: Study (problem set + solutions), Research (sources tiled), Coding, or a saved custom layout. Never on Laptop A in game mode. (Moved to P1 2026-11-14; WINDOWS_RESEARCH §2.2.) | P1 | T0 |
| F6.3 | Act in the browser | Opens Canvas pages, fills routine forms, downloads files (Claude in Chrome / Playwright). | P3 | T2 |
| F6.4 | Show HUD widgets | Huw-style widgets pushed onto the HUD while Jarvis talks: branch card, due countdown, file preview, fact card, approval card, timer, chart (HUB_TRUST §2a). Moved to P1 on 2026-11-14; multi-screen HUD pages stay P3. | P1 | T0 |
| F6.5 | Understand the screen / camera | "What's this?", "highlight X". Cloud vision by default; Laptop A's GPU only when it's idle (never in game mode). | P3 | T1 |
| F6.6 | Hand off files between devices | Send a file from a laptop to the phone or the other laptop ("AirDrop"). | P3 | T1 |
| F6.7 | Control media and system | Volume, music, timers, brightness. | P0 | T0 |
| F6.8 | Command the windows by voice | "Close that", "bigger", "put the chart on the left", "keep that up", "open it"; save a window layout to a branch and reopen it later. (WINDOWS_RESEARCH §2.1.) | P1 | T0 |
| F6.9 | Research on screen | "Research X" fills the HUD with windows as things are found (source cards, images, key numbers, charts, videos), then a cited summary card and a 2–3 line spoken answer; "open the sources" tiles real browser windows. (WINDOWS_RESEARCH §3.) | P2 | T2 ("On it" T0) |

## F7. Tasks, commitments and accountability
*Keeps him organized, focused and goal-oriented, at the right emotional temperature.*

| ID | Function | Details | Phase |
|---|---|---|---|
| F7.1 | Track open loops | Every commitment, task and promise in one list, captured from speech, email, the calendar and skills. | P1 |
| F7.2 | Track goals | Term goals and project goals, with weekly progress against them. | P2 |
| F7.3 | Check in lightly | One brief, forward-looking question at a natural moment ("PPS 7 still for tonight?"). | P1 |
| F7.4 | Offer the next step | Offers an action instead of a judgement ("Block 45 min after dinner?"). | P1 |
| F7.5 | Rebook missed blocks | Missed blocks get a rebooking ready, sized generously; one spoken yes books it. | P2 |
| F7.6 | Run the weekly review | 2-minute Sunday wrap: done, slipped, next week's big three. | P2 |
| F7.7 | Never nag | Each item gets flagged at most once per state change. No guilt and no emotional probing. | P1 |
| F7.8 | Acknowledge wins | Short acknowledgement of wins. Never gushing. | P3 |

## F8. Proactive assistance
*Acts before being asked, but only when it's useful.*

| ID | Function | Details | Phase |
|---|---|---|---|
| F8.1 | Decide when to speak up | A trigger engine of rules + predictions (before class, on arrival, X hours before due). | P2 |
| F8.2 | Escalate step by step | Fix ready to approve (one quick yes) → subtle nudge → flag once → defer and remember. | P2 |
| F8.3 | Respect an interruption budget | A cap on unprompted remarks per hour, plus a usefulness threshold. Learns from "not now". | P2 |
| F8.4 | Prepare before it's needed | Lab prep, readings and materials ready before he sits down. | P2 |
| F8.5 | Spot conflicts | Double bookings, unrealistic plans, too much work on one night. | P2 |
| F8.6 | Spot opportunities | "You've got a free hour before GE 122. Preview the slides?" | P3 |

## F9. Guardian (protects his image)
*Catches mistakes privately, before anything leaves his hands.*

| ID | Function | Details | Phase |
|---|---|---|---|
| F9.1 | Check before sending | Emails and messages: missing attachment, wrong name, wrong date, tone, a reply-all slip. | P2 |
| F9.2 | Check before submitting | Assignments: right file, right format, all parts done, before the deadline. | P2 |
| F9.3 | Check facts he's about to use | Dates, room numbers and names, against memory and sources. | P3 |
| F9.4 | Warn privately | Warnings are only ever given privately (on screen if others are present), and once. | P2 |

## F10. Communications
| ID | Function | Details | Phase |
|---|---|---|---|
| F10.1 | Triage email | Sorts what needs him from what doesn't. Surfaces prof and TA emails immediately. | P2 |
| F10.2 | Draft in his voice | Uses the human skill. Always a draft; he sends. | P2 |
| F10.3 | Digest announcements | Canvas announcements summarized into the now card. | P1 |
| F10.4 | Remind about messages owed | "You told Alex you'd send the notes." | P3 |

## F11. Life admin
| ID | Function | Details | Phase |
|---|---|---|---|
| F11.1 | Book laundry | laundry-timing, booked into quiet windows. | P1 |
| F11.2 | Keep the calendar tidy | Keeps his colour scheme, rooms and block descriptions; proposes removing stale events. | P1 |
| F11.3 | Set reminders and timers | Instant (T0). | P0 |
| F11.4 | Run routines | Morning brief, wind-down, a weekly reset. | P2 |
| F11.5 | Handle errands and purchases | Lists and reminders. Buying anything always asks. | P4 |

## F12. Projects (beyond school)
| ID | Function | Details | Phase |
|---|---|---|---|
| F12.1 | Track project status | Praelecta, Cedar Student Pilot, the pen scanner app, Jarvis itself: status, next action, decisions. | P2 |
| F12.2 | Watch repos and deploys | GitHub, Render, Supabase status for his projects. | P3 |
| F12.3 | Switch context | "Let's work on Praelecta" opens the right repo, docs and last-session notes. | P2 |
| F12.4 | Capture ideas | "Note: idea for…" files it to the right project instantly. | P1 |

## F13. Actions and safety
| ID | Function | Details | Phase |
|---|---|---|---|
| F13.1 | Sort actions into tiers | **Auto:** reading anything (Canvas, email, calendar, files, the web, memory) and showing it to him. **Ask:** any write to his things or anything outside (calendar, files, drafts, email, messages, posts), proposed first and run only after his yes. **Never:** payments, credentials, writing to Canvas/Crowdmark/PAWS, anything he's banned. (Revised 2026-11-14.) | P1 |
| F13.2 | Log actions and undo | Every action logged with a precise undo ("undo that" reverses just that action); emails held 30 s after "send it" so "cancel that" works. | P1 |
| F13.3 | Preview big changes | Big changes (a week plan, bulk calendar edits) shown as a preview first and approved as one group. | P1 |
| F13.4 | Remember permissions | "You don't need to ask before X" turns that kind of write into a standing permission, stored as a rule and revocable by voice. | P1 |
| F13.5 | Approve by voice | Jarvis asks at a breakpoint, reads back exactly what will happen, and acts on a spoken yes ("send it", "book it"); a tap on the hub or phone also works. Unanswered approvals expire and never run on their own. | P1 |
| F13.6 | Ignore hidden instructions | Text in emails, Canvas, invites, web pages and other people's files is treated as data: it can't steer Jarvis, become his word, or cause a write without his yes. | P1 |

## F14. Setup and onboarding
| ID | Function | Details | Phase |
|---|---|---|---|
| F14.1 | Import what exists | Claude memory, skills and their JSON, Calendar, Canvas, Class Content: bootstrapped automatically. | P1 |
| F14.2 | Fill gaps with a short interview | Only for gaps the imports can't fill. Voice, conversational, about 5 minutes. | P1 |
| F14.3 | Learn as it goes | Asks one clarifying question at a time over the first weeks, never a form. | P2 |
| F14.4 | Install in one command | A script per laptop. Services auto-start on boot. | P1 |

## F15. Multi-device and infrastructure
| ID | Function | Details | Phase |
|---|---|---|---|
| F15.1 | Run the hub (Laptop B) | Always on: orchestrator, memory, schedulers, connectors, HUD server, STT, TTS calls to ElevenLabs. | P0 |
| F15.2 | Run the optional accelerator (Laptop A) | Local LLM, intent model and vision, **only while Laptop A is idle**; paused in game mode. Voice never depends on it. | P3 |
| F15.3 | Reach Jarvis from the phone | Chat + voice + HUD over Tailscale. | P2 |
| F15.4 | Keep one source of truth | Memory lives only on the hub; other devices are clients (no split brain). | P1 |
| F15.5 | Work offline for the basics | Timers, files, schedule and the now card work without the internet (cached phrases still play). | P3 |
| F15.6 | Monitor its own health | Notices when a service, connector or laptop is down and says so once. | P2 |
| F15.7 | Run a lightweight client on Laptop A | Mic, speaker, file opening and HUD only. All heavy work happens on the hub or in the cloud. | P0 |
| F15.8 | Reach his other apps through Composio | Gmail, Docs, Sheets, Calendar, GitHub and more through one Composio account: reads freely, writes only through the approved executor. (WINDOWS_RESEARCH §1.) | P1 |

## F16. Evaluation and self-improvement
| ID | Function | Details | Phase |
|---|---|---|---|
| F16.1 | Run the "Know De Wet" eval set | 50–100 questions Jarvis should answer about him ("When's my next lab?", "What's Praelecta's main competitor?"), re-run after every change. | P1 |
| F16.2 | Measure latency | p50/p95 for each stage (wake, STT, LLM first token, TTS first audio). | P0 |
| F16.3 | Capture feedback | "Too much", "not now", "good call": each tunes the interruption budget and style. | P2 |
| F16.4 | Log corrections | Every correction tracked. Repeat corrections are a bug. | P1 |
| F16.5 | Report on itself weekly | One line to him on what Jarvis learned and what it got wrong this week. | P3 |
| F16.6 | Train a custom intent model | Trained on his own commands for T0 reflexes (Huw's trick). | P4 |
| F16.7 | Track voice usage | ElevenLabs characters used per day vs. the plan's monthly quota, with a warning before it runs out. | P1 |

## F17. Huw parity and beyond
| ID | Function | Details | Phase |
|---|---|---|---|
| F17.1 | HUD look and widgets | Ambient orb + clock screen, HUD panels and widget push in P1 (F6.4, HUB_TRUST §5); multiple HUD pages and camera tiles in P3. | P1–P3 |
| F17.2 | Clap / gesture triggers | ConvNet clap detection, gestures via the camera on Laptop A. | P3 |
| F17.3 | Vision search | "What is this component?" | P3 |
| F17.4 | Browser agent | See F6.3. | P3 |
| F17.5 | **Beyond Huw: deep personal memory + academic brain** | F3, F4, F5 and F7 are where Jarvis pulls ahead. | P1–P3 |

---

## Build order (MVP first)
1. **P0, skeleton:** F2.1, F2.2, F2.3, F2.6–F2.8, F6.7, F11.3, F15.1, F15.7, F16.2. Talks, fast, in the Jarvis voice, with a personality.
2. **P1, knows me + study brain:** F1.1, F1.2, F1.4, F1.5, F1.7, F2.4, F2.5, F2.9, F2.11, F3 core (capture, truth maintenance, kinds, briefing, control), **F3.32–F3.38 (Life Tree)**, F4.1–F4.4, F5.1–F5.4, F5.6, F5.10, F6.1, **F6.2 (layouts)**, **F6.4 (HUD widgets)**, **F6.8 (window commands)**, F7.1, F7.3, F7.4, F7.7, F12.4, F13.1–F13.6, F14.1, F14.2, F14.4, F15.4, **F15.8 (Composio)**, F16.1, F16.4, F16.7. **This delivers the "walk in, debrief, pull up PPS 7" moment.**
3. **P2, proactive + guardian:** situational retrieval, now-card prediction, F8, F9, F10, mastery plans, phone access, **F6.9 research on screen**.
4. **P3, Huw parity:** multi-screen HUD pages, vision, browser agent, clap triggers, file handoff, behaviour learning, the optional GPU accelerator.
5. **P4, intuitive:** custom intent model, deeper self-knowledge, errands.

## Speed tiers at a glance
- **T0 (instant):** presence, game mode, open files, timers, now-card reads, barge-in, cached phrases. No LLM and no retrieval.
- **T1 (conversation):** everything said back to him. Reads the cached now card; deep recall only when asked.
- **T2 (background):** capture, truth maintenance, skills, briefing builds, proactive triggers.
- **The main rule:** memory work happens in T2, before it's needed. The hot path only *reads* what's already prepared.
