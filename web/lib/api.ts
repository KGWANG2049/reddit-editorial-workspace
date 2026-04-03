import type {
  DocumentDetail,
  DocumentRecord,
  Health,
  IntegrationStatus,
  IntegrationTestResult,
  ProcessDocumentsResponse,
  TaskJob,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  integrationStatus: () => request<IntegrationStatus>("/integrations/status"),
  testObsidianIntegration: () =>
    request<IntegrationTestResult>("/integrations/obsidian/test", {
      method: "POST",
    }),
  testOpenAIIntegration: () =>
    request<IntegrationTestResult>("/integrations/openai/test", {
      method: "POST",
    }),
  processDocuments: (urls: string[]) =>
    request<ProcessDocumentsResponse>("/documents/process", {
      method: "POST",
      body: JSON.stringify({ urls }),
    }),
  documents: (limit = 50) => request<DocumentRecord[]>(`/documents?limit=${limit}`),
  documentDetail: (documentId: string) => request<DocumentDetail>(`/documents/${documentId}`),
  jobs: (limit = 20) => request<TaskJob[]>(`/jobs?limit=${limit}`),
  job: (jobId: string) => request<TaskJob>(`/jobs/${jobId}`),
  retryJob: (jobId: string) =>
    request<TaskJob>(`/jobs/${jobId}/retry`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
};
