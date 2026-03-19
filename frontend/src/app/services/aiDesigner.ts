import { AI_PRESET } from "../data/aiPreset";
import { defaultSteps } from "../data/seed";
import type { LessonStep } from "../data/models";
import type {
  AiDesignInput,
  AiDraftSuggestion,
  AiRefineSuggestion,
  AiServiceError,
} from "../types/ai";

interface ChatCompletionResponse {
  choices?: Array<{
    message?: {
      content?: string;
    };
  }>;
}

const STEP_FIELDS: Array<keyof LessonStep> = [
  "id",
  "phaseName",
  "stepName",
  "learningGoal",
  "teacherActivity",
  "studentActivity",
  "learningSupport",
  "evidence",
  "evaluationPoints",
  "lessonTimeSuggestion",
];

function createError(code: AiServiceError["code"], message: string, status?: number): AiServiceError {
  return { code, message, status };
}

function normalizeText(value: unknown, fallback = ""): string {
  if (typeof value === "string") {
    return value.trim();
  }
  return fallback;
}

function sanitizeStep(step: Partial<LessonStep> | undefined, index: number): LessonStep {
  const fallback = defaultSteps[index % defaultSteps.length];
  return {
    id: normalizeText(step?.id, `ai_step_${index + 1}`),
    phaseName: normalizeText(step?.phaseName, fallback.phaseName),
    stepName: normalizeText(step?.stepName, fallback.stepName),
    learningGoal: normalizeText(step?.learningGoal, fallback.learningGoal),
    teacherActivity: normalizeText(step?.teacherActivity, fallback.teacherActivity),
    studentActivity: normalizeText(step?.studentActivity, fallback.studentActivity),
    learningSupport: normalizeText(step?.learningSupport, fallback.learningSupport),
    evidence: normalizeText(step?.evidence, fallback.evidence),
    evaluationPoints: normalizeText(step?.evaluationPoints, fallback.evaluationPoints),
    lessonTimeSuggestion: normalizeText(step?.lessonTimeSuggestion, fallback.lessonTimeSuggestion),
  };
}

function sanitizeSteps(steps: unknown): LessonStep[] {
  const raw = Array.isArray(steps) ? steps : [];
  if (raw.length === 0) {
    return defaultSteps.slice(0, 4).map((item, index) => sanitizeStep(item, index));
  }

  const normalized = raw
    .slice(0, 8)
    .map((item, index) => sanitizeStep((item ?? {}) as Partial<LessonStep>, index));

  if (normalized.length < 3) {
    return defaultSteps.slice(0, 4).map((item, index) => sanitizeStep(item, index));
  }
  return normalized;
}

function extractJsonText(content: string): string {
  const trimmed = content.trim();
  if (!trimmed) {
    throw createError("PARSE_ERROR", "AI 返回内容为空");
  }

  const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fenced?.[1]) {
    return fenced[1].trim();
  }

  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start >= 0 && end > start) {
    return trimmed.slice(start, end + 1);
  }

  throw createError("PARSE_ERROR", "AI 返回内容不是有效 JSON");
}

function parsePayload(content: string): Record<string, unknown> {
  const jsonText = extractJsonText(content);
  try {
    return JSON.parse(jsonText) as Record<string, unknown>;
  } catch {
    throw createError("PARSE_ERROR", "AI 返回 JSON 解析失败");
  }
}

function buildDraftSystemPrompt(): string {
  return [
    "你是一名中小学跨学科教学设计专家。",
    "请严格返回 JSON，不要输出任何 JSON 之外的文字。",
    "必须使用以下字段：",
    "{",
    '  "title": "string",',
    '  "description": "string",',
    '  "detailedSteps": [',
    "    {",
    '      "id": "string",',
    '      "phaseName": "string",',
    '      "stepName": "string",',
    '      "learningGoal": "string",',
    '      "teacherActivity": "string",',
    '      "studentActivity": "string",',
    '      "learningSupport": "string",',
    '      "evidence": "string",',
    '      "evaluationPoints": "string",',
    '      "lessonTimeSuggestion": "string"',
    "    }",
    "  ]",
    "}",
    "要求：",
    "1. detailedSteps 至少 4 步；",
    "2. 字段内容完整、可执行、中文表达；",
    "3. 与输入的学段、主学科和融合学科一致。",
  ].join("\n");
}

function buildRefineSystemPrompt(): string {
  return [
    "你是一名中小学跨学科教学设计专家。",
    "请严格返回 JSON，不要输出任何 JSON 之外的文字。",
    "只返回字段：",
    "{",
    '  "detailedSteps": [',
    "    {",
    '      "id": "string",',
    '      "phaseName": "string",',
    '      "stepName": "string",',
    '      "learningGoal": "string",',
    '      "teacherActivity": "string",',
    '      "studentActivity": "string",',
    '      "learningSupport": "string",',
    '      "evidence": "string",',
    '      "evaluationPoints": "string",',
    '      "lessonTimeSuggestion": "string"',
    "    }",
    "  ]",
    "}",
    "要求：",
    "1. 保留并优化现有步骤结构；",
    "2. 强化学习支持与评价要点，补齐可观察证据；",
    "3. 至少 3 步。",
  ].join("\n");
}

function buildUserPayload(input: AiDesignInput): string {
  return JSON.stringify(
    {
      schoolLevel: input.schoolLevel,
      gradeName: input.gradeName,
      title: input.title,
      description: input.description,
      mainSubjectName: input.mainSubjectName,
      integratedSubjectNames: input.integratedSubjectNames,
      assignmentTypeName: input.assignmentTypeName,
      depthName: input.depthName,
      crossConceptNames: input.crossConceptNames,
      detailedSteps: input.detailedSteps.map((step) => {
        const mapped: Partial<LessonStep> = {};
        STEP_FIELDS.forEach((field) => {
          mapped[field] = step[field];
        });
        return mapped;
      }),
    },
    null,
    2,
  );
}

async function requestAi(
  mode: "draft" | "refine",
  input: AiDesignInput,
  apiKey: string,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  const key = apiKey.trim();
  if (!key) {
    throw createError("BAD_REQUEST", "请先输入 API Key");
  }

  let response: Response;
  try {
    response = await fetch(`${AI_PRESET.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${key}`,
      },
      body: JSON.stringify({
        model: AI_PRESET.model,
        temperature: 0.4,
        messages: [
          {
            role: "system",
            content: mode === "draft" ? buildDraftSystemPrompt() : buildRefineSystemPrompt(),
          },
          {
            role: "user",
            content: buildUserPayload(input),
          },
        ],
      }),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw createError("NETWORK_ERROR", "请求已取消");
    }
    throw createError("NETWORK_ERROR", "网络异常，请稍后重试");
  }

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw createError("UNAUTHORIZED", "API Key 无效或无权限", response.status);
    }
    if (response.status === 429) {
      throw createError("RATE_LIMIT", "请求过于频繁，请稍后再试", response.status);
    }
    if (response.status >= 500) {
      throw createError("SERVER_ERROR", "AI 服务暂时不可用", response.status);
    }
    throw createError("UNKNOWN", "AI 请求失败", response.status);
  }

  let data: ChatCompletionResponse;
  try {
    data = (await response.json()) as ChatCompletionResponse;
  } catch {
    throw createError("PARSE_ERROR", "AI 返回格式异常");
  }

  const content = data.choices?.[0]?.message?.content;
  if (!content) {
    throw createError("PARSE_ERROR", "AI 返回内容为空");
  }

  return parsePayload(content);
}

export async function generateAiDraft(
  input: AiDesignInput,
  apiKey: string,
  signal?: AbortSignal,
): Promise<AiDraftSuggestion> {
  const payload = await requestAi("draft", input, apiKey, signal);
  return {
    title: normalizeText(payload.title, input.title || "跨学科探究任务"),
    description: normalizeText(payload.description, input.description || "请补充任务描述。"),
    detailedSteps: sanitizeSteps(payload.detailedSteps),
  };
}

export async function refineAiSteps(
  input: AiDesignInput,
  apiKey: string,
  signal?: AbortSignal,
): Promise<AiRefineSuggestion> {
  const payload = await requestAi("refine", input, apiKey, signal);
  return {
    detailedSteps: sanitizeSteps(payload.detailedSteps),
  };
}

export function buildLocalFallback(input: AiDesignInput): AiDraftSuggestion {
  const safeTitle = input.title.trim() || `${input.schoolLevel}${input.mainSubjectName}跨学科探究任务`;
  const safeDescription =
    input.description.trim() ||
    `围绕${input.mainSubjectName}学习目标，联合${input.integratedSubjectNames.join("、") || "相关学科"}开展真实情境探究。`;

  const seed = input.detailedSteps.length >= 3 ? input.detailedSteps : defaultSteps;
  const detailedSteps = seed.slice(0, 6).map((step, index) => {
    const fallback = defaultSteps[index % defaultSteps.length];
    return sanitizeStep(
      {
        ...fallback,
        ...step,
        phaseName: step.phaseName || fallback.phaseName,
        stepName: step.stepName || fallback.stepName,
        learningGoal:
          step.learningGoal ||
          `结合${input.mainSubjectName}核心概念，完成“${step.stepName || fallback.stepName}”并形成可评价证据。`,
        teacherActivity:
          step.teacherActivity ||
          `教师提供${input.assignmentTypeName}任务支架，明确评价标准并进行过程性指导。`,
        studentActivity:
          step.studentActivity ||
          `学生围绕“${step.stepName || fallback.stepName}”开展小组协作，提交过程记录与阶段成果。`,
        learningSupport:
          step.learningSupport ||
          `提供模板、样例与安全提示，支持${input.depthName}层次探究。`,
        evidence: step.evidence || "过程记录、图表/作品、反思文本。",
        evaluationPoints:
          step.evaluationPoints ||
          `评价关注证据完整性、跨学科迁移质量与${input.crossConceptNames[0] || "核心概念"}运用。`,
        lessonTimeSuggestion: step.lessonTimeSuggestion || fallback.lessonTimeSuggestion,
      },
      index,
    );
  });

  return {
    title: safeTitle,
    description: safeDescription,
    detailedSteps,
  };
}

export function shouldAutoFallback(error: AiServiceError): boolean {
  return (
    error.code === "RATE_LIMIT" ||
    error.code === "SERVER_ERROR" ||
    error.code === "NETWORK_ERROR" ||
    error.code === "PARSE_ERROR"
  );
}
