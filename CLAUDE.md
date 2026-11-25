# Jarvis repo: rules for every Claude session and agent

- Read `docs/hub-build-plan.md` before changing anything. It says which work package owns which paths.
- Building a work package: follow `.claude/skills/jarvis-build/SKILL.md`.
- Committing, merging or releasing: follow `.claude/skills/jarvis-release/SKILL.md` exactly.
- Only the overseer edits shared files: `ui/components/index.js`, `ui/index.html`, `CHANGELOG.md`, `VERSION`,
  `docs/work/STATUS.md`.
- Hex colours live only in `ui/tokens.css`. Data flows only through `contracts/`.
- `docs/design/` mirrors the Claude Project docs; propose
  design changes to De Wet rather than editing them.
- Never commit secrets, keys, `.env`, logs, or personal data. Jarvis's memory database never goes in git.
- Latency and calm matter: feedback ≤ 100 ms, motion only for state, nothing animates on Laptop A's strip.
