# Strip (V07, N8)

Laptop A's small always-on-top bar (360 × 96). A still orb read through `orbView()` (Standby when nobody is at the hub, a red ring and "Critical" while something on the Rail is critical), its word ("Listening" when idle, as the status line), the Rail's worst glance shape + word and "N new" (a static cyan notch), and one line for what matters next: the critical thing, else what waits for a yes, else next up. After game mode, one still line: "While you played: Homework 1, Messages 2" (marks made while it was on, by Rail slot; it goes when they are seen). In game mode nothing shows except a critical thing. Nothing animates and nothing makes a sound (tested). Under 72 px tall it becomes one line.

Game mode's start isn't in the contracts, so the strip notes it itself (`ui.gameSince` / `ui.gameEnded`, the UI-only slice).

Scenes: `strip`, `strip-waiting`, `strip-muted`, `strip-standby`, `strip-critical`, `strip-game`, `strip-game-critical`, `strip-after-game`. Add `&theme=day`. Tests: `tests/e2e/test_phone_strip.py`.
