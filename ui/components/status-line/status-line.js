// <jv-status-line>: the tiny status text in the corner ("Listening", "Standby · Mic on", "Thinking · Quiet")
// with the mic dot. Listening is always visible (HUB_TRUST §1.9): the dot shows mic on/off by shape, icon and
// word, and one tap mutes.   .orb = orb_state (the state of the orb he can see: main.js shownOrbState)
// .settings = settings   .online = boolean
// The interruption dial is a setting, not a state: it shows only when it isn't the default ("Quiet", "Chatty").
import { css, html, icon, Jv } from "../../core/dom.js";
import { el, registerGallery } from "../../core/scenes.js";

css(import.meta.url);

const STATE = { idle: "Listening", listening: "Hearing you", thinking: "Thinking", speaking: "Speaking", waiting: "Your yes", muted: "Muted", offline: "Offline", standby: "Standby", alert: "Needs you" };
const DIAL = { quiet: "Quiet", balanced: "Balanced", chatty: "Chatty" };

class StatusLine extends Jv {
  static props = ["orb", "settings", "online"];
  render() {
    const o = this.orb || { state: "idle" }, s = this.settings || {};
    const muted = o.state === "muted" || s.muted, offline = o.state === "offline" || this.online === false;
    const word = offline ? STATE.offline : muted ? STATE.muted : STATE[o.state] || STATE.idle;
    const mode = s.game_mode === "on" ? "Game mode" : s.focus ? "Focus" : s.interruption === "balanced" ? "" : DIAL[s.interruption] || "";
    const standby = !offline && !muted && o.state === "standby";  // the sphere is resting, but he can still be heard
    const words = [standby ? "Mic on" : "", mode].filter(Boolean);
    const extra = [s.memory_paused ? "Memory paused" : "", s.off_record ? "Off the record" : ""].filter(Boolean);
    // The mic follows the orb: on (green ring) only while Jarvis can hear; muted shows mic-off; offline shows
    // the notice colours and can't be toggled (there is no hub to tell).
    const mic = offline
      ? html`<button type="button" class="jv-status-line__mic jv-status-line__mic--offline" aria-disabled="true" data-key="mic"
          title="The hub is offline, so the mic is off for now">${icon("mic-off")}<span class="jv-sr">Microphone unavailable while offline</span></button>`
      : html`<button type="button" class="jv-status-line__mic ${muted ? "jv-status-line__mic--off" : ""}" data-act="${muted ? "unmute" : "mute"}" data-target="mic" data-key="mic"
          aria-pressed="${muted ? "true" : "false"}" title="${muted ? "The mic is off. Turn it on" : "The mic is on. Mute it"}">
          ${icon(muted ? "mic-off" : "mic")}<span class="jv-sr">${muted ? "Microphone off. Turn it on" : "Microphone on. Mute"}</span></button>`;
    return html`<div class="jv-status-line" role="group" aria-label="Jarvis status" data-orb="${offline ? "offline" : muted ? "muted" : o.state || "idle"}">
      ${mic}
      <span class="jv-status-line__text"><span class="jv-status-line__state">${word}</span>${words.map((x) => html` · ${x}`)}${extra.map((x) => html` · <span class="jv-status-line__flag">${x}</span>`)}</span>
      ${offline && o.message ? html`<span class="jv-status-line__help">${o.message}</span>` : ""}
    </div>`;
  }
}
StatusLine.define("jv-status-line");

const line = (orb, settings = { interruption: "balanced" }, online = true) => el("jv-status-line", { orb, settings, online });
registerGallery("status-line", [
  { label: "Listening", build: () => line({ state: "idle" }) },
  { label: "Standby, mic on", build: () => line({ state: "standby" }) },
  { label: "Thinking, quiet dial", build: () => line({ state: "thinking" }, { interruption: "quiet" }) },
  { label: "Waiting for your yes", build: () => line({ state: "waiting" }) },
  { label: "Muted", build: () => line({ state: "muted" }, { interruption: "balanced", muted: true }) },
  { label: "Game mode, memory paused", build: () => line({ state: "idle" }, { interruption: "chatty", game_mode: "on", memory_paused: true }) },
  { label: "Offline (says what to do)", wide: true, build: () => line({ state: "offline", message: "Can't reach the hub. It will reconnect on its own." }, { interruption: "balanced" }, false) },
], { about: "Always shows the mic state. One tap mutes. The dial shows only when it isn't Balanced." });
