import type {
  AIGenerationMeta,
  Assignment,
  AssignmentCreatePayload,
  AssignmentLessonPlanDraftResponse,
  AssignmentPreviewResponse,
  AssignmentType,
  AssignmentUpdatePayload,
  SchoolStage,
  SubmissionMode,
} from "../lib/api";
import {
  lessonStepsToPhases,
  phasesToLessonSteps,
  type LessonStepDraft,
} from "../lib/mappers";

export interface AssignmentDesignerForm {
  title: string;
  topic: string;
  description: string;
  background_setting: string;
  school_stage: SchoolStage;
  grade: number;
  main_subject_id: number;
  related_subject_ids: number[];
  assignment_type: AssignmentType;
  practical_subtype: "visit" | "simulation" | "observation";
  inquiry_subtype: "literature" | "survey" | "experiment";
  inquiry_depth: "basic" | "intermediate" | "deep";
  submission_mode: SubmissionMode;
  duration_weeks: number;
  deadline: string;
  objectives_json: {
    knowledge: string;
    process: string;
    emotion: string;
  };
  steps: LessonStepDraft[];
  rubric_dimensions: string[];
}

export interface AssignmentDesignerPreviewState {
  background_setting: string;
  objectives_json: AssignmentDesignerForm["objectives_json"];
  steps: LessonStepDraft[];
  rubric_dimensions: string[];
  meta?: AIGenerationMeta;
}

const DEFAULT_STEPS: LessonStepDraft[] = [
  {
    id: "step_1",
    phaseName: "问题提出",
    stepName: "明确探究问题",
    description: "结合情境提出可探究问题，并给出问题边界。",
    evidence: "问题清单与问题陈述",
    evaluationPoints: "问题清晰、可探究、与主题相关",
    lessonTimeSuggestion: "1课时",
  },
  {
    id: "step_2",
    phaseName: "资料与证据",
    stepName: "收集多源证据",
    description: "通过资料检索、调查或实验收集支撑证据。",
    evidence: "资料摘录、问卷记录或实验原始数据",
    evaluationPoints: "证据来源可靠、记录完整",
    lessonTimeSuggestion: "1-2课时",
  },
  {
    id: "step_3",
    phaseName: "分析与建模",
    stepName: "形成解释框架",
    description: "对证据进行整理分析，完成跨学科解释与建模。",
    evidence: "分析图表、推理过程记录",
    evaluationPoints: "分析逻辑严谨、跨学科关联明确",
    lessonTimeSuggestion: "1课时",
  },
  {
    id: "step_4",
    phaseName: "表达与反思",
    stepName: "输出成果并反思",
    description: "完成成果展示，并对过程与结果进行反思。",
    evidence: "成果报告、展示材料、反思文本",
    evaluationPoints: "成果完整、反思具体、改进建议可执行",
    lessonTimeSuggestion: "1课时",
  },
];

function cloneDefaultSteps(): LessonStepDraft[] {
  return DEFAULT_STEPS.map((item) => ({ ...item }));
}

export function defaultRubricNames(type: AssignmentType): string[] {
  if (type === "practical") {
    return ["实践准备", "实践参与", "过程记录", "跨学科运用", "成果表达", "反思能力"];
  }
  if (type === "project") {
    return ["问题分析", "规划协作", "迭代改进", "成果质量", "展示汇报", "复盘反思"];
  }
  return ["问题意识", "方案设计", "探究过程", "结论质量", "反思能力"];
}

export function generationSourceLabel(meta?: AIGenerationMeta): string {
  if (!meta || meta.source === "ai") return "AI生成";
  if (meta.source === "fallback") return "兜底草稿";
  return "混合结果";
}

export function formatAIGenerationMeta(meta?: AIGenerationMeta): string {
  if (!meta) return "";

  const parts: string[] = [`来源：${generationSourceLabel(meta)}`];
  if (meta.stage) {
    parts.push(`阶段：${meta.stage}`);
  }
  if (meta.prompt_id && meta.prompt_version) {
    parts.push(`${meta.prompt_id}@${meta.prompt_version}`);
  } else if (meta.prompt_id) {
    parts.push(meta.prompt_id);
  }
  if (meta.used_rag) {
    parts.push("含RAG上下文");
  }
  if (meta.fallback_reason && meta.fallback_reason !== "none") {
    parts.push(`原因：${meta.fallback_reason}`);
  }
  if (meta.input_truncated) {
    parts.push("已截断输入");
  }
  if (meta.warnings?.length) {
    parts.push(`提示${meta.warnings.length}条`);
  }
  if (meta.selected_chunk_ids?.length) {
    parts.push(`片段${meta.selected_chunk_ids.length}个`);
  }
  if (meta.selected_document_ids?.length) {
    parts.push(`文档${meta.selected_document_ids.length}个`);
  }
  if (meta.upstream_extract_source) {
    parts.push(`抽取：${meta.upstream_extract_source}`);
  }
  if (meta.upstream_extract_fallback_reason) {
    parts.push(`抽取兜底：${meta.upstream_extract_fallback_reason}`);
  }
  return parts.join(" · ");
}

export function assignmentStatusLabel(assignment: Assignment): string {
  if (assignment.is_archived) return "已归档";
  return assignment.is_published ? "已发布" : "草稿";
}

export function splitBackgroundFromProcess(processText: string): { background: string; process: string } {
  const raw = (processText || "").trim();
  if (!raw) {
    return { background: "", process: "" };
  }
  const prefixes = ["背景设定：", "背景设定:"];
  const prefix = prefixes.find((item) => raw.startsWith(item));
  if (!prefix) {
    return { background: "", process: raw };
  }

  const body = raw.slice(prefix.length).trim();
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

  return {
    background: body,
    process: "",
  };
}

export function composeProcessWithBackground(background: string, process: string): string {
  const bg = background.trim();
  const core = process.trim();
  if (bg && core) {
    return `背景设定：${bg}\n${core}`;
  }
  if (bg) {
    return `背景设定：${bg}`;
  }
  return core;
}

export function pickOrKeep<T>(nextValue: T | null | undefined, currentValue: T): T {
  if (nextValue === null || nextValue === undefined) return currentValue;
  if (typeof nextValue === "string" && !nextValue.trim()) return currentValue;
  return nextValue;
}

export function mergeRelatedSubjectIds(nextIds: number[] | undefined, currentIds: number[], mainSubjectId: number): number[] {
  const source = nextIds && nextIds.length ? nextIds : currentIds;
  const seen = new Set<number>();
  const merged: number[] = [];
  for (const id of source) {
    if (!id || id === mainSubjectId || seen.has(id)) continue;
    seen.add(id);
    merged.push(id);
  }
  return merged;
}

export function buildDesignerInitialForm(): AssignmentDesignerForm {
  return {
    title: "",
    topic: "",
    description: "",
    background_setting: "",
    school_stage: "middle",
    grade: 8,
    main_subject_id: 0,
    related_subject_ids: [],
    assignment_type: "inquiry",
    practical_subtype: "visit",
    inquiry_subtype: "literature",
    inquiry_depth: "intermediate",
    submission_mode: "phased",
    duration_weeks: 2,
    deadline: "",
    objectives_json: {
      knowledge: "",
      process: "",
      emotion: "",
    },
    steps: cloneDefaultSteps(),
    rubric_dimensions: defaultRubricNames("inquiry"),
  };
}

export function toDateInputValue(iso: string | null | undefined): string {
  if (!iso) return "";
  if (iso.length >= 10) return iso.slice(0, 10);
  return "";
}

export function scoreStageLabel(stage: SchoolStage): string {
  return stage === "primary" ? "小学" : "初中";
}

export function gradeLabelByStage(stage: SchoolStage, grade: number): string {
  if (stage === "primary") return `${Math.max(1, Math.min(6, grade))}年级`;
  return `${Math.max(1, grade - 6)}年级`;
}

export function buildDesignerFormFromAssignment(assignment: Assignment): AssignmentDesignerForm {
  const processParts = splitBackgroundFromProcess(assignment.objectives_json?.process || "");
  const steps = phasesToLessonSteps(assignment.phases_json);

  return {
    title: assignment.title,
    topic: assignment.topic,
    description: assignment.description || "",
    background_setting: processParts.background,
    school_stage: assignment.school_stage,
    grade: assignment.grade,
    main_subject_id: assignment.main_subject_id,
    related_subject_ids: assignment.related_subject_ids || [],
    assignment_type: assignment.assignment_type,
    practical_subtype: assignment.practical_subtype || "visit",
    inquiry_subtype: assignment.inquiry_subtype || "literature",
    inquiry_depth: assignment.inquiry_depth,
    submission_mode: assignment.submission_mode,
    duration_weeks: assignment.duration_weeks || 2,
    deadline: toDateInputValue(assignment.deadline),
    objectives_json: {
      knowledge: assignment.objectives_json?.knowledge || "",
      process: processParts.process,
      emotion: assignment.objectives_json?.emotion || "",
    },
    steps: steps.length ? steps : cloneDefaultSteps(),
    rubric_dimensions:
      assignment.rubric_json?.dimensions?.map((item) => item.name).filter(Boolean) || defaultRubricNames(assignment.assignment_type),
  };
}

export function buildDesignerPreviewState(
  result: AssignmentPreviewResponse | AssignmentLessonPlanDraftResponse,
  fallbackAssignmentType: AssignmentType,
): AssignmentDesignerPreviewState {
  const processParts = splitBackgroundFromProcess(result.objectives_json?.process || "");
  const steps = phasesToLessonSteps(result.phases_json);
  const rubricDimensions =
    result.rubric_json?.dimensions?.map((item) => item.name).filter(Boolean) || defaultRubricNames(fallbackAssignmentType);

  return {
    background_setting: processParts.background,
    objectives_json: {
      knowledge: result.objectives_json?.knowledge || "",
      process: processParts.process,
      emotion: result.objectives_json?.emotion || "",
    },
    steps: steps.length ? steps : cloneDefaultSteps(),
    rubric_dimensions: rubricDimensions,
    meta: result.meta,
  };
}

export function mergeDesignerFormWithPreview(
  current: AssignmentDesignerForm,
  preview: AssignmentDesignerPreviewState,
): AssignmentDesignerForm {
  return {
    ...current,
    background_setting: preview.background_setting,
    objectives_json: { ...preview.objectives_json },
    steps: preview.steps.map((step) => ({ ...step })),
    rubric_dimensions: [...preview.rubric_dimensions],
  };
}

export function mergeDesignerFormWithLessonPlanDraft(
  current: AssignmentDesignerForm,
  draft: AssignmentLessonPlanDraftResponse,
): AssignmentDesignerForm {
  const processParts = splitBackgroundFromProcess(draft.objectives_json?.process || "");
  const steps = phasesToLessonSteps(draft.phases_json);
  const rubricDimensions =
    draft.rubric_json?.dimensions?.map((item) => item.name).filter(Boolean) || defaultRubricNames(draft.assignment_type);

  return {
    ...current,
    title: pickOrKeep(draft.title, current.title),
    topic: pickOrKeep(draft.topic, current.topic),
    description: pickOrKeep(draft.description, current.description),
    background_setting: pickOrKeep(processParts.background, current.background_setting),
    school_stage: pickOrKeep(draft.school_stage, current.school_stage),
    grade: pickOrKeep(draft.grade, current.grade),
    main_subject_id: pickOrKeep(draft.main_subject_id, current.main_subject_id),
    related_subject_ids: mergeRelatedSubjectIds(
      draft.related_subject_ids,
      current.related_subject_ids,
      pickOrKeep(draft.main_subject_id, current.main_subject_id),
    ),
    assignment_type: pickOrKeep(draft.assignment_type, current.assignment_type),
    practical_subtype: pickOrKeep(draft.practical_subtype, current.practical_subtype),
    inquiry_subtype: pickOrKeep(draft.inquiry_subtype, current.inquiry_subtype),
    inquiry_depth: pickOrKeep(draft.inquiry_depth, current.inquiry_depth),
    submission_mode: pickOrKeep(draft.submission_mode, current.submission_mode),
    duration_weeks: pickOrKeep(draft.duration_weeks, current.duration_weeks),
    deadline: current.deadline,
    objectives_json: {
      knowledge: pickOrKeep(draft.objectives_json?.knowledge, current.objectives_json.knowledge),
      process: pickOrKeep(processParts.process, current.objectives_json.process),
      emotion: pickOrKeep(draft.objectives_json?.emotion, current.objectives_json.emotion),
    },
    steps: steps.length ? steps.map((step) => ({ ...step })) : current.steps,
    rubric_dimensions: rubricDimensions.length ? [...rubricDimensions] : current.rubric_dimensions,
  };
}

export function buildDesignerCreatePayload(
  form: AssignmentDesignerForm,
  referenceDocumentId: number | null,
): AssignmentCreatePayload {
  const phases = lessonStepsToPhases(form.steps);
  const rubricDimensions = (form.rubric_dimensions.length ? form.rubric_dimensions : defaultRubricNames(form.assignment_type))
    .map((name) => name.trim())
    .filter(Boolean)
    .map((name) => ({ name }));

  return {
    title: form.title.trim(),
    topic: form.topic.trim(),
    description: form.description.trim(),
    school_stage: form.school_stage,
    grade: form.grade,
    main_subject_id: form.main_subject_id,
    related_subject_ids: form.related_subject_ids,
    document_id: referenceDocumentId ?? undefined,
    assignment_type: form.assignment_type,
    practical_subtype: form.assignment_type === "practical" ? form.practical_subtype : undefined,
    inquiry_subtype: form.assignment_type === "inquiry" ? form.inquiry_subtype : undefined,
    inquiry_depth: form.inquiry_depth,
    submission_mode: form.submission_mode,
    duration_weeks: form.duration_weeks,
    deadline: form.deadline ? `${form.deadline}T23:59:59` : null,
    objectives_json: {
      knowledge: form.objectives_json.knowledge,
      process: composeProcessWithBackground(form.background_setting, form.objectives_json.process),
      emotion: form.objectives_json.emotion,
    },
    phases_json: phases,
    rubric_json: {
      dimensions: rubricDimensions,
    },
  };
}

export function buildDesignerUpdatePayload(
  form: AssignmentDesignerForm,
  referenceDocumentId: number | null,
): AssignmentUpdatePayload {
  const createPayload = buildDesignerCreatePayload(form, referenceDocumentId);
  return {
    title: createPayload.title,
    topic: createPayload.topic,
    description: createPayload.description,
    document_id: createPayload.document_id ?? null,
    deadline: createPayload.deadline ?? null,
    objectives_json: createPayload.objectives_json,
    phases_json: createPayload.phases_json,
    rubric_json: createPayload.rubric_json,
  };
}
