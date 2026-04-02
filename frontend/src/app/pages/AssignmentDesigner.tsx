import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import {
  CircleAlert,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  FileText,
  LoaderCircle,
  Plus,
  Sparkles,
  Upload,
  WandSparkles,
  X,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { PageState } from "../components/PageState";
import { StatusBanner } from "../components/StatusBanner";
import {
  assignmentsApi,
  documentsApi,
  getApiErrorMessage,
  subjectsApi,
  type Assignment,
  type DocumentItem,
  type Subject,
} from "../lib/api";
import { type LessonStepDraft } from "../lib/mappers";
import {
  applyLessonPlanDraft,
  assignmentStatusLabel,
  type AssignmentDesignerForm,
  type AssignmentDesignerPreviewState,
  type AssignmentDesignerTouchedField,
  type AssignmentDesignerTouchedFields,
  buildDesignerCreatePayload,
  buildDesignerFormFromAssignment,
  buildDesignerInitialForm,
  buildLessonPlanDraftRequest,
  buildDesignerPreviewState,
  defaultRubricNames,
  formatAIGenerationMeta,
  formatLessonPlanApplySummary,
  gradeLabelByStage,
  mergeDesignerFormWithPreview,
  buildDesignerUpdatePayload,
  isLessonPlanTouchedField,
  scoreStageLabel,
} from "../view-models/assignment";
import { validateAssignmentDesignerForm } from "../validation/assignment";

type EditorTab = "editor" | "history";
type NoticeTone = "success" | "warning" | "error";
type AIFeedbackFlow = "preview" | "lessonPlan";

const AI_FEEDBACK_STEPS: Record<AIFeedbackFlow, string[]> = {
  preview: ["整理表单上下文", "检索学科知识片段", "生成任务步骤与目标", "校验格式并回传"],
  lessonPlan: ["解析教案与关键信息", "识别主副学科并筛选片段", "生成任务步骤与目标", "校验格式并回填表单"],
};

export function AssignmentDesigner() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const referenceFileInputRef = useRef<HTMLInputElement | null>(null);

  const [tab, setTab] = useState<EditorTab>("editor");
  const [form, setForm] = useState<AssignmentDesignerForm>(() => buildDesignerInitialForm());
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [referenceDocId, setReferenceDocId] = useState<number | null>(null);
  const [editingAssignmentId, setEditingAssignmentId] = useState<number | null>(null);
  const [preview, setPreview] = useState<AssignmentDesignerPreviewState | null>(null);
  const [lessonPlanTouchedFields, setLessonPlanTouchedFields] = useState<AssignmentDesignerTouchedFields>({});

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [generatingFromLessonPlan, setGeneratingFromLessonPlan] = useState(false);
  const [uploadingReference, setUploadingReference] = useState(false);
  const [aiFeedbackFlow, setAiFeedbackFlow] = useState<AIFeedbackFlow | null>(null);
  const [aiFeedbackStep, setAiFeedbackStep] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [noticeTone, setNoticeTone] = useState<NoticeTone>("success");
  const [showAdvancedStepFields, setShowAdvancedStepFields] = useState(false);

  const showNotice = (message: string, tone: NoticeTone = "success") => {
    setNotice(message);
    setNoticeTone(tone);
  };

  const dismissNotice = () => {
    setNotice("");
    setNoticeTone("success");
  };

  const handleActionError = (err: unknown, fallback: string) => {
    const message = getApiErrorMessage(err, fallback);
    showNotice(message, "error");
  };

  const beginAIFeedback = (flow: AIFeedbackFlow) => {
    setAiFeedbackFlow(flow);
    setAiFeedbackStep(0);
  };

  const endAIFeedback = () => {
    setAiFeedbackFlow(null);
    setAiFeedbackStep(0);
  };

  const loadData = async () => {
    setError("");
    try {
      const [subjectResp, assignmentResp, documentResp] = await Promise.all([
        subjectsApi.list(),
        assignmentsApi.list(1, 100, false, true),
        documentsApi.list(),
      ]);
      setSubjects(subjectResp.subjects || []);
      setAssignments(assignmentResp.assignments || []);
      setDocuments(documentResp || []);
    } catch (err) {
      const message = getApiErrorMessage(err, "加载作业设计数据失败");
      setError(message);
      showNotice(message, "error");
    }
  };

  useEffect(() => {
    if (!aiFeedbackFlow) return;
    const steps = AI_FEEDBACK_STEPS[aiFeedbackFlow];
    const timer = window.setInterval(() => {
      setAiFeedbackStep((prev) => Math.min(prev + 1, steps.length - 1));
    }, 1300);
    return () => window.clearInterval(timer);
  }, [aiFeedbackFlow]);

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
      if (!user || user.role !== "teacher") {
        if (mounted) setLoading(false);
        return;
      }
      setLoading(true);
      await loadData();
      if (mounted) setLoading(false);
    }

    bootstrap();
    return () => {
      mounted = false;
    };
  }, [user]);

  const stageSubjects = useMemo(() => {
    return subjects.filter((subject) => {
      if (form.school_stage === "primary") return subject.primary_available;
      return subject.middle_available;
    });
  }, [subjects, form.school_stage]);

  useEffect(() => {
    if (form.main_subject_id && !stageSubjects.some((subject) => subject.id === form.main_subject_id)) {
      setForm((prev) => ({ ...prev, main_subject_id: 0 }));
    }
    setForm((prev) => ({
      ...prev,
      related_subject_ids: prev.related_subject_ids.filter((id) => stageSubjects.some((subject) => subject.id === id)),
    }));
  }, [stageSubjects, form.main_subject_id]);

  useEffect(() => {
    const editValue = new URLSearchParams(location.search).get("edit");
    if (!editValue) return;

    const assignmentId = Number(editValue);
    if (!Number.isFinite(assignmentId) || assignmentId <= 0) return;

    const target = assignments.find((assignment) => assignment.id === assignmentId);
    if (!target) return;

    setEditingAssignmentId(target.id);
    setReferenceDocId(target.document_id ?? null);
    setForm(buildDesignerFormFromAssignment(target));
    setLessonPlanTouchedFields({});
    setTab("editor");
    setPreview(null);
    showNotice(`已载入：${target.title}`);
  }, [location.search, assignments]);

  useEffect(() => {
    setForm((prev) => {
      if (prev.assignment_type === "practical" || prev.assignment_type === "project") {
        return prev;
      }
      return prev;
    });
  }, [form.assignment_type]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => {
      dismissNotice();
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const gradeOptions = useMemo(
    () => (form.school_stage === "primary" ? [1, 2, 3, 4, 5, 6] : [7, 8, 9]),
    [form.school_stage],
  );

  const sortedAssignments = useMemo(
    () => [...assignments].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)),
    [assignments],
  );

  const readyDocuments = useMemo(
    () => documents.filter((doc) => (doc.status || doc.parsing_status) === "ready"),
    [documents],
  );

  const customReadyDocuments = useMemo(
    () => readyDocuments.filter((doc) => doc.source !== "system"),
    [readyDocuments],
  );

  const selectedReferenceDocument = useMemo(
    () => readyDocuments.find((doc) => doc.id === referenceDocId) || null,
    [readyDocuments, referenceDocId],
  );

  const markLessonPlanFieldTouched = (field: AssignmentDesignerTouchedField) => {
    setLessonPlanTouchedFields((prev) => (prev[field] ? prev : { ...prev, [field]: true }));
  };

  const updateForm = <K extends keyof AssignmentDesignerForm>(
    key: K,
    value: AssignmentDesignerForm[K],
    options?: { markTouched?: boolean },
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (options?.markTouched !== false && isLessonPlanTouchedField(key)) {
      markLessonPlanFieldTouched(key);
    }
  };

  const addStep = () => {
    setForm((prev) => ({
      ...prev,
      steps: [
        ...prev.steps,
        {
          id: `step_${Date.now()}`,
          phaseName: "新增阶段",
          stepName: "新增步骤",
          description: "",
          evidence: "",
          evaluationPoints: "",
          lessonTimeSuggestion: "1课时",
        },
      ],
    }));
  };

  const removeStep = (stepId: string) => {
    setForm((prev) => {
      if (prev.steps.length <= 2) {
        showNotice("至少保留 2 个步骤", "warning");
        return prev;
      }
      return {
        ...prev,
        steps: prev.steps.filter((step) => step.id !== stepId),
      };
    });
  };

  const updateStep = (stepId: string, key: keyof LessonStepDraft, value: string) => {
    setForm((prev) => ({
      ...prev,
      steps: prev.steps.map((step) => (step.id === stepId ? { ...step, [key]: value } : step)),
    }));
  };

  const toggleRelatedSubject = (subjectId: number) => {
    setForm((prev) => ({
      ...prev,
      related_subject_ids: prev.related_subject_ids.includes(subjectId)
        ? prev.related_subject_ids.filter((id) => id !== subjectId)
        : [...prev.related_subject_ids, subjectId],
    }));
    markLessonPlanFieldTouched("related_subject_ids");
  };

  const triggerReferenceUpload = () => {
    referenceFileInputRef.current?.click();
  };

  const handleReferenceUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setUploadingReference(true);
    setError("");
    try {
      const uploaded = await documentsApi.upload(file);
      await loadData();
      if ((uploaded.status || uploaded.parsing_status) === "ready") {
        setReferenceDocId(uploaded.document_id);
        showNotice(`参考资料已导入并选中：${uploaded.filename}`);
      } else {
        showNotice(`已上传「${uploaded.filename}」，文档索引完成后可在下方列表选择`, "warning");
      }
    } catch (err) {
      handleActionError(err, "上传参考资料失败");
    } finally {
      setUploadingReference(false);
    }
  };

  const validateForm = (mode: "save" | "preview" | "publish"): string | null =>
    validateAssignmentDesignerForm(
      {
        title: form.title,
        topic: form.topic,
        school_stage: form.school_stage,
        grade: form.grade,
        main_subject_id: form.main_subject_id,
        related_subject_ids: form.related_subject_ids,
        rubric_dimensions: form.rubric_dimensions,
        steps: form.steps.map((step) => ({
          phaseName: step.phaseName,
          stepName: step.stepName,
          description: step.description,
          evidence: step.evidence,
        })),
      },
      mode,
    ) ?? (gradeOptions.includes(form.grade) ? null : "当前年级与学段不匹配");

  const handlePreview = async () => {
    const invalid = validateForm("preview");
    if (invalid) {
      showNotice(invalid, "warning");
      return;
    }

    setPreviewing(true);
    beginAIFeedback("preview");
    setError("");
    try {
      const payload = buildDesignerCreatePayload(form, referenceDocId);
      const result = await assignmentsApi.preview(payload, { forceGenerate: true });
      setPreview(buildDesignerPreviewState(result, form.assignment_type));
      if (result.meta?.source === "fallback") {
        const reason = result.meta.fallback_reason && result.meta.fallback_reason !== "none"
          ? `（原因：${result.meta.fallback_reason}）`
          : "";
        showNotice(`本次返回为兜底草稿，建议再次点击 AI 预览重试${reason}`, "warning");
      } else {
        showNotice("AI 预览已生成，可应用到当前设计");
      }
    } catch (err) {
      handleActionError(err, "AI 预览生成失败");
    } finally {
      setPreviewing(false);
      endAIFeedback();
    }
  };

  const handleGenerateFromLessonPlan = async () => {
    if (!referenceDocId) {
      showNotice("请先选择一份已入库完成的教案资料", "warning");
      return;
    }

    setGeneratingFromLessonPlan(true);
    beginAIFeedback("lessonPlan");
    setError("");
    try {
      const generated = await assignmentsApi.fromLessonPlan(
        buildLessonPlanDraftRequest(form, referenceDocId, lessonPlanTouchedFields),
      );
      const applied = applyLessonPlanDraft(form, generated, lessonPlanTouchedFields);

      setForm(applied.form);
      setReferenceDocId(generated.document_id);
      setPreview(null);
      const summaryText = formatLessonPlanApplySummary(applied.summary);
      if (generated.meta?.source === "fallback") {
        const reason = generated.meta.fallback_reason && generated.meta.fallback_reason !== "none"
          ? `（原因：${generated.meta.fallback_reason}）`
          : "";
        showNotice(`${summaryText}；当前为兜底结果，建议重试以获取 AI 版本${reason}`, "warning");
      } else {
        showNotice(summaryText);
      }
    } catch (err) {
      const raw = getApiErrorMessage(err, "教案生成草稿失败");
      const message = raw.includes("超时")
        ? "教案生成超时，请重试；如文档较长，建议先精简后再导入。"
        : raw;
      showNotice(message, "error");
    } finally {
      setGeneratingFromLessonPlan(false);
      endAIFeedback();
    }
  };

  const applyPreview = () => {
    if (!preview) return;
    setForm((prev) => mergeDesignerFormWithPreview(prev, preview));
    showNotice("已应用 AI 预览结果");
    setPreview(null);
  };

  const saveDraft = async () => {
    const invalid = validateForm("save");
    if (invalid) {
      showNotice(invalid, "warning");
      return;
    }

    setSaving(true);
    setError("");
    try {
      if (editingAssignmentId) {
        await assignmentsApi.update(editingAssignmentId, buildDesignerUpdatePayload(form, referenceDocId));
        showNotice("作业已更新");
      } else {
        const created = await assignmentsApi.create(buildDesignerCreatePayload(form, referenceDocId));
        setEditingAssignmentId(created.id);
        showNotice("草稿创建成功");
      }

      await loadData();
    } catch (err) {
      handleActionError(err, "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const publishCurrent = async () => {
    setPublishing(true);
    setError("");
    try {
      let targetId = editingAssignmentId;
      if (!targetId) {
        const invalid = validateForm("publish");
        if (invalid) {
          showNotice(invalid, "warning");
          return;
        }
        const created = await assignmentsApi.create(buildDesignerCreatePayload(form, referenceDocId));
        targetId = created.id;
        setEditingAssignmentId(created.id);
      } else {
        await assignmentsApi.update(targetId, buildDesignerUpdatePayload(form, referenceDocId));
      }

      await assignmentsApi.publish(targetId);
      await loadData();
      showNotice("作业已发布");
    } catch (err) {
      handleActionError(err, "发布失败");
    } finally {
      setPublishing(false);
    }
  };

  const loadForEdit = (assignment: Assignment) => {
    navigate(`/create?edit=${assignment.id}`, { replace: false });
  };

  const resetEditor = () => {
    setEditingAssignmentId(null);
    setReferenceDocId(null);
    setPreview(null);
    setForm(buildDesignerInitialForm());
    setLessonPlanTouchedFields({});
    showNotice("已新建空白设计");
    navigate("/create", { replace: true });
  };

  const deleteAssignment = async (assignment: Assignment) => {
    const confirmed = window.confirm(`确认删除「${assignment.title}」吗？该操作不可撤销。`);
    if (!confirmed) return;

    try {
      await assignmentsApi.delete(assignment.id);
      if (editingAssignmentId === assignment.id) {
        resetEditor();
      }
      await loadData();
      showNotice("作业已删除");
    } catch (err) {
      handleActionError(err, "删除失败");
    }
  };

  const publishFromHistory = async (assignmentId: number) => {
    try {
      await assignmentsApi.publish(assignmentId);
      await loadData();
      showNotice("作业已发布");
    } catch (err) {
      handleActionError(err, "发布失败");
    }
  };

  const archiveFromHistory = async (assignmentId: number) => {
    try {
      await assignmentsApi.archive(assignmentId);
      await loadData();
      showNotice("作业已归档");
    } catch (err) {
      handleActionError(err, "归档失败");
    }
  };

  const unarchiveFromHistory = async (assignmentId: number) => {
    try {
      await assignmentsApi.unarchive(assignmentId);
      await loadData();
      showNotice("作业已取消归档");
    } catch (err) {
      handleActionError(err, "取消归档失败");
    }
  };

  if (!user || user.role !== "teacher") {
    return <PageState variant="warning" title="访问受限" description="仅教师可访问作业设计器。" actionLabel="返回学生首页" actionTo="/student" />;
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <section className="bg-surface rounded-2xl border border-border p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">跨学科作业设计工坊</h1>
            <p className="text-sm text-text-secondary mt-1">已接入真实后端，支持 AI 预览、保存、发布与历史管理。</p>
          </div>
          <div className="flex items-center gap-2 bg-secondary p-1 rounded-xl">
            <button
              onClick={() => setTab("editor")}
              className={`px-4 py-2 rounded-lg text-sm font-semibold ${
                tab === "editor" ? "bg-surface text-primary" : "text-text-secondary"
              }`}
            >
              设计编辑
            </button>
            <button
              onClick={() => setTab("history")}
              className={`px-4 py-2 rounded-lg text-sm font-semibold ${
                tab === "history" ? "bg-surface text-primary" : "text-text-secondary"
              }`}
            >
              历史记录
            </button>
          </div>
        </div>
        {error && <StatusBanner tone="error" message={error} className="mt-2" />}
      </section>

      {loading ? (
        <PageState variant="loading" title="正在加载作业设计数据" description="正在同步学科与历史作业，请稍候。" />
      ) : tab === "history" ? (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">历史作业</h2>
            <button
              onClick={resetEditor}
              className="px-4 py-2 bg-primary hover:bg-primary-hover active:bg-primary-active text-white rounded-xl text-sm font-bold"
            >
              新建设计
            </button>
          </div>

          {sortedAssignments.length === 0 && (
            <div className="bg-surface rounded-2xl border border-border p-8 text-text-secondary">暂无历史作业。</div>
          )}

          {sortedAssignments.map((assignment) => (
            <article key={assignment.id} className="bg-surface rounded-2xl border border-border p-6">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-bold text-lg">{assignment.title}</h3>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        assignment.is_archived
                          ? "bg-secondary text-text"
                          : assignment.is_published
                          ? "bg-success-soft text-success"
                          : "bg-warning-soft text-warning"
                      }`}
                    >
                      {assignmentStatusLabel(assignment)}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary">
                    {scoreStageLabel(assignment.school_stage)} · {gradeLabelByStage(assignment.school_stage, assignment.grade)} · 主题：{assignment.topic}
                  </p>
                  <p className="text-xs text-text-muted mt-1">创建时间：{assignment.created_at.slice(0, 19).replace("T", " ")}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => loadForEdit(assignment)}
                    className="px-3 py-2 rounded-lg border border-border-strong text-sm font-semibold hover:bg-surface-muted"
                  >
                    编辑
                  </button>
                  {!assignment.is_published && !assignment.is_archived && (
                    <button
                      onClick={() => publishFromHistory(assignment.id)}
                      className="px-3 py-2 rounded-lg border border-success/25 text-success text-sm font-semibold hover:bg-success-soft"
                    >
                      发布
                    </button>
                  )}
                  {!assignment.is_archived ? (
                    <button
                      onClick={() => archiveFromHistory(assignment.id)}
                      className="px-3 py-2 rounded-lg border border-border-strong text-text text-sm font-semibold hover:bg-surface-muted"
                    >
                      归档
                    </button>
                  ) : (
                    <button
                      onClick={() => unarchiveFromHistory(assignment.id)}
                      className="px-3 py-2 rounded-lg border border-secondary text-primary text-sm font-semibold hover:bg-secondary"
                    >
                      取消归档
                    </button>
                  )}
                  <button
                    onClick={() => deleteAssignment(assignment)}
                    className="px-3 py-2 rounded-lg border border-danger/25 text-danger text-sm font-semibold hover:bg-danger-soft"
                  >
                    删除
                  </button>
                  <Link
                    to={`/assignment/${assignment.id}`}
                    className="px-3 py-2 rounded-lg border border-border-strong text-sm font-semibold hover:bg-surface-muted"
                  >
                    查看详情
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section className="space-y-6">
          <div className="bg-surface rounded-2xl border border-border p-6 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold">基本信息</h2>
              <button
                onClick={resetEditor}
                className="px-3 py-2 rounded-lg border border-border-strong text-sm font-semibold hover:bg-surface-muted"
              >
                清空重置
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-semibold text-text">作业标题 *</label>
                <input
                  value={form.title}
                  onChange={(e) => updateForm("title", e.target.value)}
                  placeholder="例如：家乡水质探究"
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                />
              </div>
              <div>
                <label className="text-sm font-semibold text-text">探究主题 *</label>
                <input
                  value={form.topic}
                  onChange={(e) => updateForm("topic", e.target.value)}
                  placeholder="例如：生态与可持续发展"
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                />
              </div>
            </div>

            <div>
              <label className="text-sm font-semibold text-text">任务描述</label>
              <textarea
                value={form.description}
                onChange={(e) => updateForm("description", e.target.value)}
                rows={3}
                placeholder="描述任务背景、目标与预期产出"
                className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong resize-none"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="text-sm font-semibold text-text">学段</label>
                <select
                  value={form.school_stage}
                  onChange={(e) => updateForm("school_stage", e.target.value as AssignmentDesignerForm["school_stage"])}
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                >
                  <option value="primary">小学</option>
                  <option value="middle">初中</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-semibold text-text">年级</label>
                <select
                  value={form.grade}
                  onChange={(e) => updateForm("grade", Number(e.target.value))}
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                >
                  {gradeOptions.map((grade) => (
                    <option key={grade} value={grade}>
                      {grade} 年级
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-semibold text-text">周期（周）</label>
                <input
                  type="number"
                  min={1}
                  max={16}
                  value={form.duration_weeks}
                  onChange={(e) => updateForm("duration_weeks", Number(e.target.value) || 1)}
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                />
              </div>
              <div>
                <label className="text-sm font-semibold text-text">截止日期</label>
                <input
                  type="date"
                  value={form.deadline}
                  onChange={(e) => updateForm("deadline", e.target.value)}
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                />
              </div>
            </div>
          </div>

          <div className="bg-surface rounded-2xl border border-border p-6 space-y-6">
            <h2 className="text-lg font-bold">学科与作业配置</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-semibold text-text">主学科 *</label>
                <select
                  value={form.main_subject_id}
                  onChange={(e) => updateForm("main_subject_id", Number(e.target.value))}
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                >
                  <option value={0}>请选择主学科</option>
                  {stageSubjects.map((subject) => (
                    <option key={subject.id} value={subject.id}>
                      {subject.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-semibold text-text">融合学科（多选）</label>
                <div className="mt-2 grid grid-cols-2 gap-2 max-h-48 overflow-auto rounded-xl border border-border-strong p-3">
                  {stageSubjects
                    .filter((subject) => subject.id !== form.main_subject_id)
                    .map((subject) => (
                      <label key={subject.id} className="flex items-center gap-2 text-sm text-text">
                        <input
                          type="checkbox"
                          checked={form.related_subject_ids.includes(subject.id)}
                          onChange={() => toggleRelatedSubject(subject.id)}
                        />
                        {subject.name}
                      </label>
                    ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="text-sm font-semibold text-text">作业类型</label>
                <select
                  value={form.assignment_type}
                  onChange={(e) => {
                    const value = e.target.value as AssignmentDesignerForm["assignment_type"];
                    updateForm("assignment_type", value);
                    updateForm("rubric_dimensions", defaultRubricNames(value));
                  }}
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                >
                  <option value="practical">实践性作业</option>
                  <option value="inquiry">探究性作业</option>
                  <option value="project">项目式作业</option>
                </select>
              </div>
              {form.assignment_type === "practical" && (
                <div>
                  <label className="text-sm font-semibold text-text">实践子类型</label>
                  <select
                    value={form.practical_subtype}
                    onChange={(e) =>
                      updateForm("practical_subtype", e.target.value as AssignmentDesignerForm["practical_subtype"])
                    }
                    className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                  >
                    <option value="visit">参观考察</option>
                    <option value="simulation">模拟表演</option>
                    <option value="observation">观察体验</option>
                  </select>
                </div>
              )}
              {form.assignment_type === "inquiry" && (
                <div>
                  <label className="text-sm font-semibold text-text">探究子类型</label>
                  <select
                    value={form.inquiry_subtype}
                    onChange={(e) =>
                      updateForm("inquiry_subtype", e.target.value as AssignmentDesignerForm["inquiry_subtype"])
                    }
                    className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                  >
                    <option value="literature">文献探究</option>
                    <option value="survey">调查探究</option>
                    <option value="experiment">实验探究</option>
                  </select>
                </div>
              )}
              <div>
                <label className="text-sm font-semibold text-text">探究深度</label>
                <select
                  value={form.inquiry_depth}
                  onChange={(e) =>
                    updateForm("inquiry_depth", e.target.value as AssignmentDesignerForm["inquiry_depth"])
                  }
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                >
                  <option value="basic">基础探究</option>
                  <option value="intermediate">中等探究</option>
                  <option value="deep">深度探究</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-semibold text-text">提交模式</label>
                <select
                  value={form.submission_mode}
                  onChange={(e) =>
                    updateForm("submission_mode", e.target.value as AssignmentDesignerForm["submission_mode"])
                  }
                  className="mt-2 w-full px-4 py-3 rounded-xl border border-border-strong"
                >
                  <option value="phased">过程性提交</option>
                  <option value="once">一次性提交</option>
                  <option value="mixed">混合提交</option>
                </select>
              </div>
            </div>
          </div>

          <div className="bg-surface rounded-2xl border border-border p-6 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold">参考资料导入与选择（可选）</h2>
                <p className="text-xs text-text-secondary mt-1">可上传教学资料并作为 AI 生成任务引导的优先参考源。</p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  ref={referenceFileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  className="hidden"
                  onChange={handleReferenceUpload}
                />
                <button
                  onClick={triggerReferenceUpload}
                  disabled={uploadingReference}
                  className="px-3 py-2 rounded-lg border border-border-strong text-sm font-semibold hover:bg-surface-muted disabled:opacity-60 flex items-center gap-1"
                >
                  {uploadingReference ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />} 上传参考资料
                </button>
                <Link
                  to="/knowledge"
                  className="px-3 py-2 rounded-lg border border-border-strong text-sm font-semibold hover:bg-surface-muted"
                >
                  前往知识库
                </Link>
                <button
                  onClick={handleGenerateFromLessonPlan}
                  disabled={generatingFromLessonPlan || !referenceDocId}
                  className="px-3 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-hover active:bg-primary-active disabled:opacity-60 flex items-center gap-1"
                  title={referenceDocId ? "基于当前已选教案生成作业草稿" : "请先选择一份教案资料"}
                >
                  {generatingFromLessonPlan ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <WandSparkles className="w-4 h-4" />} 从教案一键生成
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <button
                onClick={() => setReferenceDocId(null)}
                className={`text-left rounded-xl border p-3 transition-colors ${
                  referenceDocId === null
                    ? "border-secondary bg-secondary"
                    : "border-border-strong bg-surface hover:bg-surface-muted"
                }`}
              >
                <p className="text-sm font-semibold text-text">仅使用系统知识库（默认）</p>
                <p className="text-xs text-text-secondary mt-1">将按学科匹配系统内置课标 chunks 生成任务引导。</p>
              </button>

              {customReadyDocuments.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => setReferenceDocId(doc.id)}
                  className={`text-left rounded-xl border p-3 transition-colors ${
                    referenceDocId === doc.id
                      ? "border-secondary bg-secondary"
                      : "border-border-strong bg-surface hover:bg-surface-muted"
                  }`}
                >
                  <p className="text-sm font-semibold text-text truncate">{doc.filename}</p>
                  <p className="text-xs text-text-secondary mt-1">导入时间：{new Date(doc.upload_date).toLocaleDateString()}</p>
                </button>
              ))}
            </div>

            {customReadyDocuments.length === 0 && (
              <p className="text-xs text-text-secondary">当前暂无可选的自定义资料。你可以先上传文档，再进行 AI 预览。</p>
            )}

            {referenceDocId !== null && !selectedReferenceDocument && (
              <StatusBanner tone="warning" message="当前选择的参考资料不可用，请重新选择或切换为系统知识库。" />
            )}

            {selectedReferenceDocument && (
              <div className="text-xs text-primary bg-secondary border border-secondary rounded-xl px-3 py-2">
                当前参考资料：{selectedReferenceDocument.filename}
              </div>
            )}
          </div>

          <div className="bg-surface rounded-2xl border border-border p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold">学习目标与任务步骤</h2>
                <p className="text-xs text-text-secondary mt-1">默认只保留三个核心字段：任务动作、学习支架、提交证据。</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowAdvancedStepFields((prev) => !prev)}
                  className="px-3 py-2 rounded-lg border border-border-strong text-sm font-semibold hover:bg-surface-muted flex items-center gap-1"
                >
                  {showAdvancedStepFields ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  {showAdvancedStepFields ? "收起高级字段" : "展开高级字段"}
                </button>
                <button
                  onClick={addStep}
                  className="px-3 py-2 rounded-lg border border-border-strong text-sm font-semibold hover:bg-surface-muted flex items-center gap-1"
                >
                  <Plus className="w-4 h-4" /> 添加步骤
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="md:col-span-3 rounded-2xl border border-secondary bg-secondary p-4">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <p className="text-sm font-semibold text-primary">背景设定（单独展示给学生）</p>
                  <span className="text-[11px] text-primary">建议 80-180 字，贴近学段语感</span>
                </div>
                <textarea
                  value={form.background_setting}
                  onChange={(e) => updateForm("background_setting", e.target.value)}
                  rows={4}
                  placeholder="例如：背景设定：你们是校园生态小队，本周要为学校食堂与教学楼之间的垃圾分类盲区设计一套可执行改进方案。"
                  className="w-full px-4 py-3 rounded-xl border border-secondary bg-surface resize-none"
                />
              </div>
              <textarea
                value={form.objectives_json.knowledge}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    objectives_json: { ...prev.objectives_json, knowledge: e.target.value },
                  }))
                }
                rows={3}
                placeholder="知识与技能目标"
                className="px-4 py-3 rounded-xl border border-border-strong resize-none"
              />
              <textarea
                value={form.objectives_json.process}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    objectives_json: { ...prev.objectives_json, process: e.target.value },
                  }))
                }
                rows={3}
                placeholder="过程与方法目标（不含背景设定）"
                className="px-4 py-3 rounded-xl border border-border-strong resize-none"
              />
              <textarea
                value={form.objectives_json.emotion}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    objectives_json: { ...prev.objectives_json, emotion: e.target.value },
                  }))
                }
                rows={3}
                placeholder="情感态度目标"
                className="px-4 py-3 rounded-xl border border-border-strong resize-none"
              />
            </div>

            <div className="space-y-4">
              {form.steps.map((step, index) => (
                <div key={step.id} className="rounded-2xl border border-border-strong bg-surface-muted p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold">步骤 {index + 1}</h3>
                    <button
                      onClick={() => removeStep(step.id)}
                      className="px-2 py-1 text-xs rounded-md border border-danger/25 text-danger hover:bg-danger-soft"
                    >
                      删除
                    </button>
                  </div>
                  <div className="space-y-3">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div>
                        <p className="text-[11px] text-text-secondary mb-1">任务动作</p>
                        <input
                          value={step.stepName}
                          onChange={(e) => updateStep(step.id, "stepName", e.target.value)}
                          placeholder="例如：采集校园垃圾分类误投数据"
                          className="w-full px-3 py-2 rounded-lg border border-border-strong"
                        />
                      </div>
                      <div>
                        <p className="text-[11px] text-text-secondary mb-1">学习支架</p>
                        <textarea
                          value={step.description}
                          onChange={(e) => updateStep(step.id, "description", e.target.value)}
                          rows={3}
                          placeholder="例如：先明确记录口径，再按时间和点位对比数据差异。"
                          className="w-full px-3 py-2 rounded-lg border border-border-strong resize-none"
                        />
                      </div>
                      <div>
                        <p className="text-[11px] text-text-secondary mb-1">提交证据</p>
                        <textarea
                          value={step.evidence}
                          onChange={(e) => updateStep(step.id, "evidence", e.target.value)}
                          rows={3}
                          placeholder="例如：观察记录表（document）+ 现场照片（image）"
                          className="w-full px-3 py-2 rounded-lg border border-border-strong resize-none"
                        />
                      </div>
                    </div>

                    {showAdvancedStepFields && (
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div>
                          <p className="text-[11px] text-text-secondary mb-1">阶段名称（高级）</p>
                          <input
                            value={step.phaseName}
                            onChange={(e) => updateStep(step.id, "phaseName", e.target.value)}
                            placeholder="例如：证据采集与整理"
                            className="w-full px-3 py-2 rounded-lg border border-border-strong"
                          />
                        </div>
                        <div>
                          <p className="text-[11px] text-text-secondary mb-1">课时建议（高级）</p>
                          <input
                            value={step.lessonTimeSuggestion}
                            onChange={(e) => updateStep(step.id, "lessonTimeSuggestion", e.target.value)}
                            placeholder="例如：1课时"
                            className="w-full px-3 py-2 rounded-lg border border-border-strong"
                          />
                        </div>
                        <div>
                          <p className="text-[11px] text-text-secondary mb-1">评价要点（高级）</p>
                          <textarea
                            value={step.evaluationPoints}
                            onChange={(e) => updateStep(step.id, "evaluationPoints", e.target.value)}
                            rows={3}
                            placeholder="例如：证据完整性、数据准确性、结论可解释性"
                            className="w-full px-3 py-2 rounded-lg border border-border-strong resize-none"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div>
              <div className="flex items-center justify-between gap-3">
                <label className="text-sm font-semibold text-text">评价维度（随作业类型自动生成）</label>
                <button
                  onClick={() => updateForm("rubric_dimensions", defaultRubricNames(form.assignment_type))}
                  className="px-3 py-1.5 text-xs rounded-lg border border-border-strong text-text-secondary hover:bg-surface-muted"
                >
                  恢复默认维度
                </button>
              </div>
              <div className="mt-2 p-4 rounded-xl border border-border-strong bg-surface-muted">
                <div className="flex flex-wrap gap-2">
                  {(form.rubric_dimensions.length ? form.rubric_dimensions : defaultRubricNames(form.assignment_type)).map((name) => (
                    <span
                      key={name}
                      className="px-2.5 py-1 rounded-full text-xs font-semibold bg-surface border border-border-strong text-text"
                    >
                      {name}
                    </span>
                  ))}
                </div>
                <p className="mt-3 text-[11px] text-text-secondary">
                  维度会根据作业类型自动切换，也可通过 AI 预览结果覆盖更新。
                </p>
              </div>
            </div>
          </div>

          <div className="bg-surface rounded-2xl border border-border p-6">
            <div className="flex flex-wrap gap-3">
              <button
                onClick={handlePreview}
                disabled={previewing}
                className="px-5 py-3 bg-primary hover:bg-primary-hover active:bg-primary-active text-white rounded-xl font-semibold flex items-center gap-2 disabled:opacity-60"
              >
                {previewing ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <WandSparkles className="w-4 h-4" />} AI 预览
              </button>
              <button
                onClick={saveDraft}
                disabled={saving}
                className="px-5 py-3 border border-border-strong rounded-xl font-semibold hover:bg-surface-muted disabled:opacity-60 flex items-center gap-2"
              >
                {saving ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />} 保存草稿
              </button>
              <button
                onClick={publishCurrent}
                disabled={publishing}
                className="px-5 py-3 bg-success hover:bg-success/90 text-white rounded-xl font-semibold disabled:opacity-60 flex items-center gap-2"
              >
                {publishing ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />} 发布作业
              </button>
            </div>
            {editingAssignmentId && (
              <p className="mt-3 text-xs text-text-secondary">
                当前编辑作业 ID：{editingAssignmentId}。后端更新接口暂不支持结构化字段全量更新，系统将优先保存目标、流程与量表内容。
              </p>
            )}
          </div>

          {preview && (
            <div className="bg-secondary border border-secondary rounded-2xl p-6 space-y-4">
              <h3 className="font-bold text-primary flex items-center gap-2">
                <Sparkles className="w-4 h-4" /> AI 预览结果
              </h3>
              {preview.meta && (
                <p className="text-xs text-primary">
                  {formatAIGenerationMeta(preview.meta)}
                </p>
              )}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                {preview.background_setting && (
                  <div className="md:col-span-3 bg-surface rounded-xl border border-secondary p-3">
                    <p className="text-xs text-primary mb-1">背景设定</p>
                    <p>{preview.background_setting}</p>
                  </div>
                )}
                <div className="bg-surface rounded-xl border border-secondary p-3">
                  <p className="text-xs text-text-secondary mb-1">知识与技能</p>
                  <p>{preview.objectives_json.knowledge || "-"}</p>
                </div>
                <div className="bg-surface rounded-xl border border-secondary p-3">
                  <p className="text-xs text-text-secondary mb-1">过程与方法</p>
                  <p>{preview.objectives_json.process || "-"}</p>
                </div>
                <div className="bg-surface rounded-xl border border-secondary p-3">
                  <p className="text-xs text-text-secondary mb-1">情感态度</p>
                  <p>{preview.objectives_json.emotion || "-"}</p>
                </div>
              </div>
              <div className="text-sm text-primary">生成步骤：{preview.steps.length} 个，评价维度：{preview.rubric_dimensions.length} 项</div>
              <button
                onClick={applyPreview}
                className="px-4 py-2 rounded-xl bg-primary text-white font-semibold hover:bg-primary-hover active:bg-primary-active"
              >
                应用到当前设计
              </button>
            </div>
          )}
        </section>
      )}

      {aiFeedbackFlow && (
        <div className="fixed bottom-28 right-6 z-40 w-[28rem] max-w-[calc(100vw-2rem)] rounded-2xl border border-secondary bg-surface shadow-floating p-5">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 w-8 h-8 rounded-xl bg-secondary text-primary flex items-center justify-center">
              <LoaderCircle className="w-5 h-5 animate-spin" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-text">AI 正在生成，请稍候</p>
              <p className="text-sm text-text-secondary mt-1">
                当前阶段：{AI_FEEDBACK_STEPS[aiFeedbackFlow][aiFeedbackStep]}
              </p>
              <div className="mt-3 space-y-1.5">
                {AI_FEEDBACK_STEPS[aiFeedbackFlow].map((step, index) => (
                  <p key={step} className={`text-xs ${index <= aiFeedbackStep ? "text-primary" : "text-text-muted"}`}>
                    {index <= aiFeedbackStep ? "●" : "○"} {step}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {notice && (
        <div
          className={`fixed bottom-6 right-6 z-40 w-[26rem] max-w-[calc(100vw-2rem)] rounded-2xl border bg-surface shadow-floating p-5 ${
            noticeTone === "error"
              ? "border-danger/20"
              : noticeTone === "warning"
                ? "border-warning/20"
                : "border-secondary"
          }`}
        >
          <div className="flex items-start gap-3">
            <div
              className={`mt-0.5 w-6 h-6 rounded-lg flex items-center justify-center ${
                noticeTone === "error"
                  ? "bg-danger-soft text-danger"
                  : noticeTone === "warning"
                    ? "bg-warning-soft text-warning"
                    : "bg-secondary text-primary"
              }`}
            >
              {noticeTone === "success" ? <CheckCircle2 className="w-4 h-4" /> : <CircleAlert className="w-4 h-4" />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-text">
                {noticeTone === "error" ? "操作失败" : noticeTone === "warning" ? "请注意" : "操作反馈"}
              </p>
              <p className="text-sm text-text-secondary mt-1 leading-relaxed">{notice}</p>
            </div>
            <button
              onClick={dismissNotice}
              className="text-text-muted hover:text-text-secondary"
              aria-label="关闭提示"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
