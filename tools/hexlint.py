"""Fails if a hex colour (or rgb()/hsl() literal) appears in UI code outside ui/tokens.css.
Run:  python tools/hexlint.py        (exit code 1 and a list of offenders when something is wrong)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {ROOT / "ui" / "tokens.css"}
SKIP_DIRS = {"vendor", "fonts", "icons"}  # icons are standalone files that cannot read CSS tokens
HEX = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\(\s*\d")
ENTITY = re.compile(r"&#x?[0-9a-fA-F]+;")  # HTML entities are not colours
URL_FRAGMENT = re.compile(r"""(?:href|xlink:href|url)\s*[=(]\s*["']?#[\w-]+""")


def offenders(root: Path = ROOT) -> list[str]:
    found = []
    for path in sorted((root / "ui").rglob("*")):
        if path.suffix not in {".css", ".js", ".html", ".svg"} or path in ALLOWED:
            continue
        if SKIP_DIRS & set(path.relative_to(root).parts):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            clean = URL_FRAGMENT.sub("", ENTITY.sub("", line))
            if HEX.search(clean) or FUNC.search(clean):
                found.append(f"{path.relative_to(root)}:{number}: {line.strip()[:100]}")
    return found


def main() -> int:
    bad = offenders()
    for line in bad:
        print(line)
    print(f"hexlint: {len(bad)} colour literal(s) outside ui/tokens.css" if bad else "hexlint: clean")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
