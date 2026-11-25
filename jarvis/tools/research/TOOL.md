---
id: research
name: Research something properly
rung: 5
tier: read
speed: task
voice: deferred
task: false
where: Laptop B
reads: the web (search, pages, his signed-in sites when needed), with every source kept
writes: a cited summary card on screen and in memory (Jarvis's own note)
needs: [tasks]
input:
  type: object
  properties:
    question: {type: string, description: "The question, with what he wants out of it ('compare the three best student budgeting apps for Canada, cost and features')"}
    depth: {enum: [standard, deep], description: "standard (~2 min, default) or deep (several angles in parallel, ~10 min)"}
  required: [question]
---
Research a question on its own: search, read the best sources, compare, and come back with a short cited answer
(spoken in 2–3 lines) and a summary card on screen with every source.

When to use: "research…", "look into…", "find out everything about…", comparisons, decisions that need several
sources, anything one search won't settle.
When not to use: a quick fact (web_search answers in seconds); his own data (Canvas, memory, files).
Cost and speed: standard ~$0.30 and 1–2 min; deep ~$1.50 and up to 10 min. Say "On it" at once.
