---
id: sign_in
name: Ask him to sign in to a site
rung: 1
tier: read
speed: fast
voice: loaded
where: Laptop B
reads: nothing
writes: nothing (opens the Jarvis browser's sign-in page in a window he can see)
needs: [browser]
input:
  type: object
  properties:
    site: {type: string, description: "The site's sign-in link, or a known name: canvas, paws, google, crowdmark, github"}
  required: [site]
---
Open a site's sign-in page in a window of its own on Laptop B (the Jarvis browser, nothing but the page), so De Wet
can sign in himself: password, saved passwords and MFA are his, and Jarvis isn't attached to that window. When he
closes it, Jarvis is told and carries on with what he asked.

When to use: a tool said a site needs him to sign in (call this in the same turn, don't ask first), or he says
"log into Canvas for me" / "connect my Google".
When not to use: to sign in on his behalf (never type passwords); when a tool already works.
Cost and speed: instant. Say one line, like "Canvas's sign-in is open; close the window when you're done."
