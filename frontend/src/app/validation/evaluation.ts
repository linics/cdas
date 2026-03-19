export interface TeacherEvaluationValidationInput {
  rubricDimensions: string[];
  dimensionScores: Record<string, number>;
  feedback: string;
}

export function validateTeacherEvaluation(input: TeacherEvaluationValidationInput): string | null {
  const feedback = input.feedback.trim();
  if (!feedback) return "请填写教师反馈";

  const normalizedRubric = input.rubricDimensions.map((item) => item.trim()).filter(Boolean);
  const providedKeys = Object.keys(input.dimensionScores || {}).map((item) => item.trim()).filter(Boolean);

  if (normalizedRubric.length > 0) {
    const rubricSet = new Set(normalizedRubric);
    const providedSet = new Set(providedKeys);
    if (rubricSet.size !== providedSet.size || normalizedRubric.some((item) => !providedSet.has(item))) {
      return "评分维度必须与量规维度完全一致";
    }
  }

  for (const [name, score] of Object.entries(input.dimensionScores || {})) {
    if (!name.trim()) return "评分维度名称不能为空";
    if (!Number.isFinite(score) || score < 1 || score > 4) return "评分维度分数必须在 1-4 之间";
  }

  return null;
}
