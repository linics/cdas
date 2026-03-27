import { describe, expect, it } from "vitest";

import {
  depthToBackend,
  depthToFrontend,
  gradeIdToNumber,
  gradeNumberToId,
  lessonStepsToPhases,
  normalizeRubricDimensions,
  phasesToLessonSteps,
  schoolLevelToStage,
  stageToSchoolLevel,
  toBackendSubjectCode,
  toFrontendSubjectCode,
} from "./mappers";

describe("mappers", () => {
  it("maps lesson steps to grouped phases with inferred checkpoint evidence types", () => {
    const phases = lessonStepsToPhases([
      {
        id: "step_1",
        phaseName: "阶段一",
        stepName: "收集资料",
        description: "整理校园用水现状",
        evidence: "提交调查报告",
        evaluationPoints: "说明调查方法",
        lessonTimeSuggestion: "1课时",
      },
      {
        id: "step_2",
        phaseName: "阶段一",
        stepName: "补充证据",
        description: "",
        evidence: "http://example.com/record",
        evaluationPoints: "",
        lessonTimeSuggestion: "1课时",
      },
      {
        id: "step_3",
        phaseName: "阶段二",
        stepName: "形成方案",
        description: "完成改进建议",
        evidence: "完成方案草稿",
        evaluationPoints: "勾选完成",
        lessonTimeSuggestion: "1课时",
      },
    ]);

    expect(phases).toEqual([
      {
        name: "阶段一",
        order: 1,
        steps: [
          {
            name: "收集资料",
            description: "整理校园用水现状",
            checkpoints: [
              { content: "提交调查报告", evidence_type: "document" },
              { content: "说明调查方法", evidence_type: "text" },
            ],
          },
          {
            name: "补充证据",
            description: "补充证据",
            checkpoints: [{ content: "http://example.com/record", evidence_type: "link" }],
          },
        ],
      },
      {
        name: "阶段二",
        order: 2,
        steps: [
          {
            name: "形成方案",
            description: "完成改进建议",
            checkpoints: [
              { content: "完成方案草稿", evidence_type: "confirm" },
              { content: "勾选完成", evidence_type: "text" },
            ],
          },
        ],
      },
    ]);
  });

  it("flattens phases back to lesson steps", () => {
    const steps = phasesToLessonSteps([
      {
        name: "阶段一",
        order: 1,
        steps: [
          {
            name: "收集资料",
            description: "整理校园用水现状",
            checkpoints: [
              { content: "提交调查报告", evidence_type: "document" },
              { content: "说明调查方法", evidence_type: "text" },
            ],
          },
        ],
      },
      {
        title: "阶段二",
        name: "阶段二",
        order: 2,
        steps: [
          {
            name: "形成方案",
            description: "",
            checkpoints: [{ content: "完成方案草稿", evidence_type: "document" }],
          },
        ],
      },
    ]);

    expect(steps).toEqual([
      {
        id: "step_1_1",
        phaseName: "阶段一",
        stepName: "收集资料",
        description: "整理校园用水现状",
        evidence: "提交调查报告",
        evaluationPoints: "说明调查方法",
        lessonTimeSuggestion: "1课时",
      },
      {
        id: "step_2_1",
        phaseName: "阶段二",
        stepName: "形成方案",
        description: "",
        evidence: "完成方案草稿",
        evaluationPoints: "",
        lessonTimeSuggestion: "1课时",
      },
    ]);
  });

  it("normalizes rubric dimensions and drops blanks", () => {
    expect(
      normalizeRubricDimensions([
        { name: "  问题意识  ", levels: { excellent: "好" }, weight: 2 },
        { name: "", description: "空白项" },
        { name: "  ", description: "仍然空白" },
        { name: "证据质量", description: "描述" },
      ]),
    ).toEqual([
      { name: "问题意识", levels: { excellent: "好" }, description: undefined, weight: 2 },
      { name: "维度2", levels: undefined, description: "空白项", weight: undefined },
      { name: "证据质量", levels: undefined, description: "描述", weight: undefined },
    ]);
  });

  it("keeps subject and grade helpers stable", () => {
    expect(toBackendSubjectCode("infoTech")).toBe("it");
    expect(toFrontendSubjectCode("pe")).toBe("sports");
    expect(schoolLevelToStage("小学")).toBe("primary");
    expect(stageToSchoolLevel("middle")).toBe("初中");
    expect(gradeIdToNumber("p3")).toBe(3);
    expect(gradeIdToNumber("j8")).toBe(8);
    expect(gradeIdToNumber("bad")).toBe(7);
    expect(gradeNumberToId(5)).toBe("p5");
    expect(gradeNumberToId(10)).toBe("j9");
    expect(depthToBackend("medium")).toBe("intermediate");
    expect(depthToFrontend("intermediate")).toBe("medium");
  });
});
