---
name: jarvis-release
description: Use for every commit and every release in De Wet's Jarvis repo (Thelaw247/jarvis): commit message format, change fragments, version bumps, CHANGELOG, tagging and publishing the Windows installer, so each one looks and works the same. Use when committing work, merging a work package, cutting a release, shipping a hotfix, or when he asks to "release", "ship", "publish a new version" or "commit this".
---

# Jarvis commits and releases

One way to commit and one way to release, so every change in the Jarvis repo reads the same and every
release ships the same way. Modeled on Pen Reader's release flow (VERSION file → GitHub Actions on Windows →
installer → GitHub Release).

## Part 1: commits

### Before committing
1. Run the tests: `python -m pytest` (and the e2e smoke if UI files changed). Never commit a red build to `main`.
2. Check you only touched the paths your work package owns (docs/hub-build-plan.md §6–7). Shared files
   (`ui/components/index.js`, `ui/index.html`, `CHANGELOG.md`, `VERSION`) are the overseer's.
3. Hex colours only in `ui/tokens.css` (`python tools/hexlint.py` once it exists).
4. Add or update your change fragment `changes/<WP-ID>.md` (format in `changes/README.md`).

### Message format
```
<type>(<scope>): <what changed, in the imperative, ≤ 72 chars>

<why, in 1–4 plain sentences, if it isn't obvious>

WP: <work package ID, e.g. C01>           (omit for overseer-only changes)
Co-Authored-By: <the Claude model that wrote it> <noreply@anthropic.com>
```
- **type**: `feat` (something new he can use) · `fix` (something broken now works) · `design` (look only)
  · `refactor` (no behaviour change) · `test` · `docs` · `build` (packaging, installer) · `ci` · `chore` · `release`.
- **scope**: `hub` (server/demo), `ui` (shell/core), `comp-<name>` (a component), `view-<name>`, `contracts`,
  `tokens`, `desktop` (launcher/installer), `skills`, `plan`.
- One logical change per commit. Small commits are fine; mixed commits are not.
- Write for a human: "feat(comp-orb): add the waiting-for-your-yes countdown ring", not "update orb.js".
- Contract changes: scope `contracts`, and say the new contract version in the body.

### Branches and merging
- Work packages: branch `wp/<ID>` (e.g. `wp/C01`) in its own worktree under `.worktrees/`.
- Only the overseer merges into `main`, with `git merge --no-ff wp/<ID> -m "merge(<scope>): <WP title>"`,
  then adds any shared-file lines, runs the full test suite, and pushes. `main` must always be green.
- Never force-push, never rewrite pushed history, never commit secrets, keys, `.env`, logs or personal data.

## Part 2: releases

### When
- End of a phase gate (G0 → v0.1.0, G4 → v0.2.0, phase N Night HUD → v0.3.0, H5 live mode → v0.4.0), or a fix he needs now (patch).
- Versioning: `0.MINOR.PATCH` until live. MINOR = a phase, a new view or anything he'd call new. PATCH = fixes only.

### Steps (do all of them, in order)
1. `git checkout main && git pull --ff-only`; confirm CI is green on the latest commit.
2. Run the full checks locally: `python -m pytest`, the e2e smoke, `tools/contrast.py`, `tools/hexlint.py`.
3. Decide the version (rules above). Write it to `VERSION` and to `version` in `pyproject.toml`.
4. Compile the changelog: create `## X.Y.Z - <short title> (<YYYY-MM-DD>)` at the top of `CHANGELOG.md`,
   group the `changes/*.md` lines under **Added / Changed / Fixed / Removed**, merge duplicates, keep his
   plain-language wording, then delete the used fragments (keep `changes/README.md`).
5. Update `docs/work/STATUS.md` (what this release contains, which gate it closes).
6. Commit exactly: `release: vX.Y.Z - <short title>` (body: the gate closed and the 3 biggest changes).
7. Push `main`. The `release.yml` workflow (windows-latest) runs the tests, builds `JarvisHub-Setup.exe`
   with PyInstaller + Inno Setup, and creates the GitHub Release `vX.Y.Z` with the installer attached.
8. Verify: `gh api repos/Thelaw247/jarvis/releases/tags/vX.Y.Z --jq '.assets[].name'` lists
   `JarvisHub-Setup.exe`. If the workflow failed, fix forward with a PATCH release; never delete a release
   that he may have installed.
9. Tell him in two lines: the version, what's new, and where to download it.

### Release notes template (used by release.yml; keep it the same every time)
```
Download **JarvisHub-Setup.exe** and run it. Python is not needed.
Windows may warn that the installer is from an unknown publisher (it isn't code-signed): choose
**More info → Run anyway**.

What's new in X.Y.Z:
- <3–6 lines from the changelog, plain words>
```

### Hotfix
Branch `fix/<short-name>` from `main`, smallest possible change + a test that would have caught it,
fragment, overseer merge, PATCH release with the steps above.

## Never
- Release with failing tests or a failing gate.
- Bump VERSION in a work-package branch.
- Edit an existing release's installer in place; ship a new PATCH instead.
- Put API keys, tokens, his email, or anything from his memory database in commits, logs or release notes.
