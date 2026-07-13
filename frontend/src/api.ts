import type {
  YieldPoint,
  NewsItem,
  NewsSource,
  SimilarNews,
  SimilarPeriod,
  MultiSimilarityResult,
  NewsYieldData,
  FactorCandidate,
  CandidatesResponse,
  CandidatesStats,
  ReviewAction,
  ReviewResponse,
  ChatMessage,
  AllStrategiesResponse,
  ForecastResponse,
  ForecastHistoryResponse,
  ForecastReport,
  ForecastPrediction,
  FullForecastReport,
  ForecastHistoryItem,
  GraphAugmentStartResponse,
  GraphAugmentStatusResponse,
  GraphAugmentResult,
  GraphAugmentExtractResult,
  GraphAugmentJob,
  GraphAugmentStatus,
  GraphAugmentNode,
  GraphAugmentRelationship,
  MacroSignalRequestLogQuery,
  MacroSignalRequestLogListResponse,
  ChangeSnapshotsResponse,
  ChangeCompareResponse,
  ChangeTriggerResponse,
} from "./types";
import { storage } from "./utils/helpers";
import { API_PREFIX } from "./constants";

const BASE = API_PREFIX;

/**
 * 获取认证请求头（如果已登录）
 */
function authHeaders(): Record<string, string> {
  const token = storage.get<string>("auth_token");
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

export async function fetchYields(
  start: string,
  end: string,
  type: string
): Promise<YieldPoint[]> {
  const r = await fetch(
    `${BASE}/yields?start=${start}&end=${end}&type=${type}`,
    { headers: authHeaders() }
  );
  return r.json();
}

export async function fetchNewsByDate(
  date: string,
  sources?: string[],
  model?: string,
  view: "best" | "single" | "all" = "best"
): Promise<NewsItem[]> {
  let url = `${BASE}/news?date=${date}&view=${view}`;
  if (sources && sources.length > 0) {
    url += `&source=${sources.join(",")}`;
  }
  if (model) {
    url += `&model=${encodeURIComponent(model)}`;
  }
  const r = await fetch(url, { headers: authHeaders() });
  return r.json();
}

export async function fetchNewsByDateRange(
  startDate: string,
  endDate: string,
  sources?: string[],
  model?: string,
  view: "best" | "single" | "all" = "best"
): Promise<NewsItem[]> {
  let url = `${BASE}/news?start_date=${startDate}&end_date=${endDate}&view=${view}`;
  if (sources && sources.length > 0) {
    url += `&source=${sources.join(",")}`;
  }
  if (model) {
    url += `&model=${encodeURIComponent(model)}`;
  }
  const r = await fetch(url, { headers: authHeaders() });
  return r.json();
}

export async function fetchNewsSources(): Promise<{ sources: NewsSource[] }> {
  const r = await fetch(`${BASE}/news/sources`, { headers: authHeaders() });
  return r.json();
}

export async function fetchLatestTradingDay(): Promise<{ latest_date: string }> {
  const r = await fetch(`${BASE}/news/latest-trading-day`, { headers: authHeaders() });
  return r.json();
}

export async function fetchNewsById(
  id: number,
  model?: string,
  includeAllModels: boolean = false
): Promise<NewsItem> {
  let url = `${BASE}/news/${id}`;
  const params = new URLSearchParams();
  if (model) {
    params.append("model", model);
  }
  if (includeAllModels) {
    params.append("include_all_models", "true");
  }
  const query = params.toString();
  if (query) {
    url += `?${query}`;
  }
  const r = await fetch(url, { headers: authHeaders() });
  return r.json();
}

export interface AnalyzeResponse {
  success: boolean;
  message?: string;
  analysis?: any;
  error?: string;
}

export async function analyzeNews(newsId: number, period: string = "10年"): Promise<AnalyzeResponse> {
  const r = await fetch(`${BASE}/news/${newsId}/analyze?period=${period}`, {
    method: "POST",
    headers: authHeaders(),
  });
  return r.json();
}

export async function fetchSimilarNews(newsId: number): Promise<SimilarNews[]> {
  const r = await fetch(`${BASE}/news/similar?news_id=${newsId}`, { headers: authHeaders() });
  return r.json();
}

export async function fetchSimilarPeriods(
  startDate: string,
  endDate: string,
  periods: string,
  topK: number = 5
): Promise<SimilarPeriod[]> {
  const r = await fetch(`${BASE}/yields/similar`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      start_date: startDate,
      end_date: endDate,
      periods: periods,
      top_k: topK,
    }),
  });
  return r.json();
}

export async function fetchNewsYieldData(
  newsId: number,
  period: string = "10年",
  windowBefore: number = 10,
  windowAfter: number = 10
): Promise<NewsYieldData> {
  const r = await fetch(
    `${BASE}/news/${newsId}/yield?period=${period}&window_before=${windowBefore}&window_after=${windowAfter}`,
    { headers: authHeaders() }
  );
  return r.json();
}

export interface FactorNewsItem {
  id: number;
  title: string;
  publish_time: string;
  publish_date: string;
  direction: string;
  horizon: string;
  factor_direction: string;
  model?: string;
}

export interface FactorNewsResponse {
  factor: {
    code: string;
    name: string;
    category: string;
  } | null;
  news: FactorNewsItem[];
  count: number;
}

export interface FactorDefinition {
  code: string;
  name: string;
  category: string;
}

export interface AllFactorsResponse {
  factors: FactorDefinition[];
  structure: Record<string, Record<string, [string, string, string][]>>;
}

export interface FactorsByCategoryResponse {
  category: string;
  subcategories: string[];
  factors: FactorDefinition[];
  count: number;
}

export async function fetchNewsByFactor(
  factorCode: string,
  model?: string
): Promise<FactorNewsResponse> {
  const encodedCode = encodeURIComponent(factorCode);
  const query = model ? `?model=${encodeURIComponent(model)}` : "";
  const r = await fetch(`${BASE}/factor/${encodedCode}/news${query}`, { headers: authHeaders() });
  return r.json();
}

export async function fetchAllFactors(): Promise<AllFactorsResponse> {
  const r = await fetch(`${BASE}/factors`, { headers: authHeaders() });
  return r.json();
}

export async function fetchFactorsByCategory(
  category: string
): Promise<FactorsByCategoryResponse> {
  const r = await fetch(`${BASE}/factors/by-category/${category}`, { headers: authHeaders() });
  return r.json();
}

// ========== 搜索 API ==========

export interface SearchNewsResponse {
  keyword: string;
  news: NewsItem[];
  count: number;
  error?: string;
}

export async function searchNews(
  keyword: string,
  limit: number = 20
): Promise<SearchNewsResponse> {
  const params = new URLSearchParams({
    keyword: keyword.trim(),
    limit: limit.toString(),
  });
  const r = await fetch(`${BASE}/search/news?${params}`, { headers: authHeaders() });
  return r.json();
}

// ========== 聊天 API ==========

export interface ChatResponse {
  content: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  error?: string;
  tool_result?: {
    news?: {
      id: number;
      title: string;
      summary: string;
      date: string;
      source: string;
      url: string;
      direction?: string;
      horizon?: string;
    }[];
  };
}

// ========== Forecast Report API ==========

export async function fetchForecastReport(date?: string): Promise<ForecastResponse> {
  const params = date ? `?date=${date}` : '';
  const r = await fetch(`${BASE}/forecast${params}`, { headers: authHeaders() });
  return r.json();
}

export async function fetchForecastHistory(limit: number = 30): Promise<ForecastHistoryResponse> {
  const r = await fetch(`${BASE}/forecast/history?limit=${limit}`, { headers: authHeaders() });
  return r.json();
}

/**
 * 发送聊天消息（流式输出）
 * @param messages 消息历史
 * @param onChunk 每收到一个chunk时的回调
 * @param onDone 完成时的回调
 * @param onError 错误时的回调
 * @param enableTools 是否启用工具调用
 */
export async function sendChatMessageStream(
  messages: ChatMessage[],
  onChunk: (content: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
  enableTools: boolean = false
): Promise<void> {
  try {
    const response = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({
        messages,
        stream: true,
        enable_tools: enableTools,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("无法获取响应流");
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            onDone();
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.content) {
              onChunk(parsed.content);
            }
            if (parsed.error) {
              onError(parsed.error);
              return;
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }

    onDone();
  } catch (error) {
    onError(error instanceof Error ? error.message : "未知错误");
  }
}

/**
 * 发送聊天消息（非流式）
 */
export async function sendChatMessage(
  messages: ChatMessage[],
  enableTools: boolean = false
): Promise<ChatResponse> {
  const response = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      messages,
      stream: false,
      enable_tools: enableTools,
    }),
  });

  return response.json();
}

// ========== Factor Candidates API ==========

export async function fetchFactorCandidates(
  status?: string,
  page: number = 1,
  limit: number = 20
): Promise<CandidatesResponse> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  params.append('page', page.toString());
  params.append('limit', limit.toString());

  const r = await fetch(`${BASE}/factor-candidates?${params}`, { headers: authHeaders() });
  return r.json();
}

export async function fetchCandidatesStats(): Promise<CandidatesStats> {
  const r = await fetch(`${BASE}/factor-candidates/stats`, { headers: authHeaders() });
  return r.json();
}

export async function fetchReviewQueue(): Promise<FactorCandidate[]> {
  const r = await fetch(`${BASE}/factor-candidates/review-queue`, { headers: authHeaders() });
  return r.json();
}

export async function reviewFactorCandidate(
  candidateId: number,
  action: ReviewAction
): Promise<ReviewResponse> {
  const r = await fetch(`${BASE}/factor-candidates/${candidateId}/review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(action),
  });
  return r.json();
}

// Re-export types for candidates.ts and chat.ts
export type { FactorCandidate, CandidatesStats, ReviewResponse, ChatMessage };

// ========== Graph Augmentation API ==========

export async function startGraphAugment(newsText: string): Promise<GraphAugmentStartResponse> {
  const r = await fetch(`${BASE}/augment/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({ newsText }),
  });
  return r.json();
}

export async function getGraphAugmentStatus(runId: string): Promise<GraphAugmentStatusResponse> {
  const r = await fetch(`${BASE}/augment/status?runId=${runId}`, { headers: authHeaders() });
  return r.json();
}

export async function getGraphAugmentResult(runId: string): Promise<GraphAugmentResult> {
  const r = await fetch(`${BASE}/augment/artifact?runId=${runId}&name=05_normalized.json`, { headers: authHeaders() });
  return r.json();
}

export async function getGraphAugmentExtract(runId: string): Promise<GraphAugmentExtractResult> {
  const r = await fetch(`${BASE}/augment/artifact?runId=${runId}&name=01_extract.json`, { headers: authHeaders() });
  return r.json();
}

export async function getGraphAugmentJobByNews(newsId: number): Promise<{ job: GraphAugmentJob | null }> {
  const r = await fetch(`${BASE}/graph-augment/job-by-news/${newsId}`, { headers: authHeaders() });
  return r.json();
}

export async function saveGraphAugmentResult(
  newsId: number,
  runId: string,
  status: GraphAugmentStatus,
  stage: string | null,
  result: GraphAugmentResult,
  extract: GraphAugmentExtractResult
): Promise<{ success: boolean; message?: string }> {
  const r = await fetch(`${BASE}/graph-augment/save`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      news_id: newsId,
      run_id: runId,
      status,
      stage,
      result_json: result,
      extract_json: extract,
    }),
  });
  return r.json();
}

export function connectGraphAugmentStream(runId: string): EventSource {
  const token = storage.get<string>("auth_token");
  const tokenParam = token ? `&token=${encodeURIComponent(token)}` : "";
  return new EventSource(`${BASE}/augment/stream?runId=${runId}${tokenParam}`);
}

// Re-export graph types
export type {
  GraphAugmentNode,
  GraphAugmentRelationship,
  GraphAugmentResult,
  GraphAugmentExtractResult,
  GraphAugmentJob,
  GraphAugmentStatus,
  GraphAugmentStartResponse,
  GraphAugmentStatusResponse,
};

export async function fetchMacroSignalRequestLogs(
  query: MacroSignalRequestLogQuery
): Promise<MacroSignalRequestLogListResponse> {
  const params = new URLSearchParams();
  if (query.page !== undefined) params.set("page", String(query.page));
  if (query.page_size !== undefined) params.set("page_size", String(query.page_size));
  if (query.request_id) params.set("request_id", query.request_id);
  if (query.factor_code) params.set("factor_code", query.factor_code);
  if (query.success !== undefined) params.set("success", String(query.success));
  if (query.signal_type) params.set("signal_type", query.signal_type);
  if (query.start_time) params.set("start_time", query.start_time);
  if (query.end_time) params.set("end_time", query.end_time);
  const r = await fetch(`${BASE}/macro/signal/logs?${params.toString()}`, { headers: authHeaders() });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || "请求失败");
  }
  return r.json();
}

// ========== Strategies ==========

export async function fetchAllStrategies(): Promise<AllStrategiesResponse> {
  const r = await fetch(`${API_PREFIX}/ai-strategy-recommendation/strategies`, { headers: authHeaders() });
  if (!r.ok) throw new Error('策略列表读取失败');
  return r.json();
}

// ========== Change / Strategy Comparison ==========

export async function fetchChangeSnapshots(hours: number = 168): Promise<ChangeSnapshotsResponse> {
  const r = await fetch(`${BASE}/change/snapshots?hours=${hours}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('快照列表读取失败');
  return r.json();
}

export async function fetchChangeCompare(
  oldSnapshotId?: number,
  newSnapshotId?: number,
  oldVersionTime?: string,
  newVersionTime?: string,
): Promise<ChangeCompareResponse> {
  const r = await fetch(`${BASE}/change/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      old_snapshot_id: oldSnapshotId,
      new_snapshot_id: newSnapshotId,
      old_version_time: oldVersionTime,
      new_version_time: newVersionTime,
    }),
  });
  if (!r.ok) throw new Error('快照对比失败');
  return r.json();
}

export async function triggerChangeSnapshot(force: boolean = false): Promise<ChangeTriggerResponse> {
  const r = await fetch(`${BASE}/change/trigger`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ force }),
  });
  if (!r.ok) throw new Error('快照触发失败');
  return r.json();
}
