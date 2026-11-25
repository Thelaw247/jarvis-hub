---
id: web_search
name: Search the web
rung: 2
tier: read
speed: slow
voice: loaded
where: Cloud
reads: the public web, with sources
server: {type: web_search_20250305, name: web_search, max_uses: 3, user_location: {type: approximate, city: Saskatoon, region: Saskatchewan, country: CA, timezone: America/Regina}}
---
Search the web for current public information, with sources (Anthropic's server tool).

When to use: anything about the world as it is now that might have changed: news, prices, opening hours, weather,
who holds a role, product specs, sports, "what's the latest on…", and facts you aren't sure of.
When not to use: his own things (Canvas → canvas_find, his files → read_document, his day → the now card); timeless
knowledge you already have; a page he named by link (web_fetch is cheaper); anything needing his login (browse).
Cost and speed: about 1.5–3 s and $0.01 a search. One or two searches is usually enough for a spoken answer.
