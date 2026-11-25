---
id: start_task
name: Start a task (call on Claude)
rung: 5
tier: read
speed: task
voice: loaded
task: false
where: Laptop B
reads: "whatever the task needs: his files, Canvas, the web, his skills"
writes: only proposals (calendar, files, email), each read back and run after his yes
needs: [tasks]
input:
  type: object
  properties:
    goal: {type: string, description: "The job and its done condition, in his terms: 'plan my week and propose the calendar blocks'"}
    skills: {type: array, items: {type: string}, description: "Optional: his skills to use, by name (week-planner, homework-finder, class-sync, lecture-pack, study-plan, laundry-timing, calendar-sync, syllabus-reader, paws-schedule, chem142-lab-worksheet, big-picture-tutor, human), or Anthropic's document skills (docx, xlsx, pptx, pdf)"}
  required: [goal]
---
Hand a bigger job to a Claude agent that works in the background with his skills and Jarvis's tools, and reports
back: planning his week, syncing classes, building a study pack, making a document, sorting files, anything with
several steps.

When to use: the request needs several steps or one of his skills ("plan my week", "sync my classes", "make me notes
for lecture 12", "make a study plan for thermo", "write up the lab"), or more time than a spoken reply allows.
When not to use: one quick lookup (use that tool directly); research (research); a single page to read (web_fetch,
browse).
Cost and speed: minutes; capped per task (Controls › Reach). Say "On it" at once. Anything it wants to change comes
back as a proposal for his yes.
