---
id: open_app
name: Open an application
rung: 3
tier: read
speed: fast
voice: loaded
where: Laptop B
reads: the names of the applications installed on the laptop he is at (its Start Menu)
writes: nothing (it starts the application)
needs: []
input:
  type: object
  properties:
    app: {type: string, description: "The application's name as he said it: 'Spotify', 'Word', 'VS Code', 'Bambu Studio', 'file explorer'."}
  required: [app]
---
Open any application installed on the laptop he is at, by its name.

When to use: "open Spotify", "pull up Word", "launch VS Code", "open the calculator". No need to ask first: opening
an application changes nothing of his.
When not to use: his coursework or a class file (work_on opens the right file); a web page (show_page, or work_on for
an assignment); arranging windows that are open (arrange_windows); closing an application or typing into one (you
can't). It opens applications by name only: never a command, a path or anything with arguments.
If the name isn't found it gives the nearest installed names: pick the one he meant or ask him. If it simply isn't
installed (Netflix, YouTube and the like are often used in the browser), offer to open its website instead.
After it runs, say one short line ("Spotify's open, sir.").
Cost and speed: a few milliseconds; about half a second more when he talks from the other laptop.
