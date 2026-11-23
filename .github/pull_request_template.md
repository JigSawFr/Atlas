<!-- Title: a conventional commit with a scope (feat(platforms): …, fix(links): …). It becomes the squash subject. -->

## 🎯 At a glance

<!-- 2 to 3 sentences for someone who has not seen the diff: what changes and what it gives. -->

## 💡 Why

<!-- The need behind it. Link the issue it closes (Closes #N). -->

## 🔧 What changes

<!-- A short list of the real changes, not a copy of the diff. -->
-

### 🖼️ Before / After

<!-- Only when the site or the explorer changes. Delete the table otherwise. -->

| Before | After |
|---|---|
| | |

## ✅ Checked

<!-- CI already runs the unit tests, actionlint on the workflows and the schemas check against the data branch: not repeated here. Say what was run beyond CI, and what could not be checked. -->

- [ ] A new field keeps `schema` and is in `tools/schemas.py` and the README (a field that changes meaning bumps the schema)
- [ ] A new platform or source is in the README's tables and in `plans/atlas/` if it is still open

Merge: squash
