# Notion Connector Synchronization

Use the Notion connector as a projection of local SQLite state. SQLite remains
the source of truth for opportunities, applications, events, and scoring
profiles.

## Safety boundaries

- Never store a Notion API token in the plugin, database, shell history, or
  generated files.
- Never overwrite the `人工备注`, `下一步行动`, or `下一步时间` properties.
- Upsert by the stable local ID property before creating a page.
- A connector failure must not roll back or block a successful local write.
- Acknowledge a queue item only after the connector confirms the page write.
- Keep one Notion page per `(entity_type, local_id)`.

## Upsert loop

1. Configure the local database once with `assets/notion-target.json`.
2. Run `notion-plan`.
3. Process only operations where `ready` is `true`.
4. If `notion_page_id` is present, update that page.
5. Otherwise query the target data source by `identity_property` and
   `identity_value`.
6. If exactly one page exists, update it. If none exists, create it. If more
   than one exists, fail the queue item and report a duplicate.
7. Resolve relation properties from the page URLs already included in
   `properties`.
8. Run `notion-ack` with the returned page ID and URL.
9. Run `notion-plan` again because newly acknowledged parents may unblock
   dependent operations.
10. Stop when there are no operations. On an external error, run
    `notion-fail`; continue local work and surface the failure.

Do not try to create a dependent page while `ready` is false. Opportunity
campaigns must be synced before their child jobs; opportunities before
applications; applications before events.

## Local-to-Notion mapping

| Local entity | Notion database | Stable identity |
|---|---|---|
| `opportunity` | 岗位池 | 本地机会ID |
| `application` | 投递记录 | 本地投递ID |
| `application_event` | 进展事件 | 本地事件ID |
| `scoring_profile` | 评分版本 | 版本号 |

The application database keeps the user's legacy `投递状态` and also receives
the full local enum in `标准阶段`.
