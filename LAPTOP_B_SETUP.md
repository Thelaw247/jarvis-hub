# Setting up Jarvis core on Laptop B

About 30 minutes. Laptop B is the always-on hub: it runs `jarvis-core` as a background service, and both laptops'
hubs show what it knows. Since v0.7.0 the hub app **starts live**: it shows the core, or an honest "offline" screen
if it can't reach it. The made-up demo day is only behind `Jarvis Hub (demo).bat`.

## Before you start (Laptop B)
- Power: never sleep when plugged in.
- Python 3.12+ from python.org (3.13 is already on Laptop B).
- Copy this folder to Laptop B (OneDrive\Documents\JarvisHub).

## 1. Install and start the core
Double-click `setup-core.bat`. It:
- makes Jarvis's own Python at `%LOCALAPPDATA%\JarvisCore\venv` and the data folder `C:\Jarvis` (memory, undo,
  data, browser, logs);
- starts the core in the background and puts a small launcher in your Startup folder, so it starts by itself
  every time you sign in and restarts itself if it stops (`ops\run-core.pyw`; no window, no password);
- waits until the core says it's healthy ("green");
- pairs this laptop's hub with the core and saves the address and token in your account's settings (the token
  is never shown).

Check: http://127.0.0.1:8770/healthz should say `"status": "green"`. Then run `setup.bat` once (it updates the
hub) and open Jarvis Hub: the orb stops saying **Offline**.

Servy (a full Windows service) is optional for later: set `JARVIS_USE_SERVY=1` before running setup-core.bat and
follow ops\README.md §2.

## 2. Reach it from your own devices only (needs Tailscale on both laptops)
In a terminal:
```
tailscale serve --bg --https=443 http://127.0.0.1:8770
```
(Never `tailscale funnel`: that would put it on the internet.) Then add a user environment variable
`JARVIS_CORE_HOSTS=<laptop-b>.<tailnet>.ts.net` for your account, then sign out and back in so the core picks it up.

## 3. Pair the other screens
Laptop B's own hub was paired in step 1. Every other screen needs its own pairing (the core answers only paired
devices). In a terminal opened in this folder:
```
%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe -m jarvis.core --pair laptop-a
%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe -m jarvis.core --pair phone --view-only
```
Each prints a token **once**. Treat it like a password. No restart needed: the core picks new pairings up at once.

## 4. Point each hub at the core
On Laptop A, set two user environment variables (Start → "Edit environment variables for your account"):
- `JARVIS_CORE_URL` = `https://<laptop-b>.<tailnet>.ts.net`
- `JARVIS_CORE_SESSION` = Laptop A's token from step 3

Then close and reopen Jarvis Hub. The orb stops saying **Offline** when it's connected.

## 5. Keys and voice
In the hub: **Controls › Keys**. Paste the Claude, ElevenLabs and Composio keys (and restic, for backups), press
**Check**, then **Make live**. Keys are kept only in Laptop B's Credential Manager; the hub shows the last 4
characters. Paste the ElevenLabs voice ID under **Voice** on the same page and press **Save** (it isn't a secret, so it's shown back).

## 6. Voice
Double-click `setup-voice.bat` once (a few minutes; downloads a 460 MB speech model). It ends by saying one line out
loud. Then run `restart-core.bat`, so the core loads the voice (it does so by itself at every start from then on).

Open **Jarvis Hub** and talk: the hub starts the voice by itself (v0.15.0) and stops it when you close the hub.
Controls > Voice // Sound shows whether this laptop has the voice, with a **Talk here** button when the other one
does, and the Microphone switch. `Talk to Jarvis.bat` still works on its own (a window that prints what it hears,
for debugging). The thinking happens in the core, so the orb and Jarvis's captions show on the hub. The mic is ignored while Jarvis speaks (no echo cancellation yet); with headphones, run it with
`--barge-in`. `Talk to Jarvis (standalone).bat` runs the whole loop in its own window and prints the latency of each
answer (for testing). `Mic test.bat` shows your mic level.

Review recording: **`Start review recording.bat`** updates this laptop and keeps everything about each
conversation for 4 days in `C:\Jarvis\logs\review` (it stays on this laptop; `Stop review recording.bat` ends it early).

After any update: run **`Update Laptop B.bat`** from OneDrive > Documents > JarvisHub (it copies the new code into
your Jarvis folder and restarts the core). If the code is already in place, `restart-core.bat` is enough.

## What works after this
- The core runs, stays up, keeps your keys and rotates them without downtime; both hubs show it live.
- Talking to Jarvis on Laptop B with its own mic (step 6). Not yet: Laptop A's mic (the thin client), and Jarvis filling the screens with your real calendar, homework and messages (his brain and pollers come next).
  Until then the live screens are honestly empty.

Logs: `C:\Jarvis\logs\core.jsonl`. Something wrong? Open /healthz: it says which part isn't well.
