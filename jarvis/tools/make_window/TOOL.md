---
id: make_window
name: Put something of his own on the hub
rung: 1
tier: read
speed: fast
voice: loaded
where: Laptop B
reads: nothing
writes: a window on the hub with a page Jarvis wrote himself (kept on this laptop; it can reach nothing outside itself)
input:
  type: object
  properties:
    title: {type: string, description: "The window's title, a few words: 'Period of a spring', 'Circuits formulas', 'This week at a glance'."}
    html: {type: string, description: "The body of the page, written by you: plain HTML (h2, p, ul, ol, table, pre, code), your own <style> if you need layout, and <script> only when it should do something (a calculator, a checklist that ticks, a step-through). No <html>, <head> or <body> tags. Keep it to what fits a window: aim under 1,500 characters unless he asked for something big."}
    size: {type: string, enum: [2x1, 2x2, 3x2], description: "How big the window is. 2x2 (default) for most things; 2x1 for a short card; 3x2 for a wide table or a worked solution."}
  required: [title, html]
---
Show him something you wrote yourself, as a window on the hub: the steps of a worked problem, a formula sheet for
what he's doing, a comparison table, a checklist, his week at a glance, a small calculator.

When to use: something is easier to look at than to listen to (steps, formulas, a table, more than three items), or
he asks you to show, lay out, write down or put something on screen. Prefer it over opening a web page when you
already know the content: it is faster and it is exactly what he needs. Say one short line as you put it up; don't
read the window out.
When not to use: a real page he needs to act on (his assignment on Canvas: work_on; a site: show_page); a one-line
answer (just say it).
The page already has the hub's colours and type: use plain tags and they look right. For layout use your own
classes with the page's variables (var(--text), var(--line), var(--line-dim), var(--bg-0)); don't name colours.
Nothing loads from outside: no links to scripts, fonts or images, and it cannot reach the internet or his files.
Formulas: write them in plain text or HTML (x<sup>2</sup>, &radic;, &pi;), not LaTeX.
Cost and speed: showing it is instant, but writing it takes you a few seconds, so keep it tight.
