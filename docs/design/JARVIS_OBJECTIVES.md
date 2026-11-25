# Jarvis — Objectives

Last updated: 2026-11-13
Part of the design set in the Jarvis/ folder: JARVIS_VALUE_PROPOSITION.md (why) · JARVIS_FUNCTIONS.md (what it must do) · **JARVIS_OBJECTIVES.md (how we judge how good a solution is)** · JARVIS_CONSTRAINTS.md (hard limits every solution must meet).

## What an objective is here
An objective is a quality where **more (or less) is better**. Objectives don't pass or fail a design; they **rank** the designs that already pass the constraints. We use them to compare options (memory frameworks, voice stacks, architectures) and to check whether a change made Jarvis better.

- **Functions** = what Jarvis must do. It either does them or it doesn't.
- **Constraints** = hard limits. Break one and the design is out.
- **Objectives** = how good a passing design is. They're scored, weighted, and used to pick the best option.

## The objectives

| # | Objective | Direction | Metric (units) | How it's measured | Weight |
|---|---|---|---|---|---|
| O1 | **Responsiveness** | Faster is better | p95 time to first audio for normal chat (ms); p95 for reflex actions like "pull up X" (ms) | Latency dashboard (F16.2); before building, from benchmarks | **14** |
| O2 | **Context accuracy ("knows me")** | Higher is better | % correct on the "Know De Wet" eval set, with confident wrong answers counted as −1 | Eval set re-run after every change (F16.1) | **14** |
| O3 | **Friction to start** | Lower is better | Seconds and exchanges from intent ("we need to do math") to the right material open | Timed on 10 standard scenarios | **10** |
| O4 | **Correction retention** | Lower is better | % of corrections that have to be given again | Correction log (F16.4) | **8** |
| O5 | **Follow-through** | Lower is better | Deadlines, preps or commitments missed per month that Jarvis knew about | Open-loops log vs. Canvas/Crowdmark | **8** |
| O6 | **Interruption quality** | Higher is better | % of unprompted remarks he rates useful; unwanted interruptions per day | "Good call" / "not now" feedback (F16.3) | **7** |
| O7 | **Simplicity and reuse** | Simpler is better | Share of his existing skills reused as-is (%); number of custom services to maintain; build hours | Architecture review | **6** |
| O8 | **Busywork offloaded** | More is better | Hours per week of planning, syncing, filing, booking and triage done by Jarvis | Action log × time estimates | **6** |
| O9 | **Transparency and control** | Higher is better | % of memories and actions he can view, edit and undo | Feature checklist | **5** |
| O10 | **Error catching** | Higher is better | % of outgoing errors (missing attachment, wrong date, name typo) caught before sending | Seeded test cases + real log | **4** |
| O11 | **No needless refusals** | Lower is better | "Can't help" or hedged answers per week on things it could do | Response log review | **4** |
| O12 | **Running cost** | Lower is better | Out-of-pocket $ per month beyond his $100 Claude API credit and his existing ElevenLabs plan (API overage, TTS top-ups, hosting) | Billing dashboards | **4** |
| O13 | **Personality and naturalness** | Higher is better | His weekly 1–5 rating ("feels like a person, not a chatbot") | Sunday review (F7.6) | **3** |
| O14 | **Robustness** | Higher is better | Uptime (%); time to recover after a crash or a dead laptop (min) | Health monitor (F15.6) | **3** |
| O15 | **Setup effort** | Lower is better | Minutes from install to first useful briefing; questions he has to answer | Fresh-install test | **2** |
| O16 | **Privacy** | Higher is better | % of sensitive data processed only on his own devices | Data-flow audit | **2** |
| | | | | **Total** | **100** |

**Why these weights:** speed and knowing him (O1, O2) *are* the product, so they carry the most. Friction, corrections and follow-through come next because they're what "personal assistant" means day to day. Things that are also protected by a hard constraint (privacy, cost ceiling, setup time) get lower weights here, since the constraint already rules out bad options. The weights are a starting proposal; adjust them if your priorities differ.

## Scoring scale (1–5)
Each option gets a 1–5 score per objective. Weighted score = Σ(weight × score) ÷ 5, giving a total out of 100.

| # | 1 (poor) | 3 (good) | 5 (excellent) |
|---|---|---|---|
| O1 | Chat > 1,500 ms | Chat 800–1,000 ms; reflex < 500 ms | Chat < 500 ms; reflex < 150 ms |
| O2 | < 60% | 80–89% | ≥ 95%, no confident wrong answers |
| O3 | > 60 s or 5+ exchanges | 10–20 s, 2–3 exchanges | < 5 s, 1 exchange |
| O4 | > 30% repeated | 5–10% | 0% |
| O5 | 3+ missed per month | 1 per month | 0 |
| O6 | < 40% useful | 60–79% useful | ≥ 90% useful, ~0 unwanted |
| O7 | < 30% skills reused, 6+ custom services | 60–80% reused, 3–4 services | ≥ 90% reused, ≤ 2 services |
| O8 | < 1 h/week | 3–5 h/week | 8+ h/week |
| O9 | Black box | Memory viewable, partly editable | Everything viewable, editable and undoable |
| O10 | < 30% | 60–79% | ≥ 95% |
| O11 | Weekly or more | Monthly | Never |
| O12 | > $60/month out of pocket | $20–35/month | < $10/month |
| O13 | 1–2 | 3 | 5 |
| O14 | < 90% uptime, hours to recover | 97–99%, < 30 min | > 99.5%, < 5 min |
| O15 | > 2 h, long form | 30–60 min | < 15 min, a few spoken questions |
| O16 | Mostly cloud | Sensitive data local, rest cloud | Everything possible local |

(Scores 2 and 4 fall between the neighbouring bands.)

## How we use this
1. **Comparing options** (e.g. memory frameworks): drop any option that breaks a constraint, then score the rest on the objectives that option affects, and pick the highest weighted total. Before anything is built, scores come from benchmarks, docs and small prototypes; mark them as estimates.
2. **Tracking Jarvis over time:** re-score monthly from real measurements to see whether changes are actually improving it.
3. **Breaking ties:** if two options are within ~5 points, choose the one with the better O1 (speed), then O7 (simplicity).

## Decision matrix template
| Objective (weight) | Option A | Option B | Option C |
|---|---|---|---|
| O1 Responsiveness (14) | | | |
| O2 Context accuracy (14) | | | |
| O3 Friction to start (10) | | | |
| … | | | |
| **Weighted total /100** | | | |
