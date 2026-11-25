---
id: canvas_find
name: Search Canvas
rung: 1
tier: read
speed: fast
voice: loaded
where: Laptop B
reads: his USask Canvas (assignments, announcements, modules, pages, files, discussions, syllabus), through his own session
needs: [canvas]
input:
  type: object
  properties:
    query: {type: string, description: "What to look for: words from a title or topic ('lab 5', 'midterm room', 'thermo formula sheet')"}
    course: {type: string, description: "Optional course code or name to search first, like 'GE 122' or 'CHEM 142'"}
    kinds: {type: array, items: {enum: [assignment, announcement, module_item, page, file, discussion, syllabus]}, description: "Optional: only these kinds"}
  required: [query]
---
Search his USask Canvas for something specific and get the matches: course, kind, title, due date, a snippet and the
link, newest and closest first.

When to use: anything that lives on Canvas: "when is lab 5 due", "did my prof post anything about the midterm",
"find the GE 122 formula sheet", "where are the CHEM 142 slides for week 9", "what does the syllabus say about late
work". Search first, then open the best match with canvas_read (or read_document for a file).
When not to use: what's already in the now card (today's due items); his calendar; email from profs (Gmail); the
public web.
Cost and speed: ~0.3–1 s live, instant from the cache for common lookups. Read-only: it can never submit or change
anything on Canvas.
