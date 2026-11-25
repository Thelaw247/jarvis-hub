# jv-now-card (C13, Night pass N5a)

The now card leads with content, never a time-of-day greeting heading (`greeting` in the contract is for
what Jarvis says, not a title): progress first (the progress glance "4 of 6 done today", or the done glance when the day is done),
then Next, led by its title in the condensed face with its picture (`next_up.thumb`) or a big room code beside it,
one flag (the **soon** glance + "One thing") with a "Why?" that shows its source and ends with controls (less of
this · that's wrong · open it), things ready to offer, and what Jarvis isn't sure about. At most four parts.
Section kickers are mono caps.

`.card` = a `now_card` contract object. `.hide = "next flag"` drops parts that a window on the Now canvas already
shows, so nothing is said twice. Scene: `?scene=component:now-card`.
