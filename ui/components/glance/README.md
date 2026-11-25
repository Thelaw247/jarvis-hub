# jv-glance (N5a)

The glance codes (HUD v2 §5): every state is a **shape + a colour + one word**, never colour alone.

| State | Shape | Colour | Default word |
|---|---|---|---|
| `done` | filled disc with a dark check (≥ 16 px) | `--cyan-hi` | Done |
| `progress` | open ring; with `value` a dim track and an arc | `--line` | In progress |
| `jarvis` | reticle (thin ring + 4 ticks), `scan` adds a scan bar | `--cyan` | Jarvis |
| `soon` | diamond in corner brackets | `--warn` | Soon |
| `yes` | hollow square in corner brackets | `--warn` | Your yes |
| `critical` | triangle in corner brackets; brackets move ±2 px for 5 s, then still (a 3 px still frame under reduced motion) | `--crit` | Now |
| `parked` | dashed ring | `--text-3` | Parked |

`<jv-glance state="soon" word="Soon · Wed 8 pm" size="rail|inline|hero" value="0.6" bare scan>`.
The accessible name is the word (`role="img"`); `bare` draws only the shape (screen readers still hear the word).

For components that draw their own markup: `import { glance, GLANCE, GLANCE_STATES, WANTS_YOU } from "../glance/glance.js"`,
then `${glance("progress", { value: 0.58, word: "Q7 of 12", size: "rail" })}` inside an `html` template.
`WANTS_YOU` (soon, yes, critical) are the only states in corner brackets and the ones that count toward "≤ 4 amber/red marks".

Scene: `?scene=component:glance` (every state at every size, shape-only, progress steps).
