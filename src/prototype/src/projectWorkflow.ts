import * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { execFile, spawn } from "node:child_process";
import { promisify } from "node:util";
import { SeedaApiClient, formatApiError } from "./apiClient";
import { memoryContext } from "./workspaceContext";
import { replacementWithTargetEnding, selectsAppliedRange } from "./acceptedRange";
import { DEFAULT_WORKBENCH_URL, localWorkbenchUrl } from "./workbenchClient";
const runFile = promisify(execFile);
const digest = (value: string | Buffer) => createHash("sha256").update(value).digest("hex");
type Edit = {
    uri: string;
    offset: number;
    before: string;
    after: string;
    previousHash: string;
    diskHash: string;
    acceptedHash: string;
    acceptedDiskHash?: string;
    experienceId: string;
    sourceCode: string;
    title: string;
    scope: string;
    version: string;
};
type Receipt = Record<string, unknown>;
type TestOptions = {
    testUri?: vscode.Uri;
    title?: string;
};
function sameContext(uri: vscode.Uri, expected: {
    scope: string;
    version: string;
}) {
    const current = memoryContext(uri);
    return current.scope === expected.scope && current.version === expected.version;
}
function projectDocument() {
    const editor = vscode.window.activeTextEditor;
    if (!vscode.workspace.isTrusted)
        throw new Error("请先信任当前工作区，再运行项目测试或写入源码。");
    if (!editor || editor.document.languageId !== "python" || editor.document.uri.scheme !== "file")
        throw new Error("请打开工作区中的本地 Python 源文件。");
    const folder = vscode.workspace.getWorkspaceFolder(editor.document.uri);
    if (!folder)
        throw new Error("请先通过 VS Code 打开源文件所在的项目文件夹。");
    if (editor.document.isDirty)
        throw new Error("请先保存当前编辑，再验证或采纳经验。");
    if (vscode.workspace.textDocuments.some(doc => doc.isDirty && vscode.workspace.getWorkspaceFolder(doc.uri)?.uri.toString() === folder.uri.toString()))
        throw new Error("请先保存当前项目内的修改，以便 pytest 测试磁盘上的同一份代码。");
    return { editor, folder };
}
function inside(root: string, file: string): string {
    const relative = path.relative(fs.realpathSync(root), fs.realpathSync(file));
    if (!relative || relative === ".." || relative.startsWith(".." + path.sep) || path.isAbsolute(relative))
        throw new Error("请选择当前工作区内的文件。");
    return relative.split(path.sep).join("/");
}
function interpreter(root: string, uri: vscode.Uri): string {
    const config = vscode.workspace.getConfiguration("seeda", uri);
    const setting = config.get<string>("pythonPath", "").trim();
    if (setting)
        return setting;
    const service = config.get<string>("serviceRoot", "");
    const local = [path.join(root, ".venv", "Scripts", "python.exe"), path.join(root, ".venv", "bin", "python")];
    if (service)
        local.push(path.join(service, "runtime", "python.exe"));
    return local.find(item => fs.existsSync(item)) ?? "python";
}
export function registerProjectWorkflow(context: vscode.ExtensionContext, api: (uri?: vscode.Uri) => SeedaApiClient, output: vscode.OutputChannel) {
    let pendingEdit: Edit | undefined;
    const documents = new Map<string, string>();
    let running = false;
    const queue = () => context.workspaceState.get<Receipt[]>("pendingProjectTests", []);
    const register = (id: string, handler: (...args: any[]) => Promise<unknown>) => context.subscriptions.push(vscode.commands.registerCommand(id, async (...args) => {
        try {
            return await handler(...args);
        }
        catch (error) {
            const message = formatApiError(error);
            output.appendLine(message);
            void vscode.window.showErrorMessage(message);
            return { status: "error", error: message };
        }
    }));
    context.subscriptions.push(vscode.workspace.registerTextDocumentContentProvider("seeda-preview", {
        provideTextDocumentContent: uri => documents.get(uri.toString()) ?? "",
    }));
    register("seeda.startWorkbench", async () => {
        const config = vscode.workspace.getConfiguration("seeda");
        const endpoint = new URL(localWorkbenchUrl(config.get<string>("workbenchUrl", DEFAULT_WORKBENCH_URL)));
        const ready = async () => {
            try {
                const http = await fetch(endpoint.origin + "/api/workbench/ide-capabilities", { signal: AbortSignal.timeout(1200), redirect: "error" });
                const state = http.ok ? await http.json() as {
                    protocol?: number;
                    project_pytest?: boolean;
                    verified_browse?: boolean;
                } : {};
                return state.protocol === 1 && state.project_pytest === true && state.verified_browse === true;
            }
            catch {
                return false;
            }
        };
        if (await ready()) {
            void vscode.window.showInformationMessage("本机经验服务已经运行。");
            return { running: true };
        }
        let occupied = false;
        try {
            occupied = !!await fetch(endpoint.origin + "/api/workbench/overview", { signal: AbortSignal.timeout(1200), redirect: "error" });
        }
        catch { }
        if (occupied)
            throw new Error("该地址上的服务不支持 0.3 项目测试协议。请关闭旧服务后启动配套版本，或更换本机端口。");
        if (endpoint.protocol !== "http:" || !["localhost", "127.0.0.1"].includes(endpoint.hostname))
            throw new Error("自动启动用于本机 HTTP 服务；自定义地址请手动启动。");
        let root = config.get<string>("serviceRoot", "");
        if (!root || !fs.existsSync(path.join(root, "run_service.py"))) {
            const dirs = await vscode.window.showOpenDialog({ canSelectFolders: true, canSelectFiles: false, canSelectMany: false, openLabel: "选择含 run_service.py 的本地配套服务目录" });
            if (!dirs?.length)
                return;
            root = dirs[0].fsPath;
        }
        const script = path.join(root, "run_service.py"), python = path.join(root, "runtime", "python.exe");
        if (!fs.existsSync(script) || !fs.existsSync(python))
            throw new Error("未找到 run_service.py 或 runtime/python.exe。请完整解压配套服务包并选择其根目录。");
        await config.update("serviceRoot", root, vscode.ConfigurationTarget.Global);
        const proc = spawn(python, [script, "--port", endpoint.port || "80"], { cwd: root, windowsHide: true, detached: true, stdio: "ignore" });
        await new Promise<void>((resolve, reject) => { proc.once("spawn", resolve); proc.once("error", reject); });
        proc.unref();
        const deadline = Date.now() + 60000;
        while (Date.now() < deadline) {
            await new Promise(resolve => setTimeout(resolve, 500));
            if (await ready()) {
                void vscode.window.showInformationMessage("本机经验服务已就绪。");
                return { running: true };
            }
        }
        throw new Error("服务尚未就绪。可从配套目录双击启动服务.cmd，查看启动诊断后重试。");
    });
    type BrowseRow = {id: string; title: string; code: string; source?: string; test?: string};
    const browseLabel = "浏览本项目此版本的已验证经验";
    const previewExperience = async (options?: {experienceId?: string; browse?: boolean; query?: string; returnCandidates?: boolean}) => {
        const { editor, folder } = projectDocument();
        const doc = editor.document, target = editor.selection;
        if (target.isEmpty && !options?.browse)
            throw new Error("请先选中要替换的代码，使差异预览只覆盖该选区。");
        const source = doc.getText(), old = doc.getText(target), offset = doc.offsetAt(target.start), revision = doc.version;
        const memory = memoryContext(doc.uri), client = api(doc.uri);
        const verifiedRows = async (query?: string):Promise<BrowseRow[]> => (await client.experiences(true, query))
            .filter(x => x.validated && !x.archived && x.scope===memory.scope && x.version===memory.version && x.receipt?.is_success===true)
            .map(x => ({id:x.id,title:x.requirement,code:x.code,source:x.source_path,test:x.test_path||x.receipt?.public_test_set_id}));
        let hits:BrowseRow[];
        if(options?.experienceId) {
            hits=(await verifiedRows()).filter(x=>x.id===options.experienceId);
        } else if(options?.browse) {
            hits=await verifiedRows(options.query);
            if(options.returnCandidates) return hits.map(({id,title,source,test})=>({id,title,source,test}));
        } else {
            const query=await vscode.window.showInputBox({title:"查找可采纳的项目经验",prompt:memory.scope+" / "+memory.version,value:old.slice(0,300)});
            if(!query?.trim()) return {status:"cancelled"};
            hits=(await client.search(query.trim(),8)).map(x=>({id:x.experience_id,title:x.task_intent.original_requirement,code:x.execution_result.final_output,source:x.source_path,test:x.test_path}));
            if(!hits.length) {
                const answer=await vscode.window.showInformationMessage("没有找到与查询匹配的经验。",browseLabel);
                if(answer!==browseLabel) return {status:"empty"};
                hits=await verifiedRows(query.trim());
            }
        }
        if (!hits.length) {
            void vscode.window.showInformationMessage(options?.experienceId?"此经验当前无法在本项目与版本中采纳。":"当前项目与版本没有可浏览的已验证经验。可先用项目 pytest 记录一次修改。");
            return { status: "empty" };
        }
        const chosen = options?.experienceId ? hits[0] : (await vscode.window.showQuickPick(hits.map(row => ({ label: row.title, description: memory.scope + " / " + memory.version, detail: (row.source || "工作台函数任务") + " · " + (row.test || "公开测试"), row })), { title: "选择经验并预览差异" }))?.row;
        if (!chosen)
            return;
        if (target.isEmpty) {
            void vscode.window.showInformationMessage("来源 "+(chosen.source||"工作台函数任务")+" · 测试 "+(chosen.test||"公开用例")+"。请在文件中选中要替换的代码，再预览差异。");
            return {status:"selection_required"};
        }
        if (doc.version !== revision || !sameContext(doc.uri, memory))
            throw new Error("选择经验期间源文件、项目或版本已变化，请重新预览。");
        const after = replacementWithTargetEnding(chosen.code, old, source.slice(offset + old.length),
            doc.eol === vscode.EndOfLine.CRLF ? "\r\n" : "\n");
        const proposed = source.slice(0, offset) + after + source.slice(offset + old.length);
        pendingEdit = { uri: doc.uri.toString(), offset, before: old, after, previousHash: digest(source), diskHash: digest(fs.readFileSync(doc.fileName)), acceptedHash: digest(proposed), experienceId: chosen.id, sourceCode: chosen.code, title: chosen.title, scope: memory.scope, version: memory.version };
        documents.clear();
        const preview = vscode.Uri.from({ scheme: "seeda-preview", path: "/" + randomUUID() + "/" + path.basename(doc.fileName) });
        documents.set(preview.toString(), proposed);
        const provenance = memory.scope + " / " + memory.version + " · 来源 " + (chosen.source || "工作台函数任务") + " · 测试 " + (chosen.test || "公开用例");
        output.appendLine(provenance);
        await vscode.commands.executeCommand("vscode.diff", doc.uri, preview, "SEED-A · " + provenance, { preview: true });
        const previewed = pendingEdit;
        void vscode.window.showInformationMessage("待采纳差异：" + provenance, "采纳并保存").then(choice => {
            if (choice === "采纳并保存" && pendingEdit === previewed)
                void vscode.commands.executeCommand("seeda.acceptExperience");
        });
        return { preview: true, experience_id: chosen.id };
    };
    register("seeda.applyExperience", (options?:{experienceId?:string})=>previewExperience(options));
    register("seeda.browseProjectExperiences", (options?:{returnCandidates?:boolean;query?:string})=>
        previewExperience({browse:true,returnCandidates:options?.returnCandidates,query:options?.query}));
    register("seeda.acceptExperience", async () => {
        if (!pendingEdit)
            throw new Error("请先在原文件中选择代码并预览经验差异。");
        const item = pendingEdit, uri = vscode.Uri.parse(item.uri), doc = await vscode.workspace.openTextDocument(uri);
        const editor = await vscode.window.showTextDocument(doc);
        if (!vscode.workspace.isTrusted || doc.isDirty || digest(doc.getText()) !== item.previousHash || digest(fs.readFileSync(doc.fileName)) !== item.diskHash || !sameContext(uri, item))
            throw new Error("原文件、项目或版本已变化，或工作区未受信任，请重新预览。");
        const range = new vscode.Range(doc.positionAt(item.offset), doc.positionAt(item.offset + item.before.length));
        if (!await editor.edit(edit => edit.replace(range, item.after)))
            throw new Error("未能应用选区修改。");
        if (!await doc.save())
            throw new Error("代码已修改但未能保存；可用编辑器撤销后重试。");
        if (digest(doc.getText()) !== item.acceptedHash)
            throw new Error("保存时其他工具改变了文件。请查看实际差异；可用编辑器撤销。");
        item.acceptedDiskHash = digest(fs.readFileSync(doc.fileName));
        editor.selection = new vscode.Selection(doc.positionAt(item.offset), doc.positionAt(item.offset + item.after.length));
        await context.workspaceState.update("lastAcceptedExperience", item);
        pendingEdit = undefined;
        void vscode.window.showInformationMessage("已采纳并保存。可选一个项目测试文件进行验证，或撤销本次采纳。", "验证项目测试").then(c => { if (c)
            void vscode.commands.executeCommand("seeda.verifySelection"); });
        return { applied: true };
    });
    register("seeda.undoExperience", async () => {
        const item = context.workspaceState.get<Edit>("lastAcceptedExperience");
        if (!item)
            throw new Error("当前工作区没有可撤销的采纳记录。");
        const doc = await vscode.workspace.openTextDocument(vscode.Uri.parse(item.uri));
        const editor = await vscode.window.showTextDocument(doc);
        if (!vscode.workspace.isTrusted || doc.isDirty || digest(doc.getText()) !== item.acceptedHash || digest(fs.readFileSync(doc.fileName)) !== item.acceptedDiskHash || !sameContext(doc.uri, item))
            throw new Error("采纳后源文件、项目或版本已有变化，已保留当前内容。请手动查看差异或使用编辑器撤销。");
        const range = new vscode.Range(doc.positionAt(item.offset), doc.positionAt(item.offset + item.after.length));
        if (!await editor.edit(edit => edit.replace(range, item.before)) || !await doc.save())
            throw new Error("撤销未完整保存，请检查编辑器。");
        await context.workspaceState.update("lastAcceptedExperience", undefined);
        void vscode.window.showInformationMessage("已恢复采纳前的选区并保存。");
        return { undone: true };
    });
    register("seeda.retryProjectReceipts", async () => {
        if (running)
            throw new Error("当前已有验证或回传工作进行中。");
        running = true;
        try {
            const work = queue();
            let sent = 0;
            for (const item of work) {
                await api().recordProjectTest(item);
                await context.workspaceState.update("pendingProjectTests", queue().filter(r => r.receipt_id !== item.receipt_id));
                sent++;
            }
            void vscode.window.showInformationMessage("已同步 " + sent + " 份项目测试收据。");
            return { sent };
        }
        finally {
            running = false;
        }
    });
    register("seeda.verifySelection", async (options?: TestOptions) => {
        if (running)
            throw new Error("当前已有验证或回传工作进行中。");
        running = true;
        try {
            const { editor, folder } = projectDocument(), doc = editor.document, root = folder.uri.fsPath;
            const memory = memoryContext(doc.uri), source = doc.fileName, original = doc.getText(), rev = doc.version;
            const fileLabel = inside(root, source);
            const last = context.workspaceState.get<Edit>("lastAcceptedExperience");
            const validEdit = last && last.uri === doc.uri.toString() && sameContext(doc.uri, last)
                && last.acceptedHash === digest(original) && last.acceptedDiskHash === digest(fs.readFileSync(source)) ? last : undefined;
            const start = doc.offsetAt(editor.selection.start), end = doc.offsetAt(editor.selection.end);
            const used = validEdit && selectsAppliedRange(original, start, end, validEdit) ? validEdit : undefined;
            if (validEdit && !used && editor.selection.isEmpty)
                throw new Error("请将光标移入刚采纳的片段以复测这条经验，或明确选中其他代码以记录新的经验。");
            const code = used ? used.after : editor.selection.isEmpty ? original : doc.getText(editor.selection);
            const offset = used ? used.offset : editor.selection.isEmpty ? 0 : start;
            if (!code.trim() || code.length > 20000)
                throw new Error("请选择 1 至 20000 字符的有效 Python 代码。");
            const title = options?.title || used?.title || await vscode.window.showInputBox({ title: "这条经验可以解决什么问题？", prompt: "写明可复用的任务或错误现象", validateInput: v => v.trim() && v.trim().length <= 120 ? undefined : "请填写 1 至 120 字" });
            if (!title?.trim())
                return;
            const test = options?.testUri || (await vscode.window.showOpenDialog({ defaultUri: folder.uri, canSelectMany: false, filters: { "Python 测试": ["py"] }, openLabel: "运行此 pytest 文件" }))?.[0];
            if (!test)
                return;
            const testLabel = inside(root, test.fsPath), before = digest(fs.readFileSync(source)), testBefore = digest(fs.readFileSync(test.fsPath));
            if (rev !== doc.version || doc.isDirty || !sameContext(doc.uri, memory))
                throw new Error("源文件、作用域或版本已变化，请重新选择并验证。");
            if (!testLabel.endsWith(".py"))
                throw new Error("请选择项目内的 Python 测试文件。");
            const script = context.asAbsolutePath("media/run_project_tests.py");
            const python = interpreter(root, doc.uri);
            const response = await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "SEED-A 正在运行 " + testLabel }, () => runFile(python, [script, source, test.fsPath], { cwd: root, timeout: 130000, maxBuffer: 1024 * 1024, windowsHide: true, encoding: "utf8" })
                .catch(error => { output.appendLine(String(error.stderr || error.message)); throw new Error("无法完成项目测试。请查看 SEED-A 输出，确认 seeda.pythonPath 指向已安装 pytest 和项目依赖的解释器。"); }));
            const result = JSON.parse(response.stdout), { output: log, ...evidence } = result;
            output.appendLine(String(log || ""));
            if (doc.version !== rev || doc.isDirty || !sameContext(doc.uri, memory) || before !== result.file_sha256 || before !== digest(fs.readFileSync(source)) || testBefore !== result.test_sha256 || testBefore !== digest(fs.readFileSync(test.fsPath)))
                throw new Error("测试期间文件、测试、作用域或版本已变化，未将结果计入经验。");
            // Reuse preserves the originally admitted snippet bytes, even under a different editor EOL.
            const recordedCode = used?.sourceCode ?? code;
            const item: Receipt = { receipt_id: randomUUID().replace(/-/g, ""), title: title.trim(), scope: memory.scope, version: memory.version,
                code: recordedCode, code_sha256: digest(recordedCode), file_label: fileLabel, test_label: testLabel,
                first_line: doc.positionAt(offset).line + 1, last_line: doc.positionAt(offset + Math.max(code.length - 1, 0)).line + 1,
                source_id: used?.experienceId ?? null, ...evidence };
            await context.workspaceState.update("pendingProjectTests", [...queue(), item]);
            try {
                const reply = await api(doc.uri).recordProjectTest(item);
                await context.workspaceState.update("pendingProjectTests", queue().filter(row => row.receipt_id !== item.receipt_id));
                output.appendLine(JSON.stringify(reply));
                void vscode.window.showInformationMessage("pytest 通过 " + result.passed + "/" + result.total + "，跳过 " + result.skipped + "。" + (reply.experience_id ? "经验 " + reply.experience_id : "已记录本次未通过的收据。"));
                return reply;
            }
            catch (error) {
                void vscode.window.showWarningMessage("测试收据已保存在本机。请恢复经验服务后运行“重传项目测试收据”。" + formatApiError(error));
                return { status: "pending", receipt_id: item.receipt_id };
            }
        }
        finally {
            running = false;
        }
    });
    if (queue().length)
        void vscode.window.showInformationMessage("SEED-A 有尚未同步的项目测试收据。恢复服务后可重传。");
}
