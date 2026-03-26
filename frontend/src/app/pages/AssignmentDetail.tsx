import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import {
  CheckCircle2,
  Circle,
  FileUp,
  LoaderCircle,
  Save,
  Send,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import {
  assignmentsApi,
  classesApi,
  evaluationsApi,
  getApiErrorMessage,
  submissionsApi,
  type Assignment,
  type AssignmentGroup,
  type Classroom,
  type ClassroomMember,
  type Evaluation,
  type Submission,
} from "../lib/api";
import { stageToSchoolLevel } from "../lib/mappers";
import { PageState } from "../components/PageState";
import { StatusBanner } from "../components/StatusBanner";
import { validateGroupName } from "../validation/classroom";
import { validateAttachmentDraft, validateSubmissionForSubmit } from "../validation/submission";

function statusLabel(status: string): string {
  if (status === "draft") return "草稿";
  if (status === "submitted") return "已提交";
  if (status === "graded") return "已评分";
  return status;
}

function scoreLabel(level: string | null | undefined): string {
  const mapping: Record<string, string> = {
    excellent: "优秀",
    good: "良好",
    pass: "合格",
    improve: "需改进",
  };
  if (!level) return "";
  return mapping[level] || level;
}

function submissionModeLabel(mode: string): string {
  if (mode === "phased") return "过程性提交";
  if (mode === "once") return "一次性提交";
  if (mode === "mixed") return "混合提交";
  return mode;
}

function gradeLabel(grade: number): string {
  if (grade <= 6) return `小学${grade}年级`;
  return `初中${Math.max(1, grade - 6)}年级`;
}

function evidenceTypeLabel(value: string | null | undefined): string {
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

function normalizeForMatch(value: string): string {
  return (value || "").toLowerCase().replace(/\s+/g, "");
}

function splitBackgroundFromProcess(processText: string): { background: string; process: string } {
  const raw = (processText || "").trim();
  if (!raw) {
    return { background: "", process: "" };
  }

  if (!raw.startsWith("背景设定：") && !raw.startsWith("背景设定:")) {
    return { background: "", process: raw };
  }

  const body = raw.replace(/^背景设定[:：]\s*/, "").trim();
  if (!body) {
    return { background: "", process: "" };
  }

  const lines = body
    .split(/\r?\n+/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length >= 2) {
    return {
      background: lines[0],
      process: lines.slice(1).join("\n").trim(),
    };
  }

  const marker = "行动主线：";
  if (body.includes(marker)) {
    const [bg, rest] = body.split(marker, 2);
    return {
      background: bg.trim(),
      process: `${marker}${(rest || "").trim()}`.trim(),
    };
  }

  if (body.length > 150) {
    const splitAt = Math.max(
      body.lastIndexOf("。", 170),
      body.lastIndexOf("！", 170),
      body.lastIndexOf("？", 170),
      body.lastIndexOf("!", 170),
      body.lastIndexOf("?", 170),
    );
    if (splitAt >= 40) {
      return {
        background: body.slice(0, splitAt + 1).trim(),
        process: body.slice(splitAt + 1).trim(),
      };
    }
  }

  return { background: body, process: "" };
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

function extractGroupMemberIds(group: AssignmentGroup): number[] {
  return (group.members_json || [])
    .map((item) => Number(item.user_id))
    .filter((value) => Number.isFinite(value) && value > 0);
}

function groupMemberText(group: AssignmentGroup): string {
  const names = (group.members_json || [])
    .map((item) => item.name || item.username || `ID:${item.user_id}`)
    .filter(Boolean);
  return names.join("、") || "暂无成员";
}

export function AssignmentDetail() {
  const { user } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const assignmentId = Number(id || 0);

  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [assignmentGroups, setAssignmentGroups] = useState<AssignmentGroup[]>([]);
  const [teacherClasses, setTeacherClasses] = useState<Classroom[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [classMembers, setClassMembers] = useState<ClassroomMember[]>([]);
  const [selectedMemberIds, setSelectedMemberIds] = useState<number[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [activeSubmissionId, setActiveSubmissionId] = useState<number | null>(null);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);

  const [contentText, setContentText] = useState("");
  const [attachments, setAttachments] = useState<Array<{ filename: string; url: string; type: string }>>([]);
  const [attachmentName, setAttachmentName] = useState("");
  const [attachmentUrl, setAttachmentUrl] = useState("");

  const [groupNameInput, setGroupNameInput] = useState("");
  const [createMemberSearch, setCreateMemberSearch] = useState("");
  const [editingGroupId, setEditingGroupId] = useState<number | null>(null);
  const [editingMemberIds, setEditingMemberIds] = useState<number[]>([]);
  const [editMemberSearch, setEditMemberSearch] = useState("");
  const [updatingGroupMembers, setUpdatingGroupMembers] = useState(false);
  const [groupRiskFilter, setGroupRiskFilter] = useState<"all" | "high">("all");
  const [teacherGroupFilter, setTeacherGroupFilter] = useState<string>("all");

  const [loading, setLoading] = useState(true);
  const [loadingClassMembers, setLoadingClassMembers] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [creatingGroup, setCreatingGroup] = useState(false);
  const [deletingGroupId, setDeletingGroupId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadData = useCallback(async () => {
    if (!assignmentId) return;
    setLoading(true);
    setError("");

    try {
      const [assignmentDetail, groupList] = await Promise.all([
        assignmentsApi.getById(assignmentId),
        assignmentsApi.listGroups(assignmentId).catch(() => [] as AssignmentGroup[]),
      ]);
      setAssignment(assignmentDetail);
      setAssignmentGroups(groupList || []);

      if (user?.role === "student") {
        setTeacherClasses([]);
        setSelectedClassId(null);
        setClassMembers([]);
        setSelectedMemberIds([]);
        const mySubmissions = await submissionsApi.listMy(assignmentId);
        const list = mySubmissions.submissions || [];
        setSubmissions(list);

        if (list.length > 0) {
          const requestedId = Number(new URLSearchParams(location.search).get("submission") || 0);
          const sorted = [...list].sort((a, b) => {
            if (a.phase_index !== b.phase_index) return a.phase_index - b.phase_index;
            return a.created_at < b.created_at ? -1 : 1;
          });
          const requested = list.find((item) => item.id === requestedId);
          const fallback = sorted[sorted.length - 1];
          setActiveSubmissionId((requested || fallback).id);
        } else {
          setActiveSubmissionId(null);
        }
      } else if (user?.role === "teacher") {
        const [teacherSubmissions, classResp] = await Promise.all([
          submissionsApi.listByAssignment(assignmentId),
          classesApi.listMy().catch(() => ({ classes: [], total: 0 })),
        ]);
        const list = teacherSubmissions.submissions || [];
        const classList = classResp.classes || [];

        setSubmissions(list);
        setTeacherClasses(classList);
        setSelectedClassId((prev) => {
          if (prev && classList.some((item) => item.id === prev)) return prev;
          return classList.length > 0 ? classList[0].id : null;
        });

        if (list.length > 0) {
          setActiveSubmissionId(list[0].id);
        } else {
          setActiveSubmissionId(null);
        }
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "加载作业详情失败"));
    } finally {
      setLoading(false);
    }
  }, [assignmentId, user?.role, location.search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (user?.role !== "teacher" || !selectedClassId) {
      setClassMembers([]);
      setSelectedMemberIds([]);
      return;
    }

    let mounted = true;
    setLoadingClassMembers(true);

    classesApi
      .listMembers(selectedClassId)
      .then((response) => {
        if (!mounted) return;
        const members = response.members || [];
        setClassMembers(members);
        setSelectedMemberIds((prev) => prev.filter((id) => members.some((item) => item.student_id === id)));
      })
      .catch((err) => {
        if (!mounted) return;
        setClassMembers([]);
        setError(getApiErrorMessage(err, "加载班级学生失败"));
      })
      .finally(() => {
        if (mounted) setLoadingClassMembers(false);
      });

    return () => {
      mounted = false;
    };
  }, [selectedClassId, user?.role]);

  const activeSubmission = useMemo(
    () => submissions.find((item) => item.id === activeSubmissionId) || null,
    [submissions, activeSubmissionId],
  );

  const myJoinedGroup = useMemo(() => {
    if (!user || user.role !== "student") return null;
    return (
      assignmentGroups.find((group) => extractGroupMemberIds(group).includes(user.id)) ||
      null
    );
  }, [assignmentGroups, user]);

  useEffect(() => {
    if (!activeSubmission) {
      setContentText("");
      setAttachments([]);
      return;
    }

    const text =
      typeof activeSubmission.content_json?.text === "string"
        ? (activeSubmission.content_json.text as string)
        : JSON.stringify(activeSubmission.content_json || {}, null, 2);

    setContentText(text === "{}" ? "" : text);
    setAttachments(
      (activeSubmission.attachments_json || []).map((item) => ({
        filename: item.filename,
        url: item.url,
        type: item.type,
      })),
    );
  }, [activeSubmission]);

  const loadEvaluations = useCallback(async () => {
    if (!activeSubmissionId) {
      setEvaluations([]);
      return;
    }

    try {
      const response = await evaluationsApi.listBySubmission(activeSubmissionId);
      setEvaluations(response.evaluations || []);
    } catch {
      setEvaluations([]);
    }
  }, [activeSubmissionId]);

  useEffect(() => {
    loadEvaluations();
  }, [loadEvaluations]);

  const currentPhase = useMemo(() => {
    if (!assignment || !activeSubmission) return null;
    return assignment.phases_json?.[activeSubmission.phase_index] || null;
  }, [assignment, activeSubmission]);

  const assignmentNarrative = useMemo(() => {
    const processText = assignment?.objectives_json?.process || "";
    return splitBackgroundFromProcess(processText);
  }, [assignment]);

  const phaseEvidenceHints = useMemo(() => {
    if (!currentPhase || !Array.isArray(currentPhase.steps)) {
      return [] as Array<{ content: string; evidenceType: string }>;
    }
    const seen = new Set<string>();
    const hints: Array<{ content: string; evidenceType: string }> = [];
    currentPhase.steps.forEach((step) => {
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
  }, [currentPhase]);

  const coveredEvidenceCount = useMemo(() => {
    if (!phaseEvidenceHints.length) return 0;
    const attachmentText = attachments.map((item) => `${item.filename} ${item.url}`).join(" ");
    const combined = normalizeForMatch(`${contentText} ${attachmentText}`);
    if (!combined) return 0;
    return phaseEvidenceHints.filter((hint) => {
      const normalizedHint = normalizeForMatch(hint.content);
      return normalizedHint.length >= 2 && combined.includes(normalizedHint);
    }).length;
  }, [phaseEvidenceHints, contentText, attachments]);

  const addHintToSubmission = (hint: string) => {
    const entry = `- ${hint}`;
    setContentText((prev) => {
      const trimmed = prev.trim();
      if (!trimmed) return entry;
      if (trimmed.includes(hint)) return prev;
      return `${trimmed}\n${entry}`;
    });
  };

  const teacherEvaluation = useMemo(
    () => evaluations.find((item) => item.evaluation_type === "teacher") || null,
    [evaluations],
  );

  const groupProgress = useMemo(() => {
    const totalPhases = assignment?.phases_json?.length || 0;
    const byGroup = new Map<number, Submission[]>();

    const toMs = (value: string | null | undefined): number => {
      if (!value) return -1;
      const ms = Date.parse(value);
      return Number.isFinite(ms) ? ms : -1;
    };

    const deadlineMs = assignment?.deadline ? toMs(assignment.deadline) : -1;
    const nowMs = Date.now();

    submissions.forEach((item) => {
      if (!item.group_id) return;
      const list = byGroup.get(item.group_id) || [];
      list.push(item);
      byGroup.set(item.group_id, list);
    });

    return assignmentGroups.map((group) => {
      const list = byGroup.get(group.id) || [];
      const sorted = [...list].sort((a, b) => {
        if (a.phase_index !== b.phase_index) return b.phase_index - a.phase_index;
        return a.created_at < b.created_at ? 1 : -1;
      });
      const latest = sorted[0] || null;
      const maxPhase = list.reduce((max, item) => Math.max(max, item.phase_index), -1);

      const lastSubmitted = list.reduce<string | null>((latestValue, item) => {
        const candidate = item.submitted_at || item.created_at;
        if (!latestValue) return candidate;
        return toMs(candidate) > toMs(latestValue) ? candidate : latestValue;
      }, null);

      const lastEvaluated = list.reduce<string | null>((latestValue, item) => {
        const candidate = item.teacher_evaluated_at || null;
        if (!candidate) return latestValue;
        if (!latestValue) return candidate;
        return toMs(candidate) > toMs(latestValue) ? candidate : latestValue;
      }, null);

      let riskScore = 0;
      let riskText = "正常";
      const hasSubmission = list.length > 0;
      const hasPendingEvaluation = list.some((item) => item.status === "submitted");

      if (deadlineMs > 0) {
        const msToDeadline = deadlineMs - nowMs;
        if (!hasSubmission && msToDeadline < 0) {
          riskScore = 3;
          riskText = "已逾期未提交";
        } else if (!hasSubmission && msToDeadline <= 48 * 60 * 60 * 1000) {
          riskScore = 2;
          riskText = "临近截止未提交";
        } else if (msToDeadline < 0 && hasPendingEvaluation) {
          riskScore = 2;
          riskText = "已截止待评分";
        }
      }

      if (riskScore < 1 && hasPendingEvaluation) {
        riskScore = 1;
        riskText = "有待评分提交";
      }

      return {
        group,
        latestSubmission: latest,
        totalSubmissions: list.length,
        submittedCount: list.filter((item) => item.status === "submitted").length,
        gradedCount: list.filter((item) => item.status === "graded").length,
        lastSubmittedAt: lastSubmitted,
        lastEvaluatedAt: lastEvaluated,
        riskScore,
        riskText,
        phaseProgress:
          totalPhases > 0 && maxPhase >= 0
            ? `${Math.min(maxPhase + 1, totalPhases)}/${totalPhases}`
            : `0/${totalPhases || 0}`,
      };
    }).sort((a, b) => {
      if (a.riskScore !== b.riskScore) return b.riskScore - a.riskScore;
      return toMs(a.lastSubmittedAt) - toMs(b.lastSubmittedAt);
    });
  }, [assignmentGroups, submissions, assignment?.phases_json, assignment?.deadline]);

  const highRiskCount = useMemo(
    () => groupProgress.filter((item) => item.riskScore >= 2).length,
    [groupProgress],
  );

  const visibleGroupProgress = useMemo(() => {
    if (groupRiskFilter === "high") {
      return groupProgress.filter((item) => item.riskScore >= 2);
    }
    return groupProgress;
  }, [groupProgress, groupRiskFilter]);

  const teacherVisibleSubmissions = useMemo(() => {
    if (user?.role !== "teacher") return submissions;

    if (teacherGroupFilter === "all") return submissions;
    if (teacherGroupFilter === "ungrouped") {
      return submissions.filter((item) => !item.group_id);
    }

    const groupId = Number(teacherGroupFilter);
    if (!Number.isFinite(groupId) || groupId <= 0) return submissions;
    return submissions.filter((item) => item.group_id === groupId);
  }, [submissions, teacherGroupFilter, user?.role]);

  useEffect(() => {
    if (user?.role !== "teacher") return;
    if (teacherGroupFilter === "all" || teacherGroupFilter === "ungrouped") return;

    const groupId = Number(teacherGroupFilter);
    if (!Number.isFinite(groupId) || groupId <= 0) {
      setTeacherGroupFilter("all");
      return;
    }

    const exists = assignmentGroups.some((item) => item.id === groupId);
    if (!exists) {
      setTeacherGroupFilter("all");
    }
  }, [assignmentGroups, teacherGroupFilter, user?.role]);

  useEffect(() => {
    if (editingGroupId === null) return;
    const exists = assignmentGroups.some((item) => item.id === editingGroupId);
    if (!exists) {
      setEditingGroupId(null);
      setEditingMemberIds([]);
    }
  }, [assignmentGroups, editingGroupId]);

  useEffect(() => {
    if (groupRiskFilter === "high" && highRiskCount === 0) {
      setGroupRiskFilter("all");
    }
  }, [groupRiskFilter, highRiskCount]);

  useEffect(() => {
    if (user?.role !== "teacher") return;
    if (teacherVisibleSubmissions.length === 0) {
      setActiveSubmissionId(null);
      return;
    }
    if (!activeSubmissionId || !teacherVisibleSubmissions.some((item) => item.id === activeSubmissionId)) {
      setActiveSubmissionId(teacherVisibleSubmissions[0].id);
    }
  }, [teacherVisibleSubmissions, activeSubmissionId, user?.role]);

  const editingGroup = useMemo(
    () => assignmentGroups.find((item) => item.id === editingGroupId) || null,
    [assignmentGroups, editingGroupId],
  );

  const editingMemberCandidates = useMemo(() => {
    const candidateMap = new Map<number, { user_id: number; name?: string; username?: string }>();

    classMembers.forEach((member) => {
      candidateMap.set(member.student_id, {
        user_id: member.student_id,
        name: member.student_name,
        username: member.student_username,
      });
    });

    if (editingGroup) {
      (editingGroup.members_json || []).forEach((item) => {
        const userId = Number(item.user_id);
        if (!Number.isFinite(userId) || userId <= 0 || candidateMap.has(userId)) return;
        candidateMap.set(userId, {
          user_id: userId,
          name: item.name,
          username: item.username,
        });
      });
    }

    return Array.from(candidateMap.values()).sort((a, b) => a.user_id - b.user_id);
  }, [classMembers, editingGroup]);

  const filteredCreateMembers = useMemo(() => {
    const keyword = createMemberSearch.trim().toLowerCase();
    if (!keyword) return classMembers;
    return classMembers.filter((member) => {
      const haystacks = [
        member.student_name,
        member.student_username,
        String(member.student_id),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystacks.includes(keyword);
    });
  }, [classMembers, createMemberSearch]);

  const filteredEditingMembers = useMemo(() => {
    const keyword = editMemberSearch.trim().toLowerCase();
    if (!keyword) return editingMemberCandidates;
    return editingMemberCandidates.filter((member) => {
      const haystacks = [
        member.name,
        member.username,
        String(member.user_id),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystacks.includes(keyword);
    });
  }, [editingMemberCandidates, editMemberSearch]);

  const addAttachment = () => {
    const errorMessage = validateAttachmentDraft(attachmentName, attachmentUrl, attachments);
    if (errorMessage) {
      setNotice(errorMessage);
      return;
    }
    const name = attachmentName.trim();
    const url = attachmentUrl.trim();

    setAttachments((prev) => [...prev, { filename: name, url, type: "link" }]);
    setAttachmentName("");
    setAttachmentUrl("");
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, idx) => idx !== index));
  };

  const saveDraft = async () => {
    if (!activeSubmission) return;
    setSaving(true);
    setError("");

    try {
      await submissionsApi.update(activeSubmission.id, {
        content_json: { text: contentText },
        attachments_json: attachments,
      });
      setNotice("草稿已保存");
      await loadData();
    } catch (err) {
      setError(getApiErrorMessage(err, "保存草稿失败"));
    } finally {
      setSaving(false);
    }
  };

  const submitCurrent = async () => {
    if (!activeSubmission) return;
    const validationError = validateSubmissionForSubmit({
      contentText,
      attachments,
      checkpoints: activeSubmission.checkpoints_json,
    });
    if (validationError) {
      setError(validationError);
      return;
    }
    setSubmitting(true);
    setError("");

    try {
      await submissionsApi.update(activeSubmission.id, {
        content_json: { text: contentText },
        attachments_json: attachments,
      });

      const result = await submissionsApi.submit(activeSubmission.id);
      if (result.next_submission_id) {
        setNotice("当前阶段已提交，已为你准备下一阶段草稿");
        navigate(`/assignment/${assignmentId}?submission=${result.next_submission_id}`, { replace: true });
      } else {
        const totalPhases = assignment?.phases_json?.length || 0;
        const reachedFinalPhase = totalPhases > 0 && activeSubmission.phase_index >= totalPhases - 1;
        if (assignment?.submission_mode === "once") {
          setNotice("作业已提交（一次性提交模式）");
        } else if (reachedFinalPhase) {
          setNotice("当前阶段已提交，你已完成全部阶段");
        } else {
          setNotice("当前阶段已提交，下一阶段草稿尚未生成，请刷新后重试");
        }
      }
      await loadData();
    } catch (err) {
      setError(getApiErrorMessage(err, "提交作业失败"));
    } finally {
      setSubmitting(false);
    }
  };

  const startFirstSubmission = async () => {
    if (!assignment) return;
    setStarting(true);
    setError("");

    try {
      const created = await submissionsApi.create({
        assignment_id: assignment.id,
        phase_index: 0,
        group_id: myJoinedGroup?.id,
        content_json: { text: "" },
      });
      setNotice("已创建第一阶段草稿");
      navigate(`/assignment/${assignment.id}?submission=${created.id}`, { replace: true });
      await loadData();
    } catch (err) {
      setError(getApiErrorMessage(err, "创建作业草稿失败"));
    } finally {
      setStarting(false);
    }
  };

  const createAssignmentGroup = async () => {
    if (!assignment) return;
    const name = groupNameInput.trim();
    const nameError = validateGroupName(
      name,
      assignmentGroups.map((group) => group.name),
    );
    if (nameError) {
      setError(nameError);
      return;
    }

    if (selectedMemberIds.length === 0) {
      setError("请至少选择 1 名学生");
      return;
    }

    setCreatingGroup(true);
    setError("");
    setNotice("");
    try {
      const payloadMembers = selectedMemberIds.map((userId) => {
        const member = classMembers.find((item) => item.student_id === userId);
        return {
          user_id: userId,
          name: member?.student_name,
          username: member?.student_username,
        };
      });

      await assignmentsApi.createGroup(assignment.id, {
        name,
        members_json: payloadMembers,
      });
      setGroupNameInput("");
      setSelectedMemberIds([]);
      setNotice(`作业小组创建成功：${name}`);
      await loadData();
    } catch (err) {
      setError(getApiErrorMessage(err, "创建作业小组失败"));
    } finally {
      setCreatingGroup(false);
    }
  };

  const toggleMemberSelection = (studentId: number) => {
    setSelectedMemberIds((prev) =>
      prev.includes(studentId)
        ? prev.filter((item) => item !== studentId)
        : [...prev, studentId],
    );
  };

  const selectAllMembers = () => {
    setSelectedMemberIds(classMembers.map((item) => item.student_id));
  };

  const clearSelectedMembers = () => {
    setSelectedMemberIds([]);
  };

  const startEditGroupMembers = (group: AssignmentGroup) => {
    setEditingGroupId(group.id);
    setEditingMemberIds(extractGroupMemberIds(group));
    setEditMemberSearch("");
    setError("");
    setNotice("");
  };

  const cancelEditGroupMembers = () => {
    setEditingGroupId(null);
    setEditingMemberIds([]);
    setEditMemberSearch("");
  };

  const toggleEditingMemberSelection = (studentId: number) => {
    setEditingMemberIds((prev) =>
      prev.includes(studentId)
        ? prev.filter((item) => item !== studentId)
        : [...prev, studentId],
    );
  };

  const selectAllEditingMembers = () => {
    setEditingMemberIds(editingMemberCandidates.map((item) => item.user_id));
  };

  const clearEditingMembers = () => {
    setEditingMemberIds([]);
  };

  const saveGroupMembers = async (group: AssignmentGroup) => {
    if (!assignment) return;
    if (editingMemberIds.length === 0) {
      setError("小组至少需要 1 名成员");
      return;
    }

    setUpdatingGroupMembers(true);
    setError("");
    setNotice("");
    try {
      const payloadMembers = editingMemberIds.map((userId) => {
        const fromCandidates = editingMemberCandidates.find((item) => item.user_id === userId);
        const fromGroup = (group.members_json || []).find((item) => Number(item.user_id) === userId);
        return {
          user_id: userId,
          name: fromCandidates?.name || fromGroup?.name,
          username: fromCandidates?.username || fromGroup?.username,
        };
      });

      await assignmentsApi.updateGroupMembers(assignment.id, group.id, payloadMembers);
      setNotice(`已更新小组成员：${group.name}`);
      setEditingGroupId(null);
      setEditingMemberIds([]);
      await loadData();
    } catch (err) {
      setError(getApiErrorMessage(err, "更新小组成员失败"));
    } finally {
      setUpdatingGroupMembers(false);
    }
  };

  const deleteAssignmentGroup = async (group: AssignmentGroup) => {
    if (!assignment) return;
    const confirmed = window.confirm(`确认删除作业小组「${group.name}」吗？`);
    if (!confirmed) return;

    setDeletingGroupId(group.id);
    setError("");
    setNotice("");
    try {
      await assignmentsApi.deleteGroup(assignment.id, group.id);
      setNotice(`已删除作业小组：${group.name}`);
      await loadData();
    } catch (err) {
      setError(getApiErrorMessage(err, "删除作业小组失败"));
    } finally {
      setDeletingGroupId(null);
    }
  };

  if (!assignmentId) {
    return <PageState variant="warning" title="参数无效" description="作业 ID 无效，请返回列表重新进入。" actionLabel="返回首页" actionTo="/" />;
  }

  if (loading) {
    return <PageState variant="loading" title="正在加载作业详情" description="正在同步作业内容与提交记录。" />;
  }

  if (error && !assignment) {
    return <PageState variant="error" title="加载失败" description={error} actionLabel="重试" onAction={loadData} />;
  }

  if (!assignment) {
    return <PageState variant="info" title="作业不存在" description="该作业可能已被删除或你无权限访问。" actionLabel="返回首页" actionTo="/" />;
  }

  const backPath = user?.role === "teacher" ? "/" : "/student";
  const backLabel = user?.role === "teacher" ? "返回教师首页" : "返回我的作业";

  const readOnly = user?.role !== "student" || (activeSubmission ? activeSubmission.status !== "draft" : true);
  const visibleSubmissions = user?.role === "teacher" ? teacherVisibleSubmissions : submissions;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <section className="bg-surface rounded-2xl border border-border p-6 space-y-3">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black text-text">{assignment.title}</h1>
            <p className="text-sm text-text-secondary mt-2">{assignment.description || assignment.topic}</p>
            <p className="text-xs text-text-secondary mt-2">
              学段：{stageToSchoolLevel(assignment.school_stage)} · 年级：{gradeLabel(assignment.grade)} · 提交模式：
              {submissionModeLabel(assignment.submission_mode)}
            </p>
            {assignmentNarrative.background && (
              <div className="mt-3 rounded-xl border border-secondary bg-secondary px-3 py-2">
                <p className="text-[11px] font-semibold text-primary">背景设定</p>
                <p className="text-xs text-primary mt-1 leading-relaxed">{assignmentNarrative.background}</p>
                {assignmentNarrative.process && (
                  <p className="text-[11px] text-primary mt-2">任务主线：{assignmentNarrative.process}</p>
                )}
              </div>
            )}
          </div>
          <Link to={backPath} className="text-sm font-semibold text-primary hover:underline">
            {backLabel}
          </Link>
        </div>
        {notice && <StatusBanner tone="info" message={notice} />}
        {error && <StatusBanner tone="error" message={error} />}
      </section>

      {user?.role === "teacher" && (
        <section className="bg-warning-soft border border-warning/20 rounded-2xl p-6 text-sm text-warning">
          教师端建议通过“评价批改”页面查看学生提交并评分。
        </section>
      )}

      {user?.role === "teacher" && (
        <section className="bg-surface rounded-2xl border border-border p-6 space-y-4">
          <div>
            <h2 className="text-lg font-bold text-text">作业小组（协作模式）</h2>
            <p className="text-xs text-text-secondary mt-1">可为该作业创建小组并配置成员，成员将共享小组提交记录与评价可见性。</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr,1fr,auto] gap-2">
            <input
              value={groupNameInput}
              onChange={(e) => setGroupNameInput(e.target.value)}
              placeholder="小组名称，例如：第一组"
              className="px-3 py-2 rounded-lg border border-border-strong"
            />
            <select
              value={selectedClassId ? String(selectedClassId) : ""}
              onChange={(e) => {
                const nextId = Number(e.target.value);
                setSelectedClassId(Number.isFinite(nextId) && nextId > 0 ? nextId : null);
                setSelectedMemberIds([]);
                setCreateMemberSearch("");
              }}
              className="px-3 py-2 rounded-lg border border-border-strong"
            >
              <option value="">选择成员来源班级</option>
              {teacherClasses.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}（{item.member_count}人）
                </option>
              ))}
            </select>
            <button
              onClick={createAssignmentGroup}
              disabled={creatingGroup || selectedMemberIds.length === 0}
              className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-hover active:bg-primary-active disabled:opacity-60"
            >
              {creatingGroup ? "创建中..." : "创建小组"}
            </button>
          </div>

          {teacherClasses.length === 0 ? (
            <p className="text-xs text-text-secondary">你还没有可用班级，请先到“班级与小组”页面创建班级并让学生入班。</p>
          ) : (
            <div className="rounded-xl border border-border-strong bg-surface-muted p-3 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-semibold text-text">可选成员（班级学生）</p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={selectAllMembers}
                    disabled={classMembers.length === 0}
                    className="text-[11px] px-2 py-1 rounded border border-border-strong hover:bg-surface disabled:opacity-60"
                  >
                    全选
                  </button>
                  <button
                    onClick={clearSelectedMembers}
                    disabled={selectedMemberIds.length === 0}
                    className="text-[11px] px-2 py-1 rounded border border-border-strong hover:bg-surface disabled:opacity-60"
                  >
                    清空
                  </button>
                </div>
              </div>

              {loadingClassMembers ? (
                <p className="text-xs text-text-secondary flex items-center gap-1">
                  <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> 加载班级学生中...
                </p>
              ) : !selectedClassId ? (
                <p className="text-xs text-text-secondary">请选择一个班级后再选择成员。</p>
              ) : classMembers.length === 0 ? (
                <p className="text-xs text-text-secondary">该班级暂无学生。</p>
              ) : (
                <div className="space-y-2">
                  <input
                    value={createMemberSearch}
                    onChange={(e) => setCreateMemberSearch(e.target.value)}
                    placeholder="搜索学生姓名 / 账号 / ID"
                    className="w-full px-3 py-2 rounded-lg border border-border-strong text-xs"
                  />
                  {filteredCreateMembers.length === 0 ? (
                    <p className="text-xs text-text-secondary">未找到匹配学生。</p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {filteredCreateMembers.map((member) => (
                        <label key={member.member_id} className="flex items-center gap-2 text-sm text-text bg-surface border border-border-strong rounded-lg px-3 py-2">
                          <input
                            type="checkbox"
                            checked={selectedMemberIds.includes(member.student_id)}
                            onChange={() => toggleMemberSelection(member.student_id)}
                          />
                          <span className="font-medium">{member.student_name}</span>
                          <span className="text-xs text-text-secondary">({member.student_username})</span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <p className="text-[11px] text-text-secondary">已选择 {selectedMemberIds.length} 人</p>
            </div>
          )}

          {assignmentGroups.length === 0 ? (
            <p className="text-sm text-text-secondary">当前作业暂无小组。</p>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {assignmentGroups.map((group) => (
                  <div key={group.id} className="rounded-xl border border-border-strong bg-surface-muted p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-text">{group.name}</p>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => startEditGroupMembers(group)}
                          disabled={updatingGroupMembers && editingGroupId === group.id}
                          className="text-xs px-2 py-1 rounded-md border border-secondary text-primary hover:bg-secondary disabled:opacity-60"
                        >
                          编辑成员
                        </button>
                        <button
                          onClick={() => deleteAssignmentGroup(group)}
                          disabled={deletingGroupId === group.id || (editingGroupId === group.id && updatingGroupMembers)}
                          className="text-xs px-2 py-1 rounded-md border border-danger/25 text-danger hover:bg-danger-soft disabled:opacity-60"
                        >
                          {deletingGroupId === group.id ? "删除中..." : "删除"}
                        </button>
                      </div>
                    </div>
                    <p className="text-xs text-text-secondary mt-1">成员：{groupMemberText(group)}</p>

                    {editingGroupId === group.id && (
                      <div className="mt-3 rounded-lg border border-secondary bg-secondary p-3 space-y-3">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs font-semibold text-primary">编辑小组成员</p>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={selectAllEditingMembers}
                              disabled={editingMemberCandidates.length === 0 || updatingGroupMembers}
                              className="text-[11px] px-2 py-1 rounded border border-secondary text-primary hover:bg-surface disabled:opacity-60"
                            >
                              全选
                            </button>
                            <button
                              onClick={clearEditingMembers}
                              disabled={editingMemberIds.length === 0 || updatingGroupMembers}
                              className="text-[11px] px-2 py-1 rounded border border-secondary text-primary hover:bg-surface disabled:opacity-60"
                            >
                              清空
                            </button>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-[1fr,1fr] gap-2">
                          <select
                            value={selectedClassId ? String(selectedClassId) : ""}
                            onChange={(e) => {
                              const nextId = Number(e.target.value);
                              setSelectedClassId(Number.isFinite(nextId) && nextId > 0 ? nextId : null);
                              setCreateMemberSearch("");
                              setEditMemberSearch("");
                            }}
                            className="px-2.5 py-2 rounded-md border border-secondary text-xs"
                          >
                            <option value="">切换班级（编辑成员来源）</option>
                            {teacherClasses.map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.name}（{item.member_count}人）
                              </option>
                            ))}
                          </select>
                          <input
                            value={editMemberSearch}
                            onChange={(e) => setEditMemberSearch(e.target.value)}
                            placeholder="搜索姓名 / 账号 / ID"
                            className="px-2.5 py-2 rounded-md border border-secondary text-xs"
                          />
                        </div>

                        {filteredEditingMembers.length === 0 ? (
                          <p className="text-xs text-primary">暂无可选成员，请先选择班级加载学生列表。</p>
                        ) : (
                          <div className="space-y-2 max-h-44 overflow-auto pr-1">
                            {filteredEditingMembers.map((member) => (
                              <label key={`${group.id}_${member.user_id}`} className="flex items-center gap-2 text-xs text-text bg-surface border border-border-strong rounded-md px-2 py-1.5">
                                <input
                                  type="checkbox"
                                  checked={editingMemberIds.includes(member.user_id)}
                                  onChange={() => toggleEditingMemberSelection(member.user_id)}
                                  disabled={updatingGroupMembers}
                                />
                                <span className="font-medium">{member.name || `ID:${member.user_id}`}</span>
                                {member.username && <span className="text-text-secondary">({member.username})</span>}
                              </label>
                            ))}
                          </div>
                        )}

                        <p className="text-[11px] text-primary">已选择 {editingMemberIds.length} 人</p>

                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={cancelEditGroupMembers}
                            disabled={updatingGroupMembers}
                            className="text-xs px-2.5 py-1.5 rounded-md border border-border-strong text-text-secondary hover:bg-surface disabled:opacity-60"
                          >
                            取消
                          </button>
                          <button
                            onClick={() => saveGroupMembers(group)}
                            disabled={updatingGroupMembers}
                            className="text-xs px-2.5 py-1.5 rounded-md bg-primary text-white hover:bg-primary-hover active:bg-primary-active disabled:opacity-60"
                          >
                            {updatingGroupMembers ? "保存中..." : "保存成员"}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="rounded-xl border border-border-strong bg-surface-muted p-4 space-y-2">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                  <h3 className="text-sm font-bold text-text">小组提交进展</h3>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setGroupRiskFilter("all")}
                      className={`text-[11px] px-2 py-1 rounded-full border ${
                        groupRiskFilter === "all"
                          ? "bg-text border-text text-surface"
                          : "bg-surface border-border-strong text-text-secondary"
                      }`}
                    >
                      全部（{groupProgress.length}）
                    </button>
                    <button
                      onClick={() => setGroupRiskFilter("high")}
                      className={`text-[11px] px-2 py-1 rounded-full border ${
                        groupRiskFilter === "high"
                          ? "bg-danger border-danger text-white"
                          : "bg-surface border-danger/25 text-danger"
                      }`}
                    >
                      仅高风险（{highRiskCount}）
                    </button>
                  </div>
                </div>

                {visibleGroupProgress.length === 0 ? (
                  <p className="text-xs text-text-secondary">当前筛选条件下暂无小组。</p>
                ) : (
                  visibleGroupProgress.map((item) => (
                  <div key={item.group.id} className="bg-surface border border-border-strong rounded-lg px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-text">{item.group.name}</p>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            if (item.riskScore >= 2) {
                              setGroupRiskFilter((prev) => (prev === "high" ? "all" : "high"));
                            } else {
                              setGroupRiskFilter("all");
                            }
                          }}
                          title={item.riskScore >= 2 ? "点击切换高风险筛选" : "低风险项，点击恢复全部"}
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
                        </button>
                        {item.latestSubmission ? (
                          <Link
                            to={`/grading/${item.latestSubmission.id}`}
                            className="text-xs font-semibold text-primary hover:underline"
                          >
                            批改最新提交
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
                )))}
              </div>
            </>
          )}
        </section>
      )}

      {user?.role === "student" && submissions.length === 0 && (
        <section className="bg-surface rounded-2xl border border-border p-8">
          <p className="text-sm text-text-secondary mb-2">你还没有该作业的提交记录，点击下方按钮创建第一阶段草稿。</p>
          <p className="text-xs text-text-secondary mb-4">
            {myJoinedGroup
              ? `当前将使用小组模式提交：${myJoinedGroup.name}`
              : "当前使用个人模式提交（如教师已配置作业小组，请先确认你已在小组成员中）。"}
          </p>
          <button
            onClick={startFirstSubmission}
            disabled={starting}
            className="px-5 py-3 bg-primary text-white rounded-xl font-bold hover:bg-primary-hover active:bg-primary-active disabled:opacity-60 flex items-center gap-2"
          >
            {starting ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <FileUp className="w-4 h-4" />} 开始作业
          </button>
        </section>
      )}

      {submissions.length > 0 && (
        <section className="grid grid-cols-1 lg:grid-cols-[2fr,1fr] gap-6">
          <article className="bg-surface rounded-2xl border border-border p-6 space-y-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              {user?.role === "teacher" && (
                <div className="flex items-center gap-2">
                  <label className="text-xs text-text-secondary">筛选小组</label>
                  <select
                    value={teacherGroupFilter}
                    onChange={(e) => setTeacherGroupFilter(e.target.value)}
                    className="px-3 py-2 rounded-lg border border-border-strong text-xs"
                  >
                    <option value="all">全部提交</option>
                    <option value="ungrouped">仅个人提交</option>
                    {assignmentGroups.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex items-center gap-2 flex-wrap">
                {visibleSubmissions
                  .slice()
                  .sort((a, b) => a.phase_index - b.phase_index)
                  .map((submission) => (
                    <button
                      key={submission.id}
                      onClick={() => setActiveSubmissionId(submission.id)}
                      className={`px-3 py-2 text-xs rounded-full border ${
                        activeSubmissionId === submission.id
                          ? "bg-primary border-primary text-white"
                          : "bg-surface border-border-strong text-text-secondary"
                      }`}
                    >
                      阶段 {submission.phase_index + 1}
                      {submission.group_name ? ` · ${submission.group_name}` : ""} · {statusLabel(submission.status)}
                    </button>
                  ))}
                {visibleSubmissions.length === 0 && user?.role === "teacher" && (
                  <p className="text-xs text-text-secondary">当前筛选条件下暂无提交。</p>
                )}
              </div>
              {user?.role === "teacher" && activeSubmission && (
                <Link
                  to={`/grading/${activeSubmission.id}`}
                  className="px-4 py-2 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary-hover active:bg-primary-active"
                >
                  进入评分
                </Link>
              )}
            </div>

            {currentPhase && (
              <div className="rounded-2xl border border-border bg-surface-muted p-4">
                {user?.role === "student" && assignmentNarrative.background && (
                  <div className="rounded-lg border border-secondary bg-secondary px-3 py-2 mb-3">
                    <p className="text-[11px] font-semibold text-primary">当前任务背景</p>
                    <p className="text-xs text-primary mt-1 leading-relaxed">{assignmentNarrative.background}</p>
                  </div>
                )}
                <h2 className="text-sm font-bold text-text mb-3">
                  当前阶段：
                  {currentPhase.title || currentPhase.name || `阶段 ${(activeSubmission?.phase_index ?? 0) + 1}`}
                </h2>
                {currentPhase.title && currentPhase.name && currentPhase.title !== currentPhase.name && (
                  <p className="text-xs text-primary bg-secondary border border-secondary rounded-lg px-3 py-2 mb-3">
                    阶段情境导引：{currentPhase.title}
                  </p>
                )}
                <div className="space-y-3">
                  {(currentPhase.steps || []).map((step, index) => (
                    <div key={`${step.name}_${index}`} className="bg-surface border border-border rounded-xl p-3">
                      <div className="text-sm font-semibold text-text mb-1">
                        {index + 1}. {step.name || step.content || step.description || `步骤 ${index + 1}`}
                      </div>
                      {step.content && step.content !== step.name && (
                        <p className="text-xs text-primary mb-2">情境承接：{step.content}</p>
                      )}
                      {step.description && (
                        <p className="text-xs text-text-secondary mb-2">
                          <span className="font-semibold text-text">学习支架：</span>
                          {step.description}
                        </p>
                      )}
                      {Array.isArray(step.checkpoints) && step.checkpoints.length > 0 && (
                        <ul className="text-xs text-text-secondary space-y-1">
                          {step.checkpoints.map((cp, cpIdx) => (
                            <li key={`${cp.content}_${cpIdx}`} className="flex items-start gap-2">
                              <Circle className="w-3 h-3 mt-0.5 text-text-muted" />
                              <span>
                                <span className="font-semibold text-text">提交证据：</span>
                                {cp.content}
                                {cp.evidence_type ? `（${evidenceTypeLabel(cp.evidence_type)}）` : ""}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeSubmission?.group_name && (
              <div className="rounded-2xl border border-secondary bg-secondary p-4">
                <p className="text-xs text-primary">当前提交模式</p>
                <p className="text-sm font-semibold text-primary mt-1">小组提交：{activeSubmission.group_name}</p>
                <p className="text-xs text-primary mt-1">
                  成员：
                  {(activeSubmission.group_members || [])
                    .map((member) => member.name || member.username || `ID:${member.user_id}`)
                    .join("、") || "未配置"}
                </p>
              </div>
            )}

            <div className="space-y-3">
              <label className="text-sm font-semibold text-text">我的提交内容</label>
              {!readOnly && phaseEvidenceHints.length > 0 && (
                <div className="rounded-xl border border-secondary bg-secondary p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold text-primary">阶段证据检查清单</p>
                    <p className="text-[11px] text-primary">
                      已覆盖 {coveredEvidenceCount}/{phaseEvidenceHints.length}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {phaseEvidenceHints.map((hint, idx) => (
                      <button
                        key={`${hint.content}_${idx}`}
                        onClick={() => addHintToSubmission(hint.content)}
                        className="text-[11px] px-2.5 py-1.5 rounded-full border border-secondary bg-surface text-primary hover:bg-secondary"
                        title="点击加入提交内容"
                        type="button"
                      >
                        {hint.content}
                        {hint.evidenceType ? `（${evidenceTypeLabel(hint.evidenceType)}）` : ""}
                      </button>
                    ))}
                  </div>
                  <p className="text-[11px] text-primary">点击条目可快速插入到下方“我的提交内容”。</p>
                </div>
              )}
              <textarea
                value={contentText}
                onChange={(e) => setContentText(e.target.value)}
                rows={10}
                placeholder={
                  phaseEvidenceHints.length
                    ? `请围绕本阶段证据要求填写成果与反思，例如：${phaseEvidenceHints[0].content}`
                    : "请填写你的阶段成果、数据分析与反思。"
                }
                disabled={readOnly}
                className="w-full px-4 py-3 rounded-xl border border-border-strong resize-none disabled:bg-secondary"
              />
            </div>

            <div className="space-y-3">
              <label className="text-sm font-semibold text-text">附件链接</label>
              <div className="grid grid-cols-1 md:grid-cols-[1fr,2fr,auto] gap-2">
                <input
                  value={attachmentName}
                  onChange={(e) => setAttachmentName(e.target.value)}
                  placeholder="附件名称"
                  disabled={readOnly}
                  className="px-3 py-2 rounded-lg border border-border-strong disabled:bg-secondary"
                />
                <input
                  value={attachmentUrl}
                  onChange={(e) => setAttachmentUrl(e.target.value)}
                  placeholder="https://..."
                  disabled={readOnly}
                  className="px-3 py-2 rounded-lg border border-border-strong disabled:bg-secondary"
                />
                <button
                  onClick={addAttachment}
                  disabled={readOnly}
                  className="px-4 py-2 rounded-lg border border-border-strong text-sm font-semibold hover:bg-surface-muted disabled:opacity-60"
                >
                  添加
                </button>
              </div>
              <div className="space-y-2">
                {attachments.length === 0 && <p className="text-xs text-text-secondary">暂无附件链接</p>}
                {attachments.map((item, index) => (
                  <div key={`${item.filename}_${index}`} className="flex items-center justify-between gap-3 bg-surface-muted border border-border rounded-lg px-3 py-2">
                    <a href={item.url} target="_blank" rel="noreferrer" className="text-sm text-primary hover:underline truncate">
                      {item.filename}
                    </a>
                    {!readOnly && (
                      <button
                        onClick={() => removeAttachment(index)}
                        className="text-danger hover:text-danger"
                        title="删除附件"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {!readOnly && (
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={saveDraft}
                  disabled={saving}
                  className="px-4 py-2 rounded-xl border border-border-strong text-sm font-semibold hover:bg-surface-muted disabled:opacity-60 flex items-center gap-2"
                >
                  {saving ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} 保存草稿
                </button>
                <button
                  onClick={submitCurrent}
                  disabled={submitting}
                  className="px-4 py-2 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary-hover active:bg-primary-active disabled:opacity-60 flex items-center gap-2"
                >
                  {submitting ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} 提交本阶段
                </button>
              </div>
            )}
          </article>

          <aside className="space-y-4">
            <div className="bg-surface rounded-2xl border border-border p-5">
              <h3 className="font-bold text-text mb-3">教师反馈</h3>
              {!teacherEvaluation && <p className="text-xs text-text-secondary">当前阶段暂无教师评分反馈。</p>}
              {teacherEvaluation && (
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-text-secondary">等级</span>
                    <span className="font-bold text-primary">{scoreLabel(teacherEvaluation.score_level)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-text-secondary">分值</span>
                    <span className="font-bold text-primary">{teacherEvaluation.score_numeric || "-"}</span>
                  </div>
                  <div className="border-t border-border pt-2">
                    <p className="text-xs text-text-secondary mb-1">评语</p>
                    <p className="text-sm text-text leading-relaxed">{teacherEvaluation.feedback || "暂无"}</p>
                  </div>
                </div>
              )}
            </div>

            <div className="bg-secondary rounded-2xl border border-secondary p-5">
              <h3 className="font-bold text-primary mb-2 flex items-center gap-2">
                <Sparkles className="w-4 h-4" /> 提交建议
              </h3>
              <p className="text-xs text-primary leading-relaxed">
                提交前请核对每个检查点是否有对应证据，避免因为证据缺失影响评价结果。
              </p>
              {activeSubmission && activeSubmission.status === "graded" && (
                <div className="mt-3 text-xs text-success flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> 当前阶段已评分，可继续下一阶段。
                </div>
              )}
            </div>
          </aside>
        </section>
      )}
    </div>
  );
}
