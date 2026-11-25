---
id: school
name: His classes, due work and courses
rung: 1
tier: read
speed: fast
voice: loaded
where: Laptop B
reads: his class schedule (PAWS), homework list and syllabi, from the files his study skills keep on this laptop
needs: [classes]
input:
  type: object
  properties:
    about: {type: string, enum: [day, due, course, exams], description: "day: his classes on one day. due: work still to do, soonest first. course: one course (instructor, next class, what's due, assessments and weights, exams). exams: tests in the next weeks."}
    day: {type: string, description: "For day: today, tomorrow, a weekday (friday) or a date like 2026-11-24. Default today."}
    course: {type: string, description: "For course (and to narrow due or exams): the code or a word of the title, like GE 122 or mechanics."}
    days: {type: integer, description: "For due and exams: how many days ahead, 1 to 60. Default 14 for due, 30 for exams."}
  required: [about]
---
His classes with rooms, his due work with how long is left, and each course's syllabus facts, in one answer. It reads
files on this laptop, so it is instant and works offline.

When to use: a class on a day that isn't today ("what do I have Thursday", "when's my chem lab"), what is due
("what's due this week", "what should I work on"), anything about one course ("who teaches GE 122", "how much is the
midterm worth", "when is the MATH 133 final"), and upcoming tests. One call answers the whole question: don't follow
it with calendar or canvas_find for the same thing.
When not to use: today's classes, what's next and what's due soon are already on your now card: answer from there.
His own events and study blocks (calendar). Course files, announcements and hints (canvas_find).
The files are as fresh as his last planner run; every answer says the date it is from. Say that date only if it
matters (the homework list is more than a few days old).
Cost and speed: free, a few milliseconds. Read-only.
