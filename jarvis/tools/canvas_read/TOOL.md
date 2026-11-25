---
id: canvas_read
name: Open something on Canvas
rung: 1
tier: read
speed: fast
voice: deferred
where: Laptop B
reads: one Canvas item in full (an assignment, page, announcement, module, discussion or file) through his session
needs: [canvas]
input:
  type: object
  properties:
    link: {type: string, description: "The Canvas link or API path from canvas_find, like /courses/123/assignments/456"}
  required: [link]
---
Open one Canvas item in full: an assignment's instructions and due date, a page, an announcement, a module's items,
a discussion, or a file (downloaded, then read like read_document).

When to use: after canvas_find found the right item and you need what it says; when he gives a Canvas link.
When not to use: to look for something (canvas_find first); anything outside Canvas.
Cost and speed: ~0.3–1 s; files take longer to download. GET only: it can't submit, post or change anything.
