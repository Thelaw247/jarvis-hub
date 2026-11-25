# jv-approval-card (C12)

A write waiting for his yes: consequences first, the read-back, the sources, then Yes (the one accent button), No and Change it. Says when it can't be undone and when the offer runs out. `.approval`, `.now`.

- The first answer locks the buttons (`aria-disabled`), so a double click can't answer twice.
- Change it opens an inline field (Enter sends, Shift+Enter new line, Esc cancels). The text goes out as `jv-act { action: "change", target, args: { text } }` and the card stays, reading "Changing…" with his words.
- Wide cards (≥ 680 px, e.g. Activity) put what will happen on the left and the question and answers on the right.

Scene: `?scene=component:approval-card` (add `&state=<name>` for one state, `&theme=evening` for Evening). Details are in the comment at the top of `approval-card.js`.
