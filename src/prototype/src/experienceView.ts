import * as vscode from "vscode";
import { formatApiError, LibraryStats, SeedaApiClient } from "./apiClient";

export class ExperienceViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "seeda.experienceView";
  private view?: vscode.WebviewView;

  public constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly getClient: () => SeedaApiClient,
  ) {}

  public resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this.extensionUri],
    };
    webviewView.webview.onDidReceiveMessage(async (message: unknown) => {
      if (!message || typeof message !== "object") {
        return;
      }
      const command = (message as { command?: string }).command;
      if (command === "refresh") {
        await this.refresh();
      } else if (command === "start") {
        await vscode.commands.executeCommand("seeda.startWorkbench");
        await this.refresh();
      } else if (command === "workbench") {
        await vscode.commands.executeCommand("seeda.openWorkbench");
      } else if (command === "draft") {
        await vscode.commands.executeCommand("seeda.sendSelectionToWorkbench");
      } else if (command === "feedback") {
        await vscode.commands.executeCommand("seeda.feedbackExperience");
      } else if (command === "search") {
        await vscode.commands.executeCommand("seeda.searchExperience");
      } else if (command === "recommend") {
        await vscode.commands.executeCommand("seeda.recommendExperience");
      } else if (command === "lifecycle") {
        await vscode.commands.executeCommand("seeda.runLifecycle");
      }
    });
    void this.refresh();
  }

  public async refresh(): Promise<void> {
    if (!this.view) {
      return;
    }
    this.view.webview.html = this.renderLoading();
    try {
      const stats = await this.getClient().stats();
      this.view.webview.html = this.renderStats(stats);
    } catch (error) {
      this.view.webview.html = this.renderError(formatApiError(error));
    }
  }

  private shell(body: string, script = ""): string {
    const nonce = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <style>
    body { padding: 12px; color: var(--vscode-foreground); font-family: var(--vscode-font-family); }
    .card { border: 1px solid var(--vscode-panel-border); border-radius: 6px; padding: 12px; margin-bottom: 10px; }
    .value { font-size: 24px; font-weight: 700; }
    .muted { color: var(--vscode-descriptionForeground); font-size: 12px; }
    button { width: 100%; margin: 4px 0; padding: 7px; color: var(--vscode-button-foreground);
      background: var(--vscode-button-background); border: 0; border-radius: 3px; cursor: pointer; }
    button:hover { background: var(--vscode-button-hoverBackground); }
    .error { color: var(--vscode-errorForeground); white-space: pre-wrap; }
  </style>
</head>
<body>${body}
<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();
  ${script}
</script>
</body>
</html>`;
  }

  private renderLoading(): string {
    return this.shell("<p>正在读取经验库状态……</p>");
  }

  private renderError(message: string): string {
    const escaped = escapeHtml(message);
    return this.shell(
      `<div class="card"><div class="error">${escaped}</div></div>
       <button id="start">启动或连接本地服务</button><button id="refresh">重新连接</button>`,
      "document.getElementById('start').onclick = () => vscode.postMessage({command:'start'});document.getElementById('refresh').onclick = () => vscode.postMessage({command:'refresh'});",
    );
  }

  private renderStats(stats: LibraryStats): string {
    const count = (value: unknown): string =>
      typeof value === "number" && Number.isInteger(value) && value >= 0 ? String(value) : "未提供";
    return this.shell(
      `<div class="card"><div class="muted">共享工作台经验记录</div><div class="value">${count(stats.total_experiences)}</div>
       <div class="muted">活跃 ${count(stats.active_nodes)} · 已归档 ${count(stats.archived_nodes)}</div></div>
       <div class="card"><div class="muted">真实任务运行</div><div class="value">${count(stats.runs_total)}</div>
       <div class="muted">完成 ${count(stats.completed)} · 测试成功 ${count(stats.successful)} · 排队/运行 ${count(stats.active_jobs)}</div></div>
       <div class="card"><div class="muted">参数模板候选</div><div class="value">${count(stats.templates_total)}</div>
       <div class="muted">实例化后仍需当前任务的真实测试。搜索和反馈使用配置的 memoryScope / memoryVersion。</div></div>
       <button id="workbench">打开研发工作台</button>
       <button id="draft">将代码保存为任务草稿</button>
       <button id="search">搜索经验</button>
       <button id="recommend">基于当前代码推荐</button>
       <button id="feedback">记录经验复用反馈</button>
       <button id="lifecycle">运行生命周期维护</button>
       <button id="refresh">刷新状态</button>`,
      [
        ["workbench", "workbench"],
        ["draft", "draft"],
        ["search", "search"],
        ["recommend", "recommend"],
        ["feedback", "feedback"],
        ["lifecycle", "lifecycle"],
        ["refresh", "refresh"],
      ]
        .map(
          ([id, command]) =>
            `document.getElementById('${id}').onclick = () => vscode.postMessage({command:'${command}'});`,
        )
        .join("\n"),
    );
  }
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
