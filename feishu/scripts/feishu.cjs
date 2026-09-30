'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const { randomUUID, createHash } = require('node:crypto');

const READ_TOOLS = new Set([
  'wiki_v2_space_getNode', 'docx_v1_document_get', 'docx_v1_document_rawContent',
  'docx_v1_documentBlock_list', 'docx_v1_documentBlock_get',
  'docx_v1_documentBlockChildren_get', 'docx_v1_document_convert',
]);
const WRITE_TOOLS = new Set([
  'docx_v1_documentBlockChildren_create', 'docx_v1_documentBlock_patch',
  'docx_v1_documentBlock_batchUpdate',
]);

function parseTarget(value) {
  const url = new URL(value);
  const match = url.pathname.match(/^\/(wiki|docx)\/([A-Za-z0-9]+)\/?$/);
  if (url.protocol !== 'https:' || url.username || url.password || url.port ||
      !/(^|\.)(feishu\.cn|larksuite\.com)$/.test(url.hostname) || !match) {
    throw new Error('请提供有效的飞书 Wiki 或 docx 文档 HTTPS 链接。');
  }
  return { kind: match[1], token: match[2], url: `${url.origin}/${match[1]}/${match[2]}` };
}

function redact(value, secrets = []) {
  if (typeof value === 'string') {
    return secrets.filter(Boolean).reduce((s, secret) => s.split(secret).join('[REDACTED]'), value);
  }
  if (Array.isArray(value)) return value.map(item => redact(item, secrets));
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key,
    /^(?:app[_-]?secret|(?:user[_-]?|tenant[_-]?)?access[_-]?token|refresh[_-]?token|authorization|client[_-]?secret)$/i.test(key)
      ? '[REDACTED]' : redact(item, secrets),
  ]));
}

function unpack(result) {
  let value = result.structuredContent;
  if (!value) {
    const block = (result.content || []).find(item => item.type === 'text');
    if (block) { try { value = JSON.parse(block.text); } catch { value = { message: block.text }; } }
  }
  value ||= {};
  if (result.isError || (value.code !== undefined && value.code !== 0)) {
    const code = value.code === undefined ? 'MCP_ERROR' : value.code;
    const error = new Error(`飞书请求未成功（${code}）。请检查授权、权限及工具参数。`);
    error.apiCode = code;
    throw error;
  }
  return value.data && value.code === 0 ? value.data : value;
}

function loadSettings(explicitFile) {
  const selectedFile = explicitFile || process.env.FEISHU_SKILL_CONNECTION;
  const localFile = path.join(__dirname, 'connection.local.json');
  const legacyFile = path.join(__dirname, 'connection.json');
  const settingsFile = selectedFile ? path.resolve(selectedFile)
    : fs.existsSync(localFile) ? localFile : legacyFile;
  if (!fs.existsSync(settingsFile)) {
    throw new Error('配置缺失：请按连接说明创建 connection.local.json，或设置 FEISHU_SKILL_CONNECTION；不要在 skill 中放入密钥。');
  }
  const settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8').replace(/^\uFEFF/, ''));
  if (typeof settings.runtimeDir !== 'string' || !settings.runtimeDir || !path.isAbsolute(settings.runtimeDir)) {
    throw new Error('配置错误：runtimeDir 必须是现有官方飞书 MCP 项目的绝对路径。');
  }
  if (settings.configFile && (typeof settings.configFile !== 'string' || !path.isAbsolute(settings.configFile))) {
    throw new Error('配置错误：configFile 必须是已有 MCP 配置文件的绝对路径。');
  }
  return { ...settings, runtimeDir: path.resolve(settings.runtimeDir),
    configFile: settings.configFile || path.join(settings.runtimeDir, 'config.local.json'),
    nodeExecutable: settings.nodeExecutable || process.execPath };
}

async function run(argv) {
  const [mode, argument, inputFile, ...flags] = argv;
  if (!['inspect', 'convert', 'schema', 'call'].includes(mode)) {
    throw new Error('用法：inspect [文档链接] | convert Markdown文件 | schema [工具名] | call 工具名 参数JSON文件 [--write]');
  }
  let args, receipt, receiptFile, receiptPersisted = false;
  const mutation = mode === 'call' && WRITE_TOOLS.has(argument);
  if (mode === 'call') {
    if (!READ_TOOLS.has(argument) && !WRITE_TOOLS.has(argument)) {
      throw new Error('工具不在本 skill 的文档操作范围内。');
    }
    if (mutation && !flags.includes('--write')) {
      throw new Error('实际写入必须带 --write，且必须有用户本次的发布或修改请求。');
    }
    if (!inputFile) throw new Error('缺少工具参数 JSON 文件。');
    args = JSON.parse(fs.readFileSync(path.resolve(inputFile), 'utf8').replace(/^\uFEFF/, ''));
    if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error('工具参数必须是 JSON 对象。');
    args.useUAT = true;
  }
  const settings = loadSettings();
  const { runtimeDir, configFile } = settings;
  let target;
  if (mode === 'inspect') {
    if (!(argument || settings.defaultUrl)) throw new Error('请提供目标文档链接，或在私有配置中设置 defaultUrl。');
    target = parseTarget(argument || settings.defaultUrl);
  }
  const runtimeRequire = createRequire(path.join(runtimeDir, 'package.json'));
  const { Client } = runtimeRequire('@modelcontextprotocol/sdk/client/index.js');
  const { StdioClientTransport } = runtimeRequire('@modelcontextprotocol/sdk/client/stdio.js');
  const config = JSON.parse(fs.readFileSync(configFile, 'utf8'));
  const secrets = [config.appSecret, config.app_secret];
  const print = value => process.stdout.write(`${JSON.stringify(redact(value, secrets))}\n`);

  const client = new Client({ name: 'personal-feishu-skill', version: '1.0.0' });
  try {
    await client.connect(new StdioClientTransport({
      command: settings.nodeExecutable,
      args: [path.join(runtimeDir, 'node_modules/@larksuiteoapi/lark-mcp/dist/cli.js'), 'mcp', '--config', configFile],
      cwd: runtimeDir, stderr: 'pipe',
    }));
    const call = async (name, parameters) => unpack(await client.callTool({ name, arguments: { ...parameters, useUAT: true } }));
    if (mode === 'schema') {
      const { tools } = await client.listTools();
      if (!argument) print(tools.map(tool => ({ name: tool.name, description: tool.description })));
      else {
        const tool = tools.find(item => item.name === argument);
        if (!tool) throw new Error('当前 MCP 没有暴露这个工具。');
        print({ name: tool.name, inputSchema: tool.inputSchema });
      }
    } else if (mode === 'inspect') {
      let documentId = target.token;
      if (target.kind === 'wiki') {
        const result = await call('wiki_v2_space_getNode', { params: { token: target.token } });
        if (result.node?.obj_type !== 'docx' || !result.node.obj_token) {
          throw new Error('这个知识库节点不是可写入的新版飞书文档（docx）。');
        }
        documentId = result.node.obj_token;
      }
      const result = await call('docx_v1_document_get', { path: { document_id: documentId } });
      if (!result.document || typeof result.document !== 'object') throw new Error('没有读取到目标文档信息。');
      print({ url: target.url, document_id: documentId, title: result.document.title,
        revision_id: result.document.revision_id, mode: 'read_only' });
    } else if (mode === 'convert') {
      if (!argument) throw new Error('缺少待发布 Markdown 文件。');
      const content = fs.readFileSync(path.resolve(argument), 'utf8').replace(/^\uFEFF/, '');
      if (!content.trim()) throw new Error('不转换或发布空内容。');
      print(await call('docx_v1_document_convert', { data: { content_type: 'markdown', content } }));
    } else {
      if (mutation) {
        args.params ||= {};
        args.params.client_token ||= randomUUID();
        const receiptsDir = path.join(path.dirname(path.resolve(inputFile)), '.feishu-write-receipts');
        fs.mkdirSync(receiptsDir, { recursive: true });
        const fileKey = createHash('sha256').update(args.params.client_token).digest('hex').slice(0, 24);
        receiptFile = path.join(receiptsDir, `${fileKey}.json`);
        receipt = { tool: argument, document_id: args.path?.document_id,
          parent_or_block_id: args.path?.block_id, client_token: args.params.client_token,
          argument_sha256: createHash('sha256').update(JSON.stringify(args)).digest('hex'),
          status: 'pending', created_at: new Date().toISOString() };
        fs.writeFileSync(receiptFile, JSON.stringify(receipt, null, 2), { encoding: 'utf8', flag: 'wx' });
        receiptPersisted = true;
        print({ phase: 'before_write', receipt_file: receiptFile, client_token: receipt.client_token });
      }
      const result = await call(argument, args);
      if (receipt) {
        receipt.status = 'api_confirmed';
        receipt.document_revision_id = result.document_revision_id;
        receipt.created_block_ids = (result.children || []).map(block => block.block_id);
        fs.writeFileSync(receiptFile, JSON.stringify(receipt, null, 2), 'utf8');
      }
      print({ result, ...(receiptFile ? { receipt_file: receiptFile, verification: 'read_back_required' } : {}) });
    }
  } catch (error) {
    if (receiptPersisted && receiptFile && receipt) {
      receipt.status = typeof error.apiCode === 'number' ? 'api_rejected' : 'unknown_check_document_before_retry';
      receipt.api_code = error.apiCode;
      try { fs.writeFileSync(receiptFile, JSON.stringify(receipt, null, 2), 'utf8'); } catch { /* Preserve the pending receipt. */ }
      print({ receipt_file: receiptFile, status: receipt.status });
    }
    throw error;
  } finally {
    await client.close();
  }
}

module.exports = { parseTarget, redact, unpack, loadSettings, READ_TOOLS, WRITE_TOOLS };
if (require.main === module) {
  run(process.argv.slice(2)).catch(error => {
    const safeMessage = /^(配置|请提供|用法：|工具不在|实际写入|缺少|工具参数|当前 MCP|这个知识库|没有读取|不转换|飞书请求)/.test(error.message)
      ? error.message : error.code === 'EEXIST'
        ? '该幂等标识已有写入回执。请先检查回执和文档，不要直接重复追加。'
        : '本地 MCP 调用失败，请检查连接路径、登录状态和已有写入回执；不要重复未核对的写入。';
    process.stderr.write(`${safeMessage}\n`);
    process.exitCode = 1;
  });
}
