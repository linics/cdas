import type { AssignmentGroup, AssignmentPhase, Submission } from "../lib/api";

export interface EvidenceHint {
  content: string;
  evidenceType: string;
}

export interface SubmissionGroupProgressRow {
  key: string;
  label: string;
  groupId: number | null;
  group: AssignmentGroup | null;
  latestSubmission: Submission | null;
  submissions: Submission[];
  totalSubmissions: number;
  submittedCount: number;
  gradedCount: number;
  lastSubmittedAt: string | null;
  lastEvaluatedAt: string | null;
  riskScore: number;
  riskText: string;
  phaseProgress: string;
}

export interface SubmissionGroupProgressInput {
  groups: AssignmentGroup[];
  submissions: Submission[];
  totalPhases: number;
  deadline?: string | null;
  includeUngrouped?: boolean;
  preseedGroups?: boolean;
  latestSubmissionStrategy?: "latest_timestamp" | "highest_phase_then_time";
}

export interface SubmissionGroupScoreSummary {
  totalBuckets: number;
  totalSubmissions: number;
  submitted: number;
  graded: number;
  highRiskBuckets: number;
  draft: number;
  gradedRate: number;
  pendingRate: number;
}

export function statusLabel(status: string): string {
  if (status === "draft") return "草稿";
  if (status === "submitted") return "已提交";
  if (status === "graded") return "已评分";
  return status;
}

export function submissionModeLabel(mode: string): string {
  if (mode === "phased") return "过程性提交";
  if (mode === "once") return "一次性提交";
  if (mode === "mixed") return "混合提交";
  return mode;
}

export function gradeLabel(grade: number): string {
  if (grade <= 6) return `小学${grade}年级`;
  return `初中${Math.max(1, grade - 6)}年级`;
}

export function scoreLabel(level: string | null | undefined): string {
  const mapping: Record<string, string> = {
    excellent: "优秀",
    good: "良好",
    pass: "合格",
    improve: "需改进",
  };
  if (!level) return "";
  return mapping[level] || level;
}

export function clampScore(value: number): number {
  if (!Number.isFinite(value)) return 3;
  return Math.max(1, Math.min(4, Math.round(value)));
}

export function evidenceTypeLabel(value: string | null | undefined): string {
  const mapping: Record<string, string> = {
    text: "文本",
    document: "文档",
    image: "图片",
    video: "视频",
    confirm: "确认",
    link: "链接",
  };
  if (!value) return "";
  return mapping[value] || value;
}

export function formatDateTime(value: string | null | undefined): string {
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

export function normalizeForMatch(value: string): string {
  return (value || "").toLowerCase().replace(/\s+/g, "");
}

export function extractGroupMemberIds(group: AssignmentGroup): number[] {
  return (group.members_json || [])
    .map((item) => Number(item.user_id))
    .filter((value) => Number.isFinite(value) && value > 0);
}

export function groupMemberText(group: AssignmentGroup): string {
  const names = (group.members_json || [])
    .map((item) => item.name || item.username || `ID:${item.user_id}`)
    .filter(Boolean);
  return names.join("、") || "暂无成员";
}

function toMs(value: string | null | undefined): number {
  if (!value) return -1;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : -1;
}

function ensureBucket(
  buckets: Map<string, SubmissionGroupProgressRow>,
  key: string,
  label: string,
  groupId: number | null,
  group: AssignmentGroup | null,
): SubmissionGroupProgressRow {
  const existing = buckets.get(key);
  if (existing) return existing;

  const created: SubmissionGroupProgressRow = {
    key,
    label,
    groupId,
    group,
    latestSubmission: null,
    submissions: [],
    totalSubmissions: 0,
    submittedCount: 0,
    gradedCount: 0,
    lastSubmittedAt: null,
    lastEvaluatedAt: null,
    riskScore: 0,
    riskText: "正常",
    phaseProgress: "0/0",
  };
  buckets.set(key, created);
  return created;
}

export function buildGroupProgressRows({
  groups,
  submissions,
  totalPhases,
  deadline,
  includeUngrouped = false,
  preseedGroups = false,
  latestSubmissionStrategy = "latest_timestamp",
}: SubmissionGroupProgressInput): SubmissionGroupProgressRow[] {
  const deadlineMs = deadline ? toMs(deadline) : -1;
  const nowMs = Date.now();

  const groupNameById = new Map<number, string>();
  groups.forEach((group) => {
    groupNameById.set(group.id, group.name);
  });

  const buckets = new Map<string, SubmissionGroupProgressRow>();

  if (preseedGroups) {
    groups.forEach((group) => {
      ensureBucket(buckets, `group:${group.id}`, group.name, group.id, group);
    });
  }

  submissions.forEach((item) => {
    const isGrouped = !!item.group_id;
    const key = isGrouped ? `group:${item.group_id}` : "ungrouped";
    if (!buckets.has(key)) {
      if (!isGrouped && !includeUngrouped) return;
      const groupId = isGrouped ? Number(item.group_id) : null;
      const label = isGrouped
        ? groupNameById.get(groupId || 0) || item.group_name || `小组#${item.group_id}`
        : "个人提交";
      const syntheticGroup = isGrouped && groupId
        ? { id: groupId, assignment_id: item.assignment_id, name: label, members_json: [] }
        : null;
      ensureBucket(buckets, key, label, groupId, syntheticGroup);
    }
    buckets.get(key)?.submissions.push(item);
  });

  return Array.from(buckets.values())
    .map((bucket) => {
      const sorted = [...bucket.submissions].sort((a, b) => {
        if (latestSubmissionStrategy === "highest_phase_then_time" && a.phase_index !== b.phase_index) {
          return b.phase_index - a.phase_index;
        }
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
}

export function buildGroupScoreSummary(rows: SubmissionGroupProgressRow[]): SubmissionGroupScoreSummary {
  const totals = rows.reduce(
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
}

export function collectPhaseEvidenceHints(phase: AssignmentPhase | null | undefined): EvidenceHint[] {
  if (!phase || !Array.isArray(phase.steps)) {
    return [];
  }
  const seen = new Set<string>();
  const hints: EvidenceHint[] = [];
  phase.steps.forEach((step) => {
    if (!step || !Array.isArray(step.checkpoints)) return;
    step.checkpoints.forEach((cp) => {
      const content = (cp?.content || "").trim();
      if (!content) return;
      if (seen.has(content)) return;
      seen.add(content);
      hints.push({ content, evidenceType: cp?.evidence_type || "text" });
    });
  });
  return hints;
}

export function countCoveredEvidence(
  hints: EvidenceHint[],
  contentText: string,
  attachments: Array<{ filename: string; url: string }>,
): number {
  if (!hints.length) return 0;
  const attachmentText = attachments.map((item) => `${item.filename} ${item.url}`).join(" ");
  const combined = normalizeForMatch(`${contentText} ${attachmentText}`);
  if (!combined) return 0;
  return hints.filter((hint) => {
    const normalizedHint = normalizeForMatch(hint.content);
    return normalizedHint.length >= 2 && combined.includes(normalizedHint);
  }).length;
}
