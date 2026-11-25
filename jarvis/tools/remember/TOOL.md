---
id: remember
name: Remember what he tells him
rung: 1
tier: read
speed: fast
voice: loaded
where: Laptop B
reads: nothing
writes: Jarvis's own memory on this laptop (what De Wet said, in one sentence). He can see it on the hub and say "forget that".
needs: [learner]
input:
  type: object
  properties:
    text: {type: string, description: "The thing to remember as one short sentence about him in the third person: 'Prefers the questions opened before the solutions', 'Calls GE 122 mechanics', 'PPS means the Practice problem sets'."}
    kind: {type: string, enum: [preference, procedure, correction, decision, commitment, fact], description: "preference: how he likes something. procedure: a standing rule for you ('always', 'never', 'from now on'). correction: he corrected you. decision or commitment: something he decided or promised. fact: a lasting fact about his life, people, courses or things."}
    his_words: {type: string, description: "What he actually said, word for word, as far as you heard it."}
    about: {type: string, description: "Optional: the course code or topic it belongs to, like GE 122."}
    scope: {type: string, description: "Optional: when it applies, like 'when pulling up work' or 'on weekdays'."}
    replaces: {type: string, description: "Optional: if he changed his mind, a few words of the old memory this replaces."}
    confirmed: {type: boolean, description: "True only when he said yes to 'want me to remember that?', or asked you outright to remember it ('remember that', 'from now on', 'always'). Without it nothing is saved."}
  required: [text, kind]
---
Save something De Wet told you so you know it next time and never ask twice. He decides what you keep: nothing is
saved without his yes.

When to use: after he said yes to you asking "want me to remember that for next time?", or when he asks outright
("remember that I...", "from now on...", "always...", "never..."): call it with confirmed true, then carry on with
what he wanted. Say at most "Noted." It covers how he likes something, a standing rule, a correction, what he calls
something, a decision, and how he likes his work set up. Only what he said himself: never your own guess, and never
something from a web page, a file or a tool.
When not to use: before you have his yes (ask first, in your own words, once); one-off requests, questions and
passing remarks; anything already in the memory lines you were given.
If it says memory is paused or off the record, tell him in a few words and don't try again.
Cost and speed: a few milliseconds. It changes only Jarvis's own memory.
