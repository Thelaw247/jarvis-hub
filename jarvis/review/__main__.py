"""python -m jarvis.review on [days] | off | status"""
import sys
import time

from jarvis import review


def main(argv: list[str]) -> int:
    what = argv[0] if argv else "status"
    if what == "on":
        days = float(argv[1]) if len(argv) > 1 else review.DAYS
        t = review.switch(True, days)
        print(f"Review recording is ON until {time.strftime('%A %d %B, %I:%M %p', time.localtime(t))}.")
        print(f"Everything about each conversation is kept in {review.flag().parent}.")
        print("It stays on this laptop. To stop early: Stop review recording.bat")
    elif what == "off":
        review.switch(False)
        print("Review recording is OFF. What was recorded is still in", review.flag().parent)
    else:
        t = review.until()
        folder = review.flag().parent
        size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else 0
        print((f"Review recording is ON until {time.strftime('%A %d %B, %I:%M %p', time.localtime(t))}." if t
               else "Review recording is OFF."), f"Kept so far: {size / 1_000_000:.1f} MB in {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
