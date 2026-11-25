---
id: calendar
name: Read his calendar
rung: 1
tier: read
speed: fast
voice: loaded
where: Cloud
reads: his Google Calendar (events, times, rooms), through Composio
needs: [calendar]
input:
  type: object
  properties:
    day: {type: string, description: "The first day to look at: today, tomorrow, a weekday (friday), or a date like 2026-11-20. Default today."}
    days: {type: integer, description: "How many days from there, 1 to 31. Default 1; use 7 for 'this week'."}
    query: {type: string, description: "Optional words to match in the event (a course code, 'lab', 'dentist')"}
---
Read his Google Calendar: every event in the days you ask for, in order, with its time and room. His classes, labs,
study blocks, exams and laundry slots are all in there (his planner books them).

When to use: anything about his time: "what's my first class tomorrow", "what do I have today", "when is my chem
lab", "am I free Friday afternoon", "what room is GE 122 in", "what's next". The first event of a day is the first
line for that day. Always call this for schedule questions, even when the now card shows today, unless the answer is
plainly on the now card.
When not to use: due dates and course material (Canvas: canvas_find); changing the calendar (you can't yet: say so).
If his calendar isn't connected yet, this tool puts a Connect Google Calendar card on his screen by itself and tells
you when it's connected: say the one line it gives you, and don't open any page yourself.
Cost and speed: about half a second. Read-only: it can never add, move or delete an event.
