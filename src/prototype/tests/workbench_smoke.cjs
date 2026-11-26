// Real loopback HTTP + command handlers with a VS Code API substitute; no GUI launch.
const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const Module = require('node:module');

async function main() {
  const out = process.argv[2] ? path.resolve(process.argv[2]) : path.resolve(__dirname, '../out');
  const { WorkbenchClient, localWorkbenchUrl, editorDraft, draftWorkspaceUrl, workbenchError } = require(path.join(out, 'workbenchClient.js'));
  const { SeedaApiClient } = require(path.join(out, 'apiClient.js'));
  const manifest = require('../package.json');
  for (const url of ['https://example.com', 'http://127.0.0.1.example.com', 'file:///tmp/test',
    'http://user:pass@localhost:8765', 'http://localhost:8765/a', 'http://localhost:8765/?external=1']) {
    assert.throws(() => localWorkbenchUrl(url), /本机|loopback/);
  }
  assert.equal(localWorkbenchUrl('http://127.0.0.1:8765/'), 'http://127.0.0.1:8765');
  assert.equal(localWorkbenchUrl('http://[::1]:8765'), 'http://[::1]:8765');
  assert.throws(() => editorDraft('x'.repeat(20001), 'module.py', 'python'), /20000/);
  assert.throws(() => editorDraft('   ', 'module.py', 'python'), /没有/);
  assert.equal(editorDraft('print(1)', 'C:\\private\\project\\module.py', 'python').file_label, 'module.py');
  assert.match(draftWorkspaceUrl('http://localhost:8765', 'draft/a?b'), /draft=draft%2Fa%3Fb$/);
  process.env.HTTP_PROXY = process.env.ALL_PROXY = 'http://127.0.0.1:1';
  process.env.NO_PROXY = '';
  const calls = [], opened = [], messages = [], handlers = new Map();
  let redirect = false, redirectedRequests = 0;
  const sink = http.createServer((_req, res) => { redirectedRequests++; res.end('{}'); });
  await new Promise(resolve => sink.listen(0, '127.0.0.1', resolve));
  const experience = { id: 'exp-1', requirement: 'implement addition', scope: 'workbench-python', version: 'v1',
    code: 'def add(a,b): return a+b', validated: true, archived: false,
    static_meta: { generalization: 0.5 }, stats: { success_rate: 1, use_count: 2, timeliness: 1 },
    receipt: { is_success: true, execution_time: 0.01 }, similarity: 0.9, composite_score: 0.8 };
  const server = http.createServer(async (req, res) => {
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    const text = Buffer.concat(chunks).toString('utf8');
    const body = text ? JSON.parse(text) : null;
    calls.push({ url: req.url, method: req.method, body, key: req.headers['x-api-key'] });
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/api/workbench/drafts') {
      if (redirect) { res.writeHead(302, { Location: `http://127.0.0.1:${sink.address().port}/capture` }).end(); return; }
      res.end(JSON.stringify({ id: 'draft-test' }));
    } else if (req.url === '/api/workbench/overview') {
      res.end(JSON.stringify({ experiences_total: 3, experiences_active: 2, runs_total: 4,
        completed: 3, successful: 2, active_jobs: 1, templates_total: 0 }));
    } else if (req.url === '/api/workbench/search') {
      res.end(JSON.stringify({ experiences: [experience], diagnostics: {} }));
    } else if (req.url.startsWith('/api/workbench/experiences?')) {
      res.end(JSON.stringify({ experiences: [experience] }));
    } else if (req.url === '/api/workbench/experiences/exp-1/feedback') {
      res.end(JSON.stringify({ ...experience, archived: body.archive }));
    } else if (req.url === '/api/workbench/maintenance') {
      res.end(JSON.stringify({ action: body.action, affected: [], templates_added: [] }));
    } else res.writeHead(404).end('{}');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const endpoint = `http://127.0.0.1:${server.address().port}`;
  const secrets = { get: async () => 'test-secret' };
  const originalLoad = Module._load;
  try {
    const workbench = new WorkbenchClient(endpoint, 2000, secrets);
    await workbench.checkConnection();
    assert.equal(await workbench.saveDraft(editorDraft('print(1)', '/private/module.py', 'python')), 'draft-test');
    assert.equal(calls.at(-1).key, 'test-secret');
    assert.deepEqual(calls.at(-1).body, { code: 'print(1)', title: 'VS Code · module.py',
      language: 'python', source: 'vscode', file_label: 'module.py' });
    redirect = true;
    await assert.rejects(() => workbench.saveDraft(editorDraft('print(1)', 'a.py', 'python')),
      error => workbenchError(error, endpoint).includes('重定向'));
    assert.equal(redirectedRequests, 0, 'source must not follow redirects');
    redirect = false;
    const api = new SeedaApiClient(endpoint, 2000, secrets);
    assert.equal((await api.stats()).archived_nodes, 1);
    assert.equal((await api.health()).total_experiences, 3);
    assert.equal((await api.search('addition', 5))[0].experience_id, 'exp-1');
    assert.deepEqual(calls.at(-1).body, { query: 'addition', top_k: 5, scope: 'workbench-python', version: 'v1' });
    assert.equal((await api.recommend('return a+b', 'python', 3))[0].suggestion, experience.code);
    assert.equal((await api.experiences())[0].id, 'exp-1');
    assert.equal((await api.feedback('exp-1', false, 'changed contract')).archived, true);
    await api.runLifecycle();
    assert.deepEqual(calls.slice(-2).map(item => item.body.action), ['archive_invalid', 'build_templates']);
    const editor = { selection: { isEmpty: false }, document: { fileName: 'C:\\private\\module.py',
      languageId: 'python', getText: selection => selection ? 'print(2)' : '# whole file\nprint(3)' } };
    const vscode = {
      window: { activeTextEditor: editor,
        createOutputChannel: () => ({ appendLine() {}, dispose() {} }),
        createStatusBarItem: () => ({ show() {}, dispose() {} }),
        registerWebviewViewProvider: () => ({ dispose() {} }),
        showInformationMessage: async msg => messages.push(msg), showErrorMessage: async msg => messages.push(msg),
        showWarningMessage: async msg => messages.push(msg),
        withProgress: async (_options, task) => task() },
      workspace: { registerTextDocumentContentProvider: () => ({dispose(){}}), getConfiguration: () => ({ get: (key, fallback) => key === 'workbenchUrl' ? endpoint : fallback }) },
      commands: { registerCommand: (id, fn) => { handlers.set(id, fn); return { dispose() {} }; },
        executeCommand: async id => handlers.get(id)() },
      env: { openExternal: async uri => { opened.push(uri); return true; } },
      Uri: { parse: value => value }, StatusBarAlignment: { Left: 1 }, ProgressLocation: { Notification: 1 },
    };
    const extensionPath = path.join(out, 'extension.js');
    Module._load = function (request, parent, isMain) {
      if (request === 'vscode') return vscode;
      if (parent?.filename === extensionPath && request === './experienceView') {
        return { ExperienceViewProvider: class { static viewType = 'seeda.experienceView'; async refresh() {} } };
      }
      return originalLoad.call(this, request, parent, isMain);
    };
    require(extensionPath).activate({ subscriptions: [], extensionUri: {}, secrets, workspaceState:{get:(_k,d)=>d} });
    for (const item of manifest.contributes.commands) assert.ok(handlers.has(item.command), item.command);
    await handlers.get('seeda.openWorkbench')();
    assert.equal(opened.at(-1), endpoint);
    await handlers.get('seeda.sendSelectionToWorkbench')();
    assert.equal(calls.at(-1).body.code, 'print(2)', 'selected code takes priority');
    assert.equal(calls.at(-1).body.file_label, 'module.py');
    assert.equal(opened.at(-1), `${endpoint}/#workspace?draft=draft-test`);
    editor.selection.isEmpty = true;
    await handlers.get('seeda.saveCurrentExperience')();
    assert.equal(calls.at(-1).body.code, '# whole file\nprint(3)', 'legacy save now preserves an unexecuted draft');
    assert.ok(!calls.some(item => /\/runs/.test(item.url)), 'no source buffer is automatically executed');
    vscode.window.activeTextEditor = undefined;
    const before = calls.length;
    await handlers.get('seeda.sendSelectionToWorkbench')();
    assert.equal(calls.length, before);
    assert.ok(messages.some(msg => msg.includes('补充任务要求和测试')));
    console.log('PASS: registered manifest commands; actual loopback draft/search/overview/feedback/maintenance; selection and file fallback; basename only; 20000-char limit; external URL and redirect rejection; proxy bypass; no automatic execution. VS Code GUI not tested.');
  } finally {
    Module._load = originalLoad;
    await new Promise(resolve => server.close(resolve));
    await new Promise(resolve => sink.close(resolve));
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
