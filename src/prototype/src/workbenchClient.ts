import axios, { AxiosInstance } from "axios";

export const DEFAULT_WORKBENCH_URL = "http://127.0.0.1:8765";
export const MAX_DRAFT_CHARACTERS = 20_000;

export interface WorkbenchDraft {
  code: string;
  title: string;
  language: string;
  source: "vscode";
  file_label: string;
  scope?: string;
  version?: string;
}

/** A selected source buffer must never be sent to an external server or redirect. */
export function localWorkbenchUrl(value: string): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("seeda.workbenchUrl 必须是本机工作台地址，例如 http://127.0.0.1:8765");
  }
  if (!(["http:", "https:"].includes(url.protocol)) ||
      !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname.toLowerCase()) ||
      url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("工作台地址仅支持本机 loopback（127.0.0.1、localhost 或 ::1）的 HTTP(S) 根地址；不会发送代码到外部站点");
  }
  return url.origin;
}

export function editorDraft(code: string, fileName: string, language: string, context?: {scope: string; version: string}): WorkbenchDraft {
  if (!code.trim()) {
    throw new Error("选区或当前文件没有可发送的代码");
  }
  if (code.length > MAX_DRAFT_CHARACTERS) {
    throw new Error(`代码超过 ${MAX_DRAFT_CHARACTERS} 字符，请选择较小的代码片段后重试`);
  }
  const fileLabel = (fileName.split(/[\\/]/).pop() || "未命名代码").replace(/[\r\n\u0000]/g, "").slice(0, 255);
  return { code, title: `VS Code · ${fileLabel}`.slice(0, 120), language: language.slice(0, 50),
    source: "vscode", file_label: fileLabel.slice(0, 240), ...(context && {scope: context.scope, version: context.version}) };
}

export function draftWorkspaceUrl(endpoint: string, draftId: string): string {
  if (!draftId || draftId.length > 200 || /[\s\u0000-\u001f]/.test(draftId)) {
    throw new Error("工作台没有返回有效草稿 ID");
  }
  return `${localWorkbenchUrl(endpoint)}/#workspace?draft=${encodeURIComponent(draftId)}`;
}

export class WorkbenchClient {
  public readonly endpoint: string;
  private readonly http: AxiosInstance;

  public constructor(endpoint: string, timeoutMs: number,
    private readonly secrets: { get(key: string): PromiseLike<string | undefined> }) {
    this.endpoint = localWorkbenchUrl(endpoint);
    this.http = axios.create({ baseURL: this.endpoint, timeout: timeoutMs,
      proxy: false, maxRedirects: 0, headers: { "Content-Type": "application/json" } });
  }

  public async checkConnection(): Promise<void> {
    const response = await this.http.get("/api/workbench/overview");
    if (typeof response.data?.experiences_total !== "number") {
      throw new Error("该本机服务没有返回有效工作台状态，请检查 seeda.workbenchUrl");
    }
  }

  public async saveDraft(payload: WorkbenchDraft): Promise<string> {
    const apiKey = await this.secrets.get("seeda.apiKey");
    const response = await this.http.post("/api/workbench/drafts", payload,
      { headers: apiKey ? { "X-API-Key": apiKey } : {} });
    const id = response.data?.id ?? response.data?.draft_id;
    if (typeof id !== "string") {
      throw new Error("工作台返回了无效草稿响应；请检查工作台服务版本");
    }
    draftWorkspaceUrl(this.endpoint, id);
    return id;
  }
}

export function workbenchError(error: unknown, endpoint: string): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 401) {
      return "工作台 API Key 缺失或无效，请运行“SEED-A：配置后端 API Key”";
    }
    if (error.response?.status === 404) {
      return "该地址没有研发工作台接口，请启动新版工作台并检查 seeda.workbenchUrl";
    }
    if (error.response?.status && error.response.status >= 300 && error.response.status < 400) {
      return "本机工作台请求发生重定向，已停止发送；请配置直接访问的本机地址";
    }
    if (!error.response) {
      return `无法连接本机研发工作台 ${endpoint}。请在项目根目录运行 python tools/run_workbench.py，再重试；地址可在 seeda.workbenchUrl 中设置`;
    }
    return `工作台请求失败（HTTP ${error.response.status}），请检查服务输出`;
  }
  return error instanceof Error ? error.message : String(error);
}
