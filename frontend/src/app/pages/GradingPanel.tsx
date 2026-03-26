import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import {
  CheckCircle2,
  LoaderCircle,
  Sparkles,
  Star,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import {
  assignmentsApi,
  evaluationsApi,
  getApiErrorMessage,
  submissionsApi,
  type Assignment,
  type AssignmentGroup,
  type Submission,
  type TeacherEvaluationPayload,
} from "../lib/api";
import { PageState } from "../components/PageState";
import { StatusBanner } from "../components/StatusBanner";
import { validateTeacherEvaluation } from "../validation/evaluation";

const SCORE_LABELS: Record<number, string> = {
  1: "需改进",
  2: "合格",
  3: "良好",
  4: "优秀",
};

function clampScore(value: number): number {
  if (!Number.isFinite(value)) return 3;
  return Math.max(1, Math.min(4, Math.round(value)));
}

function submissionStatusLabel(status: string): string {
  if (status === "draft") return "草稿";
  if (status === "submitted") return "已提交";
  if (status === "graded") return "已评分";
  return status;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "暂无";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "暂无";
  return date.toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function GradingPanel() {
  const { user } = useAuth();
  const { id } = useParams();
  const submissionId = Number(id || 0);

  const [submission, setSubmission] = useState<Submission | null>(null);
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [assignmentGroups, setAssignmentGroups] = useState<AssignmentGroup[]>([]);
  const [assignmentSubmissions, setAssignmentSubmissions] = useState<Submission[]>([]);
  const [groupViewFilter, setGroupViewFilter] = useState<string>("all");
  const [dimensionScores, setDimensionScores] = useState<Record<string, number>>({});
  const [scoreNumeric, setScoreNumeric] = useState<number>(3);
  const [feedback, setFeedback] = useState("");

  const [loading, setLoading] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const rubricDimensions = useMemo(
    () => assignment?.rubric_json?.dimensions?.map((item) => item.name).filter(Boolean) || [],
    [assignment],
  );

  const groupAggregateRows = useMemo(() => {
    const totalPhases = assignment?.phases_json?.length || 0;

    const toMs = (value: string | null | undefined): number => {
      if (!value) return -1;
      const ms = Date.parse(value);
      return Number.isFinite(ms) ? ms : -1;
    };

    const deadlineMs = assignment?.deadline ? toMs(assignment.deadline) : -1;
    const nowMs = Date.now();

    const groupNameById = new Map<number, string>();
    assignmentGroups.forEach((group) => {
      groupNameById.set(group.id, group.name);
    });

    const buckets = new Map<string, { key: string; label: string; groupId: number | null; submissions: Submission[] }>();

    assignmentSubmissions.forEach((item) => {
      const isGrouped = !!item.group_id;
      const key = isGrouped ? `group:${item.group_id}` : "ungrouped";
      if (!buckets.has(key)) {
        const groupId = isGrouped ? Number(item.group_id) : null;
        const fallbackName = isGrouped ? `小组#${item.group_id}` : "个人提交";
        const label = isGrouped
          ? groupNameById.get(groupId || 0) || item.group_name || fallbackName
          : "个人提交";
        buckets.set(key, {
          key,
          label,
          groupId,
          submissions: [],
        });
      }
      buckets.get(key)?.submissions.push(item);
    });

    return Array.from(buckets.values())
      .map((bucket) => {
        const sorted = [...bucket.submissions].sort((a, b) => {
          const aTime = toMs(a.submitted_at || a.created_at);
          const bTime = toMs(b.submitted_at || b.created_at);
          return bTime - aTime;
        });

        const latest = sorted[0] || null;
        const maxPhase = bucket.submissions.reduce((max, item) => Math.max(max, item.phase_index), -1);
        const submittedCount = bucket.submissions.filter((item) => item.status === "submitted").length;
        const gradedCount = bucket.submissions.filter((item) => item.status === "graded").length;

        const lastSubmittedAt = bucket.submissions.reduce<string | null>((latestValue, item) => {
          const candidate = item.submitted_at || item.created_at;
          if (!latestValue) return candidate;
          return toMs(candidate) > toMs(latestValue) ? candidate : latestValue;
        }, null);

        const lastEvaluatedAt = bucket.submissions.reduce<string | null>((latestValue, item) => {
          const candidate = item.teacher_evaluated_at || null;
          if (!candidate) return latestValue;
          if (!latestValue) return candidate;
          return toMs(candidate) > toMs(latestValue) ? candidate : latestValue;
        }, null);

        let riskScore = 0;
        let riskText = "正常";
        const hasSubmission = bucket.submissions.length > 0;

        if (deadlineMs > 0) {
          const msToDeadline = deadlineMs - nowMs;
          if (!hasSubmission && msToDeadline < 0) {
            riskScore = 3;
            riskText = "已逾期未提交";
          } else if (!hasSubmission && msToDeadline <= 48 * 60 * 60 * 1000) {
            riskScore = 2;
            riskText = "临近截止未提交";
          } else if (msToDeadline < 0 && submittedCount > 0) {
            riskScore = 2;
            riskText = "已截止待评分";
          }
        }

        if (riskScore < 1 && submittedCount > 0) {
          riskScore = 1;
          riskText = "有待评分提交";
        }

        return {
          ...bucket,
          latestSubmission: latest,
          submittedCount,
          gradedCount,
          totalSubmissions: bucket.submissions.length,
          lastSubmittedAt,
          lastEvaluatedAt,
          riskScore,
          riskText,
          phaseProgress:
            totalPhases > 0 && maxPhase >= 0
              ? `${Math.min(maxPhase + 1, totalPhases)}/${totalPhases}`
              : `0/${totalPhases || 0}`,
        };
      })
      .sort((a, b) => {
        if (a.riskScore !== b.riskScore) return b.riskScore - a.riskScore;
        return toMs(a.lastSubmittedAt) - toMs(b.lastSubmittedAt);
      });
  }, [assignmentSubmissions, assignmentGroups, assignment?.phases_json, assignment?.deadline]);

  const filteredGroupAggregateRows = useMemo(() => {
    if (groupViewFilter === "all") return groupAggregateRows;
    if (groupViewFilter === "ungrouped") return groupAggregateRows.filter((item) => item.groupId === null);

    const groupId = Number(groupViewFilter);
    if (!Number.isFinite(groupId) || groupId <= 0) return groupAggregateRows;
    return groupAggregateRows.filter((item) => item.groupId === groupId);
  }, [groupAggregateRows, groupViewFilter]);

  const groupScoreSummary = useMemo(() => {
    const totals = filteredGroupAggregateRows.reduce(
      (acc, row) => {
        acc.totalBuckets += 1;
        acc.totalSubmissions += row.totalSubmissions;
        acc.submitted += row.submittedCount;
        acc.graded += row.gradedCount;
        acc.highRiskBuckets += row.riskScore >= 2 ? 1 : 0;
        return acc;
      },
      {
        totalBuckets: 0,
        totalSubmissions: 0,
        submitted: 0,
        graded: 0,
        highRiskBuckets: 0,
      },
    );

    const draft = Math.max(0, totals.totalSubmissions - totals.submitted - totals.graded);
    const gradedRate = totals.totalSubmissions > 0 ? Math.round((totals.graded / totals.totalSubmissions) * 100) : 0;
    const pendingRate = totals.totalSubmissions > 0 ? Math.round((totals.submitted / totals.totalSubmissions) * 100) : 0;

    return {
      ...totals,
      draft,
      gradedRate,
      pendingRate,
    };
  }, [filteredGroupAggregateRows]);

  const loadData = async () => {
    if (!submissionId) return;
    setLoading(true);
    setError("");

    try {
      const submissionData = await submissionsApi.getById(submissionId);
      const assignmentData = await assignmentsApi.getById(submissionData.assignment_id);

      const [evaluationData, assignmentSubmissionData, groupData] = await Promise.all([
        evaluationsApi.listBySubmission(submissionId),
        submissionsApi.listByAssignment(submissionData.assignment_id).catch(() => ({ submissions: [], total: 0 })),
        assignmentsApi.listGroups(submissionData.assignment_id).catch(() => [] as AssignmentGroup[]),
      ]);

      setSubmission(submissionData);
      setAssignment(assignmentData);
      setAssignmentSubmissions(assignmentSubmissionData.submissions || []);
      setAssignmentGroups(groupData || []);
      const teacherEval = (evaluationData.evaluations || []).find((item) => item.evaluation_type === "teacher");
      if (teacherEval) {
        setDimensionScores(teacherEval.dimension_scores_json || {});
        setScoreNumeric(clampScore(teacherEval.score_numeric || 3));
        setFeedback(teacherEval.feedback || "");
      } else {
        const defaultScores: Record<string, number> = {};
        (assignmentData.rubric_json?.dimensions || []).forEach((dimension) => {
          defaultScores[dimension.name] = 3;
        });
        setDimensionScores(defaultScores);
        setScoreNumeric(3);
        setFeedback("");
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "加载评分数据失败"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [submissionId]);

  useEffect(() => {
    if (!submission) return;
    setGroupViewFilter(submission.group_id ? String(submission.group_id) : "ungrouped");
  }, [submission?.id]);

  useEffect(() => {
    if (groupViewFilter === "all" || groupViewFilter === "ungrouped") return;
    const groupId = Number(groupViewFilter);
    if (!Number.isFinite(groupId) || groupId <= 0) {
      setGroupViewFilter("all");
      return;
    }
    const exists = assignmentGroups.some((item) => item.id === groupId);
    if (!exists) {
      setGroupViewFilter("all");
    }
  }, [groupViewFilter, assignmentGroups]);

  const handleAiAssist = async () => {
    if (!submissionId) return;
    setAiLoading(true);
    setError("");
    setNotice("");

    try {
      const result = await evaluationsApi.aiAssist(submissionId);
      const suggestion = result.suggestion;
      const nextScores: Record<string, number> = {};

      rubricDimensions.forEach((name) => {
        const source = suggestion.dimension_scores?.[name];
        nextScores[name] = clampScore(source ?? 3);
      });

      if (rubricDimensions.length === 0) {
        Object.entries(suggestion.dimension_scores || {}).forEach(([name, score]) => {
          nextScores[name] = clampScore(score);
        });
      }

      setDimensionScores(nextScores);
      setScoreNumeric(clampScore(suggestion.suggested_score || 3));
      setFeedback(suggestion.feedback || "");
      setNotice("AI 建议已生成，请教师复核后提交评分");
    } catch (err) {
      setError(getApiErrorMessage(err, "AI 辅助评分失败"));
    } finally {
      setAiLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!submissionId) return;
    const validationError = validateTeacherEvaluation({
      rubricDimensions,
      dimensionScores,
      feedback,
    });
    if (validationError) {
      setError(validationError);
      setNotice("");
      return;
    }
    setSubmitting(true);
    setError("");
    setNotice("");

    const payload: TeacherEvaluationPayload = {
      submission_id: submissionId,
      score_numeric: clampScore(scoreNumeric),
      dimension_scores_json:
        Object.keys(dimensionScores).length > 0
          ? Object.fromEntries(
              Object.entries(dimensionScores).map(([name, value]) => [name, clampScore(value)]),
            )
          : {},
      feedback: feedback.trim(),
    };

    try {
      await evaluationsApi.createTeacher(payload);
      setNotice("评分提交成功");
      await loadData();
    } catch (err) {
      setError(getApiErrorMessage(err, "提交评分失败"));
    } finally {
      setSubmitting(false);
    }
  };

  if (!user || user.role !== "teacher") {
    return <PageState variant="warning" title="访问受限" description="仅教师可访问批改页面。" actionLabel="返回学生首页" actionTo="/student" />;
  }

  if (!submissionId) {
    return <PageState variant="warning" title="参数无效" description="提交 ID 无效，请从作业详情重新进入。" actionLabel="返回首页" actionTo="/" />;
  }

  if (loading) {
    return <PageState variant="loading" title="正在加载评分数据" description="正在同步提交内容与量表信息。" />;
  }

  if (!submission || !assignment) {
    return (
      <PageState
        variant="error"
        title="未找到提交记录"
        description={error || "该提交可能已删除或你无权限访问。"}
        actionLabel="重试"
        onAction={loadData}
      />
    );
  }

  return (
    <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-[2fr,1fr] gap-6">
      <section className="bg-surface rounded-2xl border border-border p-6 space-y-4">
        <div>
          <h1 className="text-2xl font-bold">{assignment.title}</h1>
          <p className="text-sm text-text-secondary mt-1">
            学生 ID：{submission.student_id} · 阶段：{submission.phase_index + 1} · 状态：
            {submissionStatusLabel(submission.status)}
          </p>
          {submission.group_name && (
            <p className="text-xs text-primary mt-1">
              小组提交：{submission.group_name}
              {submission.group_members?.length
                ? `（${submission.group_members.map((member) => member.name || member.username || `ID:${member.user_id}`).join("、")}）`
                : ""}
            </p>
          )}
          <Link
            to={`/assignment/${assignment.id}`}
            className="inline-flex mt-2 text-xs font-semibold text-primary hover:underline"
          >
            返回作业提交
          </Link>
        </div>

        <div className="rounded-2xl border border-border-strong bg-surface-muted p-4 space-y-3">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
            <h2 className="text-sm font-semibold text-text">小组聚合视图</h2>
            <select
              value={groupViewFilter}
              onChange={(e) => setGroupViewFilter(e.target.value)}
              className="px-3 py-2 rounded-lg border border-border-strong text-xs"
            >
              <option value="all">全部小组/个人</option>
              <option value="ungrouped">仅个人提交</option>
              {assignmentGroups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </select>
          </div>

          {filteredGroupAggregateRows.length === 0 ? (
            <p className="text-xs text-text-secondary">当前筛选下暂无提交记录。</p>
          ) : (
            <div className="space-y-2">
              <div className="bg-surface border border-border-strong rounded-lg p-3 space-y-2">
                <p className="text-xs font-semibold text-text">组内评分分布小结</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                  <div className="rounded-md bg-surface-muted border border-border-strong px-2 py-1.5">
                    <p className="text-text-secondary">聚合单元</p>
                    <p className="font-semibold text-text mt-0.5">{groupScoreSummary.totalBuckets}</p>
                  </div>
                  <div className="rounded-md bg-surface-muted border border-border-strong px-2 py-1.5">
                    <p className="text-text-secondary">高风险组</p>
                    <p className="font-semibold text-danger mt-0.5">{groupScoreSummary.highRiskBuckets}</p>
                  </div>
                  <div className="rounded-md bg-surface-muted border border-border-strong px-2 py-1.5">
                    <p className="text-text-secondary">待评分</p>
                    <p className="font-semibold text-primary mt-0.5">
                      {groupScoreSummary.submitted}（{groupScoreSummary.pendingRate}%）
                    </p>
                  </div>
                  <div className="rounded-md bg-surface-muted border border-border-strong px-2 py-1.5">
                    <p className="text-text-secondary">已评分</p>
                    <p className="font-semibold text-success mt-0.5">
                      {groupScoreSummary.graded}（{groupScoreSummary.gradedRate}%）
                    </p>
                  </div>
                </div>
                <p className="text-[11px] text-text-secondary">
                  总提交 {groupScoreSummary.totalSubmissions} 次，草稿 {groupScoreSummary.draft} 次。
                </p>
              </div>

              {filteredGroupAggregateRows.map((item) => (
                <div key={item.key} className="bg-surface border border-border-strong rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-text">{item.label}</p>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[11px] px-2 py-0.5 rounded-full ${
                          item.riskScore >= 3
                            ? "bg-danger-soft text-danger"
                            : item.riskScore >= 2
                              ? "bg-warning-soft text-warning"
                              : item.riskScore >= 1
                                ? "bg-secondary text-primary"
                                : "bg-success-soft text-success"
                        }`}
                      >
                        {item.riskText}
                      </span>
                      {item.latestSubmission ? (
                        <Link
                          to={`/grading/${item.latestSubmission.id}`}
                          className="text-xs font-semibold text-primary hover:underline"
                        >
                          {item.latestSubmission.id === submission.id ? "当前批改" : "查看最新提交"}
                        </Link>
                      ) : (
                        <span className="text-xs text-text-muted">暂无提交</span>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-text-secondary mt-1">
                    阶段进度 {item.phaseProgress} · 提交 {item.totalSubmissions} 次 · 待评分 {item.submittedCount} · 已评分 {item.gradedCount}
                  </p>
                  <p className="text-[11px] text-text-muted mt-1">
                    最近提交：{formatDateTime(item.lastSubmittedAt)} · 最近评分：{formatDateTime(item.lastEvaluatedAt)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-border bg-surface-muted p-4">
          <h2 className="text-sm font-semibold text-text mb-2">提交内容</h2>
          <pre className="text-xs text-text whitespace-pre-wrap break-words">
            {typeof submission.content_json?.text === "string"
              ? (submission.content_json.text as string)
              : JSON.stringify(submission.content_json, null, 2)}
          </pre>
        </div>

        <div className="rounded-2xl border border-border bg-surface-muted p-4">
          <h2 className="text-sm font-semibold text-text mb-2">附件</h2>
          {submission.attachments_json?.length ? (
            <ul className="space-y-2">
              {submission.attachments_json.map((attachment, index) => (
                <li key={`${attachment.filename}_${index}`} className="text-sm text-primary">
                  <a href={attachment.url} target="_blank" rel="noreferrer" className="hover:underline">
                    {attachment.filename}
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-text-secondary">暂无附件</p>
          )}
        </div>

        <div className="rounded-2xl border border-border bg-surface-muted p-4">
          <h2 className="text-sm font-semibold text-text mb-2">检查点完成情况</h2>
          {Object.keys(submission.checkpoints_json || {}).length === 0 ? (
            <p className="text-xs text-text-secondary">暂无检查点记录</p>
          ) : (
            <ul className="space-y-1">
              {Object.entries(submission.checkpoints_json || {}).map(([name, value]) => (
                <li key={name} className="text-sm text-text flex items-center gap-2">
                  {value ? <CheckCircle2 className="w-4 h-4 text-success" /> : <Star className="w-4 h-4 text-text-muted" />} {name}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <aside className="bg-surface rounded-2xl border border-border p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">评分面板</h2>
          <button
            onClick={handleAiAssist}
            disabled={aiLoading}
            className="px-3 py-2 rounded-lg bg-primary text-white text-xs font-semibold hover:bg-primary-hover active:bg-primary-active disabled:opacity-60 flex items-center gap-1"
          >
            {aiLoading ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />} AI 辅助
          </button>
        </div>

        {notice && <StatusBanner tone="info" message={notice} />}
        {error && <StatusBanner tone="error" message={error} />}

        <div className="space-y-4">
          {rubricDimensions.length === 0 && <p className="text-sm text-text-secondary">当前作业未配置维度量表。</p>}
          {rubricDimensions.map((dimensionName) => {
            const value = clampScore(dimensionScores[dimensionName] || 3);
            return (
              <div key={dimensionName} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-semibold text-text">{dimensionName}</span>
                  <span className="text-primary font-bold">
                    {value}（{SCORE_LABELS[value]}）
                  </span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={4}
                  step={1}
                  value={value}
                  onChange={(e) => {
                    const next = clampScore(Number(e.target.value));
                    setDimensionScores((prev) => ({ ...prev, [dimensionName]: next }));
                  }}
                  className="w-full"
                />
              </div>
            );
          })}
        </div>

        <div className="rounded-2xl border border-border-strong p-4 bg-surface-muted space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-semibold text-text">总评价</span>
            <span className="font-bold text-primary">
              {clampScore(scoreNumeric)}（{SCORE_LABELS[clampScore(scoreNumeric)]}）
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={4}
            step={1}
            value={clampScore(scoreNumeric)}
            onChange={(e) => setScoreNumeric(clampScore(Number(e.target.value)))}
            className="w-full"
          />
        </div>

        <div>
          <label className="text-sm font-semibold text-text">教师评语</label>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            rows={6}
            className="mt-2 w-full px-3 py-2 rounded-xl border border-border-strong resize-none"
            placeholder="请输入本阶段评价与改进建议"
          />
        </div>

        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full py-3 rounded-xl bg-primary text-white font-semibold hover:bg-primary-hover active:bg-primary-active disabled:opacity-60 flex items-center justify-center gap-2"
        >
          {submitting ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />} 提交评分
        </button>
      </aside>
    </div>
  );
}
