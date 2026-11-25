---
id: work_on
name: Pull up his work
rung: 1
tier: read
speed: fast
voice: loaded
where: Laptop B
reads: his Class Content folder and homework list on this laptop; opens the file he means and puts what's due on the hub
needs: [classes]
input:
  type: object
  properties:
    what: {type: string, description: "What he wants to work on, in his words: 'pps 6', 'GE 122 practice 6', 'the chem lab', 'mechanics', 'math', 'lecture 14 for GE 122'. Keep the course if he named one."}
    also: {type: array, items: {type: string, enum: [claude, lecture_notes, course_page]}, description: "What else to open beside it, the way he likes that kind of work set up (from the Remember lines, or because he just asked): claude = the Claude app, if it isn't open already; lecture_notes = the latest lecture's notes for that course; course_page = the course's own page."}
  required: [what]
---
Pull up a piece of his school work so he can start: it finds the assignment, lab, lecture, test or study plan he
means in his Class Content folder, opens the file on his laptop (the questions, not the solutions), and puts its
deadline and the course on the hub. With only a course ("let's work on mechanics") it picks the next thing due there.

When to use: "pull up PPS 6", "open the chem lab", "let's work on math", "let's do mechanics", "get my GE 122 stuff
up", "open lecture 14". One call does all of it.
When not to use: questions about a class or a deadline with nothing to open (school); files outside his classes
(read_document); a web page (show_page).
After it runs, say in one short line what you opened and when it's due. If it says it couldn't open the file here,
tell him where it is instead.
Work that lives online (a Canvas or WebAssign assignment) opens its own page in his normal browser, where he is
already signed in; Canvas refuses to be shown inside the hub, so the hub gets a card for it and the deadline.
If he asked for something extra beside it, or you added it, ask afterwards whether he wants it set up that way for
similar work next time (and remember it only on his yes).
Cost and speed: free, a few milliseconds. It never changes a file.
