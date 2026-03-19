import type { AssignmentType, SchoolStage } from "../lib/api";

export interface LessonStepValidationInput {
  phaseName: string;
  stepName: string;
  description: string;
  evidence: string;
}

export interface AssignmentDesignerValidationInput {
  title: string;
  topic: string;
  school_stage: SchoolStage;
  grade: number;
  main_subject_id: number;
  related_subject_ids: number[];
  rubric_dimensions: string[];
  steps: LessonStepValidationInput[];
}

export type AssignmentValidationMode = "save" | "preview" | "publish";

function gradeMatchesStage(stage: SchoolStage, grade: number): boolean {
  if (stage === "primary") return grade >= 1 && grade <= 6;
  return grade >= 7 && grade <= 9;
}

export function defaultRubricNames(type: AssignmentType): string[] {
  if (type === "practical") return ["实践准备", "实践参与", "过程记录", "跨学科运用", "成果表达", "反思能力"];
  if (type === "project") return ["问题分析", "规划协作", "迭代改进", "成果质量", "展示汇报", "复盘反思"];
  return ["问题意识", "方案设计", "探究过程", "结论质量", "反思能力"];
}

export function validateAssignmentDesignerForm(
  form: AssignmentDesignerValidationInput,
  mode: AssignmentValidationMode,
): string | null {
  if (!form.title.trim()) return "请填写作业标题";
  if (!form.topic.trim()) return "请填写探究主题";
  if (!form.main_subject_id) return "请选择主学科";
  if (!gradeMatchesStage(form.school_stage, form.grade)) return "当前年级与学段不匹配";
  if (form.related_subject_ids.includes(form.main_subject_id)) return "融合学科不能包含主学科";
  if (new Set(form.related_subject_ids).size !== form.related_subject_ids.length) return "融合学科不能重复选择";

  if (mode === "save") return null;

  if (form.steps.length < 2) return "至少配置 2 个步骤";
  const invalidStep = form.steps.find(
    (step) => !step.phaseName.trim() || !step.stepName.trim() || !step.description.trim() || !step.evidence.trim(),
  );
  if (invalidStep) return "每个步骤都需要填写阶段、名称、描述和提交证据";

  const rubricNames = form.rubric_dimensions.map((item) => item.trim()).filter(Boolean);
  if (rubricNames.length < 2) return "至少配置 2 个评价维度";
  if (new Set(rubricNames.map((item) => item.toLowerCase())).size !== rubricNames.length) {
    return "评价维度名称不能重复";
  }

  return null;
}
