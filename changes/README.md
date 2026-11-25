# Change fragments

Every work package adds one file here named after its ID, for example `C01.md`:

```
### Added | Changed | Fixed | Removed
- One line per change, in plain words, written for De Wet (what he will notice), not for developers.
```

At release time the `jarvis-release` skill moves all fragments into CHANGELOG.md under the new version and
deletes them. Never edit CHANGELOG.md directly in a work package.
