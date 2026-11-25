# Controls › Keys (K2)

`#/controls/keys` (`jv-view-keys`, registers its own route). The API keys Jarvis holds, write-only
(contracts/keys.schema.json, JARVIS_CORE_BUILD_MAP §3). One row per service: status as a glance code (shape + colour +
word), the last 4 characters only (none at all for a password: restic), added, last checked, last used. Rotation:
**Add next key → Check → Make live → Remove old**; the old key is kept 15 minutes ("kept for 14 more minutes…") with a
link to the provider's console to revoke it. Remove asks first ("Remove it" / "Keep it"). A `fell_back` row shows the
Your yes mark and raises a Your yes flag on the Rail (`keysYesFlag`; `jarvis_hub/demo/keys.py yes_flag`).

**Secrets.** `keys-api.js` is the only door (not `bridge.act`, not `/api/act`, not the store). The field is one
`<input type=password autocomplete=off spellcheck=false>` node made in JS and moved back in after each render, so its
value never goes through a template, attribute, the store, events or web storage. Check reads it once, clears it at
once, and sends it only in the request body.

**No core.** The hub's demo backend (`jarvis_hub/demo/keys.py`) answers with the header `X-Jarvis-Keys: example`:
the page says "Jarvis core isn't connected yet", marks every row as an example (made-up last 4s `EX01`…) and accepts
nothing. Its write routes refuse without reading the body. **Phone** (or `can_write: false`): view-only.

Scenes: `keys` (not connected), `keys-live`, `keys-next-waiting`, `keys-checking`, `keys-failed-check`,
`keys-fell-back`, `keys-old-kept`, `keys-missing`, `keys-expiring`, `keys-phone`. The state scenes are a local preview
of a connected core: writes are answered in the page, nothing is sent or kept.

**Voice.** Below the keys, one plain field for the ElevenLabs voice ID (`voice-setting.js`, `jv-voice-setting`). Not a
secret: shown back, saved where Jarvis core runs via `PUT /api/settings/voice` (jarvis-core `data\settings.json`). With no core
(answer header `X-Jarvis-Settings: example`) it says so and is disabled; hidden when the page is view-only.

Two laptops (v0.24.0): the hub's answers carry `X-Jarvis-Kept` ("here" or the other laptop's name), and on a laptop
that runs its own Jarvis `X-Jarvis-Other-Name`. Then the page shows "Also update <laptop>": ticked, a new key's steps
and the voice ID go out with `X-Jarvis-Also-Other: 1` and the hub repeats them on the other laptop's Jarvis
(`jarvis_hub/keys_proxy.py`). Removing a service is never repeated.
