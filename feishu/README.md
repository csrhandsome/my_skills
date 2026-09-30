# feishu

将选定的对话输出、报告或总结写入飞书云文档的 Codex skill。默认追加，保留原内容；支持指定段落修改、Wiki 链接解析、Markdown 转换与写入后核对。

## 使用

将本仓库的 `feishu` 目录安装到你的 Codex 个人 skills 目录，然后调用：

```text
$feishu 把上面的结果写入这个飞书文档：https://你的租户.feishu.cn/wiki/文档Token
$feishu 把这份报告追加到我配置的默认文档
```

需要已接入并授权的飞书 MCP。当前会话有飞书工具时直接复用；否则可使用附带的本地辅助脚本，连接到现有官方 MCP 运行目录。路径配置方式见 [连接说明](references/connection.md)。

仓库不包含应用密钥、登录令牌、个人文档地址或本机授权状态。`connection.local.json` 仅留在本机，不能提交。

## 辅助脚本

```text
node scripts/feishu.cjs inspect <文档链接>
node scripts/feishu.cjs convert <Markdown文件>
node scripts/feishu.cjs schema <工具名>
node scripts/feishu.cjs call <工具名> <参数JSON文件> --write
node --test scripts/feishu.test.cjs
```

实际写入需要用户明确的发布或修改请求。写调用没有自动重试，并生成本地回执；超时或部分成功必须先核对，避免重复追加。

目前的辅助脚本不开放删除、上传素材和子孙创建接口。支持正文、常见富文本及基础表格的分层写入流程，不保证图片素材迁移、合并单元格或像素级排版复刻。详细流程见 [写入与核对](references/write-workflow.md)。
