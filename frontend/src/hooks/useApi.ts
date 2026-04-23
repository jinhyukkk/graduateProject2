import { useQuery, useQueries, useMutation } from '@tanstack/react-query';
import type {
  DatabasesResponse,
  QueryResult,
  ConfigResponse,
  ExperimentsResponse,
  ExperimentDetail,
  ExperimentResultsResponse,
  ExperimentCreateResponse,
  ExperimentConfig,
  KSweepConfig,
  BatchExperiment,
  QueryDetailResult,
} from '../types';

const API_BASE = '';

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ============================================================
// Query keys
// ============================================================

export const queryKeys = {
  databases: ['databases'] as const,
  config: ['config'] as const,
  experiments: (params?: Record<string, string | number>) =>
    ['experiments', params] as const,
  experiment: (id: string) => ['experiments', id] as const,
  experimentResults: (
    id: string,
    params?: Record<string, string | number>,
  ) => ['experiments', id, 'results', params] as const,
  experimentQuery: (expId: string, qid: number) =>
    ['experiments', expId, 'query', qid] as const,
};

// ============================================================
// Config & databases
// ============================================================

export function useDatabases() {
  return useQuery({
    queryKey: queryKeys.databases,
    queryFn: () => fetchJson<DatabasesResponse>('/api/databases'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useConfig() {
  return useQuery({
    queryKey: queryKeys.config,
    queryFn: () => fetchJson<ConfigResponse>('/api/config'),
    staleTime: 10 * 60 * 1000,
  });
}

// ============================================================
// Query (single NL query execution)
// ============================================================

export function useRunQuery() {
  return useMutation({
    mutationFn: (payload: {
      query: string;
      db_id: string;
      dataset?: string;
      conversation_history?: Array<{ question: string; sql: string; explanation?: string }>;
    }) =>
      fetchJson<QueryResult>('/api/query', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
  });
}

// ============================================================
// Streaming query (SSE)
// ============================================================

export interface StreamQueryPayload {
  query: string;
  db_id: string;
  dataset?: string;
  conversation_history?: Array<{ question: string; sql: string; explanation?: string }>;
}

/**
 * /api/query/stream へ POST し、SSE イベントをコールバックで返す。
 * 各イベント: step / sql_generated / validated / verified / corrected / explanation / result / error
 */
export async function streamQuery(
  payload: StreamQueryPayload,
  onEvent: (event: string, data: unknown) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/query/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  if (!res.body) throw new Error('No response body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE メッセージは \n\n で区切られる
      const messages = buffer.split('\n\n');
      buffer = messages.pop() ?? '';

      for (const message of messages) {
        if (!message.trim()) continue;
        const lines = message.split('\n');
        let eventName = 'message';
        let dataStr = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) eventName = line.slice(7).trim();
          else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
        }

        if (dataStr) {
          try {
            onEvent(eventName, JSON.parse(dataStr));
          } catch {
            onEvent(eventName, dataStr);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ============================================================
// Experiments
// ============================================================

export function useExperiments(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.offset) searchParams.set('offset', String(params.offset));
  const qs = searchParams.toString();

  return useQuery({
    queryKey: queryKeys.experiments(params as Record<string, string | number>),
    queryFn: () =>
      fetchJson<ExperimentsResponse>(`/api/experiments${qs ? `?${qs}` : ''}`),
    staleTime: 10_000,
  });
}

export function useExperiment(id: string | null) {
  return useQuery({
    queryKey: queryKeys.experiment(id!),
    queryFn: () => fetchJson<ExperimentDetail>(`/api/experiments/${id}`),
    enabled: !!id,
    staleTime: 10_000,
  });
}

export function useExperimentResults(
  id: string | null,
  params?: {
    filter?: string;
    sort_by?: string;
    sort_order?: string;
    page?: number;
    page_size?: number;
  },
) {
  const searchParams = new URLSearchParams();
  if (params?.filter && params.filter !== 'all')
    searchParams.set('filter', params.filter);
  if (params?.sort_by) searchParams.set('sort_by', params.sort_by);
  if (params?.sort_order) searchParams.set('sort_order', params.sort_order);
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.page_size) searchParams.set('page_size', String(params.page_size));
  const qs = searchParams.toString();

  return useQuery({
    queryKey: queryKeys.experimentResults(
      id!,
      params as Record<string, string | number>,
    ),
    queryFn: () =>
      fetchJson<ExperimentResultsResponse>(
        `/api/experiments/${id}/results${qs ? `?${qs}` : ''}`,
      ),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useExperimentQueryDetail(
  expId: string | null,
  qid: number | null,
) {
  return useQuery({
    queryKey: queryKeys.experimentQuery(expId!, qid!),
    queryFn: () =>
      fetchJson<QueryDetailResult>(
        `/api/experiments/${expId}/results/${qid}`,
      ),
    enabled: !!expId && qid !== null,
  });
}

export function useCreateExperiment() {
  return useMutation({
    mutationFn: (config: ExperimentConfig) =>
      fetchJson<ExperimentCreateResponse>('/api/experiments', {
        method: 'POST',
        body: JSON.stringify(config),
      }),
  });
}

// ============================================================
// K-Sweep batch
// ============================================================

export function useCreateKSweep() {
  return useMutation({
    mutationFn: (config: KSweepConfig) =>
      fetchJson<BatchExperiment>('/api/experiments/k-sweep', {
        method: 'POST',
        body: JSON.stringify(config),
      }),
  });
}

export function useBatchStatus(batchId: string | null) {
  return useQuery({
    queryKey: ['batch', batchId] as const,
    queryFn: () =>
      fetchJson<BatchExperiment>(`/api/experiments/batch/${batchId}`),
    enabled: !!batchId,
    refetchInterval: 3000,
  });
}

// ============================================================
// Cross-experiment comparison
// ============================================================

export function useMultipleExperiments(ids: string[]) {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: queryKeys.experiment(id),
      queryFn: () => fetchJson<ExperimentDetail>(`/api/experiments/${id}`),
      staleTime: 30_000,
    })),
  });
}
