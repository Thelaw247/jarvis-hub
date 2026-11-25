# Jarvis — Tools and skills: everything Claude can do, picked as intuitively as Claude picks

Last updated: 2026-11-17
Status: design + phase A build (v0.12.0). Extends JARVIS_DESIGN_RUNTIME.md (§4 skills, §5a Canvas, §9 approvals, §9a
hidden instructions), JARVIS_DESIGN_REACH.md (the reach ladder, local tools, agent sessions) and
JARVIS_DESIGN_ASK_OR_ACT.md. Where they disagree on tools, this file wins.

**What De Wet asked (2026-11-17):** "build the skills, make sure Jarvis can do everything that you can, and add this to
his memory through a tools folder or something. Plan out the architecture, take your time and research it thoroughly.
I want Jarvis to be able to browse the web, use my login credentials, pull tabs from the web, read PDFs and other
documents, browse through Canvas and look for specific things, conduct research on his own. Research what Jarvis is
capable of and make sure ours can do all those things as well." And: **"keep in mind I want Jarvis to be intuitive
like you on when to use all these tools."**

---

## 1. What the research found

### 1.1 Three things changed since the runtime design (Nov 14)

1. **Anthropic now ships the browser toolset Claude is trained on, for our own browser.** `browser_toolset_20260801`
   (GA 19 Aug 2026, Claude API, Haiku 5.5 / Sonnet 5.5 / Opus 5.5 supported) gives Claude 27 browser tools (navigate,
   read_page, find, get_page_text, clicks, typing, form_input, scrolling, tabs) plus four optional ones (file_upload,
   javascript_exec, read_console, read_network). **We run the browser; Anthropic only supplies the definitions.** The
   Python SDK (`anthropic` ≥ 2.8, checked in 2.10.0) includes an abstract async toolset class with a **URL policy hook**
   and a **confirm hook**, so our driver only implements the members on Playwright and our rules run before every call.
   This is the same vocabulary Claude uses in Chrome, which is what makes the browsing feel like Claude's.
2. **The Agent SDK turns skills on with one option.** `claude-agent-sdk` 0.2.183 (checked; Windows wheel bundles the
   Claude Code binary, 167 MB) has `skills=[...]` / `"all"` and the `can_use_tool` permission callback. That is
   exactly what RUNTIME §4 needed: his SKILL.md folders load unchanged, every permission question comes to Jarvis in
   code.
3. **Tool search.** With `defer_loading: true`, a tool's definition stays out of the prompt until Claude searches for
   it (`tool_search_tool_bm25_20251119`). Anthropic's numbers: ~85% fewer tool tokens, and tool-choice accuracy holds
   with hundreds of tools where it drops past ~30–50 loaded at once. So Jarvis can have every tool without slowing
   every turn.

### 1.2 What "everything Claude can do" means, and Jarvis's version

Claude's abilities are taken from this session's own tool list (what I actually used to build Jarvis). Huw's are from
his public reels and his Mk4 write-up; the film's from the HUD v2 research.

| Ability | Claude (me) | Huw's Jarvis | Film JARVIS | Our Jarvis: tool | Phase |
|---|---|---|---|---|---|
| Search the web, cite sources | web search + fetch | news, weather | yes | `web_search`, `web_fetch` (Anthropic server tools) | **A** |
| Browse sites, click, fill forms, tabs | Claude in Chrome | — | yes | `browse` (browser worker, browser toolset) | **A** read · **B** act |
| Use his logins (USask, Google, Canvas…) | his Chrome sign-ins | — | — | the Jarvis browser profile he signs into once (§6) | **A** |
| Pull up pages / tabs on screen | built-in browser pane | widgets on screen | holograms | `show_page` → web window on the Stage | **A** |
| Read what's in his open Chrome tabs | Chrome extension | — | — | client + Playwright MCP Bridge on Laptop A | C |
| Read PDFs, Word, Excel, PowerPoint, images | file reading + skills | "look up spec files" | yes | `read_document` (MarkItDown + PyMuPDF; Claude vision for scans) | **A** |
| Search Canvas for specific things | browser on Canvas | — | — | `canvas_find`, `canvas_read` (Canvas JSON through his session) | **A** |
| Research on its own, cited | deep research, subagents | vision search | yes | `research` task (Sonnet, search/fetch/browse, parallel subagents) | **A** |
| Multi-step jobs, his USask skills | skills + subagents | — | — | `start_task` → Agent SDK runner with his skills | **A** runner · B skills live |
| Write docs, sheets, slides, PDFs | docx/xlsx/pptx/pdf skills | — | — | Anthropic's document skills in tasks; files via `propose_*` | B |
| Email, calendar, Drive | connectors | email count, writing | calls, schedule | Composio (REACH §1, designed) | B |
| Files and apps on his laptops | device bridge | Blender, VR | workshop | local tools in the client (REACH §2) | B |
| Run code, analyse data | code execution | — | diagnostics | Bash/Python inside tasks (sandboxed folder) | B |
| Remember | memory | knowledge base | yes | memory (built, K3) + `remember`/`recall` | **A** |
| Schedule things for later | scheduled tasks | — | — | `schedule` (APScheduler, designed) | B |
| Ask him questions | ask the user | — | yes | `ask_dewet` / voice (RUNTIME §4) | **A** |
| See (screen, camera) | screenshots | camera vision search, desk camera | yes | `look` (screenshot via client; webcam later) | C |
| Maps, "plot a course" | — | maps | yes | map window (hub, designed) + directions via web | C |
| Use any desktop app | computer use | — | — | `computer_toolset_20260801` on Laptop A (REACH rung 6) | C |
| Drive his 3D printer | — | (others' helmets) | suit fabrication | pen plotter tool (designed) | C |

**Phase A** = this build. B and C follow, in that order, each needing one thing from him (Composio key; Laptop A
client; his OK for the screen and camera).

## 2. The architecture

```
                 ┌──────────────── jarvis/tools/<id>/  (the tools folder: one folder per tool) ──────────────┐
                 │  TOOL.md  (name, when to use, when not, tier, speed, where, rung)   handler.py (the code)   │
                 └───────────────┬──────────────────────────────┬──────────────────────────┬────────────────┘
                                 │ registry (loaded at start)    │                          │
    ┌────────────────────────────▼───────┐   ┌───────────────────▼────────────────┐   ┌─────▼──────────────────┐
    │ VOICE BRAIN (T1, Haiku 5.5)         │   │ TASK BRAIN (T2, Agent SDK, Sonnet)  │   │ MEMORY + HUB            │
    │ Messages API, streamed              │   │ one-shot sessions, max 2            │   │ "abilities" card on the │
    │ • ~8 instant tools always loaded    │   │ • every tool as in-process MCP      │   │ Life Tree (jarvis ›     │
    │ • the rest deferred → tool search   │   │ • his skills: skills=[…]            │   │ abilities), recalled    │
    │ • web_search / web_fetch (server)   │   │ • Claude Code built-ins: Read, Grep,│   │ like any branch         │
    │ • slow work → start_task, "On it"   │   │   Glob, WebSearch, WebFetch         │   │ • Controls › Reach list │
    └──────────────┬─────────────────────┘   │ • can_use_tool → approvals (§9)     │   │   (contracts/reach)     │
                   │                          └───────────────┬────────────────────┘   └────────────────────────┘
                   │          WORKERS (plain code + their own model loop)  │
                   └─────────► browser worker: Messages API + browser_toolset_20260801 → Playwright driver
                               (Edge, persistent "Jarvis browser" profile on Laptop B; URL policy + confirm hook)
                               canvas client: Canvas /api/v1 GETs with the profile's cookies
                               document reader: MarkItDown / PyMuPDF; pages as images for Claude when scanned
```

**Three kinds of thing, kept apart:**
- **Tools** are single abilities with a fixed contract: `read_document(path)`, `canvas_find(query)`. Code. Fast.
  Checked by tests. This is the "tools folder".
- **Skills** are recipes written in words (SKILL.md): his USask skills (week-planner, class-sync…) and Anthropic's
  document skills (docx, xlsx, pptx, pdf). They run in the task brain and call tools.
- **Workers** are the two places a model drives something step by step: the browser worker and the task runner.
  Each has its own budget and its own transcript in Activity.

**Why two brains:** a spoken reply has ~1.5 s; a tool round trip on Haiku costs ~0.4–0.8 s. So the voice brain keeps
only instant tools (memory, today, Canvas lookups from the cache, showing things) and hands anything with several
steps to the task brain with an immediate "On it". The task brain has no latency budget, only cost caps.

## 3. The tools folder

```
jarvis/tools/
  read_document/
    TOOL.md        ← what Jarvis reads to decide (and what the hub shows)
    handler.py     ← async def run(args, ctx) -> Result
  canvas_find/ …   browse/ …   research/ …
```

`TOOL.md` front matter (the body is the description Claude reads, written in the style of Anthropic's own tool docs):

```yaml
---
id: read_document
name: Read a document
rung: 1               # reach ladder: 1 own data · 2 app APIs · 3 local · 4 app automation · 5 agent · 6 computer
tier: read            # read (free) · ask (proposes; runs after his yes) · never
speed: fast           # instant < 100 ms · fast < 1 s · slow < 10 s · task (minutes, always via start_task)
where: Laptop B
voice: deferred       # loaded (always in the voice prompt) · deferred (found by tool search) · off
reads: PDFs, Word, Excel, PowerPoint, text and image files, by path or link
writes: nothing
input:                # JSON Schema of the arguments
  type: object
  properties: {path: {type: string}, pages: {type: string}, question: {type: string}}
  required: [path]
---
Read a document and return its text as Markdown (tables kept), with page numbers…
When to use: …   When not to use: …   Prefer: …   Cost and speed: …
```

**One registry** loads every folder at start and produces, from the same files:
1. the voice brain's tool list (loaded ones in full; deferred ones marked `defer_loading` for tool search);
2. the task brain's in-process MCP server (`mcp__jarvis__<id>`);
3. the `reach.tools` rows for Controls › Reach (status, on/off, last used);
4. the **abilities card** in memory (§4).
Adding an ability = adding a folder. Nothing else changes. A test checks every folder: front matter valid, schema
valid, description has "When to use" and "When not to use", handler importable, a fake-run passes.

## 4. How Jarvis knows what it can do (memory)

- **Abilities branch.** The registry writes a Life Tree branch `jarvis › abilities` with one leaf per tool and one per
  skill (name, one line, tier, speed, status), rebuilt when the registry changes. Its branch card is recalled like
  any other, so "can you read PDFs?" or "what can you do with Canvas?" are answered from memory, and the hub's Life Map
  shows it.
- **In the cached prompt:** a ~600-token index (one line per tool and skill) sits in the persona's cached prefix. The
  voice brain always knows the whole set exists, even for deferred tools, and searches for the details only when it
  needs them.
- **Procedures learned from use.** When a tool solves something new ("the GE 122 lab manual is in Canvas Files, not
  Modules"), the after-turn memory step files it as a procedure on that course's branch (MEMORY §2), so next time
  Jarvis goes straight there. His corrections ("use the Canvas calendar, not my email") are pinned like any correction.
- **Status is live:** a tool that needs a sign-in shows `needs_sign_in`; Jarvis then says so once instead of trying.

## 5. Intuition: picking the right tool like Claude does

Claude picks well because of three things, and Jarvis copies all three:

1. **The same tools.** Where Anthropic defines a tool Claude was trained on, Jarvis uses that exact definition:
   `web_search`, `web_fetch`, `browser_toolset_20260801`, tool search, and (phase C) `computer_toolset_20260801`; in
   tasks, Claude Code's own Read/Grep/Glob/WebSearch/WebFetch and skills. No home-made look-alikes.
2. **Descriptions that say when, not just what.** Every TOOL.md has *When to use*, *When not to use* (naming the
   better tool) and *Cost and speed*, the way Claude's own tool docs are written. Tested for in CI.
3. **A short routing policy in the persona**, the same ladder Claude follows (it's how this conversation was run):
   - **What he's told you or what's on his screen first** (now card, memory, branch cards): no tool at all.
   - **His own data next:** Canvas → `canvas_find`; his files → `read_document`; calendar/email → the Google tools.
   - **Public facts** → `web_search`; **a known link** → `web_fetch` (cheaper, no search fee).
   - **A site that needs his login, has no API, or needs clicking** → `browse`.
   - **Several steps, a skill, or research** → `start_task` / `research`, and say "On it" at once.
   - **Unsure what something is** → ask per ASK_OR_ACT (one casual question with a guess), never a tool fishing trip.
   - **Act, don't narrate.** No "I'll now search the web". If a tool takes longer than ~0.8 s, the filler covers it
     ("Let me see."), and the answer is short with details on screen.
   - **Writes are proposals** (`propose_*`), read back by code, run after his yes (RUNTIME §9).

**Checked, not hoped:** a routing eval (`tools/eval_routing.py`, ~60 of his kinds of requests → the tool(s) expected)
runs against the real model from a .bat on Laptop B and reports accuracy per tool; a wrong pick becomes a description
fix and a new eval line. Target ≥ 90% right first tool; 0 writes without a proposal.

## 6. The browser and his logins

- **The Jarvis browser** is a separate Microsoft Edge profile on Laptop B (`C:\Jarvis\browser\profile`), driven by
  Playwright (Edge is already on Windows 11: nothing to download). It is not his everyday Chrome.
- **His logins:** he signs in once per site in that profile, in a visible window (hub: Controls › Reach › "Sign in to
  a site", or when Jarvis says "Canvas wants you to sign in"). He types the password and does MFA himself; Edge may
  save it in its own password manager (encrypted by Windows for his account), so later sign-ins are a click.
  **Jarvis never sees, stores or types a password** (C26), and the browser worker refuses to type into password
  fields. After that, Jarvis browses those sites as him through the kept session: USask, Canvas, PAWS, Google,
  Crowdmark, GitHub, whatever he signs into.
- **Why this deviates from Anthropic's advice** (a fresh profile with no credentials): his request is exactly to use his
  logins. The mitigations: a separate profile; reading is the default; every consequential click (submit, send, buy,
  post, delete, change a setting) goes through the confirm hook to his yes; never on payments, passwords or
  Canvas/PAWS/Crowdmark submissions (C25); `javascript_exec` and `file_upload` stay off; outside text is data (§9a).
- **Tabs:** the worker keeps its own tabs. `show_page(url)` pulls a page up on the Stage as a web window (REACH §5.1)
  and, if he wants to use it himself, opens it as a real tab in the visible Jarvis browser. Reading *his* open Chrome
  tabs on Laptop A comes in phase C (Playwright MCP Bridge in his Chrome, through the client, with his OK per tab).
- **Modes:** `browse(task, mode="read")` (default: navigate, read, find, scroll, click links and tabs) or
  `mode="act"` (forms and buttons; each consequential step asks). Budget per run: 25 steps, $0.25, 3 minutes.

## 7. Canvas: "look for specific things"

`canvas_find(query, course?)` and `canvas_read(path)` use Canvas's own JSON endpoints with the browser profile's
cookies (GET only, enforced in code; RUNTIME §5a). `canvas_find` searches, in order and in parallel:
assignments, announcements, modules and their items, pages, files (names), discussion topics, and the syllabus;
ranks matches by title/body text and recency; and returns course, kind, title, due date, a one-line snippet and the
link. For "what does the lab 5 handout say about…", the next step is `read_document` on the file it found. A cache
(refreshed by the poller) makes common lookups instant for the voice brain. If the session has expired, it says so
and the hub shows "Sign in to Canvas".

## 8. Documents

`read_document(path_or_url, pages?, question?)`: PDFs through PyMuPDF (fast, page numbers kept), Word/Excel/
PowerPoint/HTML/CSV through MarkItDown, images through Claude vision. A PDF page with no text layer (a scan) is sent
to Claude as an image. Long documents return an outline and the pages asked for (or the pages that match the
question) instead of everything, so a 200-page manual doesn't flood the prompt. Paths only inside allowed folders
(REACH §2) or Jarvis's downloads folder; links only through `web_fetch`'s rules or the browser.

## 9. Research

`research(question, depth="standard")` starts a task: Sonnet 5.5 with web search, web fetch and the browser worker,
fanning out to up to 3 parallel researcher subagents for broad questions. It streams source cards to the Stage, ends
with a cited summary card and a 2–3 line spoken answer, and files the summary on the right branch. Caps: standard
~$0.30 / 2 min; deep ~$1.50 / 10 min (Controls › Reach). Every claim keeps its link.

## 10. Safety (what code holds, whatever the model thinks)

- **Tiers from TOOL.md, enforced by the registry:** `read` runs; `ask` only files a proposal; `never` doesn't exist
  for the model. Task brain: `can_use_tool` allows reads, routes asks to Your yes, denies the rest.
- **Browser confirm hook:** clicks and form fills are checked against the page (a submit button, a form post, words
  like send/buy/pay/delete/submit/post/confirm); those wait for his yes with a code-written read-back. URL policy:
  http/https only, no local network, refused domains listed in Controls.
- **No password fields, no payments, no Canvas/PAWS/Crowdmark writes** (C25, C26).
- **Outside text is data** (C41): page text, PDFs and Canvas content enter as tool results marked untrusted; Anthropic
  also runs injection classifiers on browser output.
- **Budgets:** per tool call, per task, per day; a run that hits its cap stops and says what it has.

## 11. Latency (per kind of tool)

| Kind | Example | Added to a spoken turn |
|---|---|---|
| No tool | "what's next today?" (now card) | 0 |
| Instant tool (cache, memory) | `canvas_find` from cache, `recall` | ~0.4–0.6 s (one more Haiku call; the filler covers > 0.8 s) |
| Fast tool | `read_document` on a PDF, `canvas_find` live | ~0.6–1.5 s |
| Server search | `web_search` | ~1.5–3 s (filler, then a short answer) |
| Tool search for a deferred tool | first use of a rare tool in a turn | + ~0.3–0.5 s |
| Task | `browse`, `research`, skills | 0 for the turn: "On it" at once; result later on screen and in voice |

## 12. Build phases

**A (v0.12.0, this build):** tools folder + registry + TOOL.md checks; abilities card; voice brain tool loop
(deferred tools, tool search, filler, server web tools); `read_document`, `canvas_find`, `canvas_read`, `web_search`,
`web_fetch`, `show_page`, `browse` (Playwright driver on the browser toolset), `research` and `start_task` (Agent SDK
runner with in-process tools and the permission callback, his skills loadable), `remember`/`recall`, `ask_dewet`;
`setup-tools.bat`; routing eval; tests with fakes.
**B:** Composio (Gmail, Calendar, Drive) behind `propose_*`; local file tools; document skills; `schedule`; code tasks;
browser act mode with real asks; his skills on live data (env note).
**C:** Laptop A client tools (his Chrome tabs, screenshots, files), computer use, camera, map, pen plotter.

**What I need from him for A:** run `setup-tools.bat` once on Laptop B; sign in to Canvas (and any other site) in the
Jarvis browser when asked; nothing else (the Claude key is already in).

## 13. Open questions for De Wet
- Per-task caps: research standard $0.30, deep $1.50, browse $0.25; per day $5. OK?
- Which sites first in the Jarvis browser: Canvas (USask), PAWS, Crowdmark, Google, GitHub?
- Reading his open Chrome tabs (phase C): wanted, and on Laptop A only?

## Sources
- Browser use tool (`browser_toolset_20260801`, members, configs, security): https://platform.claude.com/docs/en/agents-and-tools/tool-use/browser-use-tool
- GA of browser use, computer use, Skills API and Files API, 19 Aug 2026: https://thenewstack.io/anthropic-browser-use-tool/
- Tool search tool (defer_loading, accuracy past 30–50 tools): https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool · https://anthropic.com/engineering/advanced-tool-use
- Web fetch tool (URLs only from the user or earlier results): https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool
- Web search pricing ($10 per 1,000): https://docs.claude.com/en/docs/about-claude/pricing
- Agent SDK custom tools and permissions: https://platform.claude.com/docs/en/agent-sdk/custom-tools (SDK 0.2.183 checked locally: `skills`, `can_use_tool`, Windows wheel)
- Playwright MCP Bridge (his existing Chrome tabs): https://playwright.dev/mcp/configuration/browser-extension
- MarkItDown: https://github.com/microsoft/markitdown
- Huw Prosser: Mk4 architecture https://buymeacoffee.com/huwprosser/mk4-architecture-building-iron-man-jarvis-irl ; reels (vision search, spec files, emails, plot a course) https://www.tiktok.com/@huwprosser
