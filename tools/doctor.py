"""One page that says why Jarvis's tools do or don't work on this laptop.

    python tools/doctor.py            # writes the report and prints where it is

His report of 2026-11-22: on Laptop B "it is as if nothing lands": no tool had ever scanned Canvas or read his
calendar, and Claude could not see that laptop's logs. This gathers, in one file: the version, what is installed,
whether the core answers, every tool's state as the core itself reports it (connected, needs sign-in, off), which keys
are saved (names only, never a value), whether his class files are found, and the last tool runs and warnings from the
core's log (ids and timings only, C21).

The report goes to OneDrive > Documents > JarvisHub > reports (so it reaches the other laptop by itself), else next
to the Jarvis folder. It reads; it changes nothing. Standard library only, so it runs before anything is installed.
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
import time
import urllib.request
from pathlib import Path

MODULES = {"fastapi": "core", "uvicorn": "core", "httpx": "core, calendar", "keyring": "keys", "anthropic": "talking, tools",
           "playwright": "browser, Canvas", "claude_agent_sdk": "tasks, research", "fitz": "documents", "yaml": "tools folder",
           "sherpa_onnx": "hearing", "pipecat": "voice", "websockets": "voice", "sounddevice": "voice window"}
SECRET_WORDS = ("value", "secret", "token", "key_value", "password", "session")
LOG_TAIL_BYTES = 600_000
SHOWN = 80


def fetch(base: str, path: str, session: str, timeout: float = 4.0):
    """GET one of the core's own pages. (status, parsed json or text). Never raises."""
    try:
        req = urllib.request.Request(base.rstrip("/") + path, headers={"X-Jarvis-Session": session} if session else {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - the core's own address
            body = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(body)
            except ValueError:
                return resp.status, body[:200]
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {str(exc)[:120]}"


def keys_lines(data) -> list[str]:
    """Which keys are saved: names and yes/no only. Anything that could be a value is never printed."""
    rows = next((v for v in data.values() if isinstance(v, list)), []) if isinstance(data, dict) else data
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("id") or row.get("provider") or "?"
        facts = [f"{k}={v}" for k, v in row.items()
                 if isinstance(v, bool) or (k in ("status", "state") and isinstance(v, str) and len(v) < 24)
                 if not any(w in k.lower() for w in SECRET_WORDS)]
        out.append(f"  {name}: {', '.join(facts) or 'listed'}")
    return out or ["  (the core listed no keys)"]


def log_lines(path: Path) -> list[str]:
    """The last tool runs, failures and warnings from core.jsonl: time, event, tool, error, ms."""
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - LOG_TAIL_BYTES))
            raw = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return [f"  (no log at {path})"]
    out = []
    for line in raw:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        event, level = str(r.get("event") or r.get("msg") or ""), str(r.get("level") or "").upper()
        if not (event.startswith(("tool.", "feed.", "voice.failed", "core.started", "memory.not")) or level in ("WARNING", "ERROR", "CRITICAL")):
            continue
        bits = [str(r.get("ts") or r.get("time") or "")[:19], level[:4], event]
        bits += [f"{k}={r[k]}" for k in ("tool", "error", "ms", "status", "step", "version", "reason") if r.get(k) not in (None, "")]
        out.append("  " + " ".join(b for b in bits if b))
    return out[-SHOWN:] or ["  (no tool runs or warnings in the recent log)"]


def report(code: Path, root: Path, env: dict, *, get=fetch, now: float | None = None, wait: int = 0) -> str:
    base = (env.get("JARVIS_CORE_URL") or "http://127.0.0.1:8770").strip()
    session = (env.get("JARVIS_CORE_SESSION") or "").strip()
    local = "http://127.0.0.1:8770"
    lines = [f"Jarvis report · {time.strftime('%A %d %B %Y, %I:%M %p', time.localtime(now))}",
             f"Laptop: {env.get('COMPUTERNAME') or platform.node()} · Python {platform.python_version()} · {sys.executable}",
             f"Jarvis folder: {code} · version {(code / 'VERSION').read_text().strip() if (code / 'VERSION').is_file() else '?'}",
             f"Data folder: {root} ({'there' if root.is_dir() else 'MISSING'})",
             f"This laptop's hub talks to: {base.split('//')[-1].split('/')[0]} · paired: {'yes' if session else 'NO (no session saved)'}", ""]
    lines.append("Installed:")
    for mod, what in MODULES.items():
        lines.append(f"  {'ok     ' if importlib.util.find_spec(mod) is not None else 'MISSING'} {mod} ({what})")
    status, health = get(local, "/healthz", "")
    for _ in range(wait):   # just restarted? Laptop B needs up to half a minute before it answers
        if status:
            break
        time.sleep(3)
        status, health = get(local, "/healthz", "")
    lines += ["", f"Core on this laptop (127.0.0.1:8770): {'answers' if status else 'NOT ANSWERING'}"
              + (f" · {json.dumps(health)[:300]}" if status else f" · {health}")]
    if status:
        s_status, state = get(local, "/api/state", session)
        if s_status == 200 and isinstance(state, dict):
            lines += ["", "Tools, as the core sees them:"]
            for row in (state.get("reach") or {}).get("tools") or (state.get("reach") or {}).get("rows") or []:
                lines.append(f"  {str(row.get('status')):<14} {row.get('id')} · last used {row.get('last_used') or 'never'}" + (" · switched off" if row.get("on") is False else ""))
            if not state.get("reach"):
                lines.append("  (the core sent no tool list: the tools did not load)")
            lines += ["", "Sources (Under the hood):"]
            lines += [f"  {str(c.get('status')):<6} {c.get('name')}" + (f" · {c['last_sync']}" if c.get("last_sync") else "") + (f" · {c['note']}" if c.get("note") else "")
                      for c in (state.get("metrics") or {}).get("connectors") or []] or ["  (none reported: the core is older than v0.18.0)"]
            lines += ["", f"Hub state: {len(state.get('branches') or [])} branches, {len((state.get('day') or {}).get('items') or [])} things today, "
                          f"{len(state.get('windows') or [])} windows up"]
        else:
            lines += ["", f"The core would not show its state (status {s_status}): {str(state)[:160]}",
                      "  If that says 401 or 403, this laptop's pairing is wrong: run setup-core.bat again."]
        k_status, keys = get(local, "/api/keys", session)
        lines += ["", "Keys saved (names only):"] + (keys_lines(keys) if k_status == 200 else [f"  could not ask (status {k_status}): {str(keys)[:120]}"])
    use = root / "data" / "tool_use.json"
    lines += ["", "Tool history kept on this laptop:"]
    try:
        for tid, rec in sorted(json.loads(use.read_text(encoding="utf-8")).items()):
            lines.append(f"  {tid}: ran {rec.get('runs', 0)}, failed {rec.get('fails', 0)}, last {rec.get('last_used') or 'never'}"
                         + (f" · last problem: {rec['last_error']}" if rec.get("last_error") else ""))
    except (OSError, ValueError, AttributeError):
        lines.append("  (none yet: no tool has been called since v0.19.1, or the core is older)")
    planner = next((p for p in (Path(env["JARVIS_CLASS_CONTENT"]) if env.get("JARVIS_CLASS_CONTENT") else None,
                                Path(env.get("OneDrive") or Path.home() / "OneDrive") / "Desktop" / "Class Content",
                                Path.home() / "Desktop" / "Class Content") if p and (p / "_Week Planner").is_dir()), None)
    lines += ["", f"Class Content: {planner or 'NOT FOUND on this laptop (so no classes, due work or work_on here)'}"]
    lines += ["", "Recent tool runs and warnings (core log):"] + log_lines(root / "logs" / "core.jsonl")
    return "\n".join(lines) + "\n"


def where_to_write(code: Path, env: dict) -> Path:
    hub = Path(env.get("OneDrive") or Path.home() / "OneDrive") / "Documents" / "JarvisHub"
    folder = (hub if hub.is_dir() else code.parent) / "reports"
    name = "".join(c if c.isalnum() or c in "-_" else "-" for c in (env.get("COMPUTERNAME") or platform.node() or "laptop")).lower()
    return folder / f"jarvis-report-{name}.txt"


def main(argv: list[str] | None = None, env: dict | None = None) -> int:
    env = dict(os.environ if env is None else env)
    code = Path(__file__).resolve().parent.parent
    root = Path(env.get("JARVIS_ROOT") or r"C:\Jarvis")
    text = report(code, root, env, wait=15)
    out = where_to_write(code, env)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(text)
        print(f"Saved to {out}")
        print("Claude can read it from there (it syncs through OneDrive). Nothing in it is a key or a password.")
    except OSError as exc:
        print(text)
        print(f"Could not save the report ({exc}). Copy the text above to Claude instead.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
