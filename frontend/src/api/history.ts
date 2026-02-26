import { apiRequest } from './client';
import { ProcessingHistoryResponse, ProcessingHistoryStats } from './types';

export interface HistoryQueryParams {
  page?: number;
  limit?: number;
  status?: 'completed' | 'failed';
  podcastSlug?: string;
  sortBy?: 'processed_at' | 'processing_duration_seconds' | 'ads_detected' | 'reprocess_number' | 'llm_cost';
  sortDir?: 'asc' | 'desc';
}

export async function getProcessingHistory(
  params: HistoryQueryParams = {}
): Promise<ProcessingHistoryResponse> {
  const queryParams = new URLSearchParams();

  if (params.page !== undefined) queryParams.set('page', String(params.page));
  if (params.limit !== undefined) queryParams.set('limit', String(params.limit));
  if (params.status) queryParams.set('status', params.status);
  if (params.podcastSlug) queryParams.set('podcast_slug', params.podcastSlug);
  if (params.sortBy) queryParams.set('sort_by', params.sortBy);
  if (params.sortDir) queryParams.set('sort_dir', params.sortDir);

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/history?${queryString}` : '/history';

  return apiRequest<ProcessingHistoryResponse>(endpoint);
}

export async function getProcessingHistoryStats(): Promise<ProcessingHistoryStats> {
  return apiRequest<ProcessingHistoryStats>('/history/stats');
}

export async function exportProcessingHistory(format: 'csv' | 'json'): Promise<Blob> {
  const response = await fetch(`/api/v1/history/export?format=${format}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Export failed' }));
    throw new Error(error.error || `HTTP ${response.status}`);
  }

  return response.blob();
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
