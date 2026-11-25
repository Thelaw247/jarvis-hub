# jv-clock (C02; small variant P1)

The clock, hours and minutes only. `.now`, `.next`, or the `live` attribute to follow the hub clock.

- Default: the big thin clock with the date and one next-up line.
- `small` (attribute): Huw's standby clock (HUD v3 §14), a small mono time with a tiny tracked date, for under
  the standby sphere: `<jv-clock live small></jv-clock>`. No next-up line. Size from the host with
  `--jv-clock-size` (the digits' font size; default `clamp(36px, 3.3vw, 64px)`).

Scene: `?scene=component:clock` (add `&state=small-standby` for one state). Details are in the comment at the top of `clock.js`.
