import { describe, expect, it } from "vitest";

import type { AssignmentLessonPlanDraftResponse } from "../lib/api";
import {
  applyLessonPlanDraft,
  buildDesignerInitialForm,
  buildLessonPlanDraftRequest,
  formatLessonPlanApplySummary,
  type AssignmentDesignerTouchedFields,
} from "./assignment";

function makeDraft(overrides: Partial<AssignmentLessonPlanDraftResponse> = {}): AssignmentLessonPlanDraftResponse {
  return {
    title: "教案生成标题",
    topic: "教案生成主题",
    description: "教案生成描述",
    school_stage: "primary",
    grade: 5,
    main_subject_id: 3,
    related_subject_ids: [4, 5],
    document_id: 91,
    assignment_type: "project",
    practical_subtype: null,
    inquiry_subtype: null,
    inquiry_depth: "deep",
    submission_mode: "once",
    duration_weeks: 6,
    objectives_json: {
      knowledge: "新的知识目标",
      process: "背景设定：新的背景\n行动主线：新的过程",
      emotion: "新的情感目标",
    },
    phases_json: [
      {
        name: "阶段一",
        order: 1,
        steps: [
          {
            name: "步骤一",
            description: "步骤描述",
            checkpoints: [{ content: "提交记录", evidence_type: "document" }],
          },
        ],
      },
    ],
    rubric_json: {
      dimensions: [{ name: "成果质量" }, { name: "合作表现" }],
    },
    source_summary: "来源摘要",
    meta: {
      source: "ai",
      prompt_id: "assignment.lesson_plan",
      prompt_version: "1.0.0",
      used_rag: false,
      fallback_reason: "none",
    },
    ...overrides,
  };
}

describe("assignment lesson plan helpers", () => {
  it("builds lesson-plan request with only touched top-level constraints", () => {
    const form = {
      ...buildDesignerInitialForm(),
      title: "教师自填标题",
      topic: "教师自填主题",
      description: "教师补充说明",
      background_setting: "教师补充背景",
      school_stage: "primary" as const,
      grade: 4,
      main_subject_id: 8,
      related_subject_ids: [2, 6],
      assignment_type: "project" as const,
      inquiry_depth: "deep" as const,
      submission_mode: "once" as const,
      duration_weeks: 5,
    };
    const touched: AssignmentDesignerTouchedFields = {
      title: true,
      topic: true,
      description: true,
      background_setting: true,
      school_stage: true,
      grade: true,
      main_subject_id: true,
      related_subject_ids: true,
      assignment_type: true,
    };

    const payload = buildLessonPlanDraftRequest(form, 12, touched);

    expect(payload).toEqual({
      document_id: 12,
      title: "教师自填标题",
      topic: "教师自填主题",
      description: "教师补充说明",
      background_setting: "教师补充背景",
      school_stage: "primary",
      grade: 4,
      main_subject_id: 8,
      related_subject_ids: [2, 6],
      assignment_type: "project",
    });
  });

  it("only forwards subtype constraints that match the current assignment type", () => {
    const practicalPayload = buildLessonPlanDraftRequest(
      {
        ...buildDesignerInitialForm(),
        assignment_type: "practical",
        practical_subtype: "simulation",
        inquiry_subtype: "survey",
      },
      99,
      {
        assignment_type: true,
        practical_subtype: true,
        inquiry_subtype: true,
      },
    );

    expect(practicalPayload).toEqual({
      document_id: 99,
      assignment_type: "practical",
      practical_subtype: "simulation",
    });

    const inquiryPayload = buildLessonPlanDraftRequest(
      {
        ...buildDesignerInitialForm(),
        assignment_type: "inquiry",
        practical_subtype: "visit",
        inquiry_subtype: "experiment",
      },
      100,
      {
        assignment_type: true,
        practical_subtype: true,
        inquiry_subtype: true,
      },
    );

    expect(inquiryPayload).toEqual({
      document_id: 100,
      assignment_type: "inquiry",
      inquiry_subtype: "experiment",
    });
  });

  it("includes assignment_type when only subtype was touched", () => {
    const practicalPayload = buildLessonPlanDraftRequest(
      {
        ...buildDesignerInitialForm(),
        assignment_type: "practical",
        practical_subtype: "observation",
      },
      101,
      {
        practical_subtype: true,
      },
    );

    expect(practicalPayload).toEqual({
      document_id: 101,
      assignment_type: "practical",
      practical_subtype: "observation",
    });

    const inquiryPayload = buildLessonPlanDraftRequest(
      {
        ...buildDesignerInitialForm(),
        assignment_type: "inquiry",
        inquiry_subtype: "survey",
      },
      102,
      {
        inquiry_subtype: true,
      },
    );

    expect(inquiryPayload).toEqual({
      document_id: 102,
      assignment_type: "inquiry",
      inquiry_subtype: "survey",
    });
  });

  it("preserves explicitly cleared text constraints in lesson-plan request payload", () => {
    const payload = buildLessonPlanDraftRequest(
      {
        ...buildDesignerInitialForm(),
        title: "",
        topic: "",
        description: "",
        background_setting: "",
      },
      55,
      {
        title: true,
        topic: true,
        description: true,
        background_setting: true,
      },
    );

    expect(payload).toEqual({
      document_id: 55,
      title: "",
      topic: "",
      description: "",
      background_setting: "",
    });
  });

  it("sends null main_subject_id when teacher clears the touched override", () => {
    const payload = buildLessonPlanDraftRequest(
      {
        ...buildDesignerInitialForm(),
        main_subject_id: 0,
      },
      56,
      {
        main_subject_id: true,
      },
    );

    expect(payload).toEqual({
      document_id: 56,
      main_subject_id: null,
    });
  });

  it("preserves touched top-level fields while refreshing generated sections", () => {
    const current = {
      ...buildDesignerInitialForm(),
      title: "教师标题",
      topic: "教师主题",
      description: "教师描述",
      school_stage: "middle" as const,
      grade: 8,
      duration_weeks: 3,
      deadline: "2026-04-10",
      objectives_json: {
        knowledge: "旧知识",
        process: "旧过程",
        emotion: "旧情感",
      },
      rubric_dimensions: ["旧量规"],
    };
    const touched: AssignmentDesignerTouchedFields = {
      title: true,
      school_stage: true,
      grade: true,
      duration_weeks: true,
    };

    const result = applyLessonPlanDraft(current, makeDraft(), touched);

    expect(result.form.title).toBe("教师标题");
    expect(result.form.school_stage).toBe("middle");
    expect(result.form.grade).toBe(8);
    expect(result.form.duration_weeks).toBe(3);
    expect(result.form.topic).toBe("教案生成主题");
    expect(result.form.description).toBe("教案生成描述");
    expect(result.form.background_setting).toBe("新的背景");
    expect(result.form.objectives_json.knowledge).toBe("新的知识目标");
    expect(result.form.steps).toHaveLength(1);
    expect(result.form.rubric_dimensions).toEqual(["成果质量", "合作表现"]);
    expect(result.form.deadline).toBe("2026-04-10");
    expect(result.summary.updatedFields).toEqual(
      expect.arrayContaining(["topic", "description", "background_setting", "assignment_type"]),
    );
    expect(result.summary.preservedFields).toEqual(expect.arrayContaining(["title", "school_stage", "grade", "duration_weeks"]));
    expect(result.summary.regeneratedSections).toEqual(["objectives", "steps", "rubric"]);
  });

  it("preserves touched background setting when applying a lesson plan draft", () => {
    const current = {
      ...buildDesignerInitialForm(),
      background_setting: "教师手动修改的背景",
    };
    const touched: AssignmentDesignerTouchedFields = {
      background_setting: true,
    };

    const result = applyLessonPlanDraft(current, makeDraft(), touched);

    expect(result.form.background_setting).toBe("教师手动修改的背景");
    expect(result.summary.updatedFields).not.toContain("background_setting");
    expect(result.summary.preservedFields).toContain("background_setting");
  });

  it("keeps explicitly cleared text fields empty when applying a touched lesson plan draft", () => {
    const current = {
      ...buildDesignerInitialForm(),
      title: "",
      topic: "",
      description: "",
      background_setting: "",
    };
    const touched: AssignmentDesignerTouchedFields = {
      title: true,
      topic: true,
      description: true,
      background_setting: true,
    };

    const result = applyLessonPlanDraft(current, makeDraft(), touched);

    expect(result.form.title).toBe("");
    expect(result.form.topic).toBe("");
    expect(result.form.description).toBe("");
    expect(result.form.background_setting).toBe("");
  });

  it("uses regenerated main subject when a touched override was cleared locally", () => {
    const current = {
      ...buildDesignerInitialForm(),
      main_subject_id: 0,
    };
    const touched: AssignmentDesignerTouchedFields = {
      main_subject_id: true,
    };

    const result = applyLessonPlanDraft(current, makeDraft({ main_subject_id: 9 }), touched);

    expect(result.form.main_subject_id).toBe(9);
    expect(result.summary.preservedFields).not.toContain("main_subject_id");
    expect(result.summary.updatedFields).toContain("main_subject_id");
  });

  it("re-normalizes touched related subjects against the regenerated main subject", () => {
    const current = {
      ...buildDesignerInitialForm(),
      main_subject_id: 3,
      related_subject_ids: [3, 5, 5, 7],
    };
    const touched: AssignmentDesignerTouchedFields = {
      related_subject_ids: true,
    };

    const result = applyLessonPlanDraft(current, makeDraft({ main_subject_id: 5 }), touched);

    expect(result.form.main_subject_id).toBe(5);
    expect(result.form.related_subject_ids).toEqual([3, 7]);
    expect(result.summary.preservedFields).toContain("related_subject_ids");
    expect(result.summary.updatedFields).not.toContain("related_subject_ids");
  });

  it("formats lesson-plan apply summary with updated, preserved, and regenerated details", () => {
    const text = formatLessonPlanApplySummary({
      updatedFields: ["topic", "assignment_type"],
      preservedFields: ["title", "grade"],
      regeneratedSections: ["objectives", "steps", "rubric"],
    });

    expect(text).toContain("已按教案更新：主题、作业类型");
    expect(text).toContain("已保留教师修改：标题、年级");
    expect(text).toContain("已重建：目标、步骤、量规");
  });
});
