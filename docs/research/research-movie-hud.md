# Movie-JARVIS HUD research for the Jarvis hub

Prepared 2026-11-14. Goal: a hub De Wet can glance at, "catch some images, and see what is all going on", where nothing gets away from him. Quotes are kept under 15 words, at most one per source. Where no source exists (for example exact film hex values), this file says so.

---

## Part 1: The films' Stark / JARVIS interfaces

### Who made them
- **Iron Man (2008), helmet HUD:** Pixel Liberation Front did early tests. The Orphanage won the HUD shots, with Dav Rauch as HUD design supervisor and Kent Seki overseeing HUD detail with VFX supervisor John Nelson. https://beforesandafters.com/2019/03/18/heads-up-the-oral-history-of-iron-mans-original-hud
- **Iron Man 2 (2010):** Prologue (Danny Yount as sequence designer, Kyle Cooper as executive producer) did the HUD and holograms. They had to choreograph Downey's snaps and flicks into "a seamless dance between man and machine". https://motionographer.com/features/prologue-iron-man-2. Perception did the JARVIS holographic garage environment and the glass Stark Phone. https://www.experienceperception.com/iron-man-2.html
- **The Avengers (2012):** Jayse Hansen designed the Mark VII widgets, icons and panels, and Cantina Creative (Stephen Lawes, Venti Hristova) built and animated them. https://www.provideocoalition.com/marvels_the_avengers_taking_the_hud_to_new_heights/amp/
- **Iron Man 3 (2013):** Cantina Creative made about 100 HUD shots, Mk7 to Mk42. https://www.provideocoalition.com/upping-the-hud-ante-with-adobe-after-effects/
- **Age of Ultron (2015):** Cantina did the Mk42 to Mk45 HUDs. https://www.creativebloq.com/3d/cinema-4d-secrets-iron-mans-interface-61515419. Territory Studio did the lab screens, giving each character a colour (Stark red and orange, Banner green, Cho purple and red) inside one shared 3D "OS". https://gizmodo.com/meet-the-crack-team-who-designed-the-technology-in-age-1702594899

### What the designers say their principles are
1. **Every element has a job.** Rauch removed anything that wouldn't work for someone actually flying the suit, because Tony is an engineer. https://beforesandafters.com/2019/03/18/heads-up-the-oral-history-of-iron-mans-original-hud. Hansen says even the micro-text matches the current story point. https://www.provideocoalition.com/marvels_the_avengers_taking_the_hud_to_new_heights/amp/
2. **Glance, then absorb.** Hansen: "He has to be able to glance at stuff and absorb the data in an instant." He calls it a balance between too much data and not enough. https://www.pushing-pixels.org/?p=7447
3. **Intuitive like a phone.** Favreau wanted the HUD to "feel intuitive like my iPhone". The team borrowed its simple zooms and wipes. https://www.idownloadblog.com/2018/05/03/iphone-iron-man-hud/
4. **The interface is a character.** Favreau said they were designing a character, not a prop. JARVIS has no body, so the HUD *is* JARVIS on screen, and information arrives visually, by voice, or by Tony's gaze. https://beforesandafters.com/2019/03/18/heads-up-the-oral-history-of-iron-mans-original-hud. LePore (Perception) says the UI "itself is the personality". https://www.engadget.com/2015-12-14-perception-ui-design.html
5. **Message first.** LePore: "The message is the priority." Stark's tech sits at the top of the films' tech hierarchy. https://www.pushing-pixels.org/?p=12751. Territory calls this "hero content": a plot point that reads in seconds. https://gizmodo.com/meet-the-crack-team-who-designed-the-technology-in-age-1702594899
6. **Grounded in real cockpits.** Hansen researched flight sims, glass-cockpit books and an A-10 pilot. https://www.provideocoalition.com/marvels_the_avengers_taking_the_hud_to_new_heights/amp/. He printed a "HUD Bible" explaining what each part does, and much of the work was deciding what should animate and what should stay still. https://thenextweb.com/news/jayse-hansen-on-creating-tools-the-avengers-use-to-fight-evil-touch-interfaces-and-project-glass

### Visual language, in detail
- **Colour.** The Mark II HUD was mostly cyan. The Mark III was white with accent colours, chosen to be different, and Obadiah's Iron Monger HUD was flat military red with plain OCR-A type. https://beforesandafters.com/2019/03/18/heads-up-the-oral-history-of-iron-mans-original-hud. The first-person view uses blue wireframe, a cyan status box and a thin white compass needle. https://scifiinterfaces.com/2015/07/21/iron-man-hud-1-person-view/. Late Avengers changes were mostly shifts toward red and changes to how much detail showed at once. https://thenextweb.com/news/jayse-hansen-on-creating-tools-the-avengers-use-to-fight-evil-touch-interfaces-and-project-glass. Why blue: it is a strong RGB primary that survives set lighting, green reads as old tech, red as too militaristic, and the in-joke after reviews is "Make it Blue". https://pushing-pixels.org/coleran/2014/04/why-so-blue. Shedroff and Noessel averaged sci-fi screen colours from 1968 to 2011 and found them mostly blue, which reads as unnatural and "inhuman". https://99percentinvisible.org/episode/future-screens-are-mostly-blue/. **No source gives official hex values.** From stills the family is cyan-white on near-black, with amber/orange and red reserved for warnings (an observation, not sourced).
- **Shapes.** The Mark II had five icons along the bottom (diagnostic, flight, power, radar, navigation). The Mark III merged them into one keyhole-shaped "Omega" widget. https://beforesandafters.com/2019/03/18/heads-up-the-oral-history-of-iron-mans-original-hud. Other shapes: circular reticles that expand in from different depths, and "battle mode" swiping round. https://www.hudsandguis.com/2013/05/15/the-avengers/. Also a compass tape, a stacked altimeter and a radar that unfolds from 2D to 3D. https://www.provideocoalition.com/marvels_the_avengers_taking_the_hud_to_new_heights/amp/
- **Line and depth.** In Iron Man 3, Sketch-and-Toon varied line weight in space. The look moved from flat 2D toward "a more organic holographic world" with volumetric light, flares and glassy reflections. https://www.cgw.com/Press-Center/Web-Exclusives/2013/Cantina-Creative-Gives-Iron-Man-3-a-Heads-Up-.aspx. Stereo meant cheats showed, so everything had to be in focus and readable, with lots of black negative space. https://www.pushing-pixels.org/?p=7447
- **Status vs detail.** The persistent part is the small strip of gauges at the bottom, and everything else "changes to the needs of the situation". https://scifiinterfaces.com/2015/07/01/iron-man-hud-a-breakdown/. Gauges sit small in the periphery and grow toward the centre when needed. Most functions appear only when JARVIS thinks Tony needs them. https://scifiinterfaces.com/2015/07/13/iron-man-hud-just-the-functions/
- **Motion.** Graphics fly in and out from behind the camera instead of cluttering the view. The Mark III keyhole turned, unlocked and fanned out, then collapsed. Seki called it "a mechanical visual in a digital form". Graphics were damped so they lagged slightly under stress. https://beforesandafters.com/2019/03/18/heads-up-the-oral-history-of-iron-mans-original-hud.
- **Manipulation.** Prologue lifted screen elements off flat surfaces into the 3D space around Stark, driven by finger snaps and wrist flicks. https://motionographer.com/features/prologue-iron-man-2. LePore himself doubts gesture for real daily work. https://www.pushing-pixels.org/?p=12751

### What makes it read as "JARVIS" and feel alive
- It is **personal and conversational.** The HUD answers Tony. Favreau's rule was to look into his eyes to see who is asking. https://beforesandafters.com/2019/03/18/heads-up-the-oral-history-of-iron-mans-original-hud
- It **moves mechanically.** Parts unlock, fan and lock, with a slight physical lag (same source). It doesn't just fade.
- It is **luminous on black.** Glow, glassy reflections and depth (CGW source above).
- It feels **ahead of everyone else's tech.** Villains get flat military UIs (befores & afters, above).
- **Its weak spot:** cryptic micro-text such as "N -8 W -97 RNG EL" adds load. Critical gauges left small in the periphery are a weak strategy. JARVIS should escalate instead, because "attention management is crisis management". https://scifiinterfaces.com/2015/07/21/iron-man-hud-1-person-view/

### What reads in under a second
Big familiar instruments (compass tape, altitude), one consolidated status widget, colour shifts to red, and JARVIS's voice. Test audiences understood the HUD at once, while extra explanation confused them. https://avclub.com/nerd-out-like-tony-stark-with-this-breakdown-of-how-the-1825732473

---

## Part 2: Glanceable and situational-awareness research

### Pre-attentive coding
- Hue, size, intensity, curvature, flicker, motion direction and velocity, and depth are detected pre-attentively, in under about 200 to 250 ms. A *conjunction* (red circle among red squares and blue circles) needs a slow serial search. https://csc2.ncsu.edu/faculty/healey/PP
- Colour beats shape: "The interference is asymmetric". Map the most important data to the most salient feature (same source).
- About seven well-chosen colours can be told apart quickly: "seven isoluminant colours is the maximum". They need enough colour distance, linear separation and different colour names. https://www.cs.ubc.ca/sites/default/files/tr/1996/TR-96-10_0.pdf
- Working memory holds about 3 to 5 chunks, "averaging about four chunks". https://memory.psych.missouri.edu/assets/doc/articles/2001/cowan-bbs-2001.pdf
- **Images vs text:** enhanced thumbnails (picture plus a large readable label) cut web search time by about 30% compared with text. Plain thumbnails didn't reliably help, and text still wins when a name identifies the target. https://web.mit.edu/rruth/www/Papers/2001-CHI-Thumbnails.pdf
- In peripheral vision, motion is detected almost 100% of the time, while colour misses rose to about 24%. Slow linear oscillation was "a good compromise" (noticed, not irritating). Travelling or scrolling motion distracted most. https://www.interruptions.net/literature/Bartram-IJHCS03.pdf

### Ambient and calm displays
- Calm technology moves things between periphery and centre. Locatedness, knowing what's going on around you, is "the fundamental gift that the periphery gives us". https://calmtech.com/papers/designing-calm-technology
- Pousman and Stasko's notification ladder runs user-poll, change-blind, make-aware, interrupt, demand-attention. Ambient systems mostly live at change-blind and make-aware. https://faculty.cc.gatech.edu/~stasko/papers/avi06.pdf
- Matthews et al.: peripheral views that show *extracted content* (Clipping Lists) beat shrunken windows and plain change borders, because "the one bit of information was not enough". https://www.interruptions.net/literature/Matthews-CHI06-p989-matthews.pdf

### Situation awareness, HUDs, overviews, dashboards
- Endsley's three levels: perceive the elements, comprehend what they mean, project their near future. Overload and underload both degrade it. https://en.wikipedia.org/wiki/Situation_awareness
- Shneiderman: "Overview first, zoom and filter, then details-on-demand". https://webspace.science.uu.nl/~telea001/uploads/VACourse/Shneiderman96.pdf
- Few defines a dashboard as a single screen for monitoring at a glance: no scrolling, summaries and exceptions, little non-data ink. "If you highlight too much information, nothing will stand out." https://www.uxmatters.com/mt/archives/2007/04/book-review-information-dashboard-design.php
- On a pilot's HUD, symbology laid over the main task causes cognitive tunnelling. Moving it about 8° away removed the cost, and placement mattered more than contrast. https://human-factors.arc.nasa.gov/groups/HCSL/publications/Foyle_AvPsyc01.pdf

### Why "things get away from me", and fixes
- **Change blindness:** people missed 64% of gradual changes and 42% of instant ones, and "high saliency alone is not always enough". https://www.pokristensson.com/pubs/BrockEtAlCHI2018.pdf.
- **Interruptions make people forget intentions:** about 85% remembered without an interruption and about 66% with one. A small persistent on-screen blue dot removed the cost. https://interruptions.net/literature/McDaniel-ACP04.pdf. An explicit "resume this" cue and an "end of interruption" cue improve resumption. https://humanfactors.arc.nasa.gov/flightcognition/Publications/Dodhia_SARMAC'05.pdf
- **Keep status visible:** two of Nielsen's heuristics apply, visibility of system status and recognition rather than recall (make cues visible). https://thedecisionlab.com/reference-guide/design/nielsens-heuristics
- **Spatial stability:** distinct fixed locations (memory-palace style) beat generic icons. https://scifiinterfaces.com/category/marvel-cinematic-universe/iron-man/iron-man-2008/

### Accessibility
- Never carry meaning by colour alone. Add text, shape or an icon. https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html. About 1 in 12 men are colour blind, mostly red/green. https://www.colourblindawareness.org/colour-blindness/
- Meaningful graphics need 3:1 against adjacent colours, and "2.999:1 would not meet the 3:1 threshold". Thin anti-aliased lines render fainter. https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- Motion: honour `prefers-reduced-motion`, and parallax triggers vestibular symptoms. https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html. Auto-moving content over 5 s needs pause, stop or hide, because continuous movement distracts. https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html
- On dark backgrounds, avoid pure black and lower saturation, because saturated colours "create optical vibrations". White-on-black halation affects people with astigmatism. https://atmos.style/blog/dark-mode-ui-best-practices
- Performance: animate only `transform` and `opacity`. Animating `box-shadow` or filters repaints. https://engineering.empathy.co/understanding-web-animation-performance

---

## Recommendations for Jarvis (original design in this genre)

Don't copy Marvel assets (no arc-reactor glyph, keyhole widget, logos or film layouts). Use the genre's grammar (luminous lines on near-black, rings, ticks, brackets, depth) with Jarvis's own signature. This is a *proposal* for a third theme in `ui/tokens.css` (e.g. `data-theme="night-hud"`, next to Daylight and Evening). The overseer owns that file and De Wet approves design changes. It reuses the fonts and motion tokens already shipped, so nothing new is downloaded.

### 1. Palette (contrast computed with the WCAG formula)
| Token | Hex | Role | vs bg #070B10 | vs surface #0D1620 |
|---|---|---|---|---|
| `--canvas` | `#070B10` | base, blue-black, not pure black | — | — |
| `--card` | `#0D1620` | panel surface (90% opaque over canvas) | — | — |
| `--sunken/raised` | `#13202C` | hover/raised | — | — |
| `--text` | `#E6F4F8` | primary text (ice white, not pure white) | 17.5 | 16.2 |
| `--muted` | `#8FA9B4` | secondary text | 8.0 | 7.4 |
| `--hud` | `#38D6F0` | the cyan family: rings, active lines | 11.3 | 10.5 |
| `--hud-soft` | `#7FE6F5` | glow core/highlights | 13.7 | 12.6 |
| `--hud-deep` | `#1A8FA6` | inactive arcs, tracks | 5.2 | 4.8 |
| `--ok` | `#4FD1A5` | done/healthy (teal-green) | 10.3 | 9.5 |
| `--warn` | `#FFB547` | needs you soon (amber) | 11.2 | 10.4 |
| `--crit` | `#FF5A5F` | critical/overdue (coral red) | 6.5 | 6.0 |
| `--jarvis` | `#A99BFF` | "Jarvis is doing this" (violet) | 8.3 | 7.7 |
| `--grid` | `#2A4A5A` | decorative grid/ticks only (2.1:1, never meaningful) | 2.1 | 1.9 |

That is seven meaningful hues, within Healey's limit. All text and meaningful colours pass 4.5:1 on all three surfaces. Glow is a static layered stroke (a wide `--hud` line at 25% opacity under a 1.5 px `--hud-soft` line), never an animated blur. Lines carrying meaning are at least 1.5 px.

### 2. Shape vocabulary (each shape means one thing)
- **Ring** = a thing being tracked. **Arc on the ring** = progress or time left (a 270° gauge, gap at the bottom).
- **Tick marks** = time scales (hour ticks on the day ring) and units. They are decorative unless labelled.
- **Corner brackets** `⌜ ⌟` = "this wants you". They are the only selection and attention frame.
- **Reticle** (thin ring plus four short ticks) = Jarvis's current focus or task. Only one exists at a time.
- **Dot grid and hairline rules** = structure. Low contrast, never carry data.
- **Signature (original): "the Lens".** The existing orb becomes three concentric rings with a notch at 12 o'clock. The notch's position and fill shows Jarvis's state: idle notch open, listening notch filled, thinking outer ring segmented, speaking middle ring pulses once per phrase.

### 3. Typography (already shipped, zero new font cost)
- Panel labels: Lexend 500, 12/16, UPPERCASE, tracking 0.08em, 2 words max.
- Numbers and telemetry: JetBrains Mono with `font-variant-numeric: tabular-nums`, so digits don't jitter as they update.
- Anything you read: Atkinson Next, 15/23, sentence case.
- **No fake micro-text.** Every string is real data (Hansen's rule, and the critics' "N -8 W -97" warning).

### 4. Glanceable codes: every state is shape + colour + word
| State | Shape | Colour | Word/icon | Notification level |
|---|---|---|---|---|
| Done / healthy | filled ring with check | `--ok` | "Done" | change-blind |
| In progress | ring with progress arc | `--hud` | "%" or time left | change-blind |
| Jarvis working on it | reticle | `--jarvis` | "Jarvis" | make-aware |
| Needs you soon | diamond inside brackets | `--warn` | "Soon" plus due time | make-aware |
| Critical / overdue | triangle inside brackets | `--crit` | "Now" plus what | interrupt, then voice |
| Parked / snoozed | dashed ring | `--muted` | "Parked" | user-poll |

Domains (classes, homework, calendar, builds, plotter, messages) are told apart by **icon and fixed position**, never by colour, so colour stays free for urgency. Each item shows an **image** (thumbnail, slide or photo) *plus* a big label, the enhanced-thumbnail pattern, because image and label together were fastest. Keep the number of things competing for attention to about 4. Anything beyond that collapses into a "+N" chip.

### 5. Layout: overview first, nothing gets away
- **Overview ring (always visible).** A day ring with hour ticks and a "now" hand surrounds the Lens. Domain sectors sit at fixed bearings (spatial memory). Each sector shows its worst state with the codes above, so one glance gives Endsley level 1, a red/amber sector gives level 2, and the arc to the next due item gives level 3.
- **The Rail (persistent strip).** Every open, deferred or interrupted item lives here as a small chip (icon, thumbnail and state shape). Closing a panel **docks it to the Rail and never removes it**. Only "Done" or explicit "Archive" takes it off. This is the McDaniel blue-dot effect, built in.
- **"Since you looked" marks.** New or changed items get a static notch on their chip and sector plus a count ("3 new"). The mark stays until the item is opened or hovered. Changes are never shown only as a transition, because gradual changes are missed 64% of the time.
- **Resume cue.** After an interruption (class, sleep), the first panel is "You were doing X → resume".
- **Details on demand.** Panels expand *from their sector or chip* and collapse back to it (scale from origin, 200 ms), so position never jumps. Moving a panel to the Rail minimises it, moving it to the "Parked" zone snoozes it, and nothing is ever thrown away.
- **Escalation, not tiny gauges.** Critical items move from their sector into a fixed alert slot *beside* the centre (not over the work area, per the HUD tunnelling finding), and Jarvis says one sentence about them.

### 6. Motion rules (light by design)
- Motion only marks a **state change**. Nothing loops idly. On Laptop A's strip nothing animates at all, and changes there are static marks only (repo rule).
- Use the existing tokens: `--t-fast 100ms` for feedback, `--t-move 200ms` for expand and collapse, `--t-fly 300ms` max for the one-time "assemble" when the hub opens. In assemble, rings draw in with `stroke-dashoffset` and panels unlock from their sector, giving a mechanical feel without a long boot.
- Critical alerts use a **slow linear oscillation** of the brackets (±2 px, about 1 Hz) for at most 5 s, then stop and stay as a static red triangle (WCAG 2.2.2).
- Ambient elements (the "now" hand, the Lens) update at **≤ 1 fps**. Any continuous ambient animation is capped at ≤ 30 fps through `requestAnimationFrame` throttling and pauses when the window is hidden.
- Animate only `transform`, `opacity` and SVG `stroke-dashoffset`. No animated `filter` or `box-shadow`, no canvas or WebGL particle backgrounds, no parallax, and no scrolling tickers (they are the most distracting peripheral motion).
- `prefers-reduced-motion: reduce` turns every transition into an instant swap or a 100 ms opacity change. The oscillation becomes a static thicker bracket.

### 7. Performance budget
Use inline SVG plus CSS only, with no video or 3D layers. Keep the HUD under about 300 SVG/DOM nodes and input feedback under 100 ms (repo rule).
