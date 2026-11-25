import hashlib
from urllib.parse import urlparse

from jarvis.tools.base import Result, ToolContext, ToolError

# Sites that sign people in refuse to do it inside another app's window (Google answers 403), so these are shown
# as a card that opens in his own browser. The hub applies the same list (ui/.../web-policy.js NEVER_FRAME).
SIGN_IN_HOSTS = ("accounts.google.com", "login.microsoftonline.com", "login.live.com", "composio.dev",
                 "appleid.apple.com", "auth.openai.com")


def signs_in(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in SIGN_IN_HOSTS)


def _id(url: str) -> str:
    return "p-" + hashlib.sha1(url.encode()).hexdigest()[:10]


async def run(args: dict, ctx: ToolContext) -> Result:
    pages = []
    for p in (args.get("pages") or [])[:6]:
        url = str(p.get("url", "")).strip()
        if urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
            raise ToolError(f"Not a web link: {url!r}. Only http and https pages can be shown.")
        page = {"id": _id(url), "url": url, "title": str(p.get("title") or urlparse(url).netloc)[:120]}
        if signs_in(url):
            page["frame"] = "no"
        pages.append(page)
    if not pages:
        raise ToolError("Give at least one page.")
    window = {"id": "w-web-" + pages[0]["id"][2:], "type": "web", "title": pages[0]["title"] if len(pages) == 1
              else f"{len(pages)} pages", "size": "2x2", "data": {"pages": pages, "active": pages[0]["id"]}}
    if args.get("browser") and ctx.browser is not None:
        for page in pages:
            await ctx.browser.open_visible(page["url"])
    titles = ", ".join(p["title"] for p in pages)
    cards = [p["title"] for p in pages if p.get("frame") == "no"]
    more = (f" {', '.join(cards)} can't be shown inside the hub (sign-in pages refuse it), so it is a card: he "
            "clicks it and it opens in his own browser. Tell him that.") if cards else ""
    return Result(f"On screen: {titles}.{more}", show=("window.push", window))
