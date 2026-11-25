# Controls (V05)

Four groups of at most four rows: Interruptions, Approvals, Look, Data and privacy. Real switches and radio groups with their state in words. Links to Under the hood, the shortcuts list and the demo replay. Data sources show four rows; the rest are behind "N more". Look › **Where Jarvis shows things** (N9): Stage window (the default: the windows Jarvis pulls up go to the Stage, a separate window, and the home page stays calm) or On the hub (the old behaviour); it sets `settings.stage` (`window | hub`).

Deep links: `#/controls/<setting>` (ids in `SETTINGS` in `controls.js`, also used by the command bar) scrolls to that row and focuses its control. Radio groups get roving tabindex and arrow keys from `core/dom.js`.

Scenes: `controls`, `controls-quiet`, `controls-stage-hub`, `controls-live`. Add `&theme=evening` or `&size=laptop|phone|ambient`. Details are in the comments at the top of each file.
