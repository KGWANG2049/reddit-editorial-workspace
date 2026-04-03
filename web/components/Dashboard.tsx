"use client";

import {
  startTransition,
  useEffect,
  useEffectEvent,
  useState,
  useTransition,
} from "react";

import { api } from "../lib/api";
import type {
  DocumentDetail,
  DocumentRecord,
  Health,
  IntegrationStatus,
  IntegrationTestResult,
  ProcessDocumentsResponse,
  TaskJob,
} from "../lib/types";

const ACTIVE_JOB_STATUSES = new Set(["queued", "running"]);
const POLL_INTERVAL_MS = 2000;

function formatDate(value: string | null) {
  if (!value) {
    return "Pending";
  }
  return new Date(value).toLocaleString("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatStatus(status: string) {
  switch (status) {
    case "queued":
      return "排队中";
    case "capturing":
      return "抓取中";
    case "polishing":
      return "编排中";
    case "completed":
      return "已完成";
    case "failed":
      return "失败";
    case "running":
      return "运行中";
    case "succeeded":
      return "成功";
    default:
      return status;
  }
}

function readString(payload: Record<string, unknown>, key: string) {
  const value = payload[key];
  return typeof value === "string" ? value : null;
}

function readNumber(payload: Record<string, unknown>, key: string) {
  const value = payload[key];
  return typeof value === "number" ? value : null;
}

function statusClass(status: string) {
  if (status === "completed" || status === "succeeded") {
    return "status-chip status-chip-success";
  }
  if (status === "failed") {
    return "status-chip status-chip-error";
  }
  if (status === "capturing" || status === "polishing" || status === "queued" || status === "running") {
    return "status-chip status-chip-pending";
  }
  return "status-chip";
}

export function Dashboard() {
  const [health, setHealth] = useState<Health | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null);
  const [integrationChecks, setIntegrationChecks] = useState<
    Partial<Record<"obsidian" | "openai", IntegrationTestResult>>
  >({});
  const [integrationPending, setIntegrationPending] = useState<"obsidian" | "openai" | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [jobs, setJobs] = useState<TaskJob[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [urlInput, setUrlInput] = useState("");
  const [activeTab, setActiveTab] = useState<"raw" | "polished">("raw");
  const [message, setMessage] = useState("系统就绪，等待新的 URL 任务。");
  const [isPending, startUiTransition] = useTransition();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const hasActiveJobs = jobs.some((job) => ACTIVE_JOB_STATUSES.has(job.status));

  const refreshAll = useEffectEvent(async () => {
    const [healthData, integrationsData, documentData, jobData] = await Promise.all([
      api.health(),
      api.integrationStatus(),
      api.documents(),
      api.jobs(),
    ]);
    setHealth(healthData);
    setIntegrations(integrationsData);
    setDocuments(documentData);

    const selectedStillExists =
      selectedDocumentId && documentData.some((document) => document.id === selectedDocumentId)
        ? selectedDocumentId
        : documentData[0]?.id ?? null;
    setSelectedDocumentId(selectedStillExists);
    setJobs(jobData);

    if (selectedStillExists) {
      const detailData = await api.documentDetail(selectedStillExists);
      setDetail(detailData);
    } else {
      setDetail(null);
    }
  });

  useEffect(() => {
    startTransition(() => {
      void refreshAll().catch((error) => {
        setMessage(error instanceof Error ? error.message : "无法连接后端。");
      });
    });
  }, [refreshAll]);

  useEffect(() => {
    if (!selectedDocumentId) {
      return;
    }
    startUiTransition(() => {
      void api
        .documentDetail(selectedDocumentId)
        .then((data) => setDetail(data))
        .catch((error) => {
          setMessage(error instanceof Error ? error.message : "加载文档详情失败。");
        });
    });
  }, [selectedDocumentId]);

  useEffect(() => {
    if (!hasActiveJobs) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshAll().catch(() => undefined);
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs, refreshAll]);

  async function handleSubmitUrls() {
    const urls = urlInput
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (!urls.length) {
      setMessage("请输入至少一条 URL。");
      return;
    }

    try {
      setIsSubmitting(true);
      setMessage("正在创建抓取任务...");
      const result: ProcessDocumentsResponse = await api.processDocuments(urls);
      setUrlInput("");
      await refreshAll();
      const firstId = result.items[0]?.document.id ?? null;
      if (firstId) {
        setSelectedDocumentId(firstId);
        setActiveTab("raw");
      }
      setMessage(`已接收 ${result.accepted} 条 URL，后台任务已排队。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "URL 提交失败。");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleIntegrationTest(provider: "obsidian" | "openai") {
    try {
      setIntegrationPending(provider);
      setMessage(`正在测试 ${provider === "obsidian" ? "Obsidian" : "OpenAI"}...`);
      const result =
        provider === "obsidian" ? await api.testObsidianIntegration() : await api.testOpenAIIntegration();
      setIntegrationChecks((current) => ({ ...current, [provider]: result }));
      setMessage(result.ok ? `${provider} 测试通过。` : `${provider} 测试失败：${result.detail}`);
      await refreshAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "集成测试失败。");
    } finally {
      setIntegrationPending(null);
    }
  }

  async function handleRetry(job: TaskJob) {
    try {
      setMessage("正在创建重试任务...");
      await api.retryJob(job.id);
      await refreshAll();
      setMessage("已提交重试任务。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务重试失败。");
    }
  }

  return (
    <div className="atelier-shell">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">URL Markdown Workbench</p>
          <h1>把网页链接整理成可落进 Obsidian 的双层 Markdown 文档。</h1>
          <p className="hero-text">
            一次粘贴多条 URL。后台先抓取网页原始 Markdown，再用 OpenAI 把内容重组为更易读的
            polished 版本，同时把图片统一收敛到本地附件目录。
          </p>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <span>Queue</span>
            <strong>{health?.queue_backend ?? "..."}</strong>
          </div>
          <div className="metric-card">
            <span>Documents</span>
            <strong>{documents.length}</strong>
          </div>
          <div className="metric-card">
            <span>Jobs</span>
            <strong>{jobs.length}</strong>
          </div>
          <div className="metric-card">
            <span>Output Root</span>
            <strong className="metric-path">{health?.output_root ?? "未配置"}</strong>
          </div>
        </div>
      </section>

      <section className="panel composer-panel">
        <div className="panel-header">
          <div>
            <p className="panel-kicker">Ingest</p>
            <h2>URL 输入面板</h2>
          </div>
          <div className={statusClass(hasActiveJobs ? "queued" : "completed")}>{message}</div>
        </div>
        <div className="composer-grid">
          <label className="field-label">
            一行一条 URL
            <textarea
              className="url-textarea"
              value={urlInput}
              onChange={(event) => setUrlInput(event.currentTarget.value)}
              placeholder={"https://example.com/article-one\nhttps://example.com/article-two"}
              disabled={isSubmitting}
            />
          </label>
          <div className="composer-sidecar">
            <div className="note-card">
              <p className="note-label">流程</p>
              <ol>
                <li>Capture 生成 `raw.md`</li>
                <li>本地化图片为 `assets/*`</li>
                <li>Polish 生成 `polished.md`</li>
              </ol>
            </div>
            <button className="primary-button" onClick={handleSubmitUrls} disabled={isSubmitting || isPending}>
              {isSubmitting ? "创建中..." : "提交处理任务"}
            </button>
          </div>
        </div>
      </section>

      <section className="panel integrations-panel">
        <div className="panel-header">
          <div>
            <p className="panel-kicker">Integrations</p>
            <h2>外部能力检查</h2>
          </div>
        </div>
        <div className="integration-grid">
          <article className="integration-card">
            <div className="integration-topline">
              <strong>Obsidian</strong>
              <span className={statusClass(integrations?.obsidian.configured ? "completed" : "failed")}>
                {integrations?.obsidian.configured ? "已配置" : "未配置"}
              </span>
            </div>
            <p>{integrations?.obsidian.detail ?? "等待后端状态..."}</p>
            <button
              className="secondary-button"
              disabled={integrationPending === "obsidian"}
              onClick={() => handleIntegrationTest("obsidian")}
            >
              {integrationPending === "obsidian" ? "检测中..." : "测试 Obsidian"}
            </button>
            {integrationChecks.obsidian ? (
              <p className={integrationChecks.obsidian.ok ? "integration-success" : "integration-error"}>
                {integrationChecks.obsidian.detail}
              </p>
            ) : null}
          </article>

          <article className="integration-card">
            <div className="integration-topline">
              <strong>OpenAI</strong>
              <span className={statusClass(integrations?.openai.configured ? "completed" : "failed")}>
                {integrations?.openai.configured ? "已配置" : "未配置"}
              </span>
            </div>
            <p>{integrations?.openai.detail ?? "等待后端状态..."}</p>
            <p className="integration-model">Model: {integrations?.openai.model ?? "..."}</p>
            <button
              className="secondary-button"
              disabled={integrationPending === "openai"}
              onClick={() => handleIntegrationTest("openai")}
            >
              {integrationPending === "openai" ? "检测中..." : "测试 OpenAI"}
            </button>
            {integrationChecks.openai ? (
              <p className={integrationChecks.openai.ok ? "integration-success" : "integration-error"}>
                {integrationChecks.openai.detail}
              </p>
            ) : null}
          </article>
        </div>
      </section>

      <section className="workspace-grid">
        <aside className="panel document-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Documents</p>
              <h2>最近文档</h2>
            </div>
          </div>
          <div className="document-list">
            {documents.length ? (
              documents.map((document) => (
                <button
                  key={document.id}
                  type="button"
                  className={`document-item ${selectedDocumentId === document.id ? "active" : ""}`}
                  onClick={() => {
                    setSelectedDocumentId(document.id);
                    setActiveTab(document.polished_markdown_path ? "polished" : "raw");
                  }}
                >
                  <div className="document-item-topline">
                    <span>{document.source_title ?? document.slug}</span>
                    <span className={statusClass(document.status)}>{formatStatus(document.status)}</span>
                  </div>
                  <p>{document.source_url}</p>
                  <div className="document-item-meta">
                    <span>{document.asset_count} assets</span>
                    <span>{formatDate(document.updated_at)}</span>
                  </div>
                </button>
              ))
            ) : (
              <div className="empty-state">
                <p>还没有文档。先从上方粘贴几条 URL。</p>
              </div>
            )}
          </div>
        </aside>

        <main className="panel detail-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Detail</p>
              <h2>{detail?.source_title ?? "文档详情"}</h2>
            </div>
            {detail ? <span className={statusClass(detail.status)}>{formatStatus(detail.status)}</span> : null}
          </div>

          {detail ? (
            <div className="detail-stack">
              <div className="detail-summary">
                <div>
                  <span>Source URL</span>
                  <strong>{detail.source_url}</strong>
                </div>
                <div>
                  <span>Output Dir</span>
                  <strong>{detail.output_dir ?? "Pending"}</strong>
                </div>
                <div>
                  <span>Updated</span>
                  <strong>{formatDate(detail.updated_at)}</strong>
                </div>
              </div>

              <div className="tab-strip">
                <button
                  className={activeTab === "raw" ? "tab-button active" : "tab-button"}
                  onClick={() => setActiveTab("raw")}
                  type="button"
                >
                  Raw Markdown
                </button>
                <button
                  className={activeTab === "polished" ? "tab-button active" : "tab-button"}
                  onClick={() => setActiveTab("polished")}
                  type="button"
                >
                  Polished Markdown
                </button>
              </div>

              <div className="markdown-viewer">
                <pre>
                  {activeTab === "raw"
                    ? detail.raw_markdown ?? "raw.md 尚未生成。"
                    : detail.polished_markdown ?? "polished.md 尚未生成。"}
                </pre>
              </div>

              <div className="asset-panel">
                <div className="asset-header">
                  <p className="panel-kicker">Assets</p>
                  <h3>本地附件</h3>
                </div>
                {detail.assets.length ? (
                  <div className="asset-list">
                    {detail.assets.map((asset) => (
                      <article key={asset.path} className="asset-card">
                        <strong>{asset.name}</strong>
                        <span>{asset.size_bytes} bytes</span>
                        <code>{asset.path}</code>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state compact">
                    <p>当前文档还没有本地图片附件。</p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="empty-state detail-empty">
              <p>选择左侧文档以查看 raw / polished 内容与附件清单。</p>
            </div>
          )}
        </main>

        <aside className="panel job-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Jobs</p>
              <h2>任务历史</h2>
            </div>
          </div>
          <div className="job-list">
            {jobs.length ? (
              jobs.map((job) => {
                const sourceTitle =
                  readString(job.result_payload, "source_title") ??
                  documents.find((document) => document.id === job.target_id)?.source_title ??
                  "Untitled";
                const assetCount = readNumber(job.result_payload, "asset_count");
                return (
                  <article key={job.id} className="job-card">
                    <div className="job-topline">
                      <strong>{sourceTitle}</strong>
                      <span className={statusClass(job.status)}>{formatStatus(job.status)}</span>
                    </div>
                    <p>{job.task_type}</p>
                    <div className="job-meta">
                      <span>{formatDate(job.created_at)}</span>
                      {assetCount !== null ? <span>{assetCount} assets</span> : null}
                    </div>
                    {job.error ? <p className="job-error">{job.error}</p> : null}
                    {job.status === "failed" ? (
                      <button className="ghost-button" type="button" onClick={() => void handleRetry(job)}>
                        重试
                      </button>
                    ) : null}
                  </article>
                );
              })
            ) : (
              <div className="empty-state compact">
                <p>任务列表为空。</p>
              </div>
            )}
          </div>
        </aside>
      </section>
    </div>
  );
}
