# jv-source-chip and jv-confidence (C07)

Where a claim came from, as icon + word (never colour alone). `.source` = `{ kind, label, unexpected?, snippet?, ref? }`. With a `snippet` the chip opens to show the evidence itself. Unexpected sources get a dashed outline, a marker and a spoken note.

`<jv-confidence level="likely|guess">` shows confidence in words; Sure is hidden unless `show-sure`. Scene: `?scene=component:source-chip`.
