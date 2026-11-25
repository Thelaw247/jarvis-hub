# Agent permission asks (R3)

An agent's permission request is an ordinary approval (`contracts/approval`, `category: "agent"`) on the same
`<jv-approval-card>`: consequences first, the read-back the hub made in code ("Claude wants to create 'Stand
v1.f3d' in Fusion Projects. Allow?"), the same voice grammar. Its answers are **Allow · Deny**, plus **Allow for
this task** once the task has asked something similar a second time (`approve` with `args.scope = "task"`).

`agent-ask.js` registers those answers with the approval card's answers hook (`registerAnswers` in
`approval-card.js`). No CSS of its own: it is the approval card.
