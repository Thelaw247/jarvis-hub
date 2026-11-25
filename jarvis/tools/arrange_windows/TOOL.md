---
id: arrange_windows
name: Arrange his windows on a screen
rung: 3
tier: read
speed: fast
voice: loaded
where: Laptop B
reads: the titles of the windows open on this laptop, only when he asks for an arrangement
writes: where his open windows sit on the screen (moves and sizes them; never closes one or types into one)
needs: [desktop]
input:
  type: object
  properties:
    windows: {type: array, items: {type: string}, description: "Leave this out (with count) to arrange the windows he has in front right now: use that for 'arrange my windows', 'put them side by side', 'so I can see everything' when he names none. Or one to four windows, left to right, each named by a word or two from its title: 'canvas', 'claude', 'practice 6', 'word'. Two share the screen side by side; three are one tall on the left and two stacked on the right; four are quarters."}
    count: {type: integer, minimum: 2, maximum: 4, description: "With no windows named: how many of his front windows to arrange (default 2)."}
    screen: {type: string, enum: [laptop, monitor], description: "laptop (default): his laptop's own screen, the one the hub is not on. monitor: the screen the hub is on."}
    confirmed: {type: boolean, description: "True only after he said yes to you asking if he is ready for his windows to move. Without it nothing moves: you get the plan back to put to him."}
  required: []
---
Lay his open windows out on one screen so everything for the task is in view: the assignment's page on one half and
Claude on the other, or the notes, the questions and a document together.

When to use: he asks you to arrange, tile or put windows side by side ("put Canvas and Claude side by side"), or
after you pulled up his work and more than one thing is open: offer it ("Shall I put them side by side on your
laptop screen?"). Moving a window under his hands is rude, so it takes two calls. First call it without confirmed:
nothing moves and you get the plan. Ask him in a few words if he is ready ("Ready for me to move them?"). When he
says yes, call it again with confirmed true.
When not to use: opening something that isn't open yet (work_on, show_page: open it first, then arrange); closing or
minimising windows (you can't). Never move anything without his yes in this conversation.
If a window isn't found it tells you which ones are open; pick from those or ask him which he means.
Cost and speed: a few milliseconds. Works on the laptop he is talking from: when that isn't the one Jarvis runs on, the voice program there looks and moves (about half a second more).
