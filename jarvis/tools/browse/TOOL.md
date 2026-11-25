---
id: browse
name: Browse the web as him
rung: 5
tier: read
speed: task
voice: deferred
where: Laptop B
reads: any website, including ones he's signed into in the Jarvis browser (USask, Canvas, PAWS, Google, Crowdmark…)
writes: nothing in read mode; in act mode, each form submit or consequential click waits for his yes
needs: [browser, tasks]
input:
  type: object
  properties:
    task: {type: string, description: "What to find or do, with the done condition: 'find the GE 122 lab 5 room on the course site and report it'"}
    start_url: {type: string, description: "Optional https link to start from"}
    mode: {enum: [read, act], description: "read (default): navigate, read, search, click links and tabs. act: may fill forms and press buttons; every submit/send/buy/delete asks him first"}
  required: [task]
---
Use a real browser, signed in as De Wet where he's signed in, to find something or do something on a website,
step by step (Claude's own browser tools: navigate, read the page, find, click, type, tabs).

When to use: the site needs his login and isn't Canvas (PAWS, Crowdmark, USask pages, Google pages), the page needs
clicking or scrolling to show the answer, a search inside a site, comparing a few pages, or anything web_fetch can't
read (JavaScript apps). From the voice brain it runs as a task: say "On it" and Jarvis reports back when it's done.
When not to use: a public page you have the link to (web_fetch: much faster); Canvas (canvas_find/canvas_read: direct
and exact); general questions (web_search); paying, passwords, or submitting anything to Canvas, PAWS or Crowdmark
(never allowed).
Cost and speed: 10 s to 3 min, ~$0.02–0.25 a run (25 steps at most).
