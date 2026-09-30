# 复用已有飞书连接

当前会话有可调用的飞书 MCP 工具时直接使用，不需要配置辅助脚本。只有工具未暴露且本机已有官方 MCP 运行环境时才使用本节。此 skill 不自带应用密钥或登录流程，也不自动安装、授权或改写已有 MCP。

官方项目：[larksuite/lark-openapi-mcp](https://github.com/larksuite/lark-openapi-mcp)。写入流程针对已验证的 0.5.1 工具结构；更换版本后应检查实际工具结构。

## 私有连接配置

根据 `scripts/connection.example.json` 创建 `scripts/connection.local.json`，只填写路径和可选默认文档链接，不填 App Secret 或访问令牌。该文件已被 `.gitignore` 排除。

也可以将配置放在 skill 目录之外，通过环境变量 `FEISHU_SKILL_CONNECTION` 指定其绝对路径。脚本仍兼容旧版个人 skill 的 `scripts/connection.json`，但这个旧文件同样不能提交到仓库。

字段：

- `runtimeDir`：必填，现有 MCP 项目的绝对目录。其中应存在 `package.json`、`node_modules/@larksuiteoapi/lark-mcp/dist/cli.js` 及 MCP SDK 依赖。
- `configFile`：可选，现有官方 MCP 配置文件的绝对路径；为空时使用运行目录下的 `config.local.json`。应用密钥只保留在此原有配置里，登录状态由官方 MCP 管理。
- `nodeExecutable`：可选，Node 可执行文件路径；为空时复用运行辅助脚本的 Node。
- `defaultUrl`：可选，私人默认 Wiki/docx 链接；为空时每次发布需要用户提供目标链接。

所有路径应是真实的绝对路径。不要提交用户的连接配置、默认私人文档链接、凭据存储或 `node_modules`。

## 使用前检查

以只读的 `inspect <文档链接>` 核对连接、标题及 docx 类型；或用 `schema` 检查当前工具。测试不应向真实文档添加内容。

已有 MCP 至少需要暴露 Wiki 节点查询、新版文档读取、Markdown 转换、块读取和创建子块能力；只有用户要求修改时才需要块更新工具。`scripts/feishu.cjs` 的白名单给出它支持的工具，不要求为了普通追加扩大到无关工具。

辅助脚本使用已验证的工具命名格式。已有官方 MCP 配置的 `toolNameCase` 应为 `snake`；若当前工具命名或可用工具不同，先检查 `schema` 输出并报告不匹配，不假定工具已可调用。

既有连接需以用户身份调用，并具有对应接口权限与目标文档访问权。若未配置、未安装或未授权，应报告具体缺项，请用户完成正常接入；不从其他无关位置搜集凭据，也不根据示例伪造 App ID 或授权状态。
