import type {
  AssignmentPhase,
  AssignmentRubricDimension,
  InquiryDepth,
  SchoolStage,
  Subject,
} from "./api";

export type SchoolLevelCN = "小学" | "初中";

export interface LessonStepDraft {
  id: string;
  phaseName: string;
  stepName: string;
  description: string;
  evidence: string;
  evaluationPoints: string;
  lessonTimeSuggestion: string;
}

const FRONT_TO_BACK_SUBJECT_CODE: Record<string, string> = {
  infoTech: "it",
  arts: "art",
  sports: "pe",
};

const BACK_TO_FRONT_SUBJECT_CODE: Record<string, string> = {
  it: "infoTech",
  art: "arts",
  pe: "sports",
};

export function toBackendSubjectCode(frontCode: string): string {
  return FRONT_TO_BACK_SUBJECT_CODE[frontCode] || frontCode;
}

export function toFrontendSubjectCode(backCode: string): string {
  return BACK_TO_FRONT_SUBJECT_CODE[backCode] || backCode;
}

export function schoolLevelToStage(level: SchoolLevelCN): SchoolStage {
  return level === "小学" ? "primary" : "middle";
}

export function stageToSchoolLevel(stage: SchoolStage): SchoolLevelCN {
  return stage === "primary" ? "小学" : "初中";
}

export function gradeIdToNumber(gradeId: string): number {
  if (!gradeId) return 7;
  if (/^p[1-6]$/.test(gradeId)) {
    return Number(gradeId.slice(1));
  }
  if (/^j[7-9]$/.test(gradeId)) {
    return Number(gradeId.slice(1));
  }
  const numeric = Number(gradeId);
  if (Number.isFinite(numeric) && numeric >= 1 && numeric <= 9) {
    return numeric;
  }
  return 7;
}

export function gradeNumberToId(grade: number): string {
  if (grade >= 1 && grade <= 6) return `p${grade}`;
  return `j${Math.min(9, Math.max(7, grade || 7))}`;
}

export function depthToBackend(depth: "basic" | "medium" | "deep" | InquiryDepth): InquiryDepth {
  if (depth === "medium") return "intermediate";
  return depth;
}

export function depthToFrontend(depth: InquiryDepth): "basic" | "medium" | "deep" {
  if (depth === "intermediate") return "medium";
  return depth;
}

function guessEvidenceType(text: string): string {
  if (!text) return "text";
  if (/链接|网址|http|www\./i.test(text)) return "link";
  if (/视频|录像|录音|音频/i.test(text)) return "video";
  if (/图片|照片|图表|截图|海报/i.test(text)) return "image";
  if (/确认|勾选|完成/i.test(text)) return "confirm";
  if (/报告|文档|表格|清单|记录|方案|计划|汇报|问卷|笔记|作业/i.test(text)) return "document";
  return "text";
}

export function lessonStepsToPhases(steps: LessonStepDraft[]): AssignmentPhase[] {
  const groups: Array<{ name: string; steps: LessonStepDraft[] }> = [];

  steps.forEach((step) => {
    const phaseName = step.phaseName.trim() || "学习任务";
    const target = groups.find((item) => item.name === phaseName);
    if (target) {
      target.steps.push(step);
    } else {
      groups.push({ name: phaseName, steps: [step] });
    }
  });

  return groups.map((group, index) => ({
    name: group.name,
    order: index + 1,
    steps: group.steps.map((step) => {
      const checkpoints = [] as Array<{ content: string; evidence_type: string }>;
      if (step.evidence.trim()) {
        checkpoints.push({
          content: step.evidence.trim(),
          evidence_type: guessEvidenceType(step.evidence),
        });
      }
      if (step.evaluationPoints.trim()) {
        checkpoints.push({
          content: step.evaluationPoints.trim(),
          evidence_type: "text",
        });
      }

      return {
        name: step.stepName.trim() || "任务步骤",
        description: step.description.trim() || step.stepName.trim() || "请按要求完成该步骤。",
        checkpoints,
      };
    }),
  }));
}

export function phasesToLessonSteps(phases: AssignmentPhase[]): LessonStepDraft[] {
  if (!Array.isArray(phases) || phases.length === 0) {
    return [];
  }

  const flattened: LessonStepDraft[] = [];
  phases.forEach((phase, phaseIndex) => {
    const phaseName = (phase.title || phase.name || `阶段 ${phaseIndex + 1}`).trim();
    const phaseSteps = Array.isArray(phase.steps) ? phase.steps : [];
    phaseSteps.forEach((step, stepIndex) => {
      const checkpoints = Array.isArray(step.checkpoints) ? step.checkpoints : [];
      const evidence = checkpoints[0]?.content || "";
      const evaluationPoints = checkpoints[1]?.content || "";

      flattened.push({
        id: `step_${phaseIndex + 1}_${stepIndex + 1}`,
        phaseName,
        stepName: step.name || `步骤 ${stepIndex + 1}`,
        description: step.description || "",
        evidence,
        evaluationPoints,
        lessonTimeSuggestion: "1课时",
      });
    });
  });

  return flattened;
}

export function normalizeRubricDimensions(dimensions: AssignmentRubricDimension[] | undefined): AssignmentRubricDimension[] {
  if (!Array.isArray(dimensions)) return [];
  return dimensions
    .map((item, index) => ({
      name: (item.name || `维度${index + 1}`).trim(),
      levels: item.levels,
      description: item.description,
      weight: item.weight,
    }))
    .filter((item) => Boolean(item.name));
}

export function subjectByFrontendCode(subjects: Subject[], code: string): Subject | undefined {
  const backendCode = toBackendSubjectCode(code);
  return subjects.find((subject) => subject.code === backendCode);
}

export function subjectIdToFrontendCode(subjects: Subject[], subjectId: number): string {
  const subject = subjects.find((item) => item.id === subjectId);
  if (!subject) return "";
  return toFrontendSubjectCode(subject.code);
}

export function safeNumber(value: unknown, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return parsed;
}
