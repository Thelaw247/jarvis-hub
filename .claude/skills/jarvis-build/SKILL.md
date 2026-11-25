---
name: jarvis-build
description: How to build one work package (WP) of the Jarvis hub so every part looks and behaves the same: where the plan and design rules live, owned paths, tokens and contracts, scenes, tests, screenshots and the definition of done. Use whenever you're assigned a WP (H0.x, Cxx, Vxx, Bxx, Ixx) in Thelaw247/jarvis, or are reviewing one.
---

# Building a Jarvis hub work package

## Read first (in this order)
1. `docs/hub-build-plan.md`: your WP row (owned paths, needs, size), §2 navigation, §3 psychology checks,
   §5 contracts, §10 definition of done.
2. `docs/design/JARVIS_DESIGN_HUD_V2.md`: the **Night HUD** look (Huw's palette, windows and orb), glance
   codes, the day dial and the Rail, the JARVIS character rules and resume points. Then
   `docs/design/JARVIS_DESIGN_HUB_TRUST.md` §1–§4 for the trust rules, views and widget push (its §5 Earth HUD
   look is now only the optional Daylight theme).
3. Only if your WP touches them: `JARVIS_DESIGN_LIFE_TREE.md` (Life Map, branch cards),
   `JARVIS_DESIGN_WINDOWS_RESEARCH.md` (windows), `JARVIS_DESIGN_MEMORY.md` (now card, facts),
   `JARVIS_PSYCHOLOGY.md` (the why).
4. `reference/pen-reader/` for proven code: mock bridge, launcher, installer, release workflow (its palette
   and plants now only matter for the Daylight theme).
5. `contracts/` (schemas + examples) and `ui/tokens.css`.

## Rules
- **Touch only your owned paths.** Need a shared file changed (`ui/components/index.js`, `ui/index.html`,
  `CHANGELOG.md`, `VERSION`)? Say so in your report; the overseer does it.
- **Colours, radii, spacing, shadows, fonts, durations: tokens only.** No hex outside `ui/tokens.css`.
- **Data only through contracts.** Read from the store (`ui/core/store.js`) and events; send user actions
  through `bridge.act(action, target, args)`. Never invent fields; if a contract lacks something, report it.
- **Components** are custom elements in `ui/components/<name>/<name>.js` (+ `.css`, `README.md`), named
  `jv-<name>`, light DOM, class names prefixed `jv-<name>__`. They render from attributes/properties and
  emit `CustomEvent`s; no global side effects.
- **Every state has a scene**: register it so `?scene=<name>` (or `?scene=component:<name>&state=<s>`) shows it.
- **Both themes** (Night, the default, and Daylight) and your sizes (full, laptop, strip, phone, ambient as relevant).
- **Design checks (plan §3, HUD v2)**: every state is shape + colour + word; ≤ 4 amber/red marks; one big
  thing per window; nothing deleted (dock to the Rail); motion only for state (≤ 300 ms except the named wake
  and dock beats, none under reduced motion, only transform/opacity/stroke offsets); feedback ≤ 100 ms;
  sources on claims, receipts + undo; no hooks; real data only (no fake micro-text); character rules for any
  copy Jarvis speaks or shows; accessibility.
- **Accessibility**: real buttons/links, labels, focus ring, keyboard path for everything, contrast ≥ 4.5:1
  text / 3:1 UI, never colour alone, `prefers-reduced-motion` honoured.
- **Performance**: no layout thrash, CSS transforms for motion, nothing animating when hidden; the strip
  never animates (Laptop A, C37).

## Done means
1. Code + scenes + README in your folder.
2. Tests pass (`python -m pytest`; e2e smoke for UI). Add a test for your WP's logic.
3. Screenshots of every scene in both themes (`python tools/screenshots.py --only <your scenes>` once it
   exists), looked at by you, with anything off fixed.
4. `changes/<WP-ID>.md` fragment.
5. Commits follow the `jarvis-release` skill format, on branch `wp/<ID>`.
6. Report to the overseer in ≤ 8 lines: what you built, scenes added, tests, anything shared that needs
   changing, open questions. Don't claim anything you didn't run.
