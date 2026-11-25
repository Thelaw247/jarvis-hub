# Jarvis's tools folder

Every ability Jarvis has is one folder here. Jarvis loads them all at start-up, gives them to his voice brain
(common ones always, rare ones through tool search) and to his task brain (Claude agents), lists them in
Controls › Reach, and files them in his memory under Projects › Jarvis › Abilities, so he knows what he can do.
Design: `docs/design/JARVIS_DESIGN_TOOLS.md`.

## Adding an ability

1. Make a folder named after the tool (`snake_case`), e.g. `jarvis/tools/weather_now/`.
2. Write `TOOL.md`:

```markdown
---
id: weather_now          # same as the folder
name: Weather right now  # what the hub shows
rung: 2                  # 1 his own data · 2 app APIs · 3 local · 4 app automation · 5 agent · 6 computer use
tier: read               # read (free) · ask (only proposes; runs after his yes) · never (never offered)
speed: fast              # instant < 100 ms · fast < 1 s · slow < 10 s · task (background, reports back)
voice: deferred          # loaded (always in the voice prompt) · deferred (found by tool search) · off (tasks only)
where: Laptop B
reads: the forecast for Saskatoon
writes: nothing
needs: []                # services it can't run without: browser, canvas, documents, memory, tasks, questions
input:
  type: object
  properties:
    when: {type: string, description: "today, tomorrow, or a weekday"}
  required: [when]
---
One sentence saying what it does (this line is its entry in the ability index).

When to use: the situations, in his words.
When not to use: the near misses, and which tool to use instead.
Cost and speed: how long it takes and what it costs.
```

3. Write `handler.py` with `async def run(args: dict, ctx: ToolContext) -> Result | str`. Raise `ToolError("…")`
   with plain words when it can't do something; return `Result(text, show=("window.push", window))` to put
   something on screen at the same time.
4. Run `python -m pytest tests/tools` (every folder is checked: front matter, "When to use", "When not to use",
   "Cost and speed", a valid schema) and add a line to `tools/eval_routing.py` so the choice is tested.

The description is what makes Jarvis pick the tool at the right moment, the way Claude picks its own: say when,
when not, and what to prefer, not just what it does.
