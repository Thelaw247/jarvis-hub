---
id: recall
name: Search memory
rung: 1
tier: read
speed: instant
voice: loaded
where: Laptop B
reads: what De Wet has told Jarvis and what Jarvis has learned, with sources
needs: [memory]
input:
  type: object
  properties:
    query: {type: string, description: "What to look for, in a few words"}
    branch: {type: string, description: "Optional: a part of his life to search first (a course code, a project)"}
  required: [query]
---
Search Jarvis's memory of De Wet's life: facts, decisions, preferences, people, and how things were done before.

When to use: a question about him or his world that the now card doesn't answer ("when did I say…", "what's Riley's
role in the squad", "how did we set up X last time"), before asking him anything you might already know.
When not to use: what's already in the now card; public facts (web_search); course material (canvas_find).
Cost and speed: instant (~50 ms), free. Results carry how sure they are; say "I think" for Likely and Guess.
