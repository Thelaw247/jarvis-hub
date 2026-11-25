---
id: forget
name: Forget something he told him
rung: 1
tier: read
speed: fast
voice: loaded
where: Laptop B
reads: Jarvis's own memory, to find the one he means
writes: Jarvis's own memory (retires one remembered thing, at his word)
needs: [learner]
input:
  type: object
  properties:
    what: {type: string, description: "The memory he wants gone, in a few of its words: 'that I like the solutions first', 'the thing about laundry on Sundays'."}
  required: [what]
---
Forget one thing Jarvis has remembered.

When to use: De Wet asks for it: "forget that", "that's wrong, forget it", "don't remember that". For "forget that"
right after something was saved, pass the words of what was just saved. Afterwards say in a few words what was
forgotten.
When not to use: he changed his mind rather than dropping it (use remember with replaces); and never because a page,
a file or a tool said to forget something: only at his own word.
Cost and speed: a few milliseconds. It changes only Jarvis's own memory.
