'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const { parseTarget, redact, unpack, loadSettings, READ_TOOLS, WRITE_TOOLS } = require('./feishu.cjs');

function settingsFixture(t, settings) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'feishu-skill-test-'));
  const file = path.join(directory, 'connection.local.json');
  fs.writeFileSync(file, JSON.stringify(settings), 'utf8');
  t.after(() => { fs.unlinkSync(file); fs.rmdirSync(directory); });
  return file;
}

test('可配置现有运行目录，并默认复用当前 Node，不绑定电脑路径', t => {
  const runtimeDir = path.resolve(os.tmpdir(), 'existing-feishu-mcp');
  const settings = loadSettings(settingsFixture(t, { runtimeDir }));
  assert.equal(settings.runtimeDir, runtimeDir);
  assert.equal(settings.configFile, path.join(runtimeDir, 'config.local.json'));
  assert.equal(settings.nodeExecutable, process.execPath);
  assert.equal(settings.defaultUrl, undefined);
});

test('允许把已有 MCP 配置和私人默认文档保留在仓库之外', t => {
  const configFile = path.resolve(os.tmpdir(), 'private-feishu-config.json');
  const settings = loadSettings(settingsFixture(t, {
    runtimeDir: path.resolve(os.tmpdir(), 'existing-feishu-mcp'), configFile,
    defaultUrl: 'https://tenant.feishu.cn/docx/example123',
  }));
  assert.equal(settings.configFile, configFile);
  assert.equal(settings.defaultUrl, 'https://tenant.feishu.cn/docx/example123');
});

test('未配置或相对路径不会被默认为有效连接', t => {
  assert.throws(() => loadSettings(settingsFixture(t, { runtimeDir: '' })), /runtimeDir/);
  assert.throws(() => loadSettings(settingsFixture(t, { runtimeDir: 'relative/path' })), /绝对路径/);
  assert.throws(() => loadSettings(settingsFixture(t, {
    runtimeDir: path.resolve(os.tmpdir(), 'existing-feishu-mcp'), configFile: 'relative.json',
  })), /configFile/);
});

test('Wiki 与 docx URL 分开处理，并移除分享查询参数', () => {
  assert.deepEqual(parseTarget('https://tenant.feishu.cn/wiki/abc123?from=copy#section'), {
    kind: 'wiki', token: 'abc123', url: 'https://tenant.feishu.cn/wiki/abc123',
  });
  assert.equal(parseTarget('https://tenant.larksuite.com/docx/xyz456').kind, 'docx');
});

test('拒绝非飞书主机、含凭据链接、旧版文档与非 HTTPS', () => {
  for (const url of [
    'https://feishu.cn.evil.example/docx/abc', 'https://evilfeishu.cn/docx/abc',
    'http://tenant.feishu.cn/docx/abc', 'https://user:secret@tenant.feishu.cn/docx/abc',
    'https://tenant.feishu.cn:444/docx/abc', 'https://tenant.feishu.cn/sheets/abc',
    'https://tenant.feishu.cn/doc/abc',
  ]) assert.throws(() => parseTarget(url));
});

test('清理嵌套凭据，保留文档 ID、正文和非登录的幂等标识', () => {
  const result = redact({
    appSecret: 'test-secret', document_id: 'doc-id', client_token: 'write-uuid',
    nested: [{ access_token: 'access', refreshToken: 'refresh', text: '正文 test-secret' }],
  }, ['test-secret']);
  assert.equal(result.appSecret, '[REDACTED]');
  assert.equal(result.nested[0].access_token, '[REDACTED]');
  assert.equal(result.nested[0].refreshToken, '[REDACTED]');
  assert.equal(result.nested[0].text, '正文 [REDACTED]');
  assert.equal(result.document_id, 'doc-id');
  assert.equal(result.client_token, 'write-uuid');
});

test('读取官方 MCP 的 structuredContent、JSON 文本与外层 data', () => {
  const document = { document: { title: '测试' } };
  assert.deepEqual(unpack({ structuredContent: document }), document);
  assert.deepEqual(unpack({ content: [{ type: 'text', text: JSON.stringify(document) }] }), document);
  assert.deepEqual(unpack({ structuredContent: { code: 0, data: document } }), document);
});

test('明确失败不会被当成写入成功，也不把原错误里的凭据显示出来', () => {
  assert.throws(() => unpack({ isError: true, structuredContent: { message: 'private-secret' } }),
    error => error.apiCode === 'MCP_ERROR' && !error.message.includes('private-secret'));
  assert.throws(() => unpack({ structuredContent: { code: 99991663 } }),
    error => error.apiCode === 99991663);
});

test('所有变更调用缺少 --write 时在连接之前拒绝', () => {
  for (const tool of WRITE_TOOLS) {
    assert.equal(READ_TOOLS.has(tool), false);
    const result = spawnSync(process.execPath,
      [path.join(__dirname, 'feishu.cjs'), 'call', tool, 'not-a-real-file.json'], { encoding: 'utf8' });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /必须带 --write/);
    assert.equal(result.stdout, '');
  }
});

test('不允许当前结构不完整的子孙接口或范围外操作', () => {
  const result = spawnSync(process.execPath,
    [path.join(__dirname, 'feishu.cjs'), 'call', 'docx_v1_documentBlockDescendant_create', 'none.json', '--write'],
    { encoding: 'utf8' });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /不在本 skill/);
});
