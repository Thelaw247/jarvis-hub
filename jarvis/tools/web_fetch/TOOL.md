---
id: web_fetch
name: Read a web page
rung: 2
tier: read
speed: slow
voice: loaded
where: Cloud
reads: one public page or PDF by its link
server: {type: web_fetch_20250910, name: web_fetch, max_uses: 3, max_content_tokens: 20000}
---
Read the full text of a public web page or online PDF by its link (Anthropic's server tool).

When to use: he gave a link, or a search result looks like it has the answer and you need the whole page.
When not to use: pages behind his login, or that need clicking (browse); Canvas (canvas_read); a link you'd have to
make up (only links he gave or that came from a search or an earlier page can be fetched).
Cost and speed: about 1–3 s; no search fee, only the page's tokens.
