---
id: mark_done
name: Mark coursework as finished
rung: 3
tier: read
speed: instant
voice: loaded
where: Laptop B
reads: his homework list (class files)
writes: done.json beside his homework list (which work he says is finished). Never Canvas, WebAssign or the list itself.
needs: [classes]
input:
  type: object
  properties:
    what: {type: string, description: "The work, as he said it: 'the physics assignment', 'assignment one for physics', 'WeBWorK 9', 'the GE 122 memo'."}
    all: {type: boolean, description: "True when he means every piece that matches ('both physics assignments', 'all of them')."}
    done: {type: boolean, description: "false to put it back on the list ('actually I haven't finished it'). Default true."}
    confirmed: {type: boolean, description: "True when he himself said it is done, submitted or handed in, or said yes when you asked. Never on your own guess."}
  required: [what, confirmed]
---
Take a piece of coursework off his to-do list (and the hub's warnings) because he has finished it.

When to use: "I finished the physics assignment", "that's submitted", "mark assignment one as done", "I handed in the
lab", or when he says a warning on the hub is wrong because the work is done. His saying so is the yes: pass
confirmed true and do it. If you only suspect it is done, ask first ("Shall I mark it as done?").
When not to use: checking what is due (school); submitting anything (you can't, and never claim it was submitted:
this only changes his own list); calendar events.
If more than one piece matches and he didn't say all, it names them: ask which, or pass all true.
After it runs, say one short line ("Marked as done, sir. That clears the warning.").
Cost and speed: instant; the hub redraws at once.
