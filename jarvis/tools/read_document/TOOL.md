---
id: read_document
name: Read a document
rung: 1
tier: read
speed: fast
voice: deferred
where: Laptop B
reads: PDFs, Word, Excel, PowerPoint, text, CSV and images, from his allowed folders and Jarvis's downloads
needs: [documents]
input:
  type: object
  properties:
    path: {type: string, description: "A file path in his allowed folders or Jarvis's downloads (canvas_read and tasks put files there)"}
    pages: {type: string, description: "Optional page range for PDFs and slides, like '3-5' or '7'"}
    question: {type: string, description: "Optional: what you're looking for; long documents then return the pages that match"}
  required: [path]
---
Read a document and get its text as Markdown (tables kept, page numbers marked): PDFs, Word, Excel, PowerPoint, text,
CSV, and images (described by vision).

When to use: he asks what a file says ("what's on page 4 of the lab manual", "summarise this PDF", "what's in the
assignment sheet"), a Canvas file canvas_find found, a file a task downloaded, a spec sheet or datasheet.
When not to use: web pages and online PDFs (web_fetch reads those by link; browse if they need his login); Canvas pages and announcements (canvas_read gives them as text
already); writing or changing a document (that's a task with a proposal).
Prefer: pass `question` for long documents so you get the matching pages, not the whole thing; then `pages` for more.
Cost and speed: ~0.1–1 s for most files; scanned pages are read by vision (~2 s a page).
