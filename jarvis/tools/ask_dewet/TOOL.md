---
id: ask_dewet
name: Ask De Wet a question
rung: 1
tier: read
speed: instant
voice: "off"
task: true
where: Laptop B
reads: nothing
writes: a question Jarvis asks him out loud at the next good moment
needs: [questions]
input:
  type: object
  properties:
    question: {type: string, description: "One short, casual, closed question with your best guess in it ('Golden week, is that the fitness thing with Charlie?')"}
    options: {type: array, items: {type: string}, description: "Optional likely answers"}
    default: {type: string, description: "What you'll assume if he doesn't answer"}
  required: [question]
---
Ask De Wet one question out loud (at the next breakpoint), in place of AskUserQuestion. The task doesn't wait: it
finishes what it can with the default and says what's waiting on his answer.

When to use: a real unknown that changes what you'd do and isn't in memory, the now card or his files (ASK_OR_ACT:
ask only when being wrong costs more than asking). One question, the one that fills the most gaps, with a guess.
When not to use: anything you can find out (recall, canvas_find, read_document); more than three questions in one
task; permission for a write (writes are proposals, he answers those separately).
Cost and speed: instant.
