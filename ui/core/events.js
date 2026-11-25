// The live event stream (SSE). One stream per window; reconnects on its own. When the stream drops,
// the orb shows "offline" with what to do; when it returns, the state is reloaded so nothing is missed.
import { bridge } from "./bridge.js";
import { store } from "./store.js";

let source = null;
let retry = null;
let wasOffline = false;

export function connect() {
  if (source) return;
  source = new EventSource("/api/events");
  source.onopen = async () => {
    clearTimeout(retry);
    if (wasOffline) {
      wasOffline = false;
      try { store.load(await bridge.loadState()); } catch { /* the next event will catch us up */ }
    }
    store.setUi({ online: true });
  };
  source.onmessage = (message) => {
    let event;
    try { event = JSON.parse(message.data); } catch { return; }
    if (event && (event.v === 2 || event.v === 1) && typeof event.type === "string") store.apply(event);  // contracts v2; v1 envelopes still fold in
  };
  source.onerror = () => {
    // EventSource retries by itself; after 3 s without a connection, say so calmly.
    clearTimeout(retry);
    retry = setTimeout(() => {
      if (source && source.readyState !== EventSource.OPEN) {
        wasOffline = true;
        store.setUi({ online: false });
        store.set({ orb: { state: "offline", message: "Can't reach the hub. It will reconnect on its own." } });
      }
    }, 3000);
  };
}

export function disconnect() { source?.close(); source = null; clearTimeout(retry); }
