"""Windows Jarvis makes himself: a worked solution, a formula sheet, a table, a small interactive thing.

His ask of 2026-11-22: "give jarvis the ability to display his own things on the hub as a window ... give him the
ability to write his own code for that". Jarvis writes the body of a page (HTML, CSS, and script if it helps); the
core keeps it and serves it to the hub, which shows it in a window.

Code written by a model is shown like a stranger's web page, never like part of the hub:
- the page is served with a `sandbox` policy, so it has no origin of its own: it cannot read the hub, its store, his
  session or the core's doors, even though it comes from the same address;
- it can load nothing from anywhere (no network, no outside scripts, images only if written into the page);
- the hub frames it with its strictest frame sandbox (no same-origin, no pop-ups, no leaving the frame).
It gets the hub's own colours and type by having ui/tokens.css written into it, so no colour is named here.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from html import escape
from pathlib import Path

MADE_HOST = "jarvis.made"           # http://jarvis.made/<id>: the hub turns this into its own /api/made/<id>
MAX_BODY = 60_000
KEEP = 60
ID = re.compile(r"^[a-f0-9]{12}$")
CSP = ("sandbox allow-scripts allow-forms; default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
       "img-src data:; font-src data:; base-uri 'none'; form-action 'none'")
HEADERS = {"Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
           "Referrer-Policy": "no-referrer"}
TOKENS = Path(__file__).resolve().parents[2] / "ui" / "tokens.css"
BASE = """
html, body { margin: 0; background: var(--bg-0); color: var(--text); }
body { padding: 16px 20px 24px; font: 15px/1.55 var(--font-ui, system-ui), system-ui, sans-serif; }
h1, h2, h3 { font-family: var(--font-head, inherit), system-ui, sans-serif; font-weight: 600; line-height: 1.25; margin: 1.1em 0 0.4em; }
h1 { font-size: 22px; margin-top: 0; } h2 { font-size: 18px; } h3 { font-size: 15px; }
p, ul, ol { margin: 0.5em 0; } li { margin: 0.2em 0; }
code, pre, kbd { font-family: var(--font-mono, monospace), monospace; font-size: 13px; }
pre { padding: 10px 12px; border: 1px solid var(--line-dim); overflow: auto; }
table { border-collapse: collapse; width: 100%; margin: 0.6em 0; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--line-dim); vertical-align: top; }
th { font-weight: 600; border-bottom-color: var(--line); }
hr { border: 0; border-top: 1px solid var(--line-dim); margin: 1em 0; }
a { color: inherit; }
.muted { opacity: 0.7; } .box { border: 1px solid var(--line-dim); padding: 10px 12px; margin: 0.6em 0; }
button, input, select { font: inherit; color: inherit; background: transparent; border: 1px solid var(--line); padding: 4px 10px; }
"""


def folder(root: Path) -> Path:
    return Path(root) / "data" / "made"


def save(root: Path, title: str, body: str) -> str:
    """Keep one page; returns its id. The oldest go once there are more than KEEP."""
    body = body[:MAX_BODY]
    made = hashlib.sha1(f"{title}\n{body}\n{time.time_ns()}".encode()).hexdigest()[:12]
    where = folder(root)
    where.mkdir(parents=True, exist_ok=True)
    (where / f"{made}.json").write_text(json.dumps({"title": title[:120], "body": body, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}), encoding="utf-8")
    for old in sorted(where.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-KEEP]:
        try:
            old.unlink()
        except OSError:
            pass
    return made


def load(root: Path, made: str) -> dict | None:
    if not ID.match(made or ""):
        return None
    try:
        data = json.loads((folder(root) / f"{made}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("body"), str) else None


def document(entry: dict, theme: str = "night") -> str:
    """The whole page: the hub's tokens and a plain base style, then what Jarvis wrote."""
    try:
        tokens = TOKENS.read_text(encoding="utf-8")
    except OSError:
        tokens = ""
    theme = theme if theme in ("night", "day") else "night"
    return (f'<!doctype html><html lang="en" data-theme="{theme}"><head><meta charset="utf-8">'
            f"<title>{escape(str(entry.get('title') or 'Jarvis'))}</title><style>{tokens}\n{BASE}</style></head>"
            f"<body>{entry['body']}</body></html>")


def url(made: str) -> str:
    return f"http://{MADE_HOST}/{made}"
