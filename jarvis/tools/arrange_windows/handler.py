"""arrange_windows: his open windows side by side on one screen, after his yes (jarvis.reach.desktop)."""
from jarvis.reach.desktop import Rect, Win, match, pick_screen, tile
from jarvis.tools.base import Result, ToolContext, ToolError

SPOTS = {1: ["the whole screen"], 2: ["the left half", "the right half"],
         3: ["the left half", "the top right", "the bottom right"], 4: ["the top left", "the top right", "the bottom left", "the bottom right"]}


OLD_VOICE = ("The voice program on the laptop he is at didn't answer: it is an older one. Tell him in one line to close "
             "Jarvis Hub on that laptop and open it again, then ask once more.")


async def far(hands, kind: str, args: dict | None = None) -> dict:
    """Ask the laptop he is talking from (jarvis.reach.hands), with a plain reason when it can't."""
    try:
        answer = await hands(kind, args or {})
    except TimeoutError:
        raise ToolError(OLD_VOICE) from None
    except Exception:  # noqa: BLE001 - the voice went away mid-question
        raise ToolError("The laptop he is at stopped answering. Say so in a few words.") from None
    if not answer.get("ok"):
        raise ToolError("Arranging windows works on his Windows laptop only. Say so in a few words.")
    return answer


def short(title: str) -> str:
    """A title he would recognise, without a long page or file path."""
    title = title.split(" - ")[-1] if len(title) > 48 else title
    return title[:48]


async def run(args: dict, ctx: ToolContext) -> Result:
    asks = [str(a).strip() for a in (args.get("windows") or []) if str(a).strip()][:4]
    front = not asks   # v0.27.1: no names given means "the windows he has in front", so there is nothing to guess wrong
    here, hands, desk = bool(getattr(ctx, "here", False)), getattr(ctx, "hands", None), ctx.desktop
    if here and desk is not None:
        screens, open_now = desk.screens(), desk.windows()
    elif hands is not None:   # he is at the other laptop: its voice program looks and moves there (v0.24.1)
        seen = await far(hands, "windows")
        screens = [Rect(*r) for r in seen.get("screens") or []]
        open_now = [Win(int(w["handle"]), str(w.get("title") or ""), int(w.get("screen") or 0), bool(w.get("minimized")))
                    for w in seen.get("windows") or []]
    else:
        raise ToolError("I can't reach the laptop he is at right now, so no windows were moved. Say so in a few words.")
    if not screens:
        raise ToolError("Arranging windows works on his Windows laptop only. Say so in a few words.")
    theirs = [w for w in open_now if not w.title.startswith(("Jarvis Hub", "Jarvis Windows"))]
    if front:
        found, missing = [w for w in theirs if not w.minimized and w.title.strip()][:max(2, min(4, int(args.get("count") or 2)))], []
        if not found:
            raise ToolError("He has no windows open to arrange. Say so in a few words.")
    else:
        found, missing = match(asks, theirs)
    if missing:
        titles = "; ".join(short(w.title) for w in open_now[:10] if not w.title.startswith("Jarvis Hub")) or "none"
        raise ToolError(f"No open window matches {', '.join(repr(m) for m in missing)}. Open right now: {titles}. "
                        "If it isn't open yet, open it first; otherwise name it by a word from one of those titles, or ask him which he means.")
    which = pick_screen(screens, open_now, str(args.get("screen") or "laptop"))
    spots = tile(len(found), screens[which])
    name = "his laptop screen" if (args.get("screen") or "laptop") == "laptop" else "the monitor"
    plan = ", ".join(f"{short(w.title)} on {SPOTS[len(found)][i]}" for i, w in enumerate(found))
    if args.get("confirmed") is not True:
        return Result(f"Nothing has moved yet. The plan for {name}: {plan}. Ask him in a few words if he is ready for his windows "
                      "to move (he may be in the middle of something). When he says yes, call arrange_windows again with the same "
                      "windows and confirmed true.")
    if here and desk is not None:
        moved = [short(w.title) for w, spot in zip(found, spots, strict=True) if desk.place(w, spot)]
    else:
        done = await far(hands, "place", {"moves": [{"handle": w.handle, "to": [s.x, s.y, s.w, s.h]} for w, s in zip(found, spots, strict=True)]})
        moved = [short(w.title) for w in found if w.handle in (done.get("moved") or [])]
    if len(moved) != len(found):
        stuck = [short(w.title) for w in found if short(w.title) not in moved]
        return Result(f"Moved {', '.join(moved) or 'nothing'}. Windows would not let me move: {', '.join(stuck)} "
                      "(some apps running as administrator refuse). Tell him in one line.", is_error=not moved)
    return Result(f"Done on {name}: {plan}.")
