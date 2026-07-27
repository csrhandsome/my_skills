# Career Application Suite

一个面向求职全流程的 Codex 插件：

- 建立独立、可验证、可版本回溯的 Base 经历库
- 同时搜索 BOSS、飞书校招表、腾讯校招表和公司官网
- 对不同来源的岗位和招聘批次进行标准化、去重和排序
- 基于指定 JD 进行经历匹配、针对性深挖和简历生成
- 保存实际投递时的 JD、Base 版本和简历快照
- 在本地后台查看投递进度
- 将岗位、投递、事件和评分版本同步到指定 Notion 页面
- 根据真实投递结果自动调整后续岗位推荐权重

## 当前接入状态

| 项目 | 状态 |
|---|---|
| 插件版本 | `0.2.0` |
| 本地事实源 | `career-data/career.db` |
| Notion 后台 | [Job](https://app.notion.com/p/32099adbdb7b80a89749c535aad52790) |
| 同步方式 | SQLite 队列 → Codex Notion 连接器 |
| 已接入数据库 | 岗位池、投递记录、进展事件、评分版本 |
| Token | 无需在本地保存 |

本地数据库已经完成目标配置，评分基线 v1 已通过 Upsert 实际同步。
后续使用 `$run-job-applications` 时，Codex 会在本地写入成功后处理
Notion 队列；连接器暂时不可用时，本地流程仍会继续。

## 核心边界

插件将职业经历分为三个相互隔离的层级：

| 层级 | 用途 | 是否可修改 Base |
|---|---|---:|
| Base Career Vault | 长期有效的经历事实与证据 | 仅 `manage-career-vault` 可以 |
| Job Session Overlay | 针对某个 JD 补充的临时事实 | 否 |
| Resume Wording | 某份简历中的表达方式 | 否 |

岗位定制、简历生成和投递结果都不能自动修改 Base 经历库。需要调整 Base 时，必须单独调用 `manage-career-vault`，查看 Diff 并确认新版本。

## 包含的 Skill

### `manage-career-vault`

用于：

- 初始化全量 Base 经历库
- 导入和整理已有简历
- 深挖单段经历
- 修改事实或证据
- 查看版本历史
- 导出或恢复历史版本

调用示例：

```text
使用 $manage-career-vault，读取我的现有简历，建立 Base 经历库。
```

```text
使用 $manage-career-vault，深挖 EXP-0003。
修改前先显示 Diff，确认后再建立新版本。
```

### `run-job-applications`

用于：

- 多来源岗位发现
- 岗位和招聘批次去重
- 公司官网岗位展开
- JD 分析与定向经历追问
- Resume Builder
- Evidence Guard
- 投递记录与后台查看
- Notion 后台同步与失败重试
- 根据结果自动调整评分权重

调用示例：

```text
使用 $run-job-applications，同时搜索 BOSS、飞书和腾讯校招表，
筛选适合我的 AI 产品经理岗位。
```

```text
使用 $run-job-applications，分析岗位 #18。
读取 Base 经历库，但不要修改 Base，确认 Match Plan 后生成简历。
```

```text
使用 $run-job-applications，把投递 #5 更新为一面，
并根据新结果更新推荐权重。
```

```text
使用 $run-job-applications，检查 Notion 同步状态并重试失败项。
```

> `$skill-name` 形式需要先在 Codex 中加载或安装本插件。未安装时，可以直接使用下面的 CLI。

## 目录结构

```text
career-application-suite/
├── .codex-plugin/
│   └── plugin.json
├── skills/
│   ├── manage-career-vault/
│   └── run-job-applications/
├── scripts/
│   ├── pipeline.py
│   ├── store.py
│   ├── notion_sync.py
│   ├── dashboard.py
│   ├── evidence_guard.py
│   ├── adapters/
│   │   └── boss.py
│   └── tests/
│       └── test_core.py
└── assets/
    ├── notion-target.json
    └── templates/
```

## 运行要求

- Python 3.9 或更高版本
- 核心数据库、后台和评分模块只使用 Python 标准库
- 使用 BOSS 时需要安装并登录 `boss-cli`
- 读取飞书或腾讯文档时需要可用的登录浏览器能力
- 同步后台时需要 Codex 中已连接的 Notion 插件
- 生成定向简历时建议安装 `resume-tailoring`
- 生成 DOCX/PDF 时需要相应的文档生成能力

BOSS 登录状态检查：

```bash
boss status
```

需要时登录：

```bash
boss login
```

不要在聊天、日志或 Markdown 中保存 BOSS Cookie。

## 快速开始

进入插件目录：

```bash
cd "/Users/qiuchan/Library/Mobile Documents/com~apple~CloudDocs/Code/my_skills/career-application-suite"
```

建议把个人数据保存在插件目录之外或单独的 `career-data/` 中：

```text
career-data/
├── career.db
├── career-vault.md
├── opportunity-report.md
├── application-log.md
├── imports/
└── jobs/
```

初始化数据库：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  init
```

接入当前 Notion 后台（无需在本地保存 Token）：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  notion-config \
  --input assets/notion-target.json
```

确认接入状态：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  notion-status
```

看到 `"configured": true` 且 `failures` 为空，即表示本地目标配置正常。

## 1. 建立 Base 经历库

复制并填写模板：

```text
assets/templates/career-vault.md
```

Base 中使用稳定 ID：

- 经历：`EXP-0001`
- 事实：`FACT-0001`
- 证据：`EV-0001`

保存第一个版本：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  vault-add \
  --input career-data/career-vault.md \
  --summary "初始化 Base 经历库"
```

查看版本历史：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  vault-history
```

导出指定版本：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  vault-export \
  --revision 1 \
  --output career-data/career-vault-v1.md
```

恢复旧版本时不要删除后续历史。先导出旧版本，确认内容，再将它保存为一个新的 Base Revision。

## 2. 搜索和导入岗位

### BOSS

搜索 BOSS 并直接导入数据库：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  boss-search "AI 产品经理" \
  --boss-arg=--city \
  --boss-arg=上海 \
  --boss-arg=--exp \
  --boss-arg=在校/应届
```

BOSS 请求必须顺序执行，不要并发绕过平台限流。

### 飞书校招表

默认数据源：

```text
https://dcnb3gfq7cll.feishu.cn/wiki/C4X6wYOFqiYzcxk5gipcCem5nwe?from=from_copylink
```

Codex 读取页面后，将记录保存为 JSON：

```json
[
  {
    "company": "示例科技",
    "title": "2027 届秋招",
    "recruitment_type": "秋招",
    "application_start": "2026-07-20",
    "application_deadline": "2026-09-01",
    "location": "上海",
    "url": "https://example.com/campus",
    "kind": "CAMPAIGN"
  }
]
```

导入：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  import \
  --source feishu \
  --input career-data/imports/feishu.json
```

### 腾讯校招表

默认数据源：

```text
https://docs.qq.com/smartsheet/DRHVEc05MbE5CYUZa?tab=t9HHQn&viewId=vasGeq
```

导入：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  import \
  --source qqdocs \
  --input career-data/imports/qqdocs.json
```

### 公司官网

只在用户选择某家公司后展开官网岗位，避免全量抓取所有公司。

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  import \
  --source company_site \
  --input career-data/imports/company-jobs.json
```

## 3. 去重和机会报告

系统使用两种实体：

- `JOB`：有明确职位和 JD 的具体岗位
- `CAMPAIGN`：公司招聘批次或招聘公告

`JOB` 和 `CAMPAIGN` 永远不会互相合并。

去重规则：

- 精确匹配自动合并
- 所有原始来源都会保留
- 官网字段优先于 BOSS
- BOSS 完整 JD 优先于飞书和腾讯表格
- 模糊匹配只标记 `possible_duplicate_of`
- 同一公司不同岗位、城市或招聘批次不合并

输出 Markdown：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  opportunities \
  --markdown career-data/opportunity-report.md
```

将招聘批次与官网岗位建立父子关系：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  opportunity-relate \
  --campaign 12 \
  --job 18
```

## 4. 建立 JD Session

选择具体岗位后创建 Session：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  session-create \
  --opportunity 18
```

Session 会绑定创建时最新的 Base Revision。之后 Base 更新不会静默改变现有 Session。

保存针对该 JD 的临时补充：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  session-overlay \
  --session 3 \
  --input career-data/jobs/18/session-overlay.md
```

保存用户确认后的 Match Plan：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  session-plan \
  --session 3 \
  --input career-data/jobs/18/match-plan.md
```

## 5. 保存岗位评分特征

参考：

```text
assets/templates/opportunity-features.json
```

所有特征使用 `0–1`：

```json
{
  "role_match": 0.9,
  "skill_match": 0.8,
  "evidence_strength": 0.85,
  "domain_match": 0.7,
  "impact_match": 0.8,
  "job_freshness": 0.9,
  "source_quality": 0.8,
  "location_fit": 1.0
}
```

写入岗位：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  opportunity-score \
  --opportunity 18 \
  --input career-data/jobs/18/features.json \
  --hard-eligible true
```

`hard-eligible` 是硬性条件，不会被自动学习修改。

## 6. 生成并验证简历

简历生成必须满足：

- 只读取 Session 绑定的 Base Revision
- 可以读取当前 Session Overlay
- 不执行 `resume-tailoring` 的永久经历库更新阶段
- Markdown 是唯一内容源
- DOCX/PDF 必须与 Markdown 内容一致

Evidence Map 示例：

```json
{
  "job_session_id": 3,
  "base_revision_id": 2,
  "claims": [
    {
      "claim": "负责 AI 产品需求分析与方案设计",
      "source_type": "base",
      "source_ref": "FACT-0012",
      "supported": true,
      "notes": ""
    }
  ]
}
```

验证：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  evidence-check \
  --mapping career-data/jobs/18/evidence-map.json
```

验证通过后登记实际文件：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  resume-add \
  --session 3 \
  --format md \
  --path career-data/jobs/18/resume.md
```

## 7. 记录真实投递

只有真正提交或用户确认提交后才能创建投递：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  application-create \
  --opportunity 18 \
  --session 3 \
  --resume 1
```

支持的结果阶段：

| 阶段 | 含义 | 是否参与学习 |
|---|---|---:|
| `PREPARING` | 准备中 | 否 |
| `APPLIED` | 已投递 | 否 |
| `VIEWED` | 已查看 | 是 |
| `CONTACTED` | HR 沟通 | 是 |
| `WRITTEN_TEST` | 笔试 | 是 |
| `INTERVIEW_1` | 一面 | 是 |
| `INTERVIEW_2` | 二面 | 是 |
| `FINAL_INTERVIEW` | 终面 | 是 |
| `OFFER` | Offer | 是 |
| `REJECTED_SCREEN` | 简历筛选拒绝 | 是 |
| `REJECTED_AFTER_INTERVIEW` | 面试后拒绝 | 否 |
| `NO_RESPONSE` | 长期无回复 | 等待 21 天后 |
| `WITHDRAWN` | 主动撤回 | 否 |
| `JOB_CLOSED` | 岗位关闭 | 否 |

记录结果：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  application-event \
  --application 1 \
  --stage INTERVIEW_1 \
  --note "已安排产品经理一面"
```

记录 Offer：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  application-event \
  --application 1 \
  --stage OFFER
```

## 8. 自动评分学习

初始评分特征：

- 岗位方向匹配
- 技能匹配
- 证据强度
- 行业匹配
- 成果匹配
- 岗位新鲜度
- 来源质量
- 地点匹配

学习保护：

- 累计至少 3 个有效投递样本后开始调权
- 每个投递只使用最新的有效结果
- 使用先验平滑，降低小样本波动
- 每个特征每次相对变化不超过 10%
- 每次调整都会生成不可变的权重版本
- 可以恢复任意历史版本
- 不修改硬性条件、Base 事实或简历内容

查看当前权重：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  weights
```

查看历史：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  weight-history
```

恢复历史版本：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  weight-activate \
  --version 1
```

## 9. 投递后台

启动本地只读后台：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  dashboard
```

默认地址：

```text
http://127.0.0.1:8765
```

后台包含：

- 投递总览
- 岗位机会
- 投递记录
- 当前阶段
- 实际简历快照
- 绑定的 Base Revision
- 当前评分权重和样本数
- Notion 待同步、已同步和失败数量

V1 后台是只读的。使用 CLI 或 Codex Skill 记录阶段变化。

导出 Markdown 投递日志：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  applications \
  --markdown career-data/application-log.md
```

## 10. Notion 同步

当前目标页面：

[Job](https://app.notion.com/p/32099adbdb7b80a89749c535aad52790)

同步采用“本地队列 + Codex Notion 连接器”：

- SQLite 是事实源
- 本地写入自动进入待同步队列
- 不在脚本、数据库或日志中保存 Notion Token
- 同步失败不影响岗位导入、投递记录或结果学习
- Upsert 使用稳定本地 ID，避免重复创建
- 不覆盖 Notion 中的 `人工备注`、`下一步行动` 和 `下一步时间`

### 日常使用

正常通过 `$run-job-applications` 搜索、评分、记录投递或更新结果时，
Codex 会自动执行以下操作：

1. 先完成本地 SQLite 写入。
2. 读取待同步计划。
3. 按稳定本地 ID 查询 Notion 中的已有页面。
4. 更新已有页面或创建新页面。
5. 写回 Notion Page ID 并确认队列。
6. 如果失败，保留本地记录并登记错误，等待重试。

自动进入队列的操作：

| 本地操作 | 同步对象 |
|---|---|
| 导入或合并岗位 | 岗位池 |
| 更新岗位评分 | 岗位池 |
| 建立招聘批次与岗位关系 | 岗位池关系 |
| 确认真实投递 | 投递记录、初始事件 |
| 更新投递结果 | 投递记录、进展事件 |
| 自动学习或恢复权重 | 评分版本、受影响的岗位评分 |

数据表映射：

| SQLite 实体 | Notion 数据库 | Upsert 标识 |
|---|---|---|
| `opportunity` | 岗位池 | `本地机会ID` |
| `application` | 投递记录 | `本地投递ID` |
| `application_event` | 进展事件 | `本地事件ID` |
| `scoring_profile` | 评分版本 | `版本号` |

`投递记录` 同时保留原有中文 `投递状态`，并使用 `标准阶段` 保存完整
流程枚举。历史人工记录不会因为同步而删除。

### 首次迁移历史数据

首次把本地已有记录全部加入队列：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  notion-enqueue-all
```

随后直接让 Codex 执行：

```text
使用 $run-job-applications，把全部待同步记录同步到 Notion。
```

### 手动诊断 CLI

以下命令主要用于调试连接器同步。正常使用 Skill 时不需要手工逐条 ACK。

生成连接器可执行的只读计划：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  notion-plan \
  --limit 50
```

`notion-plan` 返回目标数据库、稳定 ID、属性、依赖关系和已有 Notion
页面映射。只有 `ready: true` 的操作可以执行。Codex 使用 Notion
连接器创建或更新页面，成功后确认：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  notion-ack \
  --queue 12 \
  --page-id <notion-page-id> \
  --page-url <notion-page-url>
```

失败时记录原因，稍后重试：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  notion-fail \
  --queue 12 \
  --error "connector unavailable"

python3 scripts/pipeline.py \
  --db career-data/career.db \
  notion-retry
```

查看状态或本地到 Notion 的映射：

```bash
python3 scripts/pipeline.py --db career-data/career.db notion-status
python3 scripts/pipeline.py --db career-data/career.db notion-state
```

处理顺序由依赖关系控制：

```text
招聘批次 → 具体岗位 → 投递记录 → 进展事件

评分版本：独立同步，无 Notion Relation 依赖
```

完整连接器策略见：

```text
skills/run-job-applications/references/notion-sync-policy.md
```

## 输出文件

推荐结构：

```text
career-data/
├── career.db
├── career-vault.md
├── opportunity-report.md
├── application-log.md
└── jobs/
    └── 18/
        ├── job-analysis.md
        ├── session-overlay.md
        ├── match-plan.md
        ├── features.json
        ├── resume.md
        ├── resume.docx
        ├── evidence-map.json
        └── evidence-report.md
```

## 测试

运行端到端测试：

```bash
python3 -m unittest discover -s scripts/tests -v
```

测试覆盖：

- BOSS 与公司官网精确岗位去重
- 原始来源保留
- Campaign 与 Job 隔离
- Campaign/Job 父子关系
- Job Session 绑定 Base
- Evidence Guard
- 第三个有效结果触发自动调权
- `NO_RESPONSE` 的 21 天等待限制
- Notion 队列、依赖、ACK、失败和重试

校验插件：

```bash
python3 /Users/qiuchan/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

## 故障排查

### BOSS 未登录

```bash
boss login
boss status
```

不要手动复制 Cookie 到聊天中。

### 无法建立 Job Session

先确认已经存在 Base Revision：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  vault-history
```

### 自动权重没有变化

检查：

- 是否已有至少 3 个有效结果
- 是否只记录了 `APPLIED`
- 岗位是否设置了评分特征
- `hard_eligible` 是否为 `false`

### `NO_RESPONSE` 被拒绝

必须距离投递时间至少 21 天，防止把仍在处理中的申请误判为负反馈。

### 后台无法启动

更换端口：

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  dashboard \
  --port 8876
```

### DOCX/PDF 生成失败

保留已经通过 Evidence Guard 的 `resume.md`，修复文档渲染能力后再生成其他格式。

### Notion 有待同步或失败

```bash
python3 scripts/pipeline.py \
  --db career-data/career.db \
  notion-status
```

失败项不会阻塞本地流程。恢复连接后执行 `notion-retry`，再由
`$run-job-applications` 重新执行同步计划。

如果 Notion 中出现相同本地 ID 的多条记录，不要任意选择一条覆盖。
先合并或删除重复项，再重试同步。

## 隐私与安全

- SQLite 和 Markdown 默认在本地；启用同步后，四类后台记录会进入指定 Notion 页面
- 后台默认只绑定 `127.0.0.1`
- 不保存或输出 BOSS Cookie
- 不保存或输出 Notion Token
- 不在 Base 中保存密码、令牌或公司机密
- 每份实际投递简历保存路径和内容哈希
- 删除或移动简历文件前先确认是否仍被投递记录引用

## 当前 V1 限制

- 飞书和腾讯文档依赖运行时浏览器读取，不是独立服务端爬虫
- 后台为只读页面，结果通过 Skill 或 CLI 更新
- Notion 当前是 SQLite → Notion 的单向投影；Notion 人工字段不会反向修改 SQLite
- 自动学习使用可解释权重，不是黑盒机器学习模型
- 不会自动投递、自动打招呼或自动发送消息
- 不会自动把 Session Overlay 合并进 Base
