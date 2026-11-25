# Setting up Laptop A

Laptop A shows the hub and talks to Jarvis; the thinking happens in Jarvis core on Laptop B. About 10 minutes.

## Before you start
- Tailscale on **both** laptops, signed in with the same account (https://tailscale.com/download).
- Python: the setup uses 3.13 (or 3.12) and gets 3.13 itself if it can; newer versions (3.14, 3.15) don't work yet.
- This folder in OneDrive\Documents\JarvisHub, so it syncs to both laptops.

## 1. On Laptop B
Double-click **`Connect Laptop A (run on Laptop B).bat`** (in your Jarvis folder or OneDrive\Documents\JarvisHub). It shares the core on your
tailnet only (`tailscale serve`, never `funnel`), tells the core its tailnet name and restarts it, pairs `laptop-a`,
and leaves the pairing in `laptop-a.pairing` for OneDrive to carry to Laptop A. The first time, Tailscale may print a
link to allow HTTPS on your tailnet: open it, allow it, and run the file again.

## 2. On Laptop A
Double-click **`Set up Laptop A.bat`**. It installs the hub, the voice window, "hey Jarvis" and the Right Ctrl talk
key, saves the pairing in your settings (and deletes `laptop-a.pairing`), checks that Jarvis core answers, then lets
you try "hey Jarvis" with a live score. One desktop shortcut: **Jarvis Hub**. It runs the voice too (v0.15.0), so there's nothing else to open.

Only one laptop has the voice at a time. The hub you opened first keeps it; the other shows **Talk here** in
Controls > Voice // Sound, and picks the voice up by itself when the first one closes.
