# Phone layout (V08, N8)

The same views for a narrow screen (390 px, down to 320) in the Night look: tabs at the bottom with the orb at their right end (the shell feeds it through `orbView()`: Standby, the critical alert), the Rail as a 44 px row above the tabs (gauges, counts, worst shapes; slot names when the row is 660 px or wider; a smaller gauge under 360), the caption in its own row above the Rail, toasts just above that band (`--phone-above-band`, kept current by `phone.js`). Now stacks everything full-width: what waits for a yes, the now card, pushed windows (glance + thumbnail), quick controls (`<jv-quick-controls>`). The reader opens full-screen with a compact resume card at the bottom.

Scenes: `phone-now`, `phone-said`, `phone-rail-open`, `phone-critical`, `phone-standby`, `phone-reader`, `phone-life`, `phone-branch`, `phone-activity`, `phone-controls`. Add `&theme=day`; open at 320 px wide to check the narrowest. Tests: `tests/e2e/test_phone_strip.py`.
