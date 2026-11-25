---
id: show_page
name: Pull up pages on screen
rung: 1
tier: read
speed: instant
voice: loaded
task: true
where: Laptop B
reads: nothing (shows pages on the Stage)
writes: nothing (opens a window on his screen)
input:
  type: object
  properties:
    pages:
      type: array
      minItems: 1
      maxItems: 6
      items:
        type: object
        properties:
          url: {type: string, description: "An http(s) link"}
          title: {type: string, description: "A short title for the tab"}
        required: [url, title]
    browser: {type: boolean, description: "Also open them as real tabs in the visible Jarvis browser, for him to use himself"}
  required: [pages]
---
Pull pages up on his screen: one page becomes a web window on the Stage, two to six become a tabs window (like Huw's).

When to use: he says "pull up", "show me", "open", "put it on screen", or the answer is a page he'll want to look at
(the lab manual, a map, the source you just cited, a Canvas page). Voice and screen together: say one line, show the
page.
When not to use: to read a page yourself (web_fetch, canvas_read, browse); to open a file (read_document, or a task);
to get him signed in or to connect an account (a tool that needs it puts its own card up; for a site, sign_in).
Prefer: links from search results, Canvas, or his own words. Set `browser` only when he wants to click around himself.
Cost and speed: instant; the page fills in at web speed and never holds up the answer.
