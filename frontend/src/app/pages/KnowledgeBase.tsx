import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  BookOpen,
  FileText,
  Layers,
  LoaderCircle,
  Trash2,
  Upload,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { PageState } from "../components/PageState";
import { StatusBanner } from "../components/StatusBanner";
import { documentsApi, getApiErrorMessage, type DocumentItem } from "../lib/api";
import { validateKnowledgeFile } from "../validation/knowledge";

function documentStatus(doc: DocumentItem): string {
  return (doc.status || doc.parsing_status || "uploaded").toLowerCase();
}

function documentStatusLabel(status: string): string {
  if (status === "uploaded") return "已上传";
  if (status === "indexing") return "索引中";
  if (status === "ready") return "已入库";
  if (status === "failed") return "处理失败";
  return status;
}

function isBuiltInDocument(doc: DocumentItem): boolean {
  return (
    doc.source === "system" ||
    /^w0\d+\.docx$/i.test(doc.filename) ||
    /^\d{2}_.+\.docx$/i.test(doc.filename)
  );
}

function metadataNumber(doc: DocumentItem, key: string): number {
  const metadata = doc.metadata_json;
  if (!metadata || typeof metadata !== "object") return 0;
  const value = (metadata as Record<string, unknown>)[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) return numeric;
  }
  return 0;
}

const BUILT_IN_SUBJECTS = [
  "课程方案（总纲）",
  "道德与法治",
  "语文",
  "历史",
  "英语",
  "地理",
  "科学",
  "物理",
  "生物学",
  "信息科技",
  "体育与健康",
  "艺术",
  "劳动",
  "数学",
  "化学",
];

export function KnowledgeBase() {
  const { user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [notice, setNotice] = useState("");

  const loadDocuments = async () => {
    setError("");
    try {
      const data = await documentsApi.list();
      setDocuments(data || []);
    } catch (err) {
      setError(getApiErrorMessage(err, "加载知识库失败"));
    }
  };

  useEffect(() => {
    let mounted = true;
    async function bootstrap() {
      setIsLoading(true);
      try {
        const data = await documentsApi.list();
        if (!mounted) return;
        setDocuments(data || []);
      } catch (err) {
        if (!mounted) return;
        setError(getApiErrorMessage(err, "加载知识库失败"));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    bootstrap();
    return () => {
      mounted = false;
    };
  }, []);

  const processingCount = useMemo(
    () => documents.filter((doc) => ["uploaded", "indexing"].includes(documentStatus(doc))).length,
    [documents],
  );

  useEffect(() => {
    if (processingCount === 0) return;
    const timer = window.setInterval(() => {
      loadDocuments();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [processingCount]);

  const builtInDocs = useMemo(() => documents.filter(isBuiltInDocument), [documents]);
  const customDocs = useMemo(() => documents.filter((doc) => !isBuiltInDocument(doc)), [documents]);

  const readyCount = customDocs.filter((doc) => documentStatus(doc) === "ready").length;
  const builtInReadyCount = builtInDocs.filter((doc) => documentStatus(doc) === "ready").length;
  const builtInChunkCount = useMemo(
    () => builtInDocs.reduce((sum, doc) => sum + metadataNumber(doc, "chunk_count"), 0),
    [builtInDocs],
  );
  const builtInProcessingCount = builtInDocs.filter((doc) => ["uploaded", "indexing"].includes(documentStatus(doc))).length;
  const builtInFailedCount = builtInDocs.filter((doc) => documentStatus(doc) === "failed").length;

  const handleChooseFile = () => {
    fileInputRef.current?.click();
  };

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const fileError = validateKnowledgeFile(file);
    if (fileError) {
      setError(fileError);
      setNotice("");
      return;
    }

    setUploading(true);
    setNotice("");
    try {
      await documentsApi.upload(file);
      setNotice(`上传成功：${file.name}`);
      await loadDocuments();
    } catch (err) {
      setError(getApiErrorMessage(err, "文档上传失败"));
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (doc: DocumentItem) => {
    const confirmed = window.confirm(`确定删除「${doc.filename}」吗？`);
    if (!confirmed) return;

    setDeletingId(doc.id);
    setNotice("");
    try {
      await documentsApi.delete(doc.id);
      setNotice("文档已删除");
      await loadDocuments();
    } catch (err) {
      setError(getApiErrorMessage(err, "删除文档失败"));
    } finally {
      setDeletingId(null);
    }
  };

  if (!user || user.role !== "teacher") {
    return <PageState variant="warning" title="访问受限" description="知识库上传与管理仅对教师开放。" actionLabel="返回学生首页" actionTo="/student" />;
  }

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <section className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold mb-1">知识库</h1>
          <p className="text-sm text-text-secondary">课程标准文档 + 自定义教学资料统一管理。</p>
        </div>
        <div className="flex items-center gap-3">
          <input ref={fileInputRef} type="file" accept=".pdf,.doc,.docx" className="hidden" onChange={handleUpload} />
          <button
            onClick={handleChooseFile}
            disabled={uploading}
            className="px-5 py-3 bg-primary text-white rounded-xl font-bold hover:bg-primary-hover active:bg-primary-active disabled:opacity-60 flex items-center gap-2"
          >
            {uploading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />} 上传文档
          </button>
        </div>
      </section>

      {error && (
        <StatusBanner tone="error" message={error} actionLabel="重试" onAction={loadDocuments} />
      )}

      {notice && <StatusBanner tone="success" message={notice} />}

      <section className="bg-surface border border-border rounded-2xl p-6">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-success" /> 系统内置课程标准知识库
          </h2>
          {builtInFailedCount > 0 ? (
            <span className="text-xs bg-danger-soft text-danger px-2 py-1 rounded-full font-semibold">存在异常</span>
          ) : builtInProcessingCount > 0 ? (
            <span className="text-xs bg-warning-soft text-warning px-2 py-1 rounded-full font-semibold">索引处理中</span>
          ) : (
            <span className="text-xs bg-success-soft text-success px-2 py-1 rounded-full font-semibold">已就绪</span>
          )}
        </div>

        <p className="text-xs text-text-secondary mb-4">
          来源：预置《义务教育课程标准（2022年版）》学科文档，系统已按语义切分为 RAG chunks，不需要逐个文件操作。
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          <div className="rounded-xl border border-success/20 bg-success-soft p-3">
            <p className="text-[11px] text-success">内置文档</p>
            <p className="text-xl font-black text-success">{builtInDocs.length}</p>
          </div>
          <div className="rounded-xl border border-secondary bg-secondary p-3">
            <p className="text-[11px] text-primary">知识块（chunks）</p>
            <p className="text-xl font-black text-primary">{builtInChunkCount}</p>
          </div>
          <div className="rounded-xl border border-border-strong bg-surface-muted p-3">
            <p className="text-[11px] text-text-secondary">就绪文档</p>
            <p className="text-xl font-black text-text">{builtInReadyCount}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {BUILT_IN_SUBJECTS.map((subject) => (
            <span
              key={subject}
              className="text-xs px-2 py-1 rounded-full border border-success/20 bg-success-soft text-success"
            >
              {subject}
            </span>
          ))}
        </div>

        {builtInDocs.length === 0 && (
          <StatusBanner
            tone="warning"
            message="当前未发现系统课标知识库，请执行 seed 脚本恢复系统内置 chunks。"
            className="mt-4"
          />
        )}
      </section>

      <section className="bg-surface border border-border rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" /> 我的教学资料
          </h2>
          <span className="text-xs bg-secondary text-primary px-2 py-1 rounded-full font-semibold">
            已入库 {readyCount} 份
          </span>
        </div>

        {isLoading ? (
          <div className="py-8 text-center text-text-secondary">加载中...</div>
        ) : customDocs.length === 0 ? (
          <div className="py-8 text-center text-text-secondary border-2 border-dashed rounded-2xl">
            暂无自定义资料，点击右上角上传教学文档。
          </div>
        ) : (
          <div className="space-y-3">
            {customDocs.map((doc) => {
              const status = documentStatus(doc);
              const statusLabel = documentStatusLabel(status);
              const isReady = status === "ready";
              const isFailed = status === "failed";
              const isProcessing = status === "uploaded" || status === "indexing";

              return (
                <div key={doc.id} className="p-4 border border-border rounded-2xl bg-surface-muted flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-surface border border-border-strong flex items-center justify-center">
                    <FileText className="w-5 h-5 text-text-secondary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold truncate">{doc.filename}</p>
                    <p className="text-xs text-text-secondary">上传时间：{new Date(doc.upload_date).toLocaleString()}</p>
                    {doc.error_msg && <p className="text-xs text-danger mt-1">错误：{doc.error_msg}</p>}
                  </div>
                  <div className="text-xs font-semibold">
                    {isReady && <span className="text-success">{statusLabel}</span>}
                    {isFailed && <span className="text-danger">{statusLabel}</span>}
                    {isProcessing && <span className="text-warning">{statusLabel}</span>}
                  </div>
                  <button
                    onClick={() => handleDelete(doc)}
                    disabled={deletingId === doc.id}
                    className="p-2 rounded-lg border border-danger/25 text-danger hover:bg-danger-soft disabled:opacity-60"
                    title="删除文档"
                  >
                    {deletingId === doc.id ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {processingCount > 0 && (
          <div className="mt-4 bg-warning-soft border border-warning/20 rounded-xl p-3 text-xs text-warning flex items-center gap-2">
            <LoaderCircle className="w-4 h-4 animate-spin" /> {processingCount} 份文档处理中，页面每 3 秒自动刷新一次。
          </div>
        )}

        {builtInDocs.length > 0 && (
          <div className="mt-4 text-xs text-text-muted flex items-center gap-2">
            <Layers className="w-3.5 h-3.5" />
            系统内置文档已聚合为 chunks 概览展示，不在此处逐条列出（共隐藏 {builtInDocs.length} 份）。
          </div>
        )}
      </section>
    </div>
  );
}
