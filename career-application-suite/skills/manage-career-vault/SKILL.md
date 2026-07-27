---
name: manage-career-vault
description: Build, inspect, deepen, edit, version, export, or restore a user-controlled Base Career Vault containing verified career facts and evidence. Use when the user asks to 初始化、建立、完善、深挖、修改、查看或恢复 Base 经历库、全量经历库、职业经历事实库，或明确要求把某段经历长期保存。 This is the only Career Application Suite skill allowed to write Base career facts.
---

# Manage Career Vault

Maintain the authoritative, versioned source of career facts. Keep this workflow independent from any specific job description.

## Enforce the ownership boundary

- Allow this skill alone to create a Base revision.
- Never let `run-job-applications`, a Job Session, a tailored resume, or an application result write Base.
- Treat a tailored wording as presentation, not a new fact.
- Require explicit user approval of a diff before creating every revision.
- If the user arrived from a JD session, re-evaluate the proposed fact without using the target JD as the truth standard.

Read [references/evidence-policy.md](references/evidence-policy.md) before adding, deepening, or editing facts.

## Locate the suite

Resolve the plugin root as the directory two levels above this `SKILL.md`. Run:

```bash
python3 <plugin-root>/scripts/pipeline.py --db <career-workspace>/career.db init
```

Default `<career-workspace>` to `career-data/` in the user's current workspace. Do not store personal career data inside the installed plugin.

## Choose the operation

### Initialize

Use when no Base revision exists.

1. Collect user-approved source material: existing resumes, portfolio notes, project files, and narrated experiences.
2. Extract facts while retaining source provenance.
3. Build one chronological vault using the shared [career vault template](../../assets/templates/career-vault.md).
4. Assign stable `EXP-*`, `FACT-*`, and `EV-*` identifiers.
5. Mark uncertainty rather than guessing.
6. Present the complete draft and unresolved questions.
7. After approval, snapshot it:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  vault-add --input <career-workspace>/career-vault.md \
  --summary "Initialize Base Career Vault"
```

### Inspect

Show the latest Base revision, its revision ID, unresolved facts, and evidence gaps. Do not create a revision.

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db vault-history
```

### Deepen one experience

1. Ask the user to select one `EXP-*`.
2. Explore context, ownership, constraints, actions, decisions, collaborators, scale, outcomes, and evidence.
3. Separate observed facts from interpretations and proposed resume wording.
4. Update only that experience in a working copy.
5. Show a focused diff.
6. Create a revision only after approval.

Do not optimize the questioning for a current JD. The result must remain generally reusable.

### Edit

1. Identify exact IDs being changed.
2. Preserve history; never overwrite an earlier revision.
3. Show additions, removals, and changed evidence links.
4. Ask for approval.
5. Snapshot the approved full Markdown file as a new revision.

### Export or restore

Exporting does not change the active history:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  vault-export --revision <revision-id> --output <output.md>
```

To restore, export the old revision, show it to the user, and create a new revision whose content matches that historical revision. Never delete intervening history.

## Deep-dive question order

Ask only the smallest useful branch at a time:

1. What was the situation and why did it matter?
2. What did the user personally own?
3. What actions and decisions did they make?
4. What constraints or trade-offs existed?
5. What changed, and how is it measured?
6. What evidence supports each important statement?

Stop when further questioning no longer increases factual confidence.

## Output contract

- Keep `career-vault.md` as the human-readable canonical export.
- Keep revision metadata in SQLite.
- Use Markdown for all review and diffs.
- Never expose private source material beyond the user's workspace.
- Report revision ID and content hash after each approved update.
