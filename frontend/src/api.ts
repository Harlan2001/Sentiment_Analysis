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
  AiStrategyGenerationResponse,
  AiStrategyConversationCreateResponse,
  AiStrategyConversationDetailResponse,
  AiStrategyConversationListResponse,
  AiStrategyPromptDraftResponse,
} from "@/types";
import { storage } from "@/utils/helpers";
import { API_PREFIX } from "@/constants";

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

/** 流式回调接口（新版，类型化 SSE 事件） */
export interface StreamCallbacks {
  onThinking?: () => void;
  onContent?: (content: string) => void;
  onToolCall?: (toolCalls: { id: string; name: string; arguments: Record<string, unknown> }[]) => void;
  onToolExecuting?: (toolCallId: string, toolName: string, args: Record<string, unknown>) => void;
  onToolResult?: (
    toolCallId: string,
    toolName: string,
    result: unknown | null,
    error: string | null,
    durationMs?: number
  ) => void;
  onDone?: (usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }) => void;
  onError?: (message: string, code?: string) => void;
}

/**
 * 发送聊天消息（新版流式，支持类型化 SSE 事件）
 * 支持 thinking / content / tool_call / tool_executing / tool_result / done / error 事件
 */
export async function sendChatMessageStream(
  messages: { role: string; content: string }[],
  callbacks: StreamCallbacks
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
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6);
        if (data === "[DONE]") {
          return; // done 事件已由 SSE done 事件处理
        }
        try {
          const parsed = JSON.parse(data);
          switch (parsed.type) {
            case "thinking":
              callbacks.onThinking?.();
              break;
            case "content":
              callbacks.onContent?.(parsed.content);
              break;
            case "tool_call":
              callbacks.onToolCall?.(parsed.tool_calls);
              break;
            case "tool_executing":
              callbacks.onToolExecuting?.(
                parsed.tool_call_id,
                parsed.tool_name,
                parsed.arguments
              );
              break;
            case "tool_result":
              callbacks.onToolResult?.(
                parsed.tool_call_id,
                parsed.tool_name,
                parsed.result ?? null,
                parsed.error ?? null,
                parsed.duration_ms
              );
              break;
            case "done":
              callbacks.onDone?.(parsed.usage);
              return;
            case "error":
              callbacks.onError?.(parsed.message, parsed.code);
              return;
          }
        } catch (_e) {
          // 忽略解析错误
        }
      }
    }
  } catch (error) {
    callbacks.onError?.(error instanceof Error ? error.message : "未知错误", "NETWORK_ERROR");
  }
}

/**
 * @deprecated 使用新版 sendChatMessageStream(messages, callbacks) 替代。
 * 旧版兼容包装，将 5 参数转为回调对象。
 */
export async function sendChatMessageStreamLegacy(
  messages: ChatMessage[],
  onChunk: (content: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
  _enableTools: boolean = false
): Promise<void> {
  return sendChatMessageStream(messages, {
    onContent: (content) => onChunk(content),
    onDone: () => onDone(),
    onError: (message) => onError(message),
  });
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
    }),
  });

  return response.json();
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

// ========== Dashboard API ==========

import type {
  DashboardCoreData,
  BehaviorStats,
  AuditLogResponse,
  PageVisitEvent,
  BehaviorBatchResponse,
  UserBehaviorProfile,
  UserProfileListResponse,
  UserCompareResponse,
} from "./types";

export async function fetchDashboardCore(): Promise<DashboardCoreData> {
  const r = await fetch(`${BASE}/dashboard/core`, { headers: authHeaders() });
  if (!r.ok) {
    const text = await r.text().catch(() => '');
    throw new Error(`服务器错误 ${r.status}${text ? ': ' + text.slice(0, 200) : ''}`);
  }
  return r.json();
}

export async function fetchDashboardHistory(days: number = 7): Promise<any[]> {
  const r = await fetch(`${BASE}/dashboard/history?days=${days}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('历史快照获取失败');
  return r.json();
}

export async function triggerDashboardSnapshot(): Promise<{ success: boolean; snapshot_id: number | null }> {
  const r = await fetch(`${BASE}/dashboard/snapshot`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error('快照生成失败');
  return r.json();
}

export async function fetchBehaviorStats(days: number = 7): Promise<BehaviorStats> {
  const r = await fetch(`${BASE}/dashboard/behavior-stats?days=${days}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('行为统计数据获取失败');
  return r.json();
}

export async function fetchBehaviorLogs(params: {
  user_id?: string;
  page_route?: string;
  action_type?: string;
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<AuditLogResponse> {
  const searchParams = new URLSearchParams();
  if (params.user_id) searchParams.set('user_id', params.user_id);
  if (params.page_route) searchParams.set('page_route', params.page_route);
  if (params.action_type) searchParams.set('action_type', params.action_type);
  if (params.start) searchParams.set('start', params.start);
  if (params.end) searchParams.set('end', params.end);
  searchParams.set('limit', String(params.limit || 100));
  searchParams.set('offset', String(params.offset || 0));

  const r = await fetch(`${BASE}/dashboard/behavior-logs?${searchParams}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('审计日志获取失败');
  return r.json();
}

export async function postBehaviorBatch(events: PageVisitEvent[]): Promise<BehaviorBatchResponse> {
  const r = await fetch(`${BASE}/dashboard/behavior/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ events }),
  });
  if (!r.ok) throw new Error('行为事件上报失败');
  return r.json();
}

// ========== User Profile API ==========

export async function fetchActiveUsers(): Promise<{ users: { id: number; username: string; display_name: string; department: string | null; company: string | null; role: string }[] }> {
  const r = await fetch(`${BASE}/dashboard/users/active`, { headers: authHeaders() });
  if (!r.ok) throw new Error('活跃用户列表获取失败');
  return r.json();
}

export async function fetchUserProfiles(sortBy: string = 'last_visit', order: string = 'desc'): Promise<UserProfileListResponse> {
  const r = await fetch(`${BASE}/dashboard/behavior/profiles?sort_by=${sortBy}&order=${order}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('用户画像列表获取失败');
  return r.json();
}

export async function fetchUserProfile(userId: number): Promise<UserBehaviorProfile> {
  const r = await fetch(`${BASE}/dashboard/behavior/profile/${userId}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('用户画像获取失败');
  return r.json();
}

export async function fetchUserCompare(userIds: number[]): Promise<UserCompareResponse> {
  const r = await fetch(`${BASE}/dashboard/behavior/compare?user_ids=${userIds.join(',')}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('用户对比失败');
  return r.json();
}

export async function triggerProfileCompute(userId: number): Promise<{ user_id: number; username: string; computed: boolean }> {
  const r = await fetch(`${BASE}/dashboard/behavior/compute-profile/${userId}`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error('画像计算触发失败');
  return r.json();
}

export async function triggerAllProfilesCompute(): Promise<{ total_users: number; computed: number }> {
  const r = await fetch(`${BASE}/dashboard/behavior/compute-all-profiles`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error('批量画像计算失败');
  return r.json();
}

// ========== Token Usage API ==========

import type {
  TokenOverview,
  TokenTrendResponse,
  TokenByModelResponse,
  UserTokenListResponse,
} from "./types";

export async function fetchTokenOverview(): Promise<TokenOverview> {
  const r = await fetch(`${BASE}/dashboard/token/overview`, { headers: authHeaders() });
  if (!r.ok) throw new Error('Token概览获取失败');
  return r.json();
}

export async function fetchTokenTrend(days: number = 7): Promise<TokenTrendResponse> {
  const r = await fetch(`${BASE}/dashboard/token/trend?days=${days}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('Token趋势获取失败');
  return r.json();
}

export async function fetchTokenByModel(days: number = 7): Promise<TokenByModelResponse> {
  const r = await fetch(`${BASE}/dashboard/token/by-model?days=${days}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('Token模型分布获取失败');
  return r.json();
}

export async function fetchUserTokenList(params: {
  sort_by?: string;
  order?: string;
  limit?: number;
  offset?: number;
  search?: string;
} = {}): Promise<UserTokenListResponse> {
  const sp = new URLSearchParams();
  if (params.sort_by) sp.set('sort_by', params.sort_by);
  if (params.order) sp.set('order', params.order);
  sp.set('limit', String(params.limit || 50));
  sp.set('offset', String(params.offset || 0));
  if (params.search) sp.set('search', params.search);
  const r = await fetch(`${BASE}/dashboard/token/users?${sp}`, { headers: authHeaders() });
  if (!r.ok) throw new Error('用户Token列表获取失败');
  return r.json();
}

// ========== Macro Data API ==========

import type {
  MacroIndicatorsResponse,
  MacroDataResponse,
} from "./types";

export async function fetchMacroIndicators(): Promise<MacroIndicatorsResponse> {
  const r = await fetch(`${BASE}/macro-data/indicators`, { headers: authHeaders() })
  if (!r.ok) throw new Error('获取指标列表失败')
  return r.json()
}

export async function fetchMacroData(
  zbcodes: string[],
  start?: string,
  end?: string,
): Promise<MacroDataResponse> {
  const params = new URLSearchParams()
  params.set('zbcode', zbcodes.join(','))
  if (start) params.set('start', start)
  if (end) params.set('end', end)

  const r = await fetch(`${BASE}/macro-data/data?${params.toString()}`, {
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error('获取宏观数据失败')
  return r.json()
}


export async function createAiStrategyConversation(title: string): Promise<AiStrategyConversationCreateResponse> {
  const response = await fetch(`${BASE}/ai-strategy-generation/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to create history conversation');
  }
  return response.json();
}

export async function fetchAiStrategyConversations(): Promise<AiStrategyConversationListResponse> {
  const response = await fetch(`${BASE}/ai-strategy-generation/conversations`, { headers: authHeaders() });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to load history conversations');
  }
  return response.json();
}

export async function fetchAiStrategyConversation(conversationId: number): Promise<AiStrategyConversationDetailResponse> {
  const response = await fetch(`${BASE}/ai-strategy-generation/conversations/${conversationId}`, { headers: authHeaders() });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to load history conversation');
  }
  return response.json();
}

export async function createAiStrategyPromptDraft(
  conversationId: number,
  requirement: string,
): Promise<AiStrategyPromptDraftResponse> {
  const response = await fetch(`${BASE}/ai-strategy-generation/conversations/${conversationId}/draft`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ requirement }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Unable to build the strategy prompt draft');
  }
  return response.json();
}

export async function confirmAiStrategyPromptDraft(
  conversationId: number,
  assistantMessageId: number,
  editedPrompt: string,
): Promise<AiStrategyGenerationResponse> {
  const response = await fetch(`${BASE}/ai-strategy-generation/conversations/${conversationId}/drafts/${assistantMessageId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ edited_prompt: editedPrompt }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'DreamStrategy generation failed');
  }
  return response.json();
}
