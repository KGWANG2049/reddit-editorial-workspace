export type Health = {
  status: string;
  queue_backend: string;
  output_root: string | null;
};

export type IntegrationProviderStatus = {
  provider: string;
  configured: boolean;
  mode: string;
  detail: string;
  model?: string | null;
};

export type IntegrationStatus = {
  obsidian: IntegrationProviderStatus;
  openai: IntegrationProviderStatus;
};

export type IntegrationTestResult = {
  provider: string;
  ok: boolean;
  detail: string;
};

export type TaskJob = {
  id: string;
  task_type: string;
  status: string;
  queue_backend: string;
  target_id: string | null;
  result_payload: Record<string, unknown>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type DocumentRecord = {
  id: string;
  source_url: string;
  source_title: string | null;
  slug: string;
  status: string;
  output_dir: string | null;
  raw_markdown_path: string | null;
  polished_markdown_path: string | null;
  asset_count: number;
  metadata: Record<string, unknown>;
  error: string | null;
  created_at: string;
  updated_at: string;
  processed_at: string | null;
};

export type Asset = {
  name: string;
  path: string;
  size_bytes: number;
};

export type DocumentDetail = DocumentRecord & {
  raw_markdown: string | null;
  polished_markdown: string | null;
  assets: Asset[];
  latest_job: TaskJob | null;
};

export type DocumentQueueItem = {
  document: DocumentRecord;
  job: TaskJob;
};

export type ProcessDocumentsResponse = {
  accepted: number;
  items: DocumentQueueItem[];
};
