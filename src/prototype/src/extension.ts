import * as vscode from "vscode";
import {
  ExperienceSearchResult,
  formatApiError,
  Recommendation,
  SeedaApiClient,
} from "./apiClient";
import { ExperienceViewProvider } from "./experienceView";
import { memoryContext } from "./workspaceContext";
import { registerProjectWorkflow } from "./projectWorkflow";
import {
  DEFAULT_WORKBENCH_URL, draftWorkspaceUrl, editorDraft, localWorkbenchUrl,
  WorkbenchClient, workbenchError,
} from "./workbenchClient";

function configuration(uri = vscode.window.activeTextEditor?.document.uri): {
  endpoint: string;
  timeoutMs: number;
  suggestionCount: number;
  scope: string;
  version: string;
} {
  const config = vscode.workspace.getConfiguration("seeda", uri);
  const memory = memoryContext(uri);
  return {
    endpoint: localWorkbenchUrl(config.get<string>("workbenchUrl", DEFAULT_WORKBENCH_URL)),
    timeoutMs: config.get<number>("requestTimeoutMs", 10_000),
    suggestionCount: config.get<number>("suggestionCount", 5),
    scope: memory.scope,
    version: memory.version,
  };
}

function client(context: vscode.ExtensionContext, uri?: vscode.Uri): SeedaApiClient {
  const config = configuration(uri);
  return new SeedaApiClient(
    config.endpoint,
    config.timeoutMs,
    context.secrets, config.scope, config.version,
  );
}

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel("SEED-A");
  const status = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    20,
  );
  status.command = "seeda.openWorkbench";
  status.text = "$(database) SEED-A";
  status.tooltip = "打开 SEED-A 研发工作台";
  status.show();

  const provider = new ExperienceViewProvider(
    context.extensionUri,
    () => client(context),
  );
  registerProjectWorkflow(context, uri => client(context, uri), output);
  context.subscriptions.push(
    output,
    status,
    vscode.window.registerWebviewViewProvider(
      ExperienceViewProvider.viewType,
      provider,
    ),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("seeda.openWorkbench", async () => {
      let endpoint = DEFAULT_WORKBENCH_URL;
      try {
        const config = configuration();
        endpoint = config.endpoint;
        const workbench = new WorkbenchClient(endpoint, config.timeoutMs, context.secrets);
        await workbench.checkConnection();
        if (!await vscode.env.openExternal(vscode.Uri.parse(endpoint))) {
          throw new Error("未能打开浏览器，请手动打开本机研发工作台地址");
        }
      } catch (error) {
        const choice = await vscode.window.showErrorMessage(workbenchError(error, endpoint), "启动本地服务");
        if (choice) await vscode.commands.executeCommand("seeda.startWorkbench");
      }
    }),
    vscode.commands.registerCommand("seeda.sendSelectionToWorkbench", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        void vscode.window.showWarningMessage("请先打开代码文件或选择要发送的代码");
        return;
      }
      let endpoint = DEFAULT_WORKBENCH_URL;
      try {
        const config = configuration();
        endpoint = config.endpoint;
        const selectedCode = editor.selection.isEmpty
          ? editor.document.getText() : editor.document.getText(editor.selection);
        const draft = editorDraft(selectedCode, editor.document.fileName, editor.document.languageId, config);
        const workbench = new WorkbenchClient(endpoint, config.timeoutMs, context.secrets);
        const draftId = await vscode.window.withProgress({
          location: vscode.ProgressLocation.Notification, title: "SEED-A 正在保存工作台草稿",
        }, () => workbench.saveDraft(draft));
        output.appendLine(`工作台草稿 ${draftId}：${draft.file_label}（${draft.code.length} 字符）`);
        const target = draftWorkspaceUrl(endpoint, draftId);
        if (!await vscode.env.openExternal(vscode.Uri.parse(target))) {
          void vscode.window.showWarningMessage(`草稿已保存，请手动打开 ${target}`);
          return;
        }
        void vscode.window.showInformationMessage("代码已保存到本机工作台草稿，请补充任务要求和测试后运行");
      } catch (error) {
        void vscode.window.showErrorMessage(workbenchError(error, endpoint));
      }
    }),
    vscode.commands.registerCommand("seeda.checkConnection", async () => {
      status.text = "$(sync~spin) SEED-A";
      try {
        const health = await client(context).health();
        status.text = `$(database) SEED-A ${health.total_experiences}`;
        status.tooltip = "共享研发工作台连接正常";
        void vscode.window.showInformationMessage(
          `SEED-A 共享工作台连接正常，经验记录 ${health.total_experiences}`,
        );
      } catch (error) {
        status.text = "$(error) SEED-A";
        status.tooltip = formatApiError(error);
        void vscode.window.showErrorMessage(formatApiError(error));
      }
    }),
    vscode.commands.registerCommand("seeda.configureApiKey", async () => {
      const value = await vscode.window.showInputBox({
        title: "配置 SEED-A 后端 API Key",
        password: true,
        ignoreFocusOut: true,
        prompt: "密钥仅保存在 VS Code SecretStorage 中；留空并确认可删除现有密钥",
      });
      if (value === undefined) {
        return;
      }
      if (value) {
        await context.secrets.store("seeda.apiKey", value);
        void vscode.window.showInformationMessage("SEED-A API Key 已安全保存");
      } else {
        await context.secrets.delete("seeda.apiKey");
        void vscode.window.showInformationMessage("SEED-A API Key 已删除");
      }
    }),
    vscode.commands.registerCommand("seeda.refreshLibrary", async () => {
      await provider.refresh();
    }),
    vscode.commands.registerCommand("seeda.searchExperience", async (options?: {query?: string; returnResults?: boolean}) => {
      const query = options?.query ?? await vscode.window.showInputBox({
        title: "搜索开发经验",
        prompt: "输入任务、错误信息、API 或项目约定",
        placeHolder: "例如：FastAPI 鉴权失败",
      });
      if (!query) {
        return;
      }
      try {
        const results = await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: "SEED-A 正在检索经验",
          },
          () => client(context).search(query, configuration().suggestionCount),
        );
        if (options?.returnResults) return results;
        await showSearchResults(results);
      } catch (error) {
        void vscode.window.showErrorMessage(formatApiError(error));
      }
    }),
    vscode.commands.registerCommand(
      "seeda.recommendExperience",
      async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
          void vscode.window.showWarningMessage("请先打开代码文件");
          return;
        }
        const selected = editor.document.getText(editor.selection).trim();
        const line = editor.document
          .lineAt(editor.selection.active.line)
          .text.trim();
        const currentCode = selected || line;
        if (!currentCode) {
          void vscode.window.showWarningMessage("请选择代码或将光标置于目标代码行");
          return;
        }
        try {
          const results = await client(context).recommend(
            currentCode,
            editor.document.languageId,
            configuration().suggestionCount,
          );
          await showRecommendations(results);
        } catch (error) {
          void vscode.window.showErrorMessage(formatApiError(error));
        }
      },
    ),
    vscode.commands.registerCommand("seeda.saveCurrentExperience", async () => {
      await vscode.commands.executeCommand("seeda.sendSelectionToWorkbench");
    }),
    vscode.commands.registerCommand("seeda.feedbackExperience", async () => {
      try {
        const api = client(context);
        const experiences = await api.experiences();
        if (!experiences.length) {
          void vscode.window.showInformationMessage("当前作用域及版本没有可反馈的活跃经验，请先在工作台完成带测试的任务");
          return;
        }
        const selected = await vscode.window.showQuickPick(experiences.map(item => ({
          label: item.title || item.requirement.slice(0, 80), description: `${item.scope} / ${item.version}`,
          detail: item.id, item,
        })), { title: "选择要反馈的共享工作台经验" });
        if (!selected) return;
        const outcome = await vscode.window.showQuickPick([
          { label: "复用成功", success: true },
          { label: "复用失败，归档以供复核", success: false },
        ], { title: "人工反馈（单独记录，不替代机器测试证据）" });
        if (!outcome) return;
        const note = await vscode.window.showInputBox({ title: "填写复用反馈", ignoreFocusOut: true,
          prompt: "描述使用场景与结果，最多1200字符", validateInput: value =>
            !value.trim() ? "请填写具体反馈" : value.length > 1200 ? "最多1200字符" : undefined });
        if (!note?.trim()) return;
        await api.feedback(selected.item.id, outcome.success, note.trim());
        void vscode.window.showInformationMessage("人工反馈已记录到共享工作台经验");
        await provider.refresh();
      } catch (error) {
        void vscode.window.showErrorMessage(formatApiError(error));
      }
    }),
    vscode.commands.registerCommand("seeda.runLifecycle", async () => {
      const answer = await vscode.window.showWarningMessage(
        "将归档失效经验并生成待测试的参数模板，是否继续？",
        { modal: true },
        "运行",
      );
      if (answer !== "运行") {
        return;
      }
      try {
        const result = await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: "SEED-A 正在维护经验库",
          },
          () => client(context).runLifecycle(),
        );
        output.appendLine(JSON.stringify(result, null, 2));
        const failedStages = ["archival", "generalization"].filter(
          (stage) => {
            const summary = result[stage];
            return summary !== null && typeof summary === "object" &&
              "error" in summary;
          },
        );
        if (failedStages.length) {
          void vscode.window.showWarningMessage(
            `生命周期维护部分失败（${failedStages.join("、")}），请查看 SEED-A 输出面板`,
          );
        } else {
          void vscode.window.showInformationMessage(
            "生命周期维护完成，详细结果已写入 SEED-A 输出面板",
          );
        }
        await provider.refresh();
      } catch (error) {
        void vscode.window.showErrorMessage(formatApiError(error));
      }
    }),
  );

  // Connect on demand: opening an editor must not trigger a server-start error.
}

async function showSearchResults(
  results: ExperienceSearchResult[],
): Promise<void> {
  if (results.length === 0) {
    void vscode.window.showInformationMessage("未找到相关经验");
    return;
  }
  const selected = await vscode.window.showQuickPick(
    results.map((item) => ({
      label: item.task_intent.original_requirement.slice(0, 80),
      description: `${item.task_intent.task_type} · 综合分 ${item.composite_score.toFixed(3)}`,
      detail: item.execution_result.final_output.slice(0, 180),
      item,
    })),
    { title: "SEED-A 经验检索结果", matchOnDescription: true, matchOnDetail: true },
  );
  if (!selected) {
    return;
  }
  await openMarkdown(
    `# SEED-A 经验详情

- 经验 ID：\`${selected.item.experience_id}\`
- 任务类型：${selected.item.task_intent.task_type}
- 检索相似度：${selected.item.similarity.toFixed(3)}
- 综合分：${selected.item.composite_score.toFixed(3)}
- 成功率元数据：${selected.item.dynamic_meta.success_rate.toFixed(3)}${selected.item.dynamic_meta.use_count === 0 ? "（尚无复用记录）" : ""}
- 使用次数：${selected.item.dynamic_meta.use_count}

## 原始需求

${selected.item.task_intent.original_requirement}

## 来源与验证记录

${selected.item.task_intent.user_instruction ?? "该经验未附加人工验证记录"}

## 经验输出

\`\`\`
${selected.item.execution_result.final_output}
\`\`\`
`,
  );
}

async function showRecommendations(
  results: Recommendation[],
): Promise<void> {
  if (results.length === 0) {
    void vscode.window.showInformationMessage("当前上下文没有命中可用经验");
    return;
  }
  const selected = await vscode.window.showQuickPick(
    results.map((item) => ({
      label: item.requirement.slice(0, 80),
      description: `${item.task_type} · 匹配 ${item.similarity.toFixed(3)}`,
      detail: item.suggestion.slice(0, 180),
      item,
    })),
    { title: "SEED-A 上下文经验推荐", matchOnDetail: true },
  );
  if (!selected) {
    return;
  }
  await openMarkdown(
    `# SEED-A 上下文推荐

- 经验 ID：\`${selected.item.experience_id}\`
- 相似度：${selected.item.similarity.toFixed(3)}
- 综合分：${selected.item.composite_score.toFixed(3)}

## 对应需求

${selected.item.requirement}

## 来源和测试

${selected.item.provenance || "该条经验尚无可展示的来源详情。"}

## 推荐内容

\`\`\`
${selected.item.suggestion}
\`\`\`
`,
  );
}

async function openMarkdown(content: string): Promise<void> {
  const document = await vscode.workspace.openTextDocument({
    content,
    language: "markdown",
  });
  await vscode.window.showTextDocument(document, { preview: true });
}

export function deactivate(): void {
  // VS Code disposes all registered resources through context.subscriptions.
}
