---
id: files
name: Create, move and rename his files
rung: 3
tier: read
speed: fast
voice: loaded
where: Laptop B
reads: the names of files in the folder he points at, only to carry out what he asked
writes: new text files and folders, and where files sit, in Class Content, Desktop, Documents and Downloads (never deletes, never overwrites)
needs: []
input:
  type: object
  properties:
    action: {type: string, enum: [create, folder, move, undo], description: "create: a new text file with the content you write. folder: a new folder. move: move or rename a file or folder. undo: take back your last file change."}
    place: {type: string, enum: [class_content, desktop, documents, downloads], description: "Which of his folders the path is in."}
    path: {type: string, description: "The file or folder inside that place, e.g. 'PHYS 152 - Physics/Assignments & Labs/notes.md' or 'lab3.pdf'. Never a full path or a drive letter."}
    content: {type: string, description: "create only: the text of the file."}
    to_place: {type: string, enum: [class_content, desktop, documents, downloads], description: "move only: the place it goes to (default: the same place)."}
    to_path: {type: string, description: "move only: the folder it goes into, or its new name. Empty means the top of to_place."}
    confirmed: {type: boolean, description: "True only after he said yes to this exact change. Without it nothing changes: you get the change back in words to put to him."}
  required: [action]
---
Create a note or a file, make a folder, and move or rename things in his four folders on the laptop he is at.

When to use: "make a file for my lab notes", "put that formula sheet in a file", "move the lab I just downloaded into
the physics folder", "rename it to Lab 3 report", "make a folder for the project". Every change needs his yes, so it
takes two calls. First call it without confirmed: nothing changes and you get the change in words. Say it to him in
a few words ("Move lab3.pdf from Downloads into Physics, Assignments and Labs?"). On his yes, call it again with the
same arguments and confirmed true. "Undo that" or "put it back": action undo, also after his yes.
When not to use: opening a file or his work (work_on, open_app); deleting (you can't: say so and tell him where it
is); anything outside the four folders; writing over a file that exists (pick a new name or ask).
File kinds you can write: .txt .md .csv .json .tex .html .py .c .cpp .h .ino .m. For a document to read, .md or .txt.
After it runs, say in one short line what changed and where it is now.
Cost and speed: a few milliseconds; about half a second more when he talks from the other laptop.
