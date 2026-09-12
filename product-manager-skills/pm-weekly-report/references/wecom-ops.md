# 企微归档（可选）

主输出是 Obsidian 一篇 Markdown。只有用户明确说「同步到企微 / 写入归档表」时才走这里。

归档是已有智能文档，不要新建：

- url: `https://doc.weixin.qq.com/smartpage/a1_AVkATwZoAJ4CNzyGbuE9RRoqZ1glt?scode=AFwAdwdNAGMxQif45FAVkATwZoAJ4&p=1jigjo`
- docid: `a1_AVkATwZoAJ4CNzyGbuE9RRoqZ1glt`

先检查：

```bash
wecom-cli --version
wecom-cli auth show --status
```

`unauthorized` 时让用户在本机执行 `wecom-cli auth init`，不要代跑扫码。

## 读结构

```bash
wecom-cli smartpage pages get --json '{"docid":"a1_AVkATwZoAJ4CNzyGbuE9RRoqZ1glt"}'
wecom-cli smartpage databases get --json '{"docid":"a1_AVkATwZoAJ4CNzyGbuE9RRoqZ1glt"}'
```

`page_id` / 表名 / 字段名只许从回包取。若报错带 `help_message`，必须把该字段逐字原样给用户。

## 写入：智能表（优先）

页面里已有「周次 / 这周已做 / 下周待做 / 行业动态」这类子表时，用智能表追加或更新记录。命令以 `wecom-cli smartpage databases --help` 和 `wecom-cli smartsheet records --help` 为准。

- 先按「周次」查有没有本周行
- 没有就 add 一行
- 有就 update 这周已做、下周待做、行业动态三列

「这周已做」「下周待做」分开两列，保持 [weekly-format.md](weekly-format.md) 的编号正文；行业动态另写一列。

## 写入：文档页 markdown 表（兜底）

没有智能表时，读取目标页 markdown：

```bash
wecom-cli smartpage pages get --json '{"docid":"a1_AVkATwZoAJ4CNzyGbuE9RRoqZ1glt","page_id":"<page_id>","content_type":"markdown"}'
```

维护一张表：

```markdown
| 周次 | 这周已做 | 下周待做 | 行业动态 |
|---|---|---|---|
| 2026-09-07 ~ 09-11 | *这周已做<br>1.… | *下周待做<br>1.… | 1.… |
```

同一周已有行就改那一行；没有就追加。改完写到 `outputs/`，再：

```bash
wecom-cli smartpage pages overwrite --json '{"docid":"a1_AVkATwZoAJ4CNzyGbuE9RRoqZ1glt","page_id":"<page_id>","content_type":"markdown","file_path":"outputs/archive-page.md"}'
```

overwrite 前必须先读到现有正文，只改表，不要清掉页上其他内容。单元格换行用 `<br>`。
