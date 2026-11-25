// Controls › Keys › Voice: the one ElevenLabs voice ID Jarvis speaks with (C38/C39: an original voice made with
// Voice Design, never a clone). Not a secret, so it is shown back; it is kept where Jarvis core runs
// (data\settings.json) through GET /api/settings and PUT /api/settings/voice, which the hub passes to jarvis-core.
// On a laptop that runs its own Jarvis, the Keys page's "Also update <other laptop>" tick box sends it to both.
//
// Built once and never re-rendered by the Keys page (it moves this node back in after each draw, like the key
// field), so what he typed survives the page's redraws. With no core it says so and accepts nothing.
import { bridge } from "../../core/bridge.js";
import { store } from "../../core/store.js";
import { localIso } from "../../core/dom.js";
import { alsoHeaders, keptWords, otherWords, readWhere } from "./keys-api.js";

const ID_SHAPE = /^[A-Za-z0-9]{10,40}$/;

export class VoiceSetting extends HTMLElement {
  connectedCallback() {
    if (this._built) { this.listen(); return; }
    this._built = true;
    this.className = "jv-voice";
    this.innerHTML = `
      <label class="jv-keys__label" for="voice-id">ElevenLabs voice ID</label>
      <input id="voice-id" class="jv-keys__secret jv-voice__input" type="text" autocomplete="off" spellcheck="false"
        autocapitalize="off" data-key="voice-id" aria-describedby="voice-hint" placeholder="e.g. 20 letters and digits" disabled>
      <button type="button" class="jv-btn jv-btn--small jv-keys__primary" data-key="voice-save" disabled>Save</button>
      <p class="jv-keys__hint" id="voice-hint">ElevenLabs › My Voices › your designed voice › Copy voice ID. Not a secret: it's shown here and kept on <span data-kept>this laptop</span>.</p>
      <p class="jv-keys__line jv-voice__now" role="status"></p>
      <div class="jv-row jv-voice__hear" data-setting="cloud_hearing"><p class="jv-row__text"><b>Cloud hearing</b><span data-hear></span></p>
        <button type="button" class="jv-switch" role="switch" aria-checked="false" aria-label="Cloud hearing"
          data-args='{"value":true}' data-key="cloud-hearing" disabled></button></div>`;
    this.input = this.querySelector("input");
    this.button = this.querySelector("button");
    this.now = this.querySelector(".jv-voice__now");
    this.button.addEventListener("click", () => this.save());
    this.input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); this.save(); } });
    this.load().finally(() => { this.hearSwitch.disabled = this.input.disabled; });   // usable when the voice field is
    // v0.25.0: who writes down what he says. ElevenLabs (fast on a busy laptop; the sound leaves it) or this laptop.
    this.hearSwitch = this.querySelector("[data-key='cloud-hearing']");
    this.hearSwitch.addEventListener("click", () => bridge.act("set", "cloud_hearing", JSON.parse(this.hearSwitch.dataset.args)));
    this.listen();
  }

  listen() {
    this.stopHear?.();
    this.stopHear = store.subscribe((s, changed) => { if (changed.has("settings")) this.hear(s); });
    this.hear(store.state);
  }

  disconnectedCallback() { this.stopHear?.(); }

  hear(s) {
    const on = s.settings?.cloud_hearing === true;
    this.hearSwitch.setAttribute("aria-checked", String(on));
    this.hearSwitch.dataset.args = JSON.stringify({ value: !on });
    this.querySelector("[data-hear]").textContent = on
      ? "On: ElevenLabs writes down what you say to Jarvis, so the sound of it leaves the laptop. If it can't be reached, the laptop takes over by itself."
      : "Off: what you say is written down on the laptop and never leaves it. Turn it on if he is slow to hear you or drops words; the sound of what you say to him then goes to ElevenLabs. The key needs the Speech to Text permission.";
  }

  async load() {
    try {
      const r = await fetch("/api/settings", { cache: "no-store", headers: { Accept: "application/json" } });
      const body = await r.json().catch(() => ({}));
      readWhere(r);
      this.querySelector("[data-kept]").textContent = keptWords();
      if (!r.ok || r.headers.get("X-Jarvis-Settings") === "example") return this.offline(body.message);
      this.ready(body.voice_id || "");
    } catch { this.offline(); }
  }
  ready(current) {
    this.input.disabled = this.button.disabled = document.documentElement.dataset.size === "phone";
    if (current && !this.input.value) this.input.value = current;
    this.now.textContent = current ? `Jarvis speaks with voice ${current}.` : "No voice yet. Jarvis stays silent until you set one.";
  }
  offline(message) {
    this.input.disabled = this.button.disabled = true;
    this.now.textContent = message || "Jarvis core isn't connected yet. The voice ID goes in once it's running.";
  }
  async save() {
    if (this.button.disabled) return;
    const value = this.input.value.trim();
    if (value && !ID_SHAPE.test(value)) return this.say("That doesn't look like a voice ID (about 20 letters and digits).", "error");
    this.button.disabled = true;
    try {
      const r = await fetch("/api/settings/voice", {
        method: "PUT", cache: "no-store", credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json", ...alsoHeaders() }, body: JSON.stringify({ voice_id: value }),
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) { this.say(body.detail || body.message || "That didn't save. Nothing was changed.", "error"); this.button.disabled = false; return; }
      this.input.value = body.voice_id || "";
      this.ready(body.voice_id || "");
      this.say((body.voice_id ? "Voice saved." : "Voice cleared.") + otherWords(r));
    } catch {
      this.say("Jarvis core isn't answering. Nothing was changed.", "error");
      this.button.disabled = false;
    }
  }
  say(text, kind = "info") {
    store.apply({ v: 2, type: "toast", ts: localIso(store.now()), data: { id: `t-voice-${Date.now()}`, kind, text, ttl_ms: 5000 } });
  }
}
if (!customElements.get("jv-voice-setting")) customElements.define("jv-voice-setting", VoiceSetting);
