---
name: run-job-applications
description: Discover, normalize, deduplicate, rank, and track job opportunities; expand selected company campaigns into roles; analyze a chosen JD against a read-only Base Career Vault; create a truth-preserving tailored resume; show an application dashboard; and automatically learn ranking weights from recorded outcomes. Use for BOSS 直聘岗位搜索、飞书或腾讯校招表筛选、公司/岗位选择、JD 匹配、定向简历、投递记录、投递后台、结果跟进、推荐权重学习或恢复。
---

# Run Job Applications

Run the job-search-to-outcome loop while treating the Base Career Vault as read-only.

## Non-negotiable boundaries

- Never create or modify a Base revision.
- Bind every Job Session to the latest Base revision at session creation.
- Store JD-specific discoveries only in that session's overlay.
- Use a new Base revision only after the user separately invokes `$manage-career-vault`.
- Never fabricate experience, metrics, dates, titles, credentials, or skill depth.
- Record an application only after the user actually submits or confirms a submission.
- Let learning change ranking weights only; never let it change facts or hard eligibility.

Use Markdown as the canonical visible output. Generate DOCX through the available document skill and PDF only when requested.

## Locate the suite and data

Resolve the plugin root as the directory two levels above this `SKILL.md`. Default the user's data directory to `career-data/` in the current workspace.

```bash
python3 <plugin-root>/scripts/pipeline.py --db <career-workspace>/career.db init
```

## Route the request

- For opportunity search or deduplication, read [references/opportunity-policy.md](references/opportunity-policy.md).
- For JD analysis, experience discovery, or resume generation, read [references/tailoring-policy.md](references/tailoring-policy.md).
- For application tracking, dashboard, outcome sync, or scoring changes, read [references/tracking-learning-policy.md](references/tracking-learning-policy.md).
- For Notion setup, synchronization, retries, or mapping repair, read [references/notion-sync-policy.md](references/notion-sync-policy.md).

## Configure the connected Notion backend

This suite uses the signed-in Notion connector rather than a stored API token.
On first use for this database, configure the local target:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  notion-config --input <plugin-root>/assets/notion-target.json
```

SQLite is the fact source. Notion is a user-facing synchronized projection.
Local mutations always succeed or fail independently of connector availability.

## Workflow

### 1. Discover and normalize

Search requested sources:

- Use the installed `boss-cli` skill for BOSS. Check authentication before any BOSS command. Keep BOSS requests sequential.
- Read the configured Feishu and Tencent recruitment sheets using an available logged-in browser capability.
- Treat company career sites as the highest-authority source.
- Do not perform mutating BOSS actions unless the user explicitly requests them.

Capture source rows into JSON, then import them:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  import --source <boss|feishu|qqdocs|company_site|manual> \
  --input <records.json>
```

The importer auto-merges exact canonical matches, preserves every source record, and only marks fuzzy candidates.

### 2. Present the choice

Export one Markdown report:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  opportunities --markdown <career-workspace>/opportunity-report.md
```

Keep two sections:

- `JOB`: concrete positions.
- `CAMPAIGN`: company recruitment waves.

Checkpoint 1: ask the user to choose a concrete job or a company campaign.

If they choose a campaign, inspect only that selected company's official career site, import concrete jobs as `JOB`, relate them to the campaign in analysis, and ask the user to choose one. Never tailor directly against a campaign summary.

Persist the parent-child relationship:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  opportunity-relate --campaign <campaign-id> --job <job-id>
```

### 3. Create an isolated Job Session

Create the session only after a concrete job is selected:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  session-create --opportunity <job-id>
```

Record the returned session ID and Base revision ID in `job-analysis.md`.

### 4. Analyze and deepen

Separate:

- Strategic fit: whether the opportunity is worth applying to.
- Document fit: how well the available verified evidence covers the JD.

Ask targeted branching questions only for important gaps. Save answers to `session-overlay.md`, not Base:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  session-overlay --session <session-id> --input <session-overlay.md>
```

Build `match-plan.md` with selected facts, omitted facts, allowed reframings, gaps, and evidence references.

Store the normalized 0–1 scoring features after analysis so outcome learning uses actual evidence:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  opportunity-score --opportunity <job-id> --input <features.json> \
  --hard-eligible <true|false|unknown>
```

Checkpoint 2: require user approval of the Match Plan.

### 5. Generate and verify

Use the installed `resume-tailoring` skill as the resume-generation engine, with these overrides:

- Supply only the bound Base revision plus current session overlay.
- Do not run its library-update phase.
- Do not promote generated bullets or discoveries to Base.
- Treat `resume.md` as canonical.

Create `evidence-map.json` from the shared template and validate it:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  evidence-check --mapping <evidence-map.json>
```

Do not finalize while the check fails. Allow at most two automatic revision passes before presenting unresolved claims.

Register each generated artifact:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  resume-add --session <session-id> --format md --path <resume.md>
```

Checkpoint 3: ask the user to approve the final resume.

### 6. Track the actual application

After confirmed submission:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  application-create --opportunity <job-id> \
  --session <session-id> --resume <resume-artifact-id>
```

Record every later outcome. The command automatically invokes learning when the event is eligible:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  application-event --application <application-id> \
  --stage <stage> --note "<evidence or context>"
```

### Synchronize queued changes to Notion

After importing or scoring opportunities, creating an application, recording an
event, or changing the active scoring version, perform this best-effort loop:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db notion-plan --limit 50
```

For each `ready: true` operation:

1. Use the Notion connector to query the supplied `data_source_id` for
   `identity_property = identity_value` unless `notion_page_id` already exists.
2. Update the mapped/existing page, or create one if no match exists, using the
   supplied `properties` exactly. Omitted properties must remain unchanged.
3. Never include `人工备注`, `下一步行动`, or `下一步时间` in an update.
4. Confirm success locally:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  notion-ack --queue <queue-id> --page-id <page-id> --page-url <page-url>
```

If the connector call fails:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  notion-fail --queue <queue-id> --error "<concise error>"
```

Run `notion-plan` again after acknowledgements. Parent pages may have unblocked
previously `ready: false` relations. Stop when `operation_count` is zero. Do not
block the local application workflow on a Notion failure.

### 7. Show the backend

Start the local read-only dashboard:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db dashboard
```

Open the printed local URL only when the user asks to view it. The dashboard
shows overview, opportunities, application snapshots, resumes, current stages,
scoring weights, and Notion queue health.

Export a portable Markdown log when requested:

```bash
python3 <plugin-root>/scripts/pipeline.py \
  --db <career-workspace>/career.db \
  applications --markdown <career-workspace>/application-log.md
```

## Graceful degradation

- If BOSS is unavailable, continue with other sources and report the missing source.
- If a sheet cannot be read, preserve its last successful data and mark freshness.
- If no Base revision exists, stop tailoring and route to `$manage-career-vault`.
- If company research is sparse, use the JD only and label the limitation.
- If fewer than three eligible outcomes exist, keep baseline weights and show that learning is collecting samples.
- If DOCX/PDF generation fails, preserve verified Markdown and report the rendering error.

## Required visible outputs

- `opportunity-report.md`
- `jobs/<job-id>/job-analysis.md`
- `jobs/<job-id>/session-overlay.md`
- `jobs/<job-id>/match-plan.md`
- `jobs/<job-id>/resume.md`
- `jobs/<job-id>/evidence-report.md`
- `application-log.md` on request

Keep raw synchronization records and weight history in SQLite rather than generating extra reports.
