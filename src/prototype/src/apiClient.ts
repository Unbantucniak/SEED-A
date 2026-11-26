import axios, { AxiosInstance } from "axios";
import * as vscode from "vscode";
import { localWorkbenchUrl } from "./workbenchClient";

export interface HealthResponse {
  status: string;
  total_experiences: number;
  health_score?: number;
}

export interface LibraryStats {
  total_experiences: number;
  health_score?: number;
  outdated_count?: number;
  conflict_count?: number;
  [key: string]: unknown;
}

export interface ExperienceSearchResult {
  experience_id: string;
  source_path?: string;
  test_path?: string;
  scope?: string;
  version?: string;
  task_intent: {
    task_type: string;
    original_requirement: string;
    user_instruction?: string;
  };
  execution_result: {
    final_output: string;
    is_success: boolean;
    execution_time: number;
  };
  static_meta: {
    generalization: number;
  };
  dynamic_meta: {
    success_rate: number;
    use_count: number;
    timeliness: number;
  };
  similarity: number;
  composite_score: number;
}

export interface Recommendation {
  experience_id: string;
  task_type: string;
  requirement: string;
  suggestion: string;
  similarity: number;
  composite_score: number;
  provenance?: string;
}

export interface WorkbenchExperience {
  id: string;
  title?: string;
  requirement: string;
  scope: string;
  version: string;
  code: string;
  validated: boolean;
  archived: boolean;
  source_path?: string;
  test_path?: string;
  stats: { success_rate: number; use_count: number; timeliness: number };
  static_meta: { generalization: number };
  receipt?: { is_success?: boolean; execution_time?: number; executor_id?: string; public_test_set_id?: string;
    tests_passed?: number; tests_total?: number; code_sha256?: string };
}

export class SeedaApiClient {
  private readonly client: AxiosInstance;

  public constructor(endpoint: string, timeoutMs: number,
    private readonly secretStorage: vscode.SecretStorage,
    private readonly scope = "workbench-python", private readonly version = "v1") {
    this.client = axios.create({ baseURL: localWorkbenchUrl(endpoint), timeout: timeoutMs,
      headers: { "Content-Type": "application/json" }, proxy: false, maxRedirects: 0 });
    this.client.interceptors.request.use(async (config) => {
      const apiKey = await this.secretStorage.get("seeda.apiKey");
      if (apiKey) config.headers.set("X-API-Key", apiKey);
      return config;
    });
  }

  public async health(): Promise<HealthResponse> {
    const stats = await this.stats();
    return { status: "ok", total_experiences: stats.total_experiences };
  }

  public async stats(): Promise<LibraryStats> {
    const { data } = await this.client.get("/api/workbench/overview");
    return { ...data, total_experiences: data.experiences_total,
      active_nodes: data.experiences_active,
      archived_nodes: data.experiences_total - data.experiences_active };
  }

  public async experiences(verifiedOnly = false, query?: string): Promise<WorkbenchExperience[]> {
    if (verifiedOnly && query?.trim()) {
      try {
        const { data } = await this.client.post("/api/workbench/ide-ranked-experiences",
          { query: query.trim(), scope: this.scope, version: this.version });
        return data.experiences;
      } catch (error) {
        if (!axios.isAxiosError(error) || ![404, 405].includes(error.response?.status ?? 0)) throw error;
      }
    }
    const { data } = await this.client.get(verifiedOnly ? "/api/workbench/ide-verified-experiences" : "/api/workbench/experiences",
      { params: { scope: this.scope, version: this.version, include_archived: false } });
    return data.experiences;
  }

  public async search(query: string, topK: number): Promise<ExperienceSearchResult[]> {
    if (query.length > 6000) throw new Error("检索内容最多6000字符，请缩短任务描述或代码选区");
    const { data } = await this.client.post("/api/workbench/search",
      { query, top_k: topK, scope: this.scope, version: this.version });
    return data.experiences.map((item: WorkbenchExperience & { similarity: number; composite_score: number }) => ({
      experience_id: item.id, scope:item.scope, version:item.version, source_path:item.source_path, test_path:item.test_path,
      task_intent: { task_type: "code_generation", original_requirement: item.requirement,
        user_instruction: `项目范围 ${item.scope} / ${item.version}\n源文件 ${item.source_path || "工作台函数任务"}\n验证方式 ${item.receipt?.executor_id || "公开测试"}\n测试 ${item.test_path || item.receipt?.public_test_set_id || "未提供"} · 通过 ${item.receipt?.tests_passed ?? "?"}/${item.receipt?.tests_total ?? "?"}` },
      execution_result: { final_output: item.code, is_success: item.receipt?.is_success === true,
        execution_time: item.receipt?.execution_time ?? 0 },
      static_meta: item.static_meta, dynamic_meta: item.stats,
      similarity: item.similarity, composite_score: item.composite_score,
    }));
  }

  public async recommend(currentCode: string, language: string, topK: number): Promise<Recommendation[]> {
    const found = await this.search(`language:${language}\n${currentCode}`, topK);
    return found.map(item => ({ experience_id: item.experience_id,
      task_type: item.task_intent.task_type, requirement: item.task_intent.original_requirement,
      suggestion: item.execution_result.final_output, similarity: item.similarity,
      composite_score: item.composite_score, provenance:item.task_intent.user_instruction }));
  }

  public async feedback(id: string, success: boolean, note: string): Promise<WorkbenchExperience> {
    const { data } = await this.client.post(`/api/workbench/experiences/${encodeURIComponent(id)}/feedback`,
      { success, note, archive: !success });
    return data;
  }

  public async recordProjectTest(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    const response = await this.client.post("/api/workbench/ide-receipts", payload);
    return response.data;
  }

  public async runLifecycle(): Promise<Record<string, unknown>> {
    const archival = await this.client.post("/api/workbench/maintenance", { action: "archive_invalid" });
    const templates = await this.client.post("/api/workbench/maintenance", { action: "build_templates" });
    return { archival: archival.data, generalization: templates.data,
      template_status: "生成的参数模板仍需在工作台实例化、测试后使用" };
  }
}

export function formatApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 401) {
      return "后端 API Key 缺失或无效，请运行“SEED-A：配置后端 API Key”后重试";
    }
    if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") {
      return "SEED-A 后端请求超时，请检查服务状态或调整 seeda.requestTimeoutMs";
    }
    const detail = error.response?.data?.detail;
    if (error.response?.status === 422 && Array.isArray(detail)) {
      const fields = detail.map((item: { loc?: unknown[]; msg?: string }) =>
        `${item.loc?.slice(1).join(".") || "请求"}：${item.msg || "参数无效"}`,
      );
      return `请求参数不符合后端要求：${fields.join("；")}`;
    }
    if (typeof detail === "string") {
      return `${error.message}：${detail}`;
    }
    if (error.code === "ECONNREFUSED") {
      return "无法连接本机研发工作台，请在项目根目录运行 python tools/run_workbench.py，并检查 seeda.workbenchUrl";
    }
    return error.message;
  }
  return error instanceof Error ? error.message : String(error);
}
