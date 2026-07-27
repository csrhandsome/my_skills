# Opportunity Sources and Deduplication

## Default sources

- BOSS 直聘 through `boss-cli`
- Feishu campus recruitment sheet:
  `https://dcnb3gfq7cll.feishu.cn/wiki/C4X6wYOFqiYzcxk5gipcCem5nwe?from=from_copylink`
- Tencent Docs campus recruitment sheet:
  `https://docs.qq.com/smartsheet/DRHVEc05MbE5CYUZa?tab=t9HHQn&viewId=vasGeq`
- Selected company official career sites

Read sources without changing them. Preserve source URL, external ID, fetched time, and raw row.

## Entity types

### JOB

A concrete position with a job title and usable JD.

### CAMPAIGN

A company recruitment wave or announcement that may contain many jobs.

Never merge `JOB` and `CAMPAIGN`. Relate a selected campaign to its official jobs as parent and child.

## Merge rules

Auto-merge only:

- Same entity type
- Same normalized company
- Same normalized title or recruitment wave
- Compatible location for jobs

For near matches:

- Keep both entities.
- Set `possible_duplicate_of`.
- Show the warning in Markdown.
- Require user confirmation before any manual merge.

Do not merge:

- Different roles at the same company
- Different cities when location is material
- Different campus waves
- Internship and full-time roles

## Field authority

Prefer:

1. Company official career site
2. Full BOSS JD
3. Feishu or Tencent sheet

Use the freshest explicit date for deadlines. Surface conflicts instead of hiding them. Retain all source records even after an exact merge.

## Presentation

Sort and show concrete jobs separately from campaigns. Include:

- Canonical ID
- Company
- Position or wave
- Location
- Deadline
- Learned ranking score
- All contributing sources
- Possible-duplicate warning
