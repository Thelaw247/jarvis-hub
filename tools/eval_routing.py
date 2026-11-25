"""Does Jarvis pick the right tool, like Claude would, and how long until his first word? (JARVIS_DESIGN_TOOLS.md §5)

    python tools/eval_routing.py                # both voice brains side by side: quick (Haiku 5.5), deep (Sonnet 5.5)
    python tools/eval_routing.py --brain quick  # just one
    python tools/eval_routing.py --no-pick      # report only; don't ask which one Jarvis should use
    python tools/eval_routing.py --choose       # no check (free): just ask which brain Jarvis should use

Each case is one of his kinds of request and the tool(s) a good assistant reaches for first ("none" = answer
without a tool). Only the FIRST model call is made, with the real persona, routing policy and tool list; no tool
actually runs (nothing is searched, opened or changed). For each brain it prints the share of right first picks,
the cases it got wrong, and the time from sending his sentence to the first thing Claude says or does (median and
the slow end), measured with the prompt cache warm, as it is in a real conversation. The report is saved to
<Jarvis folder>\\logs\\routing-eval.txt. Cost: under 25 cents for both brains.

Then it asks which brain Jarvis should use and sets it (the hub setting voice_brain; no restart needed).
Target: >= 90% right first tool. A wrong pick becomes a description fix in that tool's TOOL.md and stays here as a
case.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CASES: list[tuple[str, set[str]]] = [
    # his own course things → Canvas
    ("when is lab five due", {"school", "canvas_find"}),
    ("did my GE 122 prof post anything about the midterm", {"canvas_find"}),
    ("find the thermo formula sheet", {"canvas_find"}),
    ("what does the CHEM 142 syllabus say about late work", {"canvas_find"}),
    ("where are this week's math slides", {"canvas_find"}),
    ("what's the room for the GE 122 midterm", {"school", "canvas_find"}),
    ("open the lab 4 worksheet instructions", {"canvas_find", "canvas_read"}),
    ("what's on the assignment page for problem set seven", {"canvas_find", "canvas_read"}),
    # his classes and due work -> the local class files (school, v0.18.0; the calendar holds the same classes)
    ("what's my first class tomorrow", {"school", "calendar"}),
    ("what do I have on Thursday", {"school", "calendar"}),
    ("when's my next lab", {"school", "calendar"}),
    ("what room is my nine thirty in", {"school", "calendar"}),
    ("what's due this week", {"school"}),
    ("who teaches GE 122 and how much is the final worth", {"school"}),
    # getting to work -> work_on (v0.19.0)
    ("pull up PPS 6", {"work_on"}),
    ("let's work on mechanics", {"work_on"}),
    ("open the chem lab", {"work_on"}),
    # learning (v0.20.0): what he tells Jarvis is saved; "forget that" is honoured
    ("from now on always open the questions before the solutions", {"remember"}),
    ("no, PPS means the practice problem sets for mechanics", {"remember"}),
    ("forget what I said about laundry on Sundays", {"forget"}),
    # his own events and free time -> his calendar
    ("am I free Friday afternoon", {"calendar"}),
    ("when is my laundry booked", {"calendar"}),
    # documents
    ("what does page four of the lab manual in my downloads say", {"read_document"}),
    ("summarise C:\\Users\\dewet\\Documents\\lab5-report.docx", {"read_document"}),
    ("read me the questions in the practice midterm pdf on my desktop", {"read_document"}),
    # the public web
    ("what's the weather in Saskatoon tomorrow", {"web_search"}),
    ("who won the Riders game last night", {"web_search"}),
    ("how much is a Raspberry Pi 5 right now", {"web_search"}),
    ("is the USask library open on Sunday", {"web_search"}),
    ("what's the latest Claude model", {"web_search"}),
    ("read this page for me https://en.wikipedia.org/wiki/Truss", {"web_fetch"}),
    ("what does https://www.usask.ca/calendar say about withdrawal dates", {"web_fetch"}),
    # signed-in sites and clicking
    ("check PAWS for my exam schedule", {"browse"}),
    ("look in Crowdmark and tell me my midterm mark", {"browse"}),
    ("go on the residence portal and see if my laundry card balance shows", {"browse"}),
    ("find the cheapest flight to Vancouver for reading week on google flights", {"browse", "research"}),
    # research
    ("research the best student budgeting apps in Canada", {"research"}),
    ("look into whether I should get a mechanical keyboard for coding, compare a few", {"research"}),
    ("find out everything about the co-op program in electrical engineering at USask", {"research"}),
    # bigger jobs and his skills
    ("plan my week", {"start_task"}),
    ("sync my classes with Canvas", {"start_task"}),
    ("make me a study pack for GE 122 lecture 22", {"start_task"}),
    ("build a study plan to master thermodynamics", {"start_task"}),
    ("when should I do laundry this week", {"start_task"}),
    ("write up my lab 5 report from my notes", {"start_task"}),
    # on screen
    ("pull up the GE 122 course page", {"show_page", "canvas_find"}),
    ("show me the Wikipedia article on trusses", {"show_page", "web_search"}),
    ("put the CHEM 142 lab manual on screen", {"canvas_find", "show_page"}),
    # memory
    ("what did I say Charlie and I planned for golden week", {"recall"}),
    ("what's Riley's role in the study squad again", {"recall"}),
    ("how did we set up the pen plotter holder last time", {"recall"}),
    # signing in
    ("log me into Canvas", {"sign_in"}),
    ("connect my Google account to the Jarvis browser", {"sign_in"}),
    # no tool at all
    ("what time is it", {"none"}),
    ("thanks Jarvis", {"none"}),
    ("tell me a joke", {"none"}),
    ("what's two hundred and forty divided by six", {"none"}),
    ("explain the method of joints simply", {"none"}),
    ("how are you", {"none"}),
]


def first_tool(message) -> str:
    for block in getattr(message, "content", []) or []:
        kind = getattr(block, "type", "")
        if kind == "tool_use":
            return block.name
        if kind == "server_tool_use":
            name = block.name
            if name.startswith("tool_search"):
                continue  # searching for a deferred tool: look at what it then loads
            return name
    return "none"


def searched_for(message) -> str:
    """A tool search alone: what did it bring in?"""
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", "") == "tool_search_tool_result":
            for ref in getattr(block.content, "tool_references", None) or []:
                name = ref.get("tool_name") if isinstance(ref, dict) else getattr(ref, "tool_name", None)
                if name:
                    return name
    return "none"


async def run_case(client, request: dict, text: str) -> tuple[str, float]:
    """(the first tool picked or "none", seconds until Claude's first word or first tool call)."""
    req = {**request, "messages": [{"role": "user", "content": text}], "max_tokens": 300}
    t0, first = time.perf_counter(), None
    async with client.messages.stream(**req) as stream:
        async for event in stream:
            kind = getattr(event, "type", "")
            said = kind == "content_block_delta" and getattr(event.delta, "type", "") == "text_delta" and event.delta.text
            acts = kind == "content_block_start" and getattr(event.content_block, "type", "") in ("tool_use", "server_tool_use")
            if first is None and (said or acts):
                first = time.perf_counter() - t0
        msg = await stream.get_final_message()
    pick = first_tool(msg)
    if pick == "none":
        pick = searched_for(msg)
    return pick, first if first is not None else time.perf_counter() - t0


async def run_brain(client, request: dict, model: str, *, at_once: int = 3, runs: int = 1) -> dict:
    """Every case against one model, `runs` times each. A few at a time, so the times are what one conversation
    would see. `score` is right picks over all tries; `steady` is the share of cases right on EVERY try (pass^k:
    an assistant he relies on has to be right each time, not on average; JARVIS_RESEARCH_GOOD_AGENT.md)."""
    request = {**request, "model": model}
    await run_case(client, request, "hello")          # writes the prompt cache; real turns find it warm
    gate = asyncio.Semaphore(at_once)

    async def one(text: str) -> tuple[str, float]:
        async with gate:
            return await run_case(client, request, text)

    runs = max(1, runs)
    tries = [await asyncio.gather(*(one(text) for text, _ in CASES)) for _ in range(runs)]
    wrong, misses = [], 0
    for i, (text, want) in enumerate(CASES):
        bad = [t[i][0] for t in tries if t[i][0] not in want]
        misses += len(bad)
        if bad:   # one line per case: what it picked on the tries that missed
            wrong.append((text, bad[0] if runs == 1 else f"{bad[0]} ({len(bad)} of {runs} tries)", want))
    times = sorted(t for one_try in tries for _, t in one_try)
    return {"model": model, "score": 1 - misses / (len(CASES) * runs), "steady": 1 - len(wrong) / len(CASES), "runs": runs,
            "wrong": wrong, "median_s": statistics.median(times), "slow_s": times[min(len(times) - 1, int(len(times) * 0.9))]}


def report(results: dict[str, dict]) -> str:
    lines = [f"Routing eval {time.strftime('%Y-%m-%d %H:%M')} ({len(CASES)} cases, first model call only)", ""]
    for brain, r in results.items():
        every = f"   every time ({r['runs']} of {r['runs']}) {r['steady']:>4.0%}" if r.get("runs", 1) > 1 else ""
        lines.append(f"{brain:<6} {r['model']:<20} right first tool {r['score']:>4.0%}{every}   "
                     f"first word after {r['median_s']:.2f} s (slow end {r['slow_s']:.2f} s)")
    if len(results) == 2:
        (qa, q), (da, d) = results.items()
        gap, more = d["median_s"] - q["median_s"], len(q["wrong"]) - len(d["wrong"])
        speed = f"{abs(gap):.2f} s {'later' if gap > 0 else 'sooner'}" if abs(gap) >= 0.01 else "at the same moment"
        picks = (f"{abs(more)} {'more' if more > 0 else 'fewer'} right first picks" if more else "the same number right")
        lines += ["", f"{da} against {qa}: first word {speed}, {picks} out of {len(CASES)}."]
    for brain, r in results.items():
        if r["wrong"]:
            lines += ["", f"{brain} got these wrong:"]
            lines += [f"  x {text!r}: picked {pick}, wanted {' or '.join(sorted(want))}" for text, pick, want in r["wrong"]]
    return "\n".join(lines)


def core_setting(value: str | None = None) -> str | None:
    """Read (or set) the hub setting voice_brain on the running core. None when the core can't be reached."""
    import httpx

    url = os.environ.get("JARVIS_CORE_URL", "http://127.0.0.1:8770").rstrip("/")
    head = {"X-Jarvis-Session": os.environ.get("JARVIS_CORE_SESSION", "")}
    try:
        if value is not None:
            done = httpx.post(f"{url}/api/act", headers=head, timeout=10,
                              json={"action": "set", "target": "voice_brain", "args": {"value": value}})
            if not (done.status_code == 200 and done.json().get("ok")):
                return None
        return httpx.get(f"{url}/api/state", headers=head, timeout=10).json().get("settings", {}).get("voice_brain")
    except Exception:  # noqa: BLE001 - the core is off or this laptop isn't paired: say so, don't crash
        return None


def pick_brain(results: dict[str, dict]) -> None:
    now = core_setting()
    if now is None:
        print("\nJarvis core isn't answering, so the brain wasn't changed. Start it (restart-core.bat) and run this again.")
        return
    names = list(results)
    print(f"\nJarvis is using the {now} brain now.")
    for i, brain in enumerate(names, 1):
        print(f"  {i} = {brain} ({results[brain]['model']})")
    try:
        answer = input("Which should he use? Type the number and press Enter, or just Enter to leave it: ").strip()
    except EOFError:
        return
    if answer.isdigit() and 1 <= int(answer) <= len(names):
        chosen = core_setting(names[int(answer) - 1])
        print(f"Jarvis now uses the {chosen} brain, from your next sentence." if chosen == names[int(answer) - 1]
              else "That didn't save. Nothing was changed.")
    else:
        print("Left as it is.")


async def main(argv: list[str] | None = None) -> int:
    import anthropic
    import keyring

    from jarvis.secrets.backend import USERNAME, service_name
    from jarvis.voice.service import BRAINS

    parser = argparse.ArgumentParser(description="Does Jarvis pick the right tool, and how fast is his first word?")
    parser.add_argument("--brain", choices=sorted(BRAINS), help="check one brain only")
    parser.add_argument("--runs", type=int, default=3, help="tries per case (default 3): 'every time' needs all of them right")
    parser.add_argument("--no-pick", action="store_true", help="report only")
    parser.add_argument("--choose", action="store_true", help="no check: just ask which brain Jarvis should use")
    args = parser.parse_args(argv)
    if args.choose:                                  # nothing is sent to Claude, so no key is needed
        pick_brain({brain: {"model": model} for brain, model in BRAINS.items()})
        return 0
    # the live key from Credential Manager, read here in this process only; never printed or saved
    key = os.environ.get("ANTHROPIC_API_KEY") or keyring.get_password(service_name("anthropic", "live"), USERNAME)
    if not key:
        print("No Claude key found (Controls > Keys on the hub). Nothing was sent.")
        return 1
    from jarvis.tools import Registry, ToolContext
    from jarvis.tools.voice import VoiceTools
    from jarvis.voice.config import VoiceConfig
    from jarvis.voice.talker_t1 import TalkerT1

    on = object()
    ctx = ToolContext(root=Path("."), canvas=on, documents=on, browser=on, tasks=on, memory=on, questions=on,
                      calendar=on)
    talker = TalkerT1(VoiceConfig(voice_id="eval"), keyed=None, tools=VoiceTools(Registry(), lambda: ctx),
                      now_card=lambda: "It's Tuesday 17 November, 2:40 pm in Saskatoon.")
    request = talker.build_request("x")
    client = anthropic.AsyncAnthropic(api_key=key)
    brains = {args.brain: BRAINS[args.brain]} if args.brain else dict(BRAINS)
    results: dict[str, dict] = {}
    for brain, model in brains.items():           # one after the other, so they don't slow each other down
        print(f"Asking the {brain} brain ({model}) {len(CASES)} things...")
        results[brain] = await run_brain(client, request, model, runs=args.runs)
    text = report(results)
    print("\n" + text)
    root = Path(os.environ.get("JARVIS_ROOT") or r"C:\Jarvis")
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "routing-eval.txt").write_text(text + "\n", encoding="utf-8")
    if not args.no_pick and len(results) > 1:
        pick_brain(results)
    return 0 if all(r["score"] >= 0.9 for r in results.values()) else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
