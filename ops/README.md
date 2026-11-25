# Running Jarvis core on Laptop B

The core is `python -m jarvis.core` (FastAPI on `127.0.0.1:8770`). It runs from the code, like the hub
(Smart App Control blocks unsigned installers), as **your own Windows account** so it can reach Credential
Manager (C26). Everything it writes at runtime goes in the Jarvis folder (`C:\Jarvis`, or `JARVIS_ROOT`):
`memory\`, `undo\`, `data\`, `browser\`, `logs\`. None of these ever go in git.

## 1. Set up (once, and again to repair or update)
Double-click `setup-core.bat` in the repo. It makes a private Python in `%LOCALAPPDATA%\JarvisCore\venv`,
installs the core's packages (fastapi, uvicorn, httpx, keyring, sqlite-vec), makes the Jarvis folder and its runtime
folders, and writes `%LOCALAPPDATA%\JarvisCore\jarvis-core.servy.json`: `ops\servy\jarvis-core.json` with this
machine's paths filled in.

Try it by hand first: `%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe -m jarvis.core`, then open
http://127.0.0.1:8770/healthz. `"status": "green"` means every part is up; amber means something is starting
or degraded; red (HTTP 503) means something is down. The `components` say which.

## 2. Run it as a service with Servy (optional)
By default `setup-core.bat` doesn't need Servy: it starts the core with `ops\run-core.pyw` (no window) and adds a
launcher to your Startup folder, so the core starts at every sign-in and restarts if it stops. For a real Windows
service instead, set `JARVIS_USE_SERVY=1`, run `setup-core.bat` again, delete `Jarvis core.cmd` from the Startup
folder, and:

1. Servy Manager → **Import** → `%LOCALAPPDATA%\JarvisCore\jarvis-core.servy.json`
   (or `servy-cli import --config=json --path=...`).
2. **Log on as your own account** (Servy never imports an account or password, so set it in the service's
   settings after importing). Not Local System: that account can't read your Credential Manager.
3. What the config already sets: **delayed automatic start** (StartupType 5), **restart the process** when it
   crashes or stops (RecoveryAction 2, unlimited tries), stdout/stderr in `C:\Jarvis\logs\` with rotation, and
   after every start a check, `python -m jarvis.core --check --wait 120`, that waits for a green `/healthz`
   (the M0.1 exit: reboot → green within 2 minutes, nobody touching it).
4. Reboot and check http://127.0.0.1:8770/healthz.

## 3. Reach it from the tailnet: `tailscale serve`
The core only listens on 127.0.0.1. Tailscale puts HTTPS in front of it, tailnet-only, with its own certificate:

```
tailscale serve --bg --https=443 http://127.0.0.1:8770
tailscale serve status
```
- The address is `https://<laptop-b>.<tailnet>.ts.net/`. Tell the core that name, or it refuses the requests:
  add `JARVIS_CORE_HOSTS=<laptop-b>.<tailnet>.ts.net` to the service's environment variables (comma-separated).
- If the hub's pages are served from another address (Laptop A's hub), list that page's origin in
  `JARVIS_CORE_ORIGINS` (e.g. `https://<laptop-a>.<tailnet>.ts.net`) so its actions are accepted.
- `--bg` keeps the setting across reboots. `tailscale serve reset` turns it off.
- **Never** `tailscale funnel`: that would put Jarvis on the public internet.
- Measure the latency from Laptop A once (`curl -w "%{time_total}" https://.../healthz`): a direct tailnet link
  is a few ms; a relayed one (DERP) is much slower and worth fixing (C30).

## 4. Pair the hub devices (for the Keys page)
Guarded routes (`/api/keys`) need a hub session. On Laptop B:
```
%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe -m jarvis.core --pair laptop-a
%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe -m jarvis.core --pair phone --view-only
```
Each prints a token **once**. The core keeps only a hash of it (`data\hub_sessions.json`). `--unpair <device>`
forgets one. The phone is view-only.

On the device that runs the hub (Laptop A), set two environment variables for your account and restart the hub:
`JARVIS_CORE_URL=https://<laptop-b>.<tailnet>.ts.net` and `JARVIS_CORE_SESSION=<the token>`. Controls › Keys then
talks to the core (the hub passes `/api/keys` straight through with `X-Jarvis-Session`); without them it shows
example rows and accepts nothing. Keys are pasted only on that page and are stored only in Credential Manager
on Laptop B.

## Settings (environment variables)
| Variable | Default | What |
|---|---|---|
| `JARVIS_ROOT` | `C:\Jarvis` | The Jarvis folder (one setting) |
| `JARVIS_CORE_PORT` | `8770` | Local port |
| `JARVIS_CORE_HOSTS` | (none) | Extra host names to answer to (the tailnet name) |
| `JARVIS_CORE_ORIGINS` | (none) | Pages allowed to send actions besides the core's own |
| `JARVIS_CORE_KEYSTORE` | `keyring` | `memory` only for tests: keys would be gone at restart |

## Logs
`C:\Jarvis\logs\core.jsonl`: one JSON object per line with ids, timings and counts only (C21). Nothing you say,
no message text and no keys are ever logged; errors show their type, not their message.
