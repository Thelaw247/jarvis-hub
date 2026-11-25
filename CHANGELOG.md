# Changelog

All notable changes to Jarvis. Each release is compiled from the fragments in `changes/` by the
`jarvis-release` skill. Versions follow `0.MINOR.PATCH` until the hub goes live (see docs/hub-build-plan.md §11).

## 0.27.3 - Speaks first (2026-11-23)
### Fixed
- **About three seconds of silence before every answer.** The model was quietly thinking before each reply (around 300 to 430 hidden tokens for a two-sentence answer), because the newer model does that unless told not to. That was the "2.5 seconds for his first word" in the friction numbers, and it also cut some replies short. The quick brain now answers without that step.

## 0.27.2 - Stands by his answer (2026-11-23)
### Fixed
- **Jarvis said the same thing five times.** After answering "what class do I have first tomorrow", he re-read the timetable and repeated it on each of the next four turns, apologising for not having checked. He only remembered the words of his answer, not that he had looked it up, so a moment later his own answer looked like a guess to him. He now keeps what he checked together with what he said, so he can stand by it.
- **A stray "okay", "sure" or half-heard few words no longer re-runs the last request.** He answers in a couple of words or asks what you'd like.

## 0.27.1 - Done means done (2026-11-23)
### Added
- **Tell Jarvis when work is finished.** "I finished the physics assignment" or "that's submitted" takes it off your list and clears the hub's warning straight away. It only changes your own list: nothing is submitted or changed on Canvas or WebAssign, and "actually I haven't finished it" puts it back.

### Changed
- **"Arrange my windows" no longer needs names.** With no windows named he takes the ones you have in front. On Laptop A, 12 of his 18 tries had failed because he guessed a window's name wrong first.

## 0.27.0 - Lets you finish (2026-11-22)
### Changed
- **Jarvis waits according to how your words end.** A pause after "and", "because", "the" or "um" is you thinking, so he waits up to 1.6 seconds for the rest. After two words he waits a little over half a second. After a clear ending he waits a quarter of a second, and a short answer or command ("yes", "stop") still lands at once. He keeps preparing his answer during the wait, so a clear question is answered as fast as before.
- **He gives way sooner when he started too early.** If you carry on in the first second and a half of his reply, half a second of your voice stops him (it was a full second).
- Every pause is now recorded as numbers (how long he waited, whether you carried on). That is what the learning step will train on.

### Fixed
- **"Open Netflix" found nothing.** Microsoft Store apps have no shortcut file; he now also asks Windows for its own list of your apps.

## 0.26.0 - Files and applications (2026-11-22)
### Added
- **Jarvis can open any application installed on your laptop**, by its name: "open Spotify", "pull up Word", "launch VS Code". He matches the name to what is installed; he never runs a command or a path.
- **Jarvis can create, move and rename your files**, in Class Content, Desktop, Documents and Downloads: "make a file for my lab notes", "move the lab I just downloaded into the physics folder", "rename it to Lab 3 report". He says the change and waits for your yes every time. He never deletes and never overwrites, he can't write a file Windows would run, and "undo that" puts things back.
- Both work on the laptop you are talking from, also when Jarvis himself runs on the other one.

## 0.25.0 - Cloud hearing (2026-11-22)
### Added
- **Cloud hearing, a switch in Controls > Keys beside the voice ID.** On, ElevenLabs' live speech-to-text writes down what you say instead of the laptop's own processor, which fell up to 44 seconds behind on long speech. The sound of what you say to Jarvis then leaves the laptop; off (the default) it never does. If ElevenLabs can't be reached or refuses the key (it needs the Speech to Text permission), the laptop hears that same turn itself and takes over for a minute, so no turn is lost to the switch. Changes from your next sentence, no restart.

## 0.24.2 - Says why (2026-11-22)
### Fixed
- **"Not connected" now says why.** Controls > Voice on this laptop showed only "Not connected" when the voice could not start. On Laptop A the real reason was a missing ElevenLabs voice ID on its own Jarvis; the page now shows the voice program's own sentence ("No voice yet: paste the ElevenLabs voice ID in Controls > Keys > Voice").

## 0.24.1 - Where he sits (2026-11-22)
### Added
- **Jarvis can act on the laptop you are talking from.** When you talk from one laptop and Jarvis runs on the other, the voice program on your laptop now does the hands-on part: it opens the assignment page, the class file or Claude there, and lines your windows up there. Until now he answered "I can only move windows on the laptop I run on" and opened nothing. It does only those fixed things: no programs, nothing outside Class Content, and windows still move only after your yes.

### Changed
- **Hub windows stay up.** A window no longer closes by itself after 60 seconds, so the sheet you are working from stays while you work and while Jarvis talks. It goes when you close it, clear the view, or a sixth window takes its place.

## 0.24.0 - Both laptops (2026-11-22)
### Added
- **Update the key and voice ID on both laptops from one Keys page.** On a laptop that runs its own Jarvis and still knows the other one, Controls > Keys shows "Also update <laptop>". Ticked, a new key (add, make live, remove old) and the voice ID go to the other laptop's Jarvis too, and the message says how that went: same there, not taken, or not answering. The hub never reads, keeps or logs the key, it only crosses over the tailnet's https, and a key this laptop refused is not sent on. Removing a service is done on each laptop by itself.
- **The Keys page says where the keys are.** "This laptop", or the other laptop's name with "one change here covers both laptops" when this laptop is using the other one's Jarvis. It no longer says "Laptop B" everywhere.

### Fixed
- **A clean "pull up ..." did nothing.** The fast router took any sentence starting with open / pull up / show me and turned it into an "open" command that nothing ran: no reply, no window (twice on 22 Nov). Those sentences now go to the talker, whose tools open the work.
- **A logging crash on spoken commands** ("Attempt to overwrite 'name' in LogRecord").

## 0.23.0 - His own windows (2026-11-22)
### Added
- **Jarvis can put his own windows on the hub.** He writes a small page himself (the steps of a worked problem, a formula sheet, a table, a checklist, a little calculator) and it appears as a window, in the hub's own look. He is told to use it when something is easier to look at than to listen to, and when he already knows the content it is quicker than opening a web page.
- **His code is kept in a box.** A page he writes is shown like a stranger's web page, never like part of the hub: it has no access to the hub, your session or Jarvis's own doors, and it cannot load anything from the internet or reach your files.

## 0.22.1 - Canvas sign-in (2026-11-22)
### Fixed
- **Jarvis kept saying Canvas wasn't signed in when it was.** Once Canvas had asked for a sign-in, a flag was raised that stopped every later Canvas call before it ran, so he could never find out you had signed in (until the next restart). Now he lowers the flag and asks Canvas again each time.
- **The sign-in didn't last** (your catch). He was opening Canvas's login address, which starts a new sign-in every time. He now opens Canvas's normal front page: it shows your dashboard if the sign-in is still good and only asks when it isn't. Same for Crowdmark.

## 0.22.0 - Side by side (2026-11-22)
### Added
- **Jarvis can lay out your laptop screen.** "Put Canvas and Claude side by side": he finds the windows by a word from their titles and places them on your laptop's own screen (the one the hub is not on): two side by side, three as one tall and two stacked, four as quarters. After pulling up work with more than one thing open, he offers it.
- **He asks before anything moves.** The first step only makes the plan; he asks "Ready for me to move them?", and moves them when you say yes. He never closes a window, types into one or reads what is inside; he reads the window titles only when you ask for an arrangement.

## 0.21.0 - More human (2026-11-22)
### Changed
- **He talks more like a person.** New rules for how he speaks: think about what you need first and lead with that; courses by the name you use ("physics", "circuits"), work as people say it ("assignment one for physics"), places by the building's name with the room number only when you ask, times as people say them. He is also given what the building and course codes mean in plain words.
- **He asks before he remembers** (your rule). Nothing goes into memory without your yes: he asks "want me to remember that for next time?", and saves only when you agree. Asking him outright ("remember that...", "from now on...") still counts as your yes. What the background pass notices is now offered to you once, never saved on its own.

### Added
- **The icons under the hub do something.** Today holds what is left of your day and Homework what is due, each one click from its window. Before, the live icons opened onto "Nothing here right now".
- **"Pull up the physics assignment" brings everything you need.** The assignment's own page opens in your normal browser (Canvas refuses to be shown inside the hub, so the hub gets a card and the deadline), and he can open the latest lecture notes, the course page and Claude beside it (Claude only if it isn't open already). When you add something to the setup he asks whether you want it that way for similar work next time.

## 0.20.1 - His first conversation with it (2026-11-22)
### Fixed
From his first conversation with the learning loop (Laptop B, 6:31 pm), where remembering worked and three other things did not:
- **Calendar: the cause is confirmed and fixed.** Composio's own words: "User ID is required with connected account". Jarvis now names the user on the first call, so there is no refused first try (about a second sooner per lookup).
- **Canvas sign-in "didn't take", four times.** Canvas's session cookie is thrown away when Chrome's last window closes. The sign-in window and Jarvis's own browser are now started so the session carries on.
- **"Pull up physics 1" found nothing.** PHYS 152 has no syllabus on file, so it wasn't a course Jarvis knew. Courses now also come from the PAWS schedule and the Class Content folders, and work that lives online (WebAssign, a Canvas quiz) opens its own page in the normal browser.

## 0.20.0 - Learns and asks (2026-11-22)
### Added
- **Jarvis learns what you tell him.** When you say how you like something, give him a standing rule, correct him, tell him what you call something or decide something, he saves it in one sentence (`remember`), and a quiet pass after each answer picks up the durable things he missed. Only what you said is saved, never his own reply or a guess. Each save shows on the hub ("Remembered: ...").
- **He uses it.** Your preferences, rules and corrections ride in every prompt, and before each answer he looks up what memory holds about what you just said (80 ms at most, usually far less; he answers without it rather than wait).
- **He asks once.** When he is missing one thing he needs, he asks one short question with his best guess in it, then saves your answer so he never asks that again. If a wrong guess would be harmless he just does it and says the assumption.
- **"Forget that."** By voice (`forget`) or with Forget on the hub's Memory page, which now really works. A changed mind replaces the old memory instead of sitting beside it.
- **Controls > Pause memory and Off the record now work**: nothing is saved while either is on.

## 0.19.2 - From Laptop B's logs (2026-11-22)
### Fixed
From Laptop B's own logs and review recording of 2026-11-22 (67 things heard, 25 answered):
- **Calendar refused every time (Composio 400).** The key works and the account list came back fine; the call after it was refused. Jarvis now picks Google Calendar's own account from the list instead of the first one, tries once more naming the user, and reports Composio's own reason if it is still refused.
- **The core froze for seconds on every calendar lookup** (2.4 to 4.8 s each: a new secure connection was set up on the main loop every time). One connection is now made once, off the main loop, and kept.
- **The core froze for 63 seconds on the first question after a restart** (the Anthropic library was loaded on the main loop). It is now loaded in the background at start, and never on the main loop.
- **Canvas said only "failed (SignInNeeded)".** Jarvis is now told Canvas needs a sign-in and to open the sign-in window.
- **The hub feed logged an error every minute** (facts from memory were sent in the wrong shape) and rewrote the now card in the database every 30 seconds. Both fixed.
- `Jarvis report.bat` waits for the core after a restart instead of reporting "not answering" too early.

## 0.19.1 - Tools that land (2026-11-22)
### Fixed
- **"What Jarvis can do" said no tool had ever run.** Each tool's history was kept in memory only, so every restart wiped it, and a tool that was refused (not set up, needs sign-in) left no trace. It is now kept on the laptop (`data\tool_use.json`: counts, times and a short reason, never your words or a result).
- **Jarvis claiming he had checked something he hadn't.** His tool rules now say: never say you checked, opened or tried something unless a tool result shows it, and when a tool fails say which one and why in one line.

### Added
- **`Jarvis report.bat`**: one page on what works on a laptop (what is installed, whether the core answers, each tool's state, which keys are saved by name only, your class files, the last tool runs and warnings). It is saved to OneDrive > Documents > JarvisHub > reports so Claude can read it from either laptop. The update files now end by writing it.

## 0.19.0 - Alone, and pull up my work (2026-11-22)
### Added
- **Jarvis can run on one laptop by itself.** `Run Jarvis on this laptop.bat` sets up the core, voice and tools on the laptop you run it on and points that laptop's hub at its own Jarvis, so it no longer needs the other laptop. Each laptop then has its own memory, settings and keys (add the keys once in Controls > Keys). `Use the other laptop's Jarvis.bat` switches a laptop back.
- **"Pull up PPS 6", "let's work on mechanics".** New `work_on` tool: finds the assignment, lab, lecture, test or study plan you mean in your Class Content folder, opens the file on your laptop (the questions, not the solutions), and puts its deadline and the course on the hub. With only a course it picks the next thing due there. Local and instant.

### Changed
- `setup-voice.bat` and `setup-tools.bat` can run unattended as part of the one-file setup.

## 0.18.0 - The hub fills up (2026-11-22)
### Added
- **The hub is no longer empty.** Jarvis core now fills it. Today and the Now card show your classes with rooms, what's next and the closest deadline, read from the files your study skills already keep (`Class Content\_Week Planner`): instant and offline. Your Google Calendar is added on top when it is connected. The Life tree shows your term and courses (next classes, due work) plus whatever is in Jarvis's memory. Under the hood shows real response times and which sources are working and how fresh they are.
- **Jarvis knows your day without looking it up.** The same day goes into his now card, so "what's next", "what room" and "what's due" are answered straight away with no tool call (about 0.5 to 1.5 s sooner).
- **`school` tool.** One instant call for classes on any day, due work, a course's instructor, weights and tests, from the same files.
- **Tool-choice check, three in a row.** `Check tool choices.bat` now asks each thing three times and also reports how often Jarvis was right every time. `tools/review_golden.py` turns real turns from the review recording into candidate cases, the ones that went wrong first.

### Changed
- With no windows open, the one-window hub is the orb in the middle with one line for what's next. It goes to the corner only when Jarvis pulls something up.

### Fixed
- The resting orb was drawn on top of the clock and the Now card when the hub went to standby in one-window mode.

## 0.17.0 - One window (2026-11-22)
### Changed
- **One Jarvis window.** Opening the hub now opens one window, not two. Windows Jarvis pulls up appear inside it and the orb moves to the corner. The old second full-screen window is still there if you want it: Controls > "Stage window".

### Added
- **Move and size windows by hand.** Drag a window by its glass to move it; drag its bottom-right corner to make it bigger or smaller. A window you placed stays put (it no longer goes to the Rail after a minute) until you close it or press Tidy. Keyboard: on the corner grip, arrows size, Shift+arrows move, Home puts it back.
- **Pull a window out.** Each window has an "own window" button, or drag it past the edge of the hub: it moves to a plain second window ("Jarvis Windows") that only holds windows, with no orb and no voice. "Back to the hub", or closing that window, brings everything back.

## 0.16.0 - Review recording (2026-11-19)
### Added
- **Review recording.** While you have it switched on, Jarvis keeps everything about every interaction in `C:\Jarvis\logs\review` on Laptop B, so a week of real use can be studied afterwards: what the speech model heard and your side of each turn as sound, exactly what Claude was sent and what came back, every tool call with its input and result, every event sent to the hub, every button you pressed, every log line with the full error, the wait at each stage of each turn, what the voice window saw (wake-word scores, sound running dry, how each reply's sound arrived) and the laptop's load. Keys, passwords, session tokens and cookies are never written. Nothing leaves the laptop, nothing is kept from before you wake him, and it switches itself off after 4 days.
- `Start review recording.bat`: one file that updates the laptop it's run on, switches review recording on and restarts Jarvis core. `Stop review recording.bat` ends it early.
- `tools/review_summary.py`: a first look at a recording (how turns ended, waits, empty replies, tool failures, warnings, sound trouble, load).

### Changed
- `Update Laptop B.bat` is rewritten on the same tested base: it also finds the update file in Downloads, updates the OneDrive hub folder too, and works when run on Laptop A.
- With review recording off, nothing changes: the everyday logs still hold ids and timings only.

## 0.15.3 - Connect the calendar, close the window (2026-11-19)
### Fixed
- Connecting Google Calendar works now. When his calendar isn't connected, Jarvis no longer pulls Composio's site up inside the hub (Google refuses to sign anyone in there: "403. You do not have access to this page"). The calendar tool makes the connect link itself and puts a **Connect Google Calendar** card on his screen; one click opens it in his own browser on whichever laptop he is at, he picks his Google account and allows it, and Jarvis notices by himself and answers what he asked.
- Sign-in pages (Google, Microsoft, Composio and the like) are never loaded inside a hub window, on the desktop app too: they show as a card that opens in his browser.
- The buttons on a window Jarvis opened work on the real core: close, pin, bigger, move, clear view, bring back from the Rail and done. Before, every one of them answered "Jarvis can't do that yet. Nothing was changed."
- With no Composio key saved, Jarvis says where to add it (Controls > Keys) instead of opening a page.

## 0.15.2 - The hidden voice leaves a log (2026-11-19)
### Added
- The hub keeps a log of what its hidden voice program does and says (`C:\Jarvis\logs\voice-host.log`): started, live, waiting for another laptop, not connected and why, ended. It holds states and errors only, never what was said. Before this, a silent Jarvis left nothing to read.

## 0.15.1 - Update Laptop B in one click (2026-11-19)
### Added
- `Update Laptop B.bat`: after an update, run it on Laptop B (it's in OneDrive > Documents > JarvisHub). It copies the newest code OneDrive brought over into your Jarvis folder and restarts Jarvis core, so this chat no longer has to be linked to Laptop B to update it.

## 0.15.0 - One icon (2026-11-19)
### Changed
- One icon: **Jarvis Hub** now runs the voice itself. Open the hub and talk; close it and the voice stops. There is no second window to open, and "Set up Laptop A.bat" removes the old "Talk to Jarvis" shortcut. (`Talk to Jarvis.bat` still works on its own as a debugging window.)
- Both hubs can be open at once. The one you opened first keeps the voice; the other waits and picks it up by itself when the first one closes. Opening a hub never takes the voice away from the laptop you're talking on.

### Added
- Controls > Voice // Sound > **Voice on this laptop** says where Jarvis is listening ("Laptop B has the voice"), with a **Talk here** button that moves it to this laptop, and says in words why when the voice isn't running.
- Controls > Voice // Sound > **Microphone**: a switch that turns the mic off and on. It follows "mute the microphone" said out loud, and it always starts On after a restart.
- Jarvis has two brains to talk with: **quick** (Claude Haiku 5.5, as before) and **deep** (Claude Sonnet 5.5). Switching needs no restart; it changes from your next sentence and he remembers the choice.
- `Check tool choices.bat` now asks both brains about 50 of your typical requests and shows, side by side, how often each picked the right tool first and how long until its first word, then asks which one Jarvis should use. `Choose Jarvis brain.bat` switches without running the check (free).
- Five calendar questions ("what's my first class tomorrow", "am I free Friday afternoon") joined the check.

### Fixed
- Jumping to a setting from the command bar could miss its row when the page redrew at the same moment.
- Sonnet 5.5 is counted in the spend meter.

## 0.14.0 - He follows through (2026-11-19)
### Fixed
- "He said mm and went quiet": when Claude sends back an empty reply (7 of the 23 times you spoke on the 18th), Jarvis asks again once, and if there is still nothing he says so instead of going silent.
- A thought said in two parts is answered as one. Before, pausing mid-sentence cancelled the first half and only the second half was answered.
- He keeps the thread: an answer you cut into stays in the conversation, so "no, the other one" makes sense.
- "Yeah" or "no" on the last word of his question is taken as your answer, not dropped as a listener noise.
- He no longer goes deaf after a turn that never ended (what happened after the sign-in): a finished answer with no sound for 8 seconds is closed.
- Words that were shown as a caption but never spoken are now spoken.
- The orb no longer closes and reopens as you start talking, and "heard you" chimes once per thought, not twice.
- Hearing keeps up with you when you talk fast: the speech model has its own worker, so the microphone side never waits on it. (The worst case in the logs was 19 seconds behind, and the voice window lost its connection five times.)
- His voice starts and stops softly: every start, end, stop and gap is a short fade, getting quieter when you talk over him is smooth, and the speaker stays awake between replies so there's no switch-on sound.
- The log now says which tool failed and why (a name and an error type, never words).

### Added
- He can read your Google Calendar: "what's my first class tomorrow", "am I free Friday afternoon", "what room is GE 122 in". It needs the Composio key in Controls › Keys and Google Calendar connected in Composio; if either is missing he says which. Read-only.
- Signing in opens in a window of its own, and when you close it Jarvis carries on with what you asked by himself.
- The light around the orb follows the sound in the room all the time, and follows his own voice exactly while he speaks. The voice window measures both and sends two loudness numbers about 12 times a second (never the sound).
- `Teach Jarvis your voice.bat`: say 24 short things you'd really ask him; it shows what he heard and saves what his hearing gets wrong for you, so he can work out what you meant. The recordings stay on the laptop.
- `Record a test conversation.bat`: for 20 minutes, keeps what Jarvis heard, what he said and your side as sound, on the laptop only, so a bad conversation can be looked at. Off unless you run it; `Stop recording.bat` ends it sooner.

### Changed
- Every tool is ready at once in a spoken turn (no search step before a less common one): about one round trip faster when he uses a tool.
- "Idle" shows on the orb 0.4 seconds after things go quiet, so quick back-and-forth never flickers.

## 0.13.4 - Wake word set-up fixed (2026-11-18)
### Fixed
- "Hey Jarvis" set-up no longer fails on Laptop A. Jarvis now runs the wake-word model himself instead of through the openWakeWord package, whose machine-learning add-on (scikit-learn) broke on install. Same model, same scores (checked side by side), smaller install.

## 0.13.3 - Laptop A on Python 3.13 (2026-11-18)
### Fixed
- `Set up Laptop A.bat` works when the newest Python (3.15) is installed: it uses Python 3.13, gets it if needed, and rebuilds the hub's Python on it. On 3.15 the voice packages had no ready-made installs and needed a C++ compiler.

## 0.13.2 - Connect from anywhere (2026-11-18)
### Fixed
- `Connect Laptop A (run on Laptop B).bat` works from your Jarvis folder too: it always leaves the pairing in OneDrive\Documents\JarvisHub, where Laptop A picks it up.

## 0.13.1 - Laptop A (2026-11-18)
### Added
- Laptop A in two double-clicks. `Connect Laptop A (run on Laptop B).bat` shares Jarvis core on your own tailnet (never the internet) and pairs Laptop A; `Set up Laptop A.bat` installs the hub, the voice window, "hey Jarvis" and the Right Ctrl talk key, connects to Laptop B and lets you test the wake word. The token travels in a small file through OneDrive and is deleted as soon as Laptop A has saved it; it's never shown. Steps in LAPTOP_A_SETUP.md.

## 0.13.0 - Hey Jarvis (2026-11-18)
### Added
- Say "hey Jarvis" to talk. The voice window listens for it on the laptop itself and sends nothing to Jarvis until it hears it. A soft two-note chime and the orb turning to listening tell you he heard. He stays listening through the conversation and for 8 seconds after his answer, so a follow-up needs no second "hey Jarvis". Then he goes back to waiting.
- Hold Right Ctrl to talk, from any app. Everything you say while it's held is one turn, even with long pauses, and letting go sends it at once (about a quarter of a second sooner than hands-free). Pressing it while Jarvis is talking stops him straight away. It works on its own too: `Talk to Jarvis.bat --listen ptt`.
- `Set up wake word.bat` installs both (about 3 MB) and lets you try "hey Jarvis" with a live score. `Wake word test.bat` does just the test. `setup-voice.bat` now sets them up as well.
- When Jarvis starts talking on his own (a task finished), he listens without the wake word, so "yes" or "stop" just works.

### Changed
- Background voices and the TV can no longer start a turn while he's waiting for "hey Jarvis". `Talk to Jarvis.bat --listen always` brings back the old always-listening behaviour.

## 0.12.5 - He knows when it's you (2026-11-18)
### Fixed
- Jarvis no longer goes quiet at the slightest noise, and he no longer hears his own voice as you. The voice detector now uses the set-up Pipecat (the framework he's built on) ships as standard, and while Jarvis is talking a stricter detector decides, so his own echo doesn't count. In testing this took "Jarvis heard himself" from 4 times in 6 seconds to none, and "stop" over him still worked every time.
- He only gets quieter once you've clearly been talking for about half a second, not on the first sound, so a tap or a cough leaves him alone. Stopping him still takes about a second of talking.
- No more flicking in and out of listening: a turn starts after 0.2 s of real speech, not on one stray sound. Nothing you say is lost, because the audio from just before is kept.

### Added
- `Conversation check.bat`: about 50 seconds of prompts (instructions, a tap and a cough, and Jarvis talking while you stay quiet or say "stop"). It tests each setting on your own mic and keeps the one that catches the most instructions with the fewest false starts. Numbers only are saved.

## 0.12.4 - Controls work (2026-11-17)
### Fixed
- Switches in Controls now work on the real Jarvis. Every one used to say "Jarvis can't do that yet". Your choices (Motion, Theme, How chatty, Sounds…) are saved on Laptop B, so they stay after a restart, and every screen updates at once.

## 0.12.3 - He hears you better (2026-11-17)
### Fixed
- Jarvis no longer crashes mid-sentence when two of your turns end close together. The speech engine was being used by two things at once and took the whole core down; now only one thing uses it at a time, and each turn keeps its own words.
- The first Canvas question or sign-in after a restart no longer freezes Jarvis for a few seconds: the browser code loads in the background when he starts.

### Added
- `Hearing check.bat`: you read three short sentences and it tests every mic set-up (the old boost, automatic gain, automatic gain with light noise suppression) through Jarvis's own speech model, then keeps the one that got the most words right. Numbers only are saved, never the recording.
- The orb's glow is scaled to your voice and your room from the hearing check, and it rises fast and falls back slowly like a level meter, so you can see he's hearing you.
- Controls › Motion › Always keeps the orb's animations even when Windows has animations turned off (Full still follows Windows).

## 0.12.2 - Sign-in without the wait (2026-11-17)
### Fixed
- Signing in no longer waits for Chrome to start, so it can't hit the time limit ("took too long and was stopped"). The window opens on its own a moment later.
- `Sign in to a site.bat` shows how long it took.
### Added
- If Jarvis ever freezes for more than a second and a half, his log now records where in the code it was stuck (code locations only, nothing you said).

## 0.12.1 - Sign in with Chrome (2026-11-17)
### Changed
- The Jarvis browser is now Google Chrome (Edge only if Chrome isn't installed). Signing in opens it as a normal Chrome window with nothing attached, so you can sign in to your Google account there and your saved Google passwords fill in for you. Jarvis never sees them.

### Fixed
- Signing in no longer freezes Jarvis for almost a minute, and `Sign in to a site.bat` now shows what went wrong if it fails.

### Added
- `Browser check.bat` tests the Jarvis browser step by step and saves the result where Claude can read it.

## 0.12.0 - Jarvis gets tools (2026-11-17)
### Added
- Jarvis has tools, kept in a tools folder (`jarvis/tools/`, one folder per ability) and filed in his memory as his abilities: search the web and read pages; search Canvas for anything (assignments, announcements, modules, pages, files, the syllabus) and open it; read PDFs, Word, Excel and PowerPoint files, including scanned pages; pull pages up on screen; browse websites as you in his own browser (PAWS, Crowdmark, Google…) using the same browser tools Claude uses; research a question on his own and come back with sources; and hand bigger jobs to a Claude agent that reports back when it's done.
- He picks tools the way Claude does: each tool says when to use it and when not, and a short routing guide tells him which to try first. "Check tool choices.bat" tests his picks on about 45 typical requests.
- "Sign in to a site.bat" opens the Jarvis browser on Laptop B so you can sign in to Canvas and other sites yourself. Jarvis uses those sessions but never sees or types a password.
- "setup-tools.bat" installs everything (about 170 MB) and checks it.
### Safety
- Reading is free. Nothing is changed anywhere: a browsing run fills forms only when you ask, and always leaves Send, Submit, Pay or Delete for you to press. Jarvis never types passwords and never submits anything to Canvas, PAWS or Crowdmark.

## 0.11.2 - A voice visualizer (2026-11-17)
### Fixed
- Jarvis's caption no longer flickers while he speaks.
- The orb keeps showing "Speaking" until Jarvis's voice has really finished; it used to go back about half a second early.
- The hub reloads itself when a new version is installed (once Jarvis is quiet), so it never keeps running an old page.
### Changed
- The outer rings are a visualizer now: while Jarvis speaks they spin the opposite way to the inner rings, faster the louder he speaks, and they speed up and coast to a stop smoothly. The inner rings also ease in and out of their faster spin instead of switching.
- The glow follows the voice with a wider range, so it reads clearly.
- Harder to interrupt: Jarvis goes quieter the moment you talk, but only stops after about a second of continuous talking. A few words over him are ignored.

## 0.11.1 - One voice window (2026-11-17)
### Fixed
- Two "Talk to Jarvis" windows no longer fight over the voice ("Another laptop took over the voice", over and over). The newest window keeps it; the older one stops and says you can close it.

## 0.11.0 - Talk over Jarvis (2026-11-17)
### Fixed
- Jarvis answers again when the room isn't silent. A fan, a cough or a click right after a question counted as you starting a new sentence, which threw his answer away, so he heard you and said nothing. Now a sound with no words never cancels an answer; a real new question replaces the old one.
### Added
- Talk over Jarvis like ChatGPT: the mic stays on while he speaks (echo cancellation removes his own voice). He goes quieter the moment you start, and stops once it's clearly you saying something (two real words, or about half a second of speech). "Mm-hmm", "yeah" and his own echo don't stop him. Needs setup-voice.bat run once.
- If an answer is slow, Jarvis says a short "Mm.", "One moment." or "Let me see." after 0.8 s so he never just goes quiet. It plays instantly from a cache in his voice, at most once per answer and rarely.
- "Benchmark speech.bat" times the speech-to-text models on this laptop, to pick the fastest.
### Changed
- The orb's glow follows your voice the whole time you talk, and Jarvis's while he speaks.
- The outer rings spin up while Jarvis speaks.
- The rings go back into the standby sphere a few seconds after a conversation, not the instant you stop, and they come out and go back over half a second, smoothly.

## 0.10.2 - Jarvis speaks again (2026-11-17)
### Fixed
- Jarvis speaks again. The more expressive voice model from 0.8.2 turned out not to work with the live voice connection, so every answer was refused and he sat on "thinking". He's back on the fast model (Flash v2.5).
- If his voice ever fails again, his answer appears as a caption on the hub instead of the orb thinking forever.

## 0.10.1 - Failure reasons (2026-11-17)
### Fixed
- When Jarvis's voice or the speaker fails, the Talk to Jarvis window and the logs now say why, so problems can be found.

## 0.10.0 - Voice in Jarvis core (2026-11-17)
### Added
- Jarvis's voice now runs inside Jarvis core: "Talk to Jarvis.bat" connects this laptop's mic and speakers to the core, and the orb and his captions show on the hub while you talk. It reconnects by itself if the core restarts. The old self-contained version is "Talk to Jarvis (standalone).bat".
- The core loads the voice by itself at start-up once it's set up, and says what's missing if it isn't.
### Fixed
- restart-core.bat works: the core restarts itself on request (the old way failed with red errors).
- Laptop A can talk to Jarvis too: setup.bat now installs the voice client, and "Talk to Jarvis.bat" works there once Laptop A can reach the core (Tailscale).

## 0.9.0 - Jarvis's personality and hearing (2026-11-17)
### Changed
- Jarvis talks like Jarvis: short, calm, "sir", status first, offers as "Shall I…", one dry remark at most, no chatbot phrases. He also knows the real date and time.
- He hears soft speech: an automatic mic boost and gentler voice detection, so you can talk at a normal volume and words aren't cut off. Mic test shows the boost.

## 0.8.2 - A more expressive voice (2026-11-17)
### Changed
- Jarvis's voice uses ElevenLabs' new Eleven v4 Turbo model: much more expressive, at about the same speed as before. "Talk to Jarvis (Flash).bat" uses the older, plainer model if you want to compare.

## 0.8.1 - Voice first-run fixes (2026-11-16)
### Fixed
- Jarvis now speaks his answers: the voice connection was being closed by a bad keep-alive message, and it now re-opens itself the moment you start talking.
- He hears soft speech from a laptop's built-in mic better and cuts sentences into pieces less often.
- A turn with no words (a cough, a noise) is ignored instead of causing an error.
### Added
- `Talk to Jarvis.bat --mic-test`: shows your mic level and whether Jarvis hears you as speech. Errors now say why.

## 0.8.0 - Talk to Jarvis (2026-11-16)
### Added
- Talk to Jarvis on Laptop B: setup-voice.bat installs the voice and downloads the speech model, then "Talk to Jarvis.bat" lets you talk to him with this laptop's mic and speakers. Each answer shows what he heard, what he said and how fast he answered.
### Fixed
- The first word you say is no longer cut off (the speech recogniser now hears the moment before Jarvis notices you started talking).

## 0.7.2 - Voice ID setting (2026-11-16)
### Added
- Controls › Keys › Voice: paste your ElevenLabs voice ID and press Save. It's kept on Laptop B and shown back (it isn't a secret).

## 0.7.1 - One-click core setup (2026-11-16)
### Changed
- setup-core.bat now does the whole Laptop B install: it starts the core, makes it start by itself at every sign-in (no Servy or password needed), waits until it's healthy, and pairs Laptop B's hub with it.

## 0.7.0 - Live mode (2026-11-16)
### Added
- The hub now runs live: it shows what Jarvis core really knows, or an honest "Offline" screen when the core isn't set up or isn't answering, and reconnects by itself.
- "Jarvis Hub (demo).bat" starts the old demo day when you want to show it off.
- LAPTOP_B_SETUP.md: a step-by-step guide for installing the core on Laptop B.
- Design doc for when Jarvis asks and when it acts (docs/design/JARVIS_DESIGN_ASK_OR_ACT.md).
### Changed
- The demo day no longer starts by default; it only runs with `--demo`.
- The core's screens and actions now answer only paired devices, and only devices allowed to write can act; pairing a new device works without restarting the core.

## 0.6.3 - Smooth hand-off, rounded everywhere (2026-11-16)
### Fixed
- the rings no longer skip a beat when the orb lands in the corner (or comes back); the corner orb picks up exactly where the rings were.
### Changed
- soft rounded corners everywhere (settings, cards, chips, the drop-down under a window, menus), labels in normal case throughout, and cards lose their blue halo.

## 0.6.2 - Blue light (2026-11-16)
### Changed
- the orb's light is blue all the way out: no bright blue rim hugging the centre circle, just a clear blue glow from behind it that fades smoothly.

## 0.6.1 - A softer orb (2026-11-16)
### Fixed
- the solid blue ring no longer flashes when Jarvis stops listening or speaking.
### Changed
- the orb keeps all its rings but takes on the serious look: a soft, muted steel-blue glow from behind the centre that brightens (never grows) when Jarvis speaks, and softer off-white rings.

## 0.6.0 - Serious mode (2026-11-16)
### Changed
- "serious mode". The hub now uses one muted steel-blue accent instead of neon cyan, off-white text, calmer amber and red, and quiet near-black surfaces. Labels are in normal case, titles and big numbers use a clean sans font instead of bold condensed capitals, and windows are softly rounded with a real shadow. Motion is short and simple: windows fade in together as the orb moves to the corner, with no flying or one-after-another effects. The orb itself is unchanged.
### Fixed
- windows could stay hidden if the Stage window never reported itself as visible; they now show after 0.6 s regardless.

## 0.5.7 - No blue flash (2026-11-16)
### Fixed
- the orb no longer flashes a solid blue ring for a moment while it slides back from the corner.

## 0.5.6 - A glow that's always there (2026-11-16)
### Changed
- the orb's glow is always on now, a small light hidden behind the centre that you only see glowing out from behind the circles, and it grows when Jarvis speaks.

## 0.5.5 - Glow from the core (2026-11-16)
### Changed
- the orb's glow now comes from the core itself, behind all the rings, and fades outward smoothly. There's no separate glowing ring any more.

## 0.5.4 - Light with a source (2026-11-16)
### Fixed
- opening an icon at the bottom no longer covers the next icon's number. The open icon gets a short lit bar under it instead of a box.
### Changed
- the orb's blue ring is now a light source: one thin bright line whose light fades away smoothly on both sides, with no inner or outer border.
- a more grown-up look. The stacked outline "ghosts" behind windows and menus are gone, replaced by a real soft shadow and a lit top edge, and the corner brackets are thinner.

## 0.5.3 - Smooth, and a cleaner look (2026-11-16)
### Fixed
- the lag when the orb slides to the corner. It's now drawn once and slid, instead of being redrawn every frame.
- the "Why?" drop-down under a window no longer runs into the caption and the icons at the bottom; it opens toward the side with more room and scrolls inside itself.
### Changed
- smoother opening and closing. Windows fly out of their icon and drop back into the icon row when they close, and the icon menu rises and settles away softly.
- a cleaner, more real look: dimmer cyan hairline edges instead of bright white outlines, no neon outline on the window Jarvis means, a tinted title strip instead of a solid neon block, a deeper amber, a fine grain and darker edges behind the windows, and a brighter resting glow on the orb.

## 0.5.2 - Windows fly out of the orb, and a real glow (2026-11-15)
### Changed
- when windows open, the orb now glides from where it was to the bottom-right in one smooth motion, and the windows fly out of the orb one after another as it goes. On Laptop A the Stage waits until it is on screen before playing this, so the orb no longer vanishes and pops back in the corner.
- the orb's blue glow is now light rather than a solid blue ring: a see-through band with a bright thin edge, light that fades smoothly far out around it, and a soft glow on every smaller ring.

## 0.5.1 - Rings stay flat when the orb moves (2026-11-15)
### Fixed
- The orb's rings no longer seem to spin on the wrong axis when the screen wakes and the orb slides to the corner. The first wake of the day used to tilt the rings in 3D; now they wind out from the centre, flat.

## 0.5.0 - Reach in the hub, and the first of Jarvis core (2026-11-15)
### Added
- Web windows: Jarvis can put a live web page (a search, a doc, a site) in a glass window on the Stage, and a "tabs" window holds a few pages with a small tab row you click or arrow through, like Huw's. Click one to open the page full size, with Open in browser and Close (Esc closes it).
- A page that can't be shown inside the hub becomes a clean card: WEB // the site, the page's title and its address; clicking it opens the page in your normal browser.
- In the desktop app, sites that usually refuse to be shown inside another page (Google, GitHub, Canvas) can be shown in web windows, and pages you sign in to stay signed in, in the hub's own browser profile (`%LOCALAPPDATA%\JarvisHub\webprofile`), kept apart from your everyday Chrome. Delete that folder to sign out of everything. (Built from Microsoft's documentation and not yet run on Windows.)
- A map window: ask "show me where my lab is" (or "show me the map") and a dark campus map opens on the Stage with today's places, the route between them, the next place lit and labelled, and one line under it like "Next: CHEM 142 lab 4 · Thorvaldson 173 · 1:30 pm". Without internet the map is a simple campus sketch, clearly marked "Schematic · approximate"; with internet it uses real map tiles (© OpenStreetMap contributors © CARTO).
- Controls › What Jarvis can do: every tool on the six rungs of the reach ladder (your data, app APIs, local tools, app automation, Claude agents, computer use), with what each can read and write, whether it's connected, needs sign-in, is paused in game mode or is off, when it was last used, and an on/off switch.
- The allowed folders are an editable list (Documents, Desktop, Class Content, Class Management and Jarvis Workspace to start). System folders, AppData and whole drives are refused. Also there: app scopes (Fusion set up; Office and VS Code not yet), your standing permissions with Revoke, and cost caps for Claude tasks ($1 per task and $5 per day, both editable).
- Claude tasks on the Stage: a CLAUDE // TASK window with the time it has run, the goal (or Fusion's view once there's something to see), the step it's on and the cost so far. Hover or focus shows Stop and Open.
- Activity › Tasks: running and finished Claude tasks with every step, the files they touched, the transcript and Undo. "Run the demo task" there plays "Design a phone stand in Fusion": the steps, one ask, your Allow, the finished file and Undo.
- When Claude wants to write something, it asks you in Your yes on the same approval card: "Claude wants to create 'Stand v1.f3d' in Fusion Projects. Allow?" with Allow, Deny, and Allow for this task after a second similar ask. If you're away it waits as Parked, never failed.
- Email catches: the Messages icon shows the emails Jarvis flagged, one line each with the reason ("Prof: GE 122 lab moved to Thursday"). Reading only: drafts happen only when you ask.
- Controls › Keys: the keys Jarvis uses (Claude, ElevenLabs, Composio, the restic backup password, plus "Add a service" for optional ones). Each row shows its status as a shape, a colour and a word, the key's last 4 characters (never any of the backup password), and when it was added and last checked. The key field clears the moment you press Check, and the key is never shown or kept on the hub.
- Swapping a key is four steps with no downtime: Add next key, Check, Make live, Remove old. A key that fails its check never goes live. The old key stays 15 minutes; if the new one is refused in that time Jarvis goes back to the old one by itself, and the row and Your yes both flag it.
- Until Jarvis core runs on Laptop B, the Keys page says "Jarvis core isn't connected yet", shows example rows marked as examples, and accepts nothing. Once the hub is told where the core is (two settings, in `ops/README.md`), the page talks to it. On the phone the page is view-only.
- Jarvis core, the back end that will run on Laptop B, now exists as a skeleton: `python -m jarvis.core` starts it and http://127.0.0.1:8770/healthz shows green when every part is up. It speaks the hub's language (state, live events, actions), starting empty; every action answers "Jarvis can't do that yet. Nothing was changed." until the real action layer arrives.
- The core keeps background jobs in a small database, so they survive a restart or crash; at most 2 run at once, failures are retried, and each job can have a time and spending limit. Its log holds only ids, timings and counts: never what you said and never a key.
- `setup-core.bat` sets the core up on Laptop B, and `ops/README.md` explains running it as a Servy service under your account, reaching it from your tailnet with `tailscale serve`, and pairing your devices (`--pair laptop-a`, `--pair phone --view-only`). Not yet run on Windows.
- The core holds your API keys in Windows Credential Manager. Each change shows up in Activity as a plain line like "Claude key replaced", with no key material in it. Keys can only be changed from your own devices with a hub session.
- A memory store: one private database file (jarvis.db, kept outside git) that holds what you said, what Jarvis learned from it, where each thing came from, and when it was true. Your own word always counts most: emails, Canvas, invites and web pages can never become your decisions, rules or pinned memories.
- Memory keeps history (you moved from Birch House to Maple Hall: both are known, with dates). "Undo that" reverses exactly one change; "Forget that" wipes the text from the database file, its log and its search index. Every memory sits on a branch of your Life Tree, so money and health branches never leak into other answers.
- Jarvis's voice loop, ready to try on Laptop B: it works out when you've finished talking, answers quick commands (time, timers, stop, mute, volume, "open ...", "book it" / "send it") without asking Claude, streams everything else from Claude into the Jarvis voice, starts thinking while you finish your sentence, and stops at once when you talk over it. Tested with stand-ins only: no real microphone, models or voices yet.
- A latency report (`python tools/latency_report.py`) that times every step from the end of your speech to the first sound, plus a spend meter for Claude and ElevenLabs.

### Changed
- Web pages, map tiles and a Claude task's picture sit under the same dark tint as a PDF page, so media never outshine text.
- The sounds are gentler: softer starts, lower and rounder tones, a shorter tick, and about 6 dB quieter. The wake rise plays only on the first wake of the day.
- A slot's list (opened from the bottom row) is one clean glass panel like the windows: just "HOMEWORK // 8" and the cards. Each card has one title line, at most one short line, and its glance mark (with a word only when it wants you); page previews stay small, other things show their line icon. "Mark all seen" and "Close" appear when you point at the panel or tab into it.
- The Google OAuth client is no longer one of the default keys, because Composio now handles Gmail, Calendar and Drive. You can still add it from "Add a service".

### Fixed
- What you open from the bottom row (a slot's list, the command bar) now always sits on top of every window on the Stage and the hub, even the bright one Jarvis means or one you're hovering. While a list is open the windows dim a step and ignore the mouse; Esc or a click anywhere else closes it.
- Windows open in silence. The sound you heard was the "heard you" tick (and the wake chime on a first wake), played by the hub and the Stage at once; now only one window plays sounds (the Stage while it's open) and nothing ever plays as windows land.
- A long job name in the bottom-left chip no longer runs over the icon row on a 1440-wide screen: it is cut with "…".
- A message card under the Messages icon opens Activity instead of Life.

## 0.4.1 - Clean windows (2026-11-15)
### Changed
- Every window Jarvis shows is now as clean as Huw's: one small label row on top ("GE 122 // PPS 7") with at most one time or page number on the right, one big thing (a picture, a number, a flat chart or a short title), at most one line under it, and one tiny note below the frame. Nothing else.
- No chips, links or buttons on a resting window. Sources, details and controls (including a question's Yes and No) appear when you point at the window or Tab into it, or when you open it; voice works as before. Clicking a question's window only opens it. It never answers for you.
- Calmer colours: one blue accent, near-white and grey, plus the picture's own colours. Big numbers are near-white, never amber; the only amber or red on a window is one small mark in its label row when it wants you. Charts are flat near-white bars. The bright title plate is only on the window Jarvis means.
- A PDF page no longer glares: pictures sit under a dark tint, so text is always brighter than media.
- The windows sit as one tidy cluster instead of a scatter: three widths (small, medium, large), 16 px between them, columns lined up on one top edge with short windows stacked under their neighbours, the picture large in the middle, and the whole group centred in the space left of the orb. They only overlap when the screen is crowded. The hub's own canvas ("On the hub") is laid out the same way.
- Glass edges are brighter, closer to Huw's.
- The orb's speaking glow is dimmer and tighter: it hugs the blue ring and is gone a short way out, instead of a wide haze. The ring is still the brightest thing on screen.
- No pulsing: nothing in the orb grows or shrinks with the voice any more. While Jarvis speaks the rings just spin faster and the glow gets a little brighter.
- On the Stage, the source chip beside what Jarvis says shows when you point at the line.

### Fixed
- The rings no longer spin off centre when Jarvis starts talking (a brief 3D tilt threw them up to 6 px off). Every ring now only turns about the centre, and a test keeps it within 1 px.
- The focus brackets on an icon in the bottom row no longer run into the count badges.

### Removed
- The four small readouts around the orb (THINK 420 MS, HEAR 180 MS, SPEAK 140 MS, CANVAS 2 MIN). The ticks are bare, like Huw's; the same numbers are in Controls › Under the hood.

## 0.4.0 - HUD v3: closer to Huw (2026-11-15)
### Added
- A small clock and date under the standby sphere, like Huw's.
- When Jarvis has something to offer you to pick up (work you left a little while ago), it shows as one small glass card under the orb: the page's picture and "PPS 7 · Q7 · Today". Tap it and the practice set opens right at the question, with no second card. "Not now" takes it away without a word, and so does leaving it alone or doing something else; it stays under the Homework icon and is only offered again when you leave and come back or your spot moves. If Jarvis says the offer, his line above the icon row is the offer.
- Picking a practice set under the Homework icon now opens it in the reader at your spot.

### Changed
- The home screen is as empty as Huw's: awake, it's just the orb in the middle of the grid. No big clock, no date, no "what's next" line and no day dial around the orb. When Jarvis rests, it's the small particle sphere with a small clock and a tiny date under it, and nothing else.
- The orb looks like Huw's: thin near-white rings and arcs with only a faint blue glow when Jarvis is idle or thinking. It is smaller too: its outer marks take about a sixth of the screen's width.
- The blue ring only lights up while you or Jarvis are talking, and it glows like Huw's: a wide soft glow outside it, a lighter line on its outer edge, a deep blue body that darkens toward the inside, then a dark gap and the thin white core outline. It still moves with the voice.
- When the orb is docked among windows it shows white rings only (amber, red and grey still show when something needs you or the mic is off).
- The Rail is now Huw's row of tiny icons at the bottom centre (Your yes · Today · Homework · Messages · Jarvis · Parked) with small counts. Anything that wants you shows its shape on the icon: an amber square for your yes, an amber diamond for soon, a red triangle for critical. Click an icon (or press Alt+1 to 6) to open it, as before.
- The five views are page dots under the icon row instead of pills in the top-right corner. Keys 1 to 5, Esc and Ctrl+K work as before, and a small search icon in the row opens the command bar. "Stage · 4" is now a small Stage icon with its count in the row.
- What Jarvis says shows above the icon row only while he's saying it, then it's kept under the Jarvis icon. The status word (Listening, Thinking, Speaking, Standby) is small, bottom-left.
- The windows Jarvis pulls up on the Stage look like Huw's: small see-through glass panels with a bright thin edge and two faint edges stacked behind them, so each one reads as a slab of glass. You can see the grid through them.
- The Stage is a loose collage, not a tiled grid: pictures and charts sit near the middle, big numbers along the top, text panels toward the edges, around the orb in the corner. They only overlap when the screen is crowded, never over the orb or the icon row, and the one Jarvis is talking about always comes to the front, whole. Windows stay where they are when a new one arrives; TIDY lays the board out fresh.
- No buttons on the cards: pin and close appear when you point at a window (or Tab into it), and clicking a window opens it ("Open it" is gone). Voice works as before.
- A PDF page or a chart fills its window edge to edge; text panels have a small blue mono label ("PPS 7 // Q7") and smaller, denser text. The window Jarvis means gets its title on a bright plate; big numbers stay big.
- HUB · TIDY · CLEAR VIEW on the Stage are three small, quiet words in the top-right corner.
- The faint square line grid replaces the dots behind everything.

### Fixed
- A small course picture beside a name no longer gets squeezed under the name in a narrow window.

### Removed
- The day dial is no longer drawn around the orb on the home screen (Today still has it).
- The always-on "what you were doing" line and the "1 waiting for your yes" pill on the home screen (the offer card and the Your yes icon carry them).

## 0.3.1 - Run it from the code (2026-11-15)
### Added
- You can run the hub straight from its code with Smart App Control left on: double-click setup.bat once, then start "Jarvis Hub" from the Start menu. The installer is still built for every release, ready for when it's signed.

## 0.3.0 - Night HUD: the JARVIS look, the Stage and resume points (2026-11-15)
### Added
- Night is the new look: Huw's deep navy with ice-cyan window frames, a faint grid, a dotted ruler along the top and a soft static glow. It's the default everywhere, the ambient screen included.
- Jarvis's orb is rebuilt as the Core, layer by layer from Huw's: a dark core with JARVIS in the middle, white inner arcs turning opposite ways, the blue energy ring that swells with the voice, an outer arc, a ring of 48 dots, ticks with four tiny live readouts (like "THINK 420 MS"), hash marks that step with Jarvis's voice, and a few twinkling motes.
- The Stage: the windows Jarvis pulls up while you talk now open in their own borderless window, full screen on the monitor you pick (Laptop B's main screen by default; `--stage-screen 1` picks another). It is made at start but stays hidden, so it appears in about a tenth of a second when Jarvis shows you something. The orb sits in its bottom-right corner, the same Rail runs along the bottom, and Hub · TIDY · CLEAR VIEW sit top-right.
- The Rail along the bottom of every tab: six small gauges (Your yes, Today, Homework, Messages, Jarvis, Parked) showing how many things are in each, how much of today is done and the most urgent state. Click one (or press Alt+1 to 6) and its things fan out; pick one and its window comes back out of the slot.
- Practice sets open inside Jarvis on a light reading page, right at the question you stopped on, with a small card behind it: the page, "PPS 7 · Q7 · Tue" and one line like "1–6 done."
- A day dial around the orb: a watch face from an hour ago to 11 hours ahead, with your classes and study blocks as arcs (done, next, upcoming, moved), due items as amber diamonds and overdue ones as red triangles. Only the next thing is labelled ("4:00 · GE 122 · ENGR 1A10"). It works across midnight and never moves except once a minute.
- A narrow display font (Barlow Condensed) for window titles and big numbers, and small mono kickers like "GE 122 // DUE" at the top of each window.
- Text Jarvis shows on a light page (PDFs, notes) keeps its colours readable: darker amber, green, blue and red made for a white page.
- Every state has its own look and word: standby turns into a soft sphere of drifting particles, listening brightens the ring, thinking spins the arcs faster with dots chasing round the ring, speaking pulses with the voice, waiting for your yes is a steady amber ring with "AWAITING YES" whose dotted ring drains (never a countdown number), alerts turn amber or red with one pulse, and muted or offline go grey with a gap and a glyph.
- Waking Jarvis shows Listening straight away. The first wake of the day (or after 4 hours away) gets the film-style beat: the rings swing in tilted on a diagonal and snap flat with a soft two-note chime; every other wake just tightens the dotted ring.
- When windows arrive the orb can pull its outer rings in and slide into the bottom-right corner, where it keeps a small set of rings (120 px on the big screen, 64 px on a laptop). It doesn't slide again if it docked in the last minute.
- Three original sounds made just for Jarvis: a two-note glass rise for the first wake, a soft tick when he's heard you, and a low tone for something critical. They sit well under his voice and stay silent in quiet hours, in game mode and on Laptop A's strip.
- The resting screen leads with one line: in the morning, today's first class with its room and what's due today; after a short break, a picture of what you were doing ("PPS 7 · Q7 · Today").
- A small cyan notch shows what changed since you last looked ("Due moved Wed 8 pm → Thu 11:59 pm"). It clears when you open, focus or hover on the thing, or when you press "Mark all seen", never just because it was on screen.
- The last ten things Jarvis said stay under the Jarvis slot, so a caption or notice you missed isn't lost.
- When Jarvis names something while speaking, brackets snap onto that window or Rail slot for a moment.
- Every state now has its own little mark, so a glance tells you what's going on without reading: a filled disc with a check for done, a ring filling up for in progress, a crosshair for what Jarvis is on, a diamond in brackets for "soon", a square in brackets for "your yes", a red triangle in brackets for "now", and a dashed ring for parked. Each one always comes with its word.
- Things show up as pictures with a big label: the page a question is on, a slide deck's first slide, a course picture, a lecture video frame, a plotter design. With no picture you get a big course code ("GE 122"), initials for people, or the room code ("ENGR 1A10"). The pictures are small and kept on your laptop, never in the repo.
- New little line icons for classes, homework, labs, exams, messages, Jarvis jobs, the plotter and money.
- When Jarvis is working on something, its window shows a segmented bar with a bright chunk sweeping across (or "Working · 60%" if you've turned motion down).
- Press Enter (or "Carry on at Q7") and brackets lock onto the question; "From the top" or "Another question" go there instead; just scrolling is an answer too, and the card gets out of the way without a word.
- Jarvis keeps your place on its own when you close or leave the set. If it can't tell which question you were on, it offers the page instead of guessing.
- "Why?" on the card says how Jarvis knows; solutions you looked at show only there, and never when someone else is around.
- The PDF reader works offline and reopens a set you've had open in a blink.
- A new demo story that feels like JARVIS: you walk in to one line about what changed, "Status." lights up each thing as Jarvis names it, "Study protocol?" is echoed back with the one calendar change read out, your "Yes." opens PPS 7 at question 7, and the week plan waits quietly under Your yes when you say something else.
- Jarvis's way of talking: short, slightly formal lines that change with what's new, never repeat the same wording back to back, never greet you the same way twice a day, keep "Shall I" rare, and say less when you're rushed, heads-down, gaming or not alone.
- Declines that feel human: ignoring or "not now" quietly turns an offer into a card, "stop offering that" switches it off with an undo, and Jarvis never brings up a past no.
- A richer demo day: the Rail has real-looking items, "since you looked" marks, practice-set progress (PPS 7, question 7) and a day dial for the next 12 hours, with picture slots for made-up slides and pages.
- To try the demo at another time, start it with `JARVIS_DEMO_CLOCK=2026-11-14T22:30`. Its clock starts there and runs on.
- The strip on Laptop A now shows the Rail at a glance: the worst thing's shape and word ("Soon", "Your yes") and how many things are new since you looked, still and silent as before.
- Something critical turns the strip's orb red, says "Critical" and names the thing ("GE 122 · PPS 7 · Overdue since Wed 8 pm"), even in game mode, where nothing else shows.
- After a game, the strip shows one still line of what came in meanwhile ("While you played: Homework 1, Messages 2"); it goes away once you've seen those things.
- The strip and the phone's orb say "Standby" when nobody is at the hub.
- When you put the last window away the Stage fades back to the orb and the clock (Laptop B), or hides (Laptop A). It never appears while game mode is on.
- A small "Stage · 4" chip on the home page says how many windows are up and brings the Stage to the front. The Stage's Hub pill (and any link inside a Stage window, like "Open GE 122") brings the hub back.
- Controls › Screens › "Where Jarvis shows things": Stage window (the default) or On the hub (the old way, windows on the home page).
- Controls has a new Voice and Sound group: how loud Jarvis's own sounds are (Off, Minimal or Full) and how he addresses you (by name, "sir", or not at all).
- Clicking the small orb in the corner brings back the full view with the big orb and the clock. When windows arrive, the big orb slides down into the corner while they assemble.
- When you leave, the hub rests on the clock screen and the orb turns into its quiet standby sphere.
- If something on the Rail is overdue, the orb's ring turns red.
- "Open it" on a practice set opens it inside Jarvis at your question.
- Ctrl+K finds your work: type "pps 7" and PPS 7 opens in the reader right where you stopped. Things that are due and your files show up too.
- The "PPS 7 · Q7 · Today" line on the home screen is now a link: click or tap it to carry on at that spot.

### Changed
- Moving a window left or right is now one clean move, not a close and a reopen.
- The bottom of the hub is now one band: status on the left, room for the Rail in the centre with Jarvis's caption just above it, and the orb on the right.
- Controls › Look now offers Night, Daylight and Sunset, and the hub opens in Night by default. Daylight is the old warm Earth look for bright rooms; Sunset uses Daylight until Saskatoon's real sunset and Night after it.
- The keyboard focus ring is now a white outline with a dark gap behind it, so it never looks like "Jarvis means this".
- With reduced motion (and always on the strip) the orb holds still and says its state in a word under the core instead.
- The orb only animates what the graphics card can move cheaply, stops when the window is hidden, off screen or a game is on, and never moves on the strip.
- The resting screen now looks like Huw's standby: the particle orb with the dial, a big light mono clock with a small PM and the tiny date, the amber "waiting for your yes" pill, and Jarvis's line sitting just above the Rail with no box around it.
- When someone else is in the room, the resting screen shows nothing personal: no titles on the dial, no "where you stopped", no count of questions waiting.
- Nothing on the hub is deleted any more: closing a window, the 60-second timeout, a window that doesn't fit, a sixth window and CLEAR VIEW all put the thing on the Rail instead. Only "done" or "archive" removes it.
- Corner brackets now only mean "this wants you" (soon, your yes, overdue). The window Jarvis is talking about gets a brighter frame and a small crosshair instead, and the others step back slightly.
- Windows no longer slide under the caption line or the orb at the bottom of the screen.
- Windows have the Night look: square corners, a small caps label at the top left ending in its status ("PPS 7 // DUE"), a timer or index at the top right, and small notes hanging just under the frame. Each window leads with one big number, picture or title.
- New windows snap together in under a third of a second (corner brackets, then the frame, then the label), and you can use them straight away.
- Big numbers, the Now card, files, branch cards, background jobs and Jarvis's spoken line all use the Night look.
- Every tab now looks like the same JARVIS screen as Now: square glowing windows, small mono headings ("TODAY // 2 LEFT"), condensed caps titles, and tiny details hanging just outside the frames.
- Today leads with one big "next" window (the time, what it is, the room) and draws the day as an instrument: hour ticks, a bar for each block, and a "now" hand.
- The Life Map in Night is a glowing constellation instead of a potted plant: ice rings for branches, thin lines between them, and the branch Jarvis is working on (and the path to it) lit in cyan with a target mark. Daylight keeps the plant.
- Every state is shown as a shape, a colour and a word: done is a cyan disc with a check, "your yes" an amber square, due soon an amber diamond, moved or held back a dashed ring. Green now only means "system healthy" in Under the hood.
- Approvals in Activity start with the amber "your yes" square and what will happen; receipts read like a log with Undo; a "no" is a quiet row.
- Under the hood shows speed as instrument readouts (big mono numbers over little gauges with the target marked) and each connection's last sync in mono.
- The tabs are small outlined pills top-right, the status line is mono in the bottom-left, and the clock is large mono digits with a tiny spaced-out date.
- In Night, the day plant becomes a faint line drawing (the bloom when everything's done is cyan).
- On the phone the Rail is a 44 px row just above the tabs: gauges, counts and worst shapes, with the slot names when the screen is wide enough. An open slot fills the width on a solid sheet.
- On the phone, toasts sit just above the spoken line and the Rail, whatever their height, never over them or the tabs.
- PPS 7 on the phone opens at Q7 with a compact "Carry on at Q7" card at the bottom, within thumb reach.
- The home page is calm: the orb with its day dial, the big clock, one line, "waiting for your yes", the Rail and the tabs. Nothing pops up on it any more, whether or not windows are up. The phone keeps its own column, as before.
- "Put it on the hub" opens that thing's page in the hub instead of the Stage.
- The background is the faint dotted grid again (from the earlier version) instead of square grid lines.
- What Jarvis names while speaking now really lights up: brackets snap onto that window, its frame brightens, the small crosshair moves to it, and the matching Rail slot lights too.
- Every window's small heading ends in its state ("PPS 7 // DUE", "PPS 7 // Q7"), shows a page or time at the top right, and hangs "Added 9:31 pm" under the frame.
- Files in windows show their real page picture at its true size with the name and "Open it" beside it, instead of a stretched image.
- Jarvis no longer says "Got it", "Okay, I won't do that" or "Booked". A yes shows what was done in plain words ("Added 9 study blocks to your Google Calendar this week") with its Undo; a no simply closes the question and leaves a quiet line in Activity.
- "Due soon" now means the same everywhere: within 72 hours.
- On the other tabs the corner orb is small and sits inside the bottom band, so it never covers a button. The status line stays on one line.
- On the phone, what Jarvis says takes its own row above the Rail instead of floating over what you're reading.
- "Clear the screen" in the command bar now says everything goes to the Rail.
- Proposed changes on Today are answered with the same words as every approval: Yes, do it / Change it / No.
- Controls: no group has more than four rows. Look keeps the theme, motion and plants; a new Screens group holds the ambient screen and where Jarvis shows things.
- A branch page's button says "What's missing" instead of "More: gaps".
- On the Stage, the windows Jarvis isn't talking about sit back a little, as they do on the hub.
- The Night clock uses a lighter mono face, and Yes / No / Change it stay in reach when an approval's window is short.
- Once you've answered the "where you stopped" card, it stays away. If you close and come back within a few minutes, the PDF just opens at your spot.
- The card never offers two answers that mean the same thing: at the start of a set there's no "From the top" next to "Carry on". When Jarvis only knows the page, it says so plainly ("You stopped on page 3.") instead of "Somewhere on page 3."
- The reader only makes room for the card when the card really covers the top of the page (not on the phone, where it sits at the bottom).
- Wording: "Moved to 4 pm tomorrow." (no "No problem."), "Thursday afternoon is still open.", "Adds 9 study blocks to your Google Calendar this week", and the laundry reason no longer says "weekday mornings". Jarvis no longer says "Asking your calendar."
- The demo day has a done CHEM 142 pre-lab quiz due at 11:59 pm, so the day dial shows a deadline diamond.
- The status line says "Standby · Mic on" while the big orb rests, instead of "Listening · Balanced". "Quiet" or "Chatty" only shows when you've picked it.
- The Life Map at night has no little leaves on the stems, and every circle says something: how many things are due under it (School "4", amber when one is close), or its short name ("PR").
- The now card no longer starts with "GOOD AFTERNOON"; it opens with what you've done today and what's next.
- One approval has one label: "CALENDAR // YOUR YES", all caps. After the voice window closes it says "Tap to answer, or wake Jarvis and say it."
- The DEMO chip is a quiet grey label (amber only ever means "needs you"). At night "Go to…" is in the same caps as the tabs, and the corner "JARVIS" is gone (the orb says it).
- At night the Life page's breadcrumbs ("LIFE › SCHOOL") use the same small caps as every other label.

### Fixed
- The live demo now runs on the real clock (Saskatoon time, from Windows) and looks real at any time of day. Deadlines, classes and labs keep their real times (PPS 7 is due Monday at 8 pm, not "Tue 2:25 am"), and only the day moves to today. Weekdays in Jarvis's lines match the dates on screen.
- Today is planned again for the time you open it. At 8:30 am your classes are still ahead and next up is the 10 am lecture. At 10:30 pm they're done, the review and the PPS 7 block that didn't fit tonight show "Moved to 11:30 am tomorrow" and "Moved to 4:30 pm tomorrow", and next up is tomorrow's 10 am lecture. Study blocks never land in quiet hours or before 9 am.
- "Study protocol" only offers to move your review when it would come up while you study. Then it moves the review to the next free time (4 pm review to 5 pm). A waiting yes that would run out overnight now waits until 9 am.
- In the evening the demo story ends with tomorrow's first class. After midnight the greeting is "Evening", not "Afternoon".
- Nothing on the phone scrolls sideways at 320 px wide: the Rail's six slots, the tab names and window headings all fit.
- The yes on an approval can no longer scroll out of sight in a small window.
- The reader keeps your question. Take "Carry on at Q8" (or pick Q8 under "Another question"), sit as long as you like, close or reload: it reopens at Q8, and the hub says "PPS 7 · Q8", not "Page 3".
- Pressing Esc on the "where you stopped" card now leaves you in the PDF, so Tab and the arrow keys carry on there instead of jumping to the footer.
- The PDF's text layers are no longer extra blank tab stops.
- Double-clicking Close in the reader goes back once, not twice.
- "Status." now counts what the Homework slot it lights up shows: "Three due this week", not "Two" while the slot lists more.
- No more "Good night." or "That's it for tonight." in the afternoon. Before 6 pm you say "That's it for now." and Jarvis names what's next today (the review your yes just moved to 5 pm); "tonight" only after 6 pm, "Good night" only after 8 pm.
- The week-plan question no longer pulls the hub off the PDF you're reading. It goes to the Stage, Your yes on the Rail and the pill, with either "Where Jarvis shows things" setting. Its window is titled "Study plan".
- With a lecture or lab on now (or starting within 15 minutes) the demo plays a short story instead: "Leave now for MATH 133 in ARTS 101.", a one-line status, and you're off. Nothing gets planned over your class.
- Weekends: no lectures or labs on Saturday or Sunday. Classes, tutorials, quizzes and deadlines that come later in the week land on weekdays ("Mon 10:00 am · Lecture 22", "First up Monday: GE 122 at 10 am"), in the same order as before.
- Quiet hours: between 10:30 pm and 7:30 am Jarvis's lines are shown as captions, but he doesn't speak (except "Leave now").
- "Play it again" keeps your Controls settings (theme, earcons, "sir"), and a replay is told in other words instead of repeating itself word for word. Your spot in PPS 7 is saved with the real time when you stop.
- The little readouts round the orb ("THINK 420 MS", "CANVAS 2 MIN") no longer sit on top of the day dial: when the dial is there, they step aside.
- The orb's state word ("SPEAKING") sits on a small plate clear of the hash marks, and no text inside the orb is ever smaller than 12 px; the docked orb shows none (its amber ring says "waiting for your yes").
- The day dial's label is short and never cut off: "4:00 · GE 122 review" or "4:00 · GE 122 · ENGR 1A10" (course code, what it is, the room only when it's a room code), on up to two lines.
- Windows on the Stage never cut their content: at 1280×720 the big number, the approval's details, "Open it" and every "ADDED" line are whole. A window that's short of room drops its extras first; if it still doesn't fit, the oldest window steps aside into the Rail; if nothing can, it says "More" instead of hiding it.
- The week chart keeps every bar (each at least 2 px) and now labels the days under the bars (MON … FRI).
- Esc on the Stage closes the window you're in (it waits on the Rail) and moves you to the next one.
- On the Stage, receipts ("Study protocol on…") show bottom-left above the status line instead of over the first window.
- The Stage's hidden centre orb no longer keeps animating behind the windows.
- In Daylight, the edges of windows that sit back are visible again.
- Each window's close button says which window it closes.
- On a Stage opened in a browser on its own, "Open it" opens the hub at the right page instead of a blank one.
- After you click a Rail slot and press Esc, the focus ring shows on that slot again.
- Windows Jarvis isn't talking about stay readable at night: the "ADDED 3:40 PM" line under them and their edges no longer fade below the contrast rules. The contrast check now measures them too.
- The clock's small "PM" no longer glows.
- The Rail no longer jumps when a slot fills or the screen wakes: empty slots keep their place, and an empty one shows no "0".
- The open Rail panel is solid; the clock no longer shows through it.
- The five page dots under the home clock are gone (they repeated the tabs).
- On the phone, Tab reaches the Rail row before the tabs under it, matching the screen.
- The Stage window tells screen readers it is the Stage.

### Removed
- The Evening theme. If you had chosen Evening (or "follow Windows" with Windows in dark mode), you now get Night.
- The plant pot on the Night resting screen (Daylight keeps a small plant).

## 0.2.2 - Evening follows the real sunset (2026-11-14)
### Changed
- The "Sunset" theme now follows Saskatoon's real sunset and sunrise (worked out on the laptop, no internet needed) instead of a fixed 6 pm to 7 am, and it switches within a minute.

## 0.2.1 - Review fixes: a calmer Now, a Life Map that reads as a plant (2026-11-14)
### Changed
- The Life Map now looks like a plant: your life (or the branch you're in) is a pot, each branch is a leaf on a curved stem growing out of it, with its name beside it in Lexend, and the small leaves on a stem are the branches inside it.
- The Now screen never shows more than six windows, counting the Now card, and never scrolls: when it gets full, older windows get smaller and the oldest one that isn't pinned steps aside. The window Jarvis is talking about goes in the top-left spot, with anything waiting for your yes right after it.
- "Change it" opens a small box for what to change; the item stays on screen as "Changing…" until Jarvis asks again, and Jarvis keeps your words instead of asking "what should change?" again.
- Saying yes now shows "Booked." with an Undo button for a few seconds, and Undo buttons say how long they still work ("Undo · until 9:12 am tomorrow"). Saying no leaves a quiet line in Activity.
- Notices (toasts) now sit in the empty middle of the top bar on a wide window, clear of the windows and of the caption by the orb. At most two show at once; they wait while you point at them, and Esc closes one.
- Terracotta is kept for the one thing to do and the orb. Due countdowns, "waiting for your yes" counts (the Activity tab badge, the Life Map tags, the idle screen) and the "One thing" flag use the gold notice colours instead.
- Due countdowns read "2 d 4 h" instead of "2D 04H" (screen readers hear "2 days 4 hours left"), and clock times read "10:00 am" everywhere: Today, branch cards, quiet hours in Controls and the demo day.
- Long panel and window titles are plain sentence-case headings instead of shouting capitals; small capitals stay only for one- or two-word titles like "Next" and "Due".
- Every page header has the same shape: breadcrumb, title, then a one-line description, all on one left edge. Breadcrumbs are quieter (sentence case, no underline).
- The Now card skips anything a window already shows (Next, or the "One thing" flag), so nothing is said twice. With nothing else on screen it sits in the middle under a quiet clock.
- Windows are only as tall as what's in them. When they move to make room, they slide one after another instead of all jumping at once (not with reduced motion).
- On the idle screen, what Jarvis says shows under the big orb instead of in the corner.
- Branch cards in windows are shorter: what's due next (or a roll-up), the next event, one key fact, and Open.
- Fact cards are calmer: Edit, Pin as rule, Move and Forget sit behind one "…" button (Esc closes it); Confirm stays out on guesses.
- Beside the map, a branch page no longer repeats its branches as "Inside" chips; the list view still shows them.
- The waiting card in Activity uses the full width: what will happen on the left, the question and answers on the right.
- Empty screens are a plain card with one action; a brand-new Activity day hides the filter chips, and a free day in Today has one button to ask Jarvis to plan something.
- Switches and chosen options in Controls look "pressed in" like Pen Reader (card fill and a darker outline) instead of green. Data sources shows four sources; the rest are behind "2 more".
- The status line, receipt times and the command-bar hint are set in the reading font; the code font is only for tiny telemetry such as file paths.
- The orb, the strip and the status line all say "Listening" when Jarvis is at rest, and the strip no longer says "waiting for your yes" twice.
- The Activity filter is called "Life Map", like the view.
- Body text has a little more line spacing (15/23) and long text lines are capped at a comfortable width.
- The hub keeps at most five pushed windows on its side too, so it and the screen always agree on which window stepped aside.

### Fixed
- If you say yes to the week's plan straight away, the orb now goes back to resting instead of staying on "waiting for your yes" forever (even after a reload).
- Undo now really stops working when its time is up ("The undo window has passed."), and a plan you didn't answer in time can't be booked later ("This offer ran out. Nothing was done."); it shows as ran out at its expiry time.
- Pressing "Yes, do it" or Undo twice no longer gives an error; the second press just does nothing.
- Pin and close work on the first click, even on a window that isn't the one Jarvis is talking about.
- "Put it on the left/right" now actually moves the window on screen, and "bigger" makes a tall window wider instead of shorter.
- Reloading the hub no longer brings back old notices and the last spoken line; the read-back line also goes away as soon as you answer.
- Once the week's study plan is booked, it's no longer offered under "Ready when you are".
- With something waiting for your yes, the hub still goes back to the calm idle screen after two minutes; it says "1 waiting for your yes" there.
- "Waiting for your yes" tags on the Life Map now come from the actual approvals (on the branch and everything above it), so GE 122 no longer claims one when the plan is for Fall 2026.
- Map labels no longer shrink to unreadable sizes when the window is small or zoomed; when there isn't room, Life switches to the list and says why.
- The hub switches between the big, laptop and phone layouts as you resize the window (phone below about 720 px): Life redraws as map or list, windows on the phone fill the column, and nothing scrolls sideways down to 320 px wide.
- On the phone the orb sits at the end of the bottom tab bar instead of floating over text; each tab has an icon, and screen readers reach the view before the tabs, matching the screen.
- Keyboard focus is never lost: after yes, no or undo in Activity it lands on the receipt (or the next card), closing a window moves you to the next one, and after Enter or Backspace on the map it stays in the map.
- Switches, toggles and radio buttons now tell screen readers "on/off" and "checked/not checked" properly (they were blank when off). Theme, motion, chattiness and game mode are each one Tab stop: use the arrow keys (or Home/End).
- The chosen tab and the chosen option in Controls have a thin outline, and on the idle screen the tabs and the "Go to…" button stay easy to read in both themes.
- Searching for a setting in the command bar (Ctrl K, e.g. "pause memory") opens Controls at that row with its switch focused, and the bar tells screen readers how many results it found.
- Screen readers hear close-together messages joined up instead of cut off; a cleared caption is no longer read out, the strip no longer says "Showing …" for windows it never shows, and the map's description no longer says "You is in the centre".
- Memory's filters are plain toggle buttons for screen readers, every fact card is named by its statement, and its buttons say which fact they act on ("Edit: …").
- The mic button no longer stays green ("on") while the hub is offline; it shows the notice colours and can't be toggled until the hub is back.
- A proposed branch no longer repeats its reason, and the sentence ends with a full stop.
- Opening a scene without the hub running (the offline demo) follows the same rules as the hub, and its receipts carry your local time instead of UTC.
- Safer: the hub only answers to its own address (and your tailnet name, set with JARVIS_HUB_HOSTS), and settings only accept values that make sense.

### Added
- Scenes for the list view of Life (`life-outline`) and a crowded Now screen (`now-crowded`).

## 0.2.0 - The full hub: every view, in demo mode (2026-11-14)
### Added
- The Now screen: an orb and a big clock when idle, and windows that appear while Jarvis talks (up to six, with the now card always there).
- Today: your day as a timeline, proposed changes you can Apply, Tweak or Skip, and moved blocks without the guilt.
- The Life Map: you in the centre, your areas around you; click or press Enter on a branch and the map flies into it. At most seven branches show around the centre; the rest fold into +n more. Breadcrumbs and Back always work.
- Branches on the map are leaves on stems: bigger when busier, with a due ring and a badge like 2d when something is due soon, a dot when something needs your yes, dotted when Jarvis is only proposing the branch, and a lock for private ones.
- The same tree as a plain list (press L), built for the keyboard, screen readers and the phone.
- A page for every branch: status, what's due (with a countdown), what's next, open loops, key facts and recent changes, with people, files, decisions and the summary under More.
- Everything Jarvis knows: every fact with its source, a short list of guesses to review, conflicts, what it learned today, and switches to pause memory or go off the record. Unsorted items can be filed with one tap.
- Activity: what's waiting for your yes at the top, then everything Jarvis did with Undo, and what it held back.
- Controls: how chatty Jarvis is, quiet hours, focus and game mode, approvals and standing permissions, the look, data sources and privacy.
- Under the hood: how fast each stage is against its target, spend, voice credits, backups and whether Jarvis is getting to know you.
- A small always-on-top strip for Laptop A with a still orb, the status and what's next. It never animates and hides in game mode.
- A phone layout: tabs at the bottom, the now card, approvals and quick controls first, and Life as a list.
- A big, thin clock with the date and one next-up line for the idle screen.
- A small status line that always shows whether the mic is on, with one-tap mute.
- A command bar (Ctrl+K or /): type to jump to any view, branch, fact or setting, or just type to Jarvis.
- Fact cards: what Jarvis knows, where it came from, and Confirm, Edit, Pin as rule, Move and Forget on every one. Guesses are dotted-underlined and say what they were guessed from.
- Big-number cards for due countdowns (like 2D 04H) and stats.
- Small charts with every value labelled and the numbers available as a table.
- Receipts: what Jarvis did, why, from which sources, the result, and Undo with its time window.
- Approval cards that show what will happen first, then what Jarvis will ask, then Yes, No or Change.
- Branch cards: a short briefing for any part of your life (status, due, next, open loops).
- A one-line caption with its source near the orb whenever Jarvis speaks.
- Pen Reader's plants: a day plant that grows a leaf for each thing you finish, and blooms when the day is done.
- A day timeline with classes, study blocks and your own events, each with its source and a reason for its time.
- File previews with an Open it button.
- Working-on chips that show real progress for background jobs.
- Keyboard shortcuts for everything: Ctrl+K or / for the command bar, 1 to 5 for the tabs, Esc to go back, ? for the list, L and M for the Life view and the mic.
- Daylight, Evening, follow Windows, or Evening after sunset; motion can be full, reduced or off; plants can be turned off.
- After two idle minutes the hub returns to the calm orb-and-clock screen; any key, click or new window wakes it. Windows leave by themselves a minute after you last used them unless pinned.
- The demo day ends with a short note and a Play it again button; it can also be replayed from Controls or the command bar.
- Screen readers hear what Jarvis says, shows and asks, including anything waiting for your yes.
- Everything is wired together: tabs, the command bar, deep links like #/life/ge-122, Back, and a Go to… button in the corner.
- Speed checks: a pushed window reaches the screen within a frame or two, a branch page opens in well under a tenth of a second, the idle screen has exactly one gentle animation and pauses when hidden.
### Changed
- Tweak on a proposed change, turning a data source on or off, and branch settings now answer in demo mode.
- Anything waiting for your yes now sits at the top of the screen and is scrolled into view, and stays up until you answer.
- The ambient screen is larger on a full-screen display so it can be read from across the room, and it respects the Ambient screen switch.
- The demo day now starts from the beginning when the app opens.
- Window commands can be typed in the command bar the same way they are spoken: close that, clear the screen, bigger, keep that up.
### Fixed
- Actions are only accepted from the hub's own window, not from another site open in a browser.

## 0.1.0 - Foundation: the hub shell and a demo day (2026-11-14)
### Added
- A fixed description of every piece of information the hub shows (the now card, branches, facts, receipts, approvals, windows and more), with a realistic demo day as the example.
- A built-in demo day (arriving home, a debrief, "pull up PPS 7", "what's going on with GE 122?", "plan my week") so every screen can be used before the real Jarvis exists.
- Jarvis Hub opens as its own Windows app (like Pen Reader), with Start-menu shortcuts for the normal window, the full-screen ambient screen and the small strip.
- An installer, `JarvisHub-Setup.exe`, is built and published automatically whenever a new version is released.
- The hub's look is set in one place: Pen Reader's warm paper colours, terracotta and plant greens, in a Daylight and an Evening theme.
- A check that stops stray colours from sneaking in outside that one file.
- Live updates: what Jarvis does shows up on screen as it happens.
- The hub's frame: five tabs (Now, Today, Life, Activity, Controls), a main area, a status line and a corner for the orb, with Back that always works.
- Any screen state can be opened directly with a `?scene=` address, for checking and screenshots.
- Automatic checks on every change: the hub is opened in a real browser, every screen state is loaded in both themes, and every colour pair is tested for readable contrast.
- The orb, Jarvis's face: ready, listening, thinking, speaking, waiting for your yes (with a countdown), muted and offline, each with a still version when motion is turned down.
- Windows: the panels Jarvis puts on screen while it talks, with corner brackets on the one it means, a pin to keep one up and a close button.
- Window rules: up to six windows on a tidy grid, each leaves after a minute unless you pin it, "close that", "bigger" and "clear the screen" work by voice or keyboard, and a layout can be saved to a branch.
- Private (tier 2) items never appear on a screen other people can see.
- The now card: what you finished today, what's next, one thing to watch (with a "Why?" that shows its source), what's ready, and what Jarvis isn't sure about.
- Five tabs (Now, Today, Life, Activity, Controls) and matching page dots. The only badge is the number of things waiting for your yes.
- Source chips on every claim (You, Canvas, Syllabus, Calendar and so on) that open to show the actual evidence, and confidence in words: Sure, Likely, Guess.
- Friendly empty states, plain error messages that say what to do next, and short notices that leave on their own.

## 0.0.1 - repository set up
- Folder layout, build plan, design docs, the `jarvis-release` and `jarvis-build` skills, and Pen Reader
  reference files for the hub build.
