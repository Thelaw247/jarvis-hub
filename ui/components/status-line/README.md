# jv-status-line (C03; HUD v3 §14 decision 2)

The status word bottom-left, tiny, saying only what is true right now ("Listening", "Thinking", "Speaking",
"Standby · Mic on", "Muted", "Offline"), with a small mic glyph. `.orb` is the state of the orb he can see (the
shell passes `shownOrbState()`: standby under the resting sphere and the empty Stage). The interruption dial shows
only when it isn't the default Balanced. The mic state is always visible (HUB_TRUST §1.9), by shape and word: mic =
can hear you, mic struck through = muted, amber struck through = offline (no toggle then). One tap mutes
(`jv-act` mute / unmute). Night: a 12 px mono readout (the smallest text the hub uses) with no ring around the mic; Daylight keeps the reading
face. `.orb`, `.settings`, `.online`.

Scene: `?scene=component:status-line` (add `&state=<name>` for one state, `&theme=night`).
