# Jarvis — Tools, Windows and On-Screen Research

Last updated: 2026-11-14
Status: design. Composio and window control are built in P1; on-screen research in P2. Part of the design set in Jarvis/. Extends JARVIS_DESIGN_RUNTIME.md (connectors, approvals, hidden instructions) and JARVIS_DESIGN_HUB_TRUST.md (§2a widget push).

**What De Wet asked for (2026-11-14):**
1. "Link it up to Composio": Jarvis gets the same kind of app access Claude has (Gmail, Docs, Sheets, Calendar, GitHub…).
2. Jarvis pulls up windows like Huw's assistant does in his reels.
3. Jarvis does research the same way: by filling the screen with windows as it finds things.

All three are possible with the current architecture. Nothing here touches the spoken-turn hot path.

---

## 1. Composio: Jarvis's tool layer

**Why Composio:** one key gives access to hundreds of apps with sign-in handled for us, it ships a provider for the Claude Agent SDK that runs its tools **in-process**, and his skills already mention Composio, so the environment note gets simpler. The claude.ai connectors themselves can't be used: they belong to his Claude account, not to an API key.

**How it's wired**
- **Account and sign-ins:** De Wet connects each app once in Composio (he signs in himself; Jarvis never sees passwords). The Composio API key lives in Windows Credential Manager (C26).
- **Background jobs (T2):** `composio-claude-agent-sdk` exposes the tools to the Agent SDK as an in-process MCP server, so Jarvis's permission rules still apply. Composio's own examples use `bypassPermissions`; **Jarvis never does** (`dontAsk` + explicit allow list, RUNTIME §4).
- **The spoken turn (T1):** no Composio tools in the cached prompt. If he asks about something only Composio can reach ("what's in the Praelecta sheet?"), the talker calls one `lookup(app, question)` tool that runs a read in the background and says "let me check" if it takes over ~300 ms.
- **Not the Messages API MCP connector.** There, Anthropic's servers run the tool call directly, so Jarvis couldn't hold a write for his yes. It's only acceptable for read-only allowlists, and we don't need it.

**Read/write split (keeps the approval rule, C12)**
| Composio tool kind | Who can use it | How |
|---|---|---|
| **Read** (list, get, search, fetch) | Jobs and `lookup` | Allowed directly. Results are outside content → reader step first (RUNTIME §9a) |
| **Write** (send, create, update, delete, post) | **Only the executor, after his yes** | Never shown to the model. The model calls a `propose_*` tool; after the spoken yes, the executor (plain code) calls the Composio write action with the stored arguments and writes the undo record |

**What stays direct (faster, free, already designed):** Google Calendar and Gmail pollers and the Canvas session keep feeding the now card and branch cards, so everyday answers stay instant. Composio covers everything else and is the **single write path** for apps (calendar writes included), so there's one executor and one undo format.

**Privacy:** Composio is a third party that sees the data passing through it. Tier-2 data (money, health, others' private details) isn't sent through Composio unless the task needs it, and the reason is logged (MEMORY §9).

**Latency effect:** a Composio call adds roughly 0.3–1.5 s (estimate; measured in P1). It's always T2 or behind "let me check"; normal turns are unchanged.

---

## 2. Windows: two kinds

### 2.1 HUD windows (inside the hub)
Huw's assistant fills the screen with panels while it talks. Jarvis already does this with **widget push** (HUB_TRUST §2a). This doc adds a small **window manager** for them:
- **Voice commands (T0, no LLM):** "close that", "close all" / "clear the screen", "bigger" / "full screen", "put the chart on the left", "next" / "back" (pages), "keep that up" (pin), "open it" (open the source as a real window, §2.2).
- **Layout:** 12-column grid; up to 6 windows; new ones fill from the top-left; the orb moves to the bottom-right while windows are up (as in Huw's reels).
- **Saved layouts:** any arrangement can be saved to a branch ("save this to Praelecta") and reopened later ("pull up that Praelecta research"). The widgets are rebuilt from stored data, not screenshots.
- **Latency:** ≤ 100 ms event to pixel (SSE).

### 2.2 Real desktop windows (apps, files, browser pages)
Jarvis also opens and arranges real windows: files, apps and browser pages.
- **Where:** the screen he's using (from presence). Laptop B's display is the HUD; Laptop A gets real windows when he's at it, **never in game mode**.
- **How:** the user-session client (`jarvis-client`, RUNTIME §2 and §7; a small copy runs on Laptop B too) opens things with `ShellExecute` / Edge app windows and places them with Win32 window positioning (`SetWindowPos`, per-monitor DPI aware). No LLM: these are T0 commands.
- **Named layouts:**
  - **Study:** problem set left, solutions right (the P1 "pull up PPS 7" moment).
  - **Research:** top sources tiled in a 2×2 or 3×2 grid of browser windows.
  - **Coding:** editor + browser + terminal.
  - **Custom:** "save this layout as X".
- **Latency:** the command is matched in < 50 ms; windows appear as fast as Windows opens them (~0.2–1 s, slower on a cold browser start).
- **Laptop A protection (C37):** windows open only on his request or an approved offer; Jarvis adds no background process cost.

---

## 3. Research on screen ("research X", "look into", "compare")

**What Huw's does (Rose reel, Oct 29):** after a question, the screen filled with text cards, photos, a video, bar charts and a big number (≈20m) while the assistant talked. Jarvis does the same, with sources on every card.

### 3.1 Flow
1. **"On it"** from the phrase cache (< 300 ms). The orb goes to its thinking state.
2. **A research job starts (T2):** Sonnet with Claude's **web search** and **web fetch** server tools, plus memory recall and Composio reads when his own data matters.
3. **Windows stream in as things are found:**
   - **Source card** for each useful source: title, site, date, the one key point, link.
   - **Image tile** when a page has a useful image (shown from the source, linked back).
   - **Number card** for a key figure (big number + source).
   - **Chart or table card** for comparisons (dataviz rules).
   - **Video tile** when a relevant video turns up (doesn't autoplay).
4. **Summary card** last: the answer in ≤ 5 lines, every claim citing its source cards. Jarvis says 2–3 lines out loud.
5. **Follow-ups:** "open the sources" → real browser windows in the research layout (§2.2); "go deeper on the second one"; "save this to Praelecta" → saved to that branch with its layout.

### 3.2 Depth
| Depth | Searches | Typical time | Use |
|---|---|---|---|
| Quick | ≤ 3 | ~5–10 s | "what's the deal with X" |
| Standard (default) | 5–8 | ~15–30 s | "research X", "compare A and B" |
| Deep | 15–25 | ~1–3 min | "really dig into X"; he's told the expected time first |

The first window appears within ~1–3 s of the first search returning. Windows appear as real work completes; **no fake delays** (psychology S3).

### 3.3 Safety (C41, C25, copyright)
- **Web pages are outside content:** they go through the reader step; research jobs have **no write tools** at all.
- **The data-leak rule (RUNTIME §9a.4):** a research job that browses the open web gets **only the question and non-sensitive context**, never his private data. If an answer needs both ("how do my grades compare with the average?"), the web part runs first without his data, then a second step with **no fetch tools** combines it with his data.
- **Short excerpts only:** cards show a key point in Jarvis's own words or a short quote, plus the link, never whole articles.
- **Academic integrity (C25):** research helps him learn and find sources; it doesn't write graded work for him.

### 3.4 Cost
Claude's web search is **$10 per 1,000 searches** plus tokens; web fetch has no fee beyond tokens. A standard research run (~6 searches on Sonnet) ≈ **$0.10–0.30**. Three a day ≈ $10–25/month, which still fits the $100 credit (current estimate ~$30/month without research). Controls gets a **daily research cap**, and the spend meter shows research separately. If it runs hot, swap in a cheaper search API behind the same tool.

---

## 4. Where it lands in the build (JARVIS_BUILD_PLAN.md)
- **M1.4:** Composio account + app sign-ins; read tools for jobs and `lookup`.
- **M1.6:** the executor's writes go through Composio; `propose_*` for each write kind.
- **M1.7:** HUD window manager + voice window commands; real-window layouts (Study first) in the client.
- **M2.8 (new):** research on screen: research job, streaming source/number/chart/video windows, summary card, "open the sources", saving to a branch, daily cap.

## 5. Tests
- No Composio write action can run without a matching approved proposal (test every write tool).
- Injection pages in research results produce no proposals and no instructions followed.
- A research job never receives tier-1/2 private data unless it has no fetch tools (checked in code).
- Window commands: 30 spoken commands → ≥ 95% correct; the Study layout opens in ≤ 1 s warm.
- Research: first window ≤ 3 s after the first search returns; every summary sentence links to a source card.

## Sources
Anthropic MCP connector https://platform.claude.com/docs/en/agents-and-tools/mcp-connector · Composio Claude Agent SDK provider https://pypi.org/project/composio-claude-agent-sdk/ · Composio with the Claude Agent SDK https://composio.dev/toolkits/composio/framework/claude-agents-sdk · Claude pricing (web search, web fetch) https://docs.claude.com/en/docs/about-claude/pricing · Huw Prosser's "Rose" reel https://www.instagram.com/huwprosser/reel/DfGOQ5pIZqy/
